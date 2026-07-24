#!/usr/bin/env python3
"""Regression tests for the adr-enforcement PostToolUse hook.

Pins the fix for the largest crash source in hook-errors.jsonl: 1,795 logged
``NameError: name '_EVENT_NAME' is not defined`` crashes (2026-07-03 to
2026-07-11). The module constant was spelled ``__EVENT_NAME`` while the code
referenced ``_EVENT_NAME``, so every invocation crashed. The typo shipped in
the hook's initial release, stayed invisible until #858 added loud error
logging, and was fixed as a side effect of #874. These tests keep it fixed:

1. Every representative payload must run crash-free: exit 0, valid JSON on
   stdout, and no HOOK-ERROR line on stderr.
2. No hook may define a module-level ``__``-prefixed constant. Three other
   hooks carried the same ``__EVENT_NAME`` spelling; the crash fired exactly
   when a later edit used the conventional ``_EVENT_NAME`` name.

Run with: python3 -m pytest hooks/tests/test_adr_enforcement.py -v
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "hooks" / "adr-enforcement.py"
HOOKS_DIR = REPO_ROOT / "hooks"


def _run_hook(payload: dict | None, tmp_path: Path) -> subprocess.CompletedProcess:
    """Run the hook with the given payload (None = empty stdin)."""
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="" if payload is None else json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
        env={"PATH": "/usr/bin:/bin", "CLAUDE_HOOK_ERRORS_PATH": str(tmp_path / "hook-errors.jsonl")},
    )


def _assert_clean(result: subprocess.CompletedProcess) -> None:
    """Exit 0, parseable JSON stdout, and no crash line on stderr."""
    assert result.returncode == 0, f"hook must exit 0, got {result.returncode}: {result.stderr}"
    assert "HOOK-ERROR" not in result.stderr, f"hook crashed: {result.stderr}"
    if result.stdout.strip():
        json.loads(result.stdout)


def test_empty_stdin_runs_clean(tmp_path: Path) -> None:
    """Empty stdin takes the earliest empty_output(_EVENT_NAME) path."""
    _assert_clean(_run_hook(None, tmp_path))


def test_missing_file_path_runs_clean(tmp_path: Path) -> None:
    """A payload without file_path exercised the crashing NameError line."""
    payload = {"tool_name": "Edit", "tool_input": {"file_path": ""}, "cwd": str(tmp_path)}
    _assert_clean(_run_hook(payload, tmp_path))


def test_non_component_file_runs_clean(tmp_path: Path) -> None:
    """Non-pipeline files skip silently, without crashing."""
    payload = {
        "tool_name": "Edit",
        "tool_input": {"file_path": str(tmp_path / "notes.txt")},
        "cwd": str(tmp_path),
    }
    _assert_clean(_run_hook(payload, tmp_path))


def test_component_file_without_adr_session_runs_clean(tmp_path: Path) -> None:
    """A hooks/*.py component path without .adr-session.json skips silently."""
    (tmp_path / "hooks").mkdir()
    target = tmp_path / "hooks" / "example.py"
    target.write_text("print('hi')\n", encoding="utf-8")
    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(target)}, "cwd": str(tmp_path)}
    result = _run_hook(payload, tmp_path)
    _assert_clean(result)
    assert "COMPLIANCE CHECK" not in result.stdout


@pytest.mark.parametrize("hook_file", sorted(HOOKS_DIR.glob("*.py")), ids=lambda p: p.name)
def test_no_module_level_dunder_constants(hook_file: Path) -> None:
    """Ban the ``__CONSTANT = ...`` spelling that caused the crash.

    ``__EVENT_NAME`` next to code written against ``_EVENT_NAME`` produced
    1,795 silent-then-logged NameError crashes. Single leading underscore is
    the convention; two invite exactly that mismatch (and class-body name
    mangling besides).
    """
    pattern = re.compile(r"^__[A-Z][A-Z0-9_]* *=", re.MULTILINE)
    matches = pattern.findall(hook_file.read_text(encoding="utf-8"))
    assert not matches, (
        f"{hook_file.name} defines module-level dunder constant(s): {matches} — use a single leading underscore"
    )
