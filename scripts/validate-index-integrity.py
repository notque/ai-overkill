#!/usr/bin/env python3
"""
Validate INDEX.json integrity for agents and skills.

Checks:
  1. All skill entries in the merged index (tracked + local overlay) have a
     corresponding SKILL.md on disk. Private-overlay skills resolve via the
     deployed symlink root (~/.claude/skills/) or the private-skills directory.
  2. All agent ``file`` fields in agents/INDEX.json point to existing files
     (paths resolved relative to the repo root).
  3. Every routable SKILL.md on disk has an INDEX entry (the reverse of check
     1). Skills carrying ``promoted_to`` are excluded — those are husks the
     generator skips on purpose so a folded skill cannot shadow its umbrella.
  4. No skill or agent has fewer than 5 triggers (warn) or 0 triggers (error).
  5. No triggers are duplicated within a single entry.
  6. No triggers are duplicated across entries (cross-entry overlap warning).

Note: routing-tables.md coverage check was removed in PR #653 — routing-tables.md was
absorbed into INDEX.json (PR #626) and check-routing-drift.py now covers this in CI.

Exit codes:
  0 — all checks pass (errors = 0)
  1 — one or more errors found

Usage:
    python scripts/validate-index-integrity.py
"""

import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_json(path: Path) -> dict:
    """Load and return JSON from *path*, exiting with an error on failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR: index file not found: {path}")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"ERROR: cannot parse {path}: {exc}")
        sys.exit(1)


def _load_json_optional(path: Path) -> dict:
    """Load JSON from *path*, returning empty dict if missing or invalid."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def build_overlay_roots(repo_root: Path) -> list[Path]:
    """Build the list of roots where skill SKILL.md files may exist.

    Resolution order mirrors the deployed layout:
    1. repo_root (tracked skills in nested layout)
    2. ~/.claude (deployed symlink root: skills/<name>/SKILL.md)
    3. /home/feedgen/private-skills (private overlay source)

    Only roots that exist on disk are included.
    """
    candidates = [
        repo_root,
        Path.home() / ".claude",
    ]
    # Private-skills root: the directory the deploy symlinks resolve to.
    private_root = Path.home() / "private-skills"
    if private_root.is_dir():
        candidates.append(private_root)

    return [r for r in candidates if r.exists()]


def resolve_skill_file(file_field: str, repo_root: Path, overlay_roots: list[Path]) -> Path | None:
    """Resolve a skill file field against all known roots.

    The file field is repo-relative (e.g. ``skills/foo/SKILL.md``). For
    private-overlay skills the path may only resolve under the deployed
    symlink root or the private-skills directory.

    Returns the resolved Path if found, None otherwise.
    """
    for root in overlay_roots:
        candidate = root / file_field
        if candidate.is_file():
            return candidate

    # Private-overlay fallback: skills/<name>/SKILL.md may resolve as
    # <private-root>/<category>/<name>/SKILL.md. Extract the skill name
    # and check deployed symlinks.
    parts = Path(file_field).parts
    if len(parts) >= 2 and parts[0] == "skills":
        skill_name = parts[1]
        deployed = Path.home() / ".claude" / "skills" / skill_name
        if deployed.exists():
            # Follow symlink to actual location
            real = deployed.resolve()
            skill_md = real / "SKILL.md"
            if skill_md.is_file():
                return skill_md

    return None


def merge_skill_indexes(skills_index_path: Path) -> dict:
    """Load tracked skills/INDEX.json and overlay skills/INDEX.local.json.

    Uses the same add-only merge as routing_index_merge.load_index_items:
    tracked entries take priority, local fills gaps per-name.
    """
    tracked = load_json(skills_index_path)
    local_path = skills_index_path.parent / "INDEX.local.json"
    local = _load_json_optional(local_path)

    merged_skills: dict = {}
    for source in [tracked, local]:
        for name, entry in source.get("skills", {}).items():
            merged_skills.setdefault(name, entry)

    # Preserve any non-skills top-level keys from tracked
    result = dict(tracked)
    result["skills"] = merged_skills
    return result


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------


