"""Append-only per-dispatch route event log (JSONL).

The aggregate routing rows in learning.db are keyed `(topic, key)` — they carry
no per-dispatch history, so faithful offline replay of "request → route →
outcome" is impossible from them alone. This module adds that history: one JSONL
line per event, append-only, at `<CLAUDE_LEARNING_DIR>/route-events.jsonl`.

Two producers:
  - routing-decision-recorder.py (PostToolUse:Agent) appends a DECISION event
    when it records a /do-routed dispatch.
  - routing-outcome-finalizer.py (UserPromptSubmit) appends an OUTCOME event
    when it finalizes a pending dispatch.

FAILURE-SAFE BY CONTRACT: a write error here must NEVER break the hook. Every
function swallows all exceptions and returns; the worst case is a lost event
line, never a non-zero hook exit. The log is auxiliary instrumentation, not the
source of truth (the aggregate rows remain authoritative).

Append-only: each event is one `json.dumps(...) + "\n"` opened in "a" mode, so
concurrent appends from parallel dispatches interleave at line granularity
(POSIX append writes under the per-line size are atomic) without a lock — no
read-modify-write, so there is no lost-update race to serialize.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

_DEFAULT_DIR = Path.home() / ".claude" / "learning"
_EVENTS_FILENAME = "route-events.jsonl"


def _events_path() -> Path:
    """Resolve the route-events.jsonl path from CLAUDE_LEARNING_DIR.

    Honors the same env var as learning_db_v2 so tests (and any redirected DB)
    keep the event log beside the throwaway DB, never the live one.
    """
    env_dir = os.environ.get("CLAUDE_LEARNING_DIR")
    base = Path(env_dir) if env_dir else _DEFAULT_DIR
    return base / _EVENTS_FILENAME


def events_path() -> Path:
    """Public accessor for the route-events.jsonl path (e.g. CLI backfill)."""
    return _events_path()


def _append(event: dict[str, Any]) -> None:
    """Append one JSON line. Best-effort: swallow every error (never break a hook)."""
    try:
        path = _events_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[route-events] append failed: {type(e).__name__}: {e}", file=sys.stderr)


def record_decision_event(
    *,
    session: str,
    request_snippet: str,
    agent: str,
    skill: str,
    complexity: str = "",
    complexity_invalid: str = "",
    stack: list[str] | None = None,
    pipeline: str | None = None,
    model: str | None = None,
    health_at_decision: float | None = None,
    n: int | None = None,
    failure: int | None = None,
    action: str | None = None,
    alternates: list[str] | None = None,
    gate_inputs_present: bool = False,
) -> None:
    """Append a per-dispatch DECISION event.

    health_at_decision is the picked pair's confidence at decision time; None
    when the pair had no weight row. n and failure are the other gate inputs the
    demote floor needs (confidence<0.30 AND failure>=3 AND n>=5) — confidence
    alone cannot reconstruct the floor, so all three are snapshotted here, never
    back-filled from later weights. action is the Step-1.5 outcome (keep/demote/
    tiebreak); alternates are the keys offered. All recorded as-is so replay can
    distinguish "no health evaluated" (null) from a real score.

    gate_inputs_present is the instrumentation signal the decommission clock
    reads. True when the marker carried a `health=` token — numeric (state a) OR
    `-` (state b, pick had no weight row, valid expected data). False when the
    marker carried no `health=` token (state c, legacy/missing wiring). This
    distinguishes "no-row, but instrumented" from "never instrumented" — null
    health_at_decision alone cannot. Additive field; old readers ignore it.

    complexity is the NORMALIZED enum value (trivial/simple/medium/complex) or
    "". complexity_invalid carries a raw marker value that failed validation
    (e.g. "Low") — written only when non-empty, so the bad value is kept for
    audit instead of dropped. stack is the parsed ` stack={s1,s2}` marker token;
    written only when present, so stack-free markers write unchanged events.
    pipeline is the parsed ` pipeline=<name>` token, written on the same terms.
    """
    event: dict[str, Any] = {
        "type": "decision",
        "ts": time.time(),
        "session": session or "",
        "request_snippet": (request_snippet or "")[:200],
        "agent": agent or "",
        "skill": skill or "",
        "complexity": complexity or "",
        "health_at_decision": health_at_decision,
        "n": n,
        "failure": failure,
        "action": action,
        "alternates": alternates,
        "gate_inputs_present": gate_inputs_present,
    }
    if complexity_invalid:
        event["complexity_invalid"] = complexity_invalid
    if stack is not None:
        event["stack"] = stack
    if pipeline is not None:
        event["pipeline"] = pipeline
    if model is not None:
        event["model"] = model
    _append(event)


def record_outcome_event(
    *,
    session: str,
    key: str,
    outcome: str,
    reason: str | None = None,
    routing_relevant: bool | None = None,
) -> None:
    """Append a per-dispatch OUTCOME event (outcome in {success, failure,
    neutral, weak_success}).

    ``reason`` is the short cause for the outcome (e.g. tool-errors, rejection,
    acceptance, neutral-new-topic). Free of prompt text/secrets. Included only
    when given, so old reason-free callers write unchanged events.

    ``routing_relevant`` marks whether the outcome is a routing signal that the
    confidence loop acts on. Written only when not None; route-value-eval counts
    only routing-relevant failures. None keeps the field absent for callers that
    do not assert relevance.
    """
    event: dict[str, Any] = {
        "type": "outcome",
        "ts": time.time(),
        "session": session or "",
        "key": key or "",
        "outcome": outcome or "",
    }
    if reason:
        event["reason"] = reason
    if routing_relevant is not None:
        event["routing_relevant"] = routing_relevant
    _append(event)
