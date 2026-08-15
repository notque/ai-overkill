# Data Warehouse Performance Reference

> **Scope**: Partitioning, clustering, incremental processing, materialized views
> **Version range**: BigQuery, Snowflake, Redshift (ra3+), PostgreSQL 14+

Performance problems are almost always partitioning/clustering failures. Address partitioning before any other optimization.

## Pattern Table: Partitioning Strategies

| Table Type | Partition Key | Cluster/Sort Keys | When to Re-evaluate |
|------------|---------------|------------------|---------------------|
| Event/fact tables | Date of event (`event_date`) | User ID, event type | If partitions > 4000 (BigQuery limit) |
| Dimension tables | None (full scans < 1GB are cheap) | Natural key | When table exceeds 1GB |
| CDC/audit tables | Load date (`_loaded_at`) | Entity type, entity ID | When querying by entity dominates |
| Large dimension (SCD Type 2) | Effective date or current flag | Natural key | When history queries are slow |

---

## Correct Patterns

### Partition Pruning Verification

Always verify that your queries actually use partition pruning. "Partitioned table" doesn't guarantee partition pruning — queries must include a filter on the partition column.

```sql
-- BigQuery: INFORMATION_SCHEMA shows bytes processed AFTER query
SELECT
  creation_time,
  total_bytes_processed,
  total_slot_ms,
  query
FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY)
  AND query LIKE '%fact_orders%'
ORDER BY total_bytes_processed DESC;

-- PostgreSQL: EXPLAIN shows which partitions are accessed
EXPLAIN (ANALYZE, BUFFERS)
SELECT SUM(amount)
FROM fact_orders
WHERE order_date BETWEEN '2026-03-01' AND '2026-03-31';
-- Look for "Partitions selected: 31 (of 1826)"
-- If it shows all partitions, add partition column to WHERE clause
```

Partitioning only helps if queries filter on the partition column.

---

### Incremental Processing with Date Watermark

```sql
-- Process only new records since last run
-- Used when source delivers append-only records

-- Step 1: Identify the watermark
SELECT MAX(order_created_at) AS last_processed
FROM fact_orders;

-- Step 2: Extract only new records
SELECT *
FROM raw.orders
WHERE created_at > (SELECT MAX(order_created_at) FROM fact_orders)
  AND created_at < NOW() - INTERVAL '5 minutes'  -- Safety buffer for late arrivals
```

```python
# Airflow: pass watermark between tasks
def extract_incremental(ds, **kwargs):
    ti = kwargs['ti']
    last_processed = ti.xcom_pull(task_ids='get_watermark', key='last_processed')
    # Extract records newer than last_processed
```

Incremental processing reduces compute 90%+. The 5-minute buffer prevents dropping late-arriving events.

---

### Materialized View for Repeated Aggregations

```sql
-- PostgreSQL 14+: materialized view for expensive aggregations
CREATE MATERIALIZED VIEW daily_revenue_by_segment AS
SELECT
  DATE_TRUNC('day', order_date) AS day,
  customer_segment,
  SUM(total_amount) AS revenue,
  COUNT(DISTINCT customer_id) AS unique_customers,
  COUNT(*) AS order_count
FROM fact_orders fo
JOIN dim_customer dc ON fo.customer_id = dc.customer_id
WHERE fo.order_date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY 1, 2
WITH DATA;

-- Index the materialized view for fast dashboard queries
CREATE INDEX idx_daily_rev_day ON daily_revenue_by_segment(day);
CREATE INDEX idx_daily_rev_segment ON daily_revenue_by_segment(customer_segment);

-- Refresh strategy: full refresh nightly (or use CONCURRENTLY for zero-downtime)
REFRESH MATERIALIZED VIEW CONCURRENTLY daily_revenue_by_segment;
```

Pre-computes aggregation; dashboard queries hit the view in milliseconds.

---

### dbt Incremental Materialization with Partition Overwrite

```sql
-- models/fact_orders.sql — incremental with partition overwrite
{{
  config(
    materialized='incremental',
    unique_key='order_id',
    partition_by={
      "field": "order_date",
      "data_type": "date",
      "granularity": "day"
    },
    cluster_by=["customer_segment", "status"],
    incremental_strategy='insert_overwrite'  -- BigQuery partition overwrite
  )
}}

SELECT
  order_id,
  customer_id,
  order_date,
  status,
  total_amount,
  customer_segment
FROM {{ source('raw', 'orders') }}
LEFT JOIN {{ ref('dim_customer') }} USING (customer_id)

{% if is_incremental() %}
  WHERE order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)
  -- Reprocess last 3 days to catch late-arriving records and updates
{% endif %}
```

`insert_overwrite` with date window handles late-arriving data. 3-day window catches late records and status updates.

---

## Pattern Catalog

