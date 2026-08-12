"""Tests for scripts/index-router.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the module under test
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import importlib

index_router = importlib.import_module("index-router")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_SKILLS_INDEX = {
    "version": "2.0",
    "skills": {
        "go-patterns": {
            "file": "skills/engineering/go-patterns/SKILL.md",
            "description": "Go patterns: testing, concurrency, error handling, code review, conventions.",
            "triggers": [
                ".go",
                "Go test",
                "_test.go",
                "table-driven",
                "goroutine",
                "channel",
                "sync.Mutex",
                "error handling",
                "fmt.Errorf",
            ],
            "force_route": True,
            "agent": "golang-general-engineer",
            "pairs_with": [],
            "category": "language",
        },
        "quick": {
            "file": "skills/process/quick/SKILL.md",
            "description": "Small mechanical changes.",
            "triggers": ["fix typo", "typo in"],
            "force_route": True,
            "category": "process",
        },
        "systematic-debugging": {
            "file": "skills/systematic-debugging/SKILL.md",
            "description": "Evidence-based debugging.",
            "triggers": ["debug", "find root cause", "reproduce bug"],
            "category": "process",
        },
        "code-linting": {
            "file": "skills/code-quality/code-linting/SKILL.md",
            "description": "Lint and format code.",
            "triggers": ["lint code", "run ruff", "format code"],
            "category": "code-quality",
        },
        "git-push-skill": {
            "file": "skills/git-push/SKILL.md",
            "description": "Push changes to remote.",
            "triggers": ["push", "push this"],
            "force_route": True,
            "category": "git-workflow",
        },
        "voice-create": {
            "file": "skills/voice-create/SKILL.md",
            "description": "Create voice profile.",
            "triggers": ["create voice", "voice profile"],
            "force_route": True,
            "category": "content",
        },
    },
}

SAMPLE_PIPELINES_INDEX = {
    "version": "2.0",
    "pipelines": {
        "pr-pipeline": {
            "file": "skills/process/pr-workflow/references/pipeline.md",
            "description": "Submit PR.",
            "triggers": ["submit PR", "create pull request", "push and PR"],
            "force_route": True,
            "phases": ["STAGE", "COMMIT", "PUSH", "CREATE", "VERIFY"],
            "pairs_with": ["pr-workflow"],
        },
        "doc-pipeline": {
            "file": "skills/workflow/references/doc-pipeline.md",
            "description": "Create documentation.",
            "triggers": ["document this", "create documentation", "write docs"],
            "force_route": True,
            "pairs_with": ["generate-claudemd"],
        },
        "explore-pipeline": {
            "file": "skills/workflow/references/explore-pipeline.md",
            "description": "Explore codebase.",
            "triggers": ["understand codebase", "explore repo", "how does this work"],
            "model": "opus",
        },
    },
}

SAMPLE_AGENTS_INDEX = {
    "version": "1.0",
    "agents": {
        "golang-general-engineer": {
            "file": "golang-general-engineer.md",
            "short_description": "Go development expert.",
            "triggers": ["go", "golang", ".go files", "gofmt"],
            "pairs_with": ["go-patterns"],
            "complexity": "Medium-Complex",
            "category": "language",
        },
        "python-general-engineer": {
            "file": "python-general-engineer.md",
            "short_description": "Python development expert.",
            "triggers": ["python", ".py", "pip", "pytest"],
            "pairs_with": ["python-quality-gate"],
            "complexity": "Medium-Complex",
            "category": "language",
        },
    },
}


@pytest.fixture()
def mock_indexes(tmp_path: Path) -> Path:
    """Create temporary INDEX files and patch REPO_ROOT."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "INDEX.json").write_text(json.dumps(SAMPLE_SKILLS_INDEX))

    pipelines_dir = tmp_path / "skills" / "workflow" / "references"
    pipelines_dir.mkdir(parents=True, exist_ok=True)
    (pipelines_dir / "pipeline-index.json").write_text(json.dumps(SAMPLE_PIPELINES_INDEX))

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "INDEX.json").write_text(json.dumps(SAMPLE_AGENTS_INDEX))

    return tmp_path


def _patched_paths(root: Path) -> dict:
    """Build an INDEX_PATHS dict (tracked path, local override name) for tmp files."""
    return {
        "skills": (root / "skills" / "INDEX.json", "INDEX.local.json"),
        "pipelines": (root / "skills" / "workflow" / "references" / "pipeline-index.json", None),
        "agents": (root / "agents" / "INDEX.json", "INDEX.local.json"),
    }


