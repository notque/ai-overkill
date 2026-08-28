#!/usr/bin/env python3
# hook-version: 3.0.0
"""
SessionStart Hook: Dream Payload Injector (ADR-147)

Injects the pre-built dream payload (if present and fresh) and surfaces a
one-line overnight dream notice (if dream ran recently).

The learning-injection path was removed with the rest of the learning loop:
this hook no longer queries learning.db and records no activations.

Design Principles:
- SILENT unless a fresh dream payload or notice exists
- Project-aware (reads the payload for the current directory)
- Fast execution (<50ms target)
- Non-blocking (always exits 0)
- Pure file reader — no LLM work, no learning.db queries
"""

import os
import sys
import time
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output, hook_error
from learning_db_v2 import sanitize_for_context

EVENT_NAME = "SessionStart"

# Dream injection payload is considered fresh for 96 hours (covers full weekend + holiday Monday)
DREAM_PAYLOAD_MAX_AGE_HOURS = 96

# Dream payload character cap. Current max observed: 5536 chars (2026-04-13).
# 7000 provides ~27% headroom before the cap activates.
# When the cap is hit, the payload is truncated at the last complete markdown heading
# boundary to preserve structural integrity.
DREAM_PAYLOAD_MAX_CHARS = 7000

# Dream report notice is surfaced if dream ran within the last 24 hours
DREAM_REPORT_MAX_AGE_HOURS = 24


def _project_hash(cwd: str) -> str:
    """Derive the project hash from a directory path.

    Mirrors the convention Claude Code uses for project-specific directories:
    replace '/' with '-', then strip the leading '-'.
    Example: /home/feedgen/vexjoy-agent -> home-feedgen-vexjoy-agent
    """
    return cwd.replace("/", "-").lstrip("-")


def inject_dream_payload(cwd: str) -> str:
    """Return the pre-built dream injection payload, or empty string if absent/stale.

    Reads ~/.claude/state/dream-injection-{project-hash}.md.
    Returns the file contents if it exists and is less than DREAM_PAYLOAD_MAX_AGE_HOURS old.
    Sanitizes content before return since dream payloads are LLM-generated.
    This is a pure file read — no LLM work, no learning.db queries.
    """
    try:
        proj_hash = _project_hash(cwd)
        payload_file = Path.home() / ".claude" / "state" / f"dream-injection-{proj_hash}.md"

        if not payload_file.exists():
            return ""

        age_hours = (time.time() - payload_file.stat().st_mtime) / 3600
        if age_hours > DREAM_PAYLOAD_MAX_AGE_HOURS:
            return ""

        content = payload_file.read_text().strip()
        if not content:
            return ""

        sanitized = sanitize_for_context(content)

        # Enforce character cap: truncate at the last complete markdown heading boundary.
        if len(sanitized) > DREAM_PAYLOAD_MAX_CHARS:
            truncated = sanitized[:DREAM_PAYLOAD_MAX_CHARS]
            # Walk back to the last heading line (## or ###) to avoid mid-section cuts.
            last_heading = max(truncated.rfind("\n## "), truncated.rfind("\n### "))
            if last_heading > 0:
                truncated = truncated[:last_heading]
            return truncated

        return sanitized

    except Exception:
        return ""


def surface_dream_report() -> str:
    """Inject recent dream summary at session start.

    Reads ~/.claude/state/last-dream.md. Returns a one-line notice if the dream
    ran within the last 24 hours, empty string otherwise.
    """
    try:
        dream_file = Path.home() / ".claude" / "state" / "last-dream.md"
        if not dream_file.exists():
            return ""

        age_hours = (time.time() - dream_file.stat().st_mtime) / 3600
        if age_hours > DREAM_REPORT_MAX_AGE_HOURS:
            return ""

        # First try ## One-Line Summary (a single natural-language sentence added by ADR-147)
        # Fall back to ## Summary (older reports or dry-run with no one-liner)
        text = dream_file.read_text()
        for target_header in ("## One-Line Summary", "## Summary"):
            in_section = False
            for line in text.splitlines():
                if line.strip() == target_header:
                    in_section = True
                    continue
                if in_section and line.startswith("##"):
                    break
                if in_section and line.strip() and not line.startswith("#"):
                    return f"[dream] {sanitize_for_context(line.strip())}"

        # Fallback: return first non-empty, non-header line in the whole file
        for line in text.splitlines():
            if line.strip() and not line.startswith("#"):
                return f"[dream] {sanitize_for_context(line.strip())}"

        return ""

    except Exception:
        return ""


def main():
    """Inject the overnight dream payload and notice at session start."""
    try:
        cwd = os.getcwd()

        context_parts = []

        # ADR-147: inject pre-built dream payload (replaces retro-knowledge-injector.py)
        dream_payload = inject_dream_payload(cwd)
        if dream_payload:
            context_parts.append(dream_payload)

        # ADR-147: surface one-line overnight dream notice
        dream_notice = surface_dream_report()
        if dream_notice:
            context_parts.append(dream_notice)

        if context_parts:
            context_output(EVENT_NAME, "\n\n".join(context_parts)).print_and_exit()

        empty_output(EVENT_NAME).print_and_exit()

    except Exception as e:
        hook_error("session-context", e)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        hook_error("session-context", e)
    finally:
        sys.exit(0)  # ALWAYS exit 0 — non-blocking requirement
