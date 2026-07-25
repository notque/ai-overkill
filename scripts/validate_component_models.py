#!/usr/bin/env python3
"""Validate model policy for agents, skills, and workflow pipeline references."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_RE = re.compile(r"^model:\s*(.+)$", re.MULTILINE)
ALLOWED_MODELS = {"sonnet", "opus"}
EXEMPT_COMPONENTS: set[tuple[str, str]] = {
    ("skill", "do"),
}


@dataclass
class Violation:
    component_type: str
    component: str
    file: str
    issue: str


def scan_targets() -> list[tuple[str, str, Path]]:
    targets: list[tuple[str, str, Path]] = []
    for path in sorted((REPO_ROOT / "agents").glob("*.md")):
        if path.name == "README.md":
            continue
        targets.append(("agent", path.stem, path))
    for path in sorted((REPO_ROOT / "skills").glob("*/SKILL.md")):
        targets.append(("skill", path.parent.name, path))
    for path in sorted((REPO_ROOT / "skills" / "workflow" / "references").glob("*.md")):
        targets.append(("workflow_ref", path.stem, path))
    return targets


def validate_models() -> list[Violation]:
    violations: list[Violation] = []
    for component_type, component, path in scan_targets():
        if (component_type, component) in EXEMPT_COMPONENTS or ("skill", component) in EXEMPT_COMPONENTS:
            continue

        text = path.read_text(encoding="utf-8", errors="ignore")
        match = MODEL_RE.search(text)
        if not match:
            continue

        model = match.group(1).strip()
        if model in ALLOWED_MODELS:
            continue

        violations.append(
            Violation(
                component_type=component_type,
                component=component,
                file=str(path.relative_to(REPO_ROOT)),
                issue=f"model '{model}' is not allowed; use 'sonnet' or 'opus' (except /do)",
            )
        )
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate component model policy")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Emit JSON output")
    args = parser.parse_args()

    violations = validate_models()
    payload = {"count": len(violations), "violations": [asdict(v) for v in violations]}
    if args.json_output:
        print(json.dumps(payload, indent=2))
    else:
        for violation in violations:
            print(f"{violation.file}: {violation.issue}")
        print(f"count: {len(violations)}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
