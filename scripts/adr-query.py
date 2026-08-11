#!/usr/bin/env python3
"""
ADR Query System — primary query interface for ADR consumers.

Treats ADR markdown files as structured databases, enabling role-targeted
context extraction, content integrity verification, and session registration.

Usage:
    python3 scripts/adr-query.py context --adr PATH --role ROLE
    python3 scripts/adr-query.py hash    --adr PATH
    python3 scripts/adr-query.py verify  --adr PATH --hash HASH
    python3 scripts/adr-query.py section --adr PATH --heading TEXT
    python3 scripts/adr-query.py list
    python3 scripts/adr-query.py register --adr PATH
    python3 scripts/adr-query.py active

Exit codes:
    0 = success
    1 = hash mismatch / file not found / session not registered
    2 = usage error (invalid role, missing arguments)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from repository_artifact import atomic_write_text, validate_relative_path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SESSION_FILE = ".adr-session.json"

# Role → list of adr-section names to include.
# None means "all sections" (full file).
ROLE_SECTIONS: dict[str, Optional[list[str]]] = {
    "skill-creator": ["step-menu", "type-matrix", "canonical-chains", "architecture-rules"],
    "agent-creator": ["architecture-rules", "self-improvement-loop"],
    "script-creator": ["step-families-enums", "schema-types", "type-matrix", "validation-rules"],
    "chain-composer": ["step-menu", "type-matrix", "canonical-chains", "operator-profiles"],
    "orchestrator": None,  # all sections
}

VALID_ROLES = list(ROLE_SECTIONS.keys())

# Heading-level aliases used during fuzzy fallback matching.
# Maps section-name tokens (from ROLE_SECTIONS) to candidate heading words.
SECTION_HEADING_ALIASES: dict[str, list[str]] = {
    "step-menu": ["step", "menu", "pipeline"],
    "type-matrix": ["type", "compatibility", "matrix"],
    "canonical-chains": ["canonical", "chain", "chains"],
    "architecture-rules": ["architecture", "rules", "rule"],
    "component-naming": ["component", "naming", "names"],
    "skill-pairing": ["skill", "pairing", "pairs"],
    "step-families-enums": ["step", "famil", "enum"],
    "schema-types": ["schema", "type", "output"],
    "validation-rules": ["validation", "rules", "rule"],
    "operator-profiles": ["operator", "profile", "profiles"],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _die(msg: str, code: int = 1) -> None:
    """Print error message to stderr and exit with given code."""
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def _repo_root(args: argparse.Namespace) -> Path:
    return args.repo_root.resolve()


def _resolve_adr(path_str: str, repo_root: Path) -> Path:
    """Resolve ADR path, enforcing it stays within the repo's adr/ directory."""
    adr_dir = repo_root / "adr"

    try:
        if stat.S_ISLNK(adr_dir.lstat().st_mode):
            raise ValueError("adr/ must not be a symbolic link")
    except FileNotFoundError as exc:
        raise ValueError(f"adr/ directory not found at {adr_dir}") from exc
    if not adr_dir.is_dir():
        raise ValueError(f"adr/ directory not found at {adr_dir}")

    candidate = Path(path_str)
    if candidate.is_absolute():
        try:
            relative = candidate.relative_to(repo_root)
        except ValueError as exc:
            raise ValueError(f"ADR path must be within the adr/ directory: {path_str}") from exc
    else:
        relative = candidate
    clean = validate_relative_path(relative.as_posix(), "ADR path")
    if Path(clean).suffix != ".md":
        raise ValueError(f"ADR path must be a .md file: {path_str}")
    if not clean.startswith("adr/"):
        raise ValueError(f"ADR path must be within the adr/ directory: {path_str}")
    current = repo_root
    for part in Path(clean).parts:
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            break
        if stat.S_ISLNK(mode):
            raise ValueError(f"ADR path must not contain a symbolic link: {path_str}")
    resolved = (repo_root / clean).resolve(strict=False)
    try:
        resolved.relative_to(adr_dir)
    except ValueError as exc:
        raise ValueError(f"ADR path must be within the adr/ directory: {path_str}") from exc

    if not resolved.is_file():
        raise ValueError(f"ADR file not found: {path_str}")

    return resolved


