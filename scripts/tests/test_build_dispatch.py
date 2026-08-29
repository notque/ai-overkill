#!/usr/bin/env python3
"""Tests for scripts/build-dispatch.py (ADR: router-improvement-program, C4).

Covers:
- Marker round-trip against the REAL recorder parser
  (hooks/routing-decision-recorder.py) on 9 marker variants: agent/skill,
  complexity, model, health gate inputs (numeric and `health=-`), alts, stack.
- Model enforcement: required for medium/complex, optional for trivial/simple.
- Preamble completeness and block order: marker first, exact Skill-tool calls,
  then thinking directive, token line, Task Specification, the 4 mandatory injections,
  optional worktree/local-only blocks.
- Thinking directive by complexity + slow/fast overrides.
- Graceful degradation: missing optional fields omit their block only.
- Token budget: explicit value, settings.json read, 500000 default.
- CLI: --json / --json-file / stdin; exit 2 + empty stdout on bad input.

Run with: python3 -m pytest scripts/tests/test_build_dispatch.py -v
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build-dispatch.py"
RECORDER_PATH = REPO_ROOT / "hooks" / "routing-decision-recorder.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    with patch("sys.exit"):
        spec.loader.exec_module(mod)
    return mod


bd = _load(SCRIPT_PATH, "build_dispatch")
recorder = _load(RECORDER_PATH, "routing_decision_recorder")


def _decision(**overrides):
    """A complete, valid routing decision; overrides replace top-level keys."""
    base = {
        "agent": "python-general-engineer",
        "skill": "test-driven-development",
        "complexity": "medium",
        "model": "opus",
        "health": {"confidence": 0.72, "n": 6, "failure": 0, "action": "keep"},
        "stack": ["verification-before-completion"],
        "task_spec": {
            "intent": "Fix the flaky retry test.",
            "constraints": "Branch from main; no force-push.",
            "acceptance": "pytest green; CI green.",
            "files": "scripts/retry.py, scripts/tests/test_retry.py",
            "operator_context": "personal profile, full autonomy",
        },
        "flags": {"worktree": False, "local_only": False, "thinking_override": None},
        "token_remaining": 480000,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Marker round-trip: build with the script, parse with the REAL recorder.
# Each case: (decision overrides, expected recorder reads).
# ---------------------------------------------------------------------------

ROUND_TRIP_CASES = [
    pytest.param(  # V1: everything — numeric health, all gate inputs, alts, stack, model
        {
            "agent": "golang-general-engineer",
            "skill": "go-patterns",
            "complexity": "complex",
            "model": "opus",
            "manual_model_override": True,
            "health": {
                "confidence": 0.72,
                "n": 6,
                "failure": 1,
                "action": "keep",
                "alts": ["claude:quick", "python-general-engineer:tdd"],
            },
            "stack": ["test-driven-development", "verification-before-completion"],
        },
        {
            "agent": "golang-general-engineer",
            "skill": "go-patterns",
            "complexity": "complex",
            "model": "opus",
            "health": 0.72,
            "n": 6,
            "failure": 1,
            "action": "keep",
            "alternates": ["claude:quick", "python-general-engineer:tdd"],
            "gate_inputs_present": True,
            "stack": ["test-driven-development", "verification-before-completion"],
        },
        id="full-gate-inputs-alts-stack-model",
    ),
    pytest.param(  # V2: no weight row (health=-) with a stack
        {"health": {}, "stack": ["quick"]},
        {
            "agent": "python-general-engineer",
            "skill": "test-driven-development",
            "complexity": "medium",
            "model": "opus",
            "health": None,
            "n": None,
            "failure": None,
            "action": None,
            "alternates": None,
            "gate_inputs_present": True,
            "stack": ["quick"],
        },
        id="health-dash-with-stack",
    ),
    pytest.param(  # V3: agent-only routing => skill=-, recorder reads ""
        # Trivial only: simple/medium/complex now hard-fail on a missing skill.
        {"skill": "", "complexity": "trivial", "health": None, "stack": []},
        {
            "agent": "python-general-engineer",
            "skill": "",
            "complexity": "trivial",
            "model": "opus",
            "health": None,
            "gate_inputs_present": True,
            "stack": None,
        },
        id="agent-only-skill-dash",
    ),
    pytest.param(  # V4: numeric health alone — no n/fail/action/alts tokens
        {"health": {"confidence": 0.5}, "stack": []},
        {
            "agent": "python-general-engineer",
            "skill": "test-driven-development",
            "complexity": "medium",
            "model": "opus",
            "health": 0.5,
            "n": None,
            "failure": None,
            "action": None,
            "alternates": None,
            "gate_inputs_present": True,
            "stack": None,
        },
        id="numeric-health-alone",
    ),
    pytest.param(  # V5: simple complexity, model omitted => model=-
        {"complexity": "simple", "health": None, "stack": [], "model": None},
        {
            "agent": "python-general-engineer",
            "skill": "test-driven-development",
            "complexity": "simple",
            "model": None,
            "health": None,
            "gate_inputs_present": True,
            "stack": None,
        },
        id="simple-no-model-no-health",
    ),
    pytest.param(  # V6: confidence 1.0 formats as integer '1'; tiebreak action
        {"health": {"confidence": 1.0, "n": 12, "failure": 0, "action": "tiebreak"}, "stack": []},
        {
            "agent": "python-general-engineer",
            "skill": "test-driven-development",
            "complexity": "medium",
            "model": "opus",
            "health": 1.0,
            "n": 12,
            "failure": 0,
            "action": "tiebreak",
            "gate_inputs_present": True,
            "stack": None,
        },
        id="confidence-one-tiebreak",
    ),
    pytest.param(  # V7: trivial complexity, uppercase input normalized, model omitted
        {"complexity": "Trivial", "agent": "CLAUDE", "skill": "quick", "health": None, "stack": [], "model": None},
        {
            "agent": "claude",
            "skill": "quick",
            "complexity": "trivial",
            "model": None,
            "health": None,
            "gate_inputs_present": True,
            "stack": None,
        },
        id="case-normalized-trivial-no-model",
    ),
    pytest.param(  # V8: legacy GPT-5.5 remains a manual-only compatibility lane.
        {"model": "gpt-5.5", "model_effort": "high", "manual_model_override": True},
        {
            "agent": "python-general-engineer",
            "skill": "test-driven-development",
            "complexity": "medium",
            "model": "gpt-5.5",
            "health": 0.72,
            "n": 6,
            "failure": 0,
            "action": "keep",
            "alternates": None,
            "gate_inputs_present": True,
            "stack": ["verification-before-completion"],
        },
        id="gpt-5.5-manual-compatibility-model",
    ),
    pytest.param(  # V9: old marker without model= (backward compat)
        # Simulate by checking recorder parses model=None from a pre-model marker
        {"complexity": "simple", "model": None, "health": None, "stack": []},
        {
            "agent": "python-general-engineer",
            "skill": "test-driven-development",
            "complexity": "simple",
            "model": None,
            "health": None,
            "gate_inputs_present": True,
            "stack": None,
        },
        id="backward-compat-no-model-token",
    ),
]


@pytest.mark.parametrize(("overrides", "expected"), ROUND_TRIP_CASES)
def test_marker_round_trip_with_real_recorder(overrides, expected):
    """Every emitted marker parses with the shipped recorder, field for field."""
    preamble = bd.build_preamble(_decision(**overrides))

    routed = recorder.parse_do_route_marker(preamble)
    assert routed == (expected["agent"], expected["skill"])

    complexity, invalid = recorder.parse_marker_complexity(preamble)
    assert (complexity, invalid) == (expected["complexity"], "")

    assert recorder.parse_stack(preamble) == expected["stack"]
    assert recorder.parse_model(preamble) == expected["model"]

    health = recorder.parse_health_inputs(preamble)
    assert health["health"] == expected["health"]
    assert health["gate_inputs_present"] == expected["gate_inputs_present"]
    for key in ("n", "failure", "action", "alternates"):
        assert health[key] == expected.get(key), key


def test_marker_is_first_line_at_line_start():
    """The recorder anchors ^\\s*\\[do-route\\]; the marker must open line 1."""
    preamble = bd.build_preamble(_decision())
    assert preamble.splitlines()[0].startswith("[do-route] agent=")


# ---------------------------------------------------------------------------
# Preamble completeness and order.
# ---------------------------------------------------------------------------


def test_preamble_contains_every_mandatory_block_in_order():
    preamble = bd.build_preamble(_decision(complexity="complex"))
    ordered = [
        "[do-route] agent=python-general-engineer skill=test-driven-development complexity=complex model=opus",
        "Call the Skill tool with `test-driven-development`.",
        "Call the Skill tool with `verification-before-completion`.",
        bd.THINKING_SLOW,
        "~480000 tokens available for this task; prioritize accordingly.",
        "## Task Specification (auto-extracted)",
        "**Intent:** Fix the flaky retry test.",
        "**Constraints:** Branch from main; no force-push.",
        "**Acceptance criteria:** pytest green; CI green.",
        "**Relevant file locations:** scripts/retry.py, scripts/tests/test_retry.py",
        "**Operator context:** personal profile, full autonomy",
        bd.INJ_REFERENCE_LOADING,
        bd.INJ_COMPLETENESS,
        bd.INJ_DENSE_COMPLETE,
        bd.INJ_BASE_INSTRUCTIONS,
        bd.INJ_ROUTE_FIT,
    ]
    pos = -1
    for piece in ordered:
        found = preamble.find(piece)
        assert found > pos, f"missing or out of order: {piece[:60]!r}"
        pos = found


def test_worktree_and_local_only_blocks_follow_flags():
    both = bd.build_preamble(_decision(flags={"worktree": True, "local_only": True}))
    assert bd.WORKTREE_RULES in both
    assert bd.LOCAL_ONLY_BLOCK in both
    neither = bd.build_preamble(_decision())
    assert bd.WORKTREE_RULES not in neither
    assert bd.LOCAL_ONLY_BLOCK not in neither


def test_skill_calls_are_primary_first_ordered_and_deduplicated():
    decision = _decision(
        skill="test-driven-development",
        stack=["verification-before-completion", "test-driven-development", "quick", "quick"],
    )
    calls = bd.render_skill_calls(decision).splitlines()
    assert calls == [
        "Call the Skill tool with `test-driven-development`.",
        "Call the Skill tool with `verification-before-completion`.",
        "Call the Skill tool with `quick`.",
    ]


def test_shared_pattern_stack_entry_is_not_a_skill_call():
    decision = _decision(stack=["anti-rationalization-core", "verification-before-completion"])
    calls = bd.render_skill_calls(decision)
    assert "anti-rationalization-core" not in calls
    assert calls.endswith("Call the Skill tool with `verification-before-completion`.")


@pytest.mark.parametrize("name", ["reviewer-code", "feature-pipeline", "not-a-real-component"])
def test_non_skill_stack_names_fail_closed(name):
    with pytest.raises(bd.InputError, match="skill call"):
        bd.build_preamble(_decision(stack=[name]))


def test_pipeline_is_validated_and_marked_but_never_called_as_a_skill():
    preamble = bd.build_preamble(_decision(pipeline="feature-pipeline"))
    assert " pipeline=feature-pipeline " in preamble.splitlines()[0] + " "
    assert "Call the Skill tool with `feature-pipeline`." not in preamble


def test_unknown_pipeline_fails_closed():
    with pytest.raises(bd.InputError, match="pipeline-index"):
        bd.build_preamble(_decision(pipeline="not-a-pipeline"))


@pytest.mark.parametrize(
    ("complexity", "override", "expected"),
    [
        ("simple", None, "THINKING_FAST"),
        ("medium", None, ""),
        ("trivial", None, ""),
        ("complex", None, "THINKING_SLOW"),
        ("simple", "slow", "THINKING_SLOW"),  # category override beats complexity
        ("complex", "fast", "THINKING_FAST"),
    ],
)
def test_thinking_directive_by_complexity_and_override(complexity, override, expected):
    decision = _decision(complexity=complexity, flags={"thinking_override": override})
    directive = bd.build_thinking(decision)
    assert directive == (getattr(bd, expected) if expected else "")
    if expected:
        assert getattr(bd, expected) in bd.build_preamble(decision)
    else:
        assert bd.THINKING_FAST not in bd.build_preamble(decision)
        assert bd.THINKING_SLOW not in bd.build_preamble(decision)


# ---------------------------------------------------------------------------
# Graceful degradation and token budget.
# ---------------------------------------------------------------------------


def test_missing_optional_fields_omit_their_blocks_only():
    # Trivial is the only complexity that may omit the skill (the
    # skill-greediness gate is HARD for simple/medium/complex).
    minimal = {"agent": "claude", "complexity": "trivial", "model": "opus"}
    preamble = bd.build_preamble(minimal)
    assert preamble.startswith("[do-route] agent=claude skill=- complexity=trivial model=opus health=-\n")
    assert "## Task Specification" not in preamble
    assert "Call the Skill tool" not in preamble
    assert "stack={" not in preamble
    # Mandatory blocks survive the minimal input.
    for injection in (bd.INJ_REFERENCE_LOADING, bd.INJ_COMPLETENESS, bd.INJ_DENSE_COMPLETE, bd.INJ_BASE_INSTRUCTIONS):
        assert injection in preamble
    assert "tokens available for this task" in preamble


def test_partial_task_spec_emits_only_given_fields():
    preamble = bd.build_preamble(_decision(task_spec={"intent": "Do the thing."}))
    assert "**Intent:** Do the thing." in preamble
    assert "**Constraints:**" not in preamble
    assert "**Acceptance criteria:**" not in preamble


def test_request_verbatim_is_first_task_spec_line_with_exact_label():
    preamble = bd.build_preamble(_decision(task_spec={"intent": "x", "request_verbatim": "hello world"}))
    block = preamble.split("## Task Specification (auto-extracted)\n\n", 1)[1]
    lines = block.split("\n")
    assert lines[0] == "**Request (verbatim):** hello world"
    assert lines[1] == "**Intent:** x"


def test_request_verbatim_absent_leaves_output_unchanged():
    with_none = bd.build_preamble(_decision(task_spec={"intent": "x"}))
    with_empty = bd.build_preamble(_decision(task_spec={"intent": "x", "request_verbatim": "  "}))
    assert "Request (verbatim)" not in with_none
    assert with_empty == with_none


def test_token_budget_reads_settings_and_defaults(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"orchestration": {"token_budget": 250000}}))
    decision = _decision(token_remaining=None)
    line = bd.build_token_line(decision, settings_path=settings)
    assert line == "~250000 tokens available for this task; prioritize accordingly."
    # Missing file => documented default 500000.
    line = bd.build_token_line(decision, settings_path=tmp_path / "absent.json")
    assert line == "~500000 tokens available for this task; prioritize accordingly."


def test_determinism_same_input_same_bytes():
    decision = _decision()
    assert bd.build_preamble(decision) == bd.build_preamble(decision)


# ---------------------------------------------------------------------------
# Validation errors.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"agent": ""},
        {"agent": "Bad Agent!"},
        {"complexity": "low"},  # the audit's real-world invalid value
        {"complexity": ""},
        {"model": "haiku"},  # retired model — not in VALID_MODELS
        {"health": {"confidence": 1.5}},
        {"health": {"confidence": -0.1}},
        {"health": {"confidence": 0.5, "action": "boost"}},
        {"health": {"confidence": 0.5, "n": -1}},
        {"stack": ["has space"]},
        {"flags": {"thinking_override": "deep"}},
        {"token_remaining": -5},
    ],
)
def test_invalid_input_raises(overrides):
    with pytest.raises(bd.InputError):
        bd.build_preamble(_decision(**overrides))


# ---------------------------------------------------------------------------
# Model enforcement: missing model on medium/complex must error.
# ---------------------------------------------------------------------------


def test_model_required_for_medium_errors_on_omission():
    """Medium complexity with no model must fail — the live incident this fixes."""
    with pytest.raises(bd.InputError, match="'model' is required"):
        bd.build_preamble(_decision(model=None))


def test_model_required_for_complex_errors_on_omission():
    with pytest.raises(bd.InputError, match="'model' is required"):
        bd.build_preamble(_decision(complexity="complex", model=None))


# ---------------------------------------------------------------------------
# Route-fit injection (D): every dispatch asks for the closing banner, and the
# banner the injection names is the one the recorder parses.
# ---------------------------------------------------------------------------


def test_route_fit_injection_present_on_every_dispatch():
    for complexity in ("trivial", "simple", "medium", "complex"):
        preamble = bd.build_preamble(_decision(complexity=complexity, model="opus"))
        assert bd.INJ_ROUTE_FIT in preamble, complexity
        assert "route-fit:" in preamble


@pytest.mark.parametrize("verdict", ["ok", "wrong-agent", "wrong-skill", "needs-coordinator", "underspecified"])
def test_every_injected_verdict_parses_with_the_real_recorder(verdict):
    """The enum the injection advertises must be exactly what the recorder reads."""
    assert verdict in bd.INJ_ROUTE_FIT
    assert recorder.parse_route_fit(f"work done.\nroute-fit: {verdict}") == verdict


# ---------------------------------------------------------------------------
# Agent validation: unknown agent coerces (never raises); general-purpose needs
# a reason; the fallback token survives the recorder's parser.
# ---------------------------------------------------------------------------


def test_unknown_agent_coerces_to_general_purpose_with_a_reason():
    """An exception mid-session would stall real work, so this must NOT raise."""
    marker = bd.build_marker(_decision(agent="python-hook-wizard"))
    assert "agent=general-purpose" in marker
    assert "fallback=invalid-agent:python-hook-wizard" in marker
    # The coerced marker still parses field-for-field with the shipped recorder.
    assert recorder.parse_do_route_marker(marker) == ("general-purpose", "test-driven-development")
    assert recorder.parse_marker_complexity(marker) == ("medium", "")
    assert recorder.parse_model(marker) == "opus"
    assert recorder.parse_health_inputs(marker)["health"] == 0.72
    assert recorder.parse_fallback_reason(marker) == "invalid-agent:python-hook-wizard"


def test_known_agent_and_builtins_are_not_coerced():
    for agent in ("python-general-engineer", "hook-development-engineer", "claude"):
        marker = bd.build_marker(_decision(agent=agent))
        assert f"agent={agent}" in marker
        assert "fallback=" not in marker


def test_unreadable_agent_index_fails_open(tmp_path):
    """No index => cannot validate => keep the agent. Never manufacture a fallback."""
    assert bd.load_known_agents(tmp_path / "nope.json") == frozenset()


def test_general_purpose_requires_a_fallback_reason():
    with pytest.raises(bd.InputError, match="fallback_reason"):
        bd.build_preamble(_decision(agent="general-purpose"))


def test_general_purpose_with_a_reason_emits_the_token():
    marker = bd.build_marker(_decision(agent="general-purpose", fallback_reason="No specialist matches!"))
    assert marker.endswith("fallback=no-specialist-matches")
    assert recorder.parse_fallback_reason(marker) == "no-specialist-matches"


def test_fallback_token_never_shifts_an_existing_marker_field():
    """`fallback=` is appended last; every other parsed field is byte-identical."""
    plain = bd.build_marker(_decision(agent="python-general-engineer"))
    fallen = bd.build_marker(_decision(agent="general-purpose", fallback_reason="no-specialist-match"))
    assert fallen == plain.replace("agent=python-general-engineer", "agent=general-purpose", 1) + (
        " fallback=no-specialist-match"
    )
    for parse in (recorder.parse_marker_complexity, recorder.parse_stack, recorder.parse_model):
        assert parse(fallen) == parse(plain)
    assert recorder.parse_health_inputs(fallen) == recorder.parse_health_inputs(plain)


def test_reason_without_a_letter_or_digit_raises():
    with pytest.raises(bd.InputError, match="fallback_reason"):
        bd.build_marker(_decision(agent="general-purpose", fallback_reason="!!!"))


# ---------------------------------------------------------------------------
# Skill enforcement: the skill-greediness gate, HARD for simple/medium/complex.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("complexity", ["simple", "medium", "complex"])
@pytest.mark.parametrize("skill", [None, "", "-"])
def test_missing_skill_raises_for_simple_and_above(complexity, skill):
    with pytest.raises(bd.InputError, match="'skill' is required"):
        bd.build_preamble(_decision(complexity=complexity, skill=skill, model="opus"))


def test_missing_skill_allowed_for_trivial():
    assert "skill=-" in bd.build_marker(_decision(complexity="trivial", skill=None))


def test_model_optional_for_trivial_and_simple():
    """Trivial/simple may omit model — inheritance risk is acceptable."""
    for complexity in ("trivial", "simple"):
        preamble = bd.build_preamble(_decision(complexity=complexity, model=None))
        assert "model=-" in preamble.splitlines()[0]


# ---------------------------------------------------------------------------
# GPT-5.6 model policy: benchmark-backed automatic defaults and manual lanes.
# ---------------------------------------------------------------------------

SUPPLIED_GPT_56_POINTS = {
    ("gpt-5.6-sol", "max"): (73, 8.39, 60_000, 61),
    ("gpt-5.6-sol", "xhigh"): (71, 4.70, 41_000, 44),
    ("gpt-5.6-sol", "high"): (69, 3.47, 28_000, 37),
    ("gpt-5.6-sol", "medium"): (61, 1.86, 18_000, 31),
    ("gpt-5.6-sol", "low"): (45, 1.07, 11_000, 23),
    ("gpt-5.6-terra", "max"): (70, 4.95, 72_000, 76),
    ("gpt-5.6-terra", "xhigh"): (60, 2.13, 40_000, 43),
    ("gpt-5.6-terra", "high"): (54, 1.13, 22_000, 34),
    ("gpt-5.6-terra", "medium"): (35, 0.58, 12_000, 25),
    ("gpt-5.6-terra", "low"): (24, 0.43, 8_600, 21),
    ("gpt-5.6-luna", "max"): (67, 3.03, 73_000, 102),
    ("gpt-5.6-luna", "xhigh"): (57, 1.54, 45_000, 71),
    ("gpt-5.6-luna", "high"): (44, 0.78, 26_000, 49),
    ("gpt-5.6-luna", "medium"): (11, 0.22, 8_200, 24),
    ("gpt-5.6-luna", "low"): (2, 0.07, 3_100, 12),
}


def _dominates(candidate: tuple[int, float, int, int], target: tuple[int, float, int, int]) -> bool:
    """Return whether ``candidate`` is at least as good on every supplied metric."""
    candidate_pass, candidate_cost, candidate_tokens, candidate_steps = candidate
    target_pass, target_cost, target_tokens, target_steps = target
    return (
        candidate_pass >= target_pass
        and candidate_cost <= target_cost
        and candidate_tokens <= target_tokens
        and candidate_steps <= target_steps
        and candidate != target
    )


@pytest.mark.parametrize(
    ("task_class", "model", "effort"),
    [
        ("low-risk", "gpt-5.6-terra", "high"),
        ("standard", "gpt-5.6-sol", "high"),
        ("high-risk", "gpt-5.6-sol", "xhigh"),
    ],
)
def test_gpt_56_policy_selects_the_automatic_pareto_defaults(task_class, model, effort):
    """Automatic task classes select only the documented benchmark defaults."""
    decision = _decision(model=None, model_policy=task_class, provider="openai")
    marker = bd.build_marker(decision)

    assert f"model={model}" in marker
    assert f"effort={effort}" in marker
    assert recorder.parse_model(marker) == model
    assert recorder.parse_model_effort(marker) == effort


def test_gpt_56_policy_points_are_not_dominated_on_supplied_metrics():
    """Automatic choices cannot regress to a worse quality/cost/latency point."""
    for policy, point in bd.AUTO_MODEL_POLICIES.items():
        assert point in SUPPLIED_GPT_56_POINTS, f"{policy} is not in the supplied benchmark"
        target = SUPPLIED_GPT_56_POINTS[point]
        assert not any(_dominates(candidate, target) for candidate in SUPPLIED_GPT_56_POINTS.values()), (
            f"{policy} selects dominated point {point}"
        )


@pytest.mark.parametrize("model", ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"))
@pytest.mark.parametrize("effort", ("low", "medium", "high", "xhigh", "max"))
def test_all_supplied_gpt_56_variants_and_efforts_are_valid_manual_overrides(model, effort):
    """Every supplied GPT-5.6 pair is representable without becoming an auto route."""
    marker = bd.build_marker(_decision(model=model, model_effort=effort, manual_model_override=True))
    assert f"model={model}" in marker
    assert f"effort={effort}" in marker


def test_exceptional_max_power_requires_explicit_override():
    """The most expensive benchmark point is opt-in, never an automatic default."""
    with pytest.raises(bd.InputError, match="manual_model_override"):
        bd.build_marker(_decision(model=None, model_policy="max-power", provider="openai"))

    marker = bd.build_marker(
        _decision(model=None, model_policy="max-power", manual_model_override=True, provider="openai")
    )
    assert "model=gpt-5.6-sol" in marker
    assert "effort=max" in marker

    # Anthropic max-power also requires override
    with pytest.raises(bd.InputError, match="manual_model_override"):
        bd.build_marker(_decision(model=None, model_policy="max-power", provider="anthropic"))

    marker = bd.build_marker(
        _decision(model=None, model_policy="max-power", manual_model_override=True, provider="anthropic")
    )
    assert "model=opus" in marker
    assert "effort=xhigh" in marker


def test_manual_override_can_replace_a_policy_default():
    """An explicit override wins over the automatic task-class selection."""
    marker = bd.build_marker(
        _decision(
            model_policy="standard",
            model="gpt-5.6-luna",
            model_effort="max",
            manual_model_override=True,
            provider="openai",
        )
    )
    assert "model=gpt-5.6-luna" in marker
    assert "effort=max" in marker


def test_manual_policy_model_override_requires_explicit_effort():
    """A different model family must never inherit the policy's effort silently."""
    with pytest.raises(bd.InputError, match="require 'model_effort'"):
        bd.build_marker(
            _decision(
                model_policy="standard",
                model="gpt-5.6-luna",
                manual_model_override=True,
                provider="openai",
            )
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"model": "gpt-5.5", "model_effort": "high"},
        {"model": "gpt-5.6-sol", "model_effort": "high"},
        {"model": "gpt-5.6-sol", "model_effort": "low"},
        {"model": "gpt-5.6-terra", "model_effort": "xhigh"},
        {"model": "gpt-5.6-luna", "model_effort": "max"},
        {"model": "gpt-5.6-sol", "model_effort": "ultra", "manual_model_override": True},
    ],
)
def test_non_default_openai_model_choices_require_manual_override(overrides):
    """Dominated and legacy choices cannot be selected accidentally."""
    with pytest.raises(bd.InputError):
        bd.build_marker(_decision(**overrides))


