#!/usr/bin/env python3
# hook-version: 1.2.0
"""
PreToolUse:Bash Hook: Ruff Format Gate

Blocks git push when changed Python files fail ruff format --check.
Forces agents to run ruff format before pushing, preventing CI failures.

This is a HARD GATE — exits 0 with JSON permissionDecision:deny to block the Bash tool.

Detection logic:
- Tool is Bash
- Command contains 'git push'
- pyproject.toml with [tool.ruff] exists in project root
- Changed .py/.pyi files are discovered in the command's actual worktree
- ruff format --check <changed files> --config pyproject.toml exits non-zero

Allow-through conditions:
- Command does not contain 'git push'
- No pyproject.toml with [tool.ruff] section (non-Python project)
- No changed Python files (Markdown and other languages are ignored)
- ruff format --check passes for the changed Python files
- RUFF_FORMAT_GATE_BYPASS=1 env var

Exit code semantics:
- Always exits 0 (non-blocking requirement)
- Deny signal delivered via JSON permissionDecision:deny on stdout
"""

import json
import os
import re
import shlex
import subprocess
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import deny_tool_use, hook_error
from stdin_timeout import read_stdin

_BYPASS_ENV = "RUFF_FORMAT_GATE_BYPASS"


def _find_project_root(cwd: str | None) -> Path | None:
    """Walk up from cwd to find the nearest pyproject.toml with [tool.ruff]."""
    if not cwd:
        return None
    candidate = Path(cwd).resolve()
    for _ in range(6):  # Max 6 levels up
        toml = candidate / "pyproject.toml"
        if toml.is_file():
            try:
                content = toml.read_text(encoding="utf-8")
                if "[tool.ruff]" in content:
                    return candidate
            except OSError:
                pass
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    return None


def _push_cwds(command: str, default_cwd: str | None) -> list[Path]:
    """Return effective worktree contexts for every push in shell order."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars="();&|{}")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return []

    current = Path(default_cwd).expanduser().resolve() if default_cwd else None
    cwd_stack: list[Path | None] = []
    pushes: list[Path] = []
    segment: list[str] = []

    def execute(argv: list[str]) -> None:
        nonlocal current
        while argv and argv[0] in {"$", "builtin"}:
            argv = argv[1:]
        if argv[:1] == ["command"]:
            argv = argv[1:]
            while argv and (argv[0] == "--" or argv[0] in {"-p", "-v", "-V"}):
                argv = argv[1:]
        if argv[:1] == ["env"]:
            argv = argv[1:]
            while argv and ("=" in argv[0] or argv[0].startswith("-")):
                argv = argv[1:]
        while argv and "=" in argv[0] and not argv[0].startswith("-"):
            argv = argv[1:]

        if argv[:1] == ["cd"] and len(argv) >= 2:
            path = Path(argv[1]).expanduser()
            if not path.is_absolute() and current:
                path = current / path
            current = path.resolve()
            return
        if argv[:1] != ["git"]:
            return

        git_cwd = current
        value_options = {
            "-c",
            "-C",
            "--config-env",
            "--exec-path",
            "--git-dir",
            "--namespace",
            "--super-prefix",
            "--work-tree",
        }
        index = 1
        while index < len(argv):
            arg = argv[index]
            if arg in value_options and index + 1 < len(argv):
                if arg == "-C":
                    path = Path(argv[index + 1]).expanduser()
                    if not path.is_absolute() and current:
                        path = current / path
                    git_cwd = path.resolve()
                index += 2
                continue
            if any(arg.startswith(f"{option}=") for option in value_options if option.startswith("--")):
                index += 1
                continue
            if arg.startswith("-"):
                index += 1
                continue
            if arg == "push" and git_cwd is not None:
                pushes.append(git_cwd)
            return

    for token in [*tokens, ";"]:
        if token and all(char in "();&|{}" for char in token):
            execute(segment)
            segment = []
            for punctuation in token:
                if punctuation == "(":
                    cwd_stack.append(current)
                elif punctuation == ")" and cwd_stack:
                    current = cwd_stack.pop()
            continue
        segment.append(token)
    return pushes


def _push_cwd(command: str, default_cwd: str | None) -> Path | None:
    """Compatibility helper returning the first push context."""
    contexts = _push_cwds(command, default_cwd)
    return contexts[0] if contexts else None


def _git_paths(project_root: Path, args: list[str]) -> list[str]:
    """Run a NUL-delimited Git path query, returning no paths on failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(project_root),
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []
    if result.returncode != 0:
        return []
    return [path for path in result.stdout.split("\0") if path]


