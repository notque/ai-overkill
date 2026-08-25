#!/usr/bin/env python3
"""Add typed Companion Skills, Agents, and Pipelines sections to agents.

Scans agents/*.md, parses YAML frontmatter for routing.pairs_with, classifies
each paired entry against the component indexes, and injects separate companion
tables before '### Optional Behaviors' or '### Default Behaviors'.

Existing companion sections are removed and regenerated to stay current.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / "agents"
SKILLS_DIR = REPO_ROOT / "skills"
PIPELINES_DIR = REPO_ROOT / "skills" / "workflow" / "references"
SKILL_INDEX = SKILLS_DIR / "INDEX.json"
AGENT_INDEX = AGENTS_DIR / "INDEX.json"
PIPELINE_INDEX = PIPELINES_DIR / "pipeline-index.json"

SKILLS_MARKER = "### Companion Skills"
PIPELINES_MARKER = "### Companion Pipelines"
AGENTS_MARKER = "### Companion Agents"
ALLOWED_TOOLS_BLOCK = re.compile(r"(?m)^(allowed-tools:\n)((?:  - [^\n]+\n)+)")

sys.path.insert(0, str(REPO_ROOT))

from scripts.lib.frontmatter import parse_frontmatter as _parse_frontmatter


def parse_frontmatter(text: str) -> tuple[dict | None, str]:
    """Extract YAML frontmatter and the remaining body from a markdown file."""
    return _parse_frontmatter(text)


def extract_description(frontmatter: dict) -> str:
    """Pull a one-line description from frontmatter, stripping examples and newlines."""
    desc = frontmatter.get("description", "")
    if not desc:
        return ""
    # Take only text before any <example> block or double newline (paragraph break)
    desc = re.split(r"<example>|\n\n", str(desc))[0]
    # Collapse whitespace
    desc = re.sub(r"\s+", " ", desc).strip()
    # Truncate if very long (keep it readable in a table)
    if len(desc) > 120:
        desc = desc[:117] + "..."
    return desc


def load_component_index(path: Path, field: str) -> dict[str, dict]:
    """Load one component index or fail with an actionable error."""
    try:
        entries = json.loads(path.read_text(encoding="utf-8")).get(field)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path.relative_to(REPO_ROOT)}: {exc}") from exc
    if not isinstance(entries, dict):
        raise ValueError(f"{path.relative_to(REPO_ROOT)} has no {field!r} object")
    return entries


def component_indexes() -> tuple[dict[str, dict], dict[str, dict], dict[str, dict]]:
    """Return the active skill, pipeline, and agent indexes."""
    return (
        load_component_index(SKILL_INDEX, "skills"),
        load_component_index(PIPELINE_INDEX, "pipelines"),
        load_component_index(AGENT_INDEX, "agents"),
    )


def resolve_paired_description(name: str, entry: dict | None = None) -> str | None:
    """Look up description for a paired skill or agent by name.

    Checks skills/{name}/SKILL.md first, then pipelines/, then agents/{name}.md.
    """
    if entry:
        desc = entry.get("description") or entry.get("short_description")
        if desc:
            return extract_description({"description": desc})

    # Try agent
    agent_path = AGENTS_DIR / f"{name}.md"
    if agent_path.exists():
        fm, _ = parse_frontmatter(agent_path.read_text())
        if fm:
            return extract_description(fm)

    return None


def classify_pairs(
    pairs: list[str],
    indexes: tuple[dict[str, dict], dict[str, dict], dict[str, dict]] | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """Split pairs_with entries into skills, pipelines, and agents."""
    skill_index, pipeline_index, agent_index = indexes or component_indexes()
    skills: list[str] = []
    pipelines: list[str] = []
    agents: list[str] = []
    for name in pairs:
        if name not in skill_index and name not in pipeline_index and name not in agent_index:
            raise ValueError(f"pairs_with entry {name!r} does not resolve to an indexed component")
        # A callable skill package can also own a same-named workflow reference.
        # Prefer the callable skill. A pipeline-only name remains a pipeline.
        if name in skill_index:
            skills.append(name)
        elif name in pipeline_index:
            pipelines.append(name)
        else:
            agents.append(name)
    return skills, pipelines, agents


def build_section(names: list[str], kind: str, index: dict[str, dict]) -> str:
    """Build one typed companion markdown section.

    Args:
        names: List of skill/pipeline names.
        kind: Either "Skills" or "Pipelines".
    """
    rows: list[str] = []
    for name in names:
        desc = resolve_paired_description(name, index.get(name))
        if desc is None:
            desc = f"(description not found for `{name}`)"
        if kind == "Skills":
            action = f"Call the Skill tool with `{name}`."
        elif kind == "Agents":
            action = "Return this handoff to the coordinator for Agent-tool dispatch."
        else:
            action = "Run through workflow dispatch; this name is not a skill."
        rows.append(f"| `{name}` | {desc} | {action} |")

    table_rows = "\n".join(rows)

    if kind == "Skills":
        return (
            "### Companion Skills\n"
            "\n"
            "| Skill | When to call | Action |\n"
            "|-------|--------------|--------|\n"
            f"{table_rows}\n"
            "\n"
            "**Rule**: Use the exact action in each applicable row.\n"
        )
    if kind == "Agents":
        return (
            "### Companion Agents\n\n"
            "| Agent | When to dispatch | Action |\n"
            "|-------|------------------|--------|\n"
            f"{table_rows}\n\n"
            "**Rule**: These are agents. The Skill tool cannot invoke them.\n"
        )
    return (
        "### Companion Pipelines\n"
        "\n"
        "| Pipeline | When to run | Action |\n"
        "|----------|-------------|--------|\n"
        f"{table_rows}\n"
        "\n"
        "**Rule**: Pipelines use workflow dispatch, not the Skill tool.\n"
    )


def remove_existing_sections(content: str) -> str:
    """Remove existing Companion Skills and Companion Pipelines sections.

    Removes from the ### heading through the **Rule** line (inclusive).
    """
    for marker in [SKILLS_MARKER, PIPELINES_MARKER, AGENTS_MARKER]:
        idx = content.find(marker)
        if idx == -1:
            continue

        # Find the end of this section: next ### heading or end of content
        rest = content[idx:]
        # Find the **Rule** line that ends the section
        rule_match = re.search(r"\*\*Rule\*\*:.*\n", rest)
        if rule_match:
            end_idx = idx + rule_match.end()
        else:
            # Fallback: find next ### heading
            next_heading = re.search(r"\n###\s", rest[len(marker) :])
            if next_heading:
                end_idx = idx + len(marker) + next_heading.start()
            else:
                end_idx = len(content)

        # Remove the section, cleaning up extra blank lines
        before = content[:idx].rstrip("\n")
        after = content[end_idx:].lstrip("\n")
        content = before + "\n\n" + after

    return content


def insert_sections(
    content: str,
    skills_section: str | None,
    pipelines_section: str | None,
    agents_section: str | None,
) -> str | None:
    """Insert Companion Skills and/or Pipelines sections before Optional/Default Behaviors."""
    combined = ""
    if pipelines_section:
        combined += pipelines_section + "\n"
    if agents_section:
        combined += agents_section + "\n"
    if skills_section:
        combined += skills_section + "\n"

    if not combined:
        return None

    # Prefer the operator-context behavior boundary, then the capabilities boundary.
    for marker in [
        "### Optional Behaviors",
        "### Default Behaviors",
        "## Capabilities & Limitations",
        "## Error Handling",
    ]:
        idx = content.find(marker)
        if idx != -1:
            before = content[:idx].rstrip("\n")
            after = content[idx:]
            return f"{before}\n\n{combined}{after}"
    return f"{content.rstrip()}\n\n{combined.rstrip()}\n"


def ensure_skill_tool(content: str, skill_names: list[str]) -> str:
    """Grant the Skill tool when generated instructions contain skill calls."""
    if not skill_names:
        return content
    fm, _ = parse_frontmatter(content)
    tools = fm.get("allowed-tools", []) if fm else []
    if isinstance(tools, list) and "Skill" in tools:
        return content
    match = ALLOWED_TOOLS_BLOCK.search(content)
    if not match:
        raise ValueError("agent with companion skills has no block-style allowed-tools list")
    replacement = match.group(1) + match.group(2) + "  - Skill\n"
    return content[: match.start()] + replacement + content[match.end() :]


def render_agent(agent_path: Path) -> str | None:
    """Return the fully regenerated agent text, or None when no sections apply."""
    content = agent_path.read_text()

    fm, _ = parse_frontmatter(content)
    if fm is None:
        return None

    routing = fm.get("routing", {})
    if not isinstance(routing, dict):
        return None

    pairs = routing.get("pairs_with", [])
    if not pairs:
        return None

    skill_index, pipeline_index, agent_index = component_indexes()
    skill_names, pipeline_names, agent_names = classify_pairs(pairs, (skill_index, pipeline_index, agent_index))
    content = ensure_skill_tool(content, skill_names)

    # Remove existing sections first (always regenerate)
    content = remove_existing_sections(content)

    # Build new sections
    skills_section = build_section(skill_names, "Skills", skill_index) if skill_names else None
    pipelines_section = build_section(pipeline_names, "Pipelines", pipeline_index) if pipeline_names else None
    agents_section = build_section(agent_names, "Agents", agent_index) if agent_names else None

    return insert_sections(content, skills_section, pipelines_section, agents_section)


def process_agent(agent_path: Path, *, write: bool = True) -> bool:
    """Process a single agent file, adding/updating Companion sections."""
    new_content = render_agent(agent_path)
    if new_content is None:
        print(f"  SKIP (no insertion point): {agent_path.name}")
        return False

    old_content = agent_path.read_text()
    if new_content == old_content:
        return False
    if write:
        agent_path.write_text(new_content)
    fm, _ = parse_frontmatter(new_content)
    pairs = fm.get("routing", {}).get("pairs_with", []) if fm else []
    skill_names, pipeline_names, agent_names = classify_pairs(pairs)
    parts: list[str] = []
    if skill_names:
        parts.append(f"{len(skill_names)} skill(s)")
    if pipeline_names:
        parts.append(f"{len(pipeline_names)} pipeline(s)")
    if agent_names:
        parts.append(f"{len(agent_names)} agent(s)")
    print(f"  UPDATED: {agent_path.name} ({', '.join(parts)})")
    return True


def main() -> int:
    """Scan all agent .md files and add Companion Skills/Pipelines sections."""
    if not AGENTS_DIR.is_dir():
        print(f"ERROR: agents directory not found at {AGENTS_DIR}", file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 when generated sections are stale")
    parser.add_argument("--dry-run", action="store_true", help="report changes without writing")
    args = parser.parse_args()

    agent_files = sorted(AGENTS_DIR.glob("*.md"))
    updated = 0
    skipped_no_pairs = 0

    print(f"Scanning {len(agent_files)} agent files in {AGENTS_DIR}...")
    for agent_path in agent_files:
        content = agent_path.read_text()
        fm, _ = parse_frontmatter(content)
        if fm is None:
            continue

        routing = fm.get("routing", {})
        if not isinstance(routing, dict):
            continue

        pairs = routing.get("pairs_with", [])
        if not pairs:
            skipped_no_pairs += 1
            continue

        if process_agent(agent_path, write=not (args.check or args.dry_run)):
            updated += 1

    print(f"\nDone. Updated: {updated}, No pairs_with: {skipped_no_pairs}")
    return 1 if args.check and updated else 0


if __name__ == "__main__":
    sys.exit(main())
