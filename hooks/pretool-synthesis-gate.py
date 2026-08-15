#!/usr/bin/env python3
# hook-version: 1.1.0
"""
PreToolUse:Write,Edit Hook: Consultation Synthesis Gate

Blocks feature implementation when an ADR exists but consultation
synthesis is missing or BLOCKED. Forces agents to complete consultation
before writing implementation code.

This is a HARD GATE — exits 0 with JSON permissionDecision:deny to block the Write/Edit tool.

Detection logic:
- Tool is Write or Edit
- .adr-session.json exists (active ADR session)
- Target path is NOT in hooks/, scripts/, adr/, or test files
- No synthesis.md in the ADR consultation directory

Allow-through conditions:
- No .adr-session.json (no active ADR session)
- Target file is in hooks/, scripts/, adr/, commands/ (infrastructure, not implementation)
- Target file is a test file (*_test.go, *_test.py, test_*.py, *.test.ts)
- synthesis.md exists with explicit PROCEED verdict
- SYNTHESIS_GATE_BYPASS=1 env var (for the consultation skill itself)

Block conditions:
- synthesis.md is missing (verdict is None)
- synthesis.md contains explicit BLOCKED verdict
- synthesis.md exists but contains neither PROCEED nor BLOCKED (verdict is UNKNOWN --
  indicates incomplete consultation, truncated write, or merge conflict markers)

Stale sessions:
A session older than SESSION_STALE_AFTER_HOURS is almost always one that was
never closed rather than live consultation work. Staleness does NOT relax the
gate — a stale session blocks exactly as hard. It only adds the diagnosis (age,
registration date, ADR name, checklist state) and the close command to the
denial message, so the fix takes seconds instead of an investigation.
See scripts/adr-query.py close.
"""

import json
import os
import re
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import deny_tool_use, hook_error
from stdin_timeout import read_stdin

_BYPASS_ENV = "SYNTHESIS_GATE_BYPASS"

# A session older than this is stale. Staleness NEVER changes whether this gate
# blocks — it only adds the diagnosis and the close command to the denial, so a
# stranded session is fixed in seconds instead of investigated for days.
# Kept in sync with SESSION_STALE_AFTER_HOURS in scripts/adr-query.py.
SESSION_STALE_AFTER_HOURS = 24

_CLOSE_COMMAND = "python3 scripts/adr-query.py close"

# Markdown checklist item: "- [ ] text" / "- [x] text".
_CHECKLIST_ITEM_RE = re.compile(r"^\s*-\s+\[([ xX])\]\s+\S", re.MULTILINE)

# Paths that ARE implementation code — only these get gated.
# Everything else (docs, config, CI, plans, tests) passes through.
_GATED_PREFIXES = (
    "/agents/",
    "/skills/",
)

# Source code extensions that are implementation code.
_GATED_EXTENSIONS = frozenset(
    {
        ".py",
        ".go",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".rs",
        ".java",
        ".rb",
        ".c",
        ".cpp",
        ".cs",
    }
)


def _is_gated(file_path: str) -> bool:
    """Return True if this is implementation code that requires consultation."""
    normalised = file_path.replace("\\", "/")
    basename = normalised.rsplit("/", 1)[-1] if "/" in normalised else normalised
    ext = "." + basename.rsplit(".", 1)[-1] if "." in basename else ""

    # Only gate source files in implementation directories
    in_gated_dir = any(prefix in normalised for prefix in _GATED_PREFIXES)
    is_source = ext.lower() in _GATED_EXTENSIONS

    # Gate if it's a source file in an implementation directory
    # OR if it's a SKILL.md or agent .md being created/modified
    if in_gated_dir:
        return True

    # Standalone source files at repo root (rare but possible)
    # are NOT gated — they're scripts or utilities
    return False


