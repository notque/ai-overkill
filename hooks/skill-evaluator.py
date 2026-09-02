#!/usr/bin/env python3
# hook-version: 1.0.0
"""
UserPromptSubmit Hook: Dynamic Skill/Agent Evaluation

Discovers available skills and agents from filesystem,
injecting a targeted evaluation protocol when meaningful.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import hook_error

REPO_ROOT = Path(__file__).parent.parent

# Complete agent routing guide with when-to-use descriptions
AGENT_ROUTING = {
    # Language/Framework Experts
    "golang-general-engineer": "Go development, concurrency, testing, interfaces",
    "python-general-engineer": "Python development, async, typing, pytest",
    "python-openstack-engineer": "OpenStack Python, oslo libraries, Tempest",
    "typescript-frontend-engineer": "TypeScript, React, type safety, Zod",
    "typescript-debugging-engineer": "TypeScript debugging, race conditions, async issues",
    "nodejs-api-engineer": "Node.js backends, Express, auth, webhooks",
    "nextjs-ecommerce-engineer": "Next.js e-commerce, Stripe, cart, checkout",
    "react-portfolio-engineer": "React portfolios, galleries, image optimization",
    # Infrastructure
    "kubernetes-helm-engineer": "K8s, Helm charts, deployments, troubleshooting",
    "ansible-automation-engineer": "Ansible playbooks, roles, automation",
    "prometheus-grafana-engineer": "Monitoring, alerting, dashboards, metrics",
    "opensearch-elasticsearch-engineer": "Search clusters, indexing, queries",
    "rabbitmq-messaging-engineer": "Message queues, routing, clustering",
    # Data & Docs
    "database-engineer": "PostgreSQL, Prisma, schema design, optimization",
    "sqlite-peewee-engineer": "SQLite, Peewee ORM, migrations",
    "technical-documentation-engineer": "API docs, READMEs, technical writing",
    "technical-journalist-writer": "Technical articles, journalism, explainers",
    # UI/Performance
    "ui-design-engineer": "UI/UX, Tailwind, accessibility, animations",
    "performance-optimization-engineer": "Core Web Vitals, bundle size, caching",
    "testing-automation-engineer": "Unit/E2E tests, Playwright, CI pipelines",
    # Meta/Creation
    "skill-creator": "Create new Claude skills",
    "hook-development-engineer": "Create Claude Code hooks, event handlers",
    "mcp-local-docs-engineer": "Build MCP servers for documentation",
    # Coordination
    "research-coordinator-engineer": "Complex research, multi-source analysis",
    "project-coordinator-engineer": "Multi-agent orchestration, TodoWrite",
    # Consolidated reviewers
    "reviewer-code": "Code quality, style, sustainability, precision",
    "reviewer-domain": "Business logic, ADR compliance, production readiness",
    "reviewer-perspectives": "Contrarian analysis, user advocacy, process review",
    "reviewer-system": "Security, concurrency, silent failures, config safety",
}

# Complete skill routing guide
SKILL_ROUTING = {
    # Code Quality
    "systematic-code-review": "Review code changes, PRs, security audits",
    "systematic-debugging": "4-phase root cause analysis, no guessing",
    "systematic-refactoring": "Safe refactoring with phase gates",
    "test-driven-development": "RED-GREEN-REFACTOR cycle",
    "code-cleanup": "Stale TODOs, unused imports, missing types",
    "comment-quality": "Fix temporal/development-activity comments",
    # Language-Specific Quality
    "go-patterns": "Go testing, concurrency, errors, review, quality, sapcc conventions",
    "python-quality-gate": "ruff, pytest, mypy, bandit",
    "universal-quality-gate": "Multi-language quality checks",
    "code-linting": "Python (ruff) + JavaScript (Biome) linting",
    # Git/CI
    "pr-workflow": "PR lifecycle umbrella: commit, codex-review, sync, status, fix, cleanup, miner, branch-name, ci-check",
    # Research/Analysis
    "codebase-overview": "Rapidly understand unfamiliar codebases",
    # codebase-analyzer: demoted to codebase-overview
    "pr-miner": "Mine PR comments for coding standards",
    "pr-mining-coordinator": "Coordinate PR mining operations",
    # Process
    "workflow-orchestrator": "Multi-step tasks, brainstorming, planning",
    "verification-before-completion": "Multiple validation layers before done",
    "read-only-ops": "Exploration and reporting without modifications",
    # skill-composer: demoted to workflow
    # Evaluation
    "agent-evaluation": "Evaluate agents/skills for quality",
    "agent-comparison": "A/B test agent variants",
    "roast": "5-persona constructive criticism",
    # Specialized
    "distinctive-frontend-design": "Unique aesthetics, avoid generic AI patterns",
    "professional-communication": "Transform technical to business formats",
    "service-health-check": "Service health, endpoint validation, CVE source auditing",
    "cron-automation": "Audit and create cron jobs with safety",
    "docs-sync-checker": "Verify all skills/agents documented",
    "routing-table-updater": "Maintain /do routing tables",
    # Plan Management
    "planning": "Planning umbrella: spec, pre-plan, plan-files, check, manage, pause, resume",
}


def classify_complexity(prompt: str) -> str:
    """Classify request complexity."""
    prompt_lower = prompt.lower()
    word_count = len(prompt.split())

    if word_count < 10 and "?" in prompt:
        return "trivial"

    complex_signals = [
        "implement",
        "create",
        "build",
        "refactor",
        "review",
        "analyze",
        "debug",
        "fix",
        "add feature",
        "and also",
        "then",
        "first",
        "after that",
    ]

    complex_count = sum(1 for s in complex_signals if s in prompt_lower)

    if complex_count >= 2 or word_count > 50:
        return "complex"
    elif complex_count >= 1 or word_count > 20:
        return "medium"
    return "simple"


def get_evaluation_prompt(complexity: str) -> str:
    """Generate skill evaluation injection prompt."""

    # Group agents by category for readability
    agent_sections = """
