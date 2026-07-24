#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse:Agent Hook: Section-Integrity Validator

Advisory hook that validates subagent_type against agents/INDEX.json and
skills/INDEX.json before Agent dispatch. Catches two common mistakes:

1. Dispatching with a skill name instead of an agent name (the harness rejects
   this but the error is confusing).
2. Dispatching with a name that exists in neither index (typo or stale name).

This is ADVISORY only -- exit 0 always, never blocks.

Enforces PHILOSOPHY.md: "Instructions can be rationalized past. Exit codes
cannot." Replaces the prose-only "SECTION-INTEGRITY RULE" in
skills/meta/do/SKILL.md with a real hook.

ARCH-002.
"""

import json
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import context_output, hook_error
from stdin_timeout import read_stdin

_EVENT_NAME = "PreToolUse"

# Cache INDEX data per process (one invocation = one process, so this is just
# a guard against accidental double-load).
_agents_cache: set[str] | None = None
_skills_cache: set[str] | None = None


def _load_index_names(index_path: Path, key: str) -> set[str]:
    """Load names from an INDEX.json file. Returns empty set on any error."""
    try:
        with open(index_path) as f:
            data = json.load(f)
        entries = data.get(key, {})
        if isinstance(entries, dict):
            return set(entries.keys())
        return set()
    except (OSError, json.JSONDecodeError, KeyError):
        return set()


def _find_project_root(event: dict) -> Path:
    """Resolve project root from event cwd or env fallback."""
    cwd_str = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR", ".")
    return Path(cwd_str).resolve()


def _get_agent_names(project_root: Path) -> set[str]:
    """Return set of valid agent names from agents/INDEX.json."""
    global _agents_cache
    if _agents_cache is not None:
        return _agents_cache
    _agents_cache = _load_index_names(project_root / "agents" / "INDEX.json", "agents")
    # Always include "general-purpose" -- it's the default agent, not listed
    # in INDEX.json but always valid.
    _agents_cache.add("general-purpose")
    return _agents_cache


def _get_skill_names(project_root: Path) -> set[str]:
    """Return set of skill names from skills/INDEX.json."""
    global _skills_cache
    if _skills_cache is not None:
        return _skills_cache
    _skills_cache = _load_index_names(project_root / "skills" / "INDEX.json", "skills")
    return _skills_cache


def main() -> None:
    """Validate subagent_type against INDEX files."""
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    # Only act on Agent tool dispatches.
    tool_name = event.get("tool_name", "")
    if tool_name != "Agent":
        sys.exit(0)

    tool_input = event.get("tool_input", {})
    subagent_type = tool_input.get("subagent_type")

    # No subagent_type or empty -- default agent, allow through.
    if not subagent_type:
        if debug:
            print(
                "[section-integrity] No subagent_type -- default agent, allowing",
                file=sys.stderr,
            )
        sys.exit(0)

    subagent_type = str(subagent_type).strip()
    if not subagent_type:
        sys.exit(0)

    project_root = _find_project_root(event)
    agent_names = _get_agent_names(project_root)
    skill_names = _get_skill_names(project_root)

    if debug:
        print(
            f"[section-integrity] subagent_type={subagent_type!r}, "
            f"agents={len(agent_names)}, skills={len(skill_names)}",
            file=sys.stderr,
        )

    # Valid agent name -- allow silently.
    if subagent_type in agent_names:
        if debug:
            print(
                f"[section-integrity] '{subagent_type}' is a valid agent -- allowing",
                file=sys.stderr,
            )
        sys.exit(0)

    # Skill name used as agent -- warn with guidance.
    if subagent_type in skill_names:
        warning = (
            f"[section-integrity] WARNING: '{subagent_type}' is a skill name, not an agent name. "
            f"The harness will reject this dispatch. Consider using 'general-purpose' as the "
            f"agent and '{subagent_type}' as a skill."
        )
        if debug:
            print(warning, file=sys.stderr)
        context_output(_EVENT_NAME, warning).print_and_exit(0)

    # Not in either index -- warn about potential typo.
    warning = (
        f"[section-integrity] WARNING: '{subagent_type}' not found in agents/INDEX.json "
        f"or skills/INDEX.json. This may cause a dispatch failure."
    )
    if debug:
        print(warning, file=sys.stderr)
    context_output(_EVENT_NAME, warning).print_and_exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        hook_error("pretool-section-integrity-validator", e)
