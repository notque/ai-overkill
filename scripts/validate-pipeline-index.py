#!/usr/bin/env python3
"""Validate that every pipeline in pipeline-index.json points at a real doc.

``skills/workflow/references/pipeline-index.json`` is hand-maintained — the
generator that builds skills/INDEX.json and agents/INDEX.json skips it. Nothing
else checks it either: ``scripts/validate-do-references.py`` resolves component
*names* mentioned in prose, so an entry whose ``file`` points at a deleted doc
passes clean. That gap is not hypothetical. Commit b2db049e deleted
perses-dac-pipeline.md and perses-plugin-pipeline.md and claimed in its own
message to have cleaned this index; it never touched the file. Both entries
survived as routable pipelines backed by nothing, and every check in CI passed.

Three ways an entry goes wrong, one check each:

  P1 MISSING-FILE    ``file`` is absent, or names a path that does not exist.
                     The router can select the pipeline and the orchestrator
                     then has no phases to run.

  P2 PHANTOM-PHASE   A name in ``phases`` appears in no heading of the
                     referenced doc. The index advertises a phase the doc does
                     not define, so the manifest promises work that cannot run.
                     Live case: voice-writer declared 13 phases while its
                     ``file`` pointed at a seven-line pointer stub defining none.

  P3 NO-PHASES       ``phases`` is absent or empty. Phases are what makes a
                     pipeline a pipeline rather than a skill, and /do's
                     PIPELINE-SELECTION RULE keys on having real phases. Live
                     case: comprehensive-review and toolkit-improvement each
                     declared none while their docs defined 13 and 10.

Phase matching is deliberately loose — a declared phase counts as present when
it appears anywhere in any heading line, case-insensitively. Docs number and
decorate their headings ("## Phase 3c: WAVE 3 DISPATCH — Adversarial
Perspectives"), so anchoring tighter would fail on formatting rather than on
substance. The check catches a phase that is absent, not one that is styled
differently.

Exit codes:
    0 — every entry resolves to a doc that defines the phases it declares
    1 — one or more failures

Usage:
    python3 scripts/validate-pipeline-index.py
    python3 scripts/validate-pipeline-index.py --verbose
    python3 scripts/validate-pipeline-index.py --index path/to/other-index.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_INDEX = REPO_ROOT / "skills" / "workflow" / "references" / "pipeline-index.json"


def heading_text(doc: Path) -> str:
    """Every markdown heading in the doc, upper-cased and joined.

    Joined with a separator so a phase cannot match by spanning two headings.
    """
    try:
        lines = doc.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return " || ".join(ln for ln in lines if ln.lstrip().startswith("#")).upper()


def check(index_path: Path, repo_root: Path, verbose: bool = False) -> list[str]:
    """Return a list of failure messages, empty when the index is clean."""
    failures: list[str] = []

    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except OSError as exc:
        return [f"  [P1 MISSING-FILE] cannot read {index_path}: {exc}"]
    except json.JSONDecodeError as exc:
        return [f"  [P1 MISSING-FILE] {index_path} is not valid JSON: {exc}"]

    pipelines = data.get("pipelines")
    if not isinstance(pipelines, dict):
        return [f"  [P1 MISSING-FILE] {index_path} has no 'pipelines' object"]

    for name in sorted(pipelines):
        entry = pipelines[name] if isinstance(pipelines[name], dict) else {}
        rel = entry.get("file")

        if not rel:
            failures.append(
                f"  [P1 MISSING-FILE] '{name}': no 'file' key. Every pipeline must name "
                f"the doc that defines its phases, so the orchestrator has something to "
                f"read once the router selects it."
            )
            continue

        doc = repo_root / rel
        if not doc.is_file():
            failures.append(
                f"  [P1 MISSING-FILE] '{name}': file '{rel}' does not exist. The router "
                f"can still select this pipeline, and the orchestrator would then have no "
                f"phases to run. Point 'file' at a real doc, or remove the entry."
            )
            continue

        phases = entry.get("phases")
        if not phases:
            failures.append(
                f"  [P3 NO-PHASES] '{name}': no phases declared. Phases are what "
                f"distinguishes a pipeline from a skill and what /do's PIPELINE-SELECTION "
                f"RULE keys on. Add the phase names from the headings in '{rel}'."
            )
            continue

        headings = heading_text(doc)
        absent = [p for p in phases if str(p).upper() not in headings]
        if absent:
            failures.append(
                f"  [P2 PHANTOM-PHASE] '{name}': phase(s) {absent} appear in no heading of "
                f"'{rel}'. The index advertises work the doc does not define. Correct the "
                f"phases list, or point 'file' at the doc that actually defines them."
            )
        elif verbose:
            print(f"  OK   {name}: {len(phases)} phase(s) resolve in {rel}")

    if verbose:
        print(f"\nChecked {len(pipelines)} pipeline(s)")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="Show every pipeline checked")
    parser.add_argument(
        "--index",
        type=Path,
        default=DEFAULT_INDEX,
        help="Index to validate (default: skills/workflow/references/pipeline-index.json)",
    )
    args = parser.parse_args()

    print("Checking pipeline index...")
    failures = check(args.index, REPO_ROOT, verbose=args.verbose)

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
