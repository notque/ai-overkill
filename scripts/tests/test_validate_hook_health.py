#!/usr/bin/env python3
"""Tests for hook-error repeat-offender health checks."""

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "validate-hook-health.py"
SPEC = importlib.util.spec_from_file_location("validate_hook_health", SCRIPT)
assert SPEC and SPEC.loader
health = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(health)


def _entry(hook: str, ts: datetime) -> str:
    return json.dumps({"ts": ts.isoformat(), "hook": hook, "type": "RuntimeError", "msg": "x"})


def _with_hook_files(monkeypatch, tmp_path, *names: str) -> Path:
    """Point HOOKS_DIR at a tmp dir holding a real file for each hook name.

    The repeat-offender check only fails on hooks that still exist in the repo,
    so a test using synthetic hook names must materialise them.
    """
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    for name in names:
        (hooks_dir / f"{name}.py").write_text("# stub\n", encoding="utf-8")
    monkeypatch.setattr(health, "HOOKS_DIR", hooks_dir)
    return hooks_dir


def test_repeat_offenders_ignore_old_and_malformed_entries(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    path = tmp_path / "hook-errors.jsonl"
    lines = [
        *[_entry("old-hook", now - timedelta(hours=169)) for _ in range(6)],
        *[_entry("recent-hook", now - timedelta(hours=1)) for _ in range(5)],
        json.dumps({"hook": "missing-ts"}),
        "not-json",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_HOOK_ERRORS_PATH", str(path))
    _with_hook_files(monkeypatch, tmp_path, "old-hook", "recent-hook")

    failures = health.check_hook_error_repeat_offenders(now=now)

    assert len(failures) == 1
    assert "recent-hook" in failures[0]
    assert "old-hook" not in failures[0]


def test_repeat_offenders_honor_runtime_path_override(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    default_path = tmp_path / "default.jsonl"
    override_path = tmp_path / "override.jsonl"
    default_path.write_text("\n".join(_entry("default-hook", now) for _ in range(5)) + "\n", encoding="utf-8")
    override_path.write_text("\n".join(_entry("override-hook", now) for _ in range(5)) + "\n", encoding="utf-8")
    monkeypatch.setattr(health, "DEFAULT_HOOK_ERRORS_JSONL", default_path)
    monkeypatch.setenv("CLAUDE_HOOK_ERRORS_PATH", str(override_path))
    _with_hook_files(monkeypatch, tmp_path, "default-hook", "override-hook")

    failures = health.check_hook_error_repeat_offenders(now=now)

    assert len(failures) == 1
    assert "override-hook" in failures[0]


def test_repeat_offender_lookback_is_configurable(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    path = tmp_path / "hook-errors.jsonl"
    path.write_text(
        "\n".join(_entry("twelve-hour-hook", now - timedelta(hours=12)) for _ in range(5)) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_HOOK_ERRORS_PATH", str(path))
    _with_hook_files(monkeypatch, tmp_path, "twelve-hour-hook")

    assert health.check_hook_error_repeat_offenders(lookback_hours=6, now=now) == []
    assert "twelve-hour-hook" in health.check_hook_error_repeat_offenders(lookback_hours=24, now=now)[0]


def test_default_lookback_covers_multi_day_crash_streaks(tmp_path, monkeypatch):
    """A sustained crash streak from days ago must still surface by default.

    Regression: adr-enforcement crashed 1,795 times over 8 days but the old
    24-hour default window only ever saw the final day's tail.
    """
    now = datetime.now(timezone.utc)
    path = tmp_path / "hook-errors.jsonl"
    path.write_text(
        "\n".join(_entry("six-day-old-hook", now - timedelta(days=6)) for _ in range(20)) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_HOOK_ERRORS_PATH", str(path))
    _with_hook_files(monkeypatch, tmp_path, "six-day-old-hook")

    failures = health.check_hook_error_repeat_offenders(now=now)

    assert len(failures) == 1
    assert "six-day-old-hook" in failures[0]


def test_stop_liveness_probe_does_not_audit_the_current_repo():
    stop_payload = health._EVENT_BASE["Stop"]

    assert stop_payload["cwd"] != str(health.REPO_ROOT)
    assert Path(stop_payload["cwd"]).is_dir()


def test_posttool_liveness_probe_uses_hook_utils_result_schema():
    result = health._EVENT_BASE["PostToolUse"]["tool_result"]

    assert result == {"output": "ok", "is_error": False}


def test_retired_hook_is_reported_as_a_note_not_a_failure(tmp_path, monkeypatch):
    """A deleted hook's historical errors must not fail a maintainer's run.

    Regression: retiring hooks/instruction-compliance.py left 37 errors inside
    the 168-hour window, so the validator failed for a week on a file nobody
    could fix. The errors still surface, as an informational note.
    """
    now = datetime.now(timezone.utc)
    path = tmp_path / "hook-errors.jsonl"
    lines = [
        *[_entry("retired-hook", now - timedelta(hours=2)) for _ in range(37)],
        *[_entry("live-hook", now - timedelta(hours=2)) for _ in range(6)],
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_HOOK_ERRORS_PATH", str(path))
    _with_hook_files(monkeypatch, tmp_path, "live-hook")  # retired-hook.py absent

    failures = health.check_hook_error_repeat_offenders(now=now)
    notes = health.hook_error_repeat_offender_notes(now=now)

    assert len(failures) == 1
    assert "live-hook" in failures[0]
    assert all("retired-hook" not in f for f in failures)
    assert len(notes) == 1
    assert "retired-hook" in notes[0]
    assert "37" in notes[0]
    assert "No action needed" in notes[0]


def test_live_hook_never_appears_in_the_retired_notes(tmp_path, monkeypatch):
    """Notes are for absent files only; a present hook stays a hard failure."""
    now = datetime.now(timezone.utc)
    path = tmp_path / "hook-errors.jsonl"
    path.write_text("\n".join(_entry("live-hook", now) for _ in range(9)) + "\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_HOOK_ERRORS_PATH", str(path))
    _with_hook_files(monkeypatch, tmp_path, "live-hook")

    assert health.hook_error_repeat_offender_notes(now=now) == []
    assert len(health.check_hook_error_repeat_offenders(now=now)) == 1


def test_path_shaped_hook_names_never_escape_the_hooks_dir(tmp_path, monkeypatch):
    """A hook field carrying a path must not be resolved outside hooks/."""
    now = datetime.now(timezone.utc)
    path = tmp_path / "hook-errors.jsonl"
    path.write_text("\n".join(_entry("../../etc/passwd", now) for _ in range(6)) + "\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_HOOK_ERRORS_PATH", str(path))
    _with_hook_files(monkeypatch, tmp_path)

    assert health.check_hook_error_repeat_offenders(now=now) == []
    assert len(health.hook_error_repeat_offender_notes(now=now)) == 1
