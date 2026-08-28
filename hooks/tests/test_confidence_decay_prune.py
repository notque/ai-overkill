#!/usr/bin/env python3
"""Tests for the destructive half of the confidence-decay Stop hook.

The hook calls prune(min_confidence=0.3, older_than_days=90) and
prune_ancillary() on every session end. Neither call had a test: every fixture
in test_confidence_decay_neutral.py is 45 days stale, so prune always matched
zero rows and the hook could be retuned to delete live data without a single
failure. prune_ancillary() deletes the activations rows that
validate-learning-effectiveness.py reads for coverage_rate.

These tests seed rows on both sides of every boundary and assert exactly what
survives.

Run with: python3 -m pytest hooks/tests/test_confidence_decay_prune.py -v
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
LIB_DIR = HOOKS_DIR / "lib"
HOOK_PATH = HOOKS_DIR / "confidence-decay.py"

if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import learning_db_v2 as ldb


def _days_ago(days: int) -> str:
    return (datetime.now() - timedelta(days=days)).isoformat()


@pytest.fixture()
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway learning.db, initialized and empty."""
    db_dir = tmp_path / "learning-prune"
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    monkeypatch.setattr(ldb, "_initialized", False, raising=False)
    ldb.init_db()
    return db_dir / "learning.db"


def _seed_learning(key: str, confidence: float, age_days: int, graduated_to: str | None = None) -> None:
    """Insert one learning row with an explicit age and confidence."""
    stamp = _days_ago(age_days)
    with ldb.get_connection() as conn:
        conn.execute(
            "INSERT INTO learnings (topic, key, value, category, confidence, source, "
            "first_seen, last_seen, graduated_to) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("t", key, "v", "error", confidence, "seed", stamp, stamp, graduated_to),
        )
        conn.commit()


def _seed_activation(key: str, age_days: int) -> None:
    with ldb.get_connection() as conn:
        conn.execute(
            "INSERT INTO activations (topic, key, timestamp) VALUES (?, ?, ?)",
            ("t", key, _days_ago(age_days)),
        )
        conn.commit()


def _seed_governance_event(event_id: str, age_days: int) -> None:
    with ldb.get_connection() as conn:
        conn.execute(
            "INSERT INTO governance_events (id, event_type, created_at) VALUES (?, ?, ?)",
            (event_id, "gate", _days_ago(age_days)),
        )
        conn.commit()


def _seed_session(session_id: str, age_days: int) -> None:
    with ldb.get_connection() as conn:
        conn.execute(
            "INSERT INTO sessions (session_id, start_time) VALUES (?, ?)",
            (session_id, _days_ago(age_days)),
        )
        conn.commit()


def _learning_keys() -> set[str]:
    with ldb.get_connection() as conn:
        return {r["key"] for r in conn.execute("SELECT key FROM learnings")}


def _activation_keys() -> list[str]:
    with ldb.get_connection() as conn:
        return [r["key"] for r in conn.execute("SELECT key FROM activations ORDER BY id")]


def _governance_ids() -> list[str]:
    with ldb.get_connection() as conn:
        return [r["id"] for r in conn.execute("SELECT id FROM governance_events ORDER BY created_at")]


def _session_ids() -> list[str]:
    with ldb.get_connection() as conn:
        return [r["session_id"] for r in conn.execute("SELECT session_id FROM sessions ORDER BY id")]


# ---------------------------------------------------------------------------
# prune(): both predicates, both directions
# ---------------------------------------------------------------------------


