# Peewee Testing Patterns

> **Scope**: In-memory SQLite databases, test isolation, fixture patterns, and migration testing with Peewee ORM.
> **Version range**: Peewee 3.x, Python 3.8+, pytest 7+
> **Generated**: 2026-04-14 — verify against current pytest-peewee releases

---

## Overview

Critical failure mode: shared database state bleeds between tests with module-level db instances. Fix: `:memory:` SQLite per-test via `bind_ctx()`. Works cleanly with pytest fixtures.

---

## Pattern Table

| Pattern | Use When | Avoid When |
|---------|----------|------------|
| `SqliteDatabase(':memory:')` | Unit tests, fast isolation | Integration tests needing file persistence |
| `db.bind_ctx(models)` | Per-test isolation via fixture | Module-level setup (state leaks) |
| `db.create_tables(models)` | Schema creation in fixture | Production code (use migrations) |
| `TestModel.truncate_table()` | Clearing data between tests | Full isolation (use bind_ctx instead) |
| `atomic()` rollback | Preserving db state across tests | Tests that commit intentionally |

---

## Correct Patterns

### Per-Test Isolation with `bind_ctx()`

Fresh in-memory db per test. Models re-bind at test start, dropped at end.

```python
import pytest
from peewee import SqliteDatabase
from myapp.models import User, Post, Comment

ALL_MODELS = [User, Post, Comment]

@pytest.fixture
def db():
    """Fresh in-memory database for each test."""
    test_db = SqliteDatabase(':memory:', pragmas={'foreign_keys': 1})
    with test_db.bind_ctx(ALL_MODELS):
        test_db.create_tables(ALL_MODELS)
        yield test_db
        # Tables auto-dropped when in-memory db is garbage collected

def test_user_creation(db):
    user = User.create(username='alice', email='alice@example.com')
    assert User.select().count() == 1
    assert user.id is not None

def test_post_belongs_to_user(db):
    user = User.create(username='bob', email='bob@example.com')
    post = Post.create(user=user, title='Hello')
    # FK constraint enforced because foreign_keys=1 pragma is set
    assert post.user_id == user.id
```

**Why**: `bind_ctx()` temporarily rebinds models to test db without changing `Meta.database`. Thread-safe, works with parallel execution.

---

### Fixture Factories for Related Data

Factory functions avoid repetitive setup:

```python
@pytest.fixture
def make_user(db):
    """Factory for creating users with defaults."""
    def factory(username='testuser', email=None, **kwargs):
        email = email or f'{username}@example.com'
        return User.create(username=username, email=email, **kwargs)
    return factory

@pytest.fixture
def make_post(db, make_user):
    """Factory for creating posts, creates user if not provided."""
    def factory(title='Test Post', user=None, **kwargs):
        if user is None:
            user = make_user()
        return Post.create(title=title, user=user, **kwargs)
    return factory

def test_post_count_per_user(db, make_user, make_post):
    alice = make_user('alice')
    make_post(user=alice)
    make_post(user=alice)
    make_post(user=alice)

    # Verify the prefetch path works correctly
    users = User.select().prefetch(Post)
    user = [u for u in users if u.username == 'alice'][0]
    assert len(list(user.posts)) == 3
```

---

### Testing Transactions and Rollback

```python
def test_atomic_rollback_on_error(db):
    """Verify atomic() rolls back all changes when exception raised."""
    user = User.create(username='alice', email='alice@example.com')

    with pytest.raises(ValueError):
        with db.atomic():
            Post.create(user=user, title='First post')
            Post.create(user=user, title='Second post')
            raise ValueError('intentional rollback')

    # Both posts should be rolled back
    assert Post.select().count() == 0

def test_savepoint_partial_rollback(db):
    """Verify nested atomic() uses savepoints for partial rollback."""
    user = User.create(username='alice', email='alice@example.com')

    with db.atomic():
        Post.create(user=user, title='Outer post')
        try:
            with db.atomic():  # Creates savepoint
                Post.create(user=user, title='Inner post')
                raise ValueError('rollback inner only')
        except ValueError:
            pass  # Inner savepoint rolled back, outer continues

    # Only the outer post committed
    assert Post.select().count() == 1
    assert Post.get().title == 'Outer post'
```

---

### Testing Migration Scripts

```python
import pytest
from peewee import SqliteDatabase, Model, CharField, TextField
from playhouse.migrate import SqliteMigrator, migrate

@pytest.fixture
def pre_migration_db():
    """Database in the state before a migration runs."""
    db = SqliteDatabase(':memory:')

    class OldUser(Model):
        username = CharField()
        # No 'email' column yet — simulates pre-migration state
        class Meta:
            database = db
            table_name = 'user'

    db.create_tables([OldUser])
    OldUser.create(username='alice')
    yield db

def test_add_email_column_migration(pre_migration_db):
    migrator = SqliteMigrator(pre_migration_db)
    migrate(
        migrator.add_column('user', 'email', TextField(null=True))
    )

    # Verify column exists and existing rows have NULL
    cursor = pre_migration_db.execute_sql('SELECT email FROM user')
    rows = cursor.fetchall()
    assert len(rows) == 1
    assert rows[0][0] is None  # NULL for pre-existing rows
```

---

## Pattern Catalog
<!-- no-pair-required: section header with no content -->

### Use Per-Test Database Fixtures (State Leakage)

**Detection**:
```bash
# Find test files using module-level database setup
grep -rn 'db = SqliteDatabase' --include="test_*.py"
grep -rn 'setUpClass\|setup_module' --include="test_*.py" -A 5 | grep 'create_tables'
rg 'SqliteDatabase.*test' --type py | grep -v 'fixture\|conftest'
```

