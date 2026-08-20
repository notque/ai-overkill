"""Tests for scripts/pre-route.py — the deterministic force-route guard.

pre-route matches force_route entries only; non-force keyword routing was
retired (2026-07). Force-route corpus pins live in test_pre_route_pr_workflow,
test_pre_route_planning, and test_pre_route_public_web_deploy."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import ClassVar

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "pre-route.py"

# ---------------------------------------------------------------------------
# Import the module for unit testing
# ---------------------------------------------------------------------------


@pytest.fixture
def pre_route(monkeypatch: pytest.MonkeyPatch):
    """Import pre_route module with real INDEX files."""
    monkeypatch.syspath_prepend(str(REPO_ROOT / "scripts"))
    # Use importlib to avoid name collision with hyphenated filename
    import importlib

    mod = importlib.import_module("pre-route")
    return mod


@pytest.fixture
def real_entries(pre_route):
    """Load real entries from INDEX.json files."""
    return pre_route.load_entries()


# ---------------------------------------------------------------------------
# Core routing tests (from spec)
# ---------------------------------------------------------------------------


class TestSpecifiedRoutes:
    """Test cases from the task specification."""

    def test_go_tests_matches_go_patterns(self, pre_route, real_entries) -> None:
        """'run the go tests' should match go-patterns or golang-general-engineer."""
        result = pre_route.route("run the go tests", entries=real_entries)
        assert result["matched"] is True
        # Should match go-patterns (force-route skill with "go test" trigger)
        assert result["skill"] == "go-patterns" or result["agent"] == "golang-general-engineer"

    @pytest.mark.parametrize("query", ["fix typo in foo.go", "fix the spelling in main.go"])
    def test_go_file_edits_match_go_patterns(self, pre_route, real_entries, query: str) -> None:
        """Even trivial .go edits must load the mandatory Go style baseline."""
        result = pre_route.route(query, entries=real_entries)
        assert result["matched"] is True
        assert result["skill"] == "go-patterns"
        assert result["match_type"] == "force_route"

    def test_non_go_typo_stays_quick(self, pre_route, real_entries) -> None:
        result = pre_route.route("fix typo in README.md", entries=real_entries)
        assert result["skill"] == "quick"

    @pytest.mark.parametrize(
        "operand",
        ["foo.go", "foo.go:42", "foo.go#L42", "foo.go,", "foo.go.", "`foo.go`", "(foo.go)"],
    )
    def test_go_source_operand_positive_matrix(self, pre_route, real_entries, operand: str) -> None:
        result = pre_route.route(f"fix typo in {operand}", entries=real_entries)
        assert result["skill"] == "go-patterns"

    @pytest.mark.parametrize(
        "operand",
        ["foo.go.txt", "changelog.go.md", ".golangci.yml", ".goreleaser.yml", "example.google", "foo.gox"],
    )
    def test_go_source_operand_negative_matrix(self, pre_route, real_entries, operand: str) -> None:
        result = pre_route.route(f"fix typo in {operand}", entries=real_entries)
        assert result["skill"] == "quick"

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("create PR for foo.go", "pr-workflow"),
            ("push foo.go", "pr-workflow"),
            ("security review foo.go", "security-review"),
            ("security audit foo.go", "security-review"),
        ],
    )
    def test_protected_composite_keeps_primary_and_stacks_go(
        self, pre_route, real_entries, query: str, expected: str
    ) -> None:
        result = pre_route.route(query, entries=real_entries)
        assert result["skill"] == expected
        assert result["stack"] == ["go-patterns"]

    @pytest.mark.parametrize("query", ["push back on foo.go", "push against foo.go", "pushback on foo.go"])
    def test_go_operand_push_metaphors_do_not_route_pr(self, pre_route, real_entries, query: str) -> None:
        result = pre_route.route(query, entries=real_entries)
        assert result["skill"] != "pr-workflow"

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
    def test_article_bearing_pr_intent_stays_primary(self, pre_route, real_entries, query: str) -> None:
        result = pre_route.route(query, entries=real_entries)
        assert result["skill"] == "pr-workflow"
        assert result["stack"] == ["go-patterns"]

    @pytest.mark.parametrize(
        "query",
        ["open main.go", "make main.go", "draft main.go", "submit main.go", "raise main.go", "file main.go"],
    )
    def test_bounded_pr_verbs_without_pr_noun_stay_go(self, pre_route, real_entries, query: str) -> None:
        result = pre_route.route(query, entries=real_entries)
        assert result["skill"] == "go-patterns"

    def test_create_pr_matches_pr_workflow(self, pre_route, real_entries) -> None:
        """'create a PR' should match pr-workflow (force-route)."""
        result = pre_route.route("create a PR", entries=real_entries)
        assert result["matched"] is True
        assert result["skill"] == "pr-workflow"
        assert result["match_type"] == "force_route"

    def test_push_changes_matches_pr_workflow(self, pre_route, real_entries) -> None:
        """'push my changes' should match pr-workflow (force-route)."""
        result = pre_route.route("push my changes", entries=real_entries)
        assert result["matched"] is True
        assert result["skill"] == "pr-workflow"
        assert result["match_type"] == "force_route"

    def test_quantum_physics_falls_through(self, pre_route, real_entries) -> None:
        """'tell me about quantum physics' should fall through."""
        result = pre_route.route("tell me about quantum physics", entries=real_entries)
        assert result["matched"] is False
        assert result["match_type"] == "fallthrough"

    def test_quick_fix_matches_quick(self, pre_route, real_entries) -> None:
        """'quick fix the login page' should match quick (force-route)."""
        result = pre_route.route("quick fix the login page", entries=real_entries)
        assert result["matched"] is True
        assert result["skill"] == "quick"
        assert result["match_type"] == "force_route"

    def test_fish_shell_matches_shell_config(self, pre_route, real_entries) -> None:
        """'configure my fish shell' should match shell-config (force-route).

        fish-shell-config folded into shell-config (skill consolidation).
        """
        result = pre_route.route("configure my fish shell", entries=real_entries)
        assert result["matched"] is True
        assert result["skill"] == "shell-config"
        assert result["match_type"] == "force_route"

    def test_review_code_ambiguous_falls_through(self, pre_route, real_entries) -> None:
        """'review this code' hits only non-force triggers -- falls through."""
        result = pre_route.route("review this code", entries=real_entries)
        assert result["matched"] is False
        assert result["confidence"] == "low"

    def test_non_force_triggers_never_match(self, pre_route) -> None:
        """Non-force entries fall through even on many trigger hits.

        Pins the 2026-07 reduction: pre-route is a force-route guard; the
        semantic router owns the long tail (live replay: 2/2 non-force
        keyword matches were misroutes).
        """
        entries = [
            {
                "name": "keyword-skill",
                "type": "skill",
                "triggers": ["alpha", "beta", "gamma", "delta"],
                "agent": None,
                "force_route": False,
            }
        ]
        result = pre_route.route("alpha beta gamma delta", entries=entries)
        assert result["matched"] is False
        assert result["match_type"] == "fallthrough"

    def test_weather_falls_through(self, pre_route, real_entries) -> None:
        """'what's the weather like' should fall through."""
        result = pre_route.route("what's the weather like", entries=real_entries)
        assert result["matched"] is False
        assert result["match_type"] == "fallthrough"


