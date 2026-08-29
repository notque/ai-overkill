#!/usr/bin/env python3
# hook-version: 2.1.0
"""
PreToolUse Hook: Subagent Warm Start (superseded)

Superseded by hooks/subagent-start-warmstart.py. PreToolUse:Agent
`additionalContext` lands in the PARENT session, not the subagent, so this
hook never reached a subagent. It stays registered for one release so
deregistration is a separate owner step. Context building lives in
hooks/lib/warmstart_lib.py and is shared with the SubagentStart hook.

Design Principles:
- Non-blocking (always exits 0)
- Sub-50ms execution (file reads only, no subprocess)
- Graceful degradation on missing files
"""

import json
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output, get_session_id
from stdin_timeout import read_stdin
from warmstart_lib import (  # re-exported for tests and callers
    ADR_SESSION_FILE,
    DISCOVERIES_DIR,
    FRESHNESS_HOURS,
    MAX_FILES_SHOWN,
    MAX_OUTPUT_CHARS,
    SESSION_READS_FILE,
    TASK_PLAN_FILE,
    build_context_block,
    extract_decisions,
    extract_task_plan,
    gather_context_block,
    is_fresh_file,
    list_discoveries,
    load_adr_session,
    load_recent_reads,
)

EVENT_NAME = "PreToolUse"


def main() -> None:
    """Emit the parent-context block on PreToolUse:Agent (lands in the parent)."""
    try:
        event_data = read_stdin(timeout=2)
        if not event_data:
            return

        event = json.loads(event_data)
        session_id = event.get("session_id") or get_session_id()
        context_output(EVENT_NAME, gather_context_block(session_id)).print_and_exit()

    except Exception as e:
        print(f"[warmstart] error: {e}", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[warmstart] Fatal: {e}", file=sys.stderr)
    finally:
        sys.exit(0)
