# Hook Architecture Reference

> Loaded by hook-development-engineer when reviewing the event-driven pipeline flow or explaining how hooks integrate with Claude Code.

## Event-Driven Pipeline

```
Claude Code Session
    ↓
Event Generation (PostToolUse, PreToolUse, SessionStart, SubagentStop, Stop)
    ↓
Hook Registry (settings.json)
    ↓
┌─────────────────────────────────────────────────────────┐
│                Hook Execution Pipeline                   │
├─────────────────────────────────────────────────────────┤
│ 1. Event JSON Input                                     │
│    - Tool name and parameters                           │
│    - Execution results and errors                       │
│    - Context and session data                           │
├─────────────────────────────────────────────────────────┤
│ 2. Gate or Classify                                     │
│    - Gates: allow, or deny with a reason (PreToolUse)   │
│    - Classifiers: read the event into an outcome        │
│    - Guards stack on the expensive direction only       │
├─────────────────────────────────────────────────────────┤
│ 3. Telemetry Write (append-only)                        │
│    - One dispatch marker per event                      │
│    - Outcome recorded with the basis it was scored on   │
│    - busy_timeout set on every connection               │
├─────────────────────────────────────────────────────────┤
│ 4. Optional Context Injection                           │
│    - Format text for Claude Code context                │
│    - Call context_output(EVENT, text).print_and_exit()  │
│    - hook_utils handles JSON encoding to stdout         │
├─────────────────────────────────────────────────────────┤
│ 5. Exit 0                                               │
│    - Every path, including every failure path           │
│    - sys.exit(0) in a finally block                     │
└─────────────────────────────────────────────────────────┘
    ↓
Context Available to Claude Code Next Tool Use
```

A hook records and gates. It never edits an agent or skill file: a pipeline that writes to a component on its own takes unbounded risk against an unproven benefit, so knowledge reaches a component through a reviewed human edit.

## Telemetry Directory Structure

```
~/.claude/learning/
└── learning.db                 # SQLite (WAL mode) — routing, evidence, governance
~/.claude/state/
├── dream-injection-{hash}.md   # Pre-built session-start payload
└── last-dream.md               # Overnight consolidation summary
/tmp/
└── claude_hook_debug.log       # Non-blocking debug log
```

Two other `learning.db` files exist on disk with an older schema. Resolve the path through `learning_db_v2.get_db_path()` rather than hardcoding it.

See [telemetry-database.md](telemetry-database.md) for schema and operations.
