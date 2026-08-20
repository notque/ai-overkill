#!/usr/bin/env python3
# hook-version: 1.0.0
"""PostToolUse Hook: ADR lifecycle checker on merge.

Fires after a Bash tool use. Detects merge commands (gh pr merge / git merge)
and scans the branch name and recent commit messages for ADR references.

For each matched ADR it:
1. Reads the ## Implementation section and extracts numbered steps.
2. Diffs HEAD~1 to get changed files.
3. Checks each step for keyword matches in the changed-file list.
4. Reports a checklist with PARTIAL / COMPLETE status.
5. If all steps matched, updates the ADR file status to "Completed" and moves
   it to adr/completed/ (shutil, not git mv — adr/ is gitignored).

Always exits 0 (non-blocking, informational hook).
Target execution time: <200ms (exits early when not a merge command).
"""

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import context_output, empty_output, get_tool_input
from stdin_timeout import read_stdin

DEBUG_LOG = Path("/tmp/claude_hook_debug.log")
EVENT_NAME = "PostToolUse"

# Patterns to identify ADR references in branch names / commit messages
ADR_PATTERNS = [
    re.compile(r"ADR-(\d+)", re.IGNORECASE),
    re.compile(r"adr/(\d+)-"),
    re.compile(r"adr-(\d+)", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def debug_log(msg: str) -> None:
    try:
        with open(DEBUG_LOG, "a") as f:
            f.write(f"[adr-lifecycle] {msg}\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_git(args: list[str], cwd: str | None = None, timeout: int = 5) -> str:
    """Run a git command and return stdout. Returns '' on failure."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def extract_adr_numbers(text: str) -> list[str]:
    """Return deduplicated ADR numbers found in *text*."""
    seen: set[str] = set()
    numbers: list[str] = []
    for pattern in ADR_PATTERNS:
        for m in pattern.finditer(text):
            num = m.group(1).lstrip("0") or "0"
            if num not in seen:
                seen.add(num)
                numbers.append(num)
    return numbers


def find_adr_file(adr_number: str) -> Path | None:
    """Locate adr/{NNN}-*.md, zero-padded searches 1-4 digits."""
    adr_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")) / "adr"
    if not adr_dir.is_dir():
        return None

    # Try zero-padded variants: 1 → 001, 179 → 179, etc.
    num_int = int(adr_number)
    padded_variants = [
        str(num_int),
        f"{num_int:03d}",
        f"{num_int:04d}",
    ]
    for variant in padded_variants:
        matches = list(adr_dir.glob(f"{variant}-*.md"))
        if matches:
            return matches[0]
    return None


def extract_implementation_steps(adr_content: str) -> list[str]:
    """Extract numbered steps from ## Implementation section."""
    steps: list[str] = []
    in_section = False
    for line in adr_content.splitlines():
        if re.match(r"^#{1,3}\s+Implementation", line, re.IGNORECASE):
            in_section = True
            continue
        if in_section:
            # Stop at next heading
            if re.match(r"^#{1,3}\s+", line):
                break
            # Match numbered list items: "1. " or "1) "
            m = re.match(r"^\s*\d+[.)]\s+(.+)", line)
            if m:
                steps.append(m.group(1).strip())
    return steps


def get_changed_files() -> list[str]:
    """Return list of files changed in the last commit (HEAD~1 diff)."""
    output = run_git(["diff", "HEAD~1", "--name-only"])
    if not output:
        # Fallback: files in most recent commit
        output = run_git(["show", "--name-only", "--format=", "HEAD"])
    return [f.strip() for f in output.splitlines() if f.strip()]


def keywords_from_step(step: str) -> list[str]:
    """Extract meaningful lowercase keywords (>3 chars) from a step description."""
    words = re.findall(r"[a-zA-Z0-9_\-/\.]+", step)
    return [w.lower() for w in words if len(w) > 3]


def step_matches_files(step: str, changed_files: list[str]) -> tuple[bool, str]:
    """Return (matched, matching_file_or_empty)."""
    keywords = keywords_from_step(step)
    if not keywords:
        return False, ""
    lower_files = [f.lower() for f in changed_files]
    for keyword in keywords:
        for i, lf in enumerate(lower_files):
            if keyword in lf:
                return True, changed_files[i]
    return False, ""


def update_adr_status(adr_path: Path, adr_number: str) -> None:
    """Change ## Status to Completed and move file to adr/completed/."""
    try:
        content = adr_path.read_text()
        today = date.today().strftime("%Y-%m-%d")
        # Replace first occurrence of status proposed/accepted/approved
        updated = re.sub(
            r"(## Status\s*\n)(Proposed|Accepted|Approved|Active|Draft)",
            rf"\1Completed ({today})",
            content,
            flags=re.IGNORECASE,
        )
        if updated == content:
            # No status line found — append/replace generically
            updated = re.sub(
                r"(## Status\s*\n)([^\n]*)",
                rf"\1Completed ({today})",
                content,
                flags=re.IGNORECASE,
            )

        completed_dir = adr_path.parent / "completed"
        completed_dir.mkdir(exist_ok=True)

        # Write updated content to destination first (atomic-ish)
        dest = completed_dir / adr_path.name
        dest.write_text(updated)

        # Remove original
        adr_path.unlink()
        debug_log(f"Moved {adr_path.name} to adr/completed/ with status Completed ({today})")
    except Exception as e:
        debug_log(f"Failed to update/move ADR: {e}")


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


def is_merge_command(command: str, exit_code: int) -> bool:
    """Return True if this is a successful merge command."""
    if exit_code != 0:
        return False
    return "gh pr merge" in command or "git merge" in command


def process_merge(command: str) -> str | None:
    """Core merge processing. Returns context string or None."""
    lines: list[str] = ["[adr-lifecycle] Merge detected — checking ADR references"]

    # Gather text to search for ADR numbers
    branch_name = run_git(["branch", "--show-current"])
    recent_commits = run_git(["log", "-10", "--oneline"])
    search_text = f"{command} {branch_name} {recent_commits}"

    adr_numbers = extract_adr_numbers(search_text)
    if not adr_numbers:
        lines.append("[adr-lifecycle] No ADR references found in branch/commits")
        debug_log("No ADR references found")
        return "\n".join(lines)

    changed_files = get_changed_files()
    debug_log(f"Changed files: {changed_files}")

    for adr_num in adr_numbers:
        adr_path = find_adr_file(adr_num)
        if not adr_path:
            lines.append(f"[adr-lifecycle] ADR-{adr_num}: file not found in adr/ — skipping")
            debug_log(f"ADR-{adr_num} file not found")
            continue

        lines.append(f"[adr-lifecycle] Found: ADR-{adr_num} ({adr_path.name})")

        adr_content = ""
        try:
            adr_content = adr_path.read_text()
        except OSError as e:
            lines.append(f"[adr-lifecycle] Could not read ADR file: {e}")
            continue

        steps = extract_implementation_steps(adr_content)
        if not steps:
            lines.append(f"[adr-lifecycle] ADR-{adr_num}: no ## Implementation steps found")
            continue

        lines.append(f"[adr-lifecycle] Implementation checklist ({len(steps)} steps):")

        matched_count = 0
        for i, step in enumerate(steps, 1):
            matched, matched_file = step_matches_files(step, changed_files)
            if matched:
                matched_count += 1
                lines.append(f"  [x] Step {i}: {step} — {matched_file}")
            else:
                lines.append(f"  [ ] Step {i}: {step} — not found in merge")

        total = len(steps)
        if matched_count == total:
            lines.append(f"[adr-lifecycle] Status: COMPLETE ({matched_count}/{total} steps)")
            update_adr_status(adr_path, adr_num)
            lines.append(f"[adr-lifecycle] ADR-{adr_num} completed and moved to adr/completed/")
        else:
            lines.append(f"[adr-lifecycle] Status: PARTIAL ({matched_count}/{total} steps complete)")

    return "\n".join(lines)


def main() -> None:
    raw = read_stdin(timeout=3)
    if not raw.strip():
        empty_output(EVENT_NAME).print_and_exit()

    try:
        event = json.loads(raw)
    except json.JSONDecodeError as e:
        debug_log(f"JSON parse error: {e}")
        empty_output(EVENT_NAME).print_and_exit()

    tool_name = event.get("tool_name", "")
    if tool_name != "Bash":
        empty_output(EVENT_NAME).print_and_exit()

    tool_input = get_tool_input(event)
    command = tool_input.get("command", "")

    tool_output = event.get("tool_output", {})
    exit_code = tool_output.get("exit_code", 0)

    # Early exit: not a merge command or merge failed
    if not is_merge_command(command, exit_code):
        empty_output(EVENT_NAME).print_and_exit()

    debug_log(f"Processing merge command: {command[:80]}")

    context = process_merge(command)
    if context:
        context_output(EVENT_NAME, context).print_and_exit()
    else:
        empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        debug_log(f"HOOK-CRASH: {type(e).__name__}: {e}")
    finally:
        sys.exit(0)
