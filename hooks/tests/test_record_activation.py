#!/usr/bin/env python3
"""Tests for the record-activation PostToolUse hook.

Run with: python3 -m pytest hooks/tests/test_record_activation.py -v
"""

import importlib.util
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HOOK_PATH = Path(__file__).parent.parent / "record-activation.py"

spec = importlib.util.spec_from_file_location("record_activation", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)

# Prevent sys.exit from killing the test runner
with patch("sys.exit"):
    spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Provide a unique session ID and patch /tmp paths to use tmp_path."""
    session_id = "test-activation-session-001"
    monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)

    # Patch Path so /tmp marker/counter files go to tmp_path
    original_truediv = Path.__truediv__

    def patched_truediv(self: Path, other: str) -> Path:
        if str(self) == "/tmp" and "claude-" in str(other):
            return tmp_path / other
        return original_truediv(self, other)

    monkeypatch.setattr(Path, "__truediv__", patched_truediv)
    return session_id


def _make_hook_input(
    tool_name: str = "Bash",
    is_error: bool = False,
    output: str = "ok",
    schema: str = "claude",
) -> str:
    """Build JSON hook input string.

    Args:
        tool_name: The tool that was called.
        is_error: Whether the tool reported an error.
        output: The tool output text.
        schema: ``"claude"`` for Claude/Codex schema (tool_result/is_error/output)
            or ``"factory"`` for Factory schema (tool_response/exitCode/stdout).
    """
    if schema == "factory":
        return json.dumps(
            {
                "tool_name": tool_name,
                "tool_response": {"stdout": output, "exitCode": 1 if is_error else 0},
            }
        )
    return json.dumps({"tool_name": tool_name, "tool_result": {"output": output, "is_error": is_error}})


def _prime_counter(tmp_path: Path, session_id: str, value: int) -> Path:
    """Set the batch counter so the next hook call is the 10th (gate open)."""
    counter = tmp_path / f"claude-activation-counter-{session_id}"
    counter.write_text(str(value))
    return counter


def _increment_in_parallel(counter: Path, workers: int, per_worker: int) -> None:
    """Fork `workers` children that each call next_count `per_worker` times."""
    pids = []
    for _ in range(workers):
        pid = os.fork()
        if pid == 0:
            try:
                for _ in range(per_worker):
                    mod.next_count(counter)
            finally:
                os._exit(0)
        pids.append(pid)
    for pid in pids:
        assert os.waitpid(pid, 0)[1] == 0, "a forked worker exited non-zero"


# Schema parameter used by tests that exercise tool-result data.
_SCHEMAS = [
    pytest.param("claude", id="claude-schema"),
    pytest.param("factory", id="factory-schema"),
]


# ---------------------------------------------------------------------------
# Tests: Tool filtering
# ---------------------------------------------------------------------------


class TestToolFiltering:
    """Where the Edit/Write/Bash restriction actually lives.

    main() never reads tool_name. The previous tests here asserted a filter the
    hook does not implement, and passed only because a fresh tmp_path leaves the
    counter at 1, so `1 % 10 != 0` returned before subprocess.run was reached.
    Each test below primes the counter to 9 so the batch gate is open and the
    assertion measures the behavior it names.
    """

    def test_settings_matcher_is_what_restricts_the_tools(self) -> None:
        """The delegation the hook comment claims is real and still configured."""
        settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text())
        matchers = {
            entry.get("matcher")
            for entry in settings["hooks"]["PostToolUse"]
            if any("record-activation.py" in hook.get("command", "") for hook in entry.get("hooks", []))
        }
        assert matchers == {"Edit|Write|Bash"}

    @pytest.mark.parametrize("schema", _SCHEMAS)
    def test_tool_name_is_not_filtered_in_process(self, tmp_session: str, tmp_path: Path, schema: str) -> None:
        """With the batch gate open, a non-matching tool name still records.

        Re-adding an in-hook tool filter would silence the settings matcher's
        own tools on any harness that spells them differently. This test fails
        if someone adds one.
        """
        _prime_counter(tmp_path, tmp_session, 9)
        with patch("subprocess.run") as mock_run, patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_hook_input(tool_name="Read", schema=schema)
            mod.main()
            mock_run.assert_called_once()

    @pytest.mark.parametrize("schema", _SCHEMAS)
    def test_error_result_returns_before_touching_the_counter(
        self, tmp_session: str, tmp_path: Path, schema: str
    ) -> None:
        """A failed tool records nothing and does not consume a batch slot."""
        counter = _prime_counter(tmp_path, tmp_session, 9)
        with patch("subprocess.run") as mock_run, patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_hook_input(is_error=True, schema=schema)
            mod.main()
            mock_run.assert_not_called()
        assert counter.read_text() == "9"


class TestCounterAtomicity:
    """The batch counter survives concurrent hooks."""

    def test_parallel_hooks_do_not_lose_increments(self, tmp_path: Path) -> None:
        """Eight parallel workers produce 200 increments, not fewer.

        The unguarded read-modify-write this replaces truncated the file before
        writing, so concurrent hooks read it empty and reset the counter to 1.
        Against that version this test reports 1.
        """
        counter = tmp_path / "counter"
        _increment_in_parallel(counter, workers=8, per_worker=25)
        assert counter.read_text() == "200"

    def test_corrupt_counter_restarts_at_one(self, tmp_path: Path) -> None:
        """Unparseable content is treated as zero, not as a crash."""
        counter = tmp_path / "counter"
        counter.write_text("not a number")
        assert mod.next_count(counter) == 1

    def test_counter_increments_from_the_stored_value(self, tmp_path: Path) -> None:
        """The new value is stored, not just returned."""
        counter = tmp_path / "counter"
        counter.write_text("41")
        assert mod.next_count(counter) == 42
        assert counter.read_text() == "42"


# ---------------------------------------------------------------------------
# Tests: Batching
# ---------------------------------------------------------------------------


class TestBatching:
    """Verify only every 10th successful call triggers recording."""

    @pytest.mark.parametrize("schema", _SCHEMAS)
    def test_no_record_before_10th_call(self, tmp_session: str, tmp_path: Path, schema: str) -> None:
        """Calls 1-9 should not trigger subprocess."""
        for i in range(1, 10):
            with patch("subprocess.run") as mock_run, patch("sys.stdin") as mock_stdin, patch("sys.exit"):
                mock_stdin.read.return_value = _make_hook_input(schema=schema)
                mod.main()
                if i < 10:
                    mock_run.assert_not_called()

    @pytest.mark.parametrize("schema", _SCHEMAS)
    def test_records_on_10th_call(self, tmp_session: str, tmp_path: Path, schema: str) -> None:
        """The 10th call should trigger a record-session subprocess."""
        # Set counter to 9 so next call is the 10th
        counter_file = tmp_path / f"claude-activation-counter-{tmp_session}"
        counter_file.write_text("9")

        with patch("subprocess.run") as mock_run, patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_hook_input(schema=schema)
            mod.main()
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert "record-session" in cmd


# ---------------------------------------------------------------------------
# Tests: Retro knowledge detection
# ---------------------------------------------------------------------------


class TestRetroDetection:
    """Verify --had-retro flag is passed only when marker exists."""

    @pytest.mark.parametrize("schema", _SCHEMAS)
    def test_had_retro_flag_when_marker_exists(self, tmp_session: str, tmp_path: Path, schema: str) -> None:
        # Set counter to 9 and create retro marker
        counter_file = tmp_path / f"claude-activation-counter-{tmp_session}"
        counter_file.write_text("9")
        marker = tmp_path / f"claude-retro-active-{tmp_session}"
        marker.write_text("1")

        with patch("subprocess.run") as mock_run, patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_hook_input(schema=schema)
            mod.main()
            cmd = mock_run.call_args[0][0]
            assert "--had-retro" in cmd

    @pytest.mark.parametrize("schema", _SCHEMAS)
    def test_no_retro_flag_without_marker(self, tmp_session: str, tmp_path: Path, schema: str) -> None:
        counter_file = tmp_path / f"claude-activation-counter-{tmp_session}"
        counter_file.write_text("9")

        with patch("subprocess.run") as mock_run, patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_hook_input(schema=schema)
            mod.main()
            cmd = mock_run.call_args[0][0]
            assert "--had-retro" not in cmd


# ---------------------------------------------------------------------------
# Tests: Error resilience
# ---------------------------------------------------------------------------


class TestErrorResilience:
    """Verify hook never blocks on errors."""

    def test_invalid_json_exits_cleanly(self) -> None:
        with patch("sys.stdin") as mock_stdin, patch("sys.exit") as mock_exit:
            mock_stdin.read.return_value = "not json"
            mod.main()
            mock_exit.assert_called_with(0)

    @pytest.mark.parametrize("schema", _SCHEMAS)
    def test_subprocess_timeout_exits_cleanly(self, tmp_session: str, tmp_path: Path, schema: str) -> None:
        counter_file = tmp_path / f"claude-activation-counter-{tmp_session}"
        counter_file.write_text("9")

        with (
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="test", timeout=5)),
            patch("sys.stdin") as mock_stdin,
            patch("sys.exit") as mock_exit,
        ):
            mock_stdin.read.return_value = _make_hook_input(schema=schema)
            mod.main()
            mock_exit.assert_called_with(0)

    @pytest.mark.parametrize("schema", _SCHEMAS)
    def test_missing_script_exits_cleanly(self, tmp_session: str, tmp_path: Path, schema: str) -> None:
        counter_file = tmp_path / f"claude-activation-counter-{tmp_session}"
        counter_file.write_text("9")

        with (
            patch.object(Path, "exists", return_value=False),
            patch("subprocess.run") as mock_run,
            patch("sys.stdin") as mock_stdin,
            patch("sys.exit"),
        ):
            mock_stdin.read.return_value = _make_hook_input(schema=schema)
            mod.main()
            mock_run.assert_not_called()
