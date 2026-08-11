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
import stat
import sys
import traceback
from pathlib import Path
from typing import NoReturn

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import deny_tool_use, hook_error
from stdin_timeout import read_stdin

_BYPASS_ENV = "PLAN_GATE_BYPASS"
_PROJECT_DIR_ENV = "CLAUDE_PROJECT_DIR"
_MAX_GIT_METADATA_BYTES = 4096

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


def _real_directory(path: Path) -> bool:
    """Return whether path is a directory, excluding symlinks."""
    try:
        return stat.S_ISDIR(path.lstat().st_mode)
    except OSError:
        return False


def _regular_file(path: Path) -> bool:
    """Return whether path is a regular file, excluding symlinks."""
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False


def _entry_present(path: Path) -> bool:
    """Treat inaccessible entries as present so root selection fails closed."""
    try:
        path.lstat()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return True


def _metadata_line(path: Path) -> str | None:
    """Read one bounded metadata line without following a final symlink."""
    if not _regular_file(path):
        return None
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except (OSError, TypeError, ValueError):
        return None

    try:
        file_stat = os.fstat(descriptor)
        if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_size > _MAX_GIT_METADATA_BYTES:
            return None
        data = os.read(descriptor, _MAX_GIT_METADATA_BYTES + 1)
    except OSError:
        return None
    finally:
        os.close(descriptor)

    if len(data) > _MAX_GIT_METADATA_BYTES or b"\x00" in data:
        return None
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return None
    if len(lines) != 1 or not lines[0].strip():
        return None
    return lines[0].strip()


def _valid_head(git_dir: Path) -> bool:
    head = _metadata_line(git_dir / "HEAD")
    if head is None:
        return False
    if len(head) in {40, 64} and all(character in "0123456789abcdefABCDEF" for character in head):
        return True
    if not head.startswith("ref: refs/"):
        return False
    ref = head.removeprefix("ref: ")
    invalid = ("..", "//", "@{", "\\", "~", "^", ":", "?", "*", "[")
    if any(token in ref for token in invalid) or any(
        ord(character) <= 32 or ord(character) == 127 for character in ref
    ):
        return False
    parts = ref.split("/")
    return all(part and not part.startswith(".") and not part.endswith((".", ".lock")) for part in parts)


def _valid_common_git_dir(git_dir: Path) -> bool:
    return (
        _real_directory(git_dir)
        and _valid_head(git_dir)
        and _real_directory(git_dir / "objects")
        and _real_directory(git_dir / "refs")
        and _regular_file(git_dir / "config")
    )


def _resolve_metadata_path(value: str, base: Path) -> Path | None:
    try:
        path = _input_path(value)
        if not path.is_absolute():
            path = base / path
        return path.resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return None


def _valid_linked_worktree(candidate: Path, marker: Path) -> bool:
    marker_line = _metadata_line(marker)
    if marker_line is None or not marker_line.startswith("gitdir: "):
        return False

    git_dir = _resolve_metadata_path(marker_line.removeprefix("gitdir: "), candidate)
    if git_dir is None or not _real_directory(git_dir) or not _valid_head(git_dir):
        return False

    common_line = _metadata_line(git_dir / "commondir")
    backlink_line = _metadata_line(git_dir / "gitdir")
    if common_line is None or backlink_line is None:
        return False

    common_dir = _resolve_metadata_path(common_line, git_dir)
    backlink = _resolve_metadata_path(backlink_line, git_dir)
    try:
        marker_path = marker.resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return False
    if common_dir is None or backlink is None or backlink != marker_path:
        return False
    if not _valid_common_git_dir(common_dir):
        return False

    worktrees_dir = common_dir / "worktrees"
    if not _real_directory(worktrees_dir) or git_dir.parent != worktrees_dir:
        return False

    outer_markers = [parent / ".git" for parent in candidate.parents if _entry_present(parent / ".git")]
    if not outer_markers:
        return True
    outer_git_dirs = [marker for marker in outer_markers if _valid_common_git_dir(marker)]
    return common_dir in outer_git_dirs


def _git_root(start: Path, *, reject_nested: bool) -> Path | None:
    """Find one structurally valid repository or linked-worktree root."""
    linked_roots: list[Path] = []
    repository_roots: list[Path] = []
    for candidate in (start, *start.parents):
        marker = candidate / ".git"
        if _valid_linked_worktree(candidate, marker):
            linked_roots.append(candidate)
        elif _valid_common_git_dir(marker):
            repository_roots.append(candidate)

    if len(linked_roots) == 1:
        return linked_roots[0]
    if linked_roots or not repository_roots:
        return None
    if reject_nested and len(repository_roots) != 1:
        return None
    return repository_roots[0]


def _project_root(event_cwd: object, *, require_repository: bool) -> Path | None:
    """Resolve the project root from the hook contract, then Git metadata."""
    project_dir = _existing_directory(os.environ.get(_PROJECT_DIR_ENV))
    if project_dir is not None:
        git_root = _git_root(project_dir, reject_nested=require_repository)
        if git_root is not None:
            return git_root
        return None if require_repository else project_dir

    cwd = _existing_directory(event_cwd)
    if cwd is not None:
        return _git_root(cwd, reject_nested=require_repository)
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

    require_repository = not _input_path(file_path).is_absolute() or "codex_tool_name" in event
    root = _project_root(event.get("cwd"), require_repository=require_repository)
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
