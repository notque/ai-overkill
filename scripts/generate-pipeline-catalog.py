#!/usr/bin/env python3
"""
Generate pipeline catalog from YAML frontmatter in pipeline SKILL.md files.

Scans all skills/workflow/references/*.md files, extracts phase metadata, and generates
a markdown reference catalog for auto-pipeline dedup checks.

Usage:
    python scripts/generate-pipeline-catalog.py --output catalog.md
    python scripts/generate-pipeline-catalog.py --output catalog.md --json

Output:
    Markdown catalog at the specified --output path.
    Optional JSON file alongside markdown when --json is passed.

Exit codes:
    0 - Success
    1 - Fatal error (directory not found, write failed, no pipelines found)
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.lib.frontmatter import extract_frontmatter_block

# auto-pipeline consumes this catalog in its Phase 0 DEDUP CHECK to decide
# whether an existing pipeline already covers the request. Its own doc lives in
# the scanned directory, so a plain glob lists it as a candidate match for
# itself: a request that reaches auto-pipeline matches auto-pipeline, and the
# HARD BLOCK routes it straight back. Exclude it at the source.
SELF_EXCLUDED = frozenset({"auto-pipeline"})


def extract_frontmatter(content: str) -> dict | None:
    """Extract YAML frontmatter from markdown content.

    Attempts YAML parsing first, then falls back to regex extraction
    for key fields when YAML parsing fails.

    Args:
        content: Full markdown file content.

    Returns:
        Parsed frontmatter dict, or None if no frontmatter found.
    """
    yaml_content = extract_frontmatter_block(content)
    if yaml_content is None:
        return None

    try:
        result = yaml.safe_load(yaml_content)
        return result
    except yaml.YAMLError as e:
        print(f"  Warning: YAML parsing failed, using regex fallback: {e}", file=sys.stderr)

    # Fallback: extract key fields via regex
    frontmatter: dict = {}

    name_match = re.search(r"^name:\s*(.+)$", yaml_content, re.MULTILINE)
    if name_match:
        frontmatter["name"] = name_match.group(1).strip()

    desc_match = re.search(
        r"^description:\s*(?:[>|][\-+]?\s*\n\s+)?(.+?)(?=\n[a-z_-]+:|$)",
        yaml_content,
        re.MULTILINE | re.DOTALL,
    )
    if desc_match:
        desc = desc_match.group(1).strip()
        desc = re.sub(r"\s+", " ", desc)
        frontmatter["description"] = desc

    routing_match = re.search(r"^routing:\s*\n((?:\s+.+\n?)+)", yaml_content, re.MULTILINE)
    if routing_match:
        routing_content = routing_match.group(1)
        routing: dict = {}

        triggers_match = re.search(r"triggers:\s*\n((?:\s+-\s+.+\n?)+)", routing_content)
        if triggers_match:
            triggers = re.findall(r'-\s+["\']?([^"\'\n]+)["\']?', triggers_match.group(1))
            routing["triggers"] = [t.strip() for t in triggers]

        category_match = re.search(r"category:\s*(.+)$", routing_content, re.MULTILINE)
        if category_match:
            routing["category"] = category_match.group(1).strip()

        if routing:
            frontmatter["routing"] = routing

    return frontmatter if frontmatter else None


def extract_description_first_line(description: str, max_length: int = 120) -> str:
    """Extract the first meaningful line from a description, truncated to max_length.

    Args:
        description: Raw description string (may be multiline).
        max_length: Maximum character length for the result.

    Returns:
        First line of description, truncated if needed.
    """
    if not description:
        return ""

    desc = description.replace("\\n", " ").strip()
    # Collapse whitespace but preserve sentence structure
    lines = desc.split("\n")
    first_line = lines[0].strip()
    first_line = re.sub(r"\s+", " ", first_line)

    if len(first_line) > max_length:
        return first_line[: max_length - 3] + "..."
    return first_line


def extract_phases(content: str) -> list[str]:
    """Extract phase names from pipeline SKILL.md content.

    Looks for multiple patterns:
    - ### Phase N: NAME or ### Phase N.N: NAME
    - **Phase N: NAME**
    - Lines in chain descriptions like NAME1 -> NAME2 -> NAME3

    Args:
        content: Full markdown file content (body after frontmatter).

    Returns:
        Ordered list of phase names (e.g., ["SCAN", "MAP", "ANALYZE", "REPORT"]).
    """
    phases: list[str] = []
    seen: set[str] = set()

    # Pattern 1: ### Phase N: NAME or ### Phase N.N: NAME (e.g., "### Phase 2.5: VALIDATE-PLAN")
    for m in re.finditer(r"^###\s+Phase\s+[\d.]+[a-z]?:\s+(.+)$", content, re.MULTILINE):
        raw = m.group(1).strip()
        # Strip trailing markdown artifacts like "(Parallel Research)" or extra parens
        name = re.split(r"\s*[\(\[]", raw)[0].strip()
        name_upper = name.upper()
        if name_upper not in seen:
            phases.append(name_upper)
            seen.add(name_upper)

    if phases:
        return phases

    # Pattern 2: **Phase N: NAME** (bold inline)
    for m in re.finditer(r"\*\*Phase\s+\d+:\s+(.+?)\*\*", content):
        name = re.split(r"\s*[\(\[]", m.group(1).strip())[0].strip()
        name_upper = name.upper()
        if name_upper not in seen:
            phases.append(name_upper)
            seen.add(name_upper)

    if phases:
        return phases

    # Pattern 3: Wave-based phases (comprehensive-review style)
    for m in re.finditer(r"^###\s+(Wave\s+\d+[a-z]?:\s+.+?)$", content, re.MULTILINE):
        name = m.group(1).strip()
        name_upper = name.upper()
        if name_upper not in seen:
            phases.append(name_upper)
            seen.add(name_upper)

    if phases:
        return phases

    # Pattern 4: Look for chain descriptions like "SCAN -> MAP -> ANALYZE -> REPORT"
    # or unicode arrow variants
    chain_pattern = r"([A-Z][-A-Z_]+(?:\s*(?:->|-->|\u2192|→)\s*[A-Z][-A-Z_]+)+)"
    for m in re.finditer(chain_pattern, content):
        chain = m.group(1)
        parts = re.split(r"\s*(?:->|-->|\u2192|→)\s*", chain)
        for part in parts:
            name = part.strip().upper()
            if name and name not in seen:
                phases.append(name)
                seen.add(name)

    return phases


def infer_task_type(frontmatter: dict, description: str) -> str:
    """Infer the task type from routing metadata or description keywords.

    Args:
        frontmatter: Parsed YAML frontmatter dict.
        description: Pipeline description text.

    Returns:
        Task type string (e.g., "exploration", "git-workflow", "content-pipeline").
    """
    routing = frontmatter.get("routing", {})
    if isinstance(routing, dict) and "category" in routing:
        return routing["category"]

    # Keyword-based inference from description
    desc_lower = description.lower()
    keyword_map = {
        "review": "review",
        "explore": "exploration",
        "research": "research",
        "article": "content-pipeline",
        "voice": "content-pipeline",
        "content": "content-pipeline",
        "pull request": "git-workflow",
        "PR": "git-workflow",
        "commit": "git-workflow",
        "test": "testing",
        "debug": "debugging",
        "deploy": "deployment",
        "document": "documentation",
        "orchestrat": "orchestration",
        "scaffold": "scaffolding",
        "upgrade": "maintenance",
        "retro": "retrospective",
    }

    for keyword, task_type in keyword_map.items():
        if keyword.lower() in desc_lower:
            return task_type

    return "general"


def extract_triggers(frontmatter: dict, description: str) -> list[str]:
    """Extract trigger keywords from routing metadata or description.

    Args:
        frontmatter: Parsed YAML frontmatter dict.
        description: Pipeline description text.

    Returns:
        List of trigger keyword strings.
    """
    routing = frontmatter.get("routing", {})
    if isinstance(routing, dict) and "triggers" in routing:
        return routing["triggers"]

    # Fall back to extracting keywords from description
    name = frontmatter.get("name", "")
    stop_words = {"the", "and", "for", "with", "use", "when", "not", "this", "that", "from", "into", "does"}
    name_parts = name.replace("-", " ").split()
    triggers = [p for p in name_parts if len(p) > 2 and p.lower() not in stop_words]
    return triggers


def scan_pipelines(references_dir: Path) -> tuple[list[dict], list[str]]:
    """Scan all workflow reference files and extract catalog entries.

    Args:
        references_dir: Path to the skills/workflow/references/ directory.

    Returns:
        Tuple of (list of pipeline entry dicts, list of warning messages).
    """
    entries: list[dict] = []
    warnings: list[str] = []

    for skill_file in sorted(references_dir.glob("*.md")):
        if not skill_file.is_file():
            continue

        try:
            content = skill_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            warnings.append(f"  - {skill_file.stem}: Failed to read: {e}")
            continue

        frontmatter = extract_frontmatter(content)
        if not frontmatter:
            warnings.append(f"  - {skill_file.stem}: No valid frontmatter found")
            continue

        name = frontmatter.get("name", skill_file.stem)
        if name in SELF_EXCLUDED:
            continue

        description = frontmatter.get("description", "")
        description_line = extract_description_first_line(description)

        phases = extract_phases(content)
        phase_count = len(phases)
        chain = " → ".join(phases) if phases else "—"

        task_type = infer_task_type(frontmatter, description)
        triggers = extract_triggers(frontmatter, description)

        entries.append(
            {
                "name": name,
                "description": description_line,
                "phase_count": phase_count,
                "phases": phases,
                "chain": chain,
                "task_type": task_type,
                "triggers": triggers,
            }
        )

    return entries, warnings


def generate_markdown(entries: list[dict], timestamp: str) -> str:
    """Generate the markdown catalog content.

    Args:
        entries: List of pipeline entry dicts.
        timestamp: ISO-formatted generation timestamp.

    Returns:
        Formatted markdown string.
    """
    lines: list[str] = [
        "# Pipeline Catalog",
        "Auto-generated reference for auto-pipeline dedup checks.",
        f"Generated: {timestamp}",
        "",
        "| Pipeline | Phases | Chain | Task Type | Triggers |",
        "|----------|--------|-------|-----------|----------|",
    ]

    for entry in entries:
        triggers_str = ", ".join(entry["triggers"][:5]) if entry["triggers"] else "—"
        lines.append(
            f"| {entry['name']} | {entry['phase_count']} | {entry['chain']} | {entry['task_type']} | {triggers_str} |"
        )

    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(
        description="Generate pipeline catalog from skills/workflow/references/*.md frontmatter.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path to write the markdown catalog",
    )
    parser.add_argument(
        "--json",
        dest="emit_json",
        action="store_true",
        default=False,
        help="Also output a JSON version alongside the markdown",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Main entry point.

    Args:
        argv: Optional argument list for testing.

    Returns:
        Exit code: 0 success, 1 error.
    """
    args = parse_args(argv)

    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    references_dir = repo_root / "skills" / "workflow" / "references"

    if not references_dir.exists():
        print(f"Error: workflow references directory not found at {references_dir}", file=sys.stderr)
        return 1

    entries, warnings = scan_pipelines(references_dir)

    if warnings:
        print("Warnings during catalog generation:", file=sys.stderr)
        for warning in warnings:
            print(warning, file=sys.stderr)

    if not entries:
        print("Error: No pipelines found. Catalog not written.", file=sys.stderr)
        return 1

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Write markdown catalog
    output_path: Path = args.output
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(generate_markdown(entries, timestamp), encoding="utf-8")
    except PermissionError:
        print(f"Error: Permission denied writing to {output_path}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"Error: Failed to write catalog: {e}", file=sys.stderr)
        return 1

    print(f"Generated {output_path}")
    print(f"  Total pipelines: {len(entries)}")

    # Show breakdown by task type
    categories: dict[str, int] = {}
    for entry in entries:
        cat = entry["task_type"]
        categories[cat] = categories.get(cat, 0) + 1

    print("  By task type:")
    for cat, count in sorted(categories.items()):
        print(f"    {cat}: {count}")

    # Write JSON if requested
    if args.emit_json:
        json_path = output_path.with_suffix(".json")
        json_data = {
            "version": "1.0",
            "generated": timestamp,
            "generated_by": "scripts/generate-pipeline-catalog.py",
            "pipelines": entries,
        }
        try:
            json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except PermissionError:
            print(f"Error: Permission denied writing to {json_path}", file=sys.stderr)
            return 1
        except OSError as e:
            print(f"Error: Failed to write JSON catalog: {e}", file=sys.stderr)
            return 1

        print(f"  JSON catalog: {json_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
