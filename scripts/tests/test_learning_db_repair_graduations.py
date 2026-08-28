#!/usr/bin/env python3
"""Tests for the `repair-graduations` subcommand in scripts/learning-db.py.

Covers: dry-run writes nothing, --apply clears only non-durable targets,
alternate notations that resolve stay graduated, and the report table.

Run with: python3 -m pytest scripts/tests/test_learning_db_repair_graduations.py -v
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

_repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_repo_root / "hooks" / "lib"))

SCRIPT_PATH = str(_repo_root / "scripts" / "learning-db.py")


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point learning.db at a temp directory for each test -- never the real one."""
    learning_dir = tmp_path / "learning"
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(learning_dir))
    import importlib

    import learning_db_v2

    importlib.reload(learning_db_v2)
    learning_db_v2.init_db()
    yield learning_dir


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """A tmp tree shaped like the toolkit repo."""
    root = tmp_path / "repo"
    for rel in (
        "agents/golang-general-engineer.md",
        "skills/meta/toolkit-evolution/SKILL.md",
        "skills/meta/install/SKILL.md",
    ):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stub\n")
    return root


def _connect(learning_dir: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(learning_dir / "learning.db")
    conn.row_factory = sqlite3.Row
    return conn


def _insert(learning_dir: Path, topic: str, key: str, graduated_to: str | None) -> None:
    conn = _connect(learning_dir)
    conn.execute(
        "INSERT INTO learnings (topic, key, value, category, confidence, source, graduated_to) "
        "VALUES (?, ?, ?, 'error', 0.55, 'hook:error-learner', ?)",
        (topic, key, f"value for {topic}/{key}", graduated_to),
    )
    conn.commit()
    conn.close()


def _graduated(learning_dir: Path) -> dict[str, str | None]:
    conn = _connect(learning_dir)
    rows = conn.execute("SELECT key, graduated_to FROM learnings").fetchall()
    conn.close()
    return {r["key"]: r["graduated_to"] for r in rows}


def _run_cli(fake_repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, SCRIPT_PATH, "repair-graduations", "--repo-root", str(fake_repo), *args],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        timeout=30,
    )


def _seed_mixed(learning_dir: Path) -> None:
    _insert(learning_dir, "t", "durable-path", "skills/meta/toolkit-evolution/SKILL.md")
    _insert(learning_dir, "t", "durable-agent-notation", "agent:golang-general-engineer")
    _insert(learning_dir, "t", "durable-skill-notation", "skill:install")
    _insert(learning_dir, "t", "sentinel", "session-artifact")
    _insert(learning_dir, "t", "pruned-sentinel", "pruned:environment-artifact")
    _insert(learning_dir, "t", "missing-path", "agents/general-purpose.md")
    _insert(learning_dir, "t", "outside-repo", "~/.claude/hooks/scanner.py")
    _insert(learning_dir, "t", "not-graduated", None)


class TestDryRun:
    def test_dry_run_writes_nothing(self, isolated_db, fake_repo):
        _seed_mixed(isolated_db)
        before = _graduated(isolated_db)

        result = _run_cli(fake_repo)

        assert result.returncode == 0, result.stderr
        assert _graduated(isolated_db) == before
        assert "DRY RUN" in result.stdout

    def test_dry_run_is_the_default(self, isolated_db, fake_repo):
        _seed_mixed(isolated_db)
        assert _run_cli(fake_repo, "--dry-run").stdout == _run_cli(fake_repo).stdout

    def test_report_lists_targets_with_count_and_action(self, isolated_db, fake_repo):
        _seed_mixed(isolated_db)
        out = _run_cli(fake_repo).stdout

        assert "session-artifact" in out
        assert "skills/meta/toolkit-evolution/SKILL.md" in out
        assert "keep" in out
        assert "clear" in out

    def test_report_shows_pool_counts(self, isolated_db, fake_repo):
        _seed_mixed(isolated_db)
        out = _run_cli(fake_repo).stdout
        assert "Injectable pool" in out


class TestApply:
    def test_apply_clears_only_non_durable_targets(self, isolated_db, fake_repo):
        _seed_mixed(isolated_db)

        result = _run_cli(fake_repo, "--apply")

        assert result.returncode == 0, result.stderr
        after = _graduated(isolated_db)
        # Durable targets survive, in every notation.
        assert after["durable-path"] == "skills/meta/toolkit-evolution/SKILL.md"
        assert after["durable-agent-notation"] == "agent:golang-general-engineer"
        assert after["durable-skill-notation"] == "skill:install"
        # Non-durable targets are cleared.
        assert after["sentinel"] is None
        assert after["pruned-sentinel"] is None
        assert after["missing-path"] is None
        assert after["outside-repo"] is None
        # Never-graduated rows are untouched.
        assert after["not-graduated"] is None

    def test_apply_reports_rows_cleared(self, isolated_db, fake_repo):
        _seed_mixed(isolated_db)
        out = _run_cli(fake_repo, "--apply").stdout
        assert "Cleared graduated_to on 4 row" in out

    def test_apply_is_idempotent(self, isolated_db, fake_repo):
        _seed_mixed(isolated_db)
        _run_cli(fake_repo, "--apply")
        first = _graduated(isolated_db)
        second = _run_cli(fake_repo, "--apply")
        assert second.returncode == 0
        assert _graduated(isolated_db) == first

    def test_apply_on_a_clean_database_is_a_noop(self, isolated_db, fake_repo):
        _insert(isolated_db, "t", "only-durable", "skills/meta/install/SKILL.md")
        result = _run_cli(fake_repo, "--apply")
        assert result.returncode == 0
        assert _graduated(isolated_db) == {"only-durable": "skills/meta/install/SKILL.md"}


class TestJsonOutput:
    def test_json_output_is_machine_readable(self, isolated_db, fake_repo):
        import json

        _seed_mixed(isolated_db)
        out = _run_cli(fake_repo, "--json").stdout
        payload = json.loads(out)
        by_target = {row["target"]: row for row in payload["targets"]}
        assert by_target["session-artifact"]["action"] == "clear"
        assert by_target["agent:golang-general-engineer"]["action"] == "keep"
        assert payload["rows_to_clear"] == 4
