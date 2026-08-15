# Peewee Query Patterns & Optimization

> **Scope**: N+1 prevention, prefetch patterns, index strategy, and SQLite-specific query optimization using Peewee ORM.
> **Version range**: Peewee 3.x, SQLite 3.35+ (generated columns), Python 3.8+
> **Generated**: 2026-04-14 — verify against current Peewee changelog

---

## Overview

Most common Peewee/SQLite performance failures: N+1 queries and missing FK indexes. `prefetch()` and `join()` solve N+1 differently — wrong choice produces cartesian products or extra round-trips. Use `EXPLAIN QUERY PLAN` for diagnosis.

---

## Pattern Table

| Pattern | Peewee Version | Use When | Avoid When |
|---------|---------------|----------|------------|
| `prefetch(Model)` | 3.0+ | Loading reverse FK relations in lists | Loading single object or filtering on related |
| `join(Model)` | 3.0+ | Filtering/ordering on related field | Loading many related objects (cartesian product) |
| `select_related()` | 3.0+ | Loading FK (forward) in loops | Reverse relations (use prefetch instead) |
| `join_lazy(Model)` | 3.15+ | Optional related load, query-time decision | Always-needed related data |
| `SQL('EXPLAIN QUERY PLAN ...')` | all | Diagnosing full table scans | N/A |
| `WITHOUT ROWID` table | SQLite 3.8.2+ | Small lookup tables, composite PK | Tables needing rowid access patterns |

---

## Correct Patterns

### Prefetch for Reverse FK Relations

`prefetch()` executes exactly 2 queries: one for primary model, one per prefetched relation. Attached in Python, not via JOIN.

```python
# Load users with all their posts — 2 queries total
users = User.select().prefetch(Post)
for user in users:
    for post in user.posts:  # No additional queries
        print(post.title)
```

**Why**: Without prefetch, each `user.posts` access executes a SELECT. 100 users = 101 queries. Prefetch: always 2.

---

### Join for Filter/Order on Related Field

Use `join()` to filter or order by a related field, not to load related data.

```python
# Find users who have published posts — efficient single query
users = (User
    .select()
    .join(Post)
    .where(Post.status == 'published')
    .distinct())

# Order users by most recent post date
users = (User
    .select(User, fn.MAX(Post.created_at).alias('last_post'))
    .join(Post, JOIN.LEFT_OUTER)
    .group_by(User.id)
    .order_by(fn.MAX(Post.created_at).desc()))
```

**Why**: `prefetch()` can't filter — it loads all related rows. Use `join()` when related table drives WHERE or ORDER BY.

---

### WAL Mode for Read-Heavy Workloads

Enable WAL for concurrent readers during writes. Set once at connection time.

```python
from peewee import SqliteDatabase

db = SqliteDatabase('app.db', pragmas={
    'journal_mode': 'wal',       # Allow concurrent reads during writes
    'cache_size': -1024 * 64,    # 64MB cache
    'foreign_keys': 1,            # Enforce FK constraints
    'synchronous': 'normal',      # Balance safety/speed (vs. 'full')
})
```

**Why**: Default journal mode blocks all readers during writes. WAL allows concurrent reads, essential for web apps.

---

### Targeted SELECT
<!-- no-pair-required: positive pattern section, title contains 'avoid' triggering false positive -->

Specify only needed columns to avoid loading TEXT/BLOB when only IDs or names needed.

```python
# Bad: loads all columns including large blob fields
users = User.select()

# Good: load only what the template needs
users = User.select(User.id, User.username, User.email)

# Named tuples for clean attribute access on partial selects
from peewee import ModelSelect
users = User.select(User.id, User.username).namedtuples()
for u in users:
    print(u.username)  # Works without model overhead
```

---

## Pattern Catalog
<!-- no-pair-required: section header with no content -->

### Use Prefetch to Load Related Data

**Detection**:
```bash
# Find .select() followed by attribute access on related model in loop
grep -rn '\.select()' --include="*.py" -A 10 | grep -B 5 'for .* in '
# More targeted: find ForeignKeyField backrefs accessed in for loops
rg 'for \w+ in \w+\.\w+:' --type py
rg '\.select\(\)' --type py -A 5 | grep '\.\w+\.\w+'
```

**Preferred action:** Use `User.select().prefetch(Post)` to load all related data in 2 queries instead of N+1.

**Signal**:
```python
users = User.select()
for user in users:
    # BAD: executes SELECT for every iteration
    post_count = user.posts.count()
    latest = user.posts.order_by(Post.created_at.desc()).first()
```

**Why this matters**: Each `user.posts` access executes a SELECT. 500 users = 1001 queries. Latency grows linearly.

**Preferred action:** Use `prefetch()` (2 queries) or annotate with subquery (1 query):

```python
# Option 1: prefetch + Python aggregation
users = User.select().prefetch(Post)
for user in users:
    posts = list(user.posts)  # Already loaded — no query
    post_count = len(posts)
    latest = max(posts, key=lambda p: p.created_at, default=None)

# Option 2: annotate with subquery at SELECT time
from peewee import fn, ModelSelect
post_count_q = (Post
    .select(fn.COUNT(Post.id))
    .where(Post.user == User.id)
    .scalar_subquery())

users = User.select(User, post_count_q.alias('post_count'))
for user in users:
    print(user.post_count)  # Available as attribute, 1 query total
```

