#!/usr/bin/env python3
# hook-version: 2.2.0
"""
SessionStart Hook: Learning Context Loader

Loads relevant learned patterns at session start from unified learning database.
Injects high-confidence solutions into context.

ADR-147 addition: also injects the pre-built dream payload (if present and fresh)
and surfaces a one-line overnight dream notice (if dream ran recently).

Design Principles:
- SILENT unless meaningful patterns found
- Project-aware (loads patterns for current directory)
- Confidence-gated by learning_db_v2.INJECTION_MIN_CONFIDENCE
- Counts only rows that carry a real solution (learning_db_v2.hint_has_solution)
- Fast execution (<50ms target)
- Non-blocking (always exits 0)
- Pure file reader for dream integration — no LLM work, no learning.db queries
"""

import os
import sys
import time
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output, get_session_id, hook_error, record_activations_safe
from learning_db_v2 import (
    INJECTION_MIN_CONFIDENCE,
    get_stats,
    hint_has_solution,
    query_learnings,
    sanitize_for_context,
)

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

# Max learnings summarized in the injected context, and max rows fetched before
# the contentless ones are dropped.
MAX_LEARNINGS = 10
MAX_CANDIDATES = 40


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
    """Load learned patterns at session start."""
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

        # Get high-confidence learnings from learning.db
        learnings = query_learnings(
            category="error",
            min_confidence=INJECTION_MIN_CONFIDENCE,
            project_path=cwd,
            limit=MAX_CANDIDATES,
        )

        # Drop rows whose solution half is a generic stub. Most error rows carry
        # one, and a count of contentless rows ("Loaded 34 high-confidence
        # patterns") reports a pool the session can do nothing with. Fetching
        # MAX_CANDIDATES first keeps real solutions from being crowded out.
        learnings = [ln for ln in learnings if hint_has_solution(ln.get("value", ""))][:MAX_LEARNINGS]

        if learnings:
            # Record activations for ROI tracking
            debug = bool(os.environ.get("CLAUDE_HOOKS_DEBUG"))
            session_id = get_session_id()
            record_activations_safe(learnings, session_id, debug=debug)

            lines = []
            lines.append(f"[learned-context] Loaded {len(learnings)} high-confidence patterns")

            # Group by error type
            by_type = {}
            for learning in learnings:
                et = learning.get("error_type") or learning.get("topic", "unknown")
                by_type[et] = by_type.get(et, 0) + 1

            type_summary = ", ".join(f"{et}({count})" for et, count in sorted(by_type.items()))
            lines.append(f"[learned-context] Types: {type_summary}")

            # Show stats
            stats = get_stats()
            total = stats.get("total_learnings", 0)
            if total > 0:
                high_conf = stats.get("high_confidence", 0)
                lines.append(f"[learned-context] {high_conf}/{total} patterns at high confidence")

            context_parts.append("\n".join(lines))

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
