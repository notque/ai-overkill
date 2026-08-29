"""
Shared warm-start context builder.

Used by hooks/subagent-start-warmstart.py (SubagentStart, lands in the
subagent) and the superseded hooks/pretool-subagent-warmstart.py
(PreToolUse:Agent, lands in the parent). Both read the same on-disk
parent-session state: session-reads JSONL, task_plan.md, .adr-session.json,
and .planning/discoveries/.

Session scoping: files-seen entries come from the v2 JSONL session-reads
format and are filtered to the given session id and the freshness window;
v1 legacy plain-path lines are ignored. Credential-shaped paths are filtered
out. task_plan.md, .adr-session.json, and discovery briefs are only used when
modified within the freshness window.
"""

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hook_utils import is_sensitive_path

SESSION_READS_FILE = ".claude/session-reads.txt"
TASK_PLAN_FILE = "task_plan.md"
ADR_SESSION_FILE = ".adr-session.json"
DISCOVERIES_DIR = ".planning/discoveries"

MAX_OUTPUT_CHARS = 4000
MAX_FILES_SHOWN = 10

# Context older than this is treated as belonging to a previous task.
FRESHNESS_HOURS = 24


def is_fresh_file(path: Path, hours: int = FRESHNESS_HOURS) -> bool:
    """True when path exists and was modified within the freshness window."""
    try:
        return (time.time() - path.stat().st_mtime) <= hours * 3600
    except OSError:
        return False


def load_recent_reads(
    reads_path: Path,
    session_id: str,
    max_count: int = MAX_FILES_SHOWN,
) -> list[str]:
    """Load up to max_count recent file paths for the current session.

    Reads the v2 JSONL format ({"ts", "session", "path"}). Entries from other
    sessions, entries older than FRESHNESS_HOURS, credential-shaped paths, and
    v1 legacy plain-path lines are all skipped.

    Args:
        reads_path: Path to the session-reads.txt file.
        session_id: Current session id; only matching entries are returned.
        max_count: Maximum number of paths to return.

    Returns:
        List of file path strings, most recent last (tail of file).
    """
    if not reads_path.is_file():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=FRESHNESS_HOURS)
    paths: list[str] = []
    try:
        for line in reads_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue  # v1 legacy plain-path line — no session id, skip
            if not isinstance(entry, dict):
                continue
            if str(entry.get("session", "")) != session_id:
                continue
            try:
                ts = datetime.fromisoformat(entry["ts"])
            except (KeyError, TypeError, ValueError):
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts < cutoff:
                continue
            path = str(entry.get("path", ""))
            if not path or is_sensitive_path(path):
                continue
            paths.append(path)
        return paths[-max_count:]
    except OSError:
        return []


def extract_task_plan(plan_path: Path) -> dict[str, str]:
    """Extract Goal and Status lines from task_plan.md.

    Args:
        plan_path: Path to task_plan.md.

    Returns:
        Dict with 'goal' and 'status' keys (empty strings if not found).
    """
    result = {"goal": "", "status": ""}

    if not plan_path.is_file() or not is_fresh_file(plan_path):
        return result

    try:
        content = plan_path.read_text(encoding="utf-8")
    except OSError:
        return result

    lines = content.splitlines()
    in_goal_section = False
    for line in lines:
        stripped = line.strip()
        if stripped == "## Goal":
            in_goal_section = True
            continue
        if in_goal_section:
            if stripped.startswith("## "):
                # Hit next section heading, goal section is over
                in_goal_section = False
            elif stripped:
                result["goal"] = stripped[:200]
                in_goal_section = False
        if stripped.startswith("**Currently in Phase") or stripped.startswith("**Status"):
            result["status"] = stripped[:200]

    return result


def extract_decisions(plan_path: Path) -> list[str]:
    """Extract decisions from the 'Decisions Made' section of task_plan.md.

    Args:
        plan_path: Path to task_plan.md.

    Returns:
        List of decision strings.
    """
    if not plan_path.is_file() or not is_fresh_file(plan_path):
        return []

    try:
        content = plan_path.read_text(encoding="utf-8")
    except OSError:
        return []

    decisions: list[str] = []
    in_decisions = False

    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "## Decisions Made":
            in_decisions = True
            continue
        if in_decisions:
            if stripped.startswith("## "):
                break  # Next section
            if stripped.startswith("- "):
                decisions.append(stripped[2:].strip()[:200])

    return decisions


