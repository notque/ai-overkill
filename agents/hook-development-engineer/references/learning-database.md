# Learning Database Reference (v2)

Complete schema, operations, and confidence tracking for the unified learning database.

## Database Location

`~/.claude/learning/learning.db` (SQLite with WAL mode for concurrent access)

## Schema

```sql
CREATE TABLE learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    category TEXT NOT NULL,        -- error | pivot | review | design | debug | gotcha | effectiveness
    confidence REAL DEFAULT 0.5,
    tags TEXT,                     -- comma-separated
    source TEXT NOT NULL,          -- error-learner | manual | precompact-archive | migrated:*
    source_detail TEXT,
    project_path TEXT,
    session_id TEXT,
    observation_count INTEGER DEFAULT 1,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    first_seen TEXT DEFAULT (datetime('now')),
    last_seen TEXT DEFAULT (datetime('now')),
    graduated_to TEXT,             -- target agent/skill when knowledge is embedded
    error_signature TEXT,          -- MD5 hash for error pattern matching
    error_type TEXT,               -- missing_file, permissions, syntax_error, etc.
    fix_type TEXT,                 -- manual | auto | skill | agent
    fix_action TEXT,               -- specific command/skill/agent name
    UNIQUE(topic, key)
);

-- FTS5 full-text search with porter stemming
CREATE VIRTUAL TABLE learnings_fts USING fts5(
    topic, key, value, tags,
    content='learnings', content_rowid='id',
    tokenize='porter unicode61'
);

CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    start_time TEXT,
    end_time TEXT,
    project_path TEXT,
    files_modified INTEGER DEFAULT 0,
    tools_used INTEGER DEFAULT 0,
    errors_encountered INTEGER DEFAULT 0,
    errors_resolved INTEGER DEFAULT 0,
    learnings_captured INTEGER DEFAULT 0,
    summary TEXT
);
```

---

## Core API (`hooks/lib/learning_db_v2.py`)

### Record a learning

```python
from learning_db_v2 import record_learning

result = record_learning(
    topic="multiple_matches",
    key="edit-replace-all",
    value="Edit tool fails with 'found N matches' → Use replace_all=True",
    category="error",
    confidence=0.9,
    source="manual",
    error_signature="a3b5c7d9e1f2g3h4",
    error_type="multiple_matches",
    fix_type="auto",
    fix_action="use_replace_all",
)
# Returns: {"topic": ..., "key": ..., "is_new": True/False, ...}
```

If `topic+key` already exists: increments observation_count, keeps higher confidence, updates value only if new is longer.

### Query learnings

```python
from learning_db_v2 import query_learnings

patterns = query_learnings(
    category="error",
    min_confidence=0.7,
    project_path="/home/user/project",
    limit=10,
)
```

### Full-text search

```python
from learning_db_v2 import search_learnings

results = search_learnings("goroutine OR channel", min_confidence=0.5)
```

### Look up error solution

```python
from learning_db_v2 import lookup_error_solution

solution = lookup_error_solution("Found 3 matches for old_string")
if solution:
    print(f"Fix: {solution['value']}")
```

### Confidence operations

```python
from learning_db_v2 import boost_confidence, decay_confidence

new_conf = boost_confidence("multiple_matches", "edit-replace-all", delta=0.12)
new_conf = decay_confidence("multiple_matches", "edit-replace-all", delta=0.18)
```

### Statistics

```python
from learning_db_v2 import get_stats

stats = get_stats()
# Returns: {
#   "total_learnings": 42,
#   "by_category": {"error": 20, "design": 15, ...},
#   "by_topic": {"multiple_matches": 5, ...},
#   "high_confidence": 28,
#   "graduated": 3,
#   "sessions_tracked": 100,
#   "learnings_per_session": 0.42
# }
```

---

## CLI (`scripts/learning-db.py`)

```bash
# Record a learning
python3 ~/.claude/scripts/learning-db.py record TOPIC KEY "VALUE" --category CATEGORY

# Query learnings
python3 ~/.claude/scripts/learning-db.py query --category error --min-confidence 0.7

# Search
python3 ~/.claude/scripts/learning-db.py search "multiple matches"

# Stats
python3 ~/.claude/scripts/learning-db.py stats

# Import from legacy patterns.db
python3 ~/.claude/scripts/learning-db.py import-patterns ~/.claude/learning/patterns.db

# Import from retro L2 markdown
python3 ~/.claude/scripts/learning-db.py import-retro retro/
```

