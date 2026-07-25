#!/usr/bin/env python3
"""Fix skill path references after folder reorganization.

Scans all .md, .py, .sh, .json files for old-style skill paths
(skills/foo/) and replaces with new nested paths (skills/category/foo/).

Usage:
    python3 scripts/fix-skill-paths.py --dry-run   # preview
    python3 scripts/fix-skill-paths.py              # execute
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Import the mapping from the migration script
SKILL_MAPPING: dict[str, str] = {
    "business-ops": "business",
    "sales": "business",
    "legal": "business",
    "finance": "business",
    "hr": "business",
    "marketing": "business",
    "customer-support": "business",
    "operations": "business",
    "product-management": "business",
    "design": "business",
    "productivity": "business",
    "code-cleanup": "code-quality",
    "code-linting": "code-quality",
    "comment-quality": "code-quality",
    "condense": "code-quality",
    "python-quality-gate": "code-quality",
    "typescript-check": "code-quality",
    "universal-quality-gate": "code-quality",
    "content-calendar": "content",
    "content-engine": "content",
    "professional-communication": "content",
    "series-planner": "content",
    "topic-brainstormer": "content",
    "publish": "content",
    "wordpress-live-validation": "content",
    "x-api": "content",
    "bluesky-reader": "content",
    "reddit-moderate": "content",
    "image-to-video": "content",
    "video-editing": "content",
    "gemini-image-generator": "content",
    "nano-banana-builder": "content",
    # Private skills (voice-* profiles and other private components)
    # live in ~/private-skills, not in this repo.
    "enterprise-search": "engineering",
    "go-patterns": "engineering",
    "kotlin": "engineering",
    "php": "engineering",
    "swift": "engineering",
    "sapcc-audit": "engineering",
    "sapcc-review": "engineering",
    "distinctive-frontend-design": "frontend",
    "frontend-slides": "frontend",
    "threejs-builder": "frontend",
    "webgl-card-effects": "frontend",
    "game-asset-generator": "game",
    "game-pipeline": "game",
    "game-sprite-pipeline": "game",
    "phaser-gamedev": "game",
    "motion-pipeline": "game",
    "kubernetes": "infrastructure",
    "shell-config": "infrastructure",
    "shell-process-patterns": "infrastructure",
    "headless-cron-creator": "infrastructure",
    "cron-automation": "infrastructure",
    "endpoint-validator": "infrastructure",
    "service-health-check": "infrastructure",
    "public-web-deploy": "infrastructure",
    "do": "meta",
    "install": "meta",
    "learn": "meta",
    "retro": "meta",
    "auto-dream": "meta",
    "routing-table-updater": "meta",
    "skill-composer": "meta",
    "skill-creator": "meta",
    "skill-eval": "meta",
    "agent-comparison": "meta",
    "agent-evaluation": "meta",
    "toolkit-evolution": "meta",
    "workflow-help": "meta",
    "reference-enrichment": "meta",
    "generate-claudemd": "meta",
    "docs-sync-checker": "meta",
    "explanation-traces": "meta",
    "planning": "process",
    "quick": "process",
    "feature-lifecycle": "process",
    "pair-programming": "process",
    "subagent-driven-development": "process",
    "with-anti-rationalization": "process",
    "verification-before-completion": "process",
    "condition-based-waiting": "process",
    "socratic-debugging": "process",
    "forensics": "process",
    "plant-seed": "process",
    "read-only-ops": "process",
    "pr-workflow": "process",
    "worktree-agent": "process",
    "github-notification-triage": "process",
    "adr-consultation": "process",
    "research-pipeline": "research",
    "data-analysis": "research",
    "architecture-deepening": "research",
    "codebase-analyzer": "research",
    "codebase-overview": "research",
    "full-repo-review": "research",
    "multi-persona-critique": "research",
    "repo-value-analysis": "research",
    "roast": "research",
    "decision-helper": "research",
    "security-threat-model": "research",
    "systematic-code-review": "review",
    "parallel-code-review": "review",
    "integration-checker": "review",
    "test-driven-development": "testing",
    "e2e-testing": "testing",
    "testing-agents-with-subagents": "testing",
    "testing-preferred-patterns": "testing",
    "vitest-runner": "testing",
}

# Sort by longest name first to avoid partial matches
# e.g., "game-pipeline" before "game"
SORTED_SKILLS = sorted(SKILL_MAPPING.keys(), key=len, reverse=True)

# Build regex: match skills/SKILL_NAME/ but NOT skills/CATEGORY/SKILL_NAME/
# This avoids double-replacing already-correct paths
PATTERN = re.compile(r"skills/(" + "|".join(re.escape(s) for s in SORTED_SKILLS) + r")/")


def fix_content(content: str) -> tuple[str, int]:
    """Replace old skill paths with new category-nested paths.

    Returns (new_content, replacement_count).
    """
    count = 0

    def replacer(m: re.Match) -> str:
        nonlocal count
        skill_name = m.group(1)
        category = SKILL_MAPPING[skill_name]

        # Check if already has the category prefix (avoid double-replace)
        start = m.start()
        prefix = content[max(0, start - len(category) - 1) : start]
        if prefix.endswith(f"{category}/"):
            return m.group(0)  # Already correct

        count += 1
        return f"skills/{category}/{skill_name}/"

    result = PATTERN.sub(replacer, content)
    return result, count


def _get_git_ignored(paths: list[Path]) -> set[Path]:
    """Return the subset of paths that are git-ignored (batch check)."""
    if not paths:
        return set()
    try:
        result = subprocess.run(
            ["git", "check-ignore", "--stdin"],
            input="\n".join(str(p) for p in paths),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return {Path(line) for line in result.stdout.strip().splitlines() if line}
    except (subprocess.SubprocessError, FileNotFoundError):
        return set()


def main() -> int:
    parser = argparse.ArgumentParser(description="Fix skill path references.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changing files")
    args = parser.parse_args()

    scan_dirs = ["skills", "agents", "scripts", "hooks", "docs"]
    scan_files = ["CLAUDE.md"]
    extensions = {".md", ".py", ".sh", ".json"}

    candidates: list[Path] = []
    for d in scan_dirs:
        p = Path(d)
        if p.is_dir():
            for f in p.rglob("*"):
                if f.is_file() and f.suffix in extensions and "__pycache__" not in str(f):
                    candidates.append(f)

    ignored = _get_git_ignored(candidates)

    files_to_scan: list[Path] = [f for f in candidates if f not in ignored]
    for f in scan_files:
        p = Path(f)
        if p.is_file():
            files_to_scan.append(p)

    total_replacements = 0
    files_changed = 0

    for filepath in sorted(files_to_scan):
        try:
            content = filepath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        new_content, count = fix_content(content)
        if count > 0:
            files_changed += 1
            total_replacements += count
            if args.dry_run:
                print(f"  {filepath}: {count} replacements")
            else:
                filepath.write_text(new_content, encoding="utf-8")
                print(f"  [fixed] {filepath}: {count} replacements")

    print(f"\n{'Would fix' if args.dry_run else 'Fixed'}: {total_replacements} references in {files_changed} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
