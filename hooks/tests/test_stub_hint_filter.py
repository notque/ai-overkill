#!/usr/bin/env python3
"""Tests for the contentless-hint filter in learning_db_v2.

The retired error-learner wrote a generic stub solution whenever it could not
classify an error ("Fix <type> error in <tool>: <snippet>"). Those rows are
still in the database: the solution half carries no instruction, so any reader
that summarizes rows must drop them. hint_has_solution() is that predicate.

The learning loop that consumed it is retired; the predicate stays because the
stub rows it recognizes are still stored.

Covers:
- hint_has_solution on a real solution, on a stub built from every
  DEFAULT_FIX_ACTIONS entry, on multi-line and Unicode-arrow values, and on
  empty or malformed input.
- The matcher is derived from DEFAULT_FIX_SOLUTION_TEMPLATE, so renaming the
  template cannot leave a stale regex behind.

Uses a throwaway learning.db via CLAUDE_LEARNING_DIR — never the real DB.

Run with: python3 -m pytest hooks/tests/test_stub_hint_filter.py -v
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "hooks" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import learning_db_v2 as db

ARROW = "→"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point every test at a throwaway learning.db."""
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path))
    db._initialized = False
    yield tmp_path
    db._initialized = False


def _record(topic: str, key: str, value: str, category: str = "error") -> None:
    db.record_learning(
        topic=topic,
        key=key,
        value=value,
        category=category,
        confidence=0.9,
        source="manual",
        project_path=None,
    )


def _stub(error_type: str, tool: str = "Bash", snippet: str = "exit status 1") -> str:
    return db.DEFAULT_FIX_SOLUTION_TEMPLATE.format(error_type=error_type, tool_name=tool, error=snippet)


# ── hint_has_solution ─────────────────────────────────────────────


class TestHintHasSolution:
    def test_real_solution_is_kept(self):
        value = f"config.yaml: No such file or directory {ARROW} copy config.yaml.example first"
        assert db.hint_has_solution(value) is True

    @pytest.mark.parametrize("error_type", sorted(db.DEFAULT_FIX_ACTIONS) + ["unknown"])
    def test_stub_for_every_fix_action_is_dropped(self, error_type):
        value = f"boom {ARROW} {_stub(error_type)}"
        assert db.hint_has_solution(value) is False

    def test_bare_stub_without_a_snippet_is_dropped(self):
        """Rows written before the snippet was appended end at the tool name."""
        assert db.hint_has_solution(f"boom {ARROW} Fix timeout error in Bash") is False

    def test_stub_with_an_empty_snippet_is_dropped(self):
        assert db.hint_has_solution(f"boom {ARROW} {_stub('unknown', snippet='')}") is False

    def test_multiline_error_half_does_not_hide_the_stub(self):
        value = f"server {{\n    listen 80;\n}}\nnginx: test failed {ARROW} {_stub('unknown', snippet='nginx: t')}"
        assert db.hint_has_solution(value) is False

    def test_multiline_error_half_keeps_a_real_solution(self):
        value = f"server {{\n    listen 80;\n}}\nnginx: test failed {ARROW} run nginx -t and fix the block"
        assert db.hint_has_solution(value) is True

    def test_ascii_arrow_value_is_read_the_same_way(self):
        assert db.hint_has_solution("Found 3 matches -> pass replace_all=True") is True
        assert db.hint_has_solution("Found 3 matches -> Fix multiple_matches error in Edit") is False

    def test_nested_arrows_read_the_last_solution(self):
        assert db.hint_has_solution(f"exit 1 {ARROW} timeout {ARROW} Fix timeout error in Bash") is False
        assert db.hint_has_solution(f"exit 1 {ARROW} timeout {ARROW} retry with --timeout 300") is True

    @pytest.mark.parametrize("value", ["", "   ", f"boom {ARROW} ", f"boom {ARROW}   \n\n", None, 42])
    def test_empty_or_malformed_values_carry_no_solution(self, value):
        assert db.hint_has_solution(value) is False

    def test_prose_gotcha_without_an_arrow_is_kept(self):
        assert db.hint_has_solution("Prefer rg over grep; grep misses .gitignored paths") is True

    def test_matcher_tracks_the_template(self):
        """The matcher is built from the template, so a rename cannot strand it."""
        rebuilt = db._build_stub_solution_pattern("Repair {error_type} fault in {tool_name}: {error}")
        assert rebuilt.match("Repair timeout fault in Bash: exit 1")
        assert not rebuilt.match("Fix timeout error in Bash: exit 1")