@pytest.fixture(autouse=True)
def _patch_repo_root(mock_indexes: Path) -> None:
    """Patch INDEX_PATHS to use temporary files."""
    with patch.object(index_router, "INDEX_PATHS", _patched_paths(mock_indexes)):
        yield


# ---------------------------------------------------------------------------
# load_indexes tests
# ---------------------------------------------------------------------------


class TestLoadIndexes:
    """Tests for load_indexes."""

    def test_loads_all_entry_types(self) -> None:
        entries = index_router.load_indexes()
        types = {e.entry_type for e in entries}
        assert types == {"skill", "pipeline", "agent"}

    def test_loads_correct_count(self) -> None:
        entries = index_router.load_indexes()
        # 6 skills + 3 pipelines + 2 agents = 11
        assert len(entries) == 11

    def test_skill_entry_fields(self) -> None:
        entries = index_router.load_indexes()
        go_patterns = next(e for e in entries if e.name == "go-patterns")
        assert go_patterns.entry_type == "skill"
        assert go_patterns.force_route is True
        assert go_patterns.agent == "golang-general-engineer"
        assert "Go test" in go_patterns.triggers

    def test_pipeline_entry_fields(self) -> None:
        entries = index_router.load_indexes()
        pr = next(e for e in entries if e.name == "pr-pipeline")
        assert pr.entry_type == "pipeline"
        assert pr.force_route is True

    def test_agent_entry_fields(self) -> None:
        entries = index_router.load_indexes()
        golang = next(e for e in entries if e.name == "golang-general-engineer")
        assert golang.entry_type == "agent"
        assert "go" in golang.triggers

    def test_missing_index_file_graceful(self, mock_indexes: Path) -> None:
        (mock_indexes / "agents" / "INDEX.json").unlink()
        with patch.object(index_router, "INDEX_PATHS", _patched_paths(mock_indexes)):
            entries = index_router.load_indexes()
        # Should still load skills and pipelines (6 + 3 = 9 entries)
        assert len(entries) == 9
        assert all(e.entry_type != "agent" for e in entries)

    def test_malformed_json_graceful(self, mock_indexes: Path) -> None:
        (mock_indexes / "skills" / "INDEX.json").write_text("not json {{{")
        with patch.object(index_router, "INDEX_PATHS", _patched_paths(mock_indexes)):
            entries = index_router.load_indexes()
        # Should still load pipelines and agents (3 + 2 = 5 entries)
        assert len(entries) == 5

    def test_local_overlay_adds_entries(self, mock_indexes: Path) -> None:
        """A local INDEX.local.json adds entries on top of the tracked index."""
        local = {"skills": {"private-skill": {"triggers": ["private thing"]}}}
        (mock_indexes / "skills" / "INDEX.local.json").write_text(json.dumps(local))
        entries = index_router.load_indexes()
        names = {e.name for e in entries}
        assert "private-skill" in names

    def test_stale_local_never_hides_tracked_entries(self, mock_indexes: Path) -> None:
        """A stale local index (missing tracked entries) cannot drop them.

        Regression for the stale-local-override bug: _resolve_index replaced
        the tracked index wholesale with INDEX.local.json, hiding newly added
        skills from routing.
        """
        stale_local = {"skills": {"private-skill": {"triggers": ["private thing"]}}}
        (mock_indexes / "skills" / "INDEX.local.json").write_text(json.dumps(stale_local))
        entries = index_router.load_indexes()
        names = {e.name for e in entries}
        # Tracked skills survive alongside the local addition.
        assert "go-patterns" in names
        assert "private-skill" in names

    def test_stale_local_never_overrides_tracked_content(self, mock_indexes: Path) -> None:
        """A stale local superset cannot revert tracked entry content (add-only merge)."""
        stale_local = {"skills": {"go-patterns": {"triggers": ["stale trigger"], "force_route": False}}}
        (mock_indexes / "skills" / "INDEX.local.json").write_text(json.dumps(stale_local))
        entries = index_router.load_indexes()
        go_patterns = next(e for e in entries if e.name == "go-patterns")
        assert go_patterns.force_route is True
        assert "Go test" in go_patterns.triggers


# ---------------------------------------------------------------------------
# check_force_routes tests
# ---------------------------------------------------------------------------


