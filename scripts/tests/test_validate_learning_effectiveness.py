"""Tests for validate-learning-effectiveness.py.

Covers each metric section with seeded data, composite score calculation,
--json output format, and edge cases (empty DB, single entry, all at baseline).
"""

from __future__ import annotations

import importlib
import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Ensure repo hooks/lib takes priority over ~/.claude/hooks/lib
_repo_root = Path(__file__).resolve().parent.parent.parent
_repo_hooks_lib = str(_repo_root / "hooks" / "lib")

sys.path.insert(0, _repo_hooks_lib)
sys.path.insert(0, str(_repo_root / "scripts"))

# Force-reload learning_db_v2 from the repo (not from ~/.claude/hooks/lib)
if "learning_db_v2" in sys.modules:
    del sys.modules["learning_db_v2"]

import learning_db_v2

# Import the CLI module so we can re-patch its references
sys_path_entry = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, sys_path_entry)
_learning_db_cli = importlib.import_module("learning-db")
sys.path.pop(0)

# Patch the CLI module's references to point to the repo version
for _attr_name in dir(learning_db_v2):
    if hasattr(_learning_db_cli, _attr_name) and not _attr_name.startswith("__"):
        try:
            setattr(_learning_db_cli, _attr_name, getattr(learning_db_v2, _attr_name))
        except (AttributeError, TypeError):
            pass

# Import the script as a module (hyphenated name)
sys.path.insert(0, sys_path_entry)
vle = importlib.import_module("validate-learning-effectiveness")
sys.path.pop(0)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point learning DB to a temp directory."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    monkeypatch.setattr(learning_db_v2, "_initialized", False)
    return db_dir