def _session_read(repo_root: Path) -> dict:
    directory_flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        directory_flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        directory_flags |= os.O_NOFOLLOW
    root_fd = os.open(repo_root, directory_flags)
    try:
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(SESSION_FILE, flags, dir_fd=root_fd)
        except FileNotFoundError as exc:
            raise ValueError(f"no active ADR session — {SESSION_FILE} not found in {repo_root}") from exc
        except OSError as exc:
            raise ValueError("ADR session registry must not be a symbolic link") from exc
        mode = os.fstat(descriptor).st_mode
        if not stat.S_ISREG(mode):
            os.close(descriptor)
            raise ValueError("ADR session registry must be a regular file")
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            try:
                session = json.load(handle)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON in {SESSION_FILE}: {exc}") from exc
    finally:
        os.close(root_fd)
    if not isinstance(session, dict):
        raise ValueError("ADR session registry must contain a JSON object")
    return session


def _validate_registration(repo_root: Path, adr_path: Path, expected_hash: str) -> None:
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", expected_hash):
        raise ValueError("expected ADR hash must use sha256:<64 lowercase hex digits>")
    actual_hash = _compute_hash(adr_path)
    if actual_hash != expected_hash:
        raise ValueError(f"ADR hash mismatch: expected {expected_hash}, actual {actual_hash}")
    session = _session_read(repo_root)
    session_path = session.get("adr_path")
    session_hash = session.get("adr_hash")
    if not isinstance(session_path, str) or not isinstance(session_hash, str):
        raise ValueError("ADR session registry must contain string adr_path and adr_hash fields")
    registered = _resolve_adr(session_path, repo_root)
    if registered != adr_path or session_hash != expected_hash:
        raise ValueError("ADR does not match the active registered path and hash")


def _compute_hash(path: Path) -> str:
    """Return sha256:hexdigest of file content."""
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    return f"sha256:{digest}"


