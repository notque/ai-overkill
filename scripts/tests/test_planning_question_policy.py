"""Contract tests for router-native planning decisions."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLANNING = ROOT / "skills/process/planning"
DO = ROOT / "skills/meta/do/SKILL.md"


def test_planning_exposes_internal_routes_without_new_user_command() -> None:
    body = (PLANNING / "SKILL.md").read_text(encoding="utf-8")

    assert "human-source-elicitation.md" in body
    assert "empirical-prototype.md" in body
    assert "context-boundary.md" in body
    assert "ambiguity-triage.md" in body
    assert "/questionnaire" not in body
    assert "/prototype" not in body


def test_do_uses_complexity_and_uncertainty_instead_of_blanket_interviews() -> None:
    body = DO.read_text(encoding="utf-8")

    assert "Question-value policy" in body
    assert "Complexity alone never forces questions" in body
    assert "human-source-elicitation.md" in body
    assert "empirical-prototype.md" in body
    assert "context-boundary.md" in body


def test_human_source_contract_searches_evidence_before_asking() -> None:
    body = (PLANNING / "references/human-source-elicitation.md").read_text(encoding="utf-8")

    assert "Inspect known evidence first" in body
    assert "Do not send" in body
    assert "Coverage map" in body
    assert "unknown" in body


def test_implicit_interview_defaults_to_execution_when_question_value_is_low() -> None:
    body = (PLANNING / "references/depth-first-interview.md").read_text(encoding="utf-8")

    assert "question value" in body.lower()
    assert "proceed without an interview" in body.lower()


def test_source_precedes_interview_threshold() -> None:
    body = (PLANNING / "references/ambiguity-triage.md").read_text(encoding="utf-8")

    assert "Source precedence" in body
    assert body.index("Source precedence") < body.index("Two or more linked high-impact decisions")
    assert "Never ask the current user to answer for another person" in body


def test_interview_batches_frontier_and_bounds_only_implicit_rounds() -> None:
    body = (PLANNING / "references/depth-first-interview.md").read_text(encoding="utf-8")

    assert "independent frontier" in body
    assert "full independent frontier in one message" in body
    assert "Explicit grill" in body and "There is no arbitrary total-question" in body
    assert "construct and exhaust the material decision tree" in body
    assert "kinds and number of questions emerge" in body
    assert "Implicit ambiguity interview" in body
    assert "5 total questions across at most 3 decision-question rounds" in body
    assert "one question alone only when its answer is a prerequisite" in body


def test_interview_adapts_to_native_question_ui_with_portable_fallback() -> None:
    body = (PLANNING / "references/depth-first-interview.md").read_text(encoding="utf-8")

    assert "harness-native question surface" in body
    assert "structured question UI" in body
    assert "numbered Markdown round" in body
    assert "free-form alternative" in body
    assert "chunk a larger frontier solely at that capacity boundary" in body
    assert "do not recompute the tree between chunks unless" in body


def test_nested_interview_resumes_original_delivery_objective() -> None:
    interview = (PLANNING / "references/depth-first-interview.md").read_text(encoding="utf-8")
    router = DO.read_text(encoding="utf-8")

    assert "automatically resume" in interview
    assert "interview-only" in interview.lower()
    assert "resume the originating build, fix, install, validation" in router
    assert "never report the decision artifact as completion" in router


def test_confirmation_state_table_prevents_answer_only_execution() -> None:
    interview = (PLANNING / "references/depth-first-interview.md").read_text(encoding="utf-8")

    assert "ANSWER_ONLY + NESTED_EXECUTION" in interview
    assert "ask one concise confirmation, and do not execute yet" in interview
    assert "EXPLICIT_PROCEED + NESTED_EXECUTION" in interview
    assert "CONFIRMED + NESTED_EXECUTION" in interview
    assert "INTERVIEW_ONLY" in interview
    assert "never infer implementation authority" in interview


def test_planning_umbrella_has_no_stale_one_at_a_time_contract() -> None:
    body = (PLANNING / "SKILL.md").read_text(encoding="utf-8")

    assert "independent questions batched into frontier rounds" in body
    assert "dependent questions asked sequentially" in body
    assert "decision-tree, one question at a time" not in body


def test_fact_gathering_can_run_beside_user_decision_frontier() -> None:
    body = (PLANNING / "references/depth-first-interview.md").read_text(encoding="utf-8")

    assert "start fact gathering alongside an independent user-decision frontier" in body
    assert "block the round only when the fact would change" in body


def test_explicit_grill_has_no_branch_or_recursion_escape_hatch() -> None:
    body = (PLANNING / "references/depth-first-interview.md").read_text(encoding="utf-8")

    assert "For an implicit interview only" in body
    assert "In an explicit grill, never carry a material branch forward" in body
    assert "restructure it into a dependency subtree" in body
    assert "continue until material coverage and shared understanding are complete" in body
    assert "Branch explodes into more than 3 sub-questions" not in body


def test_context_boundary_preserves_handoff_ownership() -> None:
    reference = (PLANNING / "references/context-boundary.md").read_text(encoding="utf-8")
    router = DO.read_text(encoding="utf-8")

    assert "Plan or session lifecycle" in reference
    assert "Inline worker or agent transfer" in reference
    assert "session-handoff" in reference
    assert "Task Spec" in reference
    assert "plan or session lifecycle" in router
    assert "inline worker or agent transfer" in router
