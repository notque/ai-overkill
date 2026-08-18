#!/usr/bin/env python3
"""Deterministic clone-and-fill for saved html-artifact templates.

Reads a frozen saved template (`templates/saved/<name>.html`) and its slot
manifest (`templates/saved/<name>.slots.json`), substitutes caller-supplied
slot values, and writes a finished artifact. The layout, CSS, and chrome are
never modified: content-vs-layout authority is enforced here, not by prompt
discipline.

Fail-loud rules (no silent degradation):
    - Missing required slot            -> exit 1
    - Provided slot not in manifest    -> exit 1 (catches typos)
    - Unresolved {{MARKER}} after fill -> exit 1

Exit codes:
    0: filled and written successfully
    1: slot validation failure
    2: template or manifest not found / unreadable

Usage:
    python3 fill-template.py --template business-review --slots slots.json --out artifact.html
    python3 fill-template.py --template business-review --slots slots.json           # prints to stdout
    python3 fill-template.py --list                                                   # list gallery
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SAVED_DIR = Path(__file__).parent.parent / "templates" / "saved"
MARKER_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def _fail(msg: str, code: int) -> None:
    sys.stderr.write(f"Error: {msg}\n")
    sys.exit(code)


def list_templates() -> list[str]:
    """Return the base names of saved templates that have a slot manifest."""
    if not SAVED_DIR.exists():
        return []
    names = []
    for html in sorted(SAVED_DIR.glob("*.html")):
        if (SAVED_DIR / f"{html.stem}.slots.json").exists():
            names.append(html.stem)
    return names


def load_manifest(name: str) -> dict:
    """Load and return the slot manifest for a template."""
    manifest_path = SAVED_DIR / f"{name}.slots.json"
    if not manifest_path.exists():
        _fail(f"no slot manifest for template '{name}' at {manifest_path}", 2)
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        _fail(f"manifest for '{name}' is not valid JSON: {e}", 2)
    if "slots" not in data or not isinstance(data["slots"], list):
        _fail(f"manifest for '{name}' must contain a 'slots' list", 2)
    return data


def fill_template(name: str, values: dict[str, str]) -> str:
    """Clone the frozen template and substitute slot values.

    Args:
        name: Base name of a saved template.
        values: Mapping of slot name to replacement HTML/text.

    Returns:
        The finished artifact HTML.

    Exits (non-zero) on any slot validation failure.
    """
    html_path = SAVED_DIR / f"{name}.html"
    if not html_path.exists():
        _fail(f"template '{name}' not found at {html_path}", 2)

    manifest = load_manifest(name)
    declared = {s["name"]: s for s in manifest["slots"]}

    # Reject slot names not declared in the manifest — catches typos loudly.
    unknown = sorted(set(values) - set(declared))
    if unknown:
        _fail(f"provided slot(s) not declared in '{name}' manifest: {', '.join(unknown)}", 1)

    # Every required slot must be provided.
    missing = sorted(s["name"] for s in manifest["slots"] if s.get("required", True) and s["name"] not in values)
    if missing:
        _fail(f"missing required slot(s) for '{name}': {', '.join(missing)}", 1)

    html = html_path.read_text(encoding="utf-8")

    # Substitute every declared slot. Optional slots default to empty string so
    # the marker never survives into the output.
    for slot_name in declared:
        replacement = values.get(slot_name, "")
        html = html.replace(f"{{{{{slot_name}}}}}", replacement)

    # No marker may survive. A leftover means the template has an undeclared
    # slot — a template bug, not a caller bug.
    leftover = sorted(set(MARKER_RE.findall(html)))
    if leftover:
        _fail(
            f"unresolved marker(s) remain after fill: {', '.join(leftover)} (declare them in {name}.slots.json)",
            1,
        )

    return html


def main() -> None:
    parser = argparse.ArgumentParser(description="Clone and fill a saved html-artifact template.")
    parser.add_argument("--template", help="Base name of a saved template (see --list).")
    parser.add_argument("--slots", help="Path to a JSON file mapping slot names to values.")
    parser.add_argument("--out", help="Output path. Prints to stdout if omitted.")
    parser.add_argument("--list", action="store_true", help="List available saved templates and exit.")
    args = parser.parse_args()

    if args.list:
        names = list_templates()
        if names:
            sys.stdout.write("\n".join(names) + "\n")
        else:
            sys.stdout.write("(no saved templates with manifests)\n")
        return

    if not args.template:
        _fail("--template is required (or use --list)", 2)
    if not args.slots:
        _fail("--slots is required", 2)

    slots_path = Path(args.slots)
    if not slots_path.exists():
        _fail(f"slots file not found: {slots_path}", 2)
    try:
        values = json.loads(slots_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        _fail(f"slots file is not valid JSON: {e}", 2)
    if not isinstance(values, dict):
        _fail("slots file must be a JSON object mapping slot names to values", 2)

    html = fill_template(args.template, values)

    if args.out:
        Path(args.out).write_text(html, encoding="utf-8")
        sys.stdout.write(f"Wrote {args.out} ({len(html)} bytes)\n")
    else:
        sys.stdout.write(html)


if __name__ == "__main__":
    main()
