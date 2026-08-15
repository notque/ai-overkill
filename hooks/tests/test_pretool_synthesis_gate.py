#!/usr/bin/env python3
"""Tests for the pretool-synthesis-gate hook.

Two obligations pull in opposite directions here:

1. The gate must stay exactly as strict. A genuine session blocks writes under
   agents/ and skills/, and the stale-session work must not weaken that.
2. A session that was never closed must announce itself. The 2026-08-11 incident
   cost three days because the denial only said "run the consultation" and gave
   no hint the session was stale and pointing at a finished ADR.

Every test uses a tmp dir as the project root, so the real .adr-session.json is
never read.

Run with: python3 -m pytest hooks/tests/test_pretool_synthesis_gate.py -v
"""

import importlib.util
import io
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).parent.parent / "pretool-synthesis-gate.py"

spec = importlib.util.spec_from_file_location("pretool_synthesis_gate", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

GATED_TARGET = "skills/some-skill/SKILL.md"

COMPLETE_ADR = "# ADR\n\n## Checklist\n\n- [x] One\n- [x] Two\n"
INCOMPLETE_ADR = "# ADR\n\n## Checklist\n\n- [x] One\n- [ ] Two\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_main(stdin_payload: str, env: dict | None = None) -> tuple[int, str]:
    """Invoke mod.main(); return (2 if denied else 0, denial reason).

    Deny detection mirrors test_pretool_adr_creation_gate.py.
    """
    base_env = dict(os.environ)
    base_env.pop(mod._BYPASS_ENV, None)
    if env:
        base_env.update(env)

    stdout_capture = io.StringIO()
    with (
        patch.dict(os.environ, base_env, clear=True),
        patch.object(mod, "read_stdin", return_value=stdin_payload),
        patch("sys.stdout", stdout_capture),
    ):
        try:
            mod.main()
        except SystemExit:
            pass

    output = stdout_capture.getvalue().strip()
    if output:
        try:
            parsed = json.loads(output)
            hook_out = parsed.get("hookSpecificOutput", {})
            if hook_out.get("permissionDecision") == "deny":
                return 2, hook_out.get("permissionDecisionReason", "")
        except (json.JSONDecodeError, AttributeError):
            pass
    return 0, ""


def _event(file_path: str, cwd: str) -> str:
    return json.dumps({"tool_name": "Write", "tool_input": {"file_path": file_path}, "cwd": cwd})


def _write_session(root: Path, *, age: timedelta, adr_path: str | None = "adr/test-adr.md") -> None:
    """Register a session in root, back-dated by `age`."""
    session = {
        "adr_hash": "sha256:" + "0" * 64,
        "domain": "test-adr",
        "registered_at": (datetime.now(timezone.utc) - age).isoformat(),
        "cwd": str(root),
    }
    if adr_path is not None:
        session["adr_path"] = adr_path
    (root / ".adr-session.json").write_text(json.dumps(session, indent=2), encoding="utf-8")


def _write_adr(root: Path, body: str, name: str = "test-adr.md") -> None:
    adr_dir = root / "adr"
    adr_dir.mkdir(exist_ok=True)
    (adr_dir / name).write_text(body, encoding="utf-8")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A project root with a gated target file path available."""
    (tmp_path / "skills" / "some-skill").mkdir(parents=True)
    return tmp_path


def _deny(project: Path) -> tuple[int, str]:
    return _run_main(_event(str(project / GATED_TARGET), str(project)))


# ---------------------------------------------------------------------------
# The gate itself must not have moved
# ---------------------------------------------------------------------------


class TestGateStrictness:
    """Staleness changes the message, never the decision."""

    def test_no_session_allows_through(self, project: Path):
        """Gate is dormant with no registered session."""
        assert _deny(project)[0] == 0

    def test_fresh_session_without_synthesis_blocks(self, project: Path):
        """The baseline block: a live session with no synthesis.md."""
        _write_session(project, age=timedelta(hours=1))
        _write_adr(project, INCOMPLETE_ADR)
        assert _deny(project)[0] == 2

    def test_stale_session_still_blocks(self, project: Path):
        """A stale session must block exactly as hard as a fresh one."""
        _write_session(project, age=timedelta(days=3))
        _write_adr(project, COMPLETE_ADR)
        assert _deny(project)[0] == 2, "stale sessions must not auto-expire the gate"

    def test_stale_session_with_proceed_verdict_still_allows(self, project: Path):
        """PROCEED remains the only way through, stale or not."""
        _write_session(project, age=timedelta(days=3))
        _write_adr(project, COMPLETE_ADR)
        synthesis_dir = project / "adr" / "test-adr"
        synthesis_dir.mkdir(parents=True)
        (synthesis_dir / "synthesis.md").write_text("Verdict: PROCEED\n", encoding="utf-8")
        assert _deny(project)[0] == 0

    def test_stale_session_blocked_verdict_still_blocks(self, project: Path):
        _write_session(project, age=timedelta(days=3))
        _write_adr(project, COMPLETE_ADR)
        synthesis_dir = project / "adr" / "test-adr"
        synthesis_dir.mkdir(parents=True)
        (synthesis_dir / "synthesis.md").write_text("Verdict: BLOCKED\n", encoding="utf-8")
        code, reason = _deny(project)
        assert code == 2
        assert "BLOCKED" in reason

    def test_non_gated_path_allows_through(self, project: Path):
        """scripts/ is infrastructure, not gated — even with a stale session."""
        _write_session(project, age=timedelta(days=3))
        _write_adr(project, COMPLETE_ADR)
        code, _ = _run_main(_event(str(project / "scripts" / "thing.py"), str(project)))
        assert code == 0

    def test_bypass_env_allows_through(self, project: Path):
        _write_session(project, age=timedelta(hours=1))
        _write_adr(project, INCOMPLETE_ADR)
        code, _ = _run_main(_event(str(project / GATED_TARGET), str(project)), env={mod._BYPASS_ENV: "1"})
        assert code == 0


# ---------------------------------------------------------------------------
# Fail-open
# ---------------------------------------------------------------------------


class TestFailOpen:
    """Unexpected input must never block work."""

    def test_malformed_session_json_fails_open(self, project: Path):
        """A corrupt registry is unreadable, so the gate cannot claim a session."""
        (project / ".adr-session.json").write_text("{not json at all", encoding="utf-8")
        _write_adr(project, COMPLETE_ADR)
        assert _deny(project)[0] == 0

    def test_session_json_wrong_type_fails_open(self, project: Path):
        """A JSON list where an object belongs must not raise."""
        (project / ".adr-session.json").write_text("[1, 2, 3]", encoding="utf-8")
        assert _deny(project)[0] == 0

    def test_malformed_event_json_fails_open(self):
        assert _run_main("not valid json {{{")[0] == 0

    def test_missing_file_path_fails_open(self):
        assert _run_main(json.dumps({"tool_name": "Write", "tool_input": {}}))[0] == 0


# ---------------------------------------------------------------------------
# Stale-session denial message
# ---------------------------------------------------------------------------


class TestStaleDenialMessage:
    """The denial must carry the whole diagnosis: age, date, ADR, checklist, fix."""

    def test_fresh_denial_message_unchanged(self, project: Path):
        """A live session gets the original message with no stale noise."""
        _write_session(project, age=timedelta(hours=2))
        _write_adr(project, INCOMPLETE_ADR)
        code, reason = _deny(project)

        assert code == 2
        assert "STALE" not in reason
        assert "adr-query.py close" not in reason
        assert "ADR consultation required before implementing test-adr" in reason

    def test_stale_denial_announces_staleness(self, project: Path):
        _write_session(project, age=timedelta(days=3, hours=4))
        _write_adr(project, COMPLETE_ADR)
        code, reason = _deny(project)

        assert code == 2
        assert "STALE ADR SESSION" in reason

    def test_stale_denial_reports_age_and_registration_date(self, project: Path):
        registered_at = datetime.now(timezone.utc) - timedelta(days=3, hours=4)
        _write_session(project, age=timedelta(days=3, hours=4))
        _write_adr(project, COMPLETE_ADR)
        _, reason = _deny(project)

        assert "3d 4h" in reason
        assert registered_at.strftime("%Y-%m-%d") in reason

    def test_stale_denial_names_the_adr(self, project: Path):
        _write_session(project, age=timedelta(days=3))
        _write_adr(project, COMPLETE_ADR)
        _, reason = _deny(project)
        assert "test-adr" in reason

    def test_stale_denial_reports_complete_checklist(self, project: Path):
        """The incident's decisive fact: the ADR's checklist was already done."""
        _write_session(project, age=timedelta(days=3))
        _write_adr(project, COMPLETE_ADR)
        _, reason = _deny(project)
        assert "COMPLETE (2 of 2 items checked)" in reason

    def test_stale_denial_reports_incomplete_checklist(self, project: Path):
        """A stale session over live work must say so, not imply it is safe to close."""
        _write_session(project, age=timedelta(days=3))
        _write_adr(project, INCOMPLETE_ADR)
        _, reason = _deny(project)
        assert "incomplete (1 of 2 items unchecked)" in reason

    def test_stale_denial_gives_the_close_command(self, project: Path):
        _write_session(project, age=timedelta(days=3))
        _write_adr(project, COMPLETE_ADR)
        _, reason = _deny(project)
        assert "python3 scripts/adr-query.py close" in reason

    def test_stale_denial_offers_the_consultation_alternative(self, project: Path):
        """Never push the user to close a session that is genuinely live."""
        _write_session(project, age=timedelta(days=3))
        _write_adr(project, COMPLETE_ADR)
        _, reason = _deny(project)
        assert "/adr-consultation" in reason

    def test_missing_adr_file_reports_unknown_checklist(self, project: Path):
        """No ADR on disk must degrade to 'unknown', not crash or guess."""
        _write_session(project, age=timedelta(days=3))
        _, reason = _deny(project)
        assert "unknown (ADR file is missing)" in reason

    def test_traversal_adr_path_reports_unknown_checklist(self, project: Path):
        """A registry path escaping adr/ must not be read."""
        _write_session(project, age=timedelta(days=3), adr_path="adr/../../etc/passwd.md")
        _, reason = _deny(project)
        assert "unknown (session ADR path is not a repo-relative adr/*.md file)" in reason

    def test_unparseable_registered_at_yields_no_stale_note(self, project: Path):
        """Bad data must not be reported as staleness."""
        session = {
            "adr_path": "adr/test-adr.md",
            "adr_hash": "sha256:" + "0" * 64,
            "domain": "test-adr",
            "registered_at": "whenever",
        }
        (project / ".adr-session.json").write_text(json.dumps(session), encoding="utf-8")
        _write_adr(project, COMPLETE_ADR)
        code, reason = _deny(project)

        assert code == 2, "unknown age must still block"
        assert "STALE" not in reason


# ---------------------------------------------------------------------------
# Boundary and unit-level checks
# ---------------------------------------------------------------------------


class TestStalenessBoundary:
    def test_just_under_ttl_is_fresh(self, project: Path):
        _write_session(project, age=timedelta(hours=mod.SESSION_STALE_AFTER_HOURS - 1))
        _write_adr(project, COMPLETE_ADR)
        _, reason = _deny(project)
        assert "STALE" not in reason

    def test_just_over_ttl_is_stale(self, project: Path):
        _write_session(project, age=timedelta(hours=mod.SESSION_STALE_AFTER_HOURS, minutes=1))
        _write_adr(project, COMPLETE_ADR)
        _, reason = _deny(project)
        assert "STALE" in reason

    def test_format_age(self):
        assert mod._format_age(timedelta(days=3, hours=4)) == "3d 4h"
        assert mod._format_age(timedelta(hours=5, minutes=6)) == "5h 6m"
        assert mod._format_age(timedelta(minutes=20)) == "20m"
        assert mod._format_age(timedelta(seconds=-10)) == "0m"

    def test_checklist_state_without_checklist(self, project: Path):
        _write_adr(project, "# ADR\n\nNo boxes here.\n")
        state = mod._checklist_state(project, {"adr_path": "adr/test-adr.md"})
        assert state == "the ADR has no checklist"

    def test_checklist_state_missing_path(self, project: Path):
        assert mod._checklist_state(project, {}) == "unknown (session records no ADR path)"
