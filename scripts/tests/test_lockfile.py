"""Tests for lockfile.py.

Tests lock acquisition, release, staleness detection, and status reporting.
All tests use temporary directories to avoid interference with real locks.
"""

from __future__ import annotations

import fcntl
import importlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the module under test
sys_path_entry = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, sys_path_entry)
lockfile = importlib.import_module("lockfile")
sys.path.pop(0)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def lock_dir(tmp_path: Path) -> Path:
    """Override LOCK_DIR to use a temp directory."""
    with patch.object(lockfile, "LOCK_DIR", tmp_path):
        yield tmp_path


@pytest.fixture()
def lock_name() -> str:
    return "test-lock"


def _ns(**kwargs: object) -> object:
    """Build a minimal namespace for command functions."""
    import argparse

    return argparse.Namespace(**kwargs)


# ---------------------------------------------------------------------------
# _lock_path
# ---------------------------------------------------------------------------


def test_lock_path_format(lock_dir: Path) -> None:
    path = lockfile._lock_path("learning-db")
    assert path == lock_dir / "claude-toolkit-learning-db.lock"


# ---------------------------------------------------------------------------
# _is_pid_alive
# ---------------------------------------------------------------------------


def test_pid_alive_self() -> None:
    assert lockfile._is_pid_alive(os.getpid()) is True


def test_pid_alive_dead() -> None:
    # PID 0 sends signal to process group — use a very high PID unlikely to exist
    assert lockfile._is_pid_alive(4_000_000) is False


# ---------------------------------------------------------------------------
# _write_lock / _read_lock
# ---------------------------------------------------------------------------


def test_write_and_read_lock(lock_dir: Path) -> None:
    path = lock_dir / "test.lock"
    assert lockfile._write_lock(path) is True

    data = lockfile._read_lock(path)
    assert data is not None
    assert data["pid"] == os.getpid()
    assert "timestamp" in data


def test_write_lock_exclusive(lock_dir: Path) -> None:
    """Second write to the same path must fail (O_EXCL)."""
    path = lock_dir / "test.lock"
    assert lockfile._write_lock(path) is True
    assert lockfile._write_lock(path) is False


def test_read_lock_missing(lock_dir: Path) -> None:
    path = lock_dir / "nonexistent.lock"
    assert lockfile._read_lock(path) is None


def test_read_lock_corrupt(lock_dir: Path) -> None:
    path = lock_dir / "corrupt.lock"
    path.write_text("not json at all")
    assert lockfile._read_lock(path) is None


def test_read_lock_missing_fields(lock_dir: Path) -> None:
    path = lock_dir / "incomplete.lock"
    path.write_text(json.dumps({"pid": 1234}))  # missing timestamp
    assert lockfile._read_lock(path) is None


# ---------------------------------------------------------------------------
# Staleness detection
# ---------------------------------------------------------------------------


def test_stale_dead_pid(lock_dir: Path) -> None:
    data = {"pid": 4_000_000, "timestamp": "2099-01-01T00:00:00+00:00"}
    assert lockfile._is_stale(data) is True


def test_stale_old_timestamp(lock_dir: Path) -> None:
    data = {"pid": os.getpid(), "timestamp": "2020-01-01T00:00:00+00:00"}
    assert lockfile._is_stale(data) is True


def test_not_stale_current_process() -> None:
    from datetime import datetime, timezone

    data = {"pid": os.getpid(), "timestamp": datetime.now(timezone.utc).isoformat()}
    assert lockfile._is_stale(data) is False


def test_stale_unparseable_timestamp() -> None:
    data = {"pid": os.getpid(), "timestamp": "not-a-date"}
    # Unparseable timestamp → infinite age → stale
    assert lockfile._is_stale(data) is True


# ---------------------------------------------------------------------------
# _steal_lock -- concurrent-steal race (regression for unlink-then-write bug)
# ---------------------------------------------------------------------------


def test_steal_does_not_clobber_fresh_lock(lock_dir: Path) -> None:
    """Regression: a stealer must never remove a lock that is no longer stale.

    Sequence being simulated: A and B both read a stale lock and both decide
    to steal. A steals first and writes a fresh lock. B's steal, decided on
    stale data, must then fail -- the old unlink-then-write implementation
    deleted A's fresh lock and both processes believed they held the mutex.
    """
    path = lock_dir / "claude-toolkit-race.lock"
    # "A" is a live process distinct from the test process.
    proc = subprocess.Popen(["sleep", "30"])
    try:
        fresh = {"pid": proc.pid, "timestamp": datetime.now(timezone.utc).isoformat()}
        path.write_text(json.dumps(fresh))

        # "B" executes its steal after A's fresh lock is in place.
        assert lockfile._steal_lock(path) is False

        data = lockfile._read_lock(path)
        assert data is not None
        assert data["pid"] == proc.pid, "fresh lock was clobbered by a late stealer"
    finally:
        proc.kill()
        proc.wait()