### Add Partition Filters to All Partitioned Table Queries
**Detection**:
```sql
-- BigQuery: find expensive queries without partition filter
SELECT
  query,
  total_bytes_processed / POW(1024, 3) AS gb_processed,
  total_slot_ms / 1000 AS slot_seconds
FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND total_bytes_processed > 1e10  -- > 10GB queries
ORDER BY total_bytes_processed DESC
LIMIT 20;
```

```bash
# PostgreSQL: Find queries doing sequential scans on large tables
grep -n "Seq Scan on fact_" query_plans/*.txt
```

**Signal**:
```sql
-- Dashboard query that scans ALL data despite date-partitioned table
SELECT customer_segment, SUM(amount)
FROM fact_orders
WHERE status = 'completed'  -- No date filter!
GROUP BY customer_segment
```

**Why**: 3-year daily table = 1095 partitions scanned. 1TB instead of 1GB. BigQuery: $5/query instead of $0.005.

**Fix**:
```sql
SELECT customer_segment, SUM(amount)
FROM fact_orders
WHERE order_date >= CURRENT_DATE - INTERVAL 30 DAY  -- Add partition filter
  AND status = 'completed'
GROUP BY customer_segment
```

---

### Add Cluster Keys Before Joining Large Tables
**Detection**:
```bash
# PostgreSQL: Look for hash joins on large tables (sort-merge join is cheaper with sort keys)
grep -n "Hash Join\|Nested Loop" explain_outputs/*.txt | grep -v "Seq Scan on small"

# BigQuery: Look for shuffle bytes in query plan
# In BigQuery console: Query Plan tab → look for large "Write" steps
```

**Signal**:
```sql
-- fact_orders (1B rows) joined to dim_customer (10M rows)
-- Neither table clustered on customer_id
SELECT fo.*, dc.segment
FROM fact_orders fo
JOIN dim_customer dc ON fo.customer_id = dc.customer_id
WHERE fo.order_date = CURRENT_DATE
```

**Why**: Without clustering, join shuffles all data across nodes. On 1B rows = multi-minute shuffle.

**Fix**:
```sql
-- BigQuery: add clustering to both tables
ALTER TABLE fact_orders CLUSTER BY customer_id;
ALTER TABLE dim_customer CLUSTER BY customer_id;

-- After clustering, joins on customer_id co-locate data, avoiding shuffle
```

---

### Schedule Materialized View Refreshes Off-Peak
**Detection**:
```bash
# PostgreSQL: Find REFRESH MATERIALIZED VIEW in scheduled jobs
grep -rn "REFRESH MATERIALIZED VIEW" cron/ scripts/ airflow/ --include="*.py" --include="*.sql"

# Check refresh timing against peak query windows
grep -rn "schedule_interval\|cron" dags/ --include="*.py" \
  | grep -E "REFRESH|materialized"
```

**Signal**:
```python
# Airflow DAG that runs at 9 AM — peak dashboard hour
refresh_mv = PostgresOperator(
    sql="REFRESH MATERIALIZED VIEW daily_revenue_by_segment;",
    schedule_interval="0 9 * * *",  # 9 AM = peak load
)
```

**Why**: Non-CONCURRENT refresh takes exclusive lock blocking all queries. 9 AM = peak dashboard hour.

**Fix**:
```python
# Schedule during off-peak hours
schedule_interval="0 4 * * *"  # 4 AM

# Or use CONCURRENTLY to avoid locking (requires unique index)
sql="REFRESH MATERIALIZED VIEW CONCURRENTLY daily_revenue_by_segment;"
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `Query exceeded resource limits` (BigQuery) | Full table scan on partitioned table | Add partition filter matching the partition column |
| `STATEMENT_TIMEOUT` (PostgreSQL) | Query exceeds statement timeout, usually full scan | Add index or partition filter; increase timeout only as last resort |
| `cannot refresh materialized view concurrently without a unique index` | `CONCURRENTLY` requires unique index | Add unique index on the materialized view PK before using CONCURRENTLY |
| `dbt incremental: no partitions selected` | Watermark condition selects no rows on first run | Add `{% if is_incremental() %}` guard around the date filter |
| Incremental pipeline producing duplicates | Late-arriving data falls outside watermark window | Widen the reprocessing window (e.g., 3 days instead of 1 day) |

---

## Detection Commands Reference

```sql
-- BigQuery: expensive queries last 7 days
SELECT query, total_bytes_processed / 1e9 AS gb
FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
ORDER BY total_bytes_processed DESC LIMIT 20;
```

```bash
# PostgreSQL: tables without partition definitions
SELECT tablename FROM pg_tables
WHERE schemaname = 'public'
AND tablename NOT IN (SELECT relname FROM pg_partitioned_table JOIN pg_class ON oid = partrelid);

# dbt: models using full table materialization (candidates for incremental)
grep -rn "materialized='table'" models/ --include="*.sql" -l
```

---

## See Also

- `sql.md` — MERGE and partition overwrite patterns for idempotent loading
- `testing.md` — Row count reconciliation and freshness checks to validate pipeline output