def _changed_python_files(project_root: Path) -> list[Path]:
    """Return changed, existing Python files relative to this worktree.

    Include committed branch changes plus staged, unstaged, and untracked work.
    Never pass directories or non-Python documents to Ruff.
    """
    paths: set[str] = set()

    # Prefer the configured integration line. Critically, a valid empty diff
    # is final; it must not trigger a fallback into stale repository history.
    bases = ["origin/dev", "dev", "@{upstream}", "origin/main", "main", "origin/HEAD", "HEAD^"]
    for base in bases:
        merge_base = _git_paths(project_root, ["merge-base", "HEAD", base])
        if merge_base:
            revision = merge_base[0].strip()
            paths.update(
                _git_paths(
                    project_root,
                    ["diff", "--name-only", "-z", "--diff-filter=ACMR", f"{revision}..HEAD"],
                )
            )
            break

    paths.update(_git_paths(project_root, ["diff", "--name-only", "-z", "--diff-filter=ACMR"]))
    paths.update(
        _git_paths(
            project_root,
            ["diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"],
        )
    )
    paths.update(_git_paths(project_root, ["ls-files", "--others", "--exclude-standard", "-z"]))

    return sorted(
        Path(path) for path in paths if Path(path).suffix in {".py", ".pyi"} and (project_root / path).is_file()
    )


def _run_ruff_format_check(project_root: Path, files: list[Path]) -> tuple[int, str]:
    """Run ruff format --check on explicit changed files in project_root.

    Returns (return_code, combined_output).
    """
    try:
        result = subprocess.run(
            [
                "ruff",
                "format",
                "--check",
                *(str(path) for path in files),
                "--config",
                "pyproject.toml",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(project_root),
        )
        output = (result.stdout + result.stderr).strip()
        return result.returncode, output
    except FileNotFoundError:
        # ruff not installed — fail open, don't block
        return 0, ""
    except subprocess.TimeoutExpired:
        return 0, ""
    except OSError:
        return 0, ""


def main() -> None:
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if not isinstance(event, dict):
        sys.exit(0)

    command = event.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    # Bypass env var
    if os.environ.get(_BYPASS_ENV) == "1":
        if debug:
            print("[ruff-format-gate] Bypassed via RUFF_FORMAT_GATE_BYPASS=1", file=sys.stderr)
        sys.exit(0)

    default_cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")
    push_contexts = _push_cwds(command, default_cwd)
    if not push_contexts:
        sys.exit(0)

    output = ""
    for effective_cwd in push_contexts:
        project_root = _find_project_root(str(effective_cwd))
        if project_root is None:
            continue
        if debug:
            print(f"[ruff-format-gate] Running ruff format --check in {project_root}", file=sys.stderr)
        changed_python = _changed_python_files(project_root)
        if not changed_python:
            continue
        returncode, output = _run_ruff_format_check(project_root, changed_python)
        if returncode != 0:
            break
    else:
        sys.exit(0)

    # Violations found — block the push
    print(
        f"[ruff-format-gate] BLOCKED: ruff format --check found violations. Run: ruff format . --config pyproject.toml",
        file=sys.stderr,
    )
    if output and debug:
        print(f"[ruff-format-gate] ruff output: {output}", file=sys.stderr)

    deny_reason = (
        "ruff format --check found formatting violations. "
        "Run `ruff format . --config pyproject.toml` to fix them, then push again. "
        "Bypass with RUFF_FORMAT_GATE_BYPASS=1 if this is a false positive."
    )
    if output:
        # Include a snippet of ruff's output in the reason for visibility
        snippet = output[:300] + ("..." if len(output) > 300 else "")
        deny_reason = f"{deny_reason}\n\nruff output:\n{snippet}"

    deny_tool_use("PreToolUse", deny_reason)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(0) propagate normally
    except Exception as e:
        hook_error("pretool-ruff-format-gate", e)
    finally:
        sys.exit(0)