class TestCheckForceRoutes:
    """Tests for check_force_routes."""

    def test_matches_force_route_skill(self) -> None:
        entries = index_router.load_indexes()
        match = index_router.check_force_routes("write Go test for auth", entries)
        assert match is not None
        assert match.name == "go-patterns"
        assert match.agent == "golang-general-engineer"

    def test_matches_force_route_pipeline(self) -> None:
        entries = index_router.load_indexes()
        match = index_router.check_force_routes("submit PR for this feature", entries)
        assert match is not None
        assert match.name == "pr-pipeline"
        assert match.entry_type == "pipeline"

    def test_case_insensitive_matching(self) -> None:
        entries = index_router.load_indexes()
        match = index_router.check_force_routes("CREATE PULL REQUEST now", entries)
        assert match is not None
        assert match.name == "pr-pipeline"

    def test_no_match_returns_none(self) -> None:
        entries = index_router.load_indexes()
        match = index_router.check_force_routes("something completely unrelated", entries)
        assert match is None

    def test_non_force_route_not_matched(self) -> None:
        entries = index_router.load_indexes()
        # "debug" is a trigger for systematic-debugging but it's NOT force_route
        match = index_router.check_force_routes("debug this issue", entries)
        assert match is None

    def test_substring_match(self) -> None:
        entries = index_router.load_indexes()
        # "table-driven" is a trigger for go-patterns
        match = index_router.check_force_routes("write table-driven tests for auth", entries)
        assert match is not None
        assert match.name == "go-patterns"

    def test_go_file_edit_outranks_quick(self) -> None:
        entries = index_router.load_indexes()
        match = index_router.check_force_routes("fix typo in foo.go", entries)
        assert match is not None
        assert match.name == "go-patterns"

    @pytest.mark.parametrize(
        "operand",
        ["foo.go", "foo.go:42", "foo.go#L42", "foo.go,", "foo.go.", "`foo.go`", "(foo.go)"],
    )
    def test_go_source_operand_positive_matrix(self, operand: str) -> None:
        entries = index_router.load_indexes()
        match = index_router.check_force_routes(f"fix typo in {operand}", entries)
        assert match is not None
        assert match.name == "go-patterns"

    @pytest.mark.parametrize(
        "operand",
        ["foo.go.txt", "changelog.go.md", ".golangci.yml", ".goreleaser.yml", "example.google", "foo.gox"],
    )
    def test_go_source_operand_negative_matrix(self, operand: str) -> None:
        entries = index_router.load_indexes()
        match = index_router.check_force_routes(f"fix typo in {operand}", entries)
        assert match is not None
        assert match.name == "quick"

    @pytest.mark.parametrize("query", ["push back on foo.go", "push against foo.go", "pushback on foo.go"])
    def test_go_operand_push_metaphors_do_not_route_pr(self, query: str) -> None:
        entries = index_router.load_indexes()
        match = index_router.check_force_routes(query, entries)
        assert match is None or match.name != "pr-workflow"


# ---------------------------------------------------------------------------
# Word-boundary matching tests
# ---------------------------------------------------------------------------


class TestWordBoundaryMatching:
    """Tests for word-boundary matching on single-word triggers."""

    def test_single_word_no_partial_word_match(self) -> None:
        """'push' should NOT match 'pushing' or 'pushed' (morphological variants)."""
        entries = index_router.load_indexes()
        assert index_router.check_force_routes("I'm pushing changes now", entries) is None
        assert index_router.check_force_routes("I pushed the changes", entries) is None

    def test_single_word_trigger_matches_standalone(self) -> None:
        """'push' SHOULD match when it appears as a standalone word."""
        entries = index_router.load_indexes()
        match = index_router.check_force_routes("push my changes", entries)
        assert match is not None
        assert match.name == "git-push-skill"

    def test_single_word_trigger_matches_at_end(self) -> None:
        """'push' SHOULD match 'please push'."""
        entries = index_router.load_indexes()
        match = index_router.check_force_routes("please push", entries)
        assert match is not None
        assert match.name == "git-push-skill"

    def test_multi_word_trigger_still_matches(self) -> None:
        """'push this' SHOULD match (multi-word trigger uses containment)."""
        entries = index_router.load_indexes()
        match = index_router.check_force_routes("push this to remote", entries)
        assert match is not None
        assert match.name == "git-push-skill"

    def test_multi_word_trigger_create_voice(self) -> None:
        """'create voice' SHOULD match 'I want to create voice profile'."""
        entries = index_router.load_indexes()
        match = index_router.check_force_routes("I want to create voice profile", entries)
        assert match is not None
        assert match.name == "voice-create"

    def test_multi_word_trigger_go_test(self) -> None:
        """'Go test' SHOULD match 'write Go test for auth'."""
        entries = index_router.load_indexes()
        match = index_router.check_force_routes("write Go test for auth", entries)
        assert match is not None
        assert match.name == "go-patterns"

    def test_hyphenated_trigger_matches(self) -> None:
        """'table-driven' should match at word boundaries."""
        entries = index_router.load_indexes()
        match = index_router.check_force_routes("write table-driven tests", entries)
        assert match is not None
        assert match.name == "go-patterns"

    def test_single_word_not_embedded_in_larger_word(self) -> None:
        """Single-word trigger should not match inside a larger word.

        Old substring matching would match 'Go test' trigger's individual
        processing against words like 'gopher'. Word-boundary prevents this.
        """
        # Direct helper test: "go" should not match inside "gopher"
        assert index_router._trigger_matches("go", "build the gopher tool") is False
        assert index_router._trigger_matches("go", "fix the Go code") is True


