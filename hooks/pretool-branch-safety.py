#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse:Bash Hook: Branch Safety Gate

Blocks git commit commands when the current working branch is main or master.
Forces agents to create a feature branch before committing.

This is a HARD GATE — exits 0 with JSON permissionDecision:deny to block the Bash tool.

Detection logic:
- Tool is Bash
- Command contains 'git commit'
- Current branch is 'main' or 'master' (checked via git branch --show-current)

Allow-through conditions:
- Tool is not Bash
- Command does not contain 'git commit'
- Current branch is NOT main or master
- BRANCH_SAFETY_BYPASS=1 env var
"""

import json
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import deny_tool_use, get_tool_input, hook_error, record_governance
from stdin_timeout import read_stdin

_BYPASS_ENV = "BRANCH_SAFETY_BYPASS"
_PROTECTED_BRANCHES = {"main", "master"}


def _extract_effective_cwd(command: str, default_cwd: str | None) -> str | None:
    """Extract the effective working directory from a command string.

    Detects two patterns:
    - ``cd <path> && ...`` or ``cd <path> ; ...`` prefix
    - ``git -C <path> ...`` flag

    Returns the extracted path if found, otherwise default_cwd.
    """
    # Pattern 1: cd <path> && or cd <path> ;
    m = re.match(r'cd\s+(?:"([^"]+)"|(\S+))\s*(?:&&|;)', command.lstrip())
    if m:
        p = (m.group(1) or m.group(2) or "").strip()
        if p:
            return p

    # Pattern 2: git -C <path>
    m = re.search(r'\bgit\s+-C\s+(?:"([^"]+)"|(\S+))', command)
    if m:
        return m.group(1) or m.group(2)

    return default_cwd


def _current_branch(cwd: str | None) -> str | None:
    """Return the current git branch name, or None on error."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd or None,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def main() -> None:
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    # tool_name filter removed — matcher "Bash" in settings.json prevents
    # this hook from spawning for non-Bash tools.

    command = get_tool_input(event).get("command", "")
    if "git commit" not in command:
        sys.exit(0)

    # Bypass env var — set when an explicit override is needed.
    if os.environ.get(_BYPASS_ENV) == "1":
        if debug:
            print("[branch-safety] Bypassed via BRANCH_SAFETY_BYPASS=1", file=sys.stderr)
        sys.exit(0)

    default_cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")
    cwd = _extract_effective_cwd(command, default_cwd)
    branch = _current_branch(cwd)

    if debug:
        print(f"[branch-safety] git commit detected, branch={branch!r}", file=sys.stderr)

    if branch is None:
        # Cannot determine branch — fail open rather than block valid work.
        if debug:
            print("[branch-safety] Could not determine branch — allowing through", file=sys.stderr)
        sys.exit(0)

    if branch in _PROTECTED_BRANCHES:
        print(
            f"[branch-safety] BLOCKED: Cannot commit directly to {branch}. Create a feature branch first.",
            file=sys.stderr,
        )
        print("[fix-with-skill] pr-workflow", file=sys.stderr)
        record_governance(
            "policy_violation",
            hook_name="pretool-branch-safety",
            tool_name="Bash",
            hook_phase="pre",
            severity="high",
            blocked=True,
            event=event,
            command=command,
        )
        deny_tool_use(
            "PreToolUse",
            f"Cannot commit directly to {branch}. Create a feature branch first. "
            "Use the pr-workflow skill (commit intent) to commit safely.",
        )
        sys.exit(0)

    if debug:
        print(f"[branch-safety] Branch {branch!r} is not protected — allowing through", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(0) propagate normally
    except Exception as e:
        hook_error("pretool-branch-safety", e)
    finally:
        sys.exit(0)
