#!/usr/bin/env python3
# hook-version: 1.0.0
"""
SubagentStart Hook: Subagent Warm Start

Injects a `[warmstart]` parent-context block into the SUBAGENT at the start
of its conversation. SubagentStart `additionalContext` is "added to the
subagent's context at the start of its conversation, before its first
prompt" (https://code.claude.com/docs/en/hooks). The earlier PreToolUse:Agent
variant landed in the parent instead.

Stdin (documented): session_id, transcript_path, cwd, hook_event_name,
agent_id, agent_type. No prompt, no tool_input. The block is built from
on-disk parent-session state only (see hooks/lib/warmstart_lib.py), so the
Codex adapter can run this hook unchanged.

Design Principles:
- Non-blocking (always exits 0)
- Sub-50ms execution (file reads only, no subprocess)
- Graceful degradation on missing files
- Caps output at ~4000 chars (~1000 tokens)
"""

import json
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output, get_session_id
from stdin_timeout import read_stdin
from warmstart_lib import gather_context_block

EVENT_NAME = "SubagentStart"


def main() -> None:
    """Build the parent-context block and inject it into the subagent.

    Flow:
    1. Read stdin JSON; take session_id and agent_type
    2. Gather parent session context from on-disk state
    3. Inject via context_output(SubagentStart, ...)
    """
    try:
        event_data = read_stdin(timeout=2)
        if not event_data:
            return

        event = json.loads(event_data)
        if not isinstance(event, dict):
            empty_output(EVENT_NAME).print_and_exit()

        session_id = event.get("session_id") or get_session_id()
        agent_type = str(event.get("agent_type") or "subagent").strip() or "subagent"

        context_output(EVENT_NAME, gather_context_block(session_id, agent_type)).print_and_exit()

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
