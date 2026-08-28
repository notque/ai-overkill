#!/usr/bin/env python3
# hook-version: 1.0.0
"""PostToolUse Hook: Record session-level retro knowledge activation for ROI tracking.

Tracks whether sessions with retro knowledge injected produce successful
outcomes. Feeds learning-db.py record-session for cohort comparison
(sessions with retro knowledge vs without).

ADR-032 Phase 1 — TRACK component.

Design:
- SILENT always (no stdout output to Claude)
- Non-blocking (always exits 0)
- Fast execution (<50ms target, no heavy imports)
- Batched recording: only records every 10th successful tool use
- Uses /tmp marker file to detect retro knowledge presence
"""

import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import get_session_id, get_tool_result, hook_error, is_tool_error
from stdin_timeout import read_stdin


def next_count(counter_file: Path) -> int:
    """Increment the batch counter atomically and return the new value.

    Parallel subagents fire this hook concurrently against one session counter.
    The unguarded read-modify-write this replaces truncated the file before
    writing, so a concurrent reader saw an empty file and reset the count to 1:
    under load the counter never reached 10 and the batch stopped firing.
    flock serializes the whole read-modify-write; the kernel drops the lock when
    the fd closes, so a killed hook cannot strand it.
    """
    fd = os.open(counter_file, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            count = int(os.read(fd, 64).decode().strip() or 0)
        except (ValueError, UnicodeDecodeError):
            count = 0
        count += 1
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        os.write(fd, str(count).encode())
        return count
    finally:
        os.close(fd)


def main() -> None:
    """Record session activation stats on successful tool completions."""
    try:
        hook_input = json.loads(read_stdin(timeout=2))

        # tool_name filter removed — matcher "Edit|Write|Bash" in settings.json
        # prevents this hook from spawning for non-matching tools.

        tool_result = get_tool_result(hook_input)
        if is_tool_error(tool_result):
            return

        session_id = get_session_id()

        # Check if retro knowledge was injected this session.
        # The retro-knowledge-injector.py sets this marker when it injects.
        marker = Path("/tmp") / f"claude-retro-active-{session_id}"
        had_retro = marker.exists()

        # Batch: only record every 10th successful tool use to avoid spam
        counter_file = Path("/tmp") / f"claude-activation-counter-{session_id}"
        count = next_count(counter_file)

        if count % 10 != 0:
            return

        # Record session stats via learning-db.py
        repo_root = Path(__file__).resolve().parent.parent
        script = repo_root / "scripts" / "learning-db.py"
        if not script.exists():
            return

        cmd = [
            sys.executable,
            str(script),
            "record-session",
            "--session",
            session_id,
            "--failures",
            "0",
            "--waste-tokens",
            "0",
        ]
        if had_retro:
            cmd.append("--had-retro")

        subprocess.run(cmd, capture_output=True, timeout=5)

    except (json.JSONDecodeError, subprocess.TimeoutExpired, OSError, Exception) as e:
        hook_error("record-activation", e)
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
