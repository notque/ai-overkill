#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PostToolUse Hook: Post-Rename Reference Sweep

After a `git mv` command, scans .py/.json/.md/.yaml files for stale
references to the old filename stem and prints a warning listing them.

Design Principles:
- SILENT by default (only speaks when stale references are found)
- Non-blocking (informational only — always exits 0)
- Fast exit path for non-matching commands (<50ms requirement)

ADR: adr/129-post-rename-reference-sweep.md
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import get_tool_input, get_tool_result, hook_error, is_tool_error
from stdin_timeout import read_stdin


def extract_git_mv_paths(command: str):
    """Extract (old_path, new_path) from a git mv command string.

    Handles:
    - Simple: git mv old new
    - With flags: git mv -f old new, git mv --force old new
    - Quoted: git mv "old path" "new path"
    - Chained: git mv old new && git add .

    Returns None if the pattern is not found.
    """
    # Skip optional flags (-f, --force, -k, -n, -v, etc.) before positional args
    # Then match either quoted or unquoted path arguments
    # Unquoted paths stop at whitespace, semicolons, pipes, and ampersands
    pattern = r"git\s+mv\s+(?:-\S+\s+)*(?:(['\"])(.+?)\1|([^\s;&|]+))\s+(?:(['\"])(.+?)\4|([^\s;&|]+))"
    match = re.search(pattern, command)
    if not match:
        return None
    # Groups: 1=old_quote, 2=old_quoted_path, 3=old_unquoted_path,
    #         4=new_quote, 5=new_quoted_path, 6=new_unquoted_path
    old_path = match.group(2) or match.group(3)
    new_path = match.group(5) or match.group(6)
    return old_path, new_path


def grep_for_stem(stem: str, search_root: str) -> list:
    """Run grep for stem across .py/.json/.md/.yaml files.

    Returns a list of "file:line: text" strings (may be empty).
    Excludes .git/ and __pycache__/.
    """
    try:
        result = subprocess.run(
            [
                "grep",
                "-rnF",
                "--include=*.py",
                "--include=*.json",
                "--include=*.md",
                "--include=*.yaml",
                "--include=*.yml",
                "--exclude-dir=.git",
                "--exclude-dir=__pycache__",
                stem,
                search_root,
            ],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode not in (0, 1):
            # returncode 1 means no matches (normal), >1 is an error
            return []
        lines = [l for l in result.stdout.splitlines() if l.strip()]
        return lines
    except subprocess.TimeoutExpired:
        return []
    except Exception:
        return []


def main():
    try:
        raw = read_stdin(timeout=5)
        if not raw:
            return

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return

        tool_name = data.get("tool_name", "")
        if tool_name != "Bash":
            return

        # Skip failed git mv commands — no rename happened
        tool_result = get_tool_result(data)
        if is_tool_error(tool_result):
            return

        tool_input = get_tool_input(data)
        command = tool_input.get("command", "")

        if "git mv" not in command:
            return

        paths = extract_git_mv_paths(command)
        if not paths:
            return

        old_path, new_path = paths

        # Extract stem: strip directory and extension
        stem = Path(old_path).stem
        if not stem or len(stem) < 3:
            return

        # Search from the repo root if possible, else cwd
        search_root = os.getcwd()

        matches = grep_for_stem(stem, search_root)
        if not matches:
            return

        # Filter out matches in the renamed file itself (new_path)
        new_path_abs = str(Path(new_path).resolve())
        filtered = []
        for line in matches:
            match_file = line.split(":")[0]
            try:
                if Path(match_file).resolve() == Path(new_path_abs):
                    continue
            except Exception:
                pass
            filtered.append(line)

        if not filtered:
            return

        max_shown = 20
        print(f'[rename-sweep] Stale references to "{stem}" found after git mv:')
        for line in filtered[:max_shown]:
            # Make path relative to search_root for readability
            try:
                rel = os.path.relpath(line.split(":")[0], search_root)
                rest = ":".join(line.split(":")[1:])
                print(f"  {rel}:{rest}")
            except Exception:
                print(f"  {line}")
        if len(filtered) > max_shown:
            print(f"  ... and {len(filtered) - max_shown} more")
        print("Consider updating these references before committing.")

    except Exception as e:
        hook_error("posttool-rename-sweep", e)
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