---

## Category Defaults

| Category | Initial Confidence | Use Case |
|----------|-------------------|----------|
| error | 0.55 | Tool errors and solutions |
| pivot | 0.60 | Approach changes during work |
| review | 0.70 | PR review findings |
| design | 0.65 | Design decisions and trade-offs |
| debug | 0.60 | Debugging insights |
| gotcha | 0.70 | Non-obvious pitfalls |
| effectiveness | 0.50 | What worked well |

---

## Error Classification

| Type | Patterns |
|------|----------|
| `missing_file` | "no such file", "file not found", "does not exist" |
| `permissions` | "permission denied", "access denied" |
| `syntax_error` | "syntax error", "unexpected token" |
| `type_error` | "type error", "cannot convert" |
| `import_error` | "import error", "no module named" |
| `timeout` | "timeout", "timed out" |
| `connection` | "connection refused", "network error" |
| `multiple_matches` | "multiple matches", "found N matches" |

---

## Confidence Lifecycle

```
New error pattern recorded at confidence 0.55  ← already above the injection floor
  → Success (+0.15): 0.55 → 0.70
  → Failure (-0.10): 0.70 → 0.60
  → Stale 30 days (-0.05): 0.60 → 0.55

Injection floor: learning_db_v2.INJECTION_MIN_CONFIDENCE (0.5)
Pruning threshold: < 0.3 AND older than 90 days
Graduation: marked when the knowledge is embedded in a durable repo file
```

The floor must stay strictly below the lowest birth confidence. Confidence
rises only for learnings that get injected, so a floor at or above birth
confidence is a one-way ratchet: a new learning never injects, so it never gets
boosted, so it never crosses the floor. Both injectors import the constant;
`hooks/tests/test_injection_floor.py` fails if it ever rises.

---

## Second Injection Gate: A Hint Must Carry a Solution

Confidence says a learning recurs. It does not say the learning tells you
anything. `error-learner.py` writes `DEFAULT_FIX_SOLUTION_TEMPLATE` — "Fix
<error_type> error in <tool>: <snippet>" — whenever it cannot map an error to a
real fix, and those rows never acquire a real solution. They dominated the
injectable pool (99 of 126 rows), so injection spent context to restate the
error type back to the agent.

Both injectors gate on `hint_has_solution(value)` after the confidence filter:

```python
from learning_db_v2 import hint_has_solution

results = [r for r in results if hint_has_solution(r.get("value", ""))]
```

Three rules hold this together:

- The matcher is derived from `DEFAULT_FIX_SOLUTION_TEMPLATE`, the same string
  that writes the stubs. Renaming the template updates the matcher in the same
  edit; a hardcoded regex would silently stop matching.
- Stub rows stay in the database. Their recurrence and frequency still feed
  error classification and the auto-feedback loop; they are only unfit to inject.
- Fetch more candidates than you inject. Most of the pool is stubs, so a query
  limited to the injection cap returns stubs alone and drops a real hint that
  ranked just below them.

Emitting no hint is the correct outcome when only stubs match.

---

## Graduation

When a learning is mature enough to embed directly into an agent:

```python
from learning_db_v2 import mark_graduated

mark_graduated("go-patterns", "mutex-over-atomics", "agent:golang-general-engineer")
```

Graduated entries are excluded from injection by default (`exclude_graduated=True`),
so the target must name a durable repo artifact. `mark_graduated` resolves
`agent:X` to `agents/X.md`, `skill:X` to that skill's `SKILL.md`, and
`target:PATH` to `PATH`. It refuses ephemeral targets (`session-artifact`,
`pruned:*`) and returns False; a path-shaped target that does not resolve is
written with a stderr warning.

Repair a database that already carries bad targets:

```bash
python3 scripts/learning-db.py repair-graduations          # dry run: review the table
python3 scripts/learning-db.py repair-graduations --apply  # clear non-durable targets
```
