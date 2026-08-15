"""Tests pinning trigger rendering in scripts/routing-manifest.py.

INDEX.json carries 1,791 hand-curated trigger phrases. They were loaded and
dropped one function later, leaving the router an alphabetical list of
descriptions with no discriminating signal. These tests pin what the full
manifest now emits, and the two rules that keep the emission safe and small.

Run with: python3 -m pytest scripts/tests/test_routing_manifest_triggers.py -v
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "routing-manifest.py"

_spec = importlib.util.spec_from_file_location("routing_manifest", SCRIPT)
assert _spec and _spec.loader
rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rm)


def _entries(tmp_path: Path, monkeypatch, skills: dict, agents: dict | None = None) -> list[dict]:
    """Load entries through the module with INDEX_PATHS pointed at fixtures."""
    skills_path = tmp_path / "SKILLS.json"
    skills_path.write_text(json.dumps({"skills": skills}), encoding="utf-8")
    paths = {"skills": (skills_path, None)}
    if agents is not None:
        agents_path = tmp_path / "AGENTS.json"
        agents_path.write_text(json.dumps({"agents": agents}), encoding="utf-8")
        paths["agents"] = (agents_path, None)
    monkeypatch.setattr(rm, "INDEX_PATHS", paths)
    return rm.load_entries()


def _skill(**over) -> dict:
    entry = {"file": "skills/x/SKILL.md", "description": "Does a thing.", "triggers": [], "category": "meta"}
    entry.update(over)
    return entry


class TestTriggerRendering:
    """Both sections carry a trailing ``t:`` field."""

    def test_skill_line_carries_triggers(self, tmp_path, monkeypatch) -> None:
        entries = _entries(tmp_path, monkeypatch, {"alpha": _skill(triggers=["do the thing", "thing time"])})
        out = rm.format_compact(entries)
        assert " t:do the thing|thing time" in out

    def test_agent_line_carries_triggers(self, tmp_path, monkeypatch) -> None:
        entries = _entries(
            tmp_path,
            monkeypatch,
            {},
            {"alpha-agent": {"file": "agents/a.md", "description": "An agent.", "triggers": ["ship it", "ship code"]}},
        )
        out = rm.format_compact(entries)
        assert " t:ship it|ship code" in out

    def test_cap_limits_emitted_triggers(self, tmp_path, monkeypatch) -> None:
        many = [f"phrase {i}" for i in range(20)]
        entries = _entries(tmp_path, monkeypatch, {"alpha": _skill(triggers=many)})
        line = next(ln for ln in rm.format_compact(entries).splitlines() if ln.startswith("  alpha"))
        assert line.count(rm.TRIGGER_SEP) == rm.TRIGGER_CAP - 1
        assert "phrase 0" in line and f"phrase {rm.TRIGGER_CAP}" not in line

    def test_entry_without_triggers_renders_no_field(self, tmp_path, monkeypatch) -> None:
        entries = _entries(tmp_path, monkeypatch, {"alpha": _skill(triggers=[])})
        assert rm.TRIGGER_PREFIX not in rm.format_compact(entries)

    def test_not_for_still_renders_once(self, tmp_path, monkeypatch) -> None:
        entries = _entries(tmp_path, monkeypatch, {"alpha": _skill(triggers=["go"], not_for="big refactors.")})
        out = rm.format_compact(entries)
        assert "NOT: big refactors." in out
        assert "NOT: NOT:" not in out


class TestTriggerSelection:
    """Two phrases are dropped before the cap applies."""

    def test_cross_section_name_is_dropped(self, tmp_path, monkeypatch) -> None:
        """A skill name inside an agent line would validate that skill as an agent."""
        entries = _entries(
            tmp_path,
            monkeypatch,
            {"kotlin": _skill(description="Kotlin methodology.")},
            {"kotlin-general-engineer": {"file": "agents/k.md", "description": "Kotlin dev.", "triggers": ["kotlin"]}},
        )
        names = rm.section_names(entries)
        agent = next(e for e in entries if e["type"] == "agent")
        assert rm.select_triggers(agent, names["skill"]) == []

    def test_phrase_already_in_description_is_dropped(self, tmp_path, monkeypatch) -> None:
        entries = _entries(
            tmp_path,
            monkeypatch,
            {"alpha": _skill(description="Handles routing drift.", triggers=["routing drift", "index rot"])},
        )
        line = next(ln for ln in rm.format_compact(entries).splitlines() if ln.startswith("  alpha"))
        assert line.endswith(" t:index rot")

    def test_selection_fills_the_cap_after_dropping(self, tmp_path, monkeypatch) -> None:
        """Filtering runs before the cap, so a dropped phrase does not cost a slot."""
        entry = {"description": "Handles drift.", "triggers": ["drift", *[f"p{i}" for i in range(6)]]}
        assert rm.select_triggers(entry, set()) == [f"p{i}" for i in range(rm.TRIGGER_CAP)]


class TestSizeBudget:
    """The manifest is injected on every routing decision, so bytes are the budget."""

    def test_live_manifest_stays_within_budget(self) -> None:
        entries = rm.load_entries()
        with_triggers = len(rm.format_compact(entries).encode("utf-8"))

        original = rm.TRIGGER_CAP
        try:
            rm.TRIGGER_CAP = 0
            baseline = len(rm.format_compact(entries).encode("utf-8"))
        finally:
            rm.TRIGGER_CAP = original

        assert baseline > 0
        growth = (with_triggers - baseline) / baseline
        assert growth < 0.30, f"triggers grew the manifest {growth:.1%}; budget is +28% at cap {original}"

    def test_compact_mode_stays_trigger_free(self) -> None:
        """--compact exists to shrink the manifest, so it skips the field."""
        assert rm.TRIGGER_PREFIX not in rm.format_compact_mode(rm.load_entries())

    def test_tiered_stubs_stay_trigger_free(self, tmp_path, monkeypatch) -> None:
        """--tiered stubs a cold entry to one short line; triggers stay off it."""
        entries = _entries(tmp_path, monkeypatch, {"cold": _skill(triggers=["some phrase"])})
        assert rm.TRIGGER_PREFIX not in rm.format_tiered(entries, set())

    def test_tiered_full_line_matches_the_full_manifest(self, tmp_path, monkeypatch) -> None:
        """A FULL line means the same line in both modes — force-route entries included."""
        entries = _entries(tmp_path, monkeypatch, {"hot": _skill(triggers=["some phrase"], force_route=True)})
        line = next(ln for ln in rm.format_compact(entries).splitlines() if ln.startswith("  hot"))
        assert line in rm.format_tiered(entries, set())