# ---------------------------------------------------------------------------
# Anthropic lane: benchmark-backed automatic defaults and manual lanes.
# ---------------------------------------------------------------------------

_DO_SKILL_PATH = REPO_ROOT / "skills" / "meta" / "do" / "SKILL.md"
_DOCUMENTED_EFFORTS = ("max", "xhigh", "high", "medium", "low")
_DOCUMENTED_ROW_MODELS = {
    "Opus-4.8 (prior measurement)": "opus-4.8",
    "Sonnet-5 (prior measurement)": "sonnet",
}


def _parse_cell(cell: str) -> tuple[int, float, int, int]:
    """Parse one `Pass@1 / cost / output tokens / steps` cell, expanding the `k` suffix."""
    passed, cost, tokens, steps = (part.strip() for part in cell.split("/"))
    scaled = int(float(tokens[:-1]) * 1000) if tokens.endswith("k") else int(tokens)
    return int(passed), float(cost), scaled, int(steps)


def _documented_claude_points() -> dict[tuple[str, str], tuple[int, float, int, int]]:
    """Read the Anthropic-lane benchmark table out of skills/meta/do/SKILL.md."""
    points: dict[tuple[str, str], tuple[int, float, int, int]] = {}
    for line in _DO_SKILL_PATH.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        model = _DOCUMENTED_ROW_MODELS.get(cells[0]) if cells else None
        if model is None or len(cells) != len(_DOCUMENTED_EFFORTS) + 1:
            continue
        for effort, cell in zip(_DOCUMENTED_EFFORTS, cells[1:]):
            points[(model, effort)] = _parse_cell(cell)
    return points


