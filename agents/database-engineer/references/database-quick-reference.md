# Database Quick Reference

> **Scope**: Detection queries and error→fix mappings worth having verbatim at the keyboard. Schema-design and optimization judgment lives in the agent body; general SQL knowledge is assumed.

## Detection Queries (PostgreSQL)

```sql
-- Foreign keys without indexes (the #1 JOIN performance miss)
SELECT c.conrelid::regclass AS table_name, a.attname AS column_name
FROM pg_constraint c
JOIN pg_attribute a ON a.attnum = ANY(c.conkey) AND a.attrelid = c.conrelid
WHERE c.contype = 'f'
AND NOT EXISTS (
  SELECT 1 FROM pg_index i
  WHERE i.indrelid = c.conrelid AND a.attnum = ANY(i.indkey)
);

-- Tables without primary keys
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name NOT IN (
  SELECT table_name FROM information_schema.table_constraints
  WHERE constraint_type = 'PRIMARY KEY'
);

-- Stale statistics after bulk loads (planner row counts up to 50x off)
SELECT tablename, last_analyze, n_live_tup
FROM pg_stat_user_tables
WHERE (last_analyze < NOW() - INTERVAL '7 days' OR last_analyze IS NULL)
  AND n_live_tup > 10000
ORDER BY n_live_tup DESC;

-- Slowest queries (requires pg_stat_statements)
SELECT query, mean_exec_time, calls, total_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC LIMIT 20;
```

Fix for stale statistics: `ANALYZE <table>;` immediately after bulk loads; for high-write tables set `autovacuum_analyze_scale_factor = 0.01`.

## Error → Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `duplicate key value violates unique constraint` | INSERT of duplicate PK/unique key | `INSERT ... ON CONFLICT DO UPDATE` |
| `deadlock detected` | Transactions locking in opposite order | Consistent lock ordering; `FOR UPDATE SKIP LOCKED` for queues |
| `could not serialize access due to concurrent update` | SERIALIZABLE conflict | Retry loop with exponential backoff |
| `remaining connection slots reserved for replication` | Pool exhausted | PgBouncer or application-side pool |
| `operator does not exist: jsonb = integer` | JSONB type mismatch | Cast: `(attributes->>'count')::integer` |