# ---------------------------------------------------------------------------
# Semantic safety tests (false positive prevention)
# ---------------------------------------------------------------------------


class TestSemanticSafety:
    """Test that common English idioms don't trigger false positives."""

    def test_push_back_does_not_match_pr_workflow(self, pre_route, real_entries) -> None:
        """'push back on this design' should NOT match pr-workflow."""
        result = pre_route.route("push back on this design", entries=real_entries)
        if result["matched"]:
            assert result["skill"] != "pr-workflow", f"'push back on this design' falsely matched pr-workflow: {result}"

    def test_fish_for_bugs_does_not_match_fish_config(self, pre_route, real_entries) -> None:
        """'fish for bugs' should NOT match fish-shell-config."""
        result = pre_route.route("fish for bugs", entries=real_entries)
        if result["matched"]:
            assert result["skill"] != "fish-shell-config", (
                f"'fish for bugs' falsely matched fish-shell-config: {result}"
            )

    def test_semantic_guard_works_with_multi_word_triggers(self, pre_route) -> None:
        """Semantic guard must work when multi-word trigger matches with intervening words.

        E.g. trigger 'push changes' matching 'push back on changes' should be guarded
        because 'back' is a guard word for pr-workflow.
        """
        entries = [
            {
                "name": "pr-workflow",
                "type": "skill",
                "triggers": ["push changes"],
                "agent": None,
                "force_route": True,
            }
        ]
        table = pre_route.build_match_table(entries)
        candidates = pre_route.score_matches(table, "push back on changes")
        # "back" is a guard word for pr-workflow, so this should be filtered out
        assert "skill:pr-workflow" not in candidates

    def test_semantic_guard_allows_legitimate_multi_word_match(self, pre_route) -> None:
        """Multi-word trigger without guard words should match normally."""
        entries = [
            {
                "name": "pr-workflow",
                "type": "skill",
                "triggers": ["push changes"],
                "agent": None,
                "force_route": True,
            }
        ]
        table = pre_route.build_match_table(entries)
        candidates = pre_route.score_matches(table, "push my changes now")
        assert "skill:pr-workflow" in candidates


