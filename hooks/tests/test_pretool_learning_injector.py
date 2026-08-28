#!/usr/bin/env python3
"""
Tests for the pretool-learning-injector hook.

Covers the cross-domain noise fix (ADR: pretool-injector-scoping):
- GENERIC_COMMAND_STOPLIST suppresses bare generic executables as fallback tags
- INJECTABLE_CATEGORIES stays a subset of learning_db_v2's VALID_CATEGORIES
- category filtering keeps error/gotcha/debug hints, drops cross-domain ones
- project_path scoping keeps global + same-project hints, drops other-project ones
- the injector still fires for a matching, in-scope pattern (no silent zero-out)

Run with: python3 -m pytest hooks/tests/test_pretool_learning_injector.py -v
"""

import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Import the modules under test
# ---------------------------------------------------------------------------

_LIB_DIR = Path(__file__).resolve().parent.parent / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

import learning_db_v2 as db

HOOK_PATH = Path(__file__).parent.parent / "pretool-learning-injector.py"

spec = importlib.util.spec_from_file_location("pretool_learning_injector", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Use a fresh temp learning.db for each test."""
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path))
    db._initialized = False
    yield tmp_path
    db._initialized = False


def _record(
    topic: str,
    key: str,
    value: str,
    category: str = "error",
    confidence: float = 0.9,
    tags: list[str] | None = None,
    project_path: str | None = None,
    source: str = "manual",
) -> dict:
    return db.record_learning(
        topic=topic,
        key=key,
        value=value,
        category=category,
        confidence=confidence,
        tags=tags,
        source=source,
        project_path=project_path,
    )


def _make_bash_event(command: str, cwd: str | None = None) -> str:
    event = {"tool_name": "Bash", "tool_input": {"command": command}}
    if cwd:
        event["cwd"] = cwd
    return json.dumps(event)


def _make_edit_event(file_path: str, old_string: str | None = None, cwd: str | None = None) -> str:
    tool_input: dict = {"file_path": file_path}
    if old_string is not None:
        tool_input["old_string"] = old_string
    event = {"tool_name": "Edit", "tool_input": tool_input}
    if cwd:
        event["cwd"] = cwd
    return json.dumps(event)


def _activations() -> list[tuple[str, str, str | None]]:
    """Every recorded activation as (topic, key, session_id)."""
    with db.get_connection() as conn:
        return [
            (r["topic"], r["key"], r["session_id"])
            for r in conn.execute("SELECT topic, key, session_id FROM activations ORDER BY id")
        ]


def _run_main(stdin_payload: str, env: dict | None = None) -> dict | None:
    """Invoke mod.main() in-process. Returns parsed stdout JSON (or None)."""
    base_env = dict(os.environ)
    if env:
        base_env.update(env)

    stdout_capture = io.StringIO()
    with (
        patch.dict(os.environ, base_env, clear=True),
        patch.object(mod, "read_stdin", return_value=stdin_payload),
        patch("sys.stdout", stdout_capture),
    ):
        try:
            mod.main()
        except SystemExit:
            pass

    output = stdout_capture.getvalue().strip()
    if not output:
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return None


def _additional_context(parsed: dict | None) -> str:
    if not parsed:
        return ""
    return parsed.get("hookSpecificOutput", {}).get("additionalContext", "")


# ---------------------------------------------------------------------------
# GENERIC_COMMAND_STOPLIST
# ---------------------------------------------------------------------------


class TestGenericCommandStoplist:
    @pytest.mark.parametrize(
        "command",
        [
            "grep foo bar.py",
            "find . -name '*.py'",
            "ls -la",
            "cat file.txt",
            "cd /tmp",
            "echo hello",
            "test -f file.txt",
            "check something",
            "wc -l file.txt",
            "sed -n '1,5p' file.txt",
            "awk '{print $1}' file.txt",
            "jq '.foo' file.json",
            "diff a.txt b.txt",
            "xargs -n1 echo",
        ],
    )
    def test_stoplisted_bare_command_yields_no_tags(self, command):
        assert mod.extract_bash_tags(command) == []

    def test_stoplist_full_membership(self):
        expected = {
            "grep",
            "find",
            "ls",
            "cat",
            "cd",
            "echo",
            "test",
            "check",
            "wc",
            "pwd",
            "mkdir",
            "touch",
            "head",
            "tail",
            "sort",
            "uniq",
            "true",
            "false",
            "sleep",
            "date",
            "env",
            "export",
            "source",
            "which",
            "type",
            "printf",
            "sed",
            "awk",
            "jq",
            "diff",
            "xargs",
        }
        assert frozenset(expected) == mod.GENERIC_COMMAND_STOPLIST

    def test_destructive_commands_not_stoplisted(self):
        """rm/mv/cp keep their fallback tag -- gotcha warnings on destructive
        commands have real safety value (ADR consultation, Concern 7)."""
        assert "rm" not in mod.GENERIC_COMMAND_STOPLIST
        assert "mv" not in mod.GENERIC_COMMAND_STOPLIST
        assert "cp" not in mod.GENERIC_COMMAND_STOPLIST
        assert mod.extract_bash_tags("rm file.txt") == ["rm"]
        assert mod.extract_bash_tags("mv a.txt b.txt") == ["mv"]
        assert mod.extract_bash_tags("cp a.txt b.txt") == ["cp"]

    def test_non_generic_bare_command_still_tagged(self):
        """A specific/unusual command name is still a useful fallback tag."""
        assert mod.extract_bash_tags("terraform plan") == ["terraform"]

    def test_keyword_pattern_match_unaffected_by_stoplist(self):
        """Commands matched by COMMAND_KEYWORD_PATTERNS never reach the
        fallback, so the stoplist is irrelevant to them."""
        tags = mod.extract_bash_tags("go test ./...")
        assert set(tags) == {"go", "golang"}

    def test_stoplisted_command_empty_tags_short_circuits_main(self):
        """main() exits without querying the DB when tags come back empty."""
        _record("go-patterns", "grep-tip", "Some hint mentioning grep", category="error")
        parsed = _run_main(_make_bash_event("grep foo"))
        assert _additional_context(parsed) == ""


# ---------------------------------------------------------------------------
# INJECTABLE_CATEGORIES sync with learning_db_v2
# ---------------------------------------------------------------------------


class TestInjectableCategoriesSync:
    def test_injectable_categories_is_subset_of_valid_categories(self):
        """A future category rename/removal in the library must fail this
        test instead of silently desyncing the hook's allowlist
        (ADR consultation, Concern 2)."""
        assert set(mod.INJECTABLE_CATEGORIES) <= db.VALID_CATEGORIES

    def test_injectable_categories_matches_spec(self):
        assert mod.INJECTABLE_CATEGORIES == ["error", "gotcha", "debug"]


# ---------------------------------------------------------------------------
# Category exclusion (cross-domain noise)
# ---------------------------------------------------------------------------


class TestCategoryExclusion:
    def test_voice_category_excluded(self):
        _record("mmr-ratings", "canon-check", "Check canon before writing", category="voice")
        # "voice" is not in learning_db_v2.VALID_CATEGORIES at all -- insert directly.
        with db.get_connection() as conn:
            conn.execute("UPDATE learnings SET category = 'voice' WHERE topic = 'mmr-ratings' AND key = 'canon-check'")
            conn.commit()

        parsed = _run_main(_make_bash_event("terraform plan"))
        assert _additional_context(parsed) == ""

    def test_review_design_effectiveness_excluded(self):
        _record("pr-42", "finding", "Reviewer flagged unused import", category="review", tags=["terraform"])
        _record("layout", "decision", "Use grid over flexbox", category="design", tags=["terraform"])
        _record("session", "roi", "Injection was useful this session", category="effectiveness", tags=["terraform"])

        parsed = _run_main(_make_bash_event("terraform plan"))
        assert _additional_context(parsed) == ""

    def test_error_gotcha_debug_pass_through(self):
        _record("terraform", "state-lock", "Plan fails -> release the state lock first", category="error")
        parsed = _run_main(_make_bash_event("terraform plan"))
        assert "state lock" in _additional_context(parsed)

    def test_mixed_categories_only_injectable_ones_surface(self):
        _record("terraform", "state-lock", "Plan fails -> release the state lock first", category="error")
        _record("terraform", "voice-note", "Some unrelated voice content about terraform", category="design")

        parsed = _run_main(_make_bash_event("terraform plan"))
        context = _additional_context(parsed)
        assert "state lock" in context
        assert "voice-note" not in context
        assert "unrelated voice content" not in context


# ---------------------------------------------------------------------------
# exclude_test_sources parity (search_learnings level -- ADR consultation
# Concern 1)
# ---------------------------------------------------------------------------


class TestExcludeTestSources:
    def test_test_source_rows_excluded_by_default(self):
        _record("terraform", "fixture", "Test fixture row", category="error", source="test-fixture")
        results = db.search_learnings("terraform", categories=["error"])
        assert results == []

    def test_test_source_rows_included_when_disabled(self):
        _record("terraform", "fixture", "Test fixture row", category="error", source="test-fixture")
        results = db.search_learnings("terraform", categories=["error"], exclude_test_sources=False)
        assert len(results) == 1

    def test_injector_does_not_surface_test_fixtures(self):
        """End-to-end: a test-source row must not leak through the hook."""
        _record("terraform", "fixture", "Plan fails -> a fixture-only tip", category="error", source="test-fixture")
        parsed = _run_main(_make_bash_event("terraform plan"))
        assert _additional_context(parsed) == ""


# ---------------------------------------------------------------------------
# project_path scoping
# ---------------------------------------------------------------------------


class TestProjectPathScoping:
    def test_global_learning_surfaces_for_any_project(self):
        _record("terraform", "state-lock", "Plan fails -> release the state lock first", category="error")
        parsed = _run_main(_make_bash_event("terraform plan", cwd="/home/user/project-a"))
        assert "state lock" in _additional_context(parsed)

    def test_same_project_learning_surfaces(self):
        _record(
            "terraform",
            "state-lock",
            "Plan fails -> release the state lock first",
            category="error",
            project_path="/home/user/project-a",
        )
        parsed = _run_main(_make_bash_event("terraform plan", cwd="/home/user/project-a"))
        assert "state lock" in _additional_context(parsed)

    def test_other_project_learning_excluded(self):
        _record(
            "terraform",
            "state-lock",
            "Plan fails -> release the state lock first",
            category="error",
            project_path="/home/user/project-b",
        )
        parsed = _run_main(_make_bash_event("terraform plan", cwd="/home/user/project-a"))
        assert _additional_context(parsed) == ""

    def test_cwd_falls_back_to_claude_project_dir(self):
        _record(
            "terraform",
            "state-lock",
            "Plan fails -> release the state lock first",
            category="error",
            project_path="/home/user/project-a",
        )
        parsed = _run_main(
            _make_bash_event("terraform plan"),
            env={"CLAUDE_PROJECT_DIR": "/home/user/project-a"},
        )
        assert "state lock" in _additional_context(parsed)


# ---------------------------------------------------------------------------
# Positive path: the injector still fires post-fix (no silent zero-out --
# ADR consultation, Concern 6)
# ---------------------------------------------------------------------------


class TestInjectorStillFires:
    def test_matching_error_pattern_injects(self):
        _record("go-patterns", "mutex-usage", "Deadlock -> always release the mutex in a defer", category="error")
        parsed = _run_main(_make_bash_event("go test ./..."))
        context = _additional_context(parsed)
        assert context.startswith("[learning-hint]")
        assert "release the mutex" in context

    def test_gotcha_category_injects(self):
        _record(
            "go-patterns",
            "slice-append",
            "Aliasing bug -> don't alias the old slice, append() may reallocate",
            category="gotcha",
        )
        parsed = _run_main(_make_bash_event("go test ./..."))
        assert "reallocate" in _additional_context(parsed)

    def test_debug_category_injects(self):
        _record("go-patterns", "race-flag", "Flaky test -> rerun with -race to confirm", category="debug")
        parsed = _run_main(_make_bash_event("go test ./..."))
        assert "-race" in _additional_context(parsed)

    def test_low_confidence_pattern_does_not_inject(self):
        _record("go-patterns", "low-conf", "Low confidence tip", category="error", confidence=0.4)
        parsed = _run_main(_make_bash_event("go test ./..."))
        assert _additional_context(parsed) == ""


# ---------------------------------------------------------------------------
# Edit branch: registered on matcher "Bash|Edit", previously untested end to end
# ---------------------------------------------------------------------------


class TestExtractEditTags:
    """File path drives the tag set; an old_string adds the Edit-specific tag."""

    @pytest.mark.parametrize(
        ("file_path", "expected"),
        [
            ("cmd/server/main.go", {"go", "golang"}),
            ("src/app.py", {"python"}),
            ("src/App.tsx", {"typescript", "react"}),
            ("src/index.ts", {"typescript"}),
            ("web/app.js", {"javascript"}),
            ("src/lib.rs", {"rust"}),
            ("deploy/Dockerfile", {"docker"}),
            ("k8s/deploy.yaml", {"yaml", "kubernetes"}),
            ("k8s/deploy.yml", {"yaml", "kubernetes"}),
        ],
    )
    def test_file_extension_maps_to_its_domain_tags(self, file_path, expected):
        assert set(mod.extract_edit_tags({"file_path": file_path})) == expected

    def test_unknown_extension_yields_no_tags(self):
        """No domain signal means no query, so the hook stays silent."""
        assert mod.extract_edit_tags({"file_path": "notes/README.md"}) == []

    def test_missing_file_path_yields_no_tags(self):
        assert mod.extract_edit_tags({}) == []

    def test_old_string_adds_the_multiple_matches_tag(self):
        """The Edit tool's multiple_matches failure is the one edit-shaped error."""
        tags = mod.extract_edit_tags({"file_path": "main.go", "old_string": "func main"})
        assert set(tags) == {"go", "golang", "multiple_matches"}

    def test_empty_old_string_does_not_add_the_tag(self):
        assert set(mod.extract_edit_tags({"file_path": "main.go", "old_string": ""})) == {"go", "golang"}


class TestEditBranchEndToEnd:
    """main()'s Edit branch: tags from the path, query, inject, record."""

    def test_edit_on_a_go_file_injects_a_go_hint(self):
        _record("go-patterns", "nil-map", "Assign to nil map -> make() the map first", category="error")
        parsed = _run_main(_make_edit_event("cmd/server/main.go"))
        assert "make() the map first" in _additional_context(parsed)

    def test_edit_on_an_unmapped_file_injects_nothing(self):
        _record("go-patterns", "nil-map", "Assign to nil map -> make() the map first", category="error")
        parsed = _run_main(_make_edit_event("notes/README.md"))
        assert _additional_context(parsed) == ""

    def test_edit_injection_records_an_activation_for_this_session(self):
        """The ROI pipeline's only writer, exercised through a real hook run.

        A KeyError inside record_activations_safe is swallowed, so a broken
        activation path is invisible everywhere except an assertion like this.
        """
        _record("go-patterns", "nil-map", "Assign to nil map -> make() the map first", category="error")
        _run_main(_make_edit_event("cmd/server/main.go"), env={"CLAUDE_SESSION_ID": "sess-edit-1"})
        assert _activations() == [("go-patterns", "nil-map", "sess-edit-1")]

    def test_silent_edit_records_no_activation(self):
        """Nothing injected means nothing activated — no phantom ROI credit."""
        _record("go-patterns", "nil-map", "Assign to nil map -> make() the map first", category="error")
        _run_main(_make_edit_event("notes/README.md"), env={"CLAUDE_SESSION_ID": "sess-edit-2"})
        assert _activations() == []


# ---------------------------------------------------------------------------
# format_hints separator handling
# ---------------------------------------------------------------------------


class TestFormatHintsSeparator:
    """error-learner writes "<error> → <solution>" with a Unicode arrow.

    format_hints must show the solution half. Splitting on the ASCII "->" only
    made it emit the raw captured error text instead -- nginx configs, ssh
    debug output, diff hunks -- for the 762 rows that store the Unicode form.
    """

    def test_unicode_arrow_yields_the_solution_half(self):
        hints = mod.format_hints(
            [{"value": "ls: cannot access '/tmp/x' → create the directory first", "error_type": "missing_file"}]
        )
        assert "create the directory first" in hints
        assert "cannot access" not in hints

    def test_ascii_arrow_yields_the_solution_half(self):
        hints = mod.format_hints(
            [{"value": "Found 3 matches -> pass replace_all=True", "error_type": "multiple_matches"}]
        )
        assert "pass replace_all=True" in hints
        assert "Found 3 matches" not in hints

    def test_multiline_error_finds_the_arrow_on_a_later_line(self):
        """The stored error half is usually multi-line, so the arrow is last."""
        value = (
            "server {\n    listen 80;\n}\nnginx: configuration file test failed \u2192 run nginx -t and fix the block"
        )
        hints = mod.format_hints([{"value": value, "error_type": "unknown"}])
        assert "run nginx -t and fix the block" in hints
        assert "server {" not in hints

    def test_nested_arrows_keep_the_innermost_solution(self):
        """Re-recording nests "<error> -> <previous value>"; the last arrow wins."""
        value = "exit 1 \u2192 timeout on fetch \u2192 retry with a longer --timeout"
        hints = mod.format_hints([{"value": value, "error_type": "timeout"}])
        assert "retry with a longer --timeout" in hints
        assert "exit 1" not in hints

    def test_control_characters_are_stripped_from_the_hint(self):
        hints = mod.format_hints([{"value": "\x07mysqladmin: connect failed", "error_type": "unknown"}])
        assert "\x07" not in hints
        assert "mysqladmin: connect failed" in hints

    def test_identical_summaries_are_emitted_once(self):
        """Distinct rows often share one generic solution; repeating it wastes the budget."""
        results = [
            {"value": "diff --git a/x \u2192 Fix timeout error in Bash", "error_type": "timeout"},
            {"value": "some other capture \u2192 Fix timeout error in Bash", "error_type": "timeout"},
            {"value": "third capture \u2192 Fix unknown error in Bash", "error_type": "unknown"},
        ]
        hints = mod.format_hints(results)
        assert hints.count("Fix timeout error in Bash") == 1
        assert hints.count("Fix unknown error in Bash") == 1

    def test_value_without_a_separator_falls_back_to_the_first_line(self):
        hints = mod.format_hints([{"value": "Prefer rg over grep", "category": "gotcha"}])
        assert "Prefer rg over grep" in hints

    def test_end_to_end_injection_shows_the_solution(self):
        _record(
            "go-patterns",
            "sig-unicode",
            "go test: config.yaml: No such file or directory → copy config.yaml.example first",
        )
        parsed = _run_main(_make_bash_event("go test ./..."))
        context = _additional_context(parsed)
        assert "copy config.yaml.example first" in context
        assert "No such file or directory" not in context
