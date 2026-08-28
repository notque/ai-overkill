#!/usr/bin/env python3
"""Validate that every relative/absolute repo-rooted link in docs/ + root markdown resolves.

Walks `docs/*.md` and root markdown (README.md, CONTRIBUTING.md, CLAUDE.md), extracts
markdown links and inline backtick paths that look like repo paths, and verifies each
target exists on disk.

Exits 0 when every link resolves; exits 1 when any link is broken.

Skips:
- External links (http://, https://, mailto:)
- Anchor-only links (#section)
- File anchors are checked for file existence; the anchor itself is not verified.

Usage:
    python3 scripts/validate-doc-links.py
    python3 scripts/validate-doc-links.py --json    # machine-readable output
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
ROOT_MARKDOWN = ["README.md", "CONTRIBUTING.md", "CLAUDE.md"]

# Paths that legitimately appear in docs as references but don't exist on disk:
# - runtime-created directories (created by hooks at session time)
# - intentionally-documented deleted stubs (the doc says "Removed. X was deleted.")
ALLOWLIST = {
    "adr/completed",  # Created at runtime by adr-lifecycle-on-merge.py when an ADR is marked COMPLETE
    "hooks/auto-plan-detector.py",  # Deleted stub, documented as removed in injected-context-contracts.md
    ".claude/settings.local.json",  # Gitignored repo-local override file, documented as such
    # Retired with the learning system (2026-08-28). The negative-results registry
    # cites them as the evidence for why they were removed, so the references stay.
    "hooks/pretool-learning-injector.py",
    "hooks/instruction-compliance.py",
    "hooks/tests/test_injection_floor.py",
}

# Markdown link: [text](target)
MD_LINK = re.compile(r"\[(?:[^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
# Backtick code path that looks like a repo file: `path/to/file.ext` or `dir/`
BACKTICK_PATH = re.compile(
    r"`("
    r"(?:agents|skills|hooks|scripts|adr|docs|templates|\.claude|\.github)"
    r"/[^`\s]+"
    r")`"
)
EXTERNAL = re.compile(r"^(?:https?://|mailto:|tel:)")


def collect_markdown_files() -> list[Path]:
    files = []
    if DOCS_DIR.is_dir():
        files.extend(sorted(DOCS_DIR.rglob("*.md")))
    for name in ROOT_MARKDOWN:
        p = REPO_ROOT / name
        if p.is_file():
            files.append(p)
    return files


def strip_anchor(target: str) -> str:
    return target.split("#", 1)[0]


def resolve_target(source: Path, target: str, from_repo_root: bool = False) -> Path:
    if target.startswith("/") or from_repo_root:
        return REPO_ROOT / target.lstrip("/")
    return (source.parent / target).resolve()


def is_template(target: str) -> bool:
    """Skip glob patterns and {placeholder} templates — they aren't real paths."""
    return "*" in target or "{" in target or "..." in target


def check_link(source: Path, raw_target: str, from_repo_root: bool = False) -> tuple[bool, str]:
    if EXTERNAL.match(raw_target):
        return True, "external"
    bare = strip_anchor(raw_target).strip()
    if not bare:
        return True, "anchor-only"
    if is_template(bare):
        return True, "template"
    if bare.rstrip("/") in ALLOWLIST:
        return True, "allowlisted"
    resolved = resolve_target(source, bare, from_repo_root=from_repo_root)
    if resolved.exists():
        return True, "ok"
    return False, str(resolved.relative_to(REPO_ROOT) if str(resolved).startswith(str(REPO_ROOT)) else resolved)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON output")
    args = parser.parse_args()

    broken: list[dict[str, str]] = []
    checked = 0

    for md in collect_markdown_files():
        text = md.read_text(encoding="utf-8", errors="replace")
        rel = md.relative_to(REPO_ROOT)
        for match in MD_LINK.finditer(text):
            target = match.group(1)
            ok, info = check_link(md, target)
            checked += 1
            if not ok:
                broken.append({"source": str(rel), "target": target, "resolved": info})
        # Backtick repo-paths are written as repo-root-relative idiomatically
        for match in BACKTICK_PATH.finditer(text):
            target = match.group(1)
            ok, info = check_link(md, target, from_repo_root=True)
            checked += 1
            if not ok:
                broken.append({"source": str(rel), "target": target, "resolved": info})

    if args.json:
        print(json.dumps({"checked": checked, "broken": broken}, indent=2))
    else:
        print(f"Checked {checked} links across {len(collect_markdown_files())} files.")
        if broken:
            print(f"\nBroken: {len(broken)}")
            for b in broken:
                print(f"  {b['source']}: {b['target']} -> {b['resolved']}")
        else:
            print("All links resolve.")

    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
