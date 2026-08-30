#!/usr/bin/env python3
"""PreToolUse:Agent gate — warn when a medium/complex dispatch drops a handoff block.

Fires on every Agent dispatch. When ``tool_input.prompt`` opens with a
``[do-route]`` marker at ``complexity=medium`` or ``complexity=complex``, the
prompt must carry the three blocks a complete handoff needs:

- ``**Request (verbatim):**``
- ``**Acceptance criteria:**``
- ``## Repo state``

Missing any block emits ``additionalContext`` naming the gap and the fix:
re-run ``scripts/build-dispatch.py`` and paste its output verbatim. No marker,
or ``trivial``/``simple``, stays silent.

Modes (env):

- ``DISPATCH_SPEC_GATE_MODE=deny`` — ``permissionDecision: deny`` with the same
  reason. Off by default. Promotion date: 2026-09-05, after a week of
  ``spec_score`` telemetry.
- ``DISPATCH_SPEC_GATE_BYPASS=1`` — disables the gate.

Budget: string checks only, no I/O, exit 0 on every path, under 50 ms on the
silent path. ``hook_utils`` imports lazily on the emit path only; its
module-level imports cost about 50 ms.

Defect this guards (scripts/routing-ab-results/handoff-context-v2/VERDICT.md):
the router hand-assembled the Agent prompt and dropped the repo-state block.
"""

from __future__ import annotations

import json
import os
import sys

EVENT_NAME = "PreToolUse"
MARKER = "[do-route]"
GATED_COMPLEXITY = ("medium", "complex")
REQUIRED_BLOCKS = (
    "**Request (verbatim):**",
    "**Acceptance criteria:**",
    "## Repo state",
)
FIX = (
    "Re-run `python3 scripts/build-dispatch.py --json '<routing decision>'` "
    "and paste its output verbatim as the Agent prompt. "
    "Do not hand-assemble the dispatch."
)


def marker_complexity(prompt: str) -> str:
    """Return the complexity token from the first-line marker, or ''."""
    head = prompt.lstrip()
    if not head.startswith(MARKER):
        return ""
    first_line = head.split("\n", 1)[0]
    for token in first_line.split():
        if token.startswith("complexity="):
            return token[len("complexity=") :].lower()
    return ""


def missing_blocks(prompt: str) -> list[str]:
    """Return the required block labels absent from ``prompt``."""
    return [block for block in REQUIRED_BLOCKS if block not in prompt]


def build_reason(complexity: str, missing: list[str]) -> str:
    names = ", ".join(f"`{block}`" for block in missing)
    return (
        f"[dispatch-spec-gate] complexity={complexity} dispatch is missing "
        f"{len(missing)} handoff block(s): {names}. {FIX}"
    )


def emit(reason: str) -> None:
    """Print the warn or deny payload. Lazy import keeps the silent path fast."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
    from hook_utils import context_output, deny_tool_use

    if os.environ.get("DISPATCH_SPEC_GATE_MODE", "").lower() == "deny":
        deny_tool_use(EVENT_NAME, reason)
        return
    context_output(EVENT_NAME, reason).print_and_exit()


def main() -> None:
    if os.environ.get("DISPATCH_SPEC_GATE_BYPASS") == "1":
        return
    try:
        event = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(event, dict) or event.get("tool_name") != "Agent":
        return
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return
    prompt = tool_input.get("prompt")
    if not isinstance(prompt, str) or not prompt:
        return
    complexity = marker_complexity(prompt)
    if complexity not in GATED_COMPLEXITY:
        return
    missing = missing_blocks(prompt)
    if not missing:
        return
    emit(build_reason(complexity, missing))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except Exception:
        pass
    finally:
        sys.exit(0)