SUPPLIED_CLAUDE_POINTS = {
    ("opus-4.8", "max"): (59, 13.22, 135_000, 120),
    ("opus-4.8", "xhigh"): (54, 8.01, 86_000, 95),
    ("opus-4.8", "high"): (52, 4.28, 50_000, 73),
    ("opus-4.8", "medium"): (49, 3.44, 41_000, 66),
    ("opus-4.8", "low"): (41, 2.29, 29_000, 54),
    ("sonnet", "max"): (54, 26.40, 214_000, 268),
    ("sonnet", "xhigh"): (50, 11.89, 121_000, 186),
    ("sonnet", "high"): (48, 7.43, 87_000, 147),
    ("sonnet", "medium"): (40, 4.08, 57_000, 108),
    ("sonnet", "low"): (31, 2.19, 36_000, 77),
}


@pytest.mark.parametrize(
    ("task_class", "model", "effort"),
    [
        ("low-risk", "opus", "low"),
        ("standard", "opus", "medium"),
        ("high-risk", "opus", "high"),
    ],
)
def test_anthropic_policy_selects_opus_at_every_task_class(task_class, model, effort):
    """Anthropic automatic task classes select Opus 5, effort rising with risk class."""
    decision = _decision(model=None, model_policy=task_class, provider="anthropic")
    marker = bd.build_marker(decision)

    assert f"model={model}" in marker
    assert f"effort={effort}" in marker
    assert recorder.parse_model(marker) == model
    assert recorder.parse_model_effort(marker) == effort


