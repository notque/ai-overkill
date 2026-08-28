#!/usr/bin/env python3
"""Tests for hook_utils.record_activations_safe.

This function is the only writer on the activation path: every injection hook
calls it, and validate-learning-effectiveness.py reads the rows it writes for
coverage_rate and the retro cohort join. It swallows every exception, so a
failure here is invisible at runtime — these tests are the only place the
failure can surface.

Run with: python3 -m pytest hooks/tests/test_record_activations_safe.py -v
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

_LIB_DIR = Path(__file__).resolve().parent.parent / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from hook_utils import record_activations_safe

SESSION = "session-abc-123"


def _db():
    """Resolve learning_db_v2 through sys.modules on every call.

    Other test modules delete and re-import it during collection, so a
    module-level alias can end up pointing at a dead copy while the code under
    test uses the live one. Patching the dead copy silently does nothing.
    """
    import learning_db_v2

    return learning_db_v2


@pytest.fixture(autouse=True)
def fresh_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point the learning DB at a throwaway directory for one test."""
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path))
    _db()._initialized = False
    _db().init_db()
    yield
    _db()._initialized = False


def _rows() -> list[tuple[str, str, str | None]]:
    """Return every activation row as (topic, key, session_id), oldest first."""
    with _db().get_connection() as conn:
        return [
            (r["topic"], r["key"], r["session_id"])
            for r in conn.execute("SELECT topic, key, session_id FROM activations ORDER BY id")
        ]


def test_injected_learnings_are_recorded_with_their_session():
    """The happy path writes one row per learning, tagged with the session id."""
    record_activations_safe([{"topic": "go", "key": "k1"}, {"topic": "python", "key": "k2"}], SESSION)
    assert _rows() == [("go", "k1", SESSION), ("python", "k2", SESSION)]


def test_extra_result_fields_are_ignored():
    """search_learnings rows carry value/category/confidence; only topic+key are used."""
    result = {"topic": "go", "key": "k1", "value": "err -> fix", "category": "error", "confidence": 0.9}
    record_activations_safe([result], SESSION)
    assert _rows() == [("go", "k1", SESSION)]


def test_one_malformed_row_does_not_drop_the_whole_batch():
    """A row missing "key" is skipped; the good rows still land.

    Regression: the bare r["key"] subscript raised KeyError on the bad row and
    the blanket except discarded every activation in the batch.
    """
    results = [{"topic": "go", "key": "k1"}, {"topic": "python"}, {"topic": "rust", "key": "k3"}]
    record_activations_safe(results, SESSION)
    assert _rows() == [("go", "k1", SESSION), ("rust", "k3", SESSION)]


def test_row_missing_topic_is_skipped():
    """The topic subscript has the same failure mode as key."""
    record_activations_safe([{"key": "k1"}, {"topic": "go", "key": "k2"}], SESSION)
    assert _rows() == [("go", "k2", SESSION)]


def test_empty_results_write_nothing():
    """No learnings injected means no activation rows."""
    record_activations_safe([], SESSION)
    assert _rows() == []


def test_all_rows_malformed_writes_nothing():
    """Nothing usable in, nothing recorded — and still no exception."""
    record_activations_safe([{"topic": "go"}, {"key": "k"}, {}], SESSION)
    assert _rows() == []


def test_missing_session_id_writes_a_null_session():
    """session_id=None still records the activation, with a NULL session column.

    Documented consequence: the row counts toward coverage_rate but drops out of
    the retro cohort join in validate-learning-effectiveness.py, which matches on
    session_id. Change this deliberately, not by accident.
    """
    record_activations_safe([{"topic": "go", "key": "k1"}])
    assert _rows() == [("go", "k1", None)]


def test_debug_reports_skipped_rows(capsys: pytest.CaptureFixture[str]):
    """With debug on, a skipped row is named on stderr instead of vanishing."""
    record_activations_safe([{"topic": "go", "key": "k1"}, {"topic": "python"}], SESSION, debug=True)
    assert "Skipped 1 row" in capsys.readouterr().err


def test_recording_failure_is_swallowed(monkeypatch: pytest.MonkeyPatch):
    """A DB error never propagates into the calling hook."""
    monkeypatch.setattr(_db(), "record_activations", _raise)
    record_activations_safe([{"topic": "go", "key": "k1"}], SESSION)
    assert _rows() == []


def _raise(*_args, **_kwargs):
    """Stand in for the DB layer failing on a locked or missing table."""
    raise sqlite3.OperationalError("no such table: activations")
