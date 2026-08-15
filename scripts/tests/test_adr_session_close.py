#!/usr/bin/env python3
"""Tests for `adr-query.py close` and session staleness reporting.

The incident these cover: an ADR completed on 2026-08-10 left `.adr-session.json`
registered from 2026-08-11 with zero unchecked checklist boxes. adr-query.py had
no way to end a session, so the synthesis gate silently blocked every write under
skills/ and agents/ for three days.

Every test drives the CLI against a tmp repo root. The real repository
`.adr-session.json` is never read or written.

Run with: python3 -m pytest scripts/tests/test_adr_session_close.py -v
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ADR_QUERY = REPO_ROOT / "scripts" / "adr-query.py"

COMPLETE_ADR = """# Test ADR

## Status

IMPLEMENTED

## Checklist

- [x] First step
- [x] Second step
"""

INCOMPLETE_ADR = """# Test ADR

## Status

ACCEPTED

## Checklist

- [x] First step
- [ ] Second step
- [ ] Third step
"""


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _run(repo_root: Path, *args: str) -> subprocess.CompletedProcess:
    """Invoke adr-query.py against an isolated repo root."""
    return subprocess.run(
        [sys.executable, str(ADR_QUERY), *args, "--repo-root", str(repo_root)],
        capture_output=True,
        text=True,
    )


def _make_repo(tmp_path: Path, adr_body: str) -> Path:
    """Build a tmp repo containing adr/test-adr.md. Returns the repo root."""
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir()
    (adr_dir / "test-adr.md").write_text(adr_body, encoding="utf-8")
    return tmp_path


def _register(repo_root: Path, *, registered_at: datetime | None = None) -> dict:
    """Register the tmp ADR, optionally back-dating registered_at."""
    result = _run(repo_root, "register", "--adr", "adr/test-adr.md")
    assert result.returncode == 0, result.stderr

    session_file = repo_root / ".adr-session.json"
    session = json.loads(session_file.read_text(encoding="utf-8"))
    if registered_at is not None:
        session["registered_at"] = registered_at.isoformat()
        session_file.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
    return session


@pytest.fixture
def complete_repo(tmp_path: Path) -> Path:
    """Repo whose ADR checklist is fully checked."""
    return _make_repo(tmp_path, COMPLETE_ADR)


@pytest.fixture
def incomplete_repo(tmp_path: Path) -> Path:
    """Repo whose ADR checklist still has unchecked boxes."""
    return _make_repo(tmp_path, INCOMPLETE_ADR)


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------


class TestClose:
    """`close` ends a session, but only when the session is genuinely finished."""

    def test_close_with_no_session_exits_nonzero(self, complete_repo: Path):
        """No registered session is an error, not a silent success."""
        result = _run(complete_repo, "close")
        assert result.returncode == 1
        assert "no active ADR session" in result.stderr
        assert ".adr-session.json" in result.stderr

    def test_close_on_complete_adr_succeeds(self, complete_repo: Path):
        """The incident case: a finished ADR's session closes cleanly."""
        _register(complete_repo)
        result = _run(complete_repo, "close")

        assert result.returncode == 0, result.stderr
        assert "Closed ADR session: adr/test-adr.md" in result.stdout
        assert "complete (2/2 checked)" in result.stdout
        assert not (complete_repo / ".adr-session.json").exists()

    def test_close_reports_registration_metadata(self, complete_repo: Path):
        """The success output names what it closed, for the audit trail."""
        session = _register(complete_repo)
        result = _run(complete_repo, "close")

        assert result.returncode == 0, result.stderr
        assert session["domain"] in result.stdout
        assert session["registered_at"] in result.stdout

    def test_close_refused_when_checklist_incomplete(self, incomplete_repo: Path):
        """Unchecked boxes mean the session is live — refuse and keep the file."""
        _register(incomplete_repo)
        result = _run(incomplete_repo, "close")

        assert result.returncode == 1
        assert "refusing to close" in result.stderr
        assert "2 unchecked checklist item(s)" in result.stderr
        assert (incomplete_repo / ".adr-session.json").exists(), "refusal must not delete the session"

    def test_refusal_message_names_the_force_override(self, incomplete_repo: Path):
        """The refusal must tell the owner how to override it."""
        _register(incomplete_repo)
        result = _run(incomplete_repo, "close")
        assert "--force" in result.stderr

    def test_force_closes_incomplete_adr(self, incomplete_repo: Path):
        """--force is the owner's explicit override of the checklist refusal."""
        _register(incomplete_repo)
        result = _run(incomplete_repo, "close", "--force")

        assert result.returncode == 0, result.stderr
        assert "2 of 3 unchecked" in result.stdout
        assert not (incomplete_repo / ".adr-session.json").exists()

    def test_close_matching_adr_argument_succeeds(self, complete_repo: Path):
        """--adr asserting the registered path is accepted."""
        _register(complete_repo)
        result = _run(complete_repo, "close", "--adr", "adr/test-adr.md")

        assert result.returncode == 0, result.stderr
        assert not (complete_repo / ".adr-session.json").exists()

    def test_close_mismatched_adr_argument_refused(self, complete_repo: Path):
        """--adr naming a different ADR must not close the active session."""
        (complete_repo / "adr" / "other-adr.md").write_text(COMPLETE_ADR, encoding="utf-8")
        _register(complete_repo)
        result = _run(complete_repo, "close", "--adr", "adr/other-adr.md")

        assert result.returncode == 1
        assert "does not match the active session" in result.stderr
        assert (complete_repo / ".adr-session.json").exists()

    def test_close_warns_on_hash_drift(self, complete_repo: Path):
        """An ADR edited since registration still closes, with a warning."""
        _register(complete_repo)
        (complete_repo / "adr" / "test-adr.md").write_text(COMPLETE_ADR + "\nAppended.\n", encoding="utf-8")
        result = _run(complete_repo, "close")

        assert result.returncode == 0, result.stderr
        assert "changed since registration" in result.stderr

    def test_close_refused_when_registered_adr_missing(self, complete_repo: Path):
        """A session pointing at a deleted ADR cannot be verified — refuse without --force."""
        _register(complete_repo)
        (complete_repo / "adr" / "test-adr.md").unlink()
        result = _run(complete_repo, "close")

        assert result.returncode == 1
        assert "cannot verify the registered ADR" in result.stderr
        assert "--force" in result.stderr

    def test_force_closes_when_registered_adr_missing(self, complete_repo: Path):
        """--force must still rescue a session whose ADR was deleted or renamed."""
        _register(complete_repo)
        (complete_repo / "adr" / "test-adr.md").unlink()
        result = _run(complete_repo, "close", "--force")

        assert result.returncode == 0, result.stderr
        assert not (complete_repo / ".adr-session.json").exists()

    def test_close_rejects_malformed_session(self, complete_repo: Path):
        """A registry missing adr_path/adr_hash is an error, not a crash."""
        (complete_repo / ".adr-session.json").write_text(json.dumps({"domain": "x"}), encoding="utf-8")
        result = _run(complete_repo, "close")

        assert result.returncode == 1
        assert "adr_path" in result.stderr

    def test_close_is_advertised_in_help(self):
        """The command must be discoverable from --help."""
        result = subprocess.run(
            [sys.executable, str(ADR_QUERY), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "close" in result.stdout


# ---------------------------------------------------------------------------
# active / staleness
# ---------------------------------------------------------------------------


class TestActiveStaleness:
    """`active` must surface a stranded session instead of reporting it normally."""

    def test_fresh_session_not_stale(self, complete_repo: Path):
        _register(complete_repo)
        result = _run(complete_repo, "active")

        assert result.returncode == 0, result.stderr
        assert "stale:         no" in result.stdout

    def test_old_session_reported_stale_with_close_command(self, complete_repo: Path):
        """The exact incident shape: a three-day-old session must announce itself."""
        registered_at = datetime.now(timezone.utc) - timedelta(days=3, hours=4)
        _register(complete_repo, registered_at=registered_at)
        result = _run(complete_repo, "active")

        assert result.returncode == 0, result.stderr
        assert "stale:         YES" in result.stdout
        assert "3d 4h" in result.stdout
        assert "adr-query.py close" in result.stdout

    def test_boundary_below_ttl_is_fresh(self, complete_repo: Path):
        """One hour short of the TTL is still a live session."""
        registered_at = datetime.now(timezone.utc) - timedelta(hours=23)
        _register(complete_repo, registered_at=registered_at)
        result = _run(complete_repo, "active")
        assert "stale:         no" in result.stdout

    def test_boundary_at_ttl_is_stale(self, complete_repo: Path):
        registered_at = datetime.now(timezone.utc) - timedelta(hours=24, minutes=1)
        _register(complete_repo, registered_at=registered_at)
        result = _run(complete_repo, "active")
        assert "stale:         YES" in result.stdout

    def test_unparseable_timestamp_is_not_stale(self, complete_repo: Path):
        """Missing data must never be read as evidence of staleness."""
        _register(complete_repo)
        session_file = complete_repo / ".adr-session.json"
        session = json.loads(session_file.read_text(encoding="utf-8"))
        session["registered_at"] = "not-a-timestamp"
        session_file.write_text(json.dumps(session), encoding="utf-8")

        result = _run(complete_repo, "active")
        assert result.returncode == 0, result.stderr
        assert "stale:         no" in result.stdout
        assert "age:           <unknown>" in result.stdout
