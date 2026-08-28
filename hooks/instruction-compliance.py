#!/usr/bin/env python3
# hook-version: 1.2.0
"""PostToolUse Hook: Instruction Compliance Measurement

Fires after Agent tool dispatches to check whether MANDATORY instructions
(M01-M09 from ADR instruction-skip-rate-measurement) were followed.

Records compliance observations to learning.db for skip-rate dashboard.

SURFACE — what this hook can and cannot see. It scans two strings: the dispatch
prompt (tool_input) and the subagent report (tool_result). Main-thread
orchestrator output is in neither, so an instruction the orchestrator follows in
its own reply is unmeasurable here and is declared `observable: False`. Those
instructions are not recorded at all: a skip rate computed from a surface that
structurally cannot show compliance measures the surface, not the behavior.

POPULATION — which dispatches a reading applies to. scripts/build-dispatch.py
injects the M04/M05/M06 directives into /do-routed prompts only. Reviewer
fan-out and nested subagent dispatches legitimately carry none, so a non-match
there is expected, not a skip. Each observation records whether the dispatch
carried the `[do-route]` marker (`injected_by_do_route` says which instructions
that gates), and the skip-rate report scores only the expected population.

Design Principles:
- Informational only (always exits 0, never blocks)
- Lightweight string-presence checks (<50ms)
- Multiple signal patterns per instruction for reduced false negatives
- Record only what this surface can observe, against the population it applies to
"""

import json
import os
import re
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "lib"))
from hook_utils import empty_output, get_session_id, get_tool_output, get_tool_result, hook_error
from learning_db_v2 import record_instruction_compliance_batch
from route_types import has_do_route_marker
from stdin_timeout import read_stdin

EVENT_NAME = "PostToolUse"

# ─── Instruction Definitions ─────────────────────────────────────

# `observable` declares whether THIS hook's surface (dispatch prompt + subagent
# report) can show the signal. False => the patterns stay for reference, but no
# observation is recorded, because a non-match proves nothing about behavior.
#
# `injected_by_do_route` declares whether the directive reaches a prompt ONLY
# via scripts/build-dispatch.py, which runs for /do-routed dispatches. True =>
# the observation counts toward the skip rate only when the dispatch carried the
# `[do-route]` marker. False => the directive is expected on every dispatch.
INSTRUCTIONS: dict[str, dict[str, str | bool | list[re.Pattern[str]]]] = {
    "M01": {
        "name": "Phase Banners",
        # Unobservable: phase banners are main-thread orchestrator output, absent
        # from both the dispatch prompt and the subagent report. Measuring them
        # needs a main-thread surface (a Stop-event transcript reader).
        "observable": False,
        "injected_by_do_route": False,
        "patterns": [
            re.compile(r"##\s*Phase\s+\d", re.IGNORECASE),
            re.compile(r"Phase\s+\d\s*:", re.IGNORECASE),
        ],
    },
    "M03": {
        "name": "Routing Decision",
        # Unobservable: the routing banner is main-thread orchestrator output,
        # printed before dispatch. Same correct surface as M01.
        "observable": False,
        "injected_by_do_route": False,
        "patterns": [
            re.compile(r"^={3,}\s*$", re.MULTILINE),
            re.compile(r"(?:^|\s)ROUTING\s*:", re.IGNORECASE | re.MULTILINE),
            re.compile(r"Selected\s*:", re.IGNORECASE),
        ],
    },
    "M04": {
        "name": "Reference Loading",
        # Observable: the reference-loading directive and an agent's own
        # reference-table mentions both land in the scanned strings.
        "observable": True,
        # build-dispatch.py injects it; a non-/do dispatch never carries it.
        "injected_by_do_route": True,
        "patterns": [
            re.compile(r"Reference\s+Loading", re.IGNORECASE),
            re.compile(r"reference.*table", re.IGNORECASE),
            re.compile(r"Before\s+starting\s+work", re.IGNORECASE),
            re.compile(r"Load\s+EVERY\s+reference\s+file", re.IGNORECASE),
        ],
    },
    "M05": {
        # Measures whether the completeness directive reached the prompt, NOT
        # whether the agent delivered a complete result. Renamed to say so.
        "name": "Completeness Injected",
        "observable": True,
        "injected_by_do_route": True,
        "patterns": [
            re.compile(r"deliver\s+the\s+finished\s+product", re.IGNORECASE),
            re.compile(r"ship\s+the\s+complete\s+thing", re.IGNORECASE),
            re.compile(r"Ship\s+the\s+complete", re.IGNORECASE),
            re.compile(r"Deliver\s+the\s+finished", re.IGNORECASE),
        ],
    },
    "M06": {
        # Measures whether the density directive reached the prompt, NOT whether
        # the output was written dense. Renamed to say so.
        "name": "Density Injected",
        "observable": True,
        "injected_by_do_route": True,
        "patterns": [
            re.compile(r"write\s+dense", re.IGNORECASE),
            re.compile(r"high\s+fidelity,?\s+minimum\s+words", re.IGNORECASE),
        ],
    },
}


