#!/usr/bin/env python3
"""Tests for the `dedupe` subcommand in scripts/learning-db.py.

Covers: cluster detection, dry-run leaving the table untouched, survivor
selection under --apply, first_seen/observation_count merging, activations
re-pointing, FTS index consistency, and graduated-row protection.

Run with: python3 -m pytest scripts/tests/test_learning_db_dedupe.py -v
"""

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_repo_root / "hooks" / "lib"))

SCRIPT_PATH = str(_repo_root / "scripts" / "learning-db.py")

# Same text, re-recorded with the noise the capture hooks add: case change,
# extra whitespace, a doubled arrow, a trailing period.
BASE_VALUE = "Run validate-doc-counts.py after merging main, because both branches bump the same README count"
NOISY_VALUE = "run  validate-doc-counts.py   after merging main, because both branches bump the same README count."
ARROW_VALUE = "Run validate-doc-counts.py after merging main → → because both branches bump the same README count"
OTHER_VALUE = "Fork PRs skip CI entirely while mergeable_state is dirty; resolve the conflict to unblock checks"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point learning.db at a temp directory for each test."""
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path))
    import importlib

    import learning_db_v2

    importlib.reload(learning_db_v2)
    learning_db_v2.init_db()
    yield tmp_path


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    return subprocess.run(
        [sys.executable, SCRIPT_PATH, *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def _connect(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "learning.db")
    conn.row_factory = sqlite3.Row
    return conn


def _insert(
    tmp_path: Path,
    topic: str,
    key: str,
    value: str,
    *,
    category: str = "gotcha",
    confidence: float = 0.5,
    observation_count: int = 1,
    age_days: int = 0,
    graduated_to: str | None = None,
) -> None:
    ts = (datetime.now() - timedelta(days=age_days)).isoformat()
    conn = _connect(tmp_path)
    conn.execute(
        "INSERT INTO learnings (topic, key, value, category, confidence, source, "
        "observation_count, first_seen, last_seen, graduated_to) "
        "VALUES (?, ?, ?, ?, ?, 'test', ?, ?, ?, ?)",
        (topic, key, value, category, confidence, observation_count, ts, ts, graduated_to),
    )
    conn.commit()
    conn.close()


def _activate(tmp_path: Path, topic: str, key: str, outcome: str = "success") -> None:
    conn = _connect(tmp_path)
    conn.execute(
        "INSERT INTO activations (topic, key, session_id, timestamp, outcome) VALUES (?, ?, 's1', ?, ?)",
        (topic, key, datetime.now().isoformat(), outcome),
    )
    conn.commit()
    conn.close()


def _rows(tmp_path: Path) -> list[sqlite3.Row]:
    conn = _connect(tmp_path)
    rows = conn.execute("SELECT * FROM learnings ORDER BY id").fetchall()
    conn.close()
    return rows


def _dedupe_json(*args: str) -> dict:
    result = _run_cli("dedupe", "--json", *args)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _seed_cluster(tmp_path: Path) -> None:
    """Three noisy recordings of one insight, plus one unrelated row."""
    _insert(tmp_path, "skill:pr-workflow", "a", BASE_VALUE, confidence=0.5, age_days=30)
    _insert(tmp_path, "skill:pr-workflow", "b", NOISY_VALUE, confidence=0.7, observation_count=3, age_days=10)
    _insert(tmp_path, "skill:pr-workflow", "c", ARROW_VALUE, confidence=0.6, age_days=1)
    _insert(tmp_path, "skill:pr-workflow", "d", OTHER_VALUE, confidence=0.9)


def test_detects_cluster_of_noisy_rerecordings(tmp_path: Path):
    _seed_cluster(tmp_path)
    report = _dedupe_json()
    assert report["clusters"] == 1
    assert report["rows_removed"] == 2
    assert report["total_before"] == 4
    assert report["total_after"] == 2
    assert report["top_clusters"][0]["size"] == 3


def test_distinct_values_are_not_clustered(tmp_path: Path):
    _insert(tmp_path, "skill:do", "a", BASE_VALUE)
    _insert(tmp_path, "skill:do", "b", OTHER_VALUE)
    report = _dedupe_json()
    assert report["clusters"] == 0
    assert report["rows_removed"] == 0


def test_same_value_in_different_categories_is_not_clustered(tmp_path: Path):
    _insert(tmp_path, "skill:do", "a", BASE_VALUE, category="gotcha")
    _insert(tmp_path, "skill:do", "b", BASE_VALUE, category="error")
    report = _dedupe_json()
    assert report["clusters"] == 0


def test_dry_run_writes_nothing(tmp_path: Path):
    _seed_cluster(tmp_path)
    before = [dict(r) for r in _rows(tmp_path)]

    report = _dedupe_json()
    assert report["applied"] is False
    assert report["activations_repointed"] == 0

    assert [dict(r) for r in _rows(tmp_path)] == before


def test_explicit_dry_run_flag_writes_nothing(tmp_path: Path):
    _seed_cluster(tmp_path)
    before = [dict(r) for r in _rows(tmp_path)]
    result = _run_cli("dedupe", "--dry-run")
    assert result.returncode == 0
    assert "DRY RUN" in result.stdout
    assert [dict(r) for r in _rows(tmp_path)] == before


def test_apply_keeps_highest_confidence_survivor(tmp_path: Path):
    _seed_cluster(tmp_path)
    report = _dedupe_json("--apply")

    assert report["applied"] is True
    assert report["rows_removed"] == 2
    assert report["total_after"] == 2

    keys = {r["key"] for r in _rows(tmp_path)}
    assert keys == {"b", "d"}


def test_survivor_inherits_earliest_first_seen_and_highest_observation_count(tmp_path: Path):
    _seed_cluster(tmp_path)
    _run_cli("dedupe", "--apply")

    conn = _connect(tmp_path)
    survivor = conn.execute("SELECT * FROM learnings WHERE key = 'b'").fetchone()
    oldest = conn.execute("SELECT MIN(first_seen) FROM learnings").fetchone()[0]
    conn.close()

    assert survivor["observation_count"] == 3
    # The 30-day-old sibling's first_seen moved onto the survivor.
    assert survivor["first_seen"] == oldest
    assert (datetime.now() - datetime.fromisoformat(survivor["first_seen"])).days >= 29


def test_apply_repoints_activations_to_survivor(tmp_path: Path):
    _seed_cluster(tmp_path)
    _activate(tmp_path, "skill:pr-workflow", "a")
    _activate(tmp_path, "skill:pr-workflow", "c")
    _activate(tmp_path, "skill:pr-workflow", "b")

    report = _dedupe_json("--apply")
    assert report["activations_repointed"] == 2

    conn = _connect(tmp_path)
    counts = dict(conn.execute("SELECT key, COUNT(*) FROM activations GROUP BY key").fetchall())
    conn.close()

    assert counts == {"b": 3}


def test_apply_leaves_fts_index_consistent(tmp_path: Path):
    _seed_cluster(tmp_path)
    report = _dedupe_json("--apply")
    assert report["fts_integrity_ok"] is True

    conn = _connect(tmp_path)
    # The deleted rows' text is gone from the index; the survivor's is still findable.
    hits = conn.execute("SELECT rowid FROM learnings_fts WHERE learnings_fts MATCH 'validate'").fetchall()
    conn.execute("INSERT INTO learnings_fts(learnings_fts) VALUES ('integrity-check')")
    surviving_ids = {r["id"] for r in conn.execute("SELECT id FROM learnings").fetchall()}
    conn.close()

    assert len(hits) == 1
    assert {h["rowid"] for h in hits} <= surviving_ids


def test_graduated_rows_are_protected(tmp_path: Path):
    _insert(tmp_path, "skill:do", "a", BASE_VALUE, confidence=0.5)
    _insert(tmp_path, "skill:do", "b", NOISY_VALUE, confidence=0.9, graduated_to="docs/PHILOSOPHY.md")

    report = _dedupe_json("--apply")
    assert report["clusters"] == 0
    assert report["rows_removed"] == 0
    assert len(_rows(tmp_path)) == 2


def test_routing_effectiveness_rows_are_protected(tmp_path: Path):
    _insert(tmp_path, "routing", "a", BASE_VALUE, category="effectiveness")
    _insert(tmp_path, "routing", "b", NOISY_VALUE, category="effectiveness")

    report = _dedupe_json("--apply")
    assert report["clusters"] == 0
    assert len(_rows(tmp_path)) == 2


def test_category_filter_scopes_the_run(tmp_path: Path):
    _insert(tmp_path, "voice-sample", "a", BASE_VALUE, category="voice")
    _insert(tmp_path, "voice-sample", "b", NOISY_VALUE, category="voice")
    _insert(tmp_path, "skill:do", "c", BASE_VALUE, category="gotcha")
    _insert(tmp_path, "skill:do", "d", NOISY_VALUE, category="gotcha")

    assert _dedupe_json("--category", "voice")["rows_removed"] == 1
    assert _dedupe_json()["rows_removed"] == 2


def test_prefix_bounds_the_comparison(tmp_path: Path):
    shared = "x" * 200
    _insert(tmp_path, "skill:do", "a", shared + " tail one")
    _insert(tmp_path, "skill:do", "b", shared + " tail two")

    # A 120-char window sees only the shared preamble.
    assert _dedupe_json()["clusters"] == 1
    # A wider window reaches the divergent tails.
    assert _dedupe_json("--prefix", "400")["clusters"] == 0


def test_empty_normalized_values_are_skipped(tmp_path: Path):
    _insert(tmp_path, "skill:do", "a", "→→→")
    _insert(tmp_path, "skill:do", "b", "!!! ...")

    report = _dedupe_json("--apply")
    assert report["clusters"] == 0
    assert len(_rows(tmp_path)) == 2


def test_no_duplicates_reports_clean(tmp_path: Path):
    _insert(tmp_path, "skill:do", "a", BASE_VALUE)
    result = _run_cli("dedupe")
    assert result.returncode == 0
    assert "Near-duplicate clusters: 0" in result.stdout