def _load_session(base_dir: Path) -> dict | None:
    """Load .adr-session.json from base_dir. Returns None if absent or malformed.

    Non-object JSON (a list, string, or number) is malformed too: returning it
    raised AttributeError downstream, which fail-open caught but logged as a
    hook error on every single Write.
    """
    session_path = base_dir / ".adr-session.json"
    if not session_path.is_file():
        return None
    try:
        session = json.loads(session_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return session if isinstance(session, dict) else None


def _format_age(age: timedelta) -> str:
    """Render a session age as a short human string, e.g. '3d 4h' or '20m'."""
    total_minutes = max(int(age.total_seconds()) // 60, 0)
    days, remainder = divmod(total_minutes, 60 * 24)
    hours, minutes = divmod(remainder, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _checklist_state(base_dir: Path, session: dict) -> str:
    """Describe the registered ADR's checklist. Returns 'unknown (...)' if unreadable."""
    adr_path = session.get("adr_path")
    if not isinstance(adr_path, str):
        return "unknown (session records no ADR path)"
    normalised = adr_path.replace("\\", "/")
    parts = normalised.split("/")
    if (
        normalised.startswith("/")
        or ".." in parts
        or not normalised.startswith("adr/")
        or not normalised.endswith(".md")
    ):
        return "unknown (session ADR path is not a repo-relative adr/*.md file)"
    adr_file = base_dir / normalised
    if not adr_file.is_file():
        return "unknown (ADR file is missing)"
    try:
        content = adr_file.read_text(encoding="utf-8")
    except OSError:
        return "unknown (ADR file is unreadable)"
    marks = [m.group(1).lower() for m in _CHECKLIST_ITEM_RE.finditer(content)]
    if not marks:
        return "the ADR has no checklist"
    unchecked = sum(1 for mark in marks if mark != "x")
    if unchecked == 0:
        return f"COMPLETE ({len(marks)} of {len(marks)} items checked)"
    return f"incomplete ({unchecked} of {len(marks)} items unchecked)"


def _stale_session_note(base_dir: Path, session: dict, adr_name: str) -> str:
    """Return an actionable stale-session note, or '' when the session is fresh.

    Never raises: any unexpected shape yields '' so the denial falls back to the
    normal consultation guidance rather than failing the hook.
    """
    try:
        raw = session.get("registered_at")
        if not isinstance(raw, str):
            return ""
        registered = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if registered.tzinfo is None:
            registered = registered.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - registered
        if age < timedelta(hours=SESSION_STALE_AFTER_HOURS):
            return ""
        checklist = _checklist_state(base_dir, session)
    except (AttributeError, OSError, TypeError, ValueError):
        return ""

    return (
        f"\n\nSTALE ADR SESSION — this, not your write, is probably the real problem.\n"
        f"  age:           {_format_age(age)} old (registered {raw})\n"
        f"  adr:           {adr_name}\n"
        f"  checklist:     {checklist}\n"
        f"A session older than {SESSION_STALE_AFTER_HOURS}h is usually one that was never closed. "
        f"It keeps blocking every Write/Edit under agents/ and skills/ until it is closed.\n"
        f"If that ADR's work is done, end the session:  {_CLOSE_COMMAND}\n"
        f"If consultation is genuinely still open, run /adr-consultation on {adr_name} instead."
    )


def _synthesis_verdict(synthesis_path: Path) -> str | None:
    """
    Return the verdict string from synthesis.md, or None if the file is missing.

    Scans for a line containing 'PROCEED' or 'BLOCKED' (case-insensitive).
    Returns 'PROCEED', 'BLOCKED', or 'UNKNOWN' if neither keyword is found.
    """
    if not synthesis_path.is_file():
        return None
    try:
        text = synthesis_path.read_text(encoding="utf-8").upper()
    except OSError:
        return None

    if "PROCEED" in text:
        return "PROCEED"
    if "BLOCKED" in text:
        return "BLOCKED"
    return "UNKNOWN"


def main() -> None:
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    # tool_name filter removed — matcher "Write|Edit" in settings.json prevents
    # this hook from spawning for non-matching tools.

    # Bypass env var — set by the consultation skill itself.
    if os.environ.get(_BYPASS_ENV) == "1":
        if debug:
            print("[synthesis-gate] Bypassed via SYNTHESIS_GATE_BYPASS=1", file=sys.stderr)
        sys.exit(0)

    tool_input = event.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Only gate implementation code (agents/, skills/).
    # Everything else (docs, config, CI, plans, tests, scripts) passes through.
    if not _is_gated(file_path):
        if debug:
            print(f"[synthesis-gate] Not implementation code, allowing: {file_path}", file=sys.stderr)
        sys.exit(0)

    # Resolve project root: prefer event["cwd"], then CLAUDE_PROJECT_DIR, then cwd.
    cwd_str = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR", ".")
    base_dir = Path(cwd_str).resolve()

    session = _load_session(base_dir)
    if session is None:
        # No active ADR session — gate is dormant.
        if debug:
            print("[synthesis-gate] No .adr-session.json found — allowing through", file=sys.stderr)
        sys.exit(0)

    domain = session.get("domain", "")
    adr_name = domain or Path(session.get("adr_path", "unknown")).stem

    if debug:
        print(f"[synthesis-gate] Active ADR session: domain={adr_name}", file=sys.stderr)

    # Diagnosis only. This never affects whether the gate blocks below — it is
    # appended to a denial that has already been decided.
    stale_note = _stale_session_note(base_dir, session, adr_name)

    # Locate synthesis.md: adr/{domain}/synthesis.md
    synthesis_path = base_dir / "adr" / adr_name / "synthesis.md"
    verdict = _synthesis_verdict(synthesis_path)

    if verdict is None:
        # synthesis.md is missing — block until consultation is run.
        print(
            f"[synthesis-gate] BLOCKED: Consultation required. "
            f"Run /adr-consultation on {adr_name} first.\n"
            f"[synthesis-gate] Expected: {synthesis_path}{stale_note}",
            file=sys.stderr,
        )
        deny_tool_use(
            "PreToolUse",
            f"ADR consultation required before implementing {adr_name}. "
            f"Run /adr-consultation on {adr_name} first to generate {synthesis_path}.{stale_note}",
        )
        sys.exit(0)

    if verdict == "BLOCKED":
        print(
            f"[synthesis-gate] BLOCKED: Consultation verdict is BLOCKED for {adr_name}.\n"
            f"[synthesis-gate] Review {synthesis_path} and resolve concerns before implementing.{stale_note}",
            file=sys.stderr,
        )
        deny_tool_use(
            "PreToolUse",
            f"ADR consultation verdict is BLOCKED for {adr_name}. "
            f"Review {synthesis_path} and resolve all concerns before implementing.{stale_note}",
        )
        sys.exit(0)

    if verdict == "UNKNOWN":
        print(
            f"[synthesis-gate] BLOCKED: synthesis.md exists but contains neither PROCEED nor BLOCKED for {adr_name}.\n"
            f"[synthesis-gate] The consultation may be incomplete, truncated, or contain merge conflict markers.\n"
            f"[synthesis-gate] Review {synthesis_path} and ensure it contains an explicit PROCEED or BLOCKED verdict."
            f"{stale_note}",
            file=sys.stderr,
        )
        deny_tool_use(
            "PreToolUse",
            f"ADR synthesis.md for {adr_name} has no clear PROCEED or BLOCKED verdict. "
            f"The consultation may be incomplete or truncated. "
            f"Review {synthesis_path} and ensure it contains an explicit verdict.{stale_note}",
        )
        sys.exit(0)

    # Explicit PROCEED — allow through.
    if debug:
        print(f"[synthesis-gate] Verdict=PROCEED for {adr_name} — allowing through", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(0) propagate normally
    except Exception as e:
        hook_error("pretool-synthesis-gate", e)
    finally:
        sys.exit(0)
