# Telemetry Database Reference

Schema, API, and operations for the store the hooks write: routing telemetry, agent evidence, and governance events.

## Database Location

`~/.claude/learning/learning.db` (SQLite with WAL mode for concurrent access). Two other `learning.db` files exist on disk and carry a different, older schema — resolve the path through `learning_db_v2.get_db_path()` rather than hardcoding it.

## What the hooks write

| Table | Written by | Carries |
|---|---|---|
| `evidence_route_decisions` | `routing-decision-recorder.py` (PostToolUse:Agent) | One row per dispatch: agent, skill, pipeline, stack, marker |
| `routing_outcome_basis` | `routing-outcome-recorder.py` (SubagentStop), `routing-outcome-finalizer.py` (UserPromptSubmit), `routing-outcome-stop-fallback.py` (Stop) | How each outcome was scored, so a rate can be read against its basis |
| `evidence_events` / `evidence_sessions` | agent evidence hooks | Per-event success and failure records with target paths |
| `telemetry_runs` | `record_telemetry_run` callers | Per-run token, step, and tool-error totals |
| `governance_events` | ADR and creation-gate hooks | Gate decisions and their resolutions |

Every one of these is append-only from a hook's perspective. A hook records what happened; it never edits an agent or skill file.

## Schema

```sql
CREATE TABLE evidence_route_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    marker TEXT,                   -- dispatch id; route-fit scoring reads one marker per event
    agent TEXT,
    skill TEXT,
    pipeline TEXT,
    stack TEXT,
    outcome TEXT,                  -- success | failure | neutral, set by the finalizer
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE telemetry_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    git_sha TEXT,
    topic TEXT,
    tokens INTEGER,
    steps INTEGER,
    tool_errors INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE governance_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    event_type TEXT,               -- the gate that fired
    detail TEXT,
    resolved_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
```

Read the live definitions in `hooks/lib/learning_db_v2.py` before writing a migration — the file is the source of truth and carries columns this summary omits.

## Core API (`hooks/lib/learning_db_v2.py`)

### Record a routing decision

```python
from learning_db_v2 import record_evidence_route_decision

record_evidence_route_decision(
    session_id=session_id,
    marker=dispatch_id,
    agent="golang-general-engineer",
    skill="systematic-debugging",
)
```

One marker per event. Packing several markers into a single Bash or Workflow call keeps them recorded but forfeits route-fit scoring, which reads a lone marker per event.

### Update a routing outcome

```python
from learning_db_v2 import update_evidence_route_outcome

update_evidence_route_outcome(marker=dispatch_id, outcome="success")
```

Three-way and deterministic: failure on errors or rejection, success on explicit acceptance, neutral otherwise. Silence is neutral, never acceptance.

### Record an evidence event

```python
from learning_db_v2 import record_evidence_event

record_evidence_event(
    session_id=session_id,
    route_key="agent:skill",
    target="path/to/file.py",
    success=True,
)
```

### Read routing context

```python
from learning_db_v2 import get_evidence_route_context, get_evidence_decision

context = get_evidence_route_context("golang-general-engineer:systematic-debugging")
advice = get_evidence_decision("golang-general-engineer:systematic-debugging")
```

### Record a governance event

```python
from learning_db_v2 import record_governance_event, resolve_governance_event

event_id = record_governance_event(session_id=session_id, event_type="adr-gate", detail="blocked")
resolve_governance_event(event_id)
```

### Record a run's totals

```python
from learning_db_v2 import record_telemetry_run

record_telemetry_run(session_id=session_id, topic="quality-loop", tokens=n, steps=k, tool_errors=e)
```

## CLI (`scripts/learning-db.py`)

Every command below is read-only except the two recorders.

```bash
# Routing health — read this before reading any rate
python3 ~/.claude/scripts/learning-db.py route-health

# Routing statistics; --by is required
python3 ~/.claude/scripts/learning-db.py route-stats --by agent   # skill|force-route|errors|override|week|day

# Health-aware re-rank input
python3 ~/.claude/scripts/learning-db.py route-weights

# Compare two cohorts before and after a change
python3 ~/.claude/scripts/learning-db.py route-delta --from SHA_OR_DATE --to SHA_OR_DATE

# Agent evidence
python3 ~/.claude/scripts/learning-db.py evidence-recent
python3 ~/.claude/scripts/learning-db.py evidence-failures
python3 ~/.claude/scripts/learning-db.py evidence-file-history PATH
python3 ~/.claude/scripts/learning-db.py evidence-route-context AGENT:SKILL
python3 ~/.claude/scripts/learning-db.py evidence-decide AGENT:SKILL

# Reviewer cost and precision
python3 ~/.claude/scripts/learning-db.py review-roi
python3 ~/.claude/scripts/learning-db.py review-fps

# Enhancement skills seen stacked
python3 ~/.claude/scripts/learning-db.py stack-usage

# Recorders
python3 ~/.claude/scripts/learning-db.py record-routing-outcome ...
python3 ~/.claude/scripts/learning-db.py route-failure AGENT:SKILL --reason-file FILE --routing-relevant yes
```

## Outcome basis: read it before reading a rate

`route-health` reports the outcome basis and the silent-success share alongside the rates. A per-route error rate computed mostly from neutral outcomes describes the scorer, not the router. Silent failure is the central enemy here: it raises no error to grep, so the basis is what tells you whether a clean-looking rate means anything.

## Atomic writes and concurrency

Hooks fire on every tool call and share this database with read-only CLI queries.

- WAL mode is enabled at init; keep it.
- Set `PRAGMA busy_timeout` on any connection a hook opens. A hook that hits `SQLITE_BUSY` and exits non-zero blocks the tool call.
- File-based state outside SQLite uses write-to-temp-then-rename, never an in-place write.
- Any failure path still exits 0. A telemetry write is never worth blocking a tool on.

## Retention

Telemetry accumulates per dispatch, so it grows with use. `prune_ancillary` trims ancillary rows; run it as a maintenance step, never inside an event hook, because a hook's budget is under 50ms and a prune is not.