def load_adr_session(session_path: Path) -> dict[str, str]:
    """Load ADR session metadata from .adr-session.json.

    Args:
        session_path: Path to .adr-session.json.

    Returns:
        Dict with 'adr_path' and 'domain' keys (empty strings if not found).
    """
    result = {"adr_path": "", "domain": ""}

    if not session_path.is_file() or not is_fresh_file(session_path):
        return result

    try:
        content = session_path.read_text(encoding="utf-8")
        data = json.loads(content)
        result["adr_path"] = data.get("adr_path", "")
        result["domain"] = data.get("domain", "")
    except (OSError, json.JSONDecodeError):
        pass

    return result


def list_discoveries(discoveries_dir: Path) -> list[str]:
    """List discovery brief filenames from .planning/discoveries/.

    Args:
        discoveries_dir: Path to the discoveries directory.

    Returns:
        List of filenames (not full paths).
    """
    if not discoveries_dir.is_dir():
        return []

    try:
        return sorted(f.name for f in discoveries_dir.iterdir() if f.is_file() and is_fresh_file(f))
    except OSError:
        return []


def build_context_block(
    files: list[str],
    task_plan: dict[str, str],
    decisions: list[str],
    adr_session: dict[str, str],
    discoveries: list[str],
    agent_type: str = "subagent",
) -> str:
    """Build the parent-context block for subagent injection.

    Args:
        files: List of file paths seen in the session.
        task_plan: Dict with 'goal' and 'status' from task_plan.md.
        decisions: List of decisions from task_plan.md.
        adr_session: Dict with 'adr_path' and 'domain'.
        discoveries: List of discovery brief filenames.
        agent_type: Name of the dispatched agent for the header line.

    Returns:
        Formatted context block string, capped at MAX_OUTPUT_CHARS.
    """
    parts: list[str] = []

    # Files seen
    if files:
        file_list = ", ".join(files)
        parts.append(f"[warmstart] Files seen ({len(files)}): {file_list}")
    else:
        parts.append("[warmstart] Files seen (0): none")

    # Task plan
    if task_plan["goal"]:
        parts.append(f"[warmstart] Task: {task_plan['goal']}")
    if task_plan["status"]:
        parts.append(f"[warmstart] Status: {task_plan['status']}")

    # ADR session
    if adr_session["adr_path"]:
        parts.append(f"[warmstart] ADR session: {adr_session['adr_path']} (domain: {adr_session['domain']})")

    # Decisions
    if decisions:
        decision_text = "; ".join(decisions)
        parts.append(f"[warmstart] Decisions: {decision_text}")

    # Discoveries
    if discoveries:
        disc_text = ", ".join(discoveries)
        parts.append(f"[warmstart] Discovery briefs: {disc_text}")

    header = f"[warmstart] Parent session context for {agent_type or 'subagent'}:"
    body = "\n".join(parts)
    full_output = f"{header}\n{body}"

    # Cap at MAX_OUTPUT_CHARS
    if len(full_output) > MAX_OUTPUT_CHARS:
        full_output = full_output[: MAX_OUTPUT_CHARS - 3] + "..."

    return full_output


def gather_context_block(session_id: str, agent_type: str = "subagent") -> str:
    """Read every parent-session source from cwd and build the block."""
    task_plan_path = Path(TASK_PLAN_FILE)
    return build_context_block(
        files=load_recent_reads(Path(SESSION_READS_FILE), session_id),
        task_plan=extract_task_plan(task_plan_path),
        decisions=extract_decisions(task_plan_path),
        adr_session=load_adr_session(Path(ADR_SESSION_FILE)),
        discoveries=list_discoveries(Path(DISCOVERIES_DIR)),
        agent_type=agent_type,
    )