def test_anthropic_policy_points_are_unmeasured_and_effort_rises_with_risk():
    """Opus 5 carries no DeepSWE point; the policy is grounded on effort ordering."""
    order = ["low", "medium", "high", "xhigh", "max"]
    previous = -1
    for policy in ("low-risk", "standard", "high-risk", "max-power"):
        model, effort = bd.ANTHROPIC_AUTO_POLICIES[policy]
        assert model == "opus", f"{policy} selects {model}, not the Opus 5 default"
        assert (model, effort) not in SUPPLIED_CLAUDE_POINTS, f"{policy} claims a benchmark point Opus 5 does not have"
        assert order.index(effort) > previous, f"{policy} breaks the start-low effort ordering"
        previous = order.index(effort)


def test_opus_max_requires_manual_override():
    """The unmeasured top tier stays an explicit escalation."""
    with pytest.raises(bd.InputError, match="manual_model_override"):
        bd.build_marker(_decision(model="opus", model_effort="max"))


def test_supplied_points_match_the_documented_benchmark_table():
    """The table in skills/meta/do/SKILL.md is the source; this dict must track it.

    Without this the dict is a private copy: an edit to the doc table (or a
    deleted row) leaves the Opus-5-has-no-benchmark-point check above asserting
    against numbers the toolkit no longer publishes.
    """
    assert _documented_claude_points() == SUPPLIED_CLAUDE_POINTS, (
        "SUPPLIED_CLAUDE_POINTS drifted from the Anthropic-lane table in skills/meta/do/SKILL.md"
    )


