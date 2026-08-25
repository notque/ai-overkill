#!/usr/bin/env python3
# hook-version: 1.0.1
"""
SessionStart Hook: Fish Shell Detection

Detects Fish shell users and injects the shell-config skill.
Runs once at session start to provide Fish-specific guidance.

Detection Logic:
- $SHELL short-circuits: names "fish" -> detected; names another shell -> skip
- Fallback (only when $SHELL is unset/unrecognised): ~/.config/fish/ directory exists

Output Format:
- [fish-shell] Detected Fish shell user
- [auto-skill] shell-config
- Call the Skill tool with `shell-config`.

Design Principles:
- Lightweight detection (no complex processing)
- Non-blocking (always exits 0)
- Fast execution (<50ms target, depends on filesystem responsiveness)
"""

import os
import sys
import traceback
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output, hook_error

EVENT_NAME = "SessionStart"


def is_fish_shell() -> bool:
    """
    Detect if the user is using Fish shell.

    Returns:
        True if Fish shell is detected, False otherwise

    Detection logic:
    - Primary: $SHELL contains "fish" → True
    - Primary: $SHELL explicitly names a different shell (zsh, bash, etc.) → False
      (config-dir fallback must NOT fire when $SHELL points elsewhere)
    - Fallback: ~/.config/fish/ exists AND $SHELL does not name a known non-fish shell
    """
    shell = os.environ.get("SHELL", "").lower()

    # Primary signal: $SHELL names fish explicitly
    if "fish" in shell:
        return True

    # If $SHELL explicitly names a different shell, do not fall through.
    # This prevents false positives for users who once tried Fish and left
    # ~/.config/fish/ on disk but have since switched to zsh/bash/etc.
    non_fish_shells = ("zsh", "bash", "dash", "ksh", "tcsh", "csh", "sh")
    if any(s in shell for s in non_fish_shells):
        return False

    # Fallback: $SHELL is unset or unrecognised — check config directory.
    # Handle environments without HOME (containers, CI) gracefully.
    try:
        fish_config_dir = Path.home() / ".config" / "fish"
        if fish_config_dir.is_dir():
            return True
    except (RuntimeError, OSError):
        # Path.home() can raise RuntimeError if HOME is not set
        # is_dir() can raise OSError for permission/filesystem issues
        pass

    return False


def get_fish_injection() -> str:
    """Get the context injection for Fish shell users.

    Emits only tags. The shell-config skill carries its own knowledge.
    ADR hook-injection-condensation: removed tutorial block.
    """
    return "[fish-shell] Detected Fish shell user\n[auto-skill] shell-config\nCall the Skill tool with `shell-config`."


def main():
    """Main entry point for the hook."""
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    try:
        if not is_fish_shell():
            # Silent for non-Fish users
            empty_output(EVENT_NAME).print_and_exit()

        # Log detection for debugging visibility
        if debug:
            shell = os.environ.get("SHELL", "")
            print(f"[fish-shell] Detected Fish shell: SHELL={shell}", file=sys.stderr)

        # Inject Fish shell context
        injection = get_fish_injection()
        context_output(EVENT_NAME, injection).print_and_exit()

    except Exception as e:
        hook_error("fish-shell-detector", e)
        # Always log error to stderr for observability
        empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    main()