def _extract_status(content: str) -> str:
    """Extract the Status value from ADR frontmatter/body (e.g. PROPOSED, ACCEPTED)."""
    match = re.search(r"^##\s+Status\s*\n+([A-Z_-]+)", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return "UNKNOWN"


def _extract_domain(path: Path) -> str:
    """Derive a domain name from an ADR filename.

    Rules:
      - Strip 'pipeline-' prefix if present.
      - Strip '.md' suffix.
      - E.g. 'pipeline-prometheus.md' → 'prometheus'
           'adr-database-system.md'  → 'adr-database-system'
    """
    stem = path.stem  # filename without extension
    if stem.startswith("pipeline-"):
        return stem[len("pipeline-") :]
    return stem


# ---------------------------------------------------------------------------
# Section extraction
# ---------------------------------------------------------------------------


def _find_sections_by_marker(content: str) -> dict[str, tuple[int, int]]:
    """Find sections via <!-- adr-section: name --> markers.

    Returns a dict mapping section-name → (start_line_idx, end_line_idx)
    where the range covers from the marker line through content before the
    next same-or-higher-level heading.

    Line indices are 0-based into the lines list.
    """
    lines = content.splitlines()
    sections: dict[str, tuple[int, int]] = {}
    marker_re = re.compile(r"<!--\s*adr-section:\s*([\w-]+)\s*-->")

    # Collect all marker positions
    markers: list[tuple[int, str]] = []  # (line_idx, section_name)
    for idx, line in enumerate(lines):
        m = marker_re.search(line)
        if m:
            markers.append((idx, m.group(1)))

    # Collect all heading positions (##, ###, etc.)
    heading_re = re.compile(r"^(#{1,6})\s+")
    headings: list[tuple[int, int]] = []  # (line_idx, level)
    for idx, line in enumerate(lines):
        m = heading_re.match(line)
        if m:
            headings.append((idx, len(m.group(1))))

    def _next_section_end(start_line: int, marker_level: int) -> int:
        """Return the line index where the section content ends."""
        # Find heading level at or before the marker (the heading that precedes it)
        preceding_level = marker_level
        for h_idx, h_level in headings:
            if h_idx <= start_line:
                preceding_level = h_level

        # Next heading at same or higher level (lower number) ends this section
        for h_idx, h_level in headings:
            if h_idx > start_line and h_level <= preceding_level:
                return h_idx
        return len(lines)

    for marker_idx, section_name in markers:
        end = _next_section_end(marker_idx, 2)  # use level 2 as default
        sections[section_name] = (marker_idx, end)

    return sections


def _find_section_by_heading_fuzzy(lines: list[str], section_name: str) -> Optional[tuple[int, int]]:
    """Fallback: find a section by fuzzy-matching heading text.

    Splits the section name by '-', looks for headings containing significant words.
    Returns (start_line_idx, end_line_idx) or None if not found.
    """
    tokens = [t.lower() for t in section_name.split("-") if len(t) > 2]
    # Also include alias tokens
    alias_tokens = SECTION_HEADING_ALIASES.get(section_name, [])
    all_tokens = list(set(tokens + [t.lower() for t in alias_tokens]))

    heading_re = re.compile(r"^(#{1,6})\s+(.*)")
    best_match: Optional[tuple[int, int, int]] = None  # (line_idx, level, score)

    for idx, line in enumerate(lines):
        m = heading_re.match(line)
        if not m:
            continue
        level = len(m.group(1))
        heading_text = m.group(2).lower()
        score = sum(1 for t in all_tokens if t in heading_text)
        if score >= 1 and (best_match is None or score > best_match[2]):
            best_match = (idx, level, score)

    if best_match is None:
        return None

    start_idx, found_level, _ = best_match
    # Find end: next heading at same or higher (lower number) level
    for idx, line in enumerate(lines):
        if idx <= start_idx:
            continue
        m = heading_re.match(line)
        if m and len(m.group(1)) <= found_level:
            return (start_idx, idx)

    return (start_idx, len(lines))


def _extract_section_content(path: Path, section_name: str) -> Optional[str]:
    """Extract the content of a named section from an ADR file.

    Uses primary (marker) detection first, then heading-based fallback.
    Returns the section text or None if not found.
    """
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Primary: marker-based
    sections = _find_sections_by_marker(content)
    if section_name in sections:
        start, end = sections[section_name]
        return "\n".join(lines[start:end])

    # Fallback: fuzzy heading match
    result = _find_section_by_heading_fuzzy(lines, section_name)
    if result:
        start, end = result
        return "\n".join(lines[start:end])

    return None


def _extract_section_by_heading(path: Path, heading_text: str) -> Optional[str]:
    """Extract a section by exact or close heading text match.

    Used by the 'section' subcommand. Matches case-insensitively against
    heading lines, returns content through the next same-or-higher heading.
    """
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    heading_re = re.compile(r"^(#{1,6})\s+(.*)")
    needle = heading_text.lower().strip()

    for idx, line in enumerate(lines):
        m = heading_re.match(line)
        if not m:
            continue
        level = len(m.group(1))
        text = m.group(2).lower().strip()
        # Accept exact match or if needle is contained in heading text
        if needle == text or needle in text or text in needle:
            # Find end
            end = len(lines)
            for j in range(idx + 1, len(lines)):
                m2 = heading_re.match(lines[j])
                if m2 and len(m2.group(1)) <= level:
                    end = j
                    break
            return "\n".join(lines[idx:end])

    return None


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------


def cmd_hash(args: argparse.Namespace) -> int:
    """Compute and print the SHA256 hash of an ADR file."""
    path = _resolve_adr(args.adr, _repo_root(args))
    print(_compute_hash(path))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify that an ADR file's current hash matches the given hash.

    Returns exit 0 on match, exit 1 on mismatch.
    """
    path = _resolve_adr(args.adr, _repo_root(args))
    expected = args.hash.strip()
    actual = _compute_hash(path)
    if actual == expected:
        print(f"OK: {path} matches {expected}")
        return 0
    else:
        print(f"MISMATCH: {path}", file=sys.stderr)
        print(f"  expected: {expected}", file=sys.stderr)
        print(f"  actual:   {actual}", file=sys.stderr)
        return 1


def cmd_section(args: argparse.Namespace) -> int:
    """Extract a specific section by heading text and print it."""
    path = _resolve_adr(args.adr, _repo_root(args))
    result = _extract_section_by_heading(path, args.heading)
    if result is None:
        print(f"warning: section '{args.heading}' not found in {path}", file=sys.stderr)
        return 1
    print(result)
    return 0


def cmd_context(args: argparse.Namespace) -> int:
    """Extract and print role-targeted context from an ADR.

    For 'orchestrator' role: returns the full file with a header.
    For other roles: returns only the sections relevant to that role.
    Warns (but does not fail) when a mapped section cannot be found.
    """
    role = args.role
    if role not in ROLE_SECTIONS:
        print(f"error: invalid role '{role}'. Valid roles: {', '.join(VALID_ROLES)}", file=sys.stderr)
        return 2

    path = _resolve_adr(args.adr, _repo_root(args))
    section_names = ROLE_SECTIONS[role]

    header = (
        f"# ADR Context for role: {role}\n"
        f"# Source: {path}\n"
        f"# Hash: {_compute_hash(path)}\n"
        f"# Generated: {datetime.now(timezone.utc).isoformat()}\n"
    )
    print(header)

    if section_names is None:
        # orchestrator: full file
        print(path.read_text(encoding="utf-8"))
        return 0

    exit_code = 0
    for section_name in section_names:
        content = _extract_section_content(path, section_name)
        if content is None:
            print(
                f"# WARNING: section '{section_name}' not found in {path.name}",
                file=sys.stderr,
            )
            print(f"\n## [SECTION NOT FOUND: {section_name}]\n")
            exit_code = 0  # warn but don't fail per spec
            continue
        print(f"\n{content}\n")

    return exit_code


def cmd_list(args: argparse.Namespace) -> int:
    """List all .md files in the adr/ directory with metadata as JSON."""
    # Find adr/ relative to this script's repo root
    repo_root = _repo_root(args)
    adr_dir = repo_root / "adr"

    if not adr_dir.exists():
        _die(f"adr/ directory not found at {adr_dir}")

    results = []
    for md_file in sorted(adr_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        results.append(
            {
                "path": str(md_file.relative_to(repo_root)),
                "hash": _compute_hash(md_file),
                "domain": _extract_domain(md_file),
                "status": _extract_status(content),
                "last_modified": datetime.fromtimestamp(md_file.stat().st_mtime, tz=timezone.utc).isoformat(),
            }
        )

    print(json.dumps(results, indent=2))
    return 0


def cmd_register(args: argparse.Namespace) -> int:
    """Register an ADR as active for the current session.

    Writes .adr-session.json to the current working directory.
    """
    repo_root = _repo_root(args)
    path = _resolve_adr(args.adr, repo_root)
    adr_hash = _compute_hash(path)
    domain = _extract_domain(path)

    adr_path_str = path.relative_to(repo_root).as_posix()

    session = {
        "adr_path": adr_path_str,
        "adr_hash": adr_hash,
        "domain": domain,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "cwd": str(repo_root),
    }

    session_file = atomic_write_text(
        repo_root,
        SESSION_FILE,
        json.dumps(session, indent=2) + "\n",
        mode=0o600,
    )
    print(f"Registered: {adr_path_str} ({adr_hash})")
    print(f"Session file: {session_file}")
    return 0


def cmd_active(args: argparse.Namespace) -> int:
    """Print the currently active ADR from .adr-session.json.

    Exits 1 with a descriptive message if no session is registered.
    """
    session = _session_read(_repo_root(args))

    adr_path = session.get("adr_path", "<unknown>")
    adr_hash = session.get("adr_hash", "<unknown>")
    domain = session.get("domain", "<unknown>")
    registered_at = session.get("registered_at", "<unknown>")

    print(f"path:          {adr_path}")
    print(f"hash:          {adr_hash}")
    print(f"domain:        {domain}")
    print(f"registered_at: {registered_at}")
    return 0


def cmd_validate_registration(args: argparse.Namespace) -> int:
    """Validate ADR containment, content hash, and active registration."""
    repo_root = _repo_root(args)
    path = _resolve_adr(args.adr, repo_root)
    _validate_registration(repo_root, path, args.hash)
    print("valid")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="adr-query.py",
        description="Query interface for ADR markdown files treated as structured data.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    def add_repo_root(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--repo-root",
            type=Path,
            default=Path(__file__).parent.parent,
            help="Repository root (default: root containing this script)",
        )

    # --- context ---
    p_context = subparsers.add_parser(
        "context",
        help="Get role-targeted context block from an ADR.",
    )
    add_repo_root(p_context)
    p_context.add_argument("--adr", required=True, metavar="PATH", help="Path to ADR file")
    p_context.add_argument(
        "--role",
        required=True,
        metavar="ROLE",
        choices=VALID_ROLES,
        help=f"Consumer role: {' | '.join(VALID_ROLES)}",
    )

    # --- hash ---
    p_hash = subparsers.add_parser(
        "hash",
        help="Compute SHA256 hash of an ADR file.",
    )
    add_repo_root(p_hash)
    p_hash.add_argument("--adr", required=True, metavar="PATH", help="Path to ADR file")

    # --- verify ---
    p_verify = subparsers.add_parser(
        "verify",
        help="Verify ADR file hash matches expected value (exit 0=match, 1=mismatch).",
    )
    add_repo_root(p_verify)
    p_verify.add_argument("--adr", required=True, metavar="PATH", help="Path to ADR file")
    p_verify.add_argument("--hash", required=True, metavar="HASH", help="Expected hash (sha256:...)")

    # --- section ---
    p_section = subparsers.add_parser(
        "section",
        help="Extract a specific section by heading text.",
    )
    add_repo_root(p_section)
    p_section.add_argument("--adr", required=True, metavar="PATH", help="Path to ADR file")
    p_section.add_argument("--heading", required=True, metavar="TEXT", help="Heading text to find")

    # --- list ---
    p_list = subparsers.add_parser(
        "list",
        help="List all ADR files in adr/ with hashes and metadata (JSON output).",
    )
    add_repo_root(p_list)

    # --- register ---
    p_register = subparsers.add_parser(
        "register",
        help="Register an ADR as active for the current session (writes .adr-session.json).",
    )
    add_repo_root(p_register)
    p_register.add_argument("--adr", required=True, metavar="PATH", help="Path to ADR file")

    # --- active ---
    p_active = subparsers.add_parser(
        "active",
        help="Print the currently active ADR from .adr-session.json.",
    )
    add_repo_root(p_active)

    p_validate_registration = subparsers.add_parser(
        "validate-registration",
        help="Validate ADR containment, hash, and active session registration.",
    )
    add_repo_root(p_validate_registration)
    p_validate_registration.add_argument("--adr", required=True, metavar="PATH", help="Path to ADR file")
    p_validate_registration.add_argument(
        "--hash",
        required=True,
        metavar="HASH",
        help="Expected hash (sha256:...)",
    )

    return parser


def main() -> int:
    """Entry point — parse args and dispatch to subcommand handler."""
    parser = _build_parser()
    args = parser.parse_args()

    dispatch = {
        "context": cmd_context,
        "hash": cmd_hash,
        "verify": cmd_verify,
        "section": cmd_section,
        "list": cmd_list,
        "register": cmd_register,
        "active": cmd_active,
        "validate-registration": cmd_validate_registration,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help(sys.stderr)
        return 2

    try:
        return handler(args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
