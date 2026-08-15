# Performance Comment Patterns to Detect and Fix

<!-- no-pair-required: document header and scope block, not an individual failure mode -->

> **Scope**: Temporal and relative-comparison comment failure modes in performance-sensitive
> code: caching, batching, concurrency limits, and algorithmic complexity notes.
> **Version range**: All languages; Go goroutine pool patterns, Python asyncio, JS Promise.all
> **Generated**: 2026-04-16

---

## Overview

Performance code attracts the worst temporal comments. "Optimized for speed", "now uses
caching", "faster than the old approach" — all describe a past comparison that no longer
exists. The pattern appears across caching layers, batch processors, query optimizers, and
concurrency machinery. The skill must recognize vague performance praise and replace it with
measurable, specific descriptions of what the optimization does.

---

## Pattern Catalog

<!-- no-pair-required: section heading organizing multiple failure mode blocks -->

### State the Specific Mechanism and Tuning Knobs

**Detection**:
```bash
grep -rn '//.*optimized.*\(for\|performance\|speed\|efficiency\)\|//.*improved.*performance' \
  --include="*.go" --include="*.py" --include="*.ts" --include="*.js" -i
rg '//\s*(optimized|improved|enhanced|tuned) (for )?(performance|speed|efficiency|throughput)' -i
```

**Signal**:
```go
// Optimized for performance using goroutine pool
func processQueue(items []Item) {
    sem := make(chan struct{}, 10)
    for _, item := range items {
        sem <- struct{}{}
        go func(it Item) {
            defer func() { <-sem }()
            process(it)
        }(item)
    }
}

// Improved performance by caching database results
cache := sync.Map{}
```

**Why this matters**: "Optimized for performance" says nothing the reader can act on. What was the
bottleneck? What does the optimization constrain? What happens if the limit changes?

**Preferred action**: State the specific mechanism (pool size, semaphore limit, cache capacity) and how to tune it.

**Preferred action**:
```go
// Limits concurrent processing to 10 goroutines to cap memory and CPU usage.
// Increase cap if CPU is underutilized; decrease if memory pressure is high.
func processQueue(items []Item) {
    sem := make(chan struct{}, 10)
    for _, item := range items {
        sem <- struct{}{}
        go func(it Item) {
            defer func() { <-sem }()
            process(it)
        }(item)
    }
}

// In-process cache avoids repeated DB roundtrips for the same key within a request.
cache := sync.Map{}
```

---

### State Parallelism Model and Constraints

**Preferred action**: State the parallelism model, its constraints, and any side-effect warnings.

**Detection**:
```bash
grep -rn '//.*faster than\|//.*more efficient than\|//.*quicker than\|//.*slower than' \
  --include="*.go" --include="*.py" --include="*.ts" --include="*.js" -i
rg '//\s*(faster|more efficient|quicker|better) than' -i
```

**Signal**:
```python
# Faster than sequential processing
results = await asyncio.gather(*[process(item) for item in items])

# More efficient than loading all records at once
def get_users_paginated(page_size=100):
    offset = 0
    while True:
        batch = db.query(User).limit(page_size).offset(offset).all()
        if not batch:
            break
        yield batch
        offset += page_size
```

**Why this matters**: "Faster than sequential" is historical context. How much faster? Under what
conditions? The reader needs to know what the parallelism model is and its trade-offs.

**Preferred action**: State the parallelism model, its constraints, and any side-effect warnings.

**Preferred action**:
```python
# Runs all process() calls concurrently; total time bounded by the slowest item.
# Do not use if process() has side effects that must not interleave.
results = await asyncio.gather(*[process(item) for item in items])

# Streams users in batches of 100 to avoid loading the full table into memory.
<!-- no-pair-required: good example inside a Fix code block; the enclosing anti-pattern section carries the Do instead marker -->
# Caller iterates yielded batches; do not materialize with list() on large tables.
def get_users_paginated(page_size=100):
    offset = 0
    while True:
        batch = db.query(User).limit(page_size).offset(offset).all()
        if not batch:
            break
        yield batch
        offset += page_size
```