class TestTriggerMatchesHelper:
    """Unit tests for the _trigger_matches helper."""

    def test_single_word_boundary_match(self) -> None:
        assert index_router._trigger_matches("push", "push my changes") is True

    def test_single_word_no_partial_match(self) -> None:
        """Word boundary prevents matching inside morphological variants."""
        assert index_router._trigger_matches("push", "pushing changes") is False
        assert index_router._trigger_matches("push", "pushed already") is False

    def test_single_word_no_embedded_match(self) -> None:
        """Word boundary prevents matching inside compound words."""
        assert index_router._trigger_matches("go", "gopher tool") is False
        assert index_router._trigger_matches("go", "ergo sum") is False

    def test_multi_word_containment(self) -> None:
        assert index_router._trigger_matches("create voice", "I want to create voice profile") is True

    def test_multi_word_no_match(self) -> None:
        assert index_router._trigger_matches("create voice", "create a new profile") is False

    def test_case_insensitive(self) -> None:
        assert index_router._trigger_matches("Go", "fix the go code") is True

    def test_empty_trigger(self) -> None:
        assert index_router._trigger_matches("", "some request") is False

    def test_hyphenated_single_token(self) -> None:
        # "table-driven" has no spaces, so it's single-word and uses \b matching.
        # \b treats hyphens as boundaries, so this matches "table-driven" as a unit.
        assert index_router._trigger_matches("table-driven", "write table-driven tests") is True

    def test_hyphenated_no_false_positive(self) -> None:
        # "table-driven" should not match "table" alone
        assert index_router._trigger_matches("table-driven", "look at the table") is False


class TestIsSingleWord:
    """Unit tests for the _is_single_word helper."""

    def test_single_word(self) -> None:
        assert index_router._is_single_word("push") is True

    def test_multi_word(self) -> None:
        assert index_router._is_single_word("create voice") is False

    def test_hyphenated(self) -> None:
        assert index_router._is_single_word("table-driven") is True  # word chars + hyphens

    def test_with_whitespace(self) -> None:
        assert index_router._is_single_word("  push  ") is True

    def test_empty(self) -> None:
        assert index_router._is_single_word("") is False  # no \w chars


# ---------------------------------------------------------------------------
# score_candidates tests
# ---------------------------------------------------------------------------


class TestScoreCandidates:
    """Tests for score_candidates."""

    def test_returns_scored_list(self) -> None:
        entries = index_router.load_indexes()
        candidates = index_router.score_candidates("debug find root cause", entries)
        assert len(candidates) > 0
        assert all(c.score > 0.1 for c in candidates)

    def test_sorted_by_score_descending(self) -> None:
        entries = index_router.load_indexes()
        candidates = index_router.score_candidates("lint code format code run ruff", entries)
        scores = [c.score for c in candidates]
        assert scores == sorted(scores, reverse=True)

    def test_top_candidate_correct(self) -> None:
        entries = index_router.load_indexes()
        candidates = index_router.score_candidates("lint code run ruff format code", entries)
        assert candidates[0].name == "code-linting"

    def test_no_match_returns_empty(self) -> None:
        entries = index_router.load_indexes()
        candidates = index_router.score_candidates("xyzzy plugh zzzzz", entries)
        assert candidates == []

    def test_respects_max_candidates(self) -> None:
        entries = index_router.load_indexes()
        candidates = index_router.score_candidates("all the things", entries)
        assert len(candidates) <= index_router.MAX_CANDIDATES


