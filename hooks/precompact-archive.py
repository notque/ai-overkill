#!/usr/bin/env python3
# hook-version: 2.0.0
"""
PreCompact Hook: ADR Survival Anchor

Fires before context compression to print the active pipeline session's ADR
recovery anchor, so an agent waking up post-compaction knows which ADR to
re-read, what hash to verify, and which commands to run.

The learning-archive path was removed with the rest of the learning loop: this
hook records nothing to learning.db.

Design Principles:
- Session-recovery output only
- Silent when no .adr-session.json exists
- Non-blocking (always exits 0)

Context Compression Events:
This hook fires when Claude's context window is getting full and needs
to be compressed.
"""

import json
import os
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import hook_error
from stdin_timeout import read_stdin


def inject_adr_anchor(event: dict) -> None:
    """
    Detect active pipeline session and inject ADR survival anchor.

    Looks for .adr-session.json in the project cwd. If found, prints
    a recovery anchor so agents waking up post-compaction know where
    to re-read the ADR, what hash to verify, and what commands to run.
    """
    try:
        # Determine project root: prefer cwd from event, then env var, then os.getcwd()
        cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        session_file = Path(cwd) / ".adr-session.json"

        if not session_file.exists():
            return

        with open(session_file, "r") as f:
            session = json.load(f)

        adr_path = session.get("adr_path", "")
        adr_hash = session.get("adr_hash", "")
        domain = session.get("domain", "")
        registered_at = session.get("registered_at", "")

        if not adr_path:
            return

        print("[precompact-adr] ==========================================")
        print("[precompact-adr] ACTIVE PIPELINE SESSION — ADR ANCHOR")
        print("[precompact-adr] ==========================================")
        print(f"[precompact-adr] Pipeline domain: {domain}")
        print(f"[precompact-adr] ADR location: {adr_path}")
        print(f"[precompact-adr] ADR hash: {adr_hash}")
        print(f"[precompact-adr] Registered at: {registered_at}")
        print("[precompact-adr]")
        print("[precompact-adr] RECOVERY AFTER COMPACTION:")
        print(f"[precompact-adr]   1. Read this ADR: {adr_path}")
        print(
            f"[precompact-adr]   2. Verify hash:  python3 ~/.claude/scripts/adr-query.py verify --adr {adr_path} --hash {adr_hash}"
        )
        print(
            f"[precompact-adr]   3. Get your context: python3 ~/.claude/scripts/adr-query.py context --adr {adr_path} --role orchestrator"
        )
        print("[precompact-adr]")
        print("[precompact-adr] COMPLIANCE CHECK FOR ANY COMPONENT FILE:")
        print("[precompact-adr]   python3 ~/.claude/scripts/adr-compliance.py check --file {file} \\")
        print("[precompact-adr]     --step-menu ~/.claude/skills/pipeline-scaffolder/references/step-menu.md \\")
        print(
            "[precompact-adr]     --spec-format ~/.claude/skills/pipeline-scaffolder/references/pipeline-spec-format.md"
        )
        print("[precompact-adr] ==========================================")

    except Exception as e:
        hook_error("precompact-archive", e)


def main():
    """Print the ADR survival anchor before context compression."""
    try:
        # Read event data from stdin
        event_data = read_stdin(timeout=2)
        if not event_data:
            return

        event = json.loads(event_data)

        # Only process PreCompact events
        event_type = event.get("hook_event_name") or event.get("type", "")
        if event_type != "PreCompact":
            return

        inject_adr_anchor(event)

    except json.JSONDecodeError as e:
        hook_error("precompact-archive", e)
    except Exception as e:
        hook_error("precompact-archive", e)
    finally:
        # CRITICAL: Always exit 0 to prevent blocking Claude Code
        sys.exit(0)


if __name__ == "__main__":
    main()