---

### Document Cache Eviction, TTL, and Miss Behavior

**Detection**:
```bash
grep -rn '//.*now.*cach\|//.*added.*cach\|//.*cach.*now\|//.*cach.*added' \
  --include="*.go" --include="*.py" --include="*.ts" --include="*.js" -i
rg '//\s*(now uses|added|uses) (a |the )?(cache|caching|LRU|Redis)' -i
```

**Signal**:
```go
// Now uses Redis cache to avoid repeated database lookups
func getUser(id int) (*User, error) {
    if v, ok := cache.Get(id); ok {
        return v.(*User), nil
    }
    // ...fetch from DB and set cache
}

// Added LRU cache for improved response times
var lru = lrucache.New(1000)
```

**Why this matters**: "Now uses" describes migration history. The reader needs cache eviction policy,
TTL, capacity, and what happens on cache miss.

**Preferred action**: State the eviction policy, TTL, capacity, and miss behavior.

**Preferred action**:
```go
// Returns cached user within 5-minute TTL; fetches from DB on miss and repopulates cache.
func getUser(id int) (*User, error) {
    if v, ok := cache.Get(id); ok {
        return v.(*User), nil
    }
    // ...fetch from DB and set cache
}

// LRU cache capped at 1000 entries; evicts least-recently-used when full.
var lru = lrucache.New(1000)
```

---

### Describe Current Loading Strategy

**Preferred action**: Describe the current loading strategy (eager, batch size, index type) and the problem it prevents.

**Detection**:
```bash
grep -rn '//.*optimized.*quer\|//.*quer.*optimized\|//.*N\+1\|//.*reduced.*quer' \
  --include="*.go" --include="*.py" --include="*.ts" --include="*.js" -i
rg '//\s*(optimized|reduced|fixed) (query|queries|N\+1|database)' -i
```

**Signal**:
```python
# Optimized to avoid N+1 query problem
<!-- no-pair-required: bad example inside a What it looks like code block; the enclosing anti-pattern section carries the Do instead marker -->
users = User.objects.prefetch_related('orders').filter(active=True)

# Reduced database queries by batching inserts
def bulk_insert(records):
    db.bulk_create(records, batch_size=500)
```

**Why this matters**: "Optimized to avoid" is history. The current behavior — eager loading, batch
size, indexed column — is what matters.

**Preferred action**: Describe the current loading strategy (eager, batch size, index type) and the problem it prevents.

**Preferred action**:
```python
# Eager-loads orders in a single query to prevent one query per user in downstream loops.
users = User.objects.prefetch_related('orders').filter(active=True)

# Inserts in batches of 500 to stay within DB parameter limits and reduce roundtrips.
def bulk_insert(records):
    db.bulk_create(records, batch_size=500)
```

---

### State Complexity Class of Current Structure

**Detection**:
```bash
grep -rn '//.*replaced.*\(better\|improve\|faster\|performance\)\|//.*\(better\|improve\|faster\|performance\).*replaced' \
  --include="*.go" --include="*.py" --include="*.ts" --include="*.js" -i
rg '//\s*replaced .* (for|with) better (performance|speed|efficiency)' -i
```

**Signal**:
```typescript
// Replaced array.find() with Map for better performance on large collections
const userIndex = new Map(users.map(u => [u.id, u]));

// Replaced polling with WebSocket for improved real-time performance
const ws = new WebSocket(endpoint);
```

**Why this matters**: Describes what was replaced instead of what the current structure provides.

**Preferred action**: State the complexity class or behavior of the current structure and when it matters.

**Preferred action**:
```typescript
// Map provides O(1) lookup by ID; array.find() is O(n) and slow for collections > 1000.
const userIndex = new Map(users.map(u => [u.id, u]));

// WebSocket pushes updates from server; avoids 1-second polling latency for real-time feeds.
const ws = new WebSocket(endpoint);
```

