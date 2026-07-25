#!/usr/bin/env python3
"""
Tests for check_skill_coverage in scripts/validate-index-integrity.py (Track M, M4).

Contract under test: the disk -> index direction. Check 1 already walks
index -> disk and catches entries whose file vanished. Check 3 catches the
opposite and quieter failure: a SKILL.md that exists, parses, and is healthy
but was never registered, so the router cannot reach it.

Skills carrying ``promoted_to`` are husks folded into an umbrella. The
generator skips them on purpose so a folded skill cannot shadow the umbrella
that replaced it, so the check must skip them too or it would demand entries
the generator will never emit.

Run with: python3 -m pytest scripts/tests/test_validate_index_coverage.py -v
"""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "validate-index-integrity.py"

_spec = importlib.util.spec_from_file_location("validate_index_integrity", SCRIPT)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

check_skill_coverage = _mod.check_skill_coverage

FRONTMATTER = '---\nname: {name}\ndescription: "fixture"\n---\nbody\n'
FRONTMATTER_PROMOTED = '---\nname: {name}\npromoted_to: {target}\ndescription: "fixture"\n---\nbody\n'


def _make_skill(repo_root: Path, category: str, name: str, content: str) -> None:
    skill_dir = repo_root / "skills" / category / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")


def test_indexed_skill_passes(tmp_path: Path) -> None:
    """A skill present on disk and in the index produces no error."""
    _make_skill(tmp_path, "research", "mapped", FRONTMATTER.format(name="mapped"))
    index = {"skills": {"mapped": {"file": "skills/research/mapped/SKILL.md"}}}

    errors, _ = check_skill_coverage(index, tmp_path)

    assert errors == []


def test_unindexed_skill_is_an_error(tmp_path: Path) -> None:
    """A healthy SKILL.md with no index entry is unroutable and must fail."""
    _make_skill(tmp_path, "research", "orphan", FRONTMATTER.format(name="orphan"))
    index: dict = {"skills": {}}

    errors, _ = check_skill_coverage(index, tmp_path)

    assert len(errors) == 1
    assert "orphan" in errors[0]
    assert "no INDEX entry" in errors[0]
    # The message must name the fix, not just the fault.
    assert "generate-skill-index.py" in errors[0]


def test_promoted_husk_is_exempt(tmp_path: Path) -> None:
    """A husk folded into an umbrella is skipped, matching the generator."""
    _make_skill(
        tmp_path,
        "research",
        "husk",
        FRONTMATTER_PROMOTED.format(name="husk", target="codebase-overview"),
    )
    index: dict = {"skills": {}}

    errors, _ = check_skill_coverage(index, tmp_path)

    assert errors == []


def test_reports_every_unindexed_skill(tmp_path: Path) -> None:
    """All gaps are reported at once, and promoted husks stay excluded."""
    _make_skill(tmp_path, "research", "gap-a", FRONTMATTER.format(name="gap-a"))
    _make_skill(tmp_path, "meta", "gap-b", FRONTMATTER.format(name="gap-b"))
    _make_skill(
        tmp_path,
        "meta",
        "folded",
        FRONTMATTER_PROMOTED.format(name="folded", target="workflow"),
    )
    index: dict = {"skills": {}}

    errors, _ = check_skill_coverage(index, tmp_path)

    reported = {name for name in ("gap-a", "gap-b", "folded") if any(name in e for e in errors)}
    assert reported == {"gap-a", "gap-b"}


def test_no_skills_dir_is_not_an_error(tmp_path: Path) -> None:
    """An absent skills/ tree yields no findings rather than a crash."""
    errors, warnings = check_skill_coverage({"skills": {}}, tmp_path)

    assert errors == []
    assert warnings == []


def test_real_repo_has_full_coverage() -> None:
    """The live tree must stay fully indexed; this is the anti-rot assertion."""
    repo_root = SCRIPT.parent.parent
    index_path = repo_root / "skills" / "INDEX.json"
    if not index_path.is_file():
        # INDEX.json is generated and gitignored; skip when it has not been built.
        return
    index = _mod.merge_skill_indexes(index_path)

    errors, _ = check_skill_coverage(index, repo_root)

    assert errors == [], "on-disk skills missing from INDEX.json:\n" + "\n".join(errors)