def test_steal_succeeds_on_stale_lock(lock_dir: Path) -> None:
    path = lock_dir / "claude-toolkit-stale.lock"
    path.write_text(json.dumps({"pid": 4_000_000, "timestamp": "2020-01-01T00:00:00+00:00"}))

    assert lockfile._steal_lock(path) is True
    data = lockfile._read_lock(path)
    assert data is not None
    assert data["pid"] == os.getpid()


def test_steal_succeeds_on_missing_lock(lock_dir: Path) -> None:
    path = lock_dir / "claude-toolkit-gone.lock"
    assert lockfile._steal_lock(path) is True
    assert lockfile._read_lock(path)["pid"] == os.getpid()


def test_steal_blocked_while_another_stealer_holds_mutex(lock_dir: Path) -> None:
    """While another process holds the steal mutex, our steal must back off."""
    path = lock_dir / "claude-toolkit-mutexed.lock"
    path.write_text(json.dumps({"pid": 4_000_000, "timestamp": "2020-01-01T00:00:00+00:00"}))
    mutex = lockfile._steal_mutex_path(path)

    fd = os.open(str(mutex), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        # Simulate contention within this process: flock is per-open-file, so a
        # second open in a child process would block. Here we spawn a child to
        # attempt the steal while we hold the mutex.
        driver = (
            "import sys, pathlib, importlib\n"
            "scripts_dir, lock_path = sys.argv[1], sys.argv[2]\n"
            "sys.path.insert(0, scripts_dir)\n"
            "lockfile = importlib.import_module('lockfile')\n"
            "ok = lockfile._steal_lock(pathlib.Path(lock_path))\n"
            "sys.exit(0 if not ok else 1)\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", driver, str(Path(lockfile.__file__).parent), str(path)], timeout=30
        )
        assert result.returncode == 0, "child stole the lock despite held steal mutex"
        # Lock content untouched.
        assert lockfile._read_lock(path)["pid"] == 4_000_000
    finally:
        os.close(fd)


def test_concurrent_acquire_mutual_exclusion(lock_dir: Path) -> None:
    """N processes race to acquire (starting from a stale lock); critical
    sections must never overlap and every process must get a turn."""
    name = "race-stress"
    path = lockfile._lock_path(name)
    path.write_text(json.dumps({"pid": 4_000_000, "timestamp": "2020-01-01T00:00:00+00:00"}))
    log = lock_dir / "critical.log"
    log.touch()

    driver = (
        "import sys, os, time, pathlib, importlib, argparse\n"
        "scripts_dir, lock_dir, name, log_path = sys.argv[1:5]\n"
        "sys.path.insert(0, scripts_dir)\n"
        "lockfile = importlib.import_module('lockfile')\n"
        "lockfile.LOCK_DIR = pathlib.Path(lock_dir)\n"
        "rc = lockfile.cmd_acquire(argparse.Namespace(name=name, timeout=30000))\n"
        "if rc != 0:\n"
        "    sys.exit(2)\n"
        "log = open(log_path, 'a')\n"
        "log.write(f'start {os.getpid()}\\n'); log.flush()\n"
        "time.sleep(0.02)\n"
        "log.write(f'end {os.getpid()}\\n'); log.flush(); log.close()\n"
        "sys.exit(lockfile.cmd_release(argparse.Namespace(name=name)))\n"
    )
    n = 6
    child_argv = [sys.executable, "-c", driver, str(Path(lockfile.__file__).parent), str(lock_dir), name, str(log)]
    procs = [subprocess.Popen(child_argv) for _ in range(n)]
    codes = [p.wait(timeout=60) for p in procs]
    assert codes == [0] * n, f"acquire/release failed in children: {codes}"

    lines = log.read_text().splitlines()
    assert len(lines) == 2 * n
    # Strict alternation: every 'start PID' is immediately followed by 'end PID'.
    for i in range(0, len(lines), 2):
        s_word, s_pid = lines[i].split()
        e_word, e_pid = lines[i + 1].split()
        assert (s_word, e_word) == ("start", "end"), f"overlapping critical sections: {lines}"
        assert s_pid == e_pid, f"interleaved holders: {lines}"
    assert len({line.split()[1] for line in lines}) == n


# ---------------------------------------------------------------------------
# cmd_acquire
# ---------------------------------------------------------------------------


def test_acquire_success(lock_dir: Path, lock_name: str) -> None:
    args = _ns(name=lock_name, timeout=5000)
    rc = lockfile.cmd_acquire(args)
    assert rc == 0

    path = lockfile._lock_path(lock_name)
    assert path.exists()
    data = lockfile._read_lock(path)
    assert data["pid"] == os.getpid()


def test_acquire_steals_stale_lock(lock_dir: Path, lock_name: str) -> None:
    """Acquire should steal a lock held by a dead PID."""
    path = lockfile._lock_path(lock_name)
    stale_data = json.dumps({"pid": 4_000_000, "timestamp": "2020-01-01T00:00:00+00:00"})
    path.write_text(stale_data)

    args = _ns(name=lock_name, timeout=1000)
    rc = lockfile.cmd_acquire(args)
    assert rc == 0

    data = lockfile._read_lock(path)
    assert data["pid"] == os.getpid()


