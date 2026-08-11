#!/usr/bin/env python3
"""Validate and safely write typed workflow handoffs."""

from __future__ import annotations

import argparse
import importlib.util
import json
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

import jsonschema
from repository_artifact import atomic_write_text, validate_relative_path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SCHEMA = (
    SCRIPT_DIR.parent / "skills" / "shared-patterns" / "schemas" / "architecture-change-handoff.schema.json"
)
ADR_QUERY = SCRIPT_DIR / "adr-query.py"
HANDOFF_ROOT = "adr/handoffs"
SHARED_STORE = "docs/architecture-decisions.md"
LOCAL_STORE = ".local/architecture-decisions.md"
ARCHITECTURE_FINGERPRINT = (
    SCRIPT_DIR.parent / "skills" / "research" / "architecture-deepening" / "scripts" / "fingerprint.py"
)


def _load_schema(path: Path) -> dict[str, Any]:
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
    except (OSError, json.JSONDecodeError, jsonschema.SchemaError) as exc:
        raise ValueError(f"invalid handoff schema {path}: {exc}") from exc
    return schema


def _validate_schema(handoff: dict[str, Any], schema_path: Path) -> None:
    validator = jsonschema.Draft202012Validator(
        _load_schema(schema_path),
        format_checker=jsonschema.FormatChecker(),
    )
    errors = sorted(validator.iter_errors(handoff), key=lambda error: list(error.absolute_path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise ValueError(f"invalid handoff at {location}: {error.message}")


def _resolve_contained(
    repo_root: Path,
    value: str,
    label: str,
    *,
    must_exist: bool = False,
    forbid_symlinks: bool = False,
) -> Path:
    clean = validate_relative_path(value, label)
    root = repo_root.resolve()
    current = root
    for part in PurePosixPath(clean).parts:
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            break
        if forbid_symlinks and stat.S_ISLNK(mode):
            raise ValueError(f"{label} must not contain a symbolic link")
    resolved = (root / clean).resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} resolves outside the repository") from exc
    if must_exist and not resolved.is_file():
        raise ValueError(f"{label} does not name an existing file")
    return resolved


def _decode_candidate(candidate: str) -> tuple[str, str, str]:
    """Delegate architecture identity semantics to the architecture package."""
    spec = importlib.util.spec_from_file_location("architecture_fingerprint", ARCHITECTURE_FINGERPRINT)
    if spec is None or spec.loader is None:
        raise ValueError("architecture fingerprint validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse_fingerprint(candidate)


def _validate_registered_adr(repo_root: Path, adr: str, digest: str) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ADR_QUERY),
            "validate-registration",
            "--repo-root",
            str(repo_root),
            "--adr",
            adr,
            "--hash",
            digest,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "ADR registration validation failed"
        raise ValueError(detail.removeprefix("error: "))


def validate_handoff(
    handoff: dict[str, Any],
    repo_root: Path,
    schema_path: Path = DEFAULT_SCHEMA,
    *,
    expected_skill: str | None = None,
    expected_pipeline: str | object | None = ...,
) -> None:
    """Validate schema, typed successor, identity, paths, and ADR provenance."""
    _validate_schema(handoff, schema_path)
    candidate = handoff["candidate"]
    if candidate is not None:
        candidate_module, _symbol, _burden = _decode_candidate(candidate)
        if candidate_module not in handoff["scope"]["modules"]:
            raise ValueError("candidate module must match one of scope.modules")
    if expected_skill is not None and handoff["next_skill"] != expected_skill:
        raise ValueError(f"handoff next_skill must be {expected_skill}")
    if expected_pipeline is not ... and handoff["next_pipeline"] != expected_pipeline:
        rendered = "null" if expected_pipeline is None else expected_pipeline
        raise ValueError(f"handoff next_pipeline must be {rendered}")
    for group in ("modules", "callers"):
        for index, value in enumerate(handoff["scope"][group]):
            _resolve_contained(repo_root, value, f"scope.{group}[{index}]")
    artifact = handoff["decision_artifact"]
    if artifact is not None:
        _resolve_contained(repo_root, artifact, "decision_artifact", forbid_symlinks=True)
        expected = LOCAL_STORE if handoff["decision_scope"] == "local" else SHARED_STORE
        if artifact != expected:
            raise ValueError(f"{handoff['decision_scope']} decision memory must use {expected}")
    adr = handoff["consultation_adr"]
    if adr is not None:
        _validate_registered_adr(repo_root, adr, handoff["consultation_adr_hash"])


def _load_input(args: argparse.Namespace, repo_root: Path) -> dict[str, Any]:
    if args.stdin:
        raw = sys.stdin.read()
    else:
        path = _resolve_contained(repo_root, args.handoff, "handoff", must_exist=True, forbid_symlinks=True)
        raw = path.read_text(encoding="utf-8")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"handoff is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("handoff must contain a JSON object")
    return value


def _add_validation_args(parser: argparse.ArgumentParser, *, writing: bool) -> None:
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    if writing:
        parser.add_argument("--handoff", required=True)
        parser.add_argument("--stdin", action="store_true", default=True, help=argparse.SUPPRESS)
    else:
        source = parser.add_mutually_exclusive_group(required=True)
        source.add_argument("--handoff")
        source.add_argument("--stdin", action="store_true")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--expected-skill", choices=("workflow", "feature-lifecycle"))
    parser.add_argument("--expected-pipeline", choices=("systematic-refactoring", "none"))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate a handoff from a file or stdin")
    _add_validation_args(validate, writing=False)
    write = subparsers.add_parser("write", help="validate stdin, then atomically write a handoff")
    _add_validation_args(write, writing=True)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        repo_root = args.repo_root.resolve()
        handoff = _load_input(args, repo_root)
        expected_pipeline: str | object | None = ...
        if args.expected_pipeline == "none":
            expected_pipeline = None
        elif args.expected_pipeline:
            expected_pipeline = args.expected_pipeline
        validate_handoff(
            handoff,
            repo_root,
            args.schema,
            expected_skill=args.expected_skill,
            expected_pipeline=expected_pipeline,
        )
        if args.command == "write":
            clean = validate_relative_path(args.handoff, "handoff")
            if not clean.startswith(f"{HANDOFF_ROOT}/"):
                raise ValueError(f"handoff path must be below {HANDOFF_ROOT}/")
            rendered = json.dumps(handoff, indent=2, ensure_ascii=False) + "\n"
            atomic_write_text(repo_root, clean, rendered, allowed_root="adr", mode=0o600)
            print(clean)
        else:
            print("valid")
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
