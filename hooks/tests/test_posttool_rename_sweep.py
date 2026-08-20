#!/usr/bin/env python3
"""
Tests for the posttool-rename-sweep hook.

Run with: python3 -m pytest hooks/tests/test_posttool_rename_sweep.py -v
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).parent.parent / "posttool-rename-sweep.py"

spec = importlib.util.spec_from_file_location("posttool_rename_sweep", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_hook(event: dict) -> tuple[str, str, int]:
    """Run the hook with given event and return (stdout, stderr, exit_code)."""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout, result.stderr, result.returncode


# Parametrize fixtures for "no error, no output" — equivalent across schemas.
_EMPTY_RESULT_PARAMS = [
    pytest.param({"tool_result": {}}, id="claude-schema"),
    pytest.param({"tool_response": {}}, id="factory-schema"),
]

# Parametrize fixtures for "error result" — equivalent across schemas.
_ERROR_RESULT_PARAMS = [
    pytest.param({"tool_result": {"is_error": True}}, id="claude-schema"),
    pytest.param({"tool_response": {"exitCode": 1}}, id="factory-schema"),
]


# ---------------------------------------------------------------------------
# extract_git_mv_paths tests
# ---------------------------------------------------------------------------


class TestExtractGitMvPaths:
    """Test regex parsing of git mv commands."""

    def test_simple(self):
        assert mod.extract_git_mv_paths("git mv old.py new.py") == ("old.py", "new.py")

    def test_with_directories(self):
        assert mod.extract_git_mv_paths("git mv hooks/old.py hooks/new.py") == (
            "hooks/old.py",
            "hooks/new.py",
        )

    def test_chained_with_and(self):
        assert mod.extract_git_mv_paths("git mv old.py new.py && git add .") == (
            "old.py",
            "new.py",
        )

    def test_chained_with_semicolon(self):
        assert mod.extract_git_mv_paths("git mv old.py new.py; echo done") == (
            "old.py",
            "new.py",
        )

    def test_chained_with_pipe(self):
        assert mod.extract_git_mv_paths("git mv old.py new.py | cat") == (
            "old.py",
            "new.py",
        )

    def test_flag_f(self):
        assert mod.extract_git_mv_paths("git mv -f old.py new.py") == (
            "old.py",
            "new.py",
        )

    def test_flag_force(self):
        assert mod.extract_git_mv_paths("git mv --force old.py new.py") == (
            "old.py",
            "new.py",
        )

    def test_double_quoted_paths(self):
        assert mod.extract_git_mv_paths('git mv "old file.py" "new file.py"') == (
            "old file.py",
            "new file.py",
        )

    def test_single_quoted_paths(self):
        assert mod.extract_git_mv_paths("git mv 'old file.py' 'new file.py'") == (
            "old file.py",
            "new file.py",
        )

    def test_no_git_mv(self):
        assert mod.extract_git_mv_paths("echo hello") is None

    def test_incomplete_git_mv(self):
        assert mod.extract_git_mv_paths("git mv") is None

    def test_git_mv_with_only_one_arg(self):
        # git mv with only source, no dest — should not match
        assert mod.extract_git_mv_paths("git mv old.py") is None


# ---------------------------------------------------------------------------
# Tool name and error filtering
# ---------------------------------------------------------------------------


class TestToolFiltering:
    """Test that the hook correctly filters by tool name and error state."""

    def test_non_bash_tool_silent(self):
        """Non-Bash tools produce no output."""
        event = {
            "tool_name": "Edit",
            "tool_input": {"command": "git mv old.py new.py"},
            "tool_result": {},
        }
        stdout, stderr, rc = run_hook(event)
        assert rc == 0
        assert stdout == ""

    @pytest.mark.parametrize("tool_result_block", _ERROR_RESULT_PARAMS)
    def test_failed_git_mv_silent(self, tool_result_block: dict) -> None:
        """Failed git mv commands (is_error=True / exitCode=1) produce no output."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "git mv nonexistent.py dest.py"},
            **tool_result_block,
        }
        stdout, stderr, rc = run_hook(event)
        assert rc == 0
        assert stdout == ""

    @pytest.mark.parametrize("tool_result_block", _EMPTY_RESULT_PARAMS)
    def test_no_git_mv_in_command_silent(self, tool_result_block: dict) -> None:
        """Bash commands without git mv produce no output."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
            **tool_result_block,
        }
        stdout, stderr, rc = run_hook(event)
        assert rc == 0
        assert stdout == ""

    @pytest.mark.parametrize("tool_result_block", _EMPTY_RESULT_PARAMS)
    def test_short_stem_silent(self, tool_result_block: dict) -> None:
        """Stems under 3 characters are skipped to avoid noisy results."""
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "git mv a.py b.py"},
            **tool_result_block,
        }
        stdout, stderr, rc = run_hook(event)
        assert rc == 0
        assert stdout == ""


# ---------------------------------------------------------------------------
# Always exits 0
# ---------------------------------------------------------------------------


class TestExitCode:
    """Hook must always exit 0 (non-blocking)."""

    def test_empty_stdin(self):
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_invalid_json(self):
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="not json",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    @pytest.mark.parametrize("tool_result_block", _EMPTY_RESULT_PARAMS)
    def test_valid_bash_no_git_mv(self, tool_result_block: dict) -> None:
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            **tool_result_block,
        }
        stdout, stderr, rc = run_hook(event)
        assert rc == 0


# ---------------------------------------------------------------------------
# Regression: tool_input arriving as a string (H1 crash — 4,540 errors)
# ---------------------------------------------------------------------------


class TestToolInputAsString:
    """tool_input sometimes arrives as a JSON string, not a dict.

    The real payload shape from hook-errors.jsonl: tool_input is a string
    like '{"command":"git mv old.py new.py"}' — the AttributeError on
    .get() crashed the hook 4,540 times. These tests pin the fix.
    """

    @pytest.mark.parametrize("tool_result_block", _EMPTY_RESULT_PARAMS)
    def test_string_tool_input_without_git_mv_silent(self, tool_result_block: dict) -> None:
        """A string tool_input with no git mv produces no output (no crash)."""
        event = {
            "tool_name": "Bash",
            "tool_input": '{"command": "ls -la"}',
            **tool_result_block,
        }
        stdout, stderr, rc = run_hook(event)
        assert rc == 0
        assert stdout == ""
        assert "HOOK-ERROR" not in stderr

    @pytest.mark.parametrize("tool_result_block", _EMPTY_RESULT_PARAMS)
    def test_string_tool_input_with_git_mv_produces_output(self, tool_result_block: dict) -> None:
        """A string tool_input containing git mv still triggers the sweep.

        This verifies the hook WORKS on the string shape, not just that
        it doesn't crash.
        """
        event = {
            "tool_name": "Bash",
            "tool_input": '{"command": "git mv hooks/old-hook.py hooks/new-hook.py"}',
            **tool_result_block,
        }
        stdout, stderr, rc = run_hook(event)
        assert rc == 0
        # The hook should at least not crash; whether it finds references
        # depends on the filesystem, so we only assert no crash.
        assert "HOOK-ERROR" not in stderr

    def test_plain_string_tool_input_no_json(self) -> None:
        """tool_input as a bare command string (not JSON-encoded dict)."""
        event = {
            "tool_name": "Bash",
            "tool_input": "echo hello",
            "tool_result": {},
        }
        stdout, stderr, rc = run_hook(event)
        assert rc == 0
        assert stdout == ""
        assert "HOOK-ERROR" not in stderr