def test_acquire_timeout(lock_dir: Path, lock_name: str) -> None:
    """Acquire should timeout when lock is held by a live process."""
    path = lockfile._lock_path(lock_name)
    from datetime import datetime, timezone

    # Write a lock with a fake PID and mock it as alive
    fake_pid = 9_999_999
    live_data = json.dumps({"pid": fake_pid, "timestamp": datetime.now(timezone.utc).isoformat()})
    path.write_text(live_data)

    def fake_is_alive(pid: int) -> bool:
        return pid == fake_pid or pid == os.getpid()

    with patch.object(lockfile, "_is_pid_alive", side_effect=fake_is_alive):
        args = _ns(name=lock_name, timeout=200)
        rc = lockfile.cmd_acquire(args)
    assert rc == 1


def test_acquire_steals_corrupt_lock(lock_dir: Path, lock_name: str) -> None:
    """Acquire should treat corrupt lock files as stale."""
    path = lockfile._lock_path(lock_name)
    path.write_text("{{broken json")

    args = _ns(name=lock_name, timeout=1000)
    rc = lockfile.cmd_acquire(args)
    assert rc == 0


# ---------------------------------------------------------------------------
# cmd_release
# ---------------------------------------------------------------------------


def test_release_own_lock(lock_dir: Path, lock_name: str) -> None:
    # Acquire first
    args = _ns(name=lock_name, timeout=5000)
    lockfile.cmd_acquire(args)

    # Release
    args = _ns(name=lock_name)
    rc = lockfile.cmd_release(args)
    assert rc == 0

    path = lockfile._lock_path(lock_name)
    assert not path.exists()


def test_release_missing_lock(lock_dir: Path, lock_name: str) -> None:
    """Releasing a non-existent lock should succeed silently."""
    args = _ns(name=lock_name)
    rc = lockfile.cmd_release(args)
    assert rc == 0


def test_release_other_pid(lock_dir: Path, lock_name: str) -> None:
    """Releasing a lock held by another PID warns but exits 0."""
    path = lockfile._lock_path(lock_name)
    from datetime import datetime, timezone

    other_data = json.dumps({"pid": 4_000_000, "timestamp": datetime.now(timezone.utc).isoformat()})
    path.write_text(other_data)

    args = _ns(name=lock_name)
    rc = lockfile.cmd_release(args)
    assert rc == 0
    # File should still exist (we didn't own it)
    assert path.exists()


def test_release_corrupt_lock(lock_dir: Path, lock_name: str) -> None:
    """Releasing a corrupt lock file should clean it up."""
    path = lockfile._lock_path(lock_name)
    path.write_text("not json")

    args = _ns(name=lock_name)
    rc = lockfile.cmd_release(args)
    assert rc == 0
    assert not path.exists()


# ---------------------------------------------------------------------------
# cmd_status
# ---------------------------------------------------------------------------


def test_status_not_locked(lock_dir: Path, lock_name: str, capsys: pytest.CaptureFixture[str]) -> None:
    args = _ns(name=lock_name)
    rc = lockfile.cmd_status(args)
    assert rc == 0
    assert "not locked" in capsys.readouterr().out


def test_status_locked(lock_dir: Path, lock_name: str, capsys: pytest.CaptureFixture[str]) -> None:
    # Acquire first
    args = _ns(name=lock_name, timeout=5000)
    lockfile.cmd_acquire(args)

    args = _ns(name=lock_name)
    rc = lockfile.cmd_status(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert f"PID {os.getpid()}" in out
    assert "alive" in out


def test_status_stale_lock(lock_dir: Path, lock_name: str, capsys: pytest.CaptureFixture[str]) -> None:
    path = lockfile._lock_path(lock_name)
    stale_data = json.dumps({"pid": 4_000_000, "timestamp": "2020-01-01T00:00:00+00:00"})
    path.write_text(stale_data)

    args = _ns(name=lock_name)
    rc = lockfile.cmd_status(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "dead" in out
    assert "STALE" in out


def test_status_corrupt_lock(lock_dir: Path, lock_name: str, capsys: pytest.CaptureFixture[str]) -> None:
    path = lockfile._lock_path(lock_name)
    path.write_text("garbage")

    args = _ns(name=lock_name)
    rc = lockfile.cmd_status(args)
    assert rc == 0
    assert "corrupt" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# main() dispatch
# ---------------------------------------------------------------------------


def test_main_no_command(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("sys.argv", ["lockfile.py"]):
        rc = lockfile.main()
    assert rc == 2


def test_main_acquire_roundtrip(lock_dir: Path) -> None:
    with patch("sys.argv", ["lockfile.py", "acquire", "test-main"]):
        rc = lockfile.main()
    assert rc == 0

    with patch("sys.argv", ["lockfile.py", "status", "test-main"]):
        rc = lockfile.main()
    assert rc == 0

    with patch("sys.argv", ["lockfile.py", "release", "test-main"]):
        rc = lockfile.main()
    assert rc == 0
