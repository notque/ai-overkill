#!/usr/bin/env python3
"""Tests for the reference-loading-enforcer PreToolUse:Agent hook.

Pins the double-injection fix: the hook's "already present" marker must match
the reference-loading text that scripts/build-dispatch.py injects into every
/do dispatch (INJ_REFERENCE_LOADING). Before the fix the marker only matched
the hook's own output, so every dispatched subagent prompt got a second,
near-duplicate reference-loading instruction.

Run with: python3 -m pytest hooks/tests/test_reference_loading_enforcer.py -v
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "hooks" / "reference-loading-enforcer.py"
BUILD_DISPATCH_PATH = REPO_ROOT / "scripts" / "build-dispatch.py"


def _load_inj_reference_loading() -> str:
    """Return INJ_REFERENCE_LOADING verbatim from scripts/build-dispatch.py."""
    spec = importlib.util.spec_from_file_location("build_dispatch", BUILD_DISPATCH_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.INJ_REFERENCE_LOADING


def _run_hook(prompt: str) -> str:
    """Run the hook with a PreToolUse Agent payload; return stdout."""
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Agent",
        "tool_input": {"prompt": prompt, "subagent_type": "python-general-engineer"},
    }
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, f"hook must exit 0, got {result.returncode}: {result.stderr}"
    return result.stdout


def test_injects_when_prompt_has_no_reference_loading_instruction() -> None:
    """A bare task prompt gets the reference-loading instruction injected."""
    stdout = _run_hook("Fix the flaky retry test in client.py.")
    assert "Reference Loading Table" in stdout


def test_skips_when_build_dispatch_already_injected() -> None:
    """The exact /do dispatch text must satisfy the marker — no double inject.

    Loads INJ_REFERENCE_LOADING from scripts/build-dispatch.py at test time, so
    rewording that constant breaks this test instead of silently re-enabling
    double injection.
    """
    inj = _load_inj_reference_loading()
    stdout = _run_hook(f"Fix the flaky retry test in client.py.\n\n{inj}")
    assert "Reference Loading Table" not in stdout


def test_skips_when_own_marker_already_present() -> None:
    """The hook's own injected text also satisfies the marker (idempotent)."""
    stdout_first = _run_hook("Fix the flaky retry test in client.py.")
    injected = json.loads(stdout_first)["hookSpecificOutput"]["additionalContext"]
    stdout_second = _run_hook(f"Fix the flaky retry test in client.py.\n\n{injected}")
    assert "Reference Loading Table" not in stdout_second


def test_ignores_non_agent_tools() -> None:
    """Non-Agent tool events pass through with no injection."""
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "ls"},
    }
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0
    assert "Reference Loading Table" not in result.stdout