def check_compliance(text: str) -> dict[str, bool]:
    """Check agent output against all instrumented instructions.

    Args:
        text: Combined agent prompt and output text to scan.

    Returns:
        Dict mapping instruction ID to compliance boolean.
    """
    results: dict[str, bool] = {}
    for instr_id, instr in INSTRUCTIONS.items():
        patterns: list[re.Pattern[str]] = instr["patterns"]  # type: ignore[assignment]
        compliant = any(p.search(text) for p in patterns)
        results[instr_id] = compliant
    return results


def is_observable(instr_id: str) -> bool:
    """Report whether this hook's surface can observe the instruction.

    Unknown IDs are unobservable: record nothing rather than record a reading
    whose surface is undeclared.
    """
    return bool(INSTRUCTIONS.get(instr_id, {}).get("observable", False))


def directive_expected(instr_id: str, do_routed: bool | None) -> bool | None:
    """Report whether this dispatch was expected to carry the directive.

    None when the caller cannot say whether the dispatch was /do-routed: the
    reading is real but its population is unknown, and the report must say so
    rather than fold it into either bucket.
    """
    if not INSTRUCTIONS.get(instr_id, {}).get("injected_by_do_route", False):
        return True
    return do_routed


def record_compliance_batch(
    results: dict[str, bool],
    session_id: str,
    do_routed: bool | None = None,
) -> None:
    """Record observable instruction compliance observations in one transaction.

    Unobservable instructions are dropped here, so the skip-rate dashboard never
    counts a non-match this surface could not have matched.

    Args:
        results: Dict mapping instruction ID to compliance boolean.
        session_id: Current session identifier.
        do_routed: Whether the dispatch prompt carried the `[do-route]` marker.
            None (the default) records an unknown population.
    """
    records = [
        (instr_id, compliant, session_id, directive_expected(instr_id, do_routed))
        for instr_id, compliant in results.items()
        if is_observable(instr_id)
    ]
    record_instruction_compliance_batch(records)


def main() -> None:
    """Process PostToolUse events for Agent instruction compliance.

    Flow:
    1. Read stdin JSON
    2. Extract agent output text
    3. Check each instruction for compliance signals
    4. Record observations to learning.db
    5. Exit silently (informational, never blocks)
    """
    try:
        event_data = read_stdin(timeout=2)
        if not event_data:
            empty_output(EVENT_NAME).print_and_exit()

        event = json.loads(event_data)
        session_id = event.get("session_id") or get_session_id()

        # Extract agent output text
        tool_result = get_tool_result(event)
        if isinstance(tool_result, dict):
            output_text = get_tool_output(tool_result)
        elif isinstance(tool_result, str):
            output_text = tool_result
        else:
            output_text = ""

        # Also check tool_input (agent prompt) for M04/M05/M06. The marker is
        # anchored to the start of a line, so keep the raw prompt too:
        # json.dumps() escapes its newlines and the anchor never matches.
        raw_input = event.get("tool_input", event.get("input", ""))
        if isinstance(raw_input, dict):
            prompt = raw_input.get("prompt")
            tool_input = json.dumps(raw_input)
        elif isinstance(raw_input, str):
            prompt = tool_input = raw_input
        else:
            prompt = tool_input = ""
        if not isinstance(prompt, str):
            prompt = ""

        combined_text = f"{tool_input}\n{output_text}"

        if not combined_text.strip():
            empty_output(EVENT_NAME).print_and_exit()

        # Read the population off the PROMPT only. The subagent report can quote
        # the marker back; counting that would mark an unrouted dispatch as
        # expected and reintroduce the denominator error.
        do_routed = has_do_route_marker(prompt)

        # Check and record compliance for all instructions in one transaction
        results = check_compliance(combined_text)
        record_compliance_batch(results, session_id, do_routed)

        empty_output(EVENT_NAME).print_and_exit()

    except Exception as e:
        hook_error("instruction-compliance", e)
    finally:
        sys.exit(0)  # Never block


if __name__ == "__main__":
    main()