@pytest.mark.parametrize("model", ("sonnet",))
def test_off_policy_claude_models_require_manual_override(model):
    """Opus 5 is the default; sonnet is the manual-only pick."""
    with pytest.raises(bd.InputError, match="manual_model_override"):
        bd.build_marker(_decision(model=model))
    # With manual_override they work fine
    marker = bd.build_marker(_decision(model=model, manual_model_override=True))
    assert f"model={model}" in marker


def test_claude_model_effort_round_trip():
    """Claude model@effort (opus@high) parses and persists in the marker."""
    marker = bd.build_marker(_decision(model="opus", model_effort="high"))
    assert "model=opus" in marker
    assert "effort=high" in marker
    assert recorder.parse_model(marker) == "opus"
    assert recorder.parse_model_effort(marker) == "high"


def test_provider_absent_defaults_to_anthropic():
    """Missing provider field defaults to 'anthropic' (Claude Code is primary)."""
    decision = _decision(model=None, model_policy="standard")
    marker = bd.build_marker(decision)
    # Should resolve via Anthropic table: opus/medium
    assert "model=opus" in marker
    assert "effort=medium" in marker


def test_provider_openai_uses_openai_table():
    """provider='openai' routes through the GPT-5.6 policy table."""
    decision = _decision(model=None, model_policy="standard", provider="openai")
    marker = bd.build_marker(decision)
    assert "model=gpt-5.6-sol" in marker
    assert "effort=high" in marker