def check_skill_files(
    skills_index: dict,
    repo_root: Path,
    overlay_roots: list[Path] | None = None,
) -> tuple[list[str], list[str]]:
    """Check 1: every skill entry has a SKILL.md on disk (any overlay root)."""
    errors: list[str] = []
    warnings: list[str] = []
    roots = overlay_roots or [repo_root]

    for name, entry in skills_index.get("skills", {}).items():
        if not isinstance(entry, dict):
            errors.append(f"  [skill malformed] '{name}': INDEX entry is not a dict")
            continue
        file_field = entry.get("file", "")
        if not file_field:
            errors.append(f"  [skill missing file] '{name}': INDEX entry has no 'file' field")
            continue
        resolved = resolve_skill_file(file_field, repo_root, roots)
        if resolved is None:
            errors.append(f"  [skill missing file] '{name}': INDEX says '{file_field}' but file does not exist")

    return errors, warnings


def check_skill_coverage(skills_index: dict, repo_root: Path) -> tuple[list[str], list[str]]:
    """Check 3: every routable SKILL.md on disk has an INDEX entry.

    Check 1 walks index -> disk and catches entries pointing at files that no
    longer exist. This walks disk -> index, the direction that catches silent
    rot: a skill added to skills/ that no generator run ever registered is
    invisible to the router even though its file is present and healthy.

    Skills carrying ``promoted_to`` are excluded. Those are husks whose content
    was folded into an umbrella skill; the generator deliberately skips them so
    a folded skill cannot re-enter routing and shadow the umbrella that
    replaced it. Excluding them here keeps this check agreeing with the
    generator instead of demanding entries the generator will never emit.
    """
    errors: list[str] = []
    warnings: list[str] = []

    indexed = set(skills_index.get("skills", {}))
    skills_dir = repo_root / "skills"

    for skill_md in sorted(skills_dir.glob("*/*/SKILL.md")):
        name = skill_md.parent.name
        if name in indexed:
            continue
        try:
            head = skill_md.read_text(encoding="utf-8")[:2000]
        except (OSError, UnicodeDecodeError):
            continue
        # Husks folded into an umbrella are skipped by the generator by design.
        if re.search(r"^promoted_to:", head, re.MULTILINE):
            continue
        rel = skill_md.relative_to(repo_root)
        errors.append(
            f"  [skill not indexed] '{name}': {rel} exists but has no INDEX entry — "
            f"it is unroutable. Run: python3 scripts/generate-skill-index.py"
        )

    return errors, warnings


def check_agent_files(agents_index: dict, repo_root: Path) -> tuple[list[str], list[str]]:
    """Check 2: every agent file field points to an existing file."""
    errors: list[str] = []
    warnings: list[str] = []

    for name, entry in agents_index.get("agents", {}).items():
        if not isinstance(entry, dict):
            errors.append(f"  [agent malformed] '{name}': INDEX entry is not a dict")
            continue
        file_field = entry.get("file", "")
        if not file_field:
            errors.append(f"  [agent missing file] '{name}': INDEX entry has no 'file' field")
            continue
        agent_path = repo_root / file_field
        if not agent_path.is_file():
            errors.append(f"  [agent missing file] '{name}': INDEX says '{file_field}' but file does not exist")

    return errors, warnings


def check_trigger_counts(index: dict, index_type: str) -> tuple[list[str], list[str]]:
    """Check 4: no entry has < 5 triggers (warn) or 0 triggers (error)."""
    errors: list[str] = []
    warnings: list[str] = []

    label = {"skills": "skill", "agents": "agent"}.get(index_type, index_type)
    items = index.get(index_type, {})
    for name, entry in items.items():
        if not isinstance(entry, dict):
            continue
        triggers = entry.get("triggers", [])
        count = len(triggers)
        if count == 0:
            errors.append(f"  [zero triggers] {label} '{name}' has 0 triggers — routing will never match this entry")
        elif count < 5:
            warnings.append(
                f"  [few triggers] {label} '{name}' has only {count} trigger(s) "
                "— consider adding more for reliable routing"
            )

    return errors, warnings