---

### State the Memory Bound Directly

**Detection**:
```bash
grep -rn '//.*reduced.*memory\|//.*less.*memory\|//.*memory.*reduced\|//.*lower.*memory' \
  --include="*.go" --include="*.py" --include="*.ts" --include="*.js" -i
rg '//\s*(reduced|lower|less|minimal) memory' -i
```

**Signal**:
```go
// Reduced memory usage by streaming instead of loading all data
func exportCSV(w io.Writer, db *DB) error {
    rows, _ := db.Query("SELECT * FROM users")
    defer rows.Close()
    enc := csv.NewWriter(w)
    for rows.Next() {
        // write row
    }
    return rows.Err()
}
```

**Why this matters**: "Reduced memory usage" compared to what? State the bound, not the reduction.

**Preferred action**: State the memory bound directly (O(1) per item, capped at X MB, or O(n) total).

**Preferred action**:
```go
// Streams rows directly to w; memory usage is O(1) per row, not O(total rows).
// Callers should buffer w if writing to a slow sink (network, disk).
func exportCSV(w io.Writer, db *DB) error {
    rows, _ := db.Query("SELECT * FROM users")
    defer rows.Close()
    enc := csv.NewWriter(w)
    for rows.Next() {
        // write row
    }
    return rows.Err()
}
```

---

## Error-Fix Mappings

| Pattern Found | Root Cause | Rewrite Strategy |
|---------------|------------|------------------|
| `// Optimized for performance` | Vague praise | State the specific mechanism (pool size, batch size, cache TTL) |
| `// Faster than X` | Relative comparison | State complexity class or measured bound |
| `// Now uses cache` | Capability addition | State eviction policy, TTL, capacity, miss behavior |
| `// Reduced N+1` | Query fix narrative | Describe current loading strategy (eager, batch size) |
| `// Replaced X with Y for speed` | Replacement narrative | State why current structure is better (O(1) vs O(n)) |
| `// Reduced memory usage` | Vague claim | State memory bound (O(1), O(n), capped at Xmb) |

---

## Pattern Table

| Pattern | When to Rewrite | Replacement Focus |
|---------|----------------|-------------------|
| `faster / slower` | Always | State complexity class or measured latency |
| `more efficient` | Always | Specify what resource (CPU, memory, I/O) and how much |
| `cache / caching` | When describing addition | State TTL, capacity, eviction, miss behavior |
| `batch` | When describing improvement | State batch size and why it was chosen |
| `goroutine pool / semaphore` | When describing optimization | State concurrency limit and tuning guidance |
| `streaming` | When comparing to bulk load | State memory bound (O(1) per item vs O(n) total) |

---

## Detection Commands Reference

```bash
# Vague performance praise
grep -rn '//.*\b(optimized|improved|enhanced)\b.*\b(performance|speed|efficiency)\b' \
  --include="*.go" --include="*.py" --include="*.ts" --include="*.js" -i

# Relative comparisons
grep -rn '//.*\b(faster|slower|quicker|more efficient|less efficient)\b' \
  --include="*.go" --include="*.py" --include="*.ts" --include="*.js" -i

# Cache addition language
grep -rn '//.*\b(now uses|added|use)\b.*\b(cache|caching|LRU|Redis|Memcached)\b' \
  --include="*.go" --include="*.py" --include="*.ts" --include="*.js" -i

# Memory vagueness
grep -rn '//.*\b(reduced|less|lower|minimal)\b.*\bmemory\b' \
  --include="*.go" --include="*.py" --include="*.ts" --include="*.js" -i
```

---

## See Also

- `preferred-patterns.md` — complete temporal failure mode catalog across all languages
- `error-handling-patterns.md` — temporal patterns in error handling code
- `go-comment-patterns.md` — Go-specific temporal patterns (goroutines, context, generics)