# ---------------------------------------------------------------------------
# Output schema tests
# ---------------------------------------------------------------------------


class TestOutputSchema:
    """Verify the output JSON schema is correct."""

    REQUIRED_KEYS: ClassVar[set[str]] = {"matched", "agent", "skill", "confidence", "match_type", "reasoning"}

    def test_matched_output_has_all_keys(self, pre_route, real_entries) -> None:
        """Matched result contains all required keys."""
        result = pre_route.route("create a PR", entries=real_entries)
        assert set(result.keys()) >= self.REQUIRED_KEYS

    def test_fallthrough_output_has_all_keys(self, pre_route, real_entries) -> None:
        """Fallthrough result contains all required keys."""
        result = pre_route.route("tell me about quantum physics", entries=real_entries)
        assert set(result.keys()) >= self.REQUIRED_KEYS

    def test_confidence_values(self, pre_route, real_entries) -> None:
        """Confidence is one of high/medium/low."""
        for req in ["create a PR", "push my changes", "quantum physics"]:
            result = pre_route.route(req, entries=real_entries)
            assert result["confidence"] in {"high", "medium", "low"}

    def test_match_type_values(self, pre_route, real_entries) -> None:
        """match_type is one of force_route/trigger_keyword/fallthrough."""
        for req in ["create a PR", "review this code", "quantum physics"]:
            result = pre_route.route(req, entries=real_entries)
            assert result["match_type"] in {"force_route", "trigger_keyword", "fallthrough"}


# ---------------------------------------------------------------------------
# Confidence threshold tests
# ---------------------------------------------------------------------------


class TestConfidence:
    """Test confidence determination logic."""

    def test_force_route_high_confidence(self, pre_route) -> None:
        """Force-route with 2+ triggers -> high."""
        from dataclasses import field as _field

        match = pre_route.ScoredMatch(
            name="test",
            entry_type="skill",
            agent=None,
            force_route=True,
            matched_triggers=["a", "b"],
        )
        assert pre_route.determine_confidence(match) == "high"

    def test_force_route_single_trigger_high_confidence(self, pre_route) -> None:
        """Force-route with 1 trigger -> high.

        A force match that reached scoring already passed every semantic
        guard; the /do fast path and Step 1(a) safety override act only on
        "high", so a single surviving force trigger must report it.
        """
        match = pre_route.ScoredMatch(
            name="test",
            entry_type="skill",
            agent=None,
            force_route=True,
            matched_triggers=["a"],
        )
        assert pre_route.determine_confidence(match) == "high"

    def test_non_force_low_confidence(self, pre_route) -> None:
        """Non-force never reports above low (the medium tier is retired)."""
        match = pre_route.ScoredMatch(
            name="test",
            entry_type="skill",
            agent=None,
            force_route=False,
            matched_triggers=["a", "b", "c"],
        )
        assert pre_route.determine_confidence(match) == "low"


# ---------------------------------------------------------------------------
# Unit tests for internal functions
# ---------------------------------------------------------------------------


