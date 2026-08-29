#!/usr/bin/env python3
"""
Tests for the subagent-start-warmstart hook (SubagentStart event).

Run with: python3 -m pytest hooks/tests/test_subagent_start_warmstart.py -v
"""

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent / "subagent-start-warmstart.py"
LIB_PATH = Path(__file__).parent.parent / "lib"

sys.path.insert(0, str(LIB_PATH))
import warmstart_lib

SUBAGENT_START_EVENT = {
    "session_id": "sess-1",
    "transcript_path": "/tmp/transcript.jsonl",
    "cwd": "/tmp",
    "hook_event_name": "SubagentStart",
    "agent_id": "agent-1",
    "agent_type": "Explore",
}


def run_hook(stdin: str) -> tuple[str, str, int]:
    """Run the hook with raw stdin and return (stdout, stderr, exit_code)."""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout, result.stderr, result.returncode


def run_event(event: dict) -> tuple[str, str, int]:
    return run_hook(json.dumps(event))


def _jsonl(paths: list[str], session: str = "sess-1") -> str:
    now = datetime.now(timezone.utc).isoformat()
    return "".join(json.dumps({"ts": now, "session": session, "path": p}) + "\n" for p in paths)


class TestEventContract:
    def test_documented_subagent_start_event_emits_subagent_start_output(self, tmp_path, monkeypatch):
        """hookEventName is SubagentStart so the block lands in the subagent."""
        monkeypatch.chdir(tmp_path)
        stdout, stderr, code = run_event(SUBAGENT_START_EVENT)
        assert code == 0
        output = json.loads(stdout)
        inner = output["hookSpecificOutput"]
        assert inner["hookEventName"] == "SubagentStart"
        assert "[warmstart]" in inner["additionalContext"]

    def test_first_line_names_agent_type(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        stdout, _, code = run_event(SUBAGENT_START_EVENT)
        assert code == 0
        context = json.loads(stdout)["hookSpecificOutput"]["additionalContext"]
        assert context.splitlines()[0] == "[warmstart] Parent session context for Explore:"

    def test_missing_agent_type_falls_back_to_subagent(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        event = {k: v for k, v in SUBAGENT_START_EVENT.items() if k != "agent_type"}
        stdout, _, code = run_event(event)
        assert code == 0
        context = json.loads(stdout)["hookSpecificOutput"]["additionalContext"]
        assert context.splitlines()[0] == "[warmstart] Parent session context for subagent:"

    def test_no_prompt_or_tool_input_needed(self, tmp_path, monkeypatch):
        """The documented SubagentStart stdin carries no prompt; the hook must not need one."""
        monkeypatch.chdir(tmp_path)
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "session-reads.txt").write_text(_jsonl(["/proj/a.py", "/proj/b.py"]))
        stdout, _, code = run_event(SUBAGENT_START_EVENT)
        assert code == 0
        context = json.loads(stdout)["hookSpecificOutput"]["additionalContext"]
        assert "[warmstart] Files seen (2): /proj/a.py, /proj/b.py" in context


class TestNonBlocking:
    def test_empty_stdin_exits_zero(self):
        """`< /dev/null` must exit 0 or the registration bricks every dispatch."""
        stdout, _, code = run_hook("")
        assert code == 0

    def test_malformed_json_exits_zero_with_empty_output(self):
        stdout, _, code = run_hook("{not json")
        assert code == 0
        assert json.loads(stdout)["hookSpecificOutput"]["hookEventName"] == "SubagentStart"

    def test_non_dict_json_exits_zero(self):
        stdout, _, code = run_hook("[1, 2, 3]")
        assert code == 0
        assert json.loads(stdout)["hookSpecificOutput"] == {"hookEventName": "SubagentStart"}


class TestSessionScoping:
    def test_other_session_reads_are_excluded(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "session-reads.txt").write_text(_jsonl(["/old/a.py"], session="sess-OLD"))
        stdout, _, code = run_event(SUBAGENT_START_EVENT)
        assert code == 0
        context = json.loads(stdout)["hookSpecificOutput"]["additionalContext"]
        assert "Files seen (0): none" in context
        assert "/old/a.py" not in context


class TestSharedBuilder:
    def test_gather_context_block_in_process_is_fast(self, tmp_path, monkeypatch):
        """Hook body budget: the on-disk gather stays well under 50 ms."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "task_plan.md").write_text("## Goal\nShip it\n\n## Decisions Made\n- use lib\n")
        start = time.perf_counter()
        block = warmstart_lib.gather_context_block("sess-1", "Explore")
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 50, f"gather took {elapsed_ms:.1f} ms"
        assert block.startswith("[warmstart] Parent session context for Explore:")
        assert "[warmstart] Task: Ship it" in block
        assert "[warmstart] Decisions: use lib" in block

    def test_both_hooks_share_one_builder(self):
        """The superseded PreToolUse hook re-exports the lib builder, not a copy."""
        src = (Path(__file__).parent.parent / "pretool-subagent-warmstart.py").read_text(encoding="utf-8")
        assert "from warmstart_lib import" in src
        assert "def build_context_block" not in src
