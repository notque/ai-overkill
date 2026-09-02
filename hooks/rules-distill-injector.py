#!/usr/bin/env python3
# hook-version: 1.0.0
"""
SessionStart Hook: Rules Distillation Candidate Injector — ADR-114.

Reads ~/.claude/learning/rules-distill-pending.json and, if pending
proposals exist, injects a <rules-distill-candidates> block into the
session additionalContext.

Design Principles:
- SessionStart event, once: true (injects once per session)
- Sub-50ms execution (file read only, no subprocess)
- Always exits 0 — purely advisory
- NEVER auto-applies proposals — user must explicitly approve in-session
- Silent when no pending candidates exist
"""

import json
import os
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output, hook_error
from stdin_timeout import read_stdin

EVENT_NAME = "SessionStart"

PENDING_JSON = Path.home() / ".claude" / "learning" / "rules-distill-pending.json"


def load_pending_candidates() -> list[dict]:
    """Load pending candidates from rules-distill-pending.json.

    Returns only candidates with status='pending'.
    Returns [] if file missing, empty, or malformed.
    """
    if not PENDING_JSON.exists():
        return []
    try:
        data = json.loads(PENDING_JSON.read_text(encoding="utf-8"))
        candidates = data.get("candidates", [])
        return [c for c in candidates if c.get("status") == "pending"]
    except (json.JSONDecodeError, OSError):
        return []


def build_injection(candidates: list[dict], distilled_at: str) -> str:
    """Build the <rules-distill-candidates> context block."""
    lines = [
        "<rules-distill-candidates>",
        f"**Rules Distillation** — {len(candidates)} candidate principle(s) awaiting review.",
        f"Last distilled: {distilled_at or 'unknown'}",
        "",
        "These principles appear in 2+ skills and passed the four-layer filter",
        "(multi-skill, actionable, violation risk, not already in shared-patterns/).",
        "",
        "These are proposals. Apply none of them until the user explicitly",
        "approves, skips, or defers each candidate.",
        "",
        "| # | Confidence | Verdict | Principle |",
        "|---|-----------|---------|-----------|",
    ]

    for i, c in enumerate(candidates, 1):
        conf = c.get("confidence", "?")
        verdict = c.get("verdict", "Append")
        principle = c.get("principle", "")
        # Truncate long principles for the table
        display = principle[:80] + ("..." if len(principle) > 80 else "")
        lines.append(f"| {i} | {conf} | {verdict} | {display} |")

    lines.append("")
    lines.append("**Details:**")
    for i, c in enumerate(candidates, 1):
        principle = c.get("principle", "")
        skills = ", ".join(c.get("skills", []))
        target = c.get("target", "skills/shared-patterns/")
        draft = c.get("draft", principle)
        lines.append(f"")
        lines.append(f"**[{i}]** {principle}")
        lines.append(f"  Sources: {skills}")
        lines.append(f"  Target:  {target}")
        lines.append(f"  Draft:   {draft}")

    lines.append("")
    lines.append("To approve: 'approve rule N' | To skip: 'skip rule N' | To defer: 'defer rule N'")
    lines.append("To approve all: 'approve all rules'")
    lines.append("</rules-distill-candidates>")

    return "\n".join(lines)


def main() -> None:
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    try:
        # Read stdin (SessionStart provides session metadata)
        try:
            raw = read_stdin(timeout=2)
            data = json.loads(raw) if raw.strip() else {}
        except (json.JSONDecodeError, Exception):
            data = {}

        # Load pending candidates (fast file read only)
        candidates = load_pending_candidates()

        if not candidates:
            if debug:
                print("[rules-distill-injector] No pending candidates — silent exit", file=sys.stderr)
            empty_output(EVENT_NAME).print_and_exit()

        # Load distilled_at timestamp for the header
        distilled_at = ""
        try:
            raw_data = json.loads(PENDING_JSON.read_text(encoding="utf-8"))
            distilled_at = raw_data.get("distilled_at", "")
        except Exception:
            pass

        if debug:
            print(
                f"[rules-distill-injector] Injecting {len(candidates)} pending candidate(s)",
                file=sys.stderr,
            )

        injection = build_injection(candidates, distilled_at)
        context_output(EVENT_NAME, injection).print_and_exit()

    except Exception as e:
        hook_error("rules-distill-injector", e)
        empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[rules-distill-injector] Fatal: {e}", file=sys.stderr)
    finally:
        sys.exit(0)
