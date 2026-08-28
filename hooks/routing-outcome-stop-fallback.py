#!/usr/bin/env python3
# hook-version: 2.0.0
"""
Stop Hook: Routing-Outcome Session-End Fallback

Resolves routed dispatches that the next-turn finalizer never saw.

Renamed from session-learning-recorder.py, which mixed this routing telemetry
with a learning-gap warning. The learning loop is retired; this fallback is
routing telemetry and stays.

Design Principles:
- Routing telemetry only — records no learnings, injects no context
- Silent (emits only the empty hook envelope)
- Non-blocking (always exits 0)
- Fast execution (<50ms target)
"""

import json
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import empty_output, get_session_id, hook_error
from learning_db_v2 import init_db
from stdin_timeout import read_stdin

EVENT_NAME = "Stop"


def finalize_routing_outcomes(session_id: str) -> None:
    """Stop fallback: resolve any STILL-pending routed dispatches.

    The next-turn finalizer (UserPromptSubmit, routing-outcome-finalizer.py)
    resolves a dispatch's outcome from tool-errors + user reaction + re-route.
    But an autonomous / headless run may end with NO next user prompt, leaving
    its dispatches provisional forever. This fallback resolves whatever the
    UserPromptSubmit finalizer did not, using the DETERMINISTIC FLOOR — this
    dispatch's own ``errors`` flag alone (no next-turn signal):
    errors => failure (decay); a CLEAN autonomous run => NEUTRAL no-op (T4).
    A clean Stop run carries no acceptance evidence, so it must NOT boost — the
    old "else boost" inflated success counts on every quiet session. It NEVER
    double-resolves: finalize_pending_outcomes atomically
    read-and-clears, so anything UserPromptSubmit already scored (and cleared)
    is simply absent here. Best-effort, silent, never raises.
    """
    try:
        from routing_outcome_score import apply_outcome, decision_row_exists
        from routing_outcome_state import (
            MAX_PENDING_AGE_SEC,
            finalize_pending_outcomes,
        )

        pending = finalize_pending_outcomes(session_id)
        if not pending:
            return
        import time

        # LOW-1: decision_row_exists no longer self-inits; ensure the schema
        # exists once before the per-key existence checks below.
        init_db()
        now = time.time()
        for item in pending:
            key = item.get("key")
            if not key:
                continue
            if now - float(item.get("created", now)) > MAX_PENDING_AGE_SEC:
                continue  # drop abandoned provisional entry, do not score
            if not decision_row_exists(key):
                continue  # no row to score (orphaned); drop quietly at session end
            # Deterministic floor (T4): errors => failure (decay); a clean
            # autonomous run carries no acceptance evidence => NEUTRAL no-op.
            # Basis is the failure-axis label only (no next turn => a non-error
            # entry is default_no_complaint), recorded for route-health's
            # silent-success report. It never changes the boost/decay/no-op.
            errors = bool(item.get("errors"))
            outcome = "failure" if errors else "neutral"
            basis = "tool_errors_only" if errors else "default_no_complaint"
            apply_outcome(key, outcome, basis=basis)

    except Exception as e:
        hook_error("routing-outcome-stop-fallback", e)


def main():
    """Resolve still-pending routing outcomes at session end."""
    try:
        event_data = read_stdin(timeout=2)
        if not event_data:
            empty_output(EVENT_NAME).print_and_exit()

        event = json.loads(event_data)
        session_id = event.get("session_id") or get_session_id()

        # Stop fallback: resolve routed dispatches the next-turn finalizer never
        # saw (autonomous / no-next-prompt runs).
        finalize_routing_outcomes(session_id)

        empty_output(EVENT_NAME).print_and_exit()

    except Exception as e:
        hook_error("routing-outcome-stop-fallback", e)
    empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    main()
