#!/usr/bin/env python3
"""Atomically write one contained repository artifact through directory fds."""

from __future__ import annotations

import argparse
import os
import re
import secrets
import stat
import sys
from pathlib import Path, PurePosixPath

SAFE_PATH = re.compile(
    r"^(?!.*(?:^|/)\.{1,2}(?:/|$))[A-Za-z0-9_.][A-Za-z0-9._-]*"
    r"(?:/[A-Za-z0-9_.][A-Za-z0-9._-]*)*$"
)


def validate_relative_path(value: str, label: str = "artifact path") -> str:
    """Return a safe repository-relative POSIX path."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty repository-relative path")
    try:
        value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{label} must use printable ASCII") from exc
    if not value.isprintable() or not SAFE_PATH.fullmatch(value):
        raise ValueError(
            f"{label} must be repository-relative and contain no traversal, controls, "
            "shell metacharacters, backslashes, empty segments, or leading '-' segments"
        )
    return value


def _directory_flags() -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def _open_root(repo_root: Path) -> int:
    try:
        descriptor = os.open(repo_root, _directory_flags())
    except OSError as exc:
        raise ValueError("repository root must be a real directory") from exc
    if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError("repository root must be a directory")
    return descriptor


def _open_directory_at(parent_fd: int, name: str, label: str) -> int:
    try:
        descriptor = os.open(name, _directory_flags(), dir_fd=parent_fd)
    except OSError as exc:
        raise ValueError(f"{label} must contain only real directories") from exc
    if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError(f"{label} must contain only directories")
    return descriptor


def _walk_directories(root_fd: int, parts: tuple[str, ...], *, create: bool, label: str) -> int:
    current = os.dup(root_fd)
    try:
        for part in parts:
            try:
                child = _open_directory_at(current, part, label)
            except ValueError:
                if not create:
                    raise
                try:
                    os.mkdir(part, 0o700, dir_fd=current)
                    os.fsync(current)
                except FileExistsError:
                    pass
                child = _open_directory_at(current, part, label)
            os.close(current)
            current = child
        return current
    except BaseException:
        os.close(current)
        raise


def _existing_mode(directory_fd: int, name: str) -> int | None:
    try:
        info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(info.st_mode):
        raise ValueError("artifact target must not be a symbolic link")
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("artifact target must be a regular file")
    return stat.S_IMODE(info.st_mode)


def atomic_write(
    repo_root: Path,
    relative_path: str,
    content: bytes,
    *,
    allowed_root: str | None = None,
    mode: int = 0o600,
) -> Path:
    """Validate containment, then write by openat + O_NOFOLLOW + atomic replace."""
    clean = validate_relative_path(relative_path)
    path_parts = PurePosixPath(clean).parts
    if allowed_root is not None:
        clean_root = validate_relative_path(allowed_root, "allowed root")
        root_parts = PurePosixPath(clean_root).parts
        if path_parts[: len(root_parts)] != root_parts or len(path_parts) <= len(root_parts):
            raise ValueError(f"artifact path must be below {clean_root}/")
    else:
        root_parts = ()

    root_fd = _open_root(repo_root)
    anchor_fd = parent_fd = -1
    temporary_name: str | None = None
    try:
        anchor_fd = _walk_directories(root_fd, root_parts, create=False, label="allowed root")
        remaining_parent = path_parts[len(root_parts) : -1]
        parent_fd = _walk_directories(anchor_fd, remaining_parent, create=True, label="artifact parent")
        name = path_parts[-1]
        existing_mode = _existing_mode(parent_fd, name)
        temporary_name = f".{name}.{secrets.token_hex(12)}.tmp"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(temporary_name, flags, existing_mode or mode, dir_fd=parent_fd)
        try:
            if existing_mode is not None:
                os.fchmod(descriptor, existing_mode)
            view = memoryview(content)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temporary_name, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        temporary_name = None
        os.fsync(parent_fd)
    finally:
        if temporary_name is not None and parent_fd >= 0:
            try:
                os.unlink(temporary_name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        for descriptor in (parent_fd, anchor_fd, root_fd):
            if descriptor >= 0:
                os.close(descriptor)
    return repo_root.resolve() / clean


def atomic_write_text(
    repo_root: Path,
    relative_path: str,
    content: str,
    *,
    allowed_root: str | None = None,
    mode: int = 0o600,
) -> Path:
    return atomic_write(repo_root, relative_path, content.encode("utf-8"), allowed_root=allowed_root, mode=mode)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    write = subparsers.add_parser("write", help="write stdin to one repository artifact")
    write.add_argument("--repo-root", type=Path, default=Path("."))
    write.add_argument("--path", required=True)
    write.add_argument("--allowed-root")
    write.add_argument("--mode", default="600")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        mode = int(args.mode, 8)
        if not 0 <= mode <= 0o777:
            raise ValueError("mode must be an octal permission value from 000 through 777")
        target = atomic_write(
            args.repo_root,
            args.path,
            sys.stdin.buffer.read(),
            allowed_root=args.allowed_root,
            mode=mode,
        )
        print(target.relative_to(args.repo_root.resolve()).as_posix())
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