def _get_conn(isolated_db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(isolated_db / "learning.db")
    conn.row_factory = sqlite3.Row
    return conn


def _seed_learnings(
    isolated_db: Path,
    entries: list[dict],
) -> None:
    """Seed learnings table with full control over fields.

    Each entry dict can have: topic, key, value, category, confidence,
    success_count, failure_count, observation_count, graduated_to,
    first_seen, last_seen, source.
    """
    learning_db_v2.init_db()
    conn = _get_conn(isolated_db)
    now = datetime.now().isoformat()
    for e in entries:
        conn.execute(
            """
            INSERT INTO learnings
                (topic, key, value, category, confidence, source,
                 success_count, failure_count, observation_count,
                 graduated_to, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                e.get("topic", "test"),
                e.get("key", "k1"),
                e.get("value", "test value"),
                e.get("category", "design"),
                e.get("confidence", 0.5),
                e.get("source", "test"),
                e.get("success_count", 0),
                e.get("failure_count", 0),
                e.get("observation_count", 1),
                e.get("graduated_to"),
                e.get("first_seen", now),
                e.get("last_seen", now),
            ),
        )
    conn.commit()
    conn.close()


def _seed_activations(isolated_db: Path, entries: list[tuple[str, str, int]]) -> None:
    """Seed activations. entries = [(topic, key, count), ...]."""
    learning_db_v2.init_db()
    conn = _get_conn(isolated_db)
    for topic, key, count in entries:
        for j in range(count):
            conn.execute(
                "INSERT INTO activations (topic, key, session_id, timestamp, outcome) VALUES (?, ?, ?, datetime('now'), 'success')",
                (topic, key, f"sess-{topic}-{key}-{j}"),
            )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Routing Health
# ---------------------------------------------------------------------------


class TestRoutingHealth:
    def test_empty_routing(self, isolated_db: Path) -> None:
        learning_db_v2.init_db()
        result = vle.measure_routing_health()
        assert result["total_routing"] == 0
        assert result["pct_with_outcomes"] == 0.0

    def test_all_at_baseline(self, isolated_db: Path) -> None:
        _seed_learnings(
            isolated_db,
            [
                {"topic": "routing", "key": f"r{i}", "confidence": 0.5, "success_count": 0, "failure_count": 0}
                for i in range(5)
            ],
        )
        result = vle.measure_routing_health()
        assert result["total_routing"] == 5
        assert result["pct_with_outcomes"] == 0.0
        assert result["pct_confidence_moved"] == 0.0

    def test_mixed_outcomes(self, isolated_db: Path) -> None:
        _seed_learnings(
            isolated_db,
            [
                {"topic": "routing", "key": "r1", "confidence": 0.7, "success_count": 3, "failure_count": 0},
                {"topic": "routing", "key": "r2", "confidence": 0.5, "success_count": 0, "failure_count": 0},
                {"topic": "routing", "key": "r3", "confidence": 0.3, "success_count": 0, "failure_count": 2},
                {"topic": "routing", "key": "r4", "confidence": 0.5, "success_count": 0, "failure_count": 0},
            ],
        )
        result = vle.measure_routing_health()
        assert result["total_routing"] == 4
        assert result["pct_with_outcomes"] == 50.0  # 2 of 4
        assert result["pct_confidence_moved"] == 50.0  # 2 of 4 (r1=0.7, r3=0.3)
        assert result["unique_combos"] == 4
        assert result["diversity_ratio"] == 1.0

    def test_non_routing_ignored(self, isolated_db: Path) -> None:
        _seed_learnings(
            isolated_db,
            [
                {"topic": "routing", "key": "r1", "confidence": 0.5},
                {"topic": "design", "key": "d1", "confidence": 0.9, "success_count": 5},
            ],
        )
        result = vle.measure_routing_health()
        assert result["total_routing"] == 1


# ---------------------------------------------------------------------------
# Confidence Distribution
# ---------------------------------------------------------------------------


class TestConfidenceDistribution:
    def test_empty_db(self, isolated_db: Path) -> None:
        learning_db_v2.init_db()
        result = vle.measure_confidence_distribution()
        assert all(v == 0 for v in result["histogram"].values())
        assert result["pct_at_baseline"] == 0.0

    def test_all_at_baseline(self, isolated_db: Path) -> None:
        _seed_learnings(
            isolated_db,
            [{"topic": "t", "key": f"k{i}", "confidence": 0.5} for i in range(10)],
        )
        result = vle.measure_confidence_distribution()
        assert result["pct_at_baseline"] == 100.0
        assert result["histogram"]["0.5-0.7"] == 10

    def test_histogram_buckets(self, isolated_db: Path) -> None:
        _seed_learnings(
            isolated_db,
            [
                {"topic": "t", "key": "k1", "confidence": 0.1},
                {"topic": "t", "key": "k2", "confidence": 0.4},
                {"topic": "t", "key": "k3", "confidence": 0.6},
                {"topic": "t", "key": "k4", "confidence": 0.8},
                {"topic": "t", "key": "k5", "confidence": 0.95},
                {"topic": "t", "key": "k6", "confidence": 1.0},
            ],
        )
        result = vle.measure_confidence_distribution()
        assert result["histogram"]["0.0-0.3"] == 1
        assert result["histogram"]["0.3-0.5"] == 1
        assert result["histogram"]["0.5-0.7"] == 1
        assert result["histogram"]["0.7-0.9"] == 1
        assert result["histogram"]["0.9-1.0"] == 2

    def test_category_movement(self, isolated_db: Path) -> None:
        _seed_learnings(
            isolated_db,
            [
                {"topic": "t", "key": "k1", "confidence": 0.5, "category": "error"},
                {"topic": "t", "key": "k2", "confidence": 0.8, "category": "error"},
                {"topic": "t", "key": "k3", "confidence": 0.5, "category": "design"},
            ],
        )
        result = vle.measure_confidence_distribution()
        assert result["category_movement"]["error"]["pct_moved"] == 50.0
        assert result["category_movement"]["design"]["pct_moved"] == 0.0


# ---------------------------------------------------------------------------
# Utilization
# ---------------------------------------------------------------------------


class TestUtilization:
    def test_empty_db(self, isolated_db: Path) -> None:
        learning_db_v2.init_db()
        result = vle.measure_utilization()
        assert result["total_learnings"] == 0
        assert result["coverage_rate"] == 0.0
        assert result["dead_weight_count"] == 0

    def test_full_coverage(self, isolated_db: Path) -> None:
        old = (datetime.now() - timedelta(days=10)).isoformat()
        _seed_learnings(
            isolated_db,
            [
                {"topic": "a", "key": "k1", "first_seen": old},
                {"topic": "b", "key": "k2", "first_seen": old},
            ],
        )
        _seed_activations(isolated_db, [("a", "k1", 3), ("b", "k2", 1)])
        result = vle.measure_utilization()
        assert result["total_with_activations"] == 2
        assert result["coverage_rate"] == 100.0
        assert result["dead_weight_count"] == 0

    def test_partial_coverage(self, isolated_db: Path) -> None:
        old = (datetime.now() - timedelta(days=10)).isoformat()
        _seed_learnings(
            isolated_db,
            [
                {"topic": "a", "key": "k1", "first_seen": old},
                {"topic": "b", "key": "k2", "first_seen": old},
                {"topic": "c", "key": "k3", "first_seen": old},
                {"topic": "d", "key": "k4", "first_seen": old},
            ],
        )
        _seed_activations(isolated_db, [("a", "k1", 5)])
        result = vle.measure_utilization()
        assert result["total_with_activations"] == 1
        assert result["coverage_rate"] == 25.0
        assert result["dead_weight_count"] == 3

    def test_dead_weight_ignores_recent(self, isolated_db: Path) -> None:
        """Entries < 7 days old should not count as dead weight."""
        recent = datetime.now().isoformat()
        old = (datetime.now() - timedelta(days=10)).isoformat()
        _seed_learnings(
            isolated_db,
            [
                {"topic": "new", "key": "k1", "first_seen": recent},
                {"topic": "old", "key": "k2", "first_seen": old},
            ],
        )
        result = vle.measure_utilization()
        assert result["dead_weight_count"] == 1  # only old entry

    def test_top_10_sorted(self, isolated_db: Path) -> None:
        _seed_learnings(isolated_db, [{"topic": "x", "key": "k1"}])
        _seed_activations(
            isolated_db,
            [("x", "k1", 2), ("y", "k2", 10), ("z", "k3", 5)],
        )
        result = vle.measure_utilization()
        counts = [item["count"] for item in result["top_10_activated"]]
        assert counts == sorted(counts, reverse=True)
        assert result["top_10_activated"][0]["count"] == 10


# ---------------------------------------------------------------------------
# Staleness
# ---------------------------------------------------------------------------


class TestStaleness:
    def test_empty_db(self, isolated_db: Path) -> None:
        learning_db_v2.init_db()
        result = vle.measure_staleness()
        assert result["stale_30d"] == 0
        assert result["stale_90d"] == 0

    def test_fresh_entries(self, isolated_db: Path) -> None:
        now = datetime.now().isoformat()
        _seed_learnings(
            isolated_db,
            [{"topic": "t", "key": f"k{i}", "last_seen": now} for i in range(5)],
        )
        result = vle.measure_staleness()
        assert result["stale_30d"] == 0
        assert result["pct_stale_30d"] == 0.0

    def test_stale_entries(self, isolated_db: Path) -> None:
        old_60 = (datetime.now() - timedelta(days=60)).isoformat()
        old_120 = (datetime.now() - timedelta(days=120)).isoformat()
        now = datetime.now().isoformat()
        _seed_learnings(
            isolated_db,
            [
                {"topic": "t", "key": "k1", "last_seen": now},
                {"topic": "t", "key": "k2", "last_seen": old_60},
                {"topic": "t", "key": "k3", "last_seen": old_120},
            ],
        )
        result = vle.measure_staleness()
        assert result["stale_30d"] == 2
        assert result["stale_90d"] == 1
        assert result["pct_stale_30d"] == pytest.approx(66.7, abs=0.1)

    def test_category_breakdown(self, isolated_db: Path) -> None:
        old = (datetime.now() - timedelta(days=60)).isoformat()
        _seed_learnings(
            isolated_db,
            [
                {"topic": "t", "key": "k1", "last_seen": old, "category": "error"},
                {"topic": "t", "key": "k2", "last_seen": old, "category": "error"},
                {"topic": "t", "key": "k3", "last_seen": old, "category": "design"},
            ],
        )
        result = vle.measure_staleness()
        assert result["stale_by_category"]["error"] == 2
        assert result["stale_by_category"]["design"] == 1


# ---------------------------------------------------------------------------
# Category Health
# ---------------------------------------------------------------------------


class TestCategoryHealth:
    def test_empty_db(self, isolated_db: Path) -> None:
        learning_db_v2.init_db()
        result = vle.measure_category_health()
        assert result["categories"] == {}
        assert result["zero_graduated"] == []

    def test_single_category(self, isolated_db: Path) -> None:
        _seed_learnings(
            isolated_db,
            [
                {"topic": "t", "key": "k1", "category": "error", "confidence": 0.8, "observation_count": 3},
                {"topic": "t", "key": "k2", "category": "error", "confidence": 0.6, "observation_count": 1},
            ],
        )
        result = vle.measure_category_health()
        assert "error" in result["categories"]
        assert result["categories"]["error"]["count"] == 2
        assert result["categories"]["error"]["avg_confidence"] == pytest.approx(0.7, abs=0.01)
        assert "error" in result["zero_graduated"]

    def test_graduated_entries(self, isolated_db: Path) -> None:
        _seed_learnings(
            isolated_db,
            [
                {
                    "topic": "t",
                    "key": "k1",
                    "category": "design",
                    "graduated_to": "agent:test",
                },
                {"topic": "t", "key": "k2", "category": "design"},
            ],
        )
        result = vle.measure_category_health()
        assert result["categories"]["design"]["graduated_count"] == 1
        assert "design" not in result["zero_graduated"]


# ---------------------------------------------------------------------------
# Effectiveness Score
# ---------------------------------------------------------------------------


class TestEffectivenessScore:
    def test_all_zeros(self, isolated_db: Path) -> None:
        """Empty DB should score 0."""
        learning_db_v2.init_db()
        routing = vle.measure_routing_health()
        confidence = vle.measure_confidence_distribution()
        utilization = vle.measure_utilization()
        staleness = vle.measure_staleness()
        category = vle.measure_category_health()
        score = vle.compute_effectiveness_score(routing, confidence, utilization, staleness, category)
        assert score["total"] == 0.0

    def test_perfect_score(self, isolated_db: Path) -> None:
        """Fully healthy DB should score 100."""
        now = datetime.now().isoformat()
        _seed_learnings(
            isolated_db,
            [
                {
                    "topic": "routing",
                    "key": f"r{i}",
                    "confidence": 0.9,
                    "success_count": 5,
                    "failure_count": 0,
                    "category": "effectiveness",
                    "graduated_to": "agent:test",
                    "last_seen": now,
                }
                for i in range(10)
            ],
        )
        _seed_activations(isolated_db, [("routing", f"r{i}", 3) for i in range(10)])

        routing = vle.measure_routing_health()
        confidence = vle.measure_confidence_distribution()
        utilization = vle.measure_utilization()
        staleness = vle.measure_staleness()
        category = vle.measure_category_health()
        score = vle.compute_effectiveness_score(routing, confidence, utilization, staleness, category)

        assert score["total"] == 100.0

    def test_weights_sum_to_100(self, isolated_db: Path) -> None:
        learning_db_v2.init_db()
        routing = vle.measure_routing_health()
        confidence = vle.measure_confidence_distribution()
        utilization = vle.measure_utilization()
        staleness = vle.measure_staleness()
        category = vle.measure_category_health()
        score = vle.compute_effectiveness_score(routing, confidence, utilization, staleness, category)
        assert sum(score["weights"].values()) == 100

    def test_partial_score(self, isolated_db: Path) -> None:
        """Some healthy, some broken should be in between."""
        now = datetime.now().isoformat()
        _seed_learnings(
            isolated_db,
            [
                # Routing: half with outcomes
                {"topic": "routing", "key": "r1", "confidence": 0.7, "success_count": 3},
                {"topic": "routing", "key": "r2", "confidence": 0.5, "success_count": 0},
                # Non-routing: mixed confidence, some graduated
                {"topic": "other", "key": "o1", "confidence": 0.9, "category": "error", "graduated_to": "x"},
                {"topic": "other", "key": "o2", "confidence": 0.5, "category": "design", "last_seen": now},
            ],
        )
        routing = vle.measure_routing_health()
        confidence = vle.measure_confidence_distribution()
        utilization = vle.measure_utilization()
        staleness = vle.measure_staleness()
        category = vle.measure_category_health()
        score = vle.compute_effectiveness_score(routing, confidence, utilization, staleness, category)

        assert 0 < score["total"] < 100


# ---------------------------------------------------------------------------
# run_all_sections
# ---------------------------------------------------------------------------


class TestRunAllSections:
    def test_returns_all_sections(self, isolated_db: Path) -> None:
        learning_db_v2.init_db()
        results = vle.run_all_sections()
        assert "routing" in results
        assert "confidence" in results
        assert "utilization" in results
        assert "staleness" in results
        assert "category" in results
        assert "score" in results

    def test_section_filter(self, isolated_db: Path) -> None:
        learning_db_v2.init_db()
        results = vle.run_all_sections(section_filter="routing")
        assert "routing" in results
        assert "confidence" not in results

    def test_score_section_alone(self, isolated_db: Path) -> None:
        """--section score should still compute the score."""
        learning_db_v2.init_db()
        results = vle.run_all_sections(section_filter="score")
        assert "score" in results
        assert "total" in results["score"]


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------


def _run_cli(
    argv: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, str]:
    """Invoke main() with the given flags; return (exit code, stdout)."""
    monkeypatch.setattr(sys, "argv", ["validate-learning-effectiveness.py", *argv])
    code = 0
    try:
        vle.main()
    except SystemExit as exc:
        code = exc.code or 0
    return code, capsys.readouterr().out


class TestJsonOutput:
    def test_json_flag_emits_parseable_sections(
        self, isolated_db: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--json prints the report itself.

        The previous version of this test printed json.dumps(...) from the test
        body and asserted capsys could read it back, so it never called main()
        and passed whatever --json actually emitted.
        """
        learning_db_v2.init_db()
        _, output = _run_cli(["--json"], monkeypatch, capsys)
        assert set(json.loads(output)) == {"routing", "confidence", "utilization", "staleness", "category", "score"}

    def test_json_never_leaks_the_internal_score_key(
        self, isolated_db: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A section filter computes "_score" for the exit code; callers never see it."""
        learning_db_v2.init_db()
        _, output = _run_cli(["--section", "routing", "--json"], monkeypatch, capsys)
        assert set(json.loads(output)) == {"routing"}


class TestExitCode:
    """The score threshold is the only thing that makes this CLI fail a build."""

    @pytest.mark.parametrize(("total", "expected"), [(0.0, 1), (49.9, 1), (50.0, 0), (50.1, 0), (100.0, 0)])
    def test_exit_one_below_fifty_and_zero_at_or_above(
        self,
        total: float,
        expected: int,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """50.0 is the boundary: passing. Flipping < to <= fails this row."""
        monkeypatch.setattr(vle, "run_all_sections", lambda **_kw: {"score": {"total": total}})
        code, _ = _run_cli(["--json"], monkeypatch, capsys)
        assert code == expected, f"score {total} should exit {expected}"

    def test_filtered_section_still_gates_on_the_hidden_score(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """With the score section suppressed, "_score" drives the exit code."""
        monkeypatch.setattr(vle, "run_all_sections", lambda **_kw: {"routing": {}, "_score": {"total": 10.0}})
        code, _ = _run_cli(["--section", "routing", "--json"], monkeypatch, capsys)
        assert code == 1

    def test_missing_score_does_not_fail_the_run(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """No score computed means no verdict, not a failed verdict."""
        monkeypatch.setattr(vle, "run_all_sections", lambda **_kw: {"routing": {}})
        code, _ = _run_cli(["--section", "routing", "--json"], monkeypatch, capsys)
        assert code == 0

    def test_json_contains_all_sections(self, isolated_db: Path) -> None:
        learning_db_v2.init_db()
        results = vle.run_all_sections()
        assert set(results.keys()) == {"routing", "confidence", "utilization", "staleness", "category", "score"}


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_single_entry(self, isolated_db: Path) -> None:
        _seed_learnings(isolated_db, [{"topic": "t", "key": "k1", "confidence": 0.5}])
        results = vle.run_all_sections()
        assert results["confidence"]["pct_at_baseline"] == 100.0
        assert results["utilization"]["total_learnings"] == 1
        assert results["score"]["total"] >= 0

    def test_empty_database(self, isolated_db: Path) -> None:
        learning_db_v2.init_db()
        results = vle.run_all_sections()
        assert results["routing"]["total_routing"] == 0
        assert results["utilization"]["total_learnings"] == 0
        assert results["score"]["total"] == 0.0

    def test_all_graduated(self, isolated_db: Path) -> None:
        now = datetime.now().isoformat()
        _seed_learnings(
            isolated_db,
            [
                {"topic": "t", "key": f"k{i}", "category": "design", "graduated_to": "x", "last_seen": now}
                for i in range(3)
            ],
        )
        result = vle.measure_category_health()
        assert result["categories"]["design"]["graduated_count"] == 3
        assert "design" not in result["zero_graduated"]

    def test_confidence_at_exact_boundaries(self, isolated_db: Path) -> None:
        """Test confidence values at exact bucket boundaries."""
        _seed_learnings(
            isolated_db,
            [
                {"topic": "t", "key": "k0", "confidence": 0.0},
                {"topic": "t", "key": "k3", "confidence": 0.3},
                {"topic": "t", "key": "k5", "confidence": 0.5},
                {"topic": "t", "key": "k7", "confidence": 0.7},
                {"topic": "t", "key": "k9", "confidence": 0.9},
            ],
        )
        result = vle.measure_confidence_distribution()
        total = sum(result["histogram"].values())
        assert total == 5  # All entries should be bucketed
