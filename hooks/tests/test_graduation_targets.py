#!/usr/bin/env python3
"""Tests for graduation-target resolution and the mark_graduated write guard.

A graduated learning is suppressed from injection forever, so `graduated_to`
must name a durable artifact in the repo. Ephemeral sentinels such as
`session-artifact` suppressed 97 rows permanently.

Covers:
- every notation the database carries: bare path, `agent:X`, `skill:X`,
  `target:PATH`, sentinels, out-of-repo paths, traversal, empty;
- mark_graduated refuses a sentinel target and records nothing;
- mark_graduated warns but still writes a path-shaped target that is missing.

Run with: python3 -m pytest hooks/tests/test_graduation_targets.py -v
"""

import sys
from pathlib import Path

import pytest

_LIB_DIR = Path(__file__).resolve().parent.parent / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

import learning_db_v2 as db


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Use a fresh temp learning.db for each test -- never the real one."""
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path / "learning"))
    db._initialized = False
    yield
    db._initialized = False


@pytest.fixture
def repo(tmp_path):
    """A tmp tree shaped like the toolkit repo."""
    root = tmp_path / "repo"
    for rel in (
        "agents/golang-general-engineer.md",
        "skills/meta/install/SKILL.md",
        "skills/process/worktree-agent/SKILL.md",
        "skills/meta/retro/SKILL.md",
        "docs/what-didnt-work.md",
        "hooks/session-context.py",
    ):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stub\n")
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    return root


class TestResolveGraduationTarget:
    def test_repo_relative_path_that_exists_is_durable(self, repo):
        result = db.resolve_graduation_target("docs/what-didnt-work.md", repo_root=repo)
        assert result.durable is True
        assert result.reason == "resolved"
        assert result.path == "docs/what-didnt-work.md"

    def test_repo_relative_directory_that_exists_is_durable(self, repo):
        result = db.resolve_graduation_target("scripts/", repo_root=repo)
        assert result.durable is True

    def test_repo_relative_path_that_is_missing_is_not_durable(self, repo):
        result = db.resolve_graduation_target("agents/general-purpose.md", repo_root=repo)
        assert result.durable is False
        assert result.reason == "missing"
        assert result.path == "agents/general-purpose.md"

    def test_agent_prefix_normalizes_to_agents_markdown(self, repo):
        result = db.resolve_graduation_target("agent:golang-general-engineer", repo_root=repo)
        assert result.durable is True
        assert result.path == "agents/golang-general-engineer.md"

    def test_agent_prefix_for_unknown_agent_is_not_durable(self, repo):
        result = db.resolve_graduation_target("agent:general-purpose", repo_root=repo)
        assert result.durable is False
        assert result.reason == "missing"

    def test_skill_prefix_normalizes_to_skill_directory(self, repo):
        result = db.resolve_graduation_target("skill:install", repo_root=repo)
        assert result.durable is True
        assert result.path == "skills/meta/install/SKILL.md"

    def test_skill_prefix_finds_skill_in_any_group(self, repo):
        result = db.resolve_graduation_target("skill:worktree-agent", repo_root=repo)
        assert result.durable is True
        assert result.path == "skills/process/worktree-agent/SKILL.md"

    def test_skill_prefix_for_unknown_skill_is_not_durable(self, repo):
        result = db.resolve_graduation_target("skill:does-not-exist", repo_root=repo)
        assert result.durable is False

    def test_target_prefix_strips_to_the_path(self, repo):
        result = db.resolve_graduation_target("target:skills/meta/retro/SKILL.md", repo_root=repo)
        assert result.durable is True
        assert result.path == "skills/meta/retro/SKILL.md"

    def test_target_prefix_composes_with_agent_prefix(self, repo):
        result = db.resolve_graduation_target("target:agents/golang-general-engineer.md", repo_root=repo)
        assert result.durable is True

    @pytest.mark.parametrize("sentinel", ["session-artifact", "pruned:environment-artifact", "pruned:anything"])
    def test_sentinels_are_not_durable(self, sentinel, repo):
        result = db.resolve_graduation_target(sentinel, repo_root=repo)
        assert result.durable is False
        assert result.reason == "sentinel"
        assert result.path is None

    @pytest.mark.parametrize("value", ["", "   ", None])
    def test_empty_target_is_not_durable(self, value, repo):
        result = db.resolve_graduation_target(value, repo_root=repo)
        assert result.durable is False
        assert result.reason == "empty"

    def test_absolute_path_outside_the_repo_is_not_durable(self, repo, tmp_path):
        outside = tmp_path / "elsewhere" / "SKILL.md"
        outside.parent.mkdir(parents=True, exist_ok=True)
        outside.write_text("stub\n")
        result = db.resolve_graduation_target(str(outside), repo_root=repo)
        assert result.durable is False
        assert result.reason == "outside-repo"

    def test_home_relative_path_is_not_durable(self, repo):
        result = db.resolve_graduation_target("~/.claude/hooks/scanner.py", repo_root=repo)
        assert result.durable is False
        assert result.reason == "outside-repo"

    def test_traversal_escaping_the_repo_is_not_durable(self, repo):
        result = db.resolve_graduation_target("../../etc/passwd", repo_root=repo)
        assert result.durable is False
        assert result.reason == "outside-repo"

    def test_absolute_path_inside_the_repo_resolves_relative(self, repo):
        result = db.resolve_graduation_target(str(repo / "docs/what-didnt-work.md"), repo_root=repo)
        assert result.durable is True
        assert result.path == "docs/what-didnt-work.md"

    def test_skill_name_with_a_slash_is_rejected(self, repo):
        result = db.resolve_graduation_target("skill:../../etc", repo_root=repo)
        assert result.durable is False


class TestMarkGraduatedGuard:
    def _seed(self):
        db.record_learning(
            topic="import_error",
            key="sig-1",
            value="module missing -> pip install it",
            category="error",
            source="hook:error-learner",
        )

    def _graduated_to(self):
        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT graduated_to FROM learnings WHERE topic = 'import_error' AND key = 'sig-1'"
            ).fetchone()
        return row["graduated_to"]

    def test_sentinel_target_is_refused_and_nothing_is_written(self, repo, capsys):
        self._seed()
        assert db.mark_graduated("import_error", "sig-1", "session-artifact", repo_root=repo) is False
        assert self._graduated_to() is None
        assert "session-artifact" in capsys.readouterr().err

    def test_pruned_sentinel_is_refused(self, repo):
        self._seed()
        assert db.mark_graduated("import_error", "sig-1", "pruned:environment-artifact", repo_root=repo) is False
        assert self._graduated_to() is None

    def test_durable_target_is_written_without_warning(self, repo, capsys):
        self._seed()
        assert db.mark_graduated("import_error", "sig-1", "agent:golang-general-engineer", repo_root=repo) is True
        assert self._graduated_to() == "agent:golang-general-engineer"
        assert capsys.readouterr().err == ""

    def test_missing_path_target_warns_but_still_writes(self, repo, capsys):
        self._seed()
        assert db.mark_graduated("import_error", "sig-1", "agents/not-yet-created.md", repo_root=repo) is True
        assert self._graduated_to() == "agents/not-yet-created.md"
        assert "does not resolve" in capsys.readouterr().err

    def test_missing_row_still_returns_false(self, repo):
        assert db.mark_graduated("nope", "nope", "agent:golang-general-engineer", repo_root=repo) is False