# ---------------------------------------------------------------------------
# resolve_agent tests
# ---------------------------------------------------------------------------


class TestResolveAgent:
    """Tests for resolve_agent."""

    def test_returns_existing_agent(self) -> None:
        entries = index_router.load_indexes()
        candidate = index_router.Candidate(
            entry_type="skill", name="go-patterns", score=0.9, agent="golang-general-engineer"
        )
        assert index_router.resolve_agent(candidate, entries) == "golang-general-engineer"

    def test_resolves_from_agent_index(self) -> None:
        entries = index_router.load_indexes()
        # pr-pipeline has no agent — should try to match against agents
        candidate = index_router.Candidate(entry_type="pipeline", name="pr-pipeline", score=0.8)
        # May or may not resolve depending on name overlap with agent triggers
        result = index_router.resolve_agent(candidate, entries)
        # Result can be None or a valid agent name
        assert result is None or isinstance(result, str)

    def test_returns_none_when_no_agent_match(self) -> None:
        entries = index_router.load_indexes()
        candidate = index_router.Candidate(entry_type="skill", name="zzzz-nonexistent", score=0.5)
        result = index_router.resolve_agent(candidate, entries)
        # No overlap between "zzzz" and any agent triggers
        assert result is None


# ---------------------------------------------------------------------------
# resolve_agent pairs_with path tests
# ---------------------------------------------------------------------------


