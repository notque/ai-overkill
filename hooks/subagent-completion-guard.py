#!/usr/bin/env python3
# hook-version: 1.0.0
"""
SubagentStop Hook: Completion Guard

Enforces safety tiers and captures metadata at the moment any subagent stops:

  Tier 0: Worktree Metadata Capture (ALWAYS ACTIVE)
    Detects if cwd is a git worktree (not the main repo), captures the
    branch name, commit count, and uncommitted file status. Outputs
    structured [worktree-result]/[worktree-warning]/[worktree-empty]
    lines so the dispatcher knows what to merge/cleanup. Records the
    worktree-to-branch mapping in the learning DB.

  Tier 1: Branch Safety Guard (ALWAYS ACTIVE)
    Blocks if the subagent committed directly to master/main.
    Uses: git log origin/master..HEAD to detect new commits.

  Tier 2: READ-ONLY Violation Guard (reviewer-* agents only)
    Blocks if a reviewer-* agent used Write, Edit, or NotebookEdit tools.
    Detection: agent_type field starts with "reviewer-".
    Uses: transcript JSON scan for write tool invocations.

  Tier 3: Protected-Org Workflow Guard (protected-org repos only)
    Blocks if git push or gh pr merge ran without user confirmation
    in a protected organization's repository. Configure protected orgs
    via PROTECTED_ORGS env var (comma-separated org name patterns).

Design Principles:
- Sub-50ms execution (git log is fast, transcript scan is O(n))
- Non-blocking on hook errors (always exits 0 on internal failures)
- Blocks ONLY on detected violations (never on uncertainty)
- Uses exit 0 + JSON permissionDecision:deny to feed blocking message back to the subagent
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import hook_error
from stdin_timeout import read_stdin

_EVENT_NAME = "SubagentStop"

# Agents whose names start with this prefix are READ-ONLY by contract
_REVIEWER_PREFIX = "reviewer-"

# Write tools that reviewer-* agents must never use
_WRITE_TOOLS = {"Write", "Edit", "NotebookEdit"}

# Commands that constitute auto-execution in protected-org repos
_PROTECTED_ORG_GATED_PATTERNS = [
    re.compile(r"\bgit\s+push\b"),
    re.compile(r"\bgh\s+pr\s+(merge|create)\b"),
]

# Marker a commit message can contain to indicate explicit user approval
# for a direct-to-main commit (escape hatch for hotfixes)
_APPROVED_DIRECT_MARKER = "[APPROVED-DIRECT]"


# ---------------------------------------------------------------------------
# Tier 0: Worktree Metadata Capture
# ---------------------------------------------------------------------------


def _git(cwd: str, *args: str) -> str | None:
    """Run a git command, return stdout stripped, or None on failure."""
    try:
        result = subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def capture_worktree_metadata(cwd: str) -> dict:
    """
    Detect if cwd is inside a git worktree and capture branch info.

    Returns a dict with worktree metadata, or empty dict if not a worktree.
    """
    # Verify we're inside a git work tree at all
    if _git(cwd, "rev-parse", "--is-inside-work-tree") is None:
        return {}

    # Get the common git dir (main repo's .git) and this worktree's git dir
    common_dir = _git(cwd, "rev-parse", "--git-common-dir")
    git_dir = _git(cwd, "rev-parse", "--git-dir")

    if common_dir is None or git_dir is None:
        return {}

    # Normalize paths for reliable comparison
    common_dir = str(Path(common_dir).resolve())
    git_dir = str(Path(git_dir).resolve())

    # If git_dir == common_dir, we're in the main repo, not a worktree
    if git_dir == common_dir:
        return {}

    # We're in a worktree — gather metadata
    branch = _git(cwd, "symbolic-ref", "--short", "HEAD") or ""

    # Count commits ahead of master (fall back to main)
    ahead = _git(cwd, "rev-list", "--count", "master..HEAD")
    if ahead is None:
        ahead = _git(cwd, "rev-list", "--count", "main..HEAD")
    commits_ahead = int(ahead) if ahead and ahead.isdigit() else 0

    # Check for uncommitted changes
    status = _git(cwd, "status", "--porcelain")
    has_uncommitted = bool(status)
    uncommitted_files = len(status.splitlines()) if status else 0

    return {
        "is_worktree": True,
        "worktree_path": cwd,
        "branch": branch,
        "commits_ahead": commits_ahead,
        "has_uncommitted": has_uncommitted,
        "uncommitted_files": uncommitted_files,
    }


def format_worktree_output(meta: dict) -> list[str]:
    """
    Format worktree metadata into structured output lines for stderr.

    Returns a list of lines to print. Each line starts with a tag:
      [worktree-result]  — always emitted when worktree detected
      [worktree-warning] — emitted when uncommitted files exist
      [worktree-empty]   — emitted when worktree has no changes at all
    """
    if not meta or not meta.get("is_worktree"):
        return []

    lines = []
    path = meta["worktree_path"]
    branch = meta["branch"]
    commits = meta["commits_ahead"]
    uncommitted = meta["uncommitted_files"]

    lines.append(f"[worktree-result] path={path} branch={branch} commits={commits} uncommitted={uncommitted}")

    if meta["has_uncommitted"]:
        lines.append(
            f"[worktree-warning] Agent left {uncommitted} uncommitted "
            f"files in worktree {path} — work may be lost on cleanup"
        )

    if commits == 0 and not meta["has_uncommitted"]:
        lines.append(f"[worktree-empty] Worktree {path} has no changes — safe to remove")

    return lines


def record_worktree_learning(meta: dict, agent_type: str) -> None:
    """
    Record worktree-to-branch mapping in the learning DB (best-effort).

    Uses lazy import to avoid slowing down the common non-worktree path.
    """
    if not meta or not meta.get("is_worktree"):
        return

    branch = meta.get("branch", "")
    if not branch:
        return

    try:
        # Lazy import — only pay the cost when we actually have worktree data
        sys.path.insert(0, str(Path(__file__).parent / "lib"))
        from learning_db_v2 import record_learning

        record_learning(
            topic="worktree-branches",
            key=f"worktree-{branch}",
            value=(
                f"path={meta['worktree_path']} branch={branch} "
                f"commits={meta['commits_ahead']} "
                f"uncommitted={meta['uncommitted_files']}"
            ),
            category="effectiveness",
            confidence=0.8,
            tags=["worktree", branch, agent_type] if agent_type else ["worktree", branch],
            source="hook:subagent-completion-guard",
        )
    except Exception:
        # Best-effort — never block the hook for a learning DB write
        pass


# ---------------------------------------------------------------------------
# Tier 1: Branch Safety
# ---------------------------------------------------------------------------


def check_branch_safety(cwd: str) -> str | None:
    """
    Check if any commits were made directly to master/main.

    Returns blocking message string if violation found, None if clean.
    """
    try:
        # Check which branch HEAD is on first
        branch_check = subprocess.run(
            ["git", "-C", cwd, "symbolic-ref", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if branch_check.returncode != 0:
            # Detached HEAD or git not available — skip silently
            return None

        current_branch = branch_check.stdout.strip()
        if current_branch not in ("master", "main"):
            # Feature branch — compliant by definition
            return None

        # HEAD is on a protected branch — check for new commits
        result = subprocess.run(
            ["git", "-C", cwd, "log", "--oneline", f"origin/{current_branch}..HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode != 0:
            # No remote or branch doesn't exist — skip
            return None

        commits = result.stdout.strip()
        if not commits:
            return None

        # Check if any commit has the approved-direct marker (escape hatch)
        lines = commits.splitlines()
        unapproved = [line for line in lines if _APPROVED_DIRECT_MARKER not in line]
        if not unapproved:
            print(
                f"[subagent-guard] escape hatch used: {len(lines)} commit(s) approved via {_APPROVED_DIRECT_MARKER}",
                file=sys.stderr,
            )
            return None

        commit_list = "\n".join(f"  {c}" for c in unapproved)
        return (
            f"BLOCKED: Subagent committed directly to {current_branch}.\n"
            f"Commits found:\n{commit_list}\n\n"
            f"Required action: git reset --soft HEAD~{len(unapproved)}, "
            f"create a feature branch, re-commit there.\n"
            f"(To explicitly approve a direct commit, add '{_APPROVED_DIRECT_MARKER}' "
            f"to the commit message.)"
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # git not available or timed out — skip silently
        pass

    return None


# ---------------------------------------------------------------------------
# Tier 2: READ-ONLY Violation Guard
# ---------------------------------------------------------------------------


def is_reviewer_agent(agent_type: str) -> bool:
    """Return True if agent_type starts with 'reviewer-' prefix."""
    return bool(agent_type) and agent_type.startswith(_REVIEWER_PREFIX)


def find_write_tool_in_transcript(transcript_path: str) -> str | None:
    """
    Scan the transcript for any Write/Edit/NotebookEdit tool use.

    Returns the first offending tool name + file, or None if clean.
    """
    if not transcript_path:
        return None

    path = Path(transcript_path)
    if not path.exists() or not path.is_file():
        return None

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    # Each transcript line is a JSON object (newline-delimited JSON)
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Tool-use entries have type="tool_use" or tool_name field
        tool_name = entry.get("tool_name")
        if not tool_name and isinstance(entry.get("content"), list):
            for block in entry["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") in _WRITE_TOOLS:
                    tool_name = block["name"]
                    break
        if tool_name in _WRITE_TOOLS:
            # Try to extract the file path from tool_input
            tool_input = entry.get("tool_input") or entry.get("input") or {}
            file_path = tool_input.get("file_path", "")
            if file_path:
                return f"{tool_name}({file_path})"
            return tool_name

    return None


def check_readonly_violation(agent_type: str, transcript_path: str) -> str | None:
    """
    Check if a reviewer-* agent used write tools.

    Returns blocking message string if violation found, None if clean.
    """
    if not is_reviewer_agent(agent_type):
        return None

    write_use = find_write_tool_in_transcript(transcript_path)
    if write_use is None:
        return None

    return (
        f"BLOCKED: {agent_type} is a READ-ONLY agent but used a write tool.\n"
        f"Tool used: {write_use}\n\n"
        f"reviewer-* agents must NEVER use Write, Edit, or NotebookEdit.\n"
        f"Remove any file modifications or re-run as a non-reviewer agent."
    )


# ---------------------------------------------------------------------------
# Tier 3: Protected-Org Workflow Guard
# ---------------------------------------------------------------------------


def _get_protected_org_patterns() -> list[re.Pattern]:
    """
    Build regex patterns for protected organizations from env var.

    Set PROTECTED_ORGS env var (comma-separated) to define protected organizations.
    Example: PROTECTED_ORGS="my-company,my-org-name"

    Returns list of compiled regex patterns, or empty list if not configured.
    """
    orgs_env = os.environ.get("PROTECTED_ORGS", "").strip()
    if not orgs_env:
        return []
    patterns = []
    for org in orgs_env.split(","):
        org = org.strip()
        if org:
            patterns.append(
                re.compile(
                    rf"github\.com[:/]{re.escape(org)}/",
                    re.IGNORECASE,
                )
            )
    return patterns


def is_protected_org_repo(cwd: str) -> bool:
    """Return True if the current repo's origin matches a protected organization."""
    patterns = _get_protected_org_patterns()
    if not patterns:
        return False

    try:
        result = subprocess.run(
            ["git", "-C", cwd, "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if result.returncode != 0:
            return False
        url = result.stdout.strip()
        return any(p.search(url) for p in patterns)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def find_gated_command_in_transcript(transcript_path: str) -> str | None:
    """
    Scan transcript for unauthorized git push or gh pr merge/create in protected-org repos.

    Returns the offending command string if found, None if clean.
    """
    if not transcript_path:
        return None

    path = Path(transcript_path)
    if not path.exists() or not path.is_file():
        return None

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Look for Bash tool calls
        tool_name = entry.get("tool_name")
        if not tool_name or tool_name.lower() != "bash":
            continue

        tool_input = entry.get("tool_input") or entry.get("input") or {}
        command = tool_input.get("command", "")
        if not command:
            continue

        for pattern in _PROTECTED_ORG_GATED_PATTERNS:
            if pattern.search(command):
                return command.strip()

    return None


def check_protected_org_workflow(cwd: str, transcript_path: str) -> str | None:
    """
    Check for auto-execution of gated git operations in protected-org repos.

    Returns blocking message string if violation found, None if clean.
    """
    if not is_protected_org_repo(cwd):
        return None

    gated_cmd = find_gated_command_in_transcript(transcript_path)
    if gated_cmd is None:
        return None

    return (
        f"BLOCKED: Unauthorized git operation in protected-org repo.\n"
        f"Command: {gated_cmd}\n\n"
        f"Protected-org repos require explicit user confirmation before EACH git push, "
        f"gh pr create, or gh pr merge.\n"
        f"Present the command to the user for approval before running it."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    try:
        raw = read_stdin(timeout=2)
        if not raw:
            sys.exit(0)

        event = json.loads(raw)

        # Only process SubagentStop events
        event_type = event.get("hook_event_name") or event.get("type", "")
        if event_type != _EVENT_NAME:
            sys.exit(0)

        cwd = event.get("cwd", str(Path.cwd()))
        transcript_path = event.get("transcript_path", "")
        agent_type = event.get("agent_type", "")

        # Tier 0: Worktree metadata capture (always active, non-blocking)
        # Note: worktree metadata is output to stderr for dispatchers but
        # no longer recorded to learning.db (was polluting knowledge store
        # with operational telemetry — see adr/skill-scoped-learning.md)
        worktree_meta = capture_worktree_metadata(cwd)
        if worktree_meta:
            for line in format_worktree_output(worktree_meta):
                print(line, file=sys.stderr)

        # Run all three tiers — collect violations
        violations = []

        # Tier 1: Branch safety (always active)
        v1 = check_branch_safety(cwd)
        if v1:
            violations.append(v1)

        # Tier 2: READ-ONLY violation (reviewer-* agents only)
        v2 = check_readonly_violation(agent_type, transcript_path)
        if v2:
            violations.append(v2)

        # Tier 3: Protected-org workflow guard
        v3 = check_protected_org_workflow(cwd, transcript_path)
        if v3:
            violations.append(v3)

        if violations:
            separator = "\n" + "=" * 60 + "\n"
            message = separator.join(violations)
            print(message, file=sys.stderr)
            # SubagentStop uses top-level permissionDecision (not wrapped in hookSpecificOutput)
            deny_output = {
                "permissionDecision": "deny",
                "permissionDecisionReason": message,
            }
            print(json.dumps(deny_output))
            sys.exit(0)

        # All clear — allow subagent to stop
        sys.exit(0)

    except (json.JSONDecodeError, KeyError, TypeError):
        # Malformed input — don't block (non-blocking on internal errors)
        sys.exit(0)
    except Exception as e:
        hook_error("subagent-completion-guard", e)


if __name__ == "__main__":
    main()
