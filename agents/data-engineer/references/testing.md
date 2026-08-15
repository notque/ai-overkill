# Data Pipeline Testing Reference

> **Scope**: dbt tests, Great Expectations, data quality gates, pipeline contract testing
> **Version range**: dbt Core 1.5+ / Great Expectations 0.18+ / Airflow 2.6+

Good pipeline tests assert grain, referential integrity, freshness, and business-rule violations -- not just "column is not null."

## Pattern Table: Test Layers

| Layer | Tool | What It Catches | When to Run |
|-------|------|-----------------|-------------|
| Schema tests | dbt schema YAML | Null PKs, duplicate IDs, referential integrity | After every transform |
| Data tests | dbt `data` tests | Business rule violations, cross-table consistency | After every transform |
| Freshness assertions | dbt source freshness | Stale data from upstream | Before pipeline start |
| Statistical tests | Great Expectations | Distribution drift, unexpected nulls, range violations | After staging load |
| Row count reconciliation | SQL assertion | Extract count matches load count | After every load step |

---

## Correct Patterns

### dbt Schema Tests — Minimum Viable Set

```yaml
# models/schema.yml
version: 2

models:
  - name: fact_orders
    description: "One row per order line item per day"
    columns:
      - name: order_line_id
        description: "Surrogate key — unique identifier for this fact row"
        tests:
          - unique              # No duplicate fact rows
          - not_null            # Every row has an identifier

      - name: customer_id
        tests:
          - not_null            # Orphaned facts are silent errors
          - relationships:      # Referential integrity
              to: ref('dim_customer')
              field: customer_id

      - name: order_date
        tests:
          - not_null
          - dbt_utils.accepted_range:  # dbt-utils package
              min_value: "'2020-01-01'"
              max_value: "current_date + interval '1 day'"

      - name: status
        tests:
          - accepted_values:
              values: ['pending', 'confirmed', 'shipped', 'delivered', 'cancelled']
```

Minimum: `unique` + `not_null` on PKs, `relationships` on FKs. Missing referential integrity allows orphaned facts.

---

### dbt Singular Tests for Business Rules

```sql
-- tests/assert_no_negative_revenue.sql
-- Fails if any row has negative revenue (data quality issue in source)
SELECT
  order_id,
  total_amount
FROM {{ ref('fact_orders') }}
WHERE total_amount < 0
  AND status != 'refund'  -- Refunds are legitimately negative
```

```sql
-- tests/assert_orders_grain.sql
-- Fails if fact table grain is violated (duplicate order_line_id per day)
SELECT
  order_line_id,
  order_date,
  COUNT(*) AS row_count
FROM {{ ref('fact_orders') }}
GROUP BY order_line_id, order_date
HAVING COUNT(*) > 1
```

Singular tests enforce business rules as SQL. Returns rows = test fails.

---

### dbt Source Freshness Configuration

```yaml
# models/sources.yml
version: 2

sources:
  - name: raw
    database: prod
    schema: raw_ingestion
    freshness:
      warn_after: {count: 6, period: hour}    # Warning: stale > 6h
      error_after: {count: 24, period: hour}   # Error: stale > 24h
    loaded_at_field: _extracted_at

    tables:
      - name: orders
        freshness:
          warn_after: {count: 1, period: hour}   # Orders data: tighter SLA
          error_after: {count: 4, period: hour}

      - name: events
        freshness:
          warn_after: {count: 30, period: minute}
          error_after: {count: 2, period: hour}
```

```bash
# Run freshness check before pipeline execution
dbt source freshness --select source:raw
# If this fails, don't run downstream transforms — they'd work on stale data
```

Stale data = silent errors. Freshness checks fail loudly before transforms run.

---

### Row Count Reconciliation in Airflow

```python
# dags/pipeline_with_reconciliation.py
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook

def reconcile_row_counts(source_table, target_table, ds, **kwargs):
    """Verify row count in source matches target after load."""
    hook = PostgresHook(postgres_conn_id='warehouse')

    source_count = hook.get_first(
        f"SELECT COUNT(*) FROM {source_table} WHERE DATE(created_at) = %s",
        parameters=(ds,)
    )[0]

    target_count = hook.get_first(
        f"SELECT COUNT(*) FROM {target_table} WHERE order_date = %s",
        parameters=(ds,)
    )[0]

    if source_count != target_count:
        raise ValueError(
            f"Row count mismatch: {source_table}={source_count}, "
            f"{target_table}={target_count} for {ds}"
        )

reconcile_task = PythonOperator(
    task_id='reconcile_counts',
    python_callable=reconcile_row_counts,
    op_kwargs={'source_table': 'raw.orders', 'target_table': 'dw.fact_orders'},
)
```