def check_duplicate_triggers(index: dict, index_type: str) -> tuple[list[str], list[str]]:
    """Check 5: no triggers are duplicated within a single entry."""
    errors: list[str] = []
    warnings: list[str] = []

    label = {"skills": "skill", "agents": "agent"}.get(index_type, index_type)
    items = index.get(index_type, {})
    for name, entry in items.items():
        if not isinstance(entry, dict):
            continue
        triggers = entry.get("triggers", [])
        seen: set[str] = set()
        duplicates: list[str] = []
        for t in triggers:
            if t in seen:
                duplicates.append(t)
            seen.add(t)
        if duplicates:
            errors.append(f"  [duplicate triggers] {label} '{name}' has duplicate trigger(s): {duplicates}")

    return errors, warnings


def check_cross_entry_trigger_overlap(skills_index: dict, agents_index: dict) -> tuple[list[str], list[str]]:
    """Check 6: detect triggers claimed by multiple entries across both indexes."""
    errors: list[str] = []
    warnings: list[str] = []

    trigger_map: dict[str, list[str]] = {}
    for index, index_type in [(skills_index, "skills"), (agents_index, "agents")]:
        label = {"skills": "skill", "agents": "agent"}.get(index_type, index_type)
        for name, entry in index.get(index_type, {}).items():
            if not isinstance(entry, dict):
                continue
            for trigger in entry.get("triggers", []):
                trigger_lower = trigger.lower()
                trigger_map.setdefault(trigger_lower, []).append(f"{label}:{name}")

    for trigger, owners in sorted(trigger_map.items()):
        if len(owners) > 1:
            warnings.append(f"  [trigger overlap] '{trigger}' claimed by: {', '.join(owners)}")

    return errors, warnings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Run all integrity checks and report results. Returns exit code."""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    skills_index_path = repo_root / "skills" / "INDEX.json"
    agents_index_path = repo_root / "agents" / "INDEX.json"

    print("Loading index files...")
    # Merge tracked + local overlay (same merge routing_index_merge uses)
    skills_index = merge_skill_indexes(skills_index_path)
    agents_index = load_json(agents_index_path)
    overlay_roots = build_overlay_roots(repo_root)

    local_path = skills_index_path.parent / "INDEX.local.json"
    if local_path.exists():
        local_count = len(_load_json_optional(local_path).get("skills", {}))
        tracked_count = len(load_json(skills_index_path).get("skills", {}))
        overlay_only = len(skills_index.get("skills", {})) - tracked_count
        if overlay_only > 0:
            print(f"  Merged {tracked_count} tracked + {overlay_only} overlay-only skills")
        print(f"  Overlay roots: {[str(r) for r in overlay_roots]}")

    all_errors: list[str] = []
    all_warnings: list[str] = []

    # Run checks
    # Note: routing-tables.md coverage check removed — routing-tables.md was absorbed
    # into INDEX.json (PR #626) and check-routing-drift.py now covers this in CI.
    checks = [
        ("Check 1: skill files on disk", check_skill_files(skills_index, repo_root, overlay_roots)),
        ("Check 2: agent files on disk", check_agent_files(agents_index, repo_root)),
        ("Check 3: skill index coverage", check_skill_coverage(skills_index, repo_root)),
        ("Check 4a: skill trigger counts", check_trigger_counts(skills_index, "skills")),
        ("Check 4b: agent trigger counts", check_trigger_counts(agents_index, "agents")),
        (
            "Check 5a: skill duplicate triggers",
            check_duplicate_triggers(skills_index, "skills"),
        ),
        (
            "Check 5b: agent duplicate triggers",
            check_duplicate_triggers(agents_index, "agents"),
        ),
        (
            "Check 6: cross-entry trigger overlap",
            check_cross_entry_trigger_overlap(skills_index, agents_index),
        ),
    ]

    for label, (errors, warnings) in checks:
        status = "PASS" if not errors else "FAIL"
        warn_suffix = f" ({len(warnings)} warning(s))" if warnings else ""
        print(f"\n{label}: {status}{warn_suffix}")
        for msg in errors:
            print(f"ERROR: {msg}")
        for msg in warnings:
            print(f"WARN:  {msg}")
        all_errors.extend(errors)
        all_warnings.extend(warnings)

    # Summary
    print("\n" + "=" * 60)
    print(f"Total errors:   {len(all_errors)}")
    print(f"Total warnings: {len(all_warnings)}")

    if all_errors:
        print("VERDICT: FAIL")
        return 1

    print("VERDICT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
