#!/usr/bin/env python3
# hook-version: 1.1.0
"""
SessionStart Hook: Cross-Repo Agent Discovery

Discovers custom agents in the current working directory's .claude/agents/
folder and injects them into context so they can be used via /do router.

Design Principles:
- SILENT when no local agents found
- Discovers agents from cwd's .claude/agents/ directory
- Injects concise agent summaries for routing
- Fast execution (<50ms target)
- Non-blocking (always exits 0)
"""

import os
import re
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output, hook_error

EVENT_NAME = "SessionStart"


def extract_agent_info(agent_path: Path) -> dict | None:
    """Extract agent metadata from markdown file.

    Returns dict with name, description, triggers or None if invalid.
    """
    try:
        content = agent_path.read_text()

        # Look for YAML frontmatter
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            # Try to extract from content directly
            name = agent_path.stem
            # Look for first heading as description
            heading_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            description = heading_match.group(1) if heading_match else name
            return {
                "name": name,
                "file": str(agent_path),
                "description": description[:100],
                "triggers": [name.replace("-", " ")],
            }

        yaml_content = match.group(1)
        info = {"file": str(agent_path)}

        # Parse name
        name_match = re.search(r"^name:\s*(.+)$", yaml_content, re.MULTILINE)
        info["name"] = name_match.group(1).strip() if name_match else agent_path.stem

        # Parse description
        desc_match = re.search(r"^description:\s*(.+?)(?:\n[a-z]|$)", yaml_content, re.MULTILINE | re.DOTALL)
        if desc_match:
            desc = desc_match.group(1).strip().replace("\\n", " ")
            # Extract "Use this agent when..." part
            use_match = re.search(r"Use this agent when (.+?)(?:\.|$)", desc)
            if use_match:
                info["description"] = f"Use when {use_match.group(1).strip()}"
            else:
                info["description"] = desc[:100]
        else:
            info["description"] = info["name"]

        # Parse triggers from routing section
        triggers_match = re.search(r"triggers:\s*\n((?:\s+-\s+.+\n?)+)", yaml_content)
        if triggers_match:
            triggers_text = triggers_match.group(1)
            triggers = re.findall(r"-\s+[\"']?([^\"'\n]+)[\"']?", triggers_text)
            info["triggers"] = [t.strip() for t in triggers]
        else:
            # Generate triggers from name
            info["triggers"] = [info["name"].replace("-", " ")]

        return info

    except Exception as e:
        hook_error("cross-repo-agents", e)


def discover_local_agents(cwd: str) -> list[dict]:
    """Discover agents in cwd/.claude/agents/ directory."""
    agents = []
    agents_dir = Path(cwd) / ".claude" / "agents"

    if not agents_dir.exists():
        return agents

    for agent_path in agents_dir.glob("*.md"):
        info = extract_agent_info(agent_path)
        if info:
            agents.append(info)

    return sorted(agents, key=lambda x: x["name"])


def main():
    """Discover and inject local agents at session start."""
    try:
        cwd = os.getcwd()

        # Discover local agents
        agents = discover_local_agents(cwd)

        if not agents:
            empty_output(EVENT_NAME).print_and_exit()

        # Keep every local identity; names can override globally installed agents.
        agents_dir = Path(cwd) / ".claude" / "agents"
        lines = [
            f"[cross-repo] {len(agents)} local agents. Files below are relative to {agents_dir}/",
            "name [file] | description | triggers",
        ]
        for agent in agents:
            triggers = ", ".join(agent["triggers"][:3])
            filename = Path(agent["file"]).name
            lines.append(f"{agent['name']} [{filename}] | {agent['description']} | {triggers}")

        lines.append("[cross-repo] /do can dispatch these agents; read the selected file for instructions.")

        context_output(EVENT_NAME, "\n".join(lines)).print_and_exit()

    except Exception as e:
        hook_error("cross-repo-agents", e)


if __name__ == "__main__":
    main()