Simplest quality check. Catches truncated loads, missed partitions, duplicates. Implement before complex tests.

---

## Pattern Catalog

### Add Minimum Test Coverage to Every dbt Model
**Detection**:
```bash
# Models with no tests at all
dbt ls --resource-type model --output name | sort > /tmp/all_models.txt
dbt ls --resource-type test --output name \
  | sed 's/^[^.]*\.\([^.]*\)\..*/\1/' \
  | sort -u > /tmp/tested_models.txt
comm -23 /tmp/all_models.txt /tmp/tested_models.txt

# Quick check: ratio of tests to models
echo "Models: $(dbt ls --resource-type model | wc -l)"
echo "Tests: $(dbt ls --resource-type test | wc -l)"
```

**Signal**: Models in `models/` directory with no corresponding entries in `schema.yml`, or schema.yml entries with empty `tests:` lists.

**Why**: Without PK tests, duplicate/null keys corrupt downstream joins (2x or 0.5x metrics, no error).

**Fix**: `unique` + `not_null` on primary key as absolute minimum.

---

### Test Mart Models for Business Rule Correctness
**Detection**:
```bash
# Count tests by model path
dbt ls --resource-type test --output json \
  | python3 -c "
import json, sys, collections
tests = [json.loads(l) for l in sys.stdin if l.strip()]
paths = [t.get('path', '') for t in tests]
for path_prefix in ['staging', 'intermediate', 'marts']:
    count = sum(1 for p in paths if path_prefix in p)
    print(f'{path_prefix}: {count} tests')
"
```

**Signal**: Many tests on `models/staging/` but zero tests on `models/marts/` or `models/reporting/`.

**Why**: Mart models introduce aggregation/joins that produce wrong numbers even with clean source data.

**Fix**: Singular tests on every mart: grain, no negative revenue, referential integrity.

---

### Apply not_null Tests Only to Required Columns
**Detection**:
```bash
# Find not_null tests on potentially nullable columns
grep -rn "not_null" models/ --include="*.yml" -B2 \
  | grep -E "name: (description|notes|middle_name|phone|optional)"
```

**Signal**:
```yaml
- name: customer_notes
  tests:
    - not_null  # Customers often don't have notes
```

**Why**: `not_null` on optional columns fails valid data. Engineers skip always-failing tests, eroding suite confidence.

**Fix**: `not_null` only on logically required columns. Use `dbt_utils.not_null_proportion` for usually-populated:

```yaml
- name: customer_notes
  tests:
    - dbt_utils.not_null_proportion:
        at_least: 0.0  # No constraint — just document it's nullable
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `Compilation Error: column "x" does not exist` | dbt schema test references column not in model | Check column name spelling; run `dbt compile` to catch before `test` |
| `Test unique_fact_orders failed: 42 rows returned` | Duplicate fact rows in grain | Investigate source duplication; add dedup step before load |
| `Source raw.orders is past the error freshness threshold` | Upstream extraction pipeline stalled | Check extraction DAG; do not run downstream transforms on stale data |
| `Great Expectations: expect_column_values_to_be_between failed` | Out-of-range values in column (negative amounts, future dates) | Validate source data; add filter or alert in extraction step |
| `dbt test: Row count reconciliation failed` | Load truncated or missed partitions | Check load task logs; verify partition coverage before marking success |

---

## Detection Commands Reference

```bash
# Run all dbt tests
dbt test

# Run only schema tests (fast)
dbt test --select test_type:schema

# Run freshness checks
dbt source freshness

# Count test coverage by layer
dbt ls --resource-type test | wc -l
dbt ls --resource-type model | wc -l

# Find untested models
dbt ls --resource-type model --output name | sort > /tmp/models.txt
dbt ls --resource-type test --output name | sed 's/\.[^.]*$//' | sort -u > /tmp/tested.txt
comm -23 /tmp/models.txt /tmp/tested.txt

# Run Great Expectations suite
great_expectations checkpoint run my_pipeline_checkpoint
```

---

## See Also

- `sql.md` — Idempotent SQL patterns (MERGE, partition overwrite) that tests should validate
- `performance.md` — Query optimization for test queries on large warehouse tables
