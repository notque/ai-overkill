#!/usr/bin/env python3
"""Audit and enforce allowed-tools declarations in agent frontmatter.

ADR-063: Tool Restriction Enforcement.
Classifies agents by role type and adds/validates allowed-tools.

Usage:
  python3 scripts/audit-tool-restrictions.py --audit     # Report only
  python3 scripts/audit-tool-restrictions.py --fix        # Add missing allowed-tools
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.lib.frontmatter import parse_frontmatter as _parse_frontmatter

# Role classifications and their allowed tools
ROLE_TOOLS = {
    "reviewer-readonly": [
        "Read",
        "Glob",
        "Grep",
        "Agent",
        "WebFetch",
        "WebSearch",
    ],
    "reviewer-with-fix": [
        "Read",
        "Edit",
        "Write",
        "Glob",
        "Grep",
        "Bash",
        "Agent",
    ],
    "research": [
        "Read",
        "Glob",
        "Grep",
        "WebFetch",
        "WebSearch",
        "Agent",
    ],
    "orchestrator": [
        "Read",
        "Glob",
        "Grep",
        "Agent",
        "Bash",
    ],
    "code-modifier": [
        "Read",
        "Edit",
        "Write",
        "Bash",
        "Glob",
        "Grep",
        "Agent",
    ],
    "documentation": [
        "Read",
        "Write",
        "Glob",
        "Grep",
        "WebFetch",
        "WebSearch",
    ],
}

# Explicit agent-to-role mappings
AGENT_ROLES = {
    # Consolidated reviewers - read-only by default
    "reviewer-code": "reviewer-readonly",
    "reviewer-domain": "reviewer-readonly",
    "reviewer-perspectives": "reviewer-readonly",
    "reviewer-system": "reviewer-readonly",
    # Research/orchestration - no code modification
    "research-coordinator-engineer": "research",
    "research-subagent-executor": "research",
    "project-coordinator-engineer": "orchestrator",
    "pipeline-orchestrator-engineer": "orchestrator",
    "system-upgrade-engineer": "orchestrator",
    # Documentation - write docs but no bash
    "technical-documentation-engineer": "documentation",
    "technical-journalist-writer": "documentation",
    # Code modifiers - full access (their job is to write code)
    "ansible-automation-engineer": "code-modifier",
    "data-engineer": "code-modifier",
    "database-engineer": "code-modifier",
    "github-profile-rules-engineer": "research",
    "golang-general-engineer": "code-modifier",
    "hook-development-engineer": "code-modifier",
    "kubernetes-helm-engineer": "code-modifier",
    "mcp-local-docs-engineer": "code-modifier",
    "nextjs-ecommerce-engineer": "code-modifier",
    "nodejs-api-engineer": "code-modifier",
    "opensearch-elasticsearch-engineer": "code-modifier",
    "performance-optimization-engineer": "code-modifier",
    "perses-engineer": "code-modifier",
    "prometheus-grafana-engineer": "code-modifier",
    "python-general-engineer": "code-modifier",
    "python-openstack-engineer": "code-modifier",
    "rabbitmq-messaging-engineer": "code-modifier",
    "react-portfolio-engineer": "code-modifier",
    "skill-creator": "code-modifier",
    "sqlite-peewee-engineer": "code-modifier",
    "testing-automation-engineer": "code-modifier",
    "typescript-debugging-engineer": "code-modifier",
    "typescript-frontend-engineer": "code-modifier",
    "ui-design-engineer": "code-modifier",
}


def parse_frontmatter(content: str) -> tuple[dict, str, str]:
    """Parse YAML frontmatter from markdown content.
    Returns (frontmatter_dict, frontmatter_text, body_text).
    """
    fm, body = _parse_frontmatter(content)
    if fm is None:
        return {}, "", content
    fm_text = content[3 : content.find("---", 3)].strip()
    return fm, fm_text, body


def has_allowed_tools(content: str) -> bool:
    """Check if frontmatter contains allowed-tools."""
    return "allowed-tools:" in content.split("---")[1] if content.count("---") >= 2 else False


def add_allowed_tools(content: str, tools: list[str]) -> str:
    """Add allowed-tools to frontmatter."""
    if content.count("---") < 2:
        return content

    parts = content.split("---", 2)
    fm = parts[1]

    # Build tools YAML
    tools_yaml = "allowed-tools:\n" + "\n".join(f"  - {t}" for t in tools)

    # Insert before the closing ---
    fm = fm.rstrip() + "\n" + tools_yaml + "\n"

    return "---" + fm + "---" + parts[2]


def audit(agents_dir: Path, fix: bool = False) -> int:
    """Audit all agents for allowed-tools compliance."""
    issues = 0
    fixed = 0

    for agent_file in sorted(agents_dir.glob("*.md")):
        name = agent_file.stem
        content = agent_file.read_text()

        role = AGENT_ROLES.get(name)
        if role is None:
            print(f"  UNKNOWN: {name} — not in classification table")
            issues += 1
            continue

        expected_tools = ROLE_TOOLS[role]
        has_tools = has_allowed_tools(content)

        if not has_tools:
            if fix:
                new_content = add_allowed_tools(content, expected_tools)
                agent_file.write_text(new_content)
                print(f"  FIXED: {name} — added {role} tools ({len(expected_tools)} tools)")
                fixed += 1
            else:
                print(f"  MISSING: {name} — needs {role} tools")
                issues += 1
        else:
            print(f"  OK: {name} — has allowed-tools")

    return issues if not fix else fixed


def main():
    parser = argparse.ArgumentParser(description="Audit agent tool restrictions (ADR-063)")
    parser.add_argument("--audit", action="store_true", help="Report missing allowed-tools")
    parser.add_argument("--fix", action="store_true", help="Add missing allowed-tools to agents")
    args = parser.parse_args()

    if not args.audit and not args.fix:
        args.audit = True

    agents_dir = Path(__file__).resolve().parent.parent / "agents"
    if not agents_dir.exists():
        print(f"Error: agents directory not found at {agents_dir}")
        sys.exit(1)

    print(f"Auditing {len(list(agents_dir.glob('*.md')))} agents in {agents_dir}")
    print(f"Mode: {'FIX' if args.fix else 'AUDIT'}")
    print()

    result = audit(agents_dir, fix=args.fix)

    if args.fix:
        print(f"\nFixed {result} agents")
    else:
        if result > 0:
            print(f"\n{result} agents need allowed-tools declarations")
            print("Run with --fix to add them")
            sys.exit(1)
        else:
            print("\nAll agents have allowed-tools declarations")


if __name__ == "__main__":
    main()