class TestBuildMatchTable:
    """Test match table construction."""

    def test_builds_from_entries(self, pre_route) -> None:
        """Match table is built from entries with patterns."""
        entries = [
            {
                "name": "test-skill",
                "type": "skill",
                "triggers": ["go test", "run tests"],
                "agent": "golang-general-engineer",
                "force_route": True,
            }
        ]
        table = pre_route.build_match_table(entries)
        assert len(table) == 2
        assert table[0].trigger == "go test"
        assert table[0].force_route is True
        assert table[0].pattern.search("let's run go test now") is not None

    def test_empty_triggers(self, pre_route) -> None:
        """Entry with no triggers produces no match entries."""
        entries = [{"name": "empty", "type": "skill", "triggers": [], "agent": None, "force_route": False}]
        table = pre_route.build_match_table(entries)
        assert len(table) == 0


class TestScoreMatches:
    """Test the force-candidate ranking logic."""

    def test_only_force_entries_reach_candidates(self, pre_route) -> None:
        """Non-force entries are excluded from the match table entirely."""
        entries = [
            {"name": "forced", "type": "skill", "triggers": ["deploy"], "agent": None, "force_route": True},
            {"name": "normal", "type": "skill", "triggers": ["deploy"], "agent": None, "force_route": False},
        ]
        table = pre_route.build_match_table(entries)
        candidates = pre_route.score_matches(table, "deploy now")
        assert "skill:forced" in candidates
        assert "skill:normal" not in candidates

    def test_more_triggers_higher_score(self, pre_route) -> None:
        """Among force entries, more matched triggers = higher rank."""
        entries = [
            {"name": "multi", "type": "skill", "triggers": ["run", "test", "go"], "agent": None, "force_route": True},
            {"name": "single", "type": "skill", "triggers": ["run"], "agent": None, "force_route": True},
        ]
        table = pre_route.build_match_table(entries)
        candidates = pre_route.score_matches(table, "run go test")
        assert candidates["skill:multi"].score > candidates["skill:single"].score

    def test_deterministic_tie_breaking(self, pre_route) -> None:
        """Equal-score candidates are ordered deterministically by name."""
        entries = [
            {"name": "zebra", "type": "skill", "triggers": ["deploy"], "agent": None, "force_route": True},
            {"name": "alpha", "type": "skill", "triggers": ["deploy"], "agent": None, "force_route": True},
        ]
        # Run multiple times to verify determinism
        for _ in range(5):
            result = pre_route.route("deploy now", entries=entries)
            # Both have identical scores; alpha should win deterministically
            assert result["skill"] == "alpha", f"Expected 'alpha' but got {result['skill']}"


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestCLI:
    """Test the script as a subprocess."""

    @pytest.mark.slow
    def test_cli_matched(self) -> None:
        """CLI returns valid JSON for a matched request."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--request", "create a PR"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["matched"] is True
        assert data["skill"] == "pr-workflow"

    @pytest.mark.slow
    def test_cli_fallthrough(self) -> None:
        """CLI returns valid JSON for a fallthrough request."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--request", "what is the meaning of life"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["matched"] is False

    @pytest.mark.slow
    def test_cli_compact_json(self) -> None:
        """--json-compact outputs single-line JSON."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--request", "create a PR", "--json-compact"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 1

    @pytest.mark.slow
    def test_cli_missing_request_fails(self) -> None:
        """Missing --request arg fails."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# Local index merge semantics
# ---------------------------------------------------------------------------


