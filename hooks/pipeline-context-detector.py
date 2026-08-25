#!/usr/bin/env python3
# hook-version: 1.0.1
"""
UserPromptSubmit Hook: Pipeline Creator Context Detection

Detects when a user is requesting pipeline creation and builds an
environmental state snapshot of existing agents, skills, and hooks.
This JSON context is injected so pipeline-orchestrator-engineer can
make informed scaffolding decisions without re-scanning the filesystem.

Detection Logic:
- Check user prompt for pipeline creation triggers
- Scan agents/ for existing agent manifests
- Scan skills/ for existing skill directories
- Scan hooks/ for existing hook scripts
- Serialize related components as JSON context

Output Format:
- [pipeline-creator] Detected pipeline creation request
- [auto-skill] workflow
- Call the Skill tool with `workflow`.
- JSON environmental state as additional context

Design Principles:
- Lightweight detection (filesystem reads only, no subprocess)
- Non-blocking (always exits 0)
- Fast execution (<50ms target)
"""

import json
import os
import re
import sys
import traceback
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output, hook_error, parse_frontmatter
from stdin_timeout import read_stdin

EVENT_NAME = "UserPromptSubmit"

# Trigger patterns that indicate pipeline creation intent
PIPELINE_TRIGGERS = [
    r"\bcreate\s+(?:a\s+)?pipeline\b",
    r"\bnew\s+pipeline\b",
    r"\bscaffold\s+(?:a\s+)?pipeline\b",
    r"\bbuild\s+(?:a\s+)?pipeline\s+for\b",
    r"\bpipeline\s+creator\b",
    r"\bpipeline\s+for\b",
]

TRIGGER_PATTERN = re.compile("|".join(PIPELINE_TRIGGERS), re.IGNORECASE)


def get_user_prompt() -> str:
    """Extract user prompt from stdin JSON."""
    try:
        data = json.loads(read_stdin(timeout=2))
        return data.get("userMessage", "")
    except (json.JSONDecodeError, KeyError):
        return ""


def is_pipeline_request(prompt: str) -> bool:
    """Check if the user prompt is requesting pipeline creation."""
    return bool(TRIGGER_PATTERN.search(prompt))


def scan_agents(base_dir: Path) -> list[dict]:
    """
    Scan agents/ directory for existing agent manifests.

    Reads agents/INDEX.json when available (single JSON parse replaces ~69
    file reads + YAML parses). Falls back to filesystem glob only when
    INDEX.json is missing or unparseable.

    Returns list of {name, triggers, pairs_with, category} dicts.
    """
    agents_dir = base_dir / "agents"
    if not agents_dir.is_dir():
        return []

    # Fast path: read pre-built index
    index_path = agents_dir / "INDEX.json"
    if index_path.is_file():
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
            agents_dict = data.get("agents", {})
            if isinstance(agents_dict, dict):
                return [
                    {
                        "name": name,
                        "triggers": entry.get("triggers", []),
                        "pairs_with": entry.get("pairs_with", []),
                        "category": entry.get("category", "unknown"),
                    }
                    for name, entry in agents_dict.items()
                ]
        except (OSError, json.JSONDecodeError, AttributeError):
            pass  # Fall through to filesystem scan

    # Slow path: filesystem glob with frontmatter parsing
    agents = []
    for md_file in sorted(agents_dir.glob("*.md")):
        if md_file.name in ("README.txt", "INDEX.json"):
            continue
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
            frontmatter = parse_frontmatter(content)
            if not frontmatter:
                continue

            routing = frontmatter.get("routing", {})
            if isinstance(routing, dict):
                agents.append(
                    {
                        "name": frontmatter.get("name", md_file.stem),
                        "triggers": routing.get("triggers", []),
                        "pairs_with": routing.get("pairs_with", []),
                        "category": routing.get("category", "unknown"),
                    }
                )
            else:
                agents.append(
                    {
                        "name": frontmatter.get("name", md_file.stem),
                        "triggers": [],
                        "pairs_with": [],
                        "category": "unknown",
                    }
                )
        except OSError:
            continue

    return agents


def _skills_from_index(index_path: Path) -> list[dict] | None:
    """
    Parse a skills/INDEX.json file.

    Returns a list of {name, user_invocable, agent} dicts on success,
    or None if the file is missing or unparseable.
    """
    if not index_path.is_file():
        return None
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        entries: dict = data.get("skills") or {}
        if not isinstance(entries, dict):
            return None
        return [
            {
                "name": name,
                "user_invocable": entry.get("user_invocable", True),
                "agent": entry.get("agent", None),
            }
            for name, entry in entries.items()
        ]
    except (OSError, json.JSONDecodeError, AttributeError):
        return None