**Agents by Domain:**
- Go: golang-general-engineer
- Python: python-general-engineer, python-openstack-engineer (OpenStack)
- TypeScript/React: typescript-frontend-engineer, typescript-debugging-engineer (bugs)
- Node.js: nodejs-api-engineer, nextjs-ecommerce-engineer, react-portfolio-engineer
- Infra: kubernetes-helm-engineer, ansible-automation-engineer
- Monitoring: prometheus-grafana-engineer, opensearch-elasticsearch-engineer
- Data: database-engineer (PostgreSQL), sqlite-peewee-engineer
- Docs: technical-documentation-engineer, technical-journalist-writer
- UI: ui-design-engineer, performance-optimization-engineer
- Testing: testing-automation-engineer
- Meta: skill-creator, hook-development-engineer
- Research: research-coordinator-engineer, project-coordinator-engineer
- Review: reviewer-code, reviewer-domain, reviewer-perspectives, reviewer-system
- Critique: roast skill (5 personas: contrarian, newcomer, builder, senior, pedant)"""

    skill_sections = """
**Skills by Purpose:**
- Code Review: systematic-code-review, systematic-debugging, systematic-refactoring
- Quality Gates: go-patterns, python-quality-gate, universal-quality-gate
- Git: pr-workflow (umbrella: commit, codex-review, sync, status, fix, cleanup, miner, branch-name, ci-check)
- Process: workflow-orchestrator, verification-before-completion, test-driven-development
- Analysis: codebase-overview, agent-evaluation
- Cleanup: code-cleanup, comment-quality, code-linting"""

    phases = {
        "trivial": "",
        "simple": "**SIMPLE**: UNDERSTAND → EXECUTE → VERIFY",
        "medium": "**MEDIUM**: UNDERSTAND (restate) → PLAN (steps) → EXECUTE → VERIFY",
        "complex": """**COMPLEX** (ALL required):
1. UNDERSTAND: Request, criteria, assumptions
2. PLAN: Steps, tools, risks
3. EXECUTE: Show progress
4. VERIFY: Criteria met, no side effects""",
    }

    systematic = phases.get(complexity, "")

    return f"""<skill-evaluation-protocol>
EVALUATE before responding:
{agent_sections}
{skill_sections}

{systematic}

Route with: `skill: [name]` or Task tool with subagent_type
</skill-evaluation-protocol>"""


def should_skip(prompt: str) -> bool:
    """Determine if prompt should skip evaluation."""
    prompt_lower = prompt.lower().strip()

    if len(prompt_lower) < 20:
        return True

    skip_patterns = [
        "hello",
        "hi ",
        "hey ",
        "thanks",
        "thank you",
        "what is",
        "how do i",
        "can you explain",
        "help",
    ]

    if any(p in prompt_lower for p in skip_patterns):
        return True

    return bool(prompt_lower.endswith("?") and len(prompt_lower) < 50)


def main():
    """Process UserPromptSubmit hook event.

    DISABLED: The routing cheat sheet this hook injects (~1.8KB per prompt)
    is redundant. When /do is active, SKILL.md has full routing tables.
    When /do is NOT active, the user is talking directly and doesn't need
    routing guidance injected. The Agent tool descriptions in the system
    prompt already list all available agents.
    """
    return


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        hook_error("skill-evaluator", e)
    finally:
        sys.exit(0)
