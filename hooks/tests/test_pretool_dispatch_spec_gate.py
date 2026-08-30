"""Behavior and protocol tests for the dispatch spec gate (PreToolUse:Agent)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "pretool-dispatch-spec-gate.py"
BUILD_DISPATCH = ROOT / "scripts" / "build-dispatch.py"
SETTINGS = ROOT / ".claude" / "settings.json"

REQUIRED = ("**Request (verbatim):**", "**Acceptance criteria:**", "## Repo state")


def _run(stdin: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = {k: v for k, v in os.environ.items() if not k.startswith("DISPATCH_SPEC_GATE")}
    merged.update(env or {})
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        env=merged,
        timeout=10,
        check=False,
    )


def _event(prompt: str, tool_name: str = "Agent") -> str:
    return json.dumps({"hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": {"prompt": prompt}})


def _payload(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)["hookSpecificOutput"]


def _load_build_dispatch():
    spec = importlib.util.spec_from_file_location("build_dispatch", BUILD_DISPATCH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BARE_MEDIUM = "[do-route] agent=x skill=y complexity=medium model=opus\n**Intent:** z"


# --- protocol -----------------------------------------------------------------


def test_empty_stdin_exits_zero_and_silent() -> None:
    result = _run("")
    assert result.returncode == 0
    assert result.stdout == ""


def test_malformed_json_exits_zero_and_silent() -> None:
    result = _run("{not json")
    assert result.returncode == 0
    assert result.stdout == ""


@pytest.mark.parametrize("stdin", ["[]", '{"tool_name":"Agent"}', '{"tool_name":"Agent","tool_input":[]}'])
def test_unexpected_shapes_stay_silent(stdin: str) -> None:
    result = _run(stdin)
    assert result.returncode == 0
    assert result.stdout == ""


def test_non_agent_tool_stays_silent() -> None:
    result = _run(_event(BARE_MEDIUM, tool_name="Bash"))
    assert result.returncode == 0
    assert result.stdout == ""


# --- gating -------------------------------------------------------------------


def test_medium_without_blocks_warns_with_every_missing_label() -> None:
    result = _run(_event(BARE_MEDIUM))
    assert result.returncode == 0
    out = _payload(result)
    assert out["hookEventName"] == "PreToolUse"
    assert "permissionDecision" not in out
    context = out["additionalContext"]
    assert context.startswith("[dispatch-spec-gate]")
    for label in REQUIRED:
        assert label in context
    assert "build-dispatch.py" in context
    assert "verbatim" in context


def test_complex_without_blocks_warns() -> None:
    result = _run(_event(BARE_MEDIUM.replace("complexity=medium", "complexity=complex")))
    assert "complexity=complex" in _payload(result)["additionalContext"]


@pytest.mark.parametrize("complexity", ["trivial", "simple"])
def test_low_complexity_stays_silent(complexity: str) -> None:
    result = _run(_event(BARE_MEDIUM.replace("complexity=medium", f"complexity={complexity}")))
    assert result.returncode == 0
    assert result.stdout == ""


def test_no_marker_stays_silent() -> None:
    result = _run(_event("Fix the bug in foo.py. complexity=medium is mentioned but no marker leads."))
    assert result.returncode == 0
    assert result.stdout == ""


def test_marker_not_on_first_line_stays_silent() -> None:
    result = _run(_event("Preamble text\n" + BARE_MEDIUM))
    assert result.returncode == 0
    assert result.stdout == ""


def test_only_missing_labels_are_named() -> None:
    prompt = BARE_MEDIUM + "\n**Request (verbatim):** do it\n**Acceptance criteria:** passes"
    context = _payload(_run(_event(prompt)))["additionalContext"]
    assert "missing 1 handoff block(s)" in context
    assert "## Repo state" in context
    assert "**Request (verbatim):**" not in context
    assert "**Acceptance criteria:**" not in context


def test_all_blocks_present_stays_silent() -> None:
    prompt = BARE_MEDIUM + "\n" + "\n".join(f"{label} filled" for label in REQUIRED)
    result = _run(_event(prompt))
    assert result.returncode == 0
    assert result.stdout == ""


# --- modes --------------------------------------------------------------------


def test_deny_mode_emits_permission_decision_with_same_reason() -> None:
    warn = _payload(_run(_event(BARE_MEDIUM)))["additionalContext"]
    result = _run(_event(BARE_MEDIUM), env={"DISPATCH_SPEC_GATE_MODE": "deny"})
    assert result.returncode == 0
    out = _payload(result)
    assert out["permissionDecision"] == "deny"
    assert out["permissionDecisionReason"] == warn
    assert "additionalContext" not in out


def test_deny_mode_stays_silent_when_complete() -> None:
    prompt = BARE_MEDIUM + "\n" + "\n".join(REQUIRED)
    result = _run(_event(prompt), env={"DISPATCH_SPEC_GATE_MODE": "deny"})
    assert result.returncode == 0
    assert result.stdout == ""


def test_bypass_disables_gate() -> None:
    result = _run(_event(BARE_MEDIUM), env={"DISPATCH_SPEC_GATE_BYPASS": "1", "DISPATCH_SPEC_GATE_MODE": "deny"})
    assert result.returncode == 0
    assert result.stdout == ""


# --- round-trip lock against build-dispatch.py --------------------------------


def _decision(complexity: str) -> dict:
    return {
        "agent": "python-general-engineer",
        "skill": "test-driven-development",
        "complexity": complexity,
        "model": "opus",
        "task_spec": {
            "request_verbatim": "make the thing",
            "intent": "make the thing work",
            "acceptance": "tests pass",
        },
    }


def test_full_preamble_from_build_dispatch_stays_silent() -> None:
    build = _load_build_dispatch()
    preamble = build.build_preamble(_decision("medium"), SETTINGS, gather=True, repo_root=ROOT)
    for label in REQUIRED:
        assert label in preamble, f"build_preamble no longer emits {label!r}; gate labels drifted"
    result = _run(_event(preamble))
    assert result.returncode == 0
    assert result.stdout == ""


def test_no_gather_preamble_at_medium_warns_about_repo_state_only() -> None:
    build = _load_build_dispatch()
    preamble = build.build_preamble(_decision("medium"), SETTINGS, gather=False, repo_root=ROOT)
    context = _payload(_run(_event(preamble)))["additionalContext"]
    assert "missing 1 handoff block(s)" in context
    assert "## Repo state" in context


def test_no_gather_preamble_at_simple_stays_silent() -> None:
    build = _load_build_dispatch()
    preamble = build.build_preamble(_decision("simple"), SETTINGS, gather=False, repo_root=ROOT)
    result = _run(_event(preamble))
    assert result.stdout == ""


# --- budget and registration --------------------------------------------------


def test_silent_path_under_50ms_median() -> None:
    samples = []
    for _ in range(5):
        start = time.perf_counter()
        _run(_event(BARE_MEDIUM.replace("complexity=medium", "complexity=simple")))
        samples.append(time.perf_counter() - start)
    assert sorted(samples)[2] < 0.05, samples


def test_registered_in_pretooluse_agent_group() -> None:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    groups = [g for g in settings["hooks"]["PreToolUse"] if g.get("matcher") == "Agent"]
    commands = [h["command"] for g in groups for h in g["hooks"]]
    assert any("pretool-dispatch-spec-gate.py" in c for c in commands)