class TestResolveAgentPairsWithPaths:
    """Tests for the pairs_with resolution path in resolve_agent.

    Covers the 3-step algorithm in resolve_agent():
    - Step 1: candidate.agent field (tested in TestResolveAgent above)
    - Step 2: pairs_with list contains an agent name -> return first agent
    - Guard clause: non-empty pairs_with with NO agent names -> return None
    - Step 3: trigger-word overlap fallback (only when pairs_with is empty/absent)
    """

    def _build_entries(self, extra_skills: list[dict] | None = None) -> list[index_router.IndexEntry]:
        """Build a controlled set of entries for pairs_with testing.

        Creates two agents (python-general-engineer, typescript-frontend-engineer)
        and merges in any extra skill entries for test-specific scenarios.

        Args:
            extra_skills: Optional list of dicts with IndexEntry kwargs for skills.

        Returns:
            List of IndexEntry objects for use in resolve_agent calls.
        """
        entries: list[index_router.IndexEntry] = [
            index_router.IndexEntry(
                name="python-general-engineer",
                entry_type="agent",
                triggers=["python", ".py", "pip", "pytest"],
            ),
            index_router.IndexEntry(
                name="typescript-frontend-engineer",
                entry_type="agent",
                triggers=["typescript", "react", "next.js", "frontend"],
            ),
            # Skills that are NOT agents (used to verify they're skipped)
            index_router.IndexEntry(
                name="test-driven-development",
                entry_type="skill",
                triggers=["tdd", "red green refactor"],
            ),
            index_router.IndexEntry(
                name="systematic-debugging",
                entry_type="skill",
                triggers=["debug", "root cause"],
            ),
        ]
        for skill_kwargs in extra_skills or []:
            entries.append(index_router.IndexEntry(entry_type="skill", **skill_kwargs))
        return entries

    def test_resolves_agent_from_pairs_with(self) -> None:
        """Step 2: skill with pairs_with containing an agent name returns that agent."""
        entries = self._build_entries(
            extra_skills=[
                {
                    "name": "security-threat-model",
                    "triggers": ["threat model", "security audit"],
                    "pairs_with": ["python-general-engineer"],
                },
            ]
        )
        candidate = index_router.Candidate(
            entry_type="skill",
            name="security-threat-model",
            score=0.8,
            agent=None,
        )
        result = index_router.resolve_agent(candidate, entries)
        assert result == "python-general-engineer"

    def test_picks_first_agent_from_mixed_pairs_with(self) -> None:
        """Step 2: when pairs_with has skills AND agents, return the first agent (skip skills)."""
        entries = self._build_entries(
            extra_skills=[
                {
                    "name": "game-sprite-pipeline",
                    "triggers": ["AI sprite", "generate sprite"],
                    "pairs_with": [
                        "test-driven-development",
                        "python-general-engineer",
                        "typescript-frontend-engineer",
                    ],
                },
            ]
        )
        candidate = index_router.Candidate(
            entry_type="skill",
            name="game-sprite-pipeline",
            score=0.7,
            agent=None,
        )
        result = index_router.resolve_agent(candidate, entries)
        # Must return python-general-engineer (first AGENT in the list), not test-driven-development
        assert result == "python-general-engineer"

    def test_non_empty_pairs_with_no_agents_returns_none(self) -> None:
        """Guard clause: non-empty pairs_with with only skill names returns None.

        This is the critical guard at line ~348: when pairs_with is non-empty but
        contains NO agent names, resolve_agent returns None and does NOT fall
        through to the trigger-word overlap step (Step 3).
        """
        entries = self._build_entries(
            extra_skills=[
                {
                    "name": "testing-preferred-patterns",
                    "triggers": ["testing anti-patterns", "flaky tests"],
                    "pairs_with": ["test-driven-development", "systematic-debugging"],
                },
            ]
        )
        candidate = index_router.Candidate(
            entry_type="skill",
            name="testing-preferred-patterns",
            score=0.6,
            agent=None,
        )
        result = index_router.resolve_agent(candidate, entries)
        # pairs_with is non-empty but contains no agents -> None (no fallback)
        assert result is None

    def test_empty_pairs_with_falls_through_to_trigger_overlap(self) -> None:
        """Step 3: empty pairs_with list falls through to trigger-word overlap."""
        entries = self._build_entries(
            extra_skills=[
                {
                    "name": "python-quality-gate",
                    "triggers": ["python", "ruff", "pytest", "mypy"],
                    "pairs_with": [],
                },
            ]
        )
        candidate = index_router.Candidate(
            entry_type="skill",
            name="python-quality-gate",
            score=0.8,
            agent=None,
        )
        result = index_router.resolve_agent(candidate, entries)
        # Empty pairs_with -> falls through to Step 3. "python" overlaps with
        # python-general-engineer triggers, but trigger-word overlap checks
        # candidate.name words against agent trigger words. "python-quality-gate"
        # splits to {"python", "quality", "gate"} — "python" matches the agent's
        # trigger words. Needs >= 2 overlap by default, so check if the algorithm
        # finds a match or returns None based on overlap threshold.
        # The name "python-quality-gate" has 3 words. min_overlap = max(2, 3//2+1) = 2.
        # Only "python" overlaps -> overlap=1 < min_overlap=2 -> returns None.
        # This confirms the fallback was ATTEMPTED (didn't short-circuit), just
        # didn't find enough overlap.
        assert result is None

    def test_absent_pairs_with_falls_through_to_trigger_overlap(self) -> None:
        """Step 3: absent pairs_with (default empty list) also falls through."""
        entries = self._build_entries(
            extra_skills=[
                {
                    "name": "python-linting",
                    "triggers": ["lint", "ruff"],
                    # No pairs_with at all -> defaults to empty list
                },
            ]
        )
        candidate = index_router.Candidate(
            entry_type="skill",
            name="python-linting",
            score=0.7,
            agent=None,
        )
        result = index_router.resolve_agent(candidate, entries)
        # "python-linting" -> {"python", "linting"}, min_overlap = max(2, 2//2+1) = 2.
        # "python" matches python-general-engineer triggers, "linting" does not.
        # overlap=1 < min_overlap=2 -> None. Confirms fallback was attempted.
        assert result is None

    def test_trigger_overlap_succeeds_with_sufficient_words(self) -> None:
        """Step 3 positive case: trigger-word overlap succeeds when words match."""
        entries = self._build_entries(
            extra_skills=[
                {
                    "name": "python-pytest-runner",
                    "triggers": ["run tests"],
                    # No pairs_with -> falls through to trigger overlap
                },
            ]
        )
        candidate = index_router.Candidate(
            entry_type="skill",
            name="python-pytest-runner",
            score=0.7,
            agent=None,
        )
        result = index_router.resolve_agent(candidate, entries)
        # "python-pytest-runner" -> {"python", "pytest", "runner"}, min_overlap = max(2, 3//2+1) = 2.
        # python-general-engineer triggers: {"python", ".py", "pip", "pytest"}
        # overlap: {"python", "pytest"} -> 2 >= 2 -> match!
        assert result == "python-general-engineer"

    def test_suggest_pairs_excludes_self_references(self) -> None:
        """Verify suggest_pairs excludes names already in the matched set."""
        matched = [
            index_router.IndexEntry(
                name="phaser-gamedev",
                entry_type="skill",
                pairs_with=["typescript-frontend-engineer", "game-asset-generator"],
            ),
            index_router.IndexEntry(
                name="game-asset-generator",
                entry_type="skill",
                pairs_with=["threejs-builder", "typescript-frontend-engineer"],
            ),
        ]
        pairs = index_router.suggest_pairs(matched)
        # "phaser-gamedev" and "game-asset-generator" are matched -> excluded from output
        assert "phaser-gamedev" not in pairs
        assert "game-asset-generator" not in pairs
        # But their pairs_with targets that aren't in matched_names should appear
        assert "typescript-frontend-engineer" in pairs
        assert "threejs-builder" in pairs
        # Verify deduplication: typescript-frontend-engineer appears in both but listed once
        assert pairs.count("typescript-frontend-engineer") == 1


