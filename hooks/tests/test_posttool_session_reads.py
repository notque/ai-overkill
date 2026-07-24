#!/usr/bin/env python3
"""
Tests for the posttool-session-reads hook (v2 JSONL session-scoped format).

Run with: python3 -m pytest hooks/tests/test_posttool_session_reads.py -v
"""

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).parent.parent / "posttool-session-reads.py"

spec = importlib.util.spec_from_file_location("posttool_session_reads", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SESSION_READS_FILE = mod.SESSION_READS_FILE


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


def read_event(path: str, session: str = "sess-1") -> dict:
    """Build a Read tool event with an explicit session id."""
    return {"tool_name": "Read", "session_id": session, "tool_input": {"file_path": path}}


def load_entries(tmp_path: Path) -> list[dict]:
    """Parse the JSONL session-reads file into a list of entry dicts."""
    reads_file = tmp_path / ".claude" / "session-reads.txt"
    if not reads_file.exists():
        return []
    return [json.loads(line) for line in reads_file.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Tool Name Filtering
# ---------------------------------------------------------------------------


class TestToolNameFiltering:
    """Only Read tool events should be processed."""

    def test_nonread_tool_exits_zero(self, tmp_path, monkeypatch):
        """Non-Read tool filtering is now handled by matcher 'Read' in settings.json.

        When called directly (without matcher), the hook processes any tool_name.
        This test verifies the hook still exits 0 (non-blocking) for any input.
        """
        monkeypatch.chdir(tmp_path)
        for tool in ("Write", "Edit", "Bash"):
            event = {
                "tool_name": tool,
                "tool_input": {"file_path": "/some/file.py"} if tool != "Bash" else {"command": "ls"},
            }
            stdout, stderr, code = run_hook(event)
            assert code == 0

    def test_ignores_bash_tool(self, tmp_path, monkeypatch):
        """Bash tool events should be ignored (no file_path to extract)."""
        monkeypatch.chdir(tmp_path)
        stdout, stderr, code = run_hook({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        assert code == 0

    def test_ignores_agent_tool(self, tmp_path, monkeypatch):
        """Agent tool events should be ignored."""
        monkeypatch.chdir(tmp_path)
        stdout, stderr, code = run_hook({"tool_name": "Agent", "tool_input": {"prompt": "do something"}})
        assert code == 0


# ---------------------------------------------------------------------------
# File Path Extraction and Tracking
# ---------------------------------------------------------------------------


class TestFilePathTracking:
    """Verify file paths are correctly extracted and written as JSONL."""

    def test_tracks_read_file_path(self, tmp_path, monkeypatch):
        """Read tool event appends a {ts, session, path} entry."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".claude").mkdir()

        stdout, stderr, code = run_hook(read_event("/home/user/project/main.py"))

        assert code == 0
        entries = load_entries(tmp_path)
        assert len(entries) == 1
        assert entries[0]["path"] == "/home/user/project/main.py"
        assert entries[0]["session"] == "sess-1"
        assert datetime.fromisoformat(entries[0]["ts"]).tzinfo is not None

    def test_tracks_multiple_reads(self, tmp_path, monkeypatch):
        """Multiple Read events should all be tracked."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".claude").mkdir()

        paths = ["/a/file1.py", "/b/file2.go", "/c/file3.rs"]
        for p in paths:
            run_hook(read_event(p))

        entries = load_entries(tmp_path)
        assert [e["path"] for e in entries] == paths

    def test_missing_file_path_does_nothing(self, tmp_path, monkeypatch):
        """Read event with no file_path in tool_input should be no-op."""
        monkeypatch.chdir(tmp_path)
        stdout, stderr, code = run_hook({"tool_name": "Read", "tool_input": {}})
        assert code == 0
        assert load_entries(tmp_path) == []

    def test_empty_file_path_does_nothing(self, tmp_path, monkeypatch):
        """Read event with empty file_path should be no-op."""
        monkeypatch.chdir(tmp_path)
        stdout, stderr, code = run_hook({"tool_name": "Read", "tool_input": {"file_path": ""}})
        assert code == 0
        assert load_entries(tmp_path) == []


# ---------------------------------------------------------------------------
# Sensitive Path Filtering
# ---------------------------------------------------------------------------


class TestSensitivePathFiltering:
    """Credential-shaped paths must never be recorded."""

    def test_ssh_paths_never_recorded(self, tmp_path, monkeypatch):
        """A .ssh public-key path is dropped (observed live: deploy key path
        was recorded and later injected into subagent prompts)."""
        monkeypatch.chdir(tmp_path)
        run_hook(read_event("/home/user/.ssh/deploy_ed25519.pub"))
        assert load_entries(tmp_path) == []

    def test_env_and_key_files_never_recorded(self, tmp_path, monkeypatch):
        """Env files and private keys are dropped; normal files kept."""
        monkeypatch.chdir(tmp_path)
        for p in ("/app/.env", "/app/.env.production", "/certs/server.pem", "/home/u/.aws/credentials"):
            run_hook(read_event(p))
        run_hook(read_event("/app/main.py"))
        assert [e["path"] for e in load_entries(tmp_path)] == ["/app/main.py"]


# ---------------------------------------------------------------------------
# Session Scoping and Pruning
# ---------------------------------------------------------------------------


class TestSessionScopingAndPruning:
    """Entries carry session ids; stale and legacy lines are pruned on write."""

    def test_records_distinct_sessions(self, tmp_path, monkeypatch):
        """Two sessions writing the same path both keep their entries."""
        monkeypatch.chdir(tmp_path)
        run_hook(read_event("/a.py", session="sess-1"))
        run_hook(read_event("/a.py", session="sess-2"))
        entries = load_entries(tmp_path)
        assert {(e["session"], e["path"]) for e in entries} == {("sess-1", "/a.py"), ("sess-2", "/a.py")}

    def test_legacy_plain_lines_are_pruned(self, tmp_path, monkeypatch):
        """v1 plain-path lines (no session id) are dropped on the next write."""
        monkeypatch.chdir(tmp_path)
        reads_dir = tmp_path / ".claude"
        reads_dir.mkdir()
        (reads_dir / "session-reads.txt").write_text("/old/v1/path.py\n/another/v1.go\n")

        run_hook(read_event("/new.py"))

        entries = load_entries(tmp_path)
        assert [e["path"] for e in entries] == ["/new.py"]

    def test_entries_past_retention_are_pruned(self, tmp_path, monkeypatch):
        """Entries older than RETENTION_DAYS are dropped on write."""
        monkeypatch.chdir(tmp_path)
        reads_dir = tmp_path / ".claude"
        reads_dir.mkdir()
        old_ts = (datetime.now(timezone.utc) - timedelta(days=mod.RETENTION_DAYS + 1)).isoformat()
        fresh_ts = datetime.now(timezone.utc).isoformat()
        (reads_dir / "session-reads.txt").write_text(
            json.dumps({"ts": old_ts, "session": "sess-0", "path": "/stale.py"})
            + "\n"
            + json.dumps({"ts": fresh_ts, "session": "sess-0", "path": "/fresh.py"})
            + "\n"
        )

        run_hook(read_event("/new.py", session="sess-1"))

        paths = [e["path"] for e in load_entries(tmp_path)]
        assert "/stale.py" not in paths
        assert paths == ["/fresh.py", "/new.py"]


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class TestDeduplication:
    """Same (session, path) pair should not appear twice."""

    def test_duplicate_path_not_appended(self, tmp_path, monkeypatch):
        """Reading the same file twice in one session produces one entry."""
        monkeypatch.chdir(tmp_path)
        run_hook(read_event("/home/user/main.py"))
        run_hook(read_event("/home/user/main.py"))
        entries = load_entries(tmp_path)
        assert [e["path"] for e in entries] == ["/home/user/main.py"]

    def test_different_paths_both_tracked(self, tmp_path, monkeypatch):
        """Different paths should both be recorded."""
        monkeypatch.chdir(tmp_path)
        for p in ["/a.py", "/b.py"]:
            run_hook(read_event(p))
        assert len(load_entries(tmp_path)) == 2


# ---------------------------------------------------------------------------
# Output Format
# ---------------------------------------------------------------------------


class TestOutputFormat:
    """Hook should produce silent output (empty JSON)."""

    def test_silent_output_on_read_event(self, tmp_path, monkeypatch):
        """Read event should produce hook JSON output with no context."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".claude").mkdir()

        stdout, stderr, code = run_hook(read_event("/some/file.py"))

        assert code == 0
        if stdout.strip():
            output = json.loads(stdout)
            hook_output = output.get("hookSpecificOutput", {})
            assert hook_output.get("hookEventName") == "PostToolUse"
            # No additionalContext should be present
            assert "additionalContext" not in hook_output


# ---------------------------------------------------------------------------
# Non-Blocking Guarantee
# ---------------------------------------------------------------------------


class TestNonBlocking:
    """Hook must always exit 0 regardless of errors."""

    def test_exits_zero_on_malformed_json(self):
        """Malformed JSON input should still exit 0."""
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="not valid json{{{",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_exits_zero_on_empty_input(self):
        """Empty stdin should still exit 0."""
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_exits_zero_on_missing_tool_input(self):
        """Event with no tool_input should still exit 0."""
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=json.dumps({"tool_name": "Read"}),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_creates_claude_dir_if_missing(self, tmp_path, monkeypatch):
        """Hook should create .claude/ directory if it doesn't exist."""
        monkeypatch.chdir(tmp_path)
        stdout, stderr, code = run_hook(read_event("/some/file.py"))
        assert code == 0
        assert (tmp_path / ".claude" / "session-reads.txt").exists()
