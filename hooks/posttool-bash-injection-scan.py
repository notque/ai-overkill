#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PostToolUse:Bash Hook: Bash Injection Scan

Scans files written by Bash commands for LLM-level prompt injection patterns.

When a Bash command contains file-write indicators (>, >>, tee, cp) targeting
agent context paths, this hook reads the affected file and scans it with the
shared injection pattern library.

ADVISORY ONLY — exit 0 always. Never blocks execution.

ADR: adr/121-injection-scanner-hardening.md
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output, get_tool_input, hook_error
from injection_patterns import scan_content
from stdin_timeout import read_stdin

EVENT_NAME = "PostToolUse"

# ═══════════════════════════════════════════════════════════════
# CONTEXT PATH PATTERNS — only scan files that enter agent context
# ═══════════════════════════════════════════════════════════════

_CONTEXT_PATH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"/agents/[^/]+\.md$"),
    re.compile(r"/skills/(?:[^/]+/)?[^/]+/SKILL\.md$"),
    re.compile(r"/hooks/[^/]+\.py$"),
    re.compile(r"/commands/[^/]+/SKILL\.md$"),
    re.compile(r"/adr/[^/]+\.md$"),
    re.compile(r"CLAUDE\.md$"),
    re.compile(r"task_plan\.md$"),
    re.compile(r"HANDOFF\.json$"),
    re.compile(r"\.continue-here\.md$"),
]

# Patterns that indicate a Bash command writes to a file.
# Group 1 captures the destination path where extractable.
_WRITE_PATTERNS: list[re.Pattern[str]] = [
    # Redirect: cmd > path  or  cmd >> path
    re.compile(r">>\s*(\S+)"),
    re.compile(r"(?<![>])>\s*(\S+)"),
    # tee: tee [-a] path
    re.compile(r"\btee\b(?:\s+-a)?\s+(\S+)"),
    # cp: cp src dest
    re.compile(r"\bcp\b\s+\S+\s+(\S+)"),
]


def _extract_written_paths(command: str) -> list[str]:
    """Return candidate file paths that a Bash command may have written to."""
    paths: list[str] = []
    for pattern in _WRITE_PATTERNS:
        for m in pattern.finditer(command):
            candidate = m.group(1).strip("'\";")
            if candidate:
                paths.append(candidate)
    return paths


def _is_context_path(path: str) -> bool:
    """Return True if path matches an agent context pattern."""
    return any(p.search(path) for p in _CONTEXT_PATH_PATTERNS)


def _resolve_path(raw: str) -> Path | None:
    """Resolve a raw path string to an absolute Path, or return None."""
    try:
        p = Path(raw).expanduser()
        if not p.is_absolute():
            p = Path.cwd() / p
        return p.resolve()
    except (ValueError, OSError):
        return None


def main() -> None:
    raw = read_stdin(timeout=2)
    if not raw:
        empty_output(EVENT_NAME).print_and_exit()

    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        empty_output(EVENT_NAME).print_and_exit()

    tool_name = event.get("tool_name") or event.get("tool", "")
    if tool_name not in ("Bash", "run_shell_command"):
        empty_output(EVENT_NAME).print_and_exit()

    tool_input = get_tool_input(event)
    command = tool_input.get("command", "")
    if not command:
        empty_output(EVENT_NAME).print_and_exit()

    # Find candidate paths written by the command
    candidate_paths = _extract_written_paths(command)
    if not candidate_paths:
        empty_output(EVENT_NAME).print_and_exit()

    # Filter to context paths that exist on disk
    context_files: list[Path] = []
    for raw_path in candidate_paths:
        if not _is_context_path(raw_path):
            continue
        resolved = _resolve_path(raw_path)
        if resolved and resolved.is_file():
            context_files.append(resolved)

    if not context_files:
        empty_output(EVENT_NAME).print_and_exit()

    # Scan each context file
    all_warnings: list[str] = []
    for file_path in context_files:
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        findings = scan_content(content, source_label=str(file_path))
        for f in findings:
            if f["category"] == "invisible-unicode":
                all_warnings.append(
                    f"[bash-injection-scan] Invisible Unicode in {f['location']}\n"
                    f"  Category: {f['category']}\n"
                    f"  Pattern: {f['snippet']}\n"
                    f"  Risk: {f['risk']}\n"
                    f"  Action: Review file written by Bash before it enters agent context"
                )
            else:
                all_warnings.append(
                    f"[bash-injection-scan] Potential prompt injection in {f['location']}\n"
                    f"  Category: {f['category']}\n"
                    f"  Pattern: {f['snippet']}\n"
                    f"  Risk: {f['risk']}\n"
                    f"  Action: Review file written by Bash before it enters agent context"
                )

    if not all_warnings:
        empty_output(EVENT_NAME).print_and_exit()

    header = f"[bash-injection-scan] {len(all_warnings)} potential injection pattern(s) in Bash-written file(s):"
    full_output = header + "\n\n" + "\n\n".join(all_warnings)

    if os.environ.get("CLAUDE_HOOKS_DEBUG"):
        print(
            f"[bash-injection-scan] {len(all_warnings)} warnings across {len(context_files)} file(s)",
            file=sys.stderr,
        )

    context_output(EVENT_NAME, full_output).print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        # Fail OPEN — advisory hook must never crash the session
        print(f"[bash-injection-scan] FATAL: hook crashed: {e}", file=sys.stderr)
        sys.exit(0)