# ---------------------------------------------------------------------------
# suggest_pairs tests
# ---------------------------------------------------------------------------


class TestSuggestPairs:
    """Tests for suggest_pairs."""

    def test_collects_pairs(self) -> None:
        entry = index_router.IndexEntry(name="go-patterns", entry_type="skill", pairs_with=["systematic-debugging"])
        pairs = index_router.suggest_pairs([entry])
        assert pairs == ["systematic-debugging"]

    def test_deduplicates(self) -> None:
        entries = [
            index_router.IndexEntry(name="a", entry_type="skill", pairs_with=["x", "y"]),
            index_router.IndexEntry(name="b", entry_type="skill", pairs_with=["y", "z"]),
        ]
        pairs = index_router.suggest_pairs(entries)
        assert pairs == ["x", "y", "z"]

    def test_excludes_self_references(self) -> None:
        entries = [
            index_router.IndexEntry(name="a", entry_type="skill", pairs_with=["b"]),
            index_router.IndexEntry(name="b", entry_type="skill", pairs_with=["a", "c"]),
        ]
        pairs = index_router.suggest_pairs(entries)
        # "a" and "b" are matched entries, so excluded from pairs
        assert pairs == ["c"]


# ---------------------------------------------------------------------------
# check_composition_chains tests
# ---------------------------------------------------------------------------


class TestCheckCompositionChains:
    """Tests for check_composition_chains."""

    def test_finds_chain_for_entry_skill(self) -> None:
        chains = index_router.check_composition_chains("systematic-debugging")
        assert len(chains) == 1
        assert chains[0] == ["systematic-debugging", "test-driven-development", "pr-pipeline"]

    def test_finds_chain_for_member_skill(self) -> None:
        chains = index_router.check_composition_chains("test-driven-development")
        assert len(chains) == 1
        assert "systematic-debugging" in chains[0]

    def test_returns_empty_for_no_match(self) -> None:
        chains = index_router.check_composition_chains("nonexistent-skill")
        assert chains == []

    def test_returns_empty_for_none(self) -> None:
        chains = index_router.check_composition_chains(None)
        assert chains == []

    def test_doc_pipeline_chain(self) -> None:
        chains = index_router.check_composition_chains("doc-pipeline")
        assert len(chains) == 1
        assert chains[0] == ["docs-sync-checker", "doc-pipeline", "generate-claudemd"]


# ---------------------------------------------------------------------------
# route_request integration tests
# ---------------------------------------------------------------------------


class TestRouteRequest:
    """Integration tests for route_request."""

    def test_force_route_populates_result(self) -> None:
        result = index_router.route_request("write Go test for the handler")
        assert result.force_route is not None
        assert result.force_route.get("skill") == "go-patterns"
        assert result.force_route.get("agent") == "golang-general-engineer"

    def test_force_only_skips_candidates(self) -> None:
        result = index_router.route_request("write Go test for the handler", force_only=True)
        assert result.force_route is not None
        assert result.candidates == []

    def test_no_match_returns_empty_result(self) -> None:
        result = index_router.route_request("xyzzy plugh zzzzz")
        assert result.force_route is None
        assert result.candidates == []
        assert result.pairs_with == []
        assert result.model_preference is None

    def test_candidates_populated_for_non_force(self) -> None:
        result = index_router.route_request("lint code format code run ruff")
        # code-linting should be top candidate
        assert len(result.candidates) > 0
        assert result.candidates[0].name == "code-linting"

    def test_pipeline_force_route(self) -> None:
        result = index_router.route_request("create documentation for the API")
        assert result.force_route is not None
        assert result.force_route.get("pipeline") == "doc-pipeline"

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("create PR for foo.go", "pr-workflow"),
            ("push foo.go", "pr-workflow"),
            ("security review foo.go", "security-review"),
            ("security audit foo.go", "security-review"),
        ],
    )
    def test_protected_composite_keeps_primary_and_pairs_go(self, query: str, expected: str) -> None:
        entries = [
            index_router.IndexEntry(
                name="go-patterns",
                entry_type="skill",
                triggers=[".go"],
                force_route=True,
                agent="golang-general-engineer",
            ),
            index_router.IndexEntry(
                name="pr-workflow",
                entry_type="skill",
                triggers=["create PR"],
                force_route=True,
            ),
            index_router.IndexEntry(
                name="security-review",
                entry_type="skill",
                triggers=["security review"],
                force_route=True,
            ),
        ]
        result = index_router.route_request(query, force_only=True, entries=entries)
        assert result.force_route is not None
        assert result.force_route.get("skill") == expected
        assert "go-patterns" in result.pairs_with


