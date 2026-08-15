#!/usr/bin/env python3
"""Validate the ``promoted_to`` retirement tag on skills.

``promoted_to: <successor>`` marks a skill whose content was folded into an
umbrella skill. ``scripts/generate-skill-index.py`` skips those husks, so the
tag removes the skill from skills/INDEX.json and therefore from the routing
manifest — the toolkit's own delete switch, applied by one frontmatter line
with no confirmation anywhere.

Two ways that goes wrong, one check each:

  P1 PHANTOM-SUCCESSOR   The successor names a skill that exists nowhere on
                         disk. The husk is retired in favour of nothing: the
                         skill leaves routing and no replacement carries its
                         traffic. Live case at the time of writing —
                         skills/meta/do/SKILL.md promoted to ``native-router``,
                         which silently dropped /do, the toolkit's own primary
                         router, out of the skill catalogue.

  P2 INVOCABLE-EXCLUDED  The husk still declares ``user-invocable: true``. It
                         advertises a user entry point the index no longer
                         carries, so ``/skill-name`` points at a skill the
                         router cannot see.

Resolution order for a successor: repo skills/ (nested and flat layouts),
the merged skill index, then the deployed and private overlay roots — the
same roots scripts/validate-index-integrity.py resolves against, so a
private-overlay successor counts as real.

Exit codes:
    0 — every promoted_to tag resolves and no husk stays user-invocable
    1 — one or more failures

Usage:
    python3 scripts/validate-promoted-successors.py
    python3 scripts/validate-promoted-successors.py --verbose
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.lib.frontmatter import parse_frontmatter


def skill_files(repo_root: Path) -> list[Path]:
    """Every SKILL.md under skills/, in both the nested and flat layouts."""
    skills_dir = repo_root / "skills"
    found = set(skills_dir.glob("*/SKILL.md")) | set(skills_dir.glob("*/*/SKILL.md"))
    return sorted(found)


def indexed_skill_names(repo_root: Path) -> set[str]:
    """Skill names in the merged tracked + local overlay index.

    Reading the index as well as the disk lets a successor that only ships in
    the private overlay resolve. A missing or unparseable index contributes
    nothing, which can only produce a stricter result, never a falsely clean one.
    """
    names: set[str] = set()
    index_dir = repo_root / "skills"
    for path in (index_dir / "INDEX.json", index_dir / "INDEX.local.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        skills = data.get("skills")
        if isinstance(skills, dict):
            names.update(skills)
    return names


def overlay_roots() -> list[Path]:
    """Deployed and private roots where a successor's SKILL.md may live."""
    candidates = [Path.home() / ".claude", Path.home() / "private-skills"]
    return [r for r in candidates if r.is_dir()]


def successor_exists(name: str, repo_root: Path, indexed: set[str]) -> bool:
    """True when *name* resolves to a real skill in any known root."""
    if not name:
        return False
    if name in indexed:
        return True
    roots = [repo_root, *overlay_roots()]
    for root in roots:
        skills_dir = root / "skills"
        if (skills_dir / name / "SKILL.md").is_file():
            return True
        if any(p.is_file() for p in skills_dir.glob(f"*/{name}/SKILL.md")):
            return True
    # Private overlay stores skills as <root>/<category>/<name>/SKILL.md.
    private = Path.home() / "private-skills"
    return private.is_dir() and any(p.is_file() for p in private.glob(f"*/{name}/SKILL.md"))


def check(repo_root: Path, verbose: bool = False) -> list[str]:
    """Run P1 and P2 over every promoted skill. Returns failure messages."""
    failures: list[str] = []
    indexed = indexed_skill_names(repo_root)
    promoted = 0

    for skill_md in skill_files(repo_root):
        try:
            text = skill_md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        frontmatter, _ = parse_frontmatter(text)
        if not frontmatter:
            continue
        successor = frontmatter.get("promoted_to")
        if not successor:
            continue

        promoted += 1
        rel = skill_md.relative_to(repo_root)
        name = frontmatter.get("name", skill_md.parent.name)
        successor = str(successor).strip()

        if successor_exists(successor, repo_root, indexed):
            if verbose:
                print(f"  OK   {rel}: promoted_to '{successor}' resolves")
        else:
            failures.append(
                f"  [P1 PHANTOM-SUCCESSOR] {rel}: skill '{name}' is retired into "
                f"'{successor}', which exists nowhere in the repo. The generator drops "
                f"'{name}' from skills/INDEX.json, so it left routing with no successor "
                f"carrying its traffic. Point promoted_to at a real skill, or remove the "
                f"tag to return '{name}' to the index."
            )

        if frontmatter.get("user-invocable") is True:
            failures.append(
                f"  [P2 INVOCABLE-EXCLUDED] {rel}: skill '{name}' declares "
                f"user-invocable: true while promoted_to '{successor}' excludes it from "
                f"skills/INDEX.json. It advertises an entry point the router cannot see. "
                f"Set user-invocable: false, or drop promoted_to to keep it routable."
            )

    if verbose:
        print(f"\nChecked {promoted} skill(s) carrying promoted_to")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="Show every promoted skill checked")
    args = parser.parse_args()

    print("Checking promoted_to successors...")
    failures = check(REPO_ROOT, verbose=args.verbose)

    for msg in failures:
        print(f"FAIL: {msg}")

    print("\n" + "=" * 60)
    print(f"Total failures: {len(failures)}")
    if failures:
        print("VERDICT: FAIL")
        return 1
    print("VERDICT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
