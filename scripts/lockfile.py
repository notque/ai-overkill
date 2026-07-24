#!/usr/bin/env python3
"""PID-based lockfile utility for preventing concurrent writes to shared resources.

Usage:
    python3 scripts/lockfile.py acquire learning-db --timeout 5000
    python3 scripts/lockfile.py release learning-db
    python3 scripts/lockfile.py status learning-db

Exit codes: 0 = success, 1 = timeout, 2 = unexpected error
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

LOCK_DIR = Path("/tmp")
LOCK_PREFIX = "claude-toolkit-"
LOCK_SUFFIX = ".lock"
STALE_AGE_SECONDS = 600  # 10 minutes
RETRY_INTERVAL_SECONDS = 0.1  # 100ms


def _lock_path(name: str) -> Path:
    """Return the lock file path for a given lock name."""
    return LOCK_DIR / f"{LOCK_PREFIX}{name}{LOCK_SUFFIX}"


def _is_pid_alive(pid: int) -> bool:
    """Check whether a process with the given PID is alive."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_lock(path: Path) -> dict | None:
    """Read and parse lock file. Returns None if missing or corrupt."""
    try:
        data = json.loads(path.read_text())
        return data if "pid" in data and "timestamp" in data else None
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _lock_age_seconds(data: dict) -> float:
    """Return lock age in seconds. Unparseable timestamps return infinity."""
    try:
        ts = datetime.fromisoformat(data["timestamp"])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds()
    except (ValueError, KeyError):
        return float("inf")


def _is_stale(data: dict) -> bool:
    """Check whether a lock is stale (dead PID or age > 10 min)."""
    if not _is_pid_alive(data.get("pid", -1)):
        return True
    return _lock_age_seconds(data) > STALE_AGE_SECONDS


def _write_lock(path: Path) -> bool:
    """Atomically create lock file with O_CREAT|O_EXCL. Returns True on success."""
    payload = json.dumps({"pid": os.getpid(), "timestamp": datetime.now(timezone.utc).isoformat()})
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        try:
            os.write(fd, payload.encode())
        finally:
            os.close(fd)
        return True
    except OSError:
        return False


def _steal_mutex_path(path: Path) -> Path:
    """Return the sidecar mutex path that serializes steals of this lock."""
    return path.with_name(path.name + ".steal")


def _steal_lock(path: Path) -> bool:
    """Steal a stale lock, serialized so two stealers cannot both win.

    An unconditional unlink-then-write is racy: two processes that both judged
    the lock stale could each remove-and-rewrite it, the second one deleting
    the first one's fresh lock -- both would then believe they hold the mutex.
    An exclusive flock on a sidecar mutex file serializes stealers, and the
    staleness re-check under that flock ensures a lock freshly written by a
    competing stealer is never removed.

    The mutex file is deliberately never unlinked: removing it would let two
    processes flock different inodes and defeat the serialization. The kernel
    releases the flock when the fd closes or the holder dies.
    """
    try:
        fd = os.open(str(_steal_mutex_path(path)), os.O_CREAT | os.O_RDWR, 0o644)
    except OSError:
        return False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False  # another stealer is active; caller retries
        data = _read_lock(path)
        if data is not None and not _is_stale(data):
            return False  # re-acquired by someone else while we decided to steal
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return _write_lock(path)
    finally:
        os.close(fd)


def cmd_acquire(args: argparse.Namespace) -> int:
    """Acquire a named lock, blocking up to timeout."""
    path = _lock_path(args.name)
    deadline = time.monotonic() + (args.timeout / 1000.0)

    while True:
        if _write_lock(path):
            return 0

        data = _read_lock(path)
        if data is None or _is_stale(data):
            if _steal_lock(path):
                return 0

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            info = f" (held by PID {data.get('pid', '?')}, age {_lock_age_seconds(data):.1f}s)" if data else ""
            print(f"lockfile: timeout acquiring '{args.name}'{info}", file=sys.stderr)
            return 1

        time.sleep(min(RETRY_INTERVAL_SECONDS, remaining))


def cmd_release(args: argparse.Namespace) -> int:
    """Release a named lock."""
    path = _lock_path(args.name)
    if not path.exists():
        return 0

    data = _read_lock(path)
    if data is None:
        try:
            path.unlink(missing_ok=True)
        except OSError as e:
            print(f"lockfile: could not remove corrupt lock: {e}", file=sys.stderr)
        return 0

    our_pid = os.getpid()
    holder_pid = data.get("pid", -1)
    if holder_pid == our_pid:
        try:
            path.unlink()
        except OSError as e:
            print(f"lockfile: could not remove lock file: {e}", file=sys.stderr)
        return 0

    print(
        f"lockfile: lock '{args.name}' held by PID {holder_pid}, not us ({our_pid}); skipping removal", file=sys.stderr
    )
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show lock status for diagnostics."""
    path = _lock_path(args.name)
    if not path.exists():
        print("not locked")
        return 0

    data = _read_lock(path)
    if data is None:
        print(f"locked (corrupt file at {path})")
        return 0

    pid = data.get("pid", "?")
    age = _lock_age_seconds(data)
    alive = _is_pid_alive(pid) if isinstance(pid, int) else False
    parts = [f"locked by PID {pid}", f"age {age:.1f}s", f"holder {'alive' if alive else 'dead'}"]
    if _is_stale(data):
        parts.append("STALE")
    print(", ".join(parts))
    return 0


def main() -> int:
    """Entry point -- parse args and dispatch to subcommand handler."""
    parser = argparse.ArgumentParser(prog="lockfile.py", description="PID-based lockfile utility.")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    p_acq = sub.add_parser("acquire", help="Acquire a named lock")
    p_acq.add_argument("name", help="Lock name (e.g. learning-db)")
    p_acq.add_argument("--timeout", type=int, default=5000, help="Timeout in ms (default: 5000)")

    p_rel = sub.add_parser("release", help="Release a named lock")
    p_rel.add_argument("name", help="Lock name (e.g. learning-db)")

    p_st = sub.add_parser("status", help="Show lock status")
    p_st.add_argument("name", help="Lock name (e.g. learning-db)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 2

    try:
        return {"acquire": cmd_acquire, "release": cmd_release, "status": cmd_status}[args.command](args)
    except Exception as e:
        print(f"lockfile: unexpected error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