def scan_skills(base_dir: Path) -> list[dict]:
    """
    Scan skills/ directory for existing skill definitions.

    Reads skills/INDEX.json when available (one JSON parse replaces the
    per-skill SKILL.md reads and YAML parses).
    Falls back to filesystem walk per directory only when INDEX.json is
    missing or unparseable.

    Returns list of {name, user_invocable, agent} dicts.
    """
    skills: list[dict] = []

    # Skills INDEX
    skills_dir = base_dir / "skills"
    if skills_dir.is_dir():
        index_entries = _skills_from_index(skills_dir / "INDEX.json")
        if index_entries is not None:
            skills.extend(index_entries)

    # Fallback: walk skills/ subdirectories if INDEX wasn't available
    if not skills and skills_dir.is_dir():
        # Slow path: walk subdirectories and parse SKILL.md frontmatter
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.is_file():
                continue

            try:
                content = skill_md.read_text(encoding="utf-8", errors="replace")
                frontmatter = parse_frontmatter(content)
                if not frontmatter:
                    continue

                skills.append(
                    {
                        "name": frontmatter.get("name", skill_dir.name),
                        "user_invocable": frontmatter.get("user-invocable", True),
                        "agent": frontmatter.get("agent", None),
                    }
                )
            except OSError:
                continue

    return skills


def scan_hooks(base_dir: Path) -> list[dict]:
    """
    Scan hooks/ directory for existing hook scripts.

    Returns list of {name, event} dicts.
    """
    hooks_dir = base_dir / "hooks"
    if not hooks_dir.is_dir():
        return []

    hooks = []
    for py_file in sorted(hooks_dir.glob("*.py")):
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
            # Extract EVENT_NAME from the hook
            event_match = re.search(r'EVENT_NAME\s*=\s*["\'](\w+)["\']', content)
            event = event_match.group(1) if event_match else "unknown"
            hooks.append(
                {
                    "name": py_file.stem,
                    "event": event,
                }
            )
        except OSError:
            continue

    return hooks


def find_related(prompt: str, agents: list[dict], skills: list[dict]) -> dict:
    """
    Find agents and skills with triggers that overlap the user's request.

    Uses simple keyword matching against agent triggers and skill names.
    """
    # Extract meaningful words from prompt (skip common words)
    stop_words = {
        "a",
        "an",
        "the",
        "for",
        "to",
        "in",
        "on",
        "with",
        "and",
        "or",
        "create",
        "new",
        "build",
        "scaffold",
        "pipeline",
        "that",
        "which",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "need",
        "must",
        "i",
        "we",
        "you",
        "it",
    }
    keywords = {w.lower() for w in re.findall(r"\b\w+\b", prompt) if w.lower() not in stop_words and len(w) > 2}

    related_agents = []
    for agent in agents:
        triggers = [t.lower() for t in agent.get("triggers", [])]
        if any(kw in trigger for kw in keywords for trigger in triggers):
            related_agents.append(agent["name"])

    related_skills = []
    for skill in skills:
        skill_name = skill["name"].lower().replace("-", " ")
        if any(kw in skill_name for kw in keywords):
            related_skills.append(skill["name"])

    return {
        "related_agents": related_agents,
        "related_skills": related_skills,
    }


def build_environmental_state(prompt: str, base_dir: Path) -> dict:
    """Build the complete environmental state JSON."""
    agents = scan_agents(base_dir)
    skills = scan_skills(base_dir)
    hooks = scan_hooks(base_dir)
    related = find_related(prompt, agents, skills)

    return {
        "request": prompt,
        "related_agents": related["related_agents"],
        "related_skills": related["related_skills"],
        "agent_count": len(agents),
        "skill_count": len(skills),
        "hook_count": len(hooks),
    }


def main():
    """Main entry point for the hook."""
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    try:
        prompt = get_user_prompt()

        if not prompt or not is_pipeline_request(prompt):
            empty_output(EVENT_NAME).print_and_exit()

        # Determine base directory (repo root)
        base_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()

        # Build environmental state
        state = build_environmental_state(prompt, base_dir)

        if debug:
            print(
                f"[pipeline-creator] Detected request, "
                f"found {state['agent_count']} agents, "
                f"{state['skill_count']} skills, "
                f"{state['hook_count']} hooks",
                file=sys.stderr,
            )

        # Build context injection — counts only, not full name arrays
        # ADR hook-injection-condensation: emit counts to save ~4,700 chars
        related_agents = ", ".join(state["related_agents"]) or "none"
        related_skills = ", ".join(state["related_skills"]) or "none"
        injection = (
            f"[pipeline-creator] Detected pipeline creation request\n"
            "[auto-skill] workflow\n"
            "Call the Skill tool with `workflow`.\n"
            f"[pipeline-creator] Inventory: {state['agent_count']} agents, "
            f"{state['skill_count']} skills, {state['hook_count']} hooks\n"
            f"[pipeline-creator] Related agents: {related_agents}\n"
            f"[pipeline-creator] Related skills: {related_skills}"
        )

        context_output(EVENT_NAME, injection).print_and_exit()

    except Exception as e:
        hook_error("pipeline-context-detector", e)
        empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    main()
