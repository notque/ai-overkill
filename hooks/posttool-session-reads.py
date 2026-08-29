#!/usr/bin/env python3
# hook-version: 2.1.0
"""
PostToolUse Hook: Session Read Tracker

Tracks files read during the session by appending JSONL entries
({"ts", "session", "path"}) to .claude/session-reads.txt. This provides a
lightweight record of files the parent session has seen, used by the
warmstart hook to give subagents context about what's already been read.

v2 (session scoping): entries carry the session id and a UTC timestamp so
the warmstart reader can restrict itself to the current session. Writes
prune entries older than RETENTION_DAYS and drop v1 legacy plain-path
lines, so the file cannot accumulate cross-session state indefinitely.
Credential-shaped paths (.ssh/, .env, *.pem, ...) are never recorded.

v2.1 (Bash reads): a Bash command that starts with a read-only pager
(cat, sed, head, tail, less, bat) also records every argument that resolves
to an existing file under cwd, capped at MAX_BASH_PATHS. Codex cannot
intercept the built-in Read tool, so this keeps the warm-start file list
populated there. Commands containing rm, mv, cp, or a redirect are ignored.

Design Principles:
- SILENT output (no context injection)
- Non-blocking (always exits 0)
- Processes Read tool results and read-only Bash commands
- Deduplicates (session, path) pairs
"""

import json
import re
import shlex
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import empty_output, get_session_id, hook_error, is_sensitive_path
from stdin_timeout import read_stdin

EVENT_NAME = "PostToolUse"

SESSION_READS_FILE = ".claude/session-reads.txt"

# Entries older than this are pruned on every write.
RETENTION_DAYS = 7

# Bash commands that read files without changing them.
_READ_CMD_RE = re.compile(r"^\s*(cat|sed|head|tail|less|bat)\b")
# Any of these anywhere in the command means it may write or move; skip it.
_MUTATING_RE = re.compile(r"(^|[\s;&|])(rm|mv|cp)\b|>")
MAX_BASH_PATHS = 20


def bash_read_paths(command: str, cwd: Path | None = None) -> list[str]:
    """Return file paths a read-only Bash command touches, in argument order.

    Only commands that open with cat/sed/head/tail/less/bat qualify. Commands
    that mention rm, mv, cp, or a `>` redirect return nothing. Each argument
    is kept when it names an existing file under cwd; the result is capped
    at MAX_BASH_PATHS. Credential-shaped paths are dropped.
    """
    if not isinstance(command, str) or not _READ_CMD_RE.match(command):
        return []
    if _MUTATING_RE.search(command):
        return []
    try:
        args = shlex.split(command)
    except ValueError:
        return []
    if args and args[0] == "sed" and any(a.startswith("-i") or a == "--in-place" for a in args[1:]):
        return []  # in-place edit, not a read
    base = (cwd or Path.cwd()).resolve()
    paths: list[str] = []
    for arg in args[1:]:
        if not arg or arg.startswith("-"):
            continue
        try:
            candidate = (base / arg).resolve()
            if not candidate.is_file() or not candidate.is_relative_to(base):
                continue
        except (OSError, ValueError):
            continue
        rel = str(candidate.relative_to(base))
        if is_sensitive_path(rel) or rel in paths:
            continue
        paths.append(rel)
        if len(paths) >= MAX_BASH_PATHS:
            break
    return paths


def event_paths(event: dict) -> list[str]:
    """Paths to record for one event: Read file_path, or read-only Bash args."""
    tool_input = event.get("tool_input", {})
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except (json.JSONDecodeError, TypeError):
            return []
    if not isinstance(tool_input, dict):
        return []
    if event.get("tool_name") == "Bash":
        return bash_read_paths(str(tool_input.get("command", "")))
    file_path = tool_input.get("file_path", "")
    if not file_path or is_sensitive_path(file_path):
        return []
    return [str(file_path)]


def _parse_entry(line: str) -> dict | None:
    """Parse one JSONL entry; None for blank, legacy plain-path, or bad lines."""
    line = line.strip()
    if not line:
        return None
    try:
        entry = json.loads(line)
    except json.JSONDecodeError:
        return None  # v1 legacy plain-path line — dropped by design
    if not isinstance(entry, dict) or not entry.get("path"):
        return None
    return entry


def _fresh(entry: dict, cutoff: datetime) -> bool:
    """True when the entry's timestamp parses and is at or after cutoff."""
    try:
        ts = datetime.fromisoformat(entry["ts"])
    except (KeyError, TypeError, ValueError):
        return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts >= cutoff


def main() -> None:
    """Record Read tool file paths and read-only Bash paths for this session.

    Flow:
    1. Read stdin JSON; extract file_path (Read) or command paths (Bash)
    2. Skip credential-shaped paths entirely
    3. Rewrite .claude/session-reads.txt: fresh entries + the new one,
       deduplicated on (session, path)
    4. Exit silently (no context injection)
    """
    try:
        event_data = read_stdin(timeout=2)
        if not event_data:
            return

        event = json.loads(event_data)

        # The settings.json matcher ("Read" or "Bash") limits which tools
        # spawn this hook; event_paths() decides what each event records.
        if not isinstance(event, dict):
            return
        new_paths = event_paths(event)
        if not new_paths:
            return

        session_id = event.get("session_id") or get_session_id()
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=RETENTION_DAYS)

        reads_path = Path(SESSION_READS_FILE)
        reads_path.parent.mkdir(parents=True, exist_ok=True)

        entries: list[dict] = []
        seen: set[tuple[str, str]] = set()
        if reads_path.is_file():
            try:
                for line in reads_path.read_text(encoding="utf-8").splitlines():
                    entry = _parse_entry(line)
                    if entry is None or not _fresh(entry, cutoff):
                        continue
                    key = (str(entry.get("session", "")), str(entry["path"]))
                    if key in seen:
                        continue
                    seen.add(key)
                    entries.append(entry)
            except OSError:
                pass

        for file_path in new_paths:
            if (session_id, file_path) not in seen:
                seen.add((session_id, file_path))
                entries.append({"ts": now.isoformat(), "session": session_id, "path": file_path})

        tmp_path = reads_path.with_suffix(".tmp")
        tmp_path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
        tmp_path.replace(reads_path)

        # Silent output — no context injection
        empty_output(EVENT_NAME).print_and_exit()

    except Exception as e:
        hook_error("posttool-session-reads", e)
    finally:
        sys.exit(0)  # Never block


if __name__ == "__main__":
    main()
