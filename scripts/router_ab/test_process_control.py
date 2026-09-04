"""Trusted fake-CLI regression: wrapper timeout must not orphan its child."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import judge
import process_control
import pytest
import runner

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX owned process groups")

FAKE_CLI = """import json, os, signal, subprocess, sys, time
from pathlib import Path
sys.stdin.read()
child_code = "import os, signal, time; " + ("signal.signal(signal.SIGTERM, signal.SIG_IGN); " if os.environ.get("STUBBORN_CHILD") else "") + "time.sleep(60)"
child = subprocess.Popen([sys.executable, '-c', child_code])
Path(os.environ['CHILD_PID_FILE']).write_text(str(child.pid))
def stop(*_):
    child.wait()
    sys.exit(0)
signal.signal(signal.SIGTERM, stop)
print(json.dumps({'type':'thread.started','thread_id':'trusted-fake'}), flush=True)
print('partial stderr retained', file=sys.stderr, flush=True)
while True: time.sleep(0.1)
"""


@pytest.fixture
def fake_cli(tmp_path, monkeypatch):
    executable = tmp_path / "codex"
    executable.write_text(f"#!{sys.executable}\n" + FAKE_CLI)
    executable.chmod(0o755)
    pid_file = tmp_path / "child.pid"
    monkeypatch.setenv("CHILD_PID_FILE", str(pid_file))
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ.get("PATH", ""))
    return executable, pid_file


def running(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    status = Path(f"/proc/{pid}/stat")
    # An orphan zombie holds no executable work; PID 1 reaping is outside the
    # runner's authority. Normal TERM cleanup reaps the child in the wrapper.
    return not status.exists() or status.read_text().split(") ", 1)[1][0] != "Z"


def wait_stopped(pid):
    deadline = time.monotonic() + 2
    while running(pid) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not running(pid)


def kill_child(pid):
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def test_old_timeout_orphans_child_new_timeout_cleans_group(fake_cli):
    executable, pid_file = fake_cli
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            subprocess.run([str(executable)], input="prompt", capture_output=True, text=True, timeout=0.5)
        old_child = int(pid_file.read_text())
        assert running(old_child), "baseline must reproduce the live-child defect"
    finally:
        if pid_file.exists():
            kill_child(int(pid_file.read_text()))
    pid_file.unlink()
    started = time.monotonic()
    try:
        with pytest.raises(subprocess.TimeoutExpired) as failure:
            process_control.run_process([str(executable)], input="prompt", timeout=0.5, cleanup_timeout=0.5)
        assert time.monotonic() - started < 3
        wait_stopped(int(pid_file.read_text()))
        stdout = failure.value.output
        stderr = failure.value.stderr
        assert "trusted-fake" in (stdout.decode() if isinstance(stdout, bytes) else stdout)
        assert "partial stderr retained" in (stderr.decode() if isinstance(stderr, bytes) else stderr)
    finally:
        if pid_file.exists():
            kill_child(int(pid_file.read_text()))


def test_kill_escalation_leaves_unrelated_process_alive(fake_cli, monkeypatch):
    executable, pid_file = fake_cli
    monkeypatch.setenv("STUBBORN_CHILD", "1")
    sibling = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            process_control.run_process([str(executable)], input="prompt", timeout=0.5, cleanup_timeout=0.2)
        wait_stopped(int(pid_file.read_text()))
        assert sibling.poll() is None
    finally:
        if pid_file.exists():
            kill_child(int(pid_file.read_text()))
        sibling.kill()
        sibling.wait(timeout=2)


def test_judge_timeout_preserves_partial_events_and_unknown_usage(fake_cli, tmp_path):
    _, pid_file = fake_cli
    output = tmp_path / "judge"
    output.mkdir()
    args = SimpleNamespace(out=output, calibration=False, timeout=0.5)
    batch = [{"id": "opaque", "request": "test", "response": "test", "rubric": {"checks": [], "critical_failures": []}}]
    try:
        result = judge.run_batch(1, batch, args)
        wait_stopped(int(pid_file.read_text()))
        assert result["valid"] is False and result["error"] == "timeout" and result["usage"] is None
        target = next(output.glob("pass-*"))
        assert "trusted-fake" in (target / "events.jsonl").read_text()
        assert "partial stderr retained" in (target / "stderr.txt").read_text()
        assert json.loads((target / "result.json").read_text()) == result
    finally:
        if pid_file.exists():
            kill_child(int(pid_file.read_text()))


def test_routing_timeout_preserves_partial_events_and_unknown_usage(fake_cli, tmp_path):
    _, pid_file = fake_cli
    snapshot = {str(tmp_path / "policy.txt"): b"policy", str(tmp_path / "task.txt"): b"task"}
    protocol = {"arms": {"baseline": {"instruction_file": "policy.txt"}}, "timeout_seconds": 0.5}
    assignment = {"arm": "baseline", "uid": "one", "case_id": "one", "repeat": 0, "suite": "dev", "position": 0}
    try:
        result = runner.run_one(
            tmp_path, protocol, {"prompt_file": "task.txt"}, assignment, tmp_path / "results", {}, snapshot
        )
        wait_stopped(int(pid_file.read_text()))
        assert result["timed_out"] and not result["success"] and result["usage"] is None
        target = tmp_path / "results/raw/baseline/one"
        assert "trusted-fake" in (target / "stdout.jsonl").read_text()
        assert "partial stderr retained" in (target / "stderr.txt").read_text()
    finally:
        if pid_file.exists():
            kill_child(int(pid_file.read_text()))


def test_normal_process_captures_output():
    result = process_control.run_process(
        [sys.executable, "-c", 'import sys; print(sys.stdin.read()); print("err", file=sys.stderr)'],
        input="normal",
        timeout=2,
    )
    assert result.returncode == 0 and result.stdout == "normal\n" and result.stderr == "err\n"