**Preferred action:** Use a per-test `db` fixture with `bind_ctx()` so each test gets a fresh in-memory database.

**Signal**:
```python
# conftest.py — WRONG: shared database across all tests
db = SqliteDatabase(':memory:')
db.bind([User, Post])
db.create_tables([User, Post])

def test_create_user():
    User.create(username='alice')

def test_user_count():
    # FAILS if test_create_user ran first — count is 1, not 0
    assert User.select().count() == 0
```

**Why this matters**: Module-level `:memory:` db persists for session. Rows bleed between tests. Passes locally, fails in CI (different ordering).

**Preferred action:** Fresh `:memory:` per test via `pytest.fixture` with `bind_ctx()`:

```python
# conftest.py — CORRECT: fresh database per test
@pytest.fixture(autouse=True)
def db():
    test_db = SqliteDatabase(':memory:', pragmas={'foreign_keys': 1})
    with test_db.bind_ctx([User, Post]):
        test_db.create_tables([User, Post])
        yield test_db
```

---

### Use In-Memory Databases for Tests

**Detection**:
```bash
# Find SqliteDatabase with file path in test files
grep -rn 'SqliteDatabase(' --include="test_*.py" | grep -v ':memory:'
rg 'SqliteDatabase\([^:)]' --type py --glob 'test_*'
```

**Preferred action:** Always use `SqliteDatabase(':memory:')` for unit tests, or a `tempfile.mkstemp()` path for integration tests with automatic cleanup.

**Signal**:
```python
# Uses real app.db in tests — modifies production data
db = SqliteDatabase('app.db')

def test_delete_user():
    User.delete().where(User.username == 'test').execute()
    # Deletes from real database!
```

**Why this matters**: Parallel runs or teardown failures corrupt the production db file.

**Preferred action:** `:memory:` for unit tests. `tempfile.mkstemp()` for integration tests:

```python
import tempfile
import os

@pytest.fixture
def file_db():
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    db = SqliteDatabase(path)
    with db.bind_ctx([User, Post]):
        db.create_tables([User, Post])
        yield db
    os.unlink(path)
```

---

### Enable FK Constraints in Test DB

**Detection**:
```bash
rg 'SqliteDatabase.*:memory:' --type py | grep -v 'foreign_keys'
grep -rn "SqliteDatabase(':memory:')" --include="*.py" -A 3 | grep -v 'foreign_keys'
```

**Preferred action:** Always pass `pragmas={'foreign_keys': 1}` when creating the test database so FK violations surface in tests, not in production.

**Signal**:
```python
# SQLite disables FK checks by default — tests pass but prod fails
db = SqliteDatabase(':memory:')  # No foreign_keys pragma

def test_post_without_user():
    # This succeeds in test — SQLite allows orphaned FK
    Post.create(user_id=99999, title='Orphan')
    # In production with foreign_keys=1 this raises IntegrityError
```

**Why this matters**: SQLite disables FK constraints by default. Tests pass with invalid data that production rejects.

**Preferred action:**

```python
db = SqliteDatabase(':memory:', pragmas={'foreign_keys': 1})
```

---

### Use Fresh bind_ctx() Database Per Test

**Detection**:
```bash
grep -rn 'truncate_table\|DELETE FROM' --include="test_*.py"
rg '\.truncate_table\(\)' --type py --glob '*test*'
```

**Signal**:
```python
def teardown_function():
    # Risky: only clears data, not schema changes or sequence state
    User.truncate_table()
    Post.truncate_table()
```

**Why this matters**: `truncate_table()` clears rows but not schema. Migration test schema changes persist. Autoincrement counters grow.

**Preferred action**: Use `bind_ctx()` with `:memory:` — db is garbage-collected between tests, resetting everything.

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `OperationalError: no such table: {name}` | Model not bound to test DB or table not created | Add model to `bind_ctx()` list and `create_tables()` call |
| `IntegrityError: FOREIGN KEY constraint failed` in test only | FK enabled in test but disabled in app config | Enable `foreign_keys=1` pragma in both test and app DB |
| `OperationalError: table {name} already exists` | Module-level setup running multiple times | Switch to per-test fixture with `bind_ctx()` |
| `AttributeError: 'NoneType' object has no attribute 'execute'` | Model's database is None after bind_ctx exits | Test is accessing model outside the `with` block |
| `PeeweeException: Model class is already using a different database` | Conflicting bind calls from multiple fixtures | Use single `autouse=True` db fixture; don't bind in multiple places |

---

## Detection Commands Reference

```bash
# Module-level database in tests (state leakage risk)
grep -rn 'db = SqliteDatabase' --include="test_*.py"

# Tests using file databases instead of :memory:
rg 'SqliteDatabase\([^:]' --type py --glob 'test_*'

# Missing FK pragma in test databases
grep -rn "':memory:'" --include="*.py" -A 3 | grep -v 'foreign_keys'

# truncate_table in tests (should use bind_ctx instead)
rg '\.truncate_table\(\)' --type py --glob '*test*'

# create_tables outside of fixtures (module-level setup)
grep -rn 'create_tables' --include="test_*.py" | grep -v 'def '
```

---

## See Also

- `peewee-query-patterns.md` — N+1 prevention and index strategy
- `peewee-migrations.md` — Playhouse migrate patterns and SQLite ALTER limitations
- [Peewee Testing Docs](https://docs.peewee-orm.com/en/latest/peewee/testing.html)
