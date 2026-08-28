# Hook Development Code Examples

Production-ready hook implementations with all safety patterns.

## Non-Blocking Hook Template

Complete template with comprehensive error handling and non-blocking execution.

```python
#!/usr/bin/env python3
"""
Hook template with non-blocking execution patterns.
Always exits with code 0 to prevent blocking Claude Code.
"""
import json
import sys
import traceback
from pathlib import Path
from datetime import datetime

def debug_log(message):
    """Log debug information without blocking execution."""
    try:
        with open('/tmp/claude_hook_debug.log', 'a') as f:
            f.write(f"[{datetime.now().isoformat()}] {message}\n")
    except Exception:
        pass  # Never let logging block execution

def process_event(event_data):
    """
    Process the event and return result.

    Args:
        event_data: Parsed JSON from Claude Code event

    Returns:
        dict: Result to output (or None)
    """
    # Implement your hook logic here
    tool_name = event_data.get('tool', '')
    tool_output = event_data.get('output', '')

    debug_log(f"Processing {tool_name} event")

    # Example: Detect errors in tool output
    if 'error' in tool_output.lower():
        debug_log(f"Error detected in {tool_name}")
        return {'detected': True, 'tool': tool_name}

    return None

def main():
    """Main hook execution with comprehensive error handling."""
    try:
        # Parse input JSON from Claude Code
        input_data = json.loads(sys.stdin.read())

        # Process the event (implement specific logic here)
        result = process_event(input_data)

        # Output result if needed
        if result:
            print(json.dumps(result))

    except json.JSONDecodeError as e:
        debug_log(f"JSON parsing error: {e}")
    except Exception as e:
        debug_log(f"Unexpected error: {e}\\n{traceback.format_exc()}")
    finally:
        # CRITICAL: Always exit 0 to prevent blocking Claude Code
        sys.exit(0)

if __name__ == "__main__":
    main()
```

---

## Routing Decision Recorder Hook

Complete PostToolUse:Agent hook that records one dispatch per event.

```python
#!/usr/bin/env python3
"""
PostToolUse:Agent hook. Records one routing decision per Agent dispatch.

Reads the dispatch marker from the tool input, writes one row, exits 0 on
every path. A telemetry write is never worth blocking a tool on.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from learning_db_v2 import record_evidence_route_decision
from stdin_timeout import read_stdin

DEBUG_LOG = Path("/tmp/claude_hook_debug.log")


def debug_log(message):
    """Log without ever raising."""
    try:
        with DEBUG_LOG.open("a") as f:
            f.write(f"{message}\n")
    except Exception:
        pass


def extract_route(event):
    """Pull agent, skill, and marker out of the event.

    Returns None when the event carries no marker: route-fit scoring reads one
    marker per event, so an unmarked dispatch is not a recordable decision.
    """
    tool_input = event.get("tool_input", {})
    marker = tool_input.get("marker") or event.get("marker")
    if not marker:
        return None
    return {
        "marker": marker,
        "agent": tool_input.get("subagent_type"),
        "skill": tool_input.get("skill"),
        "session_id": event.get("session_id"),
    }


def main():
    try:
        event = json.loads(read_stdin())
        route = extract_route(event)
        if route:
            record_evidence_route_decision(**route)
            debug_log(f"[routing-recorder] recorded {route['agent']}:{route['skill']}")
    except Exception as exc:
        debug_log(f"[routing-recorder] {exc}")
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
```

**What makes this correct**: one marker per event, every failure path swallowed, `sys.exit(0)` in a `finally` so no code path can exit non-zero, and no write outside the telemetry store.

---

## Routing Outcome Finalizer Hook

Hook that scores a pending outcome on the next user turn.

