#!/usr/bin/env python3
"""Tests for the contentless-hint filter shared by both learning injectors.

error-learner.py writes a generic stub solution whenever it cannot classify an
error ("Fix <type> error in <tool>: <snippet>"). Those rows keep their
recurrence signal, but the solution half carries no instruction, so injecting
them spends context for nothing. hint_has_solution() is the shared predicate
that drops them at injection time.

Covers:
- hint_has_solution on a real solution, on a stub built from every
  DEFAULT_FIX_ACTIONS entry, on multi-line and Unicode-arrow values, and on
  empty or malformed input.
- The matcher is derived from DEFAULT_FIX_SOLUTION_TEMPLATE, so renaming the
  template cannot leave a stale regex behind.
- pretool-learning-injector emits nothing when only stubs match, and still
  emits when a real solution sits behind a wall of stubs.
- session-context drops stub-only learnings instead of counting them.
- Both hooks exit 0 on empty and malformed stdin.

Uses a throwaway learning.db via CLAUDE_LEARNING_DIR — never the real DB.

Run with: python3 -m pytest hooks/tests/test_stub_hint_filter.py -v
"""

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "hooks" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import learning_db_v2 as db


def _load(name: str, filename: str):
    path = REPO_ROOT / "hooks" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


injector = _load("pretool_learning_injector", "pretool-learning-injector.py")
session_context = _load("session_context", "session-context.py")

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


def _context(output: str) -> str:
    text = output.strip()
    if not text:
        return ""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return ""
    return parsed.get("hookSpecificOutput", {}).get("additionalContext", "") or ""


def _run_injector(command: str) -> str:
    """Run the injector's main() on a Bash event; return the injected context."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    stdout = io.StringIO()
    with (
        patch.object(injector, "read_stdin", return_value=payload),
        patch("sys.stdout", stdout),
    ):
        try:
            injector.main()
        except SystemExit:
            pass
    return _context(stdout.getvalue())


def _run_session_context() -> str:
    """Run session-context's main() with the dream readers stubbed out."""
    stdout = io.StringIO()
    with (
        patch.object(session_context, "inject_dream_payload", return_value=""),
        patch.object(session_context, "surface_dream_report", return_value=""),
        patch("sys.stdout", stdout),
    ):
        try:
            session_context.main()
        except SystemExit:
            pass
    return _context(stdout.getvalue())


def _run_hook_subprocess(filename: str, stdin_text: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "CLAUDE_LEARNING_DIR": str(tmp_path)}
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "hooks" / filename)],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


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


# ── pretool-learning-injector ─────────────────────────────────────


class TestInjectorDropsStubs:
    def test_stub_only_pool_emits_nothing(self):
        _record("timeout", "sig-1", f"go test timed out {ARROW} {_stub('timeout')}")
        _record("unknown", "sig-2", f"go build failed {ARROW} {_stub('unknown')}")
        assert _run_injector("go test ./...") == ""

    def test_real_solution_still_reaches_the_prompt(self):
        _record("missing_file", "sig-real", f"go test: config.yaml missing {ARROW} copy config.yaml.example first")
        assert "copy config.yaml.example first" in _run_injector("go test ./...")

    def test_real_solution_survives_a_wall_of_stubs(self):
        """Stubs must not crowd the real hint out of the fetch window."""
        for index in range(8):
            _record("unknown", f"stub-{index}", f"go build failed {index} {ARROW} {_stub('unknown')}")
        _record("missing_file", "sig-real", f"go test: config.yaml missing {ARROW} copy config.yaml.example first")
        context = _run_injector("go test ./...")
        assert "copy config.yaml.example first" in context
        assert "Fix unknown error in Bash" not in context

    def test_no_activation_recorded_for_a_dropped_stub(self):
        _record("timeout", "sig-1", f"go test timed out {ARROW} {_stub('timeout')}")
        assert _run_injector("go test ./...") == ""
        with db.get_connection() as conn:
            assert conn.execute("SELECT COUNT(*) FROM activations").fetchone()[0] == 0

    def test_exits_zero_on_empty_stdin(self, tmp_path):
        assert _run_hook_subprocess("pretool-learning-injector.py", "", tmp_path).returncode == 0

    def test_exits_zero_on_malformed_stdin(self, tmp_path):
        assert _run_hook_subprocess("pretool-learning-injector.py", "{not json", tmp_path).returncode == 0


# ── session-context ───────────────────────────────────────────────


class TestSessionContextDropsStubs:
    def test_stub_only_pool_emits_nothing(self):
        for index in range(3):
            _record("unknown", f"stub-{index}", f"boom {index} {ARROW} {_stub('unknown')}")
        assert _run_session_context() == ""

    def test_real_solutions_are_still_counted(self):
        _record("missing_file", "real-1", f"config.yaml missing {ARROW} copy config.yaml.example first")
        for index in range(3):
            _record("unknown", f"stub-{index}", f"boom {index} {ARROW} {_stub('unknown')}")
        context = _run_session_context()
        assert "[learned-context] Loaded 1 high-confidence patterns" in context
        assert "missing_file(1)" in context
        assert "unknown" not in context

    def test_exits_zero_on_empty_stdin(self, tmp_path):
        assert _run_hook_subprocess("session-context.py", "", tmp_path).returncode == 0

    def test_exits_zero_on_malformed_stdin(self, tmp_path):
        assert _run_hook_subprocess("session-context.py", "{not json", tmp_path).returncode == 0