class TestPrune:
    """prune deletes only rows below the confidence floor AND past the age cutoff."""

    def test_deletes_only_the_old_low_confidence_row(self, db: Path) -> None:
        _seed_learning("old-weak", confidence=0.2, age_days=120)
        _seed_learning("old-strong", confidence=0.5, age_days=120)
        _seed_learning("recent-weak", confidence=0.2, age_days=45)
        assert ldb.prune(min_confidence=0.3, older_than_days=90) == 1
        assert _learning_keys() == {"old-strong", "recent-weak"}

    def test_recent_weak_rows_survive_the_ninety_day_cutoff(self, db: Path) -> None:
        """Shortening older_than_days mass-deletes live learnings; this catches it."""
        _seed_learning("weak-45d", confidence=0.1, age_days=45)
        assert ldb.prune(min_confidence=0.3, older_than_days=90) == 0
        assert _learning_keys() == {"weak-45d"}

    def test_confidence_floor_is_exclusive(self, db: Path) -> None:
        """A row sitting exactly on 0.3 is kept, not deleted."""
        _seed_learning("at-floor", confidence=0.3, age_days=120)
        assert ldb.prune(min_confidence=0.3, older_than_days=90) == 0
        assert _learning_keys() == {"at-floor"}

    def test_graduated_rows_are_never_pruned(self, db: Path) -> None:
        """Graduation is the promotion record; deleting it loses the provenance."""
        _seed_learning("graduated", confidence=0.1, age_days=200, graduated_to="skills/foo")
        assert ldb.prune(min_confidence=0.3, older_than_days=90) == 0
        assert _learning_keys() == {"graduated"}

    def test_empty_db_deletes_nothing(self, db: Path) -> None:
        assert ldb.prune(min_confidence=0.3, older_than_days=90) == 0


# ---------------------------------------------------------------------------
# prune_ancillary(): per-table retention
# ---------------------------------------------------------------------------


class TestPruneAncillary:
    """Each ancillary table has its own retention window."""

    def test_activations_older_than_ninety_days_are_deleted(self, db: Path) -> None:
        """coverage_rate in validate-learning-effectiveness.py reads what survives here."""
        _seed_activation("old", age_days=120)
        _seed_activation("recent", age_days=30)
        assert ldb.prune_ancillary()["activations"] == 1
        assert _activation_keys() == ["recent"]

    def test_governance_events_keep_one_hundred_eighty_days(self, db: Path) -> None:
        _seed_governance_event("old", age_days=200)
        _seed_governance_event("recent", age_days=100)
        assert ldb.prune_ancillary()["governance_events"] == 1
        assert _governance_ids() == ["recent"]

    def test_sessions_keep_one_year(self, db: Path) -> None:
        _seed_session("old", age_days=400)
        _seed_session("recent", age_days=300)
        assert ldb.prune_ancillary()["sessions"] == 1
        assert _session_ids() == ["recent"]

    def test_fresh_rows_are_all_kept(self, db: Path) -> None:
        _seed_activation("k", age_days=1)
        _seed_governance_event("g", age_days=1)
        _seed_session("s", age_days=1)
        assert ldb.prune_ancillary() == {
            "governance_events": 0,
            "sessions": 0,
            "session_stats": 0,
            "activations": 0,
        }


# ---------------------------------------------------------------------------
# The hook wires both calls with the parameters it documents
# ---------------------------------------------------------------------------


def _run_hook(db_path: Path) -> subprocess.CompletedProcess:
    """Run the Stop hook against the throwaway DB."""
    env = dict(os.environ)
    env["CLAUDE_LEARNING_DIR"] = str(db_path.parent)
    return subprocess.run([sys.executable, str(HOOK_PATH)], input="", capture_output=True, text=True, env=env)


class TestHookPruneWiring:
    """confidence-decay.py must prune with (0.3, 90) and the default retentions."""

    def test_hook_prunes_old_weak_learnings_and_keeps_the_rest(self, db: Path) -> None:
        _seed_learning("old-weak", confidence=0.2, age_days=120)
        _seed_learning("recent-weak", confidence=0.2, age_days=45)
        _seed_learning("old-strong", confidence=0.9, age_days=120)
        assert _run_hook(db).returncode == 0
        assert _learning_keys() == {"recent-weak", "old-strong"}

    def test_hook_prunes_old_activations_and_keeps_recent_ones(self, db: Path) -> None:
        _seed_activation("old", age_days=120)
        _seed_activation("recent", age_days=30)
        assert _run_hook(db).returncode == 0
        assert _activation_keys() == ["recent"]