def test_provider_other_rejects_model_policy():
    """provider='other' cannot use model_policy — no hardcoded table."""
    with pytest.raises(bd.InputError, match="other"):
        bd.build_marker(_decision(model=None, model_policy="standard", provider="other"))


def test_cross_provider_policy_override_rejected():
    """Anthropic policy cannot be overridden with a GPT model (cross-lane)."""
    with pytest.raises(bd.InputError, match="Claude model"):
        bd.build_marker(
            _decision(
                model_policy="standard",
                model="gpt-5.6-sol",
                model_effort="high",
                manual_model_override=True,
                provider="anthropic",
            )
        )


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def _run_cli(*args, stdin_text=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        input=stdin_text,
        capture_output=True,
        text=True,
    )


def test_cli_json_flag_emits_preamble():
    result = _run_cli("--json", json.dumps(_decision()))
    assert result.returncode == 0
    assert result.stdout == bd.build_preamble(_decision())


def test_cli_json_file_and_stdin(tmp_path):
    decision = _decision()
    path = tmp_path / "route.json"
    path.write_text(json.dumps(decision))
    from_file = _run_cli("--json-file", str(path))
    from_stdin = _run_cli("--json-file", "-", stdin_text=json.dumps(decision))
    assert from_file.returncode == from_stdin.returncode == 0
    assert from_file.stdout == from_stdin.stdout == bd.build_preamble(decision)


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        json.dumps({"complexity": "medium"}),  # agent missing
        json.dumps({"agent": "claude", "complexity": "Low"}),  # invalid enum
        json.dumps({"agent": "claude", "complexity": "medium"}),  # model missing for medium
    ],
)
def test_cli_bad_input_exits_2_with_empty_stdout(payload):
    result = _run_cli("--json", payload)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "build-dispatch:" in result.stderr


def test_cli_model_missing_error_message():
    """CLI exit-2 message names the missing field and the allowed values."""
    result = _run_cli("--json", json.dumps({"agent": "claude", "skill": "quick", "complexity": "complex"}))
    assert result.returncode == 2
    assert "'model' is required" in result.stderr
    assert "Model Selection" in result.stderr or "sonnet" in result.stderr
