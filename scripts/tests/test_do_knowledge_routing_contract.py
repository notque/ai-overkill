"""Adversarial contracts for router-native ambiguity handling."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PRE_ROUTE = ROOT / "scripts/pre-route.py"
PLANNING = ROOT / "skills/process/planning"


def _route(prompt: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(PRE_ROUTE), "--request", prompt, "--json-compact"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    "prompt",
    [
        "write questions for a stakeholder who owns the billing rules",
        "what should I ask them before we change the API contract",
        "get requirements from the team that runs this process",
        "the knowledge is in their head, help me collect it",
    ],
)
def test_external_human_requests_route_to_planning(prompt: str) -> None:
    """Third-party knowledge acquisition reaches planning automatically."""
    route = _route(prompt)
    assert route["skill"] == "planning", route
    assert route["match_type"] == "force_route", route


@pytest.mark.parametrize(
    "prompt",
    [
        "add a test for parseConfig in src/config.go",
        "rename cfg to config in internal/parser.go",
        "fix the typo on line 42 of README.md",
        "implement the documented retry limit and run the tests",
    ],
)
def test_clear_work_does_not_force_planning(prompt: str) -> None:
    """Concrete work stays executable instead of starting an interview."""
    route = _route(prompt)
    forced = route.get("skill") == "planning" and route.get("match_type") == "force_route"
    assert not forced, route


def test_question_threshold_requires_impact_and_uncertainty() -> None:
    """Complexity alone cannot become a blanket interview trigger."""
    body = (PLANNING / "references/ambiguity-triage.md").read_text(encoding="utf-8")
    interview = (PLANNING / "references/depth-first-interview.md").read_text(encoding="utf-8")
    assert "Complexity raises the chance that a question helps; it never makes questioning mandatory" in body
    assert "Two or more linked high-impact decisions" in body
    assert "Low impact, reversible, or supported by convention" in body
    assert "Proceed without an interview when question value is low" in interview


def test_question_rounds_follow_dependency_frontier_not_ceremony() -> None:
    """Independent choices batch; dependent branches wait; interviews stay bounded."""
    body = (PLANNING / "references/depth-first-interview.md").read_text(encoding="utf-8")
    assert "ask the whole independent frontier together" in body
    assert "Do not ask a dependent follow-up before its prerequisite is answered" in body
    assert "Never add low-value questions" in body
    assert "explicit grill" in body.lower() and "exhaustive" in body.lower()
    assert "implicit interview" in body.lower() and "3-decision-round caps" in body


def test_missing_knowledge_routes_by_source() -> None:
    """The router distinguishes evidence, users, third parties, and experiments."""
    body = (PLANNING / "references/ambiguity-triage.md").read_text(encoding="utf-8")
    for source in ("Repository", "public evidence", "current user", "another person", "empirical test"):
        assert source in body
    assert "create an artifact instead of blocking the live session" in body


def test_empirical_route_has_evidence_and_production_gates() -> None:
    """A prototype answers one question and cannot bypass normal delivery gates."""
    body = (PLANNING / "references/empirical-prototype.md").read_text(encoding="utf-8")
    assert "State one falsifiable question" in body
    assert "Question → Evidence → Verdict → Next action" in body
    assert "Do not treat prototype code as production code" in body


def test_context_transition_is_artifact_driven() -> None:
    """Session changes depend on durable state, not a user-facing command."""
    body = (PLANNING / "references/context-boundary.md").read_text(encoding="utf-8")
    assert "live conversation is primary evidence" in body
    assert "fully described by durable artifacts" in body
    assert "Plan or session lifecycle" in body and "`pause.md`" in body
    assert "Inline worker or agent transfer" in body and "`session-handoff`" in body
    assert "Task Spec" in body
    assert "Never assume conversation memory" in body