class TestLocalIndexMerge:
    """_load_index_items merges the local override instead of replacing.

    Regression for the stale-local-override bug: _resolve_index replaced the
    tracked index wholesale with INDEX.local.json, hiding newly added skills
    from routing.
    """

    def test_local_overlay_adds_but_never_hides(self, pre_route, tmp_path: Path) -> None:
        tracked = tmp_path / "INDEX.json"
        tracked.write_text(json.dumps({"skills": {"tracked-skill": {"triggers": ["t"]}}}))
        (tmp_path / "INDEX.local.json").write_text(json.dumps({"skills": {"local-skill": {"triggers": ["l"]}}}))
        items = pre_route._load_index_items(tracked, "INDEX.local.json", "skills")
        assert set(items) == {"tracked-skill", "local-skill"}

    def test_stale_local_never_overrides_tracked_content(self, pre_route, tmp_path: Path) -> None:
        """A stale local superset cannot revert tracked entry content (add-only merge)."""
        tracked = tmp_path / "INDEX.json"
        tracked.write_text(json.dumps({"skills": {"skill": {"triggers": ["fresh"]}}}))
        (tmp_path / "INDEX.local.json").write_text(json.dumps({"skills": {"skill": {"triggers": ["stale"]}}}))
        items = pre_route._load_index_items(tracked, "INDEX.local.json", "skills")
        assert items["skill"]["triggers"] == ["fresh"]

    def test_no_local_file_reads_tracked_only(self, pre_route, tmp_path: Path) -> None:
        tracked = tmp_path / "INDEX.json"
        tracked.write_text(json.dumps({"skills": {"tracked-skill": {"triggers": ["t"]}}}))
        items = pre_route._load_index_items(tracked, "INDEX.local.json", "skills")
        assert set(items) == {"tracked-skill"}


# ---------------------------------------------------------------------------
# Pipeline FORCE-route tests (regression: pre-route reads pipelines too)
# ---------------------------------------------------------------------------


class TestPipelineForceRoute:
    """FORCE pipelines get the same deterministic guard as FORCE skills.

    Regression test for the asymmetry where pre-route.py read skills only,
    leaving 4 FORCE pipelines (de-ai-pipeline, pr-pipeline,
    skill-creation-pipeline, voice-writer) with no deterministic idiom guard.
    """

    def test_voice_article_matches_voice_writer_pipeline(self, pre_route, real_entries) -> None:
        """'write an article about kubernetes in my voice' matches voice-writer pipeline."""
        result = pre_route.route("write an article about kubernetes in my voice", entries=real_entries)
        assert result["matched"] is True
        assert result.get("pipeline") == "voice-writer"

    def test_voice_metaphor_guard_suppresses_pipeline(self, pre_route, real_entries) -> None:
        """'remove voice artifacts' must NOT match voice-writer pipeline."""
        result = pre_route.route("remove voice artifacts from this recording", entries=real_entries)
        if result["matched"]:
            assert result.get("pipeline") != "voice-writer"

    def test_de_ai_matches_pipeline(self, pre_route, real_entries) -> None:
        """'de-ai these docs' matches de-ai-pipeline."""
        result = pre_route.route("de-ai these docs", entries=real_entries)
        assert result["matched"] is True
        assert result.get("pipeline") == "de-ai-pipeline"

    def test_skill_creation_pipeline_matches(self, pre_route, real_entries) -> None:
        """'create a new skill formally with gates' matches skill-creation-pipeline."""
        result = pre_route.route("create a new skill formally with gates", entries=real_entries)
        assert result["matched"] is True
        assert result.get("pipeline") == "skill-creation-pipeline"

    @pytest.mark.parametrize(
        "query",
        [
            "send my manuscript for review",
            "send my paper for review",
            "submit my research paper",
            "open the manuscript for review",
        ],
    )
    def test_pr_pipeline_inherits_pr_workflow_guards(self, pre_route, real_entries, query: str) -> None:
        result = pre_route.route(query, entries=real_entries)
        assert result.get("pipeline") != "pr-pipeline", result

    @pytest.mark.parametrize("query", ["send my commits for review", "submit changes", "open PR"])
    def test_pr_pipeline_guard_keeps_real_git_intent(self, pre_route, real_entries, query: str) -> None:
        result = pre_route.route(query, entries=real_entries)
        assert result.get("pipeline") == "pr-pipeline", result

    def test_fallthrough_has_pipeline_none(self, pre_route, real_entries) -> None:
        """Fallthrough results include pipeline: None."""
        result = pre_route.route("tell me about quantum physics", entries=real_entries)
        assert result.get("pipeline") is None

    def test_skill_only_match_has_pipeline_none(self, pre_route, real_entries) -> None:
        """A match on a skill-only force-route (no pipeline counterpart) has pipeline: None."""
        result = pre_route.route("configure my fish shell", entries=real_entries)
        assert result["matched"] is True
        assert result["skill"] == "shell-config"
        assert result.get("pipeline") is None
