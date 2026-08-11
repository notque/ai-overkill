#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse:Write,Edit Hook: Plan Gate

Blocks implementation when task_plan.md doesn't exist in the project root.
Forces agents to create a plan before writing implementation code.

This is a HARD GATE — exits 0 with JSON permissionDecision:deny to block the Write/Edit tool.

Detection logic:
- Tool is Write or Edit
- Target resolves inside the project-root agents/ or skills/ directory
- task_plan.md does not exist in the project root

Allow-through conditions:
- Target file is NOT in agents/, skills/
- task_plan.md exists in the project root
- PLAN_GATE_BYPASS=1 env var (for use by the plans skill itself)
"""

import json
import os
import sys
import traceback
from pathlib import Path
from typing import NoReturn

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import deny_tool_use, hook_error
from stdin_timeout import read_stdin

_BYPASS_ENV = "PLAN_GATE_BYPASS"
_PROJECT_DIR_ENV = "CLAUDE_PROJECT_DIR"

_GATED_DIRECTORIES = ("agents", "skills")
_GATED = "gated"
_ALLOW = "allow"
_UNSAFE = "unsafe"


def _input_path(value: str) -> Path:
    """Return a platform path for a hook path using either slash style."""
    return Path(value.replace("\\", "/"))


def _existing_directory(value: object) -> Path | None:
    """Resolve an absolute directory from trusted hook context."""
    if not isinstance(value, str) or not value or "\x00" in value:
        return None
    try:
        path = _input_path(value)
        if not path.is_absolute():
            return None
        resolved = path.resolve(strict=True)
        return resolved if resolved.is_dir() else None
    except (OSError, RuntimeError, ValueError):
        return None


def _git_root(start: Path) -> Path | None:
    """Find the nearest Git root, including worktrees with a .git file."""
    for candidate in (start, *start.parents):
        try:
            if (candidate / ".git").exists():
                return candidate
        except OSError:
            continue
    return None


def _project_root(event_cwd: object) -> Path | None:
    """Resolve the project root from the hook contract, then Git metadata."""
    project_dir = _existing_directory(os.environ.get(_PROJECT_DIR_ENV))
    if project_dir is not None:
        return _git_root(project_dir) or project_dir

    cwd = _existing_directory(event_cwd)
    if cwd is not None:
        return _git_root(cwd)
    return None


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _mentions_gated_directory(file_path: str) -> bool:
    """Identify a gated-looking path when no safe root can be resolved."""
    try:
        return any(part in _GATED_DIRECTORIES for part in _input_path(file_path).parts)
    except (OSError, ValueError):
        return False


def _target_status(file_path: str, event_cwd: object, root: Path) -> str:
    """Classify a normalized target as allowed, gated, or unsafe."""
    if not file_path or "\x00" in file_path:
        return _UNSAFE

    raw_path = _input_path(file_path)
    is_relative = not raw_path.is_absolute()
    if is_relative:
        base_dir = _existing_directory(event_cwd)
        if base_dir is None:
            return _UNSAFE
        candidate = base_dir / raw_path
    else:
        candidate = raw_path

    try:
        lexical = Path(os.path.normpath(str(candidate)))
        canonical = candidate.resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return _UNSAFE

    lexical_in_project = _is_within(lexical, root)
    canonical_in_project = _is_within(canonical, root)

    # A relative tool path belongs to this project. Do not let traversal or a
    # symlink move it outside the root selected by the hook contract.
    if is_relative and (not lexical_in_project or not canonical_in_project):
        return _UNSAFE
    if lexical_in_project and not canonical_in_project:
        return _UNSAFE

    root_plan = root / "task_plan.md"
    if lexical == root_plan and canonical == root_plan:
        return _ALLOW

    for directory in _GATED_DIRECTORIES:
        lexical_root = root / directory
        try:
            canonical_root = lexical_root.resolve(strict=False)
        except (OSError, RuntimeError, ValueError):
            return _UNSAFE

        lexically_gated = _is_within(lexical, lexical_root)
        if lexically_gated and not _is_within(canonical_root, root):
            return _UNSAFE
        if _is_within(canonical, canonical_root):
            return _GATED
        if lexically_gated:
            return _UNSAFE

    return _ALLOW


def _deny(reason: str, *, stderr_message: str, fix_with_plans: bool = False) -> NoReturn:
    print(f"[plan-gate] BLOCKED: {stderr_message}", file=sys.stderr)
    if fix_with_plans:
        print("[fix-with-skill] plans", file=sys.stderr)
    deny_tool_use("PreToolUse", reason)
    sys.exit(0)


def _root_plan_exists(root: Path) -> bool:
    """Return whether the exact root plan is a regular file, not a symlink."""
    plan_path = root / "task_plan.md"
    try:
        resolved = plan_path.resolve(strict=True)
        return resolved == plan_path and resolved.is_file()
    except (OSError, RuntimeError, ValueError):
        return False


def main() -> None:
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    # tool_name filter removed — matcher "Write|Edit" in settings.json prevents
    # this hook from spawning for non-matching tools.

    # Bypass env var — set by the plans skill itself.
    if os.environ.get(_BYPASS_ENV) == "1":
        if debug:
            print(f"[plan-gate] Bypassed via {_BYPASS_ENV}=1", file=sys.stderr)
        sys.exit(0)

    if not isinstance(event, dict):
        sys.exit(0)

    tool_input = event.get("tool_input", {})
    if not isinstance(tool_input, dict):
        sys.exit(0)
    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not file_path:
        sys.exit(0)

    root = _project_root(event.get("cwd"))
    if root is None:
        if _input_path(file_path).is_absolute() and not _mentions_gated_directory(file_path):
            sys.exit(0)
        _deny(
            "Cannot resolve the project root safely for this edit.",
            stderr_message="Cannot resolve the project root safely.",
        )

    status = _target_status(file_path, event.get("cwd"), root)
    if status == _UNSAFE:
        _deny(
            "Target path cannot be resolved safely inside the project.",
            stderr_message="Target path escapes the project or cannot be resolved safely.",
        )
    if status == _ALLOW:
        if debug:
            print(f"[plan-gate] Not a gated path, allowing: {file_path}", file=sys.stderr)
        sys.exit(0)

    if _root_plan_exists(root):
        if debug:
            print(
                f"[plan-gate] task_plan.md found at {root / 'task_plan.md'} — allowing through",
                file=sys.stderr,
            )
        sys.exit(0)

    _deny(
        "Create task_plan.md before modifying implementation code in agents/ or skills/. "
        "Use the planning skill to create one.",
        stderr_message="Create task_plan.md before modifying implementation code.",
        fix_with_plans=True,
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(0) propagate normally
    except Exception as e:
        hook_error("pretool-plan-gate", e)
    finally:
        sys.exit(0)