---

### Index Every ForeignKeyField

**Detection**:
```bash
# Find ForeignKeyField definitions — verify each has an index
grep -rn 'ForeignKeyField' --include="*.py"
# Check if index=True is absent
rg 'ForeignKeyField\([^)]*\)' --type py | grep -v 'index=True'
```

**Preferred action:** Add `index=True` to every `ForeignKeyField` and declare composite indexes in `Meta.indexes` for multi-column query patterns.

**Signal**:
```python
class Post(Model):
    user = ForeignKeyField(User, backref='posts')  # No index!
    category = ForeignKeyField(Category, backref='posts')  # No index!
```

**Why this matters**: Peewee does NOT auto-index ForeignKeyField (unlike Django). Full table scan at 10k+ rows.

**Preferred action:** `index=True` on every FK, composite indexes for multi-column filters:

```python
class Post(Model):
    user = ForeignKeyField(User, backref='posts', index=True)
    category = ForeignKeyField(Category, backref='posts', index=True)

    class Meta:
        # Composite index for queries that filter on both
        indexes = (
            (('user', 'created_at'), False),  # Non-unique
        )
```

**Version note**: Peewee 3.0+ changed FK index behavior. In 2.x, FKs had implicit indexes.
In 3.x you must declare `index=True` explicitly.

---

### Use Join or Prefetch, Not Both

**Detection**:
```bash
rg '\.prefetch\(' --type py -A 2 | grep '\.join\('
grep -rn 'prefetch' --include="*.py" -A 3 | grep 'join'
```

**Preferred action:** Use `join()` alone when filtering on a related field, or `prefetch()` alone when loading related data. Never combine both for the same model.

**Signal**:
```python
# BUG: join + prefetch on same model produces cartesian product rows
users = (User
    .select()
    .join(Post)  # Creates JOIN
    .prefetch(Post))  # Also prefetches — duplicates Post rows
```

**Why this matters**: `join()` + `prefetch()` on same model are mutually exclusive. Combining duplicates Post rows.

**Preferred action:** One strategy per query — `join()` for filter/order, `prefetch()` for loading:

```python
# For filtering: use join only, no prefetch
users = User.select().join(Post).where(Post.status == 'published').distinct()

# For loading related data: use prefetch only, no join
users = User.select().prefetch(Post)
```

---

### Select Only Needed Columns

**Detection**:
```bash
# Model.select() with no arguments — loads all columns
rg '\.select\(\s*\)' --type py
grep -rn '\.select()' --include="*.py" | grep -v 'select(.*\.'
```

**Preferred action:** Specify only the columns you need: `Post.select(Post.id, Post.title, Post.created_at)`.

**Signal**:
```python
# Loads all columns including large TEXT/BLOB fields
posts = Post.select()  # Includes body, attachments_json, etc.
for post in posts:
    print(post.title)  # Only needed title
```

**Why this matters**: SQLite reads entire row pages. Unused large columns waste cache and I/O.

**Preferred action:**

```python
posts = Post.select(Post.id, Post.title, Post.created_at)
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `OperationalError: database is locked` | Concurrent writes or long read transaction | Enable WAL: `PRAGMA journal_mode=WAL`; shorten transaction scope |
| `DoesNotExist: {Model} instance matching query does not exist` | `.get()` on empty result set | Use `.get_or_none()` or wrap in `try/except DoesNotExist` |
| `IntegrityError: FOREIGN KEY constraint failed` | FK enforcement not enabled by default | Add `'foreign_keys': 1` to pragma dict or call `db.execute_sql('PRAGMA foreign_keys=ON')` |
| `AttributeError: 'SelectQuery' object has no attribute 'posts'` | Accessing backref before query executes | Call `list()` or iterate the queryset first |
| `ProgrammingError: not all arguments converted during string formatting` | Using `%s` placeholders (not `?`) in raw SQL | SQLite uses `?` as placeholder: `db.execute_sql('SELECT ? + ?', (1, 2))` |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| Peewee 3.0 | FK indexes no longer implicit | Add `index=True` to all ForeignKeyField |
| Peewee 3.15 | `join_lazy()` added | Prefer over manual deferred loading patterns |
| SQLite 3.35 | `DROP COLUMN` supported | Before 3.35, column removal required table rebuild |
| SQLite 3.37 | `STRICT` table mode | Enforces type affinity — opt-in per table |
| SQLite 3.38 | `unixepoch()` function | Use instead of strftime for Unix timestamps |

---

## Detection Commands Reference

```bash
# N+1 loop access pattern
rg 'for \w+ in \w+\.\w+:' --type py

# Missing FK index
rg 'ForeignKeyField\([^)]*\)' --type py | grep -v 'index=True'

# Cartesian product risk (join + prefetch same model)
rg '\.prefetch\(' --type py -A 2 | grep '\.join\('

# Bare select() calls (potential overfetch)
rg '\.select\(\s*\)' --type py

# No WAL mode configured
rg 'SqliteDatabase' --type py -A 5 | grep -v 'journal_mode'
```

---

## See Also

- `peewee-testing.md` — in-memory SQLite test isolation patterns
- `peewee-migrations.md` — Playhouse migrate and SQLite ALTER limitations
- [Peewee Querying Docs](https://docs.peewee-orm.com/en/latest/peewee/querying.html)
