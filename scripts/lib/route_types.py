"""Shared TypedDict contracts for the routing pipeline.

Defines the structured return types and input shapes used across:
  - Step 0: semantic routing (RouteDecision)
  - Step 1: deterministic pre-route (PreRouteResult)
  - Step 1.5: health-aware re-rank (HealthAdjustResult)
  - routing-decision-recorder hook (HealthGateInputs)

All types use TypedDict so callers get static type-checking without
runtime overhead. Import from here; do not redefine these shapes.
"""

from __future__ import annotations

from typing import Literal, TypedDict

# ---------------------------------------------------------------------------
# Step 0: semantic routing decision (held by the orchestrator LLM)
# ---------------------------------------------------------------------------


class RouteDecision(TypedDict, total=False):
    """Step 0 semantic routing decision (held by the orchestrator LLM)."""

    agent: str | None
    skill: str | None
    pipeline: str | None
    reasoning: str
    confidence: Literal["high", "medium", "low"]


# ---------------------------------------------------------------------------
# Step 1: deterministic safety-net output from pre-route.py
# ---------------------------------------------------------------------------


class PreRouteResult(TypedDict, total=False):
    """Step 1 deterministic safety-net output from pre-route.py."""

    matched: bool
    agent: str | None
    skill: str | None
    pipeline: str | None
    confidence: Literal["high", "medium", "low"]
    match_type: Literal["fallthrough", "force_route", "trigger_keyword"]
    reasoning: str


# ---------------------------------------------------------------------------
# Step 1.5: health-aware re-rank (route_policy.py)
# ---------------------------------------------------------------------------

RouteAction = Literal["keep", "demote", "tiebreak"]


class HealthAdjustResult(TypedDict):
    """Return type of health_adjust() in route_policy.py."""

    final_pick: str | None
    action: RouteAction
    reason: str


# ---------------------------------------------------------------------------
# routing-decision-recorder.py: parsed gate inputs from [do-route] marker
# ---------------------------------------------------------------------------


class HealthGateInputs(TypedDict):
    """Parsed from the [do-route] marker by routing-decision-recorder.py."""

    health: float | None
    n: int | None
    failure: int | None
    action: str | None
    alternates: list[str] | None
    gate_inputs_present: bool


# ---------------------------------------------------------------------------
# Confidence conversion: Step 0 categorical <-> Step 1.5 numeric
# ---------------------------------------------------------------------------

CONFIDENCE_TO_FLOAT: dict[str, float] = {
    "high": 0.9,
    "medium": 0.6,
    "low": 0.3,
}


def confidence_to_float(confidence: str | float | None) -> float:
    """Convert Step 0 categorical confidence to Step 1.5 numeric.

    Args:
        confidence: "high"/"medium"/"low", a float, or None.

    Returns:
        Float in [0.0, 1.0]. None -> 1.0 (assume full confidence when absent).
        Unknown strings -> 0.5.
    """
    if confidence is None:
        return 1.0
    if isinstance(confidence, (int, float)):
        return float(confidence)
    return CONFIDENCE_TO_FLOAT.get(str(confidence).lower(), 0.5)
