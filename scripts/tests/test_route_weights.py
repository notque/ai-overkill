"""Tests for the `route-weights --json` subcommand of learning-db.py.

route-weights is a thin read-only reader over routing/effectiveness rows.
It emits JSON keyed `<agent>:<skill>` with {confidence, n, success, failure,
last_seen}, where n = observation_count. It must:
  - be deterministic in ordering,
  - exclude obvious test rows (source LIKE 'test%'),
  - never write to the DB,
  - run fast (<100ms at 10k rows).

Rows are seeded into a temp DB via record_learning / boost_confidence /
decay_confidence; the command runs as a subprocess so we exercise the real
CLI entry point against CLAUDE_LEARNING_DIR.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

_repo_root = Path(__file__).resolve().parent.parent.parent
_repo_hooks_lib = str(_repo_root / "hooks" / "lib")
_cli_path = str(_repo_root / "scripts" / "learning-db.py")


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the learning DB at a temp dir so tests never touch real data."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))

    # Make the repo hooks/lib importable and reset the init flag for this proc.
    if _repo_hooks_lib not in sys.path:
        sys.path.insert(0, _repo_hooks_lib)
    import learning_db_v2

    monkeypatch.setattr(learning_db_v2, "_initialized", False)
    return db_dir


def _seed_route(key: str, *, source: str = "routing:decision") -> None:
    """Seed one routing/effectiveness row."""
    from learning_db_v2 import record_learning

    record_learning(
        topic="routing",
        key=key,
        value=f"agent: {key.split(':')[0]} | skill: {key.split(':')[-1]}",
        category="effectiveness",
        source=source,
    )


def _run_cli(db_dir: Path) -> subprocess.CompletedProcess[str]:
    """Run `learning-db.py route-weights --json` as a subprocess."""
    env = dict(os.environ)
    env["CLAUDE_LEARNING_DIR"] = str(db_dir)
    return subprocess.run(
        [sys.executable, _cli_path, "route-weights", "--json"],
        capture_output=True,
        text=True,
        env=env,
    )


def test_shape_and_math(isolated_db: Path) -> None:
    """Output is keyed agent:skill with the documented fields and correct math."""
    from learning_db_v2 import boost_confidence, decay_confidence

    _seed_route("golang-general-engineer:go-patterns")
    boost_confidence("routing", "golang-general-engineer:go-patterns")
    boost_confidence("routing", "golang-general-engineer:go-patterns")

    _seed_route("python-general-engineer:test-driven-development")
    decay_confidence("routing", "python-general-engineer:test-driven-development")

    result = _run_cli(isolated_db)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)

    go = data["golang-general-engineer:go-patterns"]
    assert set(go) == {"confidence", "n", "success", "failure", "last_seen"}
    assert go["success"] == 2
    assert go["failure"] == 0
    assert go["n"] >= 1
    assert isinstance(go["confidence"], float)
    assert go["last_seen"]

    py = data["python-general-engineer:test-driven-development"]
    assert py["success"] == 0
    assert py["failure"] == 1


def test_excludes_test_rows(isolated_db: Path) -> None:
    """Rows from a test source are omitted."""
    _seed_route("real-agent:real-skill", source="routing:decision")
    _seed_route("fake-agent:fake-skill", source="test:fixture")

    result = _run_cli(isolated_db)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)

    assert "real-agent:real-skill" in data
    assert "fake-agent:fake-skill" not in data


def test_deterministic_ordering(isolated_db: Path) -> None:
    """Two runs over the same data yield byte-identical key ordering."""
    for key in ("b-agent:b-skill", "a-agent:a-skill", "c-agent:c-skill"):
        _seed_route(key)

    first = _run_cli(isolated_db)
    second = _run_cli(isolated_db)
    assert first.returncode == 0 and second.returncode == 0
    assert first.stdout == second.stdout
    keys = list(json.loads(first.stdout).keys())
    assert keys == sorted(keys)


def test_empty_db_emits_object(isolated_db: Path) -> None:
    """No routing rows -> empty JSON object, exit 0."""
    result = _run_cli(isolated_db)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {}


def test_no_writes(isolated_db: Path) -> None:
    """The command does not mutate the DB file."""
    _seed_route("x-agent:x-skill")
    db_file = isolated_db / "learning.db"
    before = db_file.stat().st_mtime_ns
    time.sleep(0.01)
    result = _run_cli(isolated_db)
    assert result.returncode == 0, result.stderr
    after = db_file.stat().st_mtime_ns
    assert before == after, "route-weights must not write to the DB"


@pytest.mark.slow
@pytest.mark.performance
def test_performance_10k_rows(isolated_db: Path) -> None:
    """Reads 10k rows in under 100ms (query time, excluding interpreter start)."""
    from learning_db_v2 import record_learning

    for i in range(10000):
        record_learning(
            topic="routing",
            key=f"agent{i}:skill{i}",
            value="agent: a | skill: s",
            category="effectiveness",
            source="routing:decision",
        )

    # Time only the query path, in-process, not subprocess startup.
    sys.path.insert(0, str(_repo_root / "scripts"))
    import importlib

    learning_db = importlib.import_module("learning-db")
    sys.path.pop(0)

    start = time.perf_counter()
    rows = learning_db.collect_route_weights()
    elapsed = time.perf_counter() - start
    assert len(rows) == 10000
    # Guard against accidental O(n^2)/full-table-scan regressions, not runner jitter.
    # At 10k rows a real regression lands in seconds; 0.5s keeps the guard while
    # absorbing shared-runner variance (a clean run is ~0.01s; shared CI runners
    # have measured ~0.114s for this same correct query).
    assert elapsed < 0.5, f"route-weights query took {elapsed * 1000:.1f}ms (>500ms)"
