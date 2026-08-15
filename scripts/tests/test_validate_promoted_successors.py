#!/usr/bin/env python3
"""Tests for scripts/validate-promoted-successors.py.

Contract under test: ``promoted_to`` retires a skill by removing it from
skills/INDEX.json, so both ways the tag can lie must fail.

P1 catches a successor that names nothing on disk — the husk is retired into
a void, which is how /do left the skill catalogue (promoted_to: native-router).
P2 catches a husk that still advertises ``user-invocable: true`` while the
index no longer carries it.

Run with: python3 -m pytest scripts/tests/test_validate_promoted_successors.py -v
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "validate-promoted-successors.py"

_spec = importlib.util.spec_from_file_location("validate_promoted_successors", SCRIPT)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

check = _mod.check


def _make_skill(
    repo_root: Path,
    category: str,
    name: str,
    promoted_to: str | None = None,
    user_invocable: bool | None = None,
) -> None:
    """Write a fixture SKILL.md carrying the frontmatter this validator reads."""
    lines = ["---", f"name: {name}", 'description: "fixture"']
    if promoted_to is not None:
        lines.append(f"promoted_to: {promoted_to}")
    if user_invocable is not None:
        lines.append(f"user-invocable: {str(user_invocable).lower()}")
    lines += ["---", "body", ""]
    skill_dir = repo_root / "skills" / category / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("\n".join(lines), encoding="utf-8")


def test_untagged_skill_is_ignored(tmp_path: Path) -> None:
    """A skill with no promoted_to is outside this validator's scope."""
    _make_skill(tmp_path, "meta", "plain-skill")
    assert check(tmp_path) == []


def test_resolving_successor_passes(tmp_path: Path) -> None:
    """A husk pointing at a real skill on disk is a clean retirement."""
    _make_skill(tmp_path, "meta", "umbrella")
    _make_skill(tmp_path, "meta", "husk", promoted_to="umbrella", user_invocable=False)
    assert check(tmp_path) == []


def test_phantom_successor_fails(tmp_path: Path) -> None:
    """P1: a successor that exists nowhere retires the skill into nothing."""
    _make_skill(tmp_path, "meta", "husk", promoted_to="native-router", user_invocable=False)
    failures = check(tmp_path)
    assert len(failures) == 1
    assert "P1 PHANTOM-SUCCESSOR" in failures[0]
    assert "skills/meta/husk/SKILL.md" in failures[0]
    assert "native-router" in failures[0]


def test_user_invocable_husk_fails(tmp_path: Path) -> None:
    """P2: an excluded skill that still advertises a user entry point."""
    _make_skill(tmp_path, "meta", "umbrella")
    _make_skill(tmp_path, "meta", "husk", promoted_to="umbrella", user_invocable=True)
    failures = check(tmp_path)
    assert len(failures) == 1
    assert "P2 INVOCABLE-EXCLUDED" in failures[0]
    assert "skills/meta/husk/SKILL.md" in failures[0]


def test_both_failures_report_together(tmp_path: Path) -> None:
    """The live /do shape: phantom successor on a user-invocable skill."""
    _make_skill(tmp_path, "meta", "do", promoted_to="native-router", user_invocable=True)
    failures = check(tmp_path)
    assert len(failures) == 2
    assert any("P1 PHANTOM-SUCCESSOR" in f for f in failures)
    assert any("P2 INVOCABLE-EXCLUDED" in f for f in failures)


def test_flat_layout_successor_resolves(tmp_path: Path) -> None:
    """Successors resolve in the flat skills/<name>/ layout too (skills/workflow)."""
    flat = tmp_path / "skills" / "workflow"
    flat.mkdir(parents=True)
    (flat / "SKILL.md").write_text('---\nname: workflow\ndescription: "fixture"\n---\nbody\n', encoding="utf-8")
    _make_skill(tmp_path, "meta", "husk", promoted_to="workflow", user_invocable=False)
    assert check(tmp_path) == []


def test_indexed_successor_resolves(tmp_path: Path) -> None:
    """A successor present only in the merged index still counts as real."""
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)
    (tmp_path / "skills" / "INDEX.local.json").write_text(
        '{"skills": {"private-umbrella": {"file": "skills/private/private-umbrella/SKILL.md"}}}',
        encoding="utf-8",
    )
    _make_skill(tmp_path, "meta", "husk", promoted_to="private-umbrella", user_invocable=False)
    assert check(tmp_path) == []


def test_repo_state_names_the_do_phantom() -> None:
    """The live repo: /do is retired into a successor that does not exist.

    The fix lands in skills/meta/do/SKILL.md, not here — this pins that the
    failure stays legible (file path plus phantom target) until it does.
    """
    repo_root = SCRIPT.resolve().parent.parent
    failures = check(repo_root)
    phantoms = [f for f in failures if "P1 PHANTOM-SUCCESSOR" in f]
    for f in phantoms:
        assert "skills/" in f and "SKILL.md" in f
