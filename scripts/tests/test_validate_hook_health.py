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