# ---------------------------------------------------------------------------
# Output formatting tests
# ---------------------------------------------------------------------------


class TestFormatting:
    """Tests for output formatting."""

    def test_json_output_valid(self) -> None:
        result = index_router.route_request("write Go test for auth")
        output = index_router.format_json_output(result)
        parsed = json.loads(output)
        assert "force_route" in parsed
        assert "candidates" in parsed
        assert "pairs_with" in parsed
        assert "model_preference" in parsed
        assert "composition_chains" in parsed

    def test_json_output_candidate_fields(self) -> None:
        result = index_router.route_request("lint code format code run ruff")
        output = index_router.format_json_output(result)
        parsed = json.loads(output)
        for candidate in parsed["candidates"]:
            assert "type" in candidate
            assert "name" in candidate
            assert "score" in candidate

    def test_text_output_force_route(self) -> None:
        result = index_router.route_request("write Go test for auth")
        output = index_router.format_text_output(result)
        assert "force_route:" in output
        assert "go-patterns" in output

    def test_text_output_no_match(self) -> None:
        result = index_router.route_request("xyzzy zzzzz")
        output = index_router.format_text_output(result)
        assert "no_match: true" in output


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


SCRIPT_PATH = str(Path(__file__).resolve().parent.parent / "index-router.py")


class TestCLI:
    """CLI integration tests using subprocess against real INDEX files."""

    def test_json_flag(self) -> None:
        result = subprocess.run(
            [sys.executable, SCRIPT_PATH, "--request", "write Go tests for auth", "--json"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert "force_route" in parsed

    def test_plain_text_output(self) -> None:
        result = subprocess.run(
            [sys.executable, SCRIPT_PATH, "--request", "write Go tests for auth"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "go-patterns" in result.stdout

    def test_force_only_flag(self) -> None:
        result = subprocess.run(
            [sys.executable, SCRIPT_PATH, "--request", "write Go tests for auth", "--force-only", "--json"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert parsed["candidates"] == []
        assert parsed["force_route"] is not None

    @pytest.mark.parametrize(
        "query",
        [
            "create a PR for main.go",
            "open a PR for main.go",
            "make a pull request for main.go",
            "draft a PR for main.go",
            "submit main.go as a PR",
            "raise a PR for main.go",
            "file a pull request for main.go",
        ],
    )
    def test_real_index_article_bearing_pr_intent(self, query: str) -> None:
        result = subprocess.run(
            [sys.executable, SCRIPT_PATH, "--request", query, "--force-only", "--json"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert parsed["force_route"]["skill"] == "pr-workflow"
        assert "go-patterns" in parsed["pairs_with"]

    @pytest.mark.parametrize(
        "query",
        ["open main.go", "make main.go", "draft main.go", "submit main.go", "raise main.go", "file main.go"],
    )
    def test_real_index_bounded_pr_verbs_without_pr_noun_stay_go(self, query: str) -> None:
        result = subprocess.run(
            [sys.executable, SCRIPT_PATH, "--request", query, "--force-only", "--json"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert parsed["force_route"]["skill"] == "go-patterns"

    @pytest.mark.parametrize("query", ["push back on foo.go", "push against foo.go", "pushback on foo.go"])
    def test_real_index_push_metaphors_do_not_route_pr(self, query: str) -> None:
        result = subprocess.run(
            [sys.executable, SCRIPT_PATH, "--request", query, "--force-only", "--json"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert parsed["force_route"] is None or parsed["force_route"].get("skill") != "pr-workflow"

    def test_always_exits_zero(self) -> None:
        result = subprocess.run(
            [sys.executable, SCRIPT_PATH, "--request", "xyzzy plugh completely unrelated"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
