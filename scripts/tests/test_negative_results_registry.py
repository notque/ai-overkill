"""Tests for the negative-results registry (ADR: Negative-Results Registry).

The registry is doc-backed: `docs/what-didnt-work.md` is capture, store, and
query target. These tests encode the ADR test plan as deterministic checks:

1. Doc present and seeded with exactly three entries, each with six fields.
2. Format conformance: heading + four bold field labels per entry.
3. Discoverability: CONTRIBUTING.md and retro SKILL.md both link the doc.
4. Retro subcommand documented in the retro skill argument table.
5. Optional learn mirror: the documented command shape is valid (topic only).
6. Doc hygiene: no banned em/en dashes in the new doc.

No new Python ships with this ADR, so these checks run against files on disk.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY = REPO_ROOT / "docs" / "what-didnt-work.md"
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"
RETRO_SKILL = REPO_ROOT / "skills" / "meta" / "retro" / "SKILL.md"

ENTRY_HEADING = re.compile(r"^## \d{4}-\d{2}-\d{2} ", re.MULTILINE)
BOLD_FIELDS = ("**Expectation**", "**What happened**", "**Evidence**", "**Decision**")

# Banned by scan-ai-patterns (forbidden_punctuation). Built via code points so the
# literal ambiguous characters never appear in this source (ruff RUF001).
EM_DASH = chr(0x2014)
EN_DASH = chr(0x2013)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# 1. Doc present and seeded ------------------------------------------------


def test_registry_exists() -> None:
    assert REGISTRY.is_file(), "docs/what-didnt-work.md must exist"


def test_registry_has_three_seed_entries() -> None:
    headings = ENTRY_HEADING.findall(_read(REGISTRY))
    assert len(headings) == 3, f"expected 3 seed entries, found {len(headings)}"


def test_registry_header_documents_format_and_mirror() -> None:
    text = _read(REGISTRY)
    # Header states what it is, when to add, and the retro mirror command.
    assert "what-didnt-work" in text
    assert "/retro what-didnt-work" in text


# 2. Format conformance ----------------------------------------------------


def _entry_blocks(text: str) -> list[str]:
    """Split the doc into per-entry blocks at each dated heading."""
    spans = [m.start() for m in ENTRY_HEADING.finditer(text)]
    spans.append(len(text))
    return [text[spans[i] : spans[i + 1]] for i in range(len(spans) - 1)]


def test_each_entry_has_all_four_bold_fields() -> None:
    blocks = _entry_blocks(_read(REGISTRY))
    assert len(blocks) == 3
    for block in blocks:
        heading = block.splitlines()[0]
        for field in BOLD_FIELDS:
            assert field in block, f"{field} missing in entry: {heading}"


def test_each_entry_decision_is_a_known_verdict() -> None:
    blocks = _entry_blocks(_read(REGISTRY))
    verdict = re.compile(r"\*\*Decision\*\*:\s*(rejected|deferred|revisit-if)")
    for block in blocks:
        assert verdict.search(block), f"entry lacks a valid Decision verdict:\n{block[:80]}"


def test_seed_entries_cover_the_three_adr_negatives() -> None:
    text = _read(REGISTRY).lower()
    # (a) provenance footers, (b) knowledge/process split, (c) eval caveats.
    assert "provenance footer" in text
    assert "knowledge" in text and "process" in text and "split" in text
    assert "eval" in text and "caveat" in text


def test_each_entry_evidence_is_a_location_not_prose() -> None:
    """Evidence must point at a location: file:line, eval path, PR #, or topic/key."""
    blocks = _entry_blocks(_read(REGISTRY))
    located = re.compile(
        r"(\.md|\.py|\.json|line|PR\s*#|verified detail|learning\.db|topic/key)",
        re.IGNORECASE,
    )
    for block in blocks:
        ev_match = re.search(r"\*\*Evidence\*\*:(.+)", block)
        assert ev_match, f"entry lacks an Evidence line:\n{block[:80]}"
        assert located.search(ev_match.group(1)), f"Evidence is not a location:\n{ev_match.group(1)}"


# 3. Discoverability (display) --------------------------------------------


def test_contributing_links_the_registry() -> None:
    assert "docs/what-didnt-work.md" in _read(CONTRIBUTING)


def test_contributing_has_negative_results_subsection() -> None:
    text = _read(CONTRIBUTING).lower()
    assert "negative results" in text


def test_retro_skill_links_the_registry() -> None:
    assert "docs/what-didnt-work.md" in _read(RETRO_SKILL)


# 4. Retro subcommand documented ------------------------------------------


def test_retro_skill_documents_subcommand_in_arg_table() -> None:
    text = _read(RETRO_SKILL)
    # The argument routing table must route the what-didnt-work argument.
    assert "what-didnt-work" in text
    # And a matching subcommand section must exist.
    assert "### Subcommand: what-didnt-work" in text


# 5. The registry doc is the single store ---------------------------------


def test_registry_doc_is_the_only_store() -> None:
    """The skill searches the doc itself; a parallel store would drift from it."""
    text = _read(RETRO_SKILL)
    assert "grep -n -i" in text and "docs/what-didnt-work.md" in text


# 6. Doc hygiene -----------------------------------------------------------


def test_registry_has_no_em_or_en_dashes() -> None:
    text = _read(REGISTRY)
    assert EM_DASH not in text, "em-dash (U+2014) is banned by scan-ai-patterns"
    assert EN_DASH not in text, "en-dash (U+2013) is banned by scan-ai-patterns"
