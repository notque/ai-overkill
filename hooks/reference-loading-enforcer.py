#!/usr/bin/env python3
# hook-version: 1.1.0
"""
PreToolUse:Agent Hook: Reference Loading Enforcer

Fires on Agent tool dispatches. Injects a reference loading requirement into
the agent prompt unless the requirement is already present.

This addresses the core problem: agents are dispatched without being told to
read their Reference Loading Table, so domain-specific reference files sit
unused on disk.

Design:
- Read prompt from tool_input["prompt"]
- Check (case-insensitively) whether the prompt already carries a
  reference-loading instruction — either this hook's own marker or the /do
  dispatch text from scripts/build-dispatch.py INJ_REFERENCE_LOADING
- If NOT present, inject the instruction via context_output
- No file I/O — just string inspection and context injection
- Always exits 0 (non-blocking)
- Sub-50ms target (no I/O, pure string ops)

Bypass: REFERENCE_ENFORCER_BYPASS=1 env var skips injection.
"""

import json
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output, hook_error
from stdin_timeout import read_stdin

EVENT_NAME = "PreToolUse"

# Marker used to detect whether the prompt already carries a reference-loading
# instruction. Matched case-insensitively so it covers both this hook's own
# injection ("REFERENCE LOADING REQUIREMENT: ...") and the /do dispatch text
# from scripts/build-dispatch.py INJ_REFERENCE_LOADING ("... Reference Loading
# Table ..."). Lockstep guarded by hooks/tests/test_reference_loading_enforcer.py.
_INJECTION_MARKER = "reference loading"

# The instruction to inject into agent prompts.
_REFERENCE_LOADING_INSTRUCTION = (
    "REFERENCE LOADING REQUIREMENT: Before starting work, read your agent .md file "
    "or skill SKILL.md to find the Reference Loading Table. Load EVERY reference file "
    "whose signal matches this task — load greedily, not conservatively. Multiple "
    "matching signals = load all matching references. Reference files contain "
    "domain-specific patterns, anti-patterns, code examples, and detection commands "
    "that make your output expert-quality. Skipping this step means operating without "
    "domain expertise that exists on disk."
)

_BYPASS_ENV = "REFERENCE_ENFORCER_BYPASS"


def main() -> None:
    """Process PreToolUse events for Agent tool reference loading injection.

    Flow:
    1. Read stdin JSON — check tool_name is Agent
    2. Extract prompt from tool_input
    3. If prompt already contains the injection marker, do nothing
    4. Otherwise emit the instruction via context_output
    """
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=2)
    if not raw:
        empty_output(EVENT_NAME).print_and_exit()
        return

    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        if debug:
            print("[ref-enforcer] Could not parse stdin JSON — allowing through", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()
        return

    # Bypass env var.
    if os.environ.get(_BYPASS_ENV) == "1":
        if debug:
            print(f"[ref-enforcer] Bypassed via {_BYPASS_ENV}=1", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()
        return

    # Only act on Agent tool dispatches (defensive check even though matcher filters).
    tool_name = event.get("tool_name", "")
    if tool_name != "Agent":
        if debug:
            print(f"[ref-enforcer] Tool is {tool_name!r} — not Agent, skipping", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()
        return

    tool_input = event.get("tool_input", {})
    prompt = tool_input.get("prompt", "")

    # If the prompt already carries a reference-loading instruction, do nothing.
    if _INJECTION_MARKER in prompt.lower():
        if debug:
            print("[ref-enforcer] Injection marker already present — skipping", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()
        return

    if debug:
        print("[ref-enforcer] Injecting reference loading instruction", file=sys.stderr)

    context_output(EVENT_NAME, _REFERENCE_LOADING_INSTRUCTION).print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        hook_error("reference-loading-enforcer", e)
    finally:
        sys.exit(0)
