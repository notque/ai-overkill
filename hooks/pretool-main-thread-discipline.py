#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse Hook: Main-Thread Discipline Gate

Enforces PHILOSOPHY.md "Router as Orchestrator, Not Worker" — the main thread's
only job during an active /do session is classify → select → dispatch → evaluate.
It must not Edit, Write, or run non-routing Bash.

Two responsibilities (both handled as PreToolUse):

1. SESSION TRACKING: When the Skill tool is invoked with skill name "do", set a
   /tmp marker file so subsequent tool calls know a /do session is active.

2. ENFORCEMENT: When Edit, Write, or Bash is called and a /do session marker
   exists, block with exit code 2 unless the call is routing-safe.

Routing-safe Bash allowlist (pass these through unconditionally):
  - python3 scripts/routing-manifest.py
  - python3 ~/.claude/scripts/learning-db.py record ...
  - git status
  - git log
  - python3 scripts/classify-repo.py

Design:
  - Blocking hook (exit 2 for violations, exit 0 for all else)
  - Silent when no /do session is active (zero noise for non-/do workflows)
  - Escape hatch: set CLAUDE_SKIP_DISCIPLINE=1 to bypass for debugging
  - Escape hatch: set CLAUDE_DO_ACTIVE=0 to force-clear active state
  - NOT registered in settings.json — deploy and register separately when ready

ADR-192 Fix 3.
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import get_session_id, hook_error
from stdin_timeout import read_stdin

_EVENT_NAME = "PreToolUse"

# Bash command patterns that are safe for the main thread during /do sessions.
# These cover the routing bookkeeping calls described in skills/meta/do/SKILL.md.
_ROUTING_SAFE_PATTERNS = [
    r"python3\s+scripts/routing-manifest\.py",
    r"python3\s+~?[^\s]*/scripts/learning-db\.py",
    r"python3\s+scripts/classify-repo\.py",
    r"python3\s+scripts/check-routing-drift\.py",
    r"python3\s+scripts/generate-(?:skill|agent)-index\.py",
    r"git\s+status",
    r"git\s+log",
    r"git\s+branch",
    r"git\s+diff\s+--name-only",
    r"cat\s+",  # read-only: cat a file
    r"ls\s+",  # read-only: list directory
    r"echo\s+",  # innocuous output
    r"python3\s+scripts/routing-benchmark\.py",
]

_COMPILED_SAFE = [re.compile(p) for p in _ROUTING_SAFE_PATTERNS]


def marker_path(session_id: str) -> Path:
    """Return the /tmp marker path for a given session."""
    return Path(f"/tmp/claude-do-active-{session_id}")


def is_routing_safe_bash(command: str) -> bool:
    """Return True if a Bash command is safe for the main thread during /do."""
    cmd = command.strip()
    return any(pattern.search(cmd) for pattern in _COMPILED_SAFE)


def main() -> None:
    """Enforce main-thread discipline during active /do sessions."""
    # Escape hatch: explicit env var bypass for debugging
    if os.environ.get("CLAUDE_SKIP_DISCIPLINE") == "1":
        sys.exit(0)

    try:
        raw = read_stdin(timeout=2)
        if not raw or not raw.strip():
            sys.exit(0)
        event = json.loads(raw)
    except (json.JSONDecodeError, OSError):
        sys.exit(0)

    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input", {})

    session_id = get_session_id()
    marker = marker_path(session_id)

    # -----------------------------------------------------------------------
    # RESPONSIBILITY 1: Track /do session activation
    # When the Skill tool is invoked with skill name "do", mark the session.
    # -----------------------------------------------------------------------
    if tool_name == "Skill":
        skill_name = tool_input.get("skill", "") or tool_input.get("name", "")
        if skill_name == "do":
            try:
                marker.write_text("active")
            except OSError:
                pass  # /tmp write failure is non-fatal
        sys.exit(0)  # Never block Skill tool calls

    # -----------------------------------------------------------------------
    # RESPONSIBILITY 2: Enforce discipline on Edit / Write / Bash
    # Only active when /do session marker exists.
    # -----------------------------------------------------------------------

    # Force-clear escape hatch
    if os.environ.get("CLAUDE_DO_ACTIVE") == "0":
        try:
            marker.unlink(missing_ok=True)
        except OSError:
            pass
        sys.exit(0)

    if not marker.exists():
        sys.exit(0)  # No active /do session — nothing to enforce

    if tool_name == "Edit" or tool_name == "Write":
        # Edit and Write are always blocked during a /do session.
        # The main thread must dispatch an agent to make file changes.
        message = (
            "[main-thread-discipline] BLOCKED: "
            f"{tool_name} called from the main thread during an active /do session.\n"
            "The /do router's only job is classify → select → dispatch → evaluate.\n"
            "Dispatch an agent to make file changes. The agent has the domain expertise; "
            "the main thread does not.\n"
            'PHILOSOPHY.md: "Router as Orchestrator, Not Worker"'
        )
        print(message, file=sys.stderr)
        sys.exit(2)

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        if is_routing_safe_bash(command):
            sys.exit(0)  # Routing bookkeeping is allowed

        message = (
            "[main-thread-discipline] BLOCKED: "
            f"Non-routing Bash called from the main thread during an active /do session.\n"
            f"Command: {command[:120]!r}\n"
            "Allowed Bash during /do: routing-manifest.py, learning-db.py record, "
            "git status/log/branch, ls, cat, classify-repo.py.\n"
            "For analysis or execution, dispatch an agent instead.\n"
            'PHILOSOPHY.md: "Router as Orchestrator, Not Worker"'
        )
        print(message, file=sys.stderr)
        sys.exit(2)

    # All other tools (Read, Grep, Glob, Task, Agent) are allowed — they are
    # the orchestration tools the router legitimately uses.
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Preserve intentional exit codes (0, 2) — do not override
    except Exception as e:
        hook_error("pretool-main-thread-discipline", e)
