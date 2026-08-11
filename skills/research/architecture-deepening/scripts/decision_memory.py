#!/usr/bin/env python3
"""Build architecture identities and atomically append decision memory."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import secrets
import stat
import sys
from pathlib import Path, PurePosixPath
from typing import Any

import jsonschema
from fingerprint import BURDEN_KINDS, canonical_fingerprint, is_canonical_fingerprint, parse_fingerprint

SHARED_STORE = "docs/architecture-decisions.md"
LOCAL_STORE = ".local/architecture-decisions.md"
LOCK_PATH = ".local/architecture-decision-memory.lock"
SAFE_PATH = re.compile(
    r"^(?!.*(?:^|/)\.{1,2}(?:/|$))[A-Za-z0-9_.][A-Za-z0-9._-]*"
    r"(?:/[A-Za-z0-9_.][A-Za-z0-9._-]*)*$"
)
SCRIPT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MEMORY_SCHEMA = SCRIPT_ROOT / "references" / "decision-memory-record.schema.json"


def _require_printable_ascii(value: str, label: str) -> None:
    try:
        value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{label} must use printable ASCII") from exc
    if not value.isprintable():
        raise ValueError(f"{label} must use printable ASCII")


def _validate_repo_relative_path(value: str, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty repository-relative path")
    _require_printable_ascii(value, label)
    if not SAFE_PATH.fullmatch(value):
        raise ValueError(
            f"{label} must be repository-relative and contain no '.' or '..' segments, controls, "
            "shell metacharacters, backslashes, empty segments, or leading '-' segments"
        )
    return value


def resolve_repository_path(
    repo_root: Path,
    value: str,
    label: str,
    *,
    must_exist: bool = False,
    forbid_symlinks: bool = False,
) -> Path:
    """Resolve a safe relative path and prove it remains inside repo_root."""
    clean = _validate_repo_relative_path(value, label)
    root = repo_root.resolve()
    lexical = root / clean
    if forbid_symlinks:
        current = root
        for part in PurePosixPath(clean).parts:
            current /= part
            try:
                mode = current.lstat().st_mode
            except FileNotFoundError:
                break
            if stat.S_ISLNK(mode):
                raise ValueError(f"{label} must not contain a symbolic link")
    resolved = lexical.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} resolves outside the repository") from exc
    if must_exist and not resolved.is_file():
        raise ValueError(f"{label} does not name an existing file: {clean}")
    return resolved


def find_latest(store: Path, fingerprint: str) -> str | None:
    """Return the latest Markdown H2 block with the exact fingerprint."""
    return _find_latest_in_content(store.read_text(encoding="utf-8"), fingerprint)


def _find_latest_in_content(content: str, fingerprint: str) -> str | None:
    """Return the latest exact fingerprint block from already-read content."""
    blocks = re.split(r"(?=^##\s)", content, flags=re.MULTILINE)
    needle = f"- Fingerprint: {fingerprint}"
    matches = [block.rstrip() for block in blocks if needle in block.splitlines()]
    return matches[-1] if matches else None


def _load_schema(schema_path: Path) -> dict[str, Any]:
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
    except (OSError, json.JSONDecodeError, jsonschema.SchemaError) as exc:
        raise ValueError(f"invalid schema {schema_path}: {exc}") from exc
    return schema


def _validate_schema(instance: dict[str, Any], schema_path: Path, label: str) -> None:
    schema = _load_schema(schema_path)
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.absolute_path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise ValueError(f"invalid {label} at {location}: {error.message}")


def _validate_single_line(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty")
    if "\n" in value or "\r" in value or not value.isprintable():
        raise ValueError(f"{label} must be one printable line")


def _validate_memory_record(
    record: dict[str, Any],
    repo_root: Path,
    schema_path: Path,
) -> None:
    _validate_schema(record, schema_path, "decision-memory record")
    fingerprint_module, _symbol, _burden_kind = parse_fingerprint(record["fingerprint"])
    if fingerprint_module not in record["scope"]["modules"]:
        raise ValueError("fingerprint module must match one of scope.modules")
    for key in ("decision", "reopen_when"):
        _validate_single_line(record[key], key)
    for key in ("assumptions", "alternatives"):
        for index, value in enumerate(record[key]):
            _validate_single_line(value, f"{key}[{index}]")
    for group in ("modules", "callers"):
        for index, value in enumerate(record["scope"][group]):
            resolve_repository_path(repo_root, value, f"scope.{group}[{index}]")
    for index, value in enumerate(record["evidence"]):
        resolve_repository_path(repo_root, value, f"evidence[{index}]")
    supersedes = record["supersedes"]
    if supersedes is not None and not is_canonical_fingerprint(supersedes):
        raise ValueError("supersedes must be a canonical fingerprint")


def _validate_store_scope(store: Path, record: dict[str, Any]) -> None:
    store_posix = store.as_posix()
    scope = record["memory_scope"]
    expected = LOCAL_STORE if scope == "local" else SHARED_STORE
    if store_posix != expected:
        raise ValueError(f"{scope} decision memory must use {expected}")


def _render_record(record: dict[str, Any]) -> str:
    scope = record["scope"]
    supersedes = record["supersedes"] or "none"
    return (
        f"## {record['date']}: {record['fingerprint']}\n\n"
        f"- Outcome: {record['outcome']}\n"
        f"- Fingerprint: {record['fingerprint']}\n"
        f"- Memory scope: {record['memory_scope']}\n"
        f"- Modules: {', '.join(scope['modules'])}\n"
        f"- Callers: {', '.join(scope['callers'])}\n"
        f"- Decision: {record['decision']}\n"
        f"- Assumptions: {'; '.join(record['assumptions'])}\n"
        f"- Alternatives: {'; '.join(record['alternatives'])}\n"
        f"- Reopen when: {record['reopen_when']}\n"
        f"- Supersedes: {supersedes}\n"
        f"- Evidence: {', '.join(record['evidence'])}\n"
    )


def _open_directory(path: Path, label: str) -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValueError(f"{label} must be a real repository directory") from exc
    if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError(f"{label} must be a directory")
    return descriptor


def _read_store_at(directory: int, name: str) -> tuple[str, int] | None:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(name, flags, dir_fd=directory)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ValueError("decision store must not be a symbolic link") from exc
    mode = os.fstat(descriptor).st_mode
    if not stat.S_ISREG(mode):
        os.close(descriptor)
        raise ValueError("decision store must be a regular file")
    with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
        return handle.read(), mode


def _atomic_write(directory: int, name: str, content: str, existing_mode: int | None) -> None:
    temporary_name = f".{name}.{secrets.token_hex(12)}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(temporary_name, flags, 0o600, dir_fd=directory)
    try:
        if existing_mode is not None:
            os.fchmod(descriptor, stat.S_IMODE(existing_mode))
        handle = os.fdopen(descriptor, "w", encoding="utf-8")
        descriptor = -1
        with handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(
            temporary_name,
            name,
            src_dir_fd=directory,
            dst_dir_fd=directory,
        )
        os.fsync(directory)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary_name, dir_fd=directory)
        except FileNotFoundError:
            pass


def append_record(
    repo_root: Path,
    store: Path,
    record: dict[str, Any],
    schema_path: Path = DEFAULT_MEMORY_SCHEMA,
) -> Path:
    """Validate and atomically append one record while holding an advisory lock."""
    if store.is_absolute():
        raise ValueError("decision store must be repository-relative")
    store_text = store.as_posix()
    _validate_memory_record(record, repo_root, schema_path)
    _validate_store_scope(store, record)
    target = resolve_repository_path(
        repo_root,
        store_text,
        "decision store",
        forbid_symlinks=True,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target = resolve_repository_path(
        repo_root,
        store_text,
        "decision store",
        forbid_symlinks=True,
    )
    lock_path = resolve_repository_path(
        repo_root,
        LOCK_PATH,
        "decision store lock",
        forbid_symlinks=True,
    )
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = resolve_repository_path(
        repo_root,
        LOCK_PATH,
        "decision store lock",
        forbid_symlinks=True,
    )

    lock_flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        lock_flags |= os.O_NOFOLLOW
    lock_directory = _open_directory(lock_path.parent, "decision store lock directory")
    try:
        lock_descriptor = os.open(lock_path.name, lock_flags, 0o600, dir_fd=lock_directory)
    finally:
        os.close(lock_directory)
    with os.fdopen(lock_descriptor, "a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        target = resolve_repository_path(
            repo_root,
            store_text,
            "decision store",
            forbid_symlinks=True,
        )
        store_directory = _open_directory(target.parent, "decision store directory")
        try:
            stored = _read_store_at(store_directory, target.name)
            current, existing_mode = stored if stored is not None else ("# Architecture Decisions\n", None)
            supersedes = record["supersedes"]
            if supersedes is not None and _find_latest_in_content(current, supersedes) is None:
                raise ValueError("supersedes does not match an existing decision-memory entry")
            separator = "\n" if current.endswith("\n") else "\n\n"
            updated = f"{current}{separator}{_render_record(record)}"
            _atomic_write(store_directory, target.name, updated, existing_mode)
        finally:
            os.close(store_directory)
    return target


def _read_json_file(repo_root: Path, value: str, label: str) -> dict[str, Any]:
    path = resolve_repository_path(repo_root, value, label, must_exist=True)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    fingerprint = subparsers.add_parser("fingerprint", help="build a canonical fingerprint")
    fingerprint.add_argument("--module", required=True)
    fingerprint.add_argument("--symbol", required=True)
    fingerprint.add_argument("--burden-kind", required=True, choices=BURDEN_KINDS)

    find = subparsers.add_parser("find", help="print the latest exact matching decision block")
    find.add_argument("--repo-root", default=".", type=Path)
    find.add_argument("--store", required=True)
    find.add_argument("--fingerprint", required=True)

    validate = subparsers.add_parser("validate", help="validate a canonical fingerprint")
    validate.add_argument("--fingerprint", required=True)

    append = subparsers.add_parser("append", help="validate and atomically append one JSON record")
    append.add_argument("--repo-root", default=".", type=Path)
    append.add_argument("--store", required=True)
    append.add_argument("--record", required=True)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "fingerprint":
            print(canonical_fingerprint(args.module, args.symbol, args.burden_kind))
            return 0
        if args.command == "validate":
            return 0 if is_canonical_fingerprint(args.fingerprint) else 1
        if args.command == "append":
            root = args.repo_root.resolve()
            record = _read_json_file(root, args.record, "decision record")
            _validate_repo_relative_path(args.store, "decision store")
            target = append_record(root, Path(args.store), record)
            print(target.relative_to(root).as_posix())
            return 0
        root = args.repo_root.resolve()
        store_text = _validate_repo_relative_path(args.store, "decision store")
        if store_text not in {SHARED_STORE, LOCAL_STORE}:
            raise ValueError(f"decision store must be {SHARED_STORE} or {LOCAL_STORE}")
        store = resolve_repository_path(
            root,
            store_text,
            "decision store",
            must_exist=True,
            forbid_symlinks=True,
        )
        if not is_canonical_fingerprint(args.fingerprint):
            raise ValueError("fingerprint is not canonical")
        match = find_latest(store, args.fingerprint)
        if match is None:
            return 1
        print(match)
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