```python
#!/usr/bin/env python3
"""
UserPromptSubmit hook. Scores the pending routing outcome three ways.

Deterministic and free: failure on errors or rejection, success on explicit
acceptance, neutral otherwise. Silence is neutral, never acceptance.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from learning_db_v2 import update_evidence_route_outcome
from stdin_timeout import read_stdin

REJECTION_MARKERS = ("that's wrong", "no, ", "revert", "undo that")
ACCEPTANCE_MARKERS = ("thanks", "perfect", "ship it")
TASK_VERBS = ("add", "fix", "write", "run", "check", "make")
MAX_CLAUSE_WORDS = 8


def score(prompt, had_errors):
    """Return success, failure, or neutral.

    The asymmetry decides the guards: a missed acceptance stays neutral and
    costs nothing, while a false acceptance corrupts the telemetry. So the
    acceptance path carries stacked precision guards and the neutral path
    carries none.
    """
    text = prompt.strip().lower()
    if had_errors:
        return "failure"
    if any(text.startswith(m) for m in REJECTION_MARKERS):
        return "failure"
    for marker in ACCEPTANCE_MARKERS:
        if not text.startswith(marker):
            continue
        rest = text[len(marker):].lstrip(" ,.!")
        if not rest:
            return "success"
        if rest.split()[0] in TASK_VERBS:      # new instruction, not praise
            return "neutral"
        if len(rest.split()) > MAX_CLAUSE_WORDS:
            return "neutral"
        return "success"
    return "neutral"


def main():
    try:
        event = json.loads(read_stdin())
        marker = event.get("pending_marker")
        if marker:
            outcome = score(event.get("prompt", ""), event.get("had_errors", False))
            update_evidence_route_outcome(marker=marker, outcome=outcome)
    except Exception:
        pass
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
```

Require golden fixtures in both directions: every acceptance marker fires, every veto case stays neutral. Evidence: `hooks/routing-outcome-finalizer.py`, PR #804.

---


## Performance-Optimized Telemetry Read

Hook read optimized for sub-50ms execution with lazy connection and early exit.

```python
#!/usr/bin/env python3
"""
Performance-optimized telemetry read inside a hook.

Opens the connection only when the event warrants a read, sets busy_timeout so
a concurrent writer never turns into a blocked tool call, and returns on the
first row.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from learning_db_v2 import get_connection

BUSY_TIMEOUT_MS = 2000


def route_outcome(route_key):
    """Return the most recent outcome for a route, or None.

    Lazy: the caller decides whether the event is worth a read, so a hook that
    fires on every tool call pays nothing on the common path.
    """
    try:
        conn = get_connection()
        conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        row = conn.execute(
            "SELECT outcome FROM evidence_route_decisions "
            "WHERE agent || ':' || COALESCE(skill,'') = ? "
            "ORDER BY id DESC LIMIT 1",
            (route_key,),
        ).fetchone()
        return row["outcome"] if row else None
    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main():
    try:
        event = json.loads(sys.stdin.read())
        route_key = event.get("route_key")
        if route_key:
            outcome = route_outcome(route_key)
            if outcome:
                print(json.dumps({"route_key": route_key, "last_outcome": outcome}))
    except Exception:
        pass
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
```

**Why `busy_timeout` is not optional**: hooks fire on every tool call and share this database with read-only CLI queries. Without a timeout, a concurrent writer raises `SQLITE_BUSY`; a hook that lets that propagate exits non-zero and blocks the tool.

---


## Hook Registration in settings.json

Complete settings.json configuration for hook registration.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "command": "python3",
        "args": ["/home/user/.claude/hooks/smart_error_detector.py"],
        "description": "Detects errors and injects learned solutions",
        "timeout": 50
      },
      {
        "command": "python3",
        "args": ["/home/user/.claude/hooks/continuous_learner.py"],
        "description": "Updates learning database with solution outcomes",
        "timeout": 50
      }
    ],
    "PreToolUse": [
      {
        "command": "python3",
        "args": ["/home/user/.claude/hooks/context_preparer.py"],
        "description": "Prepares context hints before tool execution",
        "timeout": 50
      }
    ],
    "SessionStart": [
      {
        "command": "python3",
        "args": ["/home/user/.claude/hooks/session_init.py"],
        "description": "Initializes learning database on session start",
        "timeout": 100,
        "once": true
      }
    ]
  }
}
```

**Key fields**:
- `command`: Python interpreter (python3)
- `args`: Full path to hook script
- `description`: Human-readable purpose
- `timeout`: Milliseconds before timeout (default 50ms for real-time hooks)
- `once`: Run only once per session (for SessionStart hooks)
