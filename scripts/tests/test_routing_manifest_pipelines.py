"""Tests pinning pipeline rendering in scripts/routing-manifest.py.

Pipelines were rendered as ``name — description`` in all three formatters. Two
router-critical fields never reached the manifest: ``force_route`` (11 pipelines
carry it, and the router rule "manifest entries marked FORCE MUST be selected"
was structurally unable to fire) and the 30 curated trigger sets. Compact mode
went further and suppressed the whole PIPELINES section unless the user's
literal text contained the substring "pipeline".

These tests pin the shared line grammar, the trigger rules that keep the
emission safe, and the removal of the substring gate.

Run with: python3 -m pytest scripts/tests/test_routing_manifest_pipelines.py -v
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "routing-manifest.py"
PIPELINE_INDEX = REPO_ROOT / "skills" / "workflow" / "references" / "pipeline-index.json"
DO_SKILL = REPO_ROOT / "skills" / "meta" / "do" / "SKILL.md"

_spec = importlib.util.spec_from_file_location("routing_manifest", SCRIPT)
assert _spec and _spec.loader
rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rm)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _pipeline(**over) -> dict:
    entry = {
        "file": "skills/workflow/references/p.md",
        "description": "Runs some phases.",
        "triggers": [],
        "category": "meta",
    }
    entry.update(over)
    return entry


def _entries(
    tmp_path: Path,
    monkeypatch,
    pipelines: dict,
    skills: dict | None = None,
    agents: dict | None = None,
) -> list[dict]:
    """Load entries with INDEX_PATHS pointed at fixture files."""
    paths = {}
    for key, payload in (("skills", skills), ("agents", agents), ("pipelines", pipelines)):
        if payload is None:
            continue
        path = tmp_path / f"{key}.json"
        path.write_text(json.dumps({key: payload}), encoding="utf-8")
        paths[key] = (path, None)
    monkeypatch.setattr(rm, "INDEX_PATHS", paths)
    return rm.load_entries()


def _line(text: str, name: str) -> str:
    """The single manifest line for `name`."""
    return next(ln for ln in text.splitlines() if ln.startswith(f"  {name} ") or ln == f"  {name}")


def _pipeline_section(text: str) -> str:
    return text.split("PIPELINES:", 1)[1]


def _index_pipelines() -> dict:
    return json.loads(PIPELINE_INDEX.read_text(encoding="utf-8"))["pipelines"]


# ---------------------------------------------------------------------------
# FORCE emission
# ---------------------------------------------------------------------------


class TestForceEmission:
    """``FORCE`` is what lets the router's force-route rule fire on a pipeline."""

    def test_force_pipeline_renders_force(self, tmp_path, monkeypatch) -> None:
        entries = _entries(tmp_path, monkeypatch, {"alpha": _pipeline(force_route=True)})
        assert "  alpha FORCE (meta) — Runs some phases." in rm.format_compact(entries)

    def test_plain_pipeline_renders_no_force(self, tmp_path, monkeypatch) -> None:
        entries = _entries(tmp_path, monkeypatch, {"alpha": _pipeline()})
        assert "FORCE" not in rm.format_compact(entries)

    def test_force_renders_in_every_mode(self, tmp_path, monkeypatch) -> None:
        entries = _entries(tmp_path, monkeypatch, {"alpha": _pipeline(force_route=True)})
        for out in (
            rm.format_compact(entries),
            rm.format_compact_mode(entries),
            rm.format_tiered(entries, set()),
        ):
            assert "  alpha FORCE (meta) —" in out

    def test_live_force_count_matches_the_index(self) -> None:
        """The manifest's FORCE pipelines are exactly the index's force_route entries.

        Pins the relationship rather than today's count of 11: a deliberate
        force_route flip should stay a one-line index edit, while a producer
        that silently drops the flag fails here.
        """
        expected = {n for n, d in _index_pipelines().items() if d.get("force_route")}
        section = _pipeline_section(rm.format_compact(rm.load_entries()))
        rendered = {ln.split()[0] for ln in section.splitlines() if " FORCE" in ln}
        assert rendered == expected

    def test_live_manifest_carries_every_index_pipeline(self) -> None:
        section = _pipeline_section(rm.format_compact(rm.load_entries()))
        rendered = {ln.split()[0] for ln in section.splitlines() if ln.startswith("  ")}
        assert rendered == set(_index_pipelines())


# ---------------------------------------------------------------------------
# Triggers
# ---------------------------------------------------------------------------


class TestTriggers:
    """Curated phrases are the only signal separating same-domain pipelines."""

    def test_pipeline_line_carries_triggers(self, tmp_path, monkeypatch) -> None:
        entries = _entries(tmp_path, monkeypatch, {"alpha": _pipeline(triggers=["ship it", "ship code"])})
        assert " t:ship it|ship code" in rm.format_compact(entries)

    def test_cap_limits_emitted_triggers(self, tmp_path, monkeypatch) -> None:
        many = [f"phrase {i}" for i in range(20)]
        entries = _entries(tmp_path, monkeypatch, {"alpha": _pipeline(triggers=many)})
        line = _line(rm.format_compact(entries), "alpha")
        assert line.count(rm.TRIGGER_SEP) == rm.TRIGGER_CAP - 1
        assert f"phrase {rm.TRIGGER_CAP}" not in line

    def test_agent_and_skill_names_are_dropped(self, tmp_path, monkeypatch) -> None:
        """A skill or agent name printed here would validate as a pipeline.

        The /do section validator tokenizes the text after PIPELINES:, so a
        borrowed name leaks across the section boundary.
        """
        entries = _entries(
            tmp_path,
            monkeypatch,
            {"alpha": _pipeline(triggers=["voice-validator", "some-agent", "real phrase"])},
            skills={"voice-validator": {"file": "s.md", "description": "A skill."}},
            agents={"some-agent": {"file": "a.md", "description": "An agent."}},
        )
        assert _line(rm.format_compact(entries), "alpha").endswith(" t:real phrase")

    def test_phrase_already_in_description_is_dropped(self, tmp_path, monkeypatch) -> None:
        entries = _entries(
            tmp_path,
            monkeypatch,
            {"alpha": _pipeline(description="Handles routing drift.", triggers=["routing drift", "index rot"])},
        )
        assert _line(rm.format_compact(entries), "alpha").endswith(" t:index rot")

    def test_live_pipelines_carry_triggers(self) -> None:
        section = _pipeline_section(rm.format_compact(rm.load_entries()))
        lines = [ln for ln in section.splitlines() if ln.startswith("  ")]
        assert lines and all(rm.TRIGGER_PREFIX in ln for ln in lines)


# ---------------------------------------------------------------------------
# Compact mode: the deleted substring gate
# ---------------------------------------------------------------------------


class TestCompactModeSectionPresence:
    """Regression tests for the removed ``show_pipelines`` gate."""

    def test_section_renders_without_the_pipeline_substring(self, tmp_path, monkeypatch) -> None:
        """The defect: "research X and write me an article" hid all 30 pipelines."""
        entries = _entries(tmp_path, monkeypatch, {"research-to-article": _pipeline()})
        out = rm.format_compact_mode(entries, request_text="research X and write me an article")
        assert "pipeline" not in "research X and write me an article"
        assert "PIPELINES:" in out
        assert "research-to-article" in out

    def test_section_renders_for_an_empty_request(self, tmp_path, monkeypatch) -> None:
        """routing-ab-test.py calls --compact with no --request at all."""
        entries = _entries(tmp_path, monkeypatch, {"alpha": _pipeline()})
        assert "PIPELINES:" in rm.format_compact_mode(entries)

    def test_output_is_independent_of_request_text(self, tmp_path, monkeypatch) -> None:
        """No request wording changes the manifest — the gate is gone, not relocated."""
        entries = _entries(tmp_path, monkeypatch, {"alpha": _pipeline(triggers=["go"])})
        baseline = rm.format_compact_mode(entries, request_text="")
        for request in ("pipeline", "build me a pipeline", "write an article", "PIPELINE"):
            assert rm.format_compact_mode(entries, request_text=request) == baseline

    def test_live_compact_manifest_shows_pipelines(self) -> None:
        out = rm.format_compact_mode(rm.load_entries(), request_text="research X and write me an article")
        assert "PIPELINES:" in out
        assert " FORCE " in _pipeline_section(out)

    def test_compact_pipelines_stay_trigger_free(self, tmp_path, monkeypatch) -> None:
        """Compact mode drops triggers on every section, pipelines included."""
        entries = _entries(tmp_path, monkeypatch, {"alpha": _pipeline(triggers=["some phrase"])})
        assert rm.TRIGGER_PREFIX not in rm.format_compact_mode(entries)

    def test_compact_truncates_description_and_not_for(self, tmp_path, monkeypatch) -> None:
        entries = _entries(
            tmp_path,
            monkeypatch,
            {"alpha": _pipeline(description="d" * 200, not_for="n" * 200)},
        )
        line = _line(rm.format_compact_mode(entries), "alpha")
        assert "d" * 200 not in line and "..." in line
        assert "n" * 200 not in line


# ---------------------------------------------------------------------------
# Line grammar and section integrity
# ---------------------------------------------------------------------------


class TestLineGrammar:
    """Pipeline lines mirror the skill line, minus the agent pairing slot."""

    def test_line_matches_the_contract_shape(self, tmp_path, monkeypatch) -> None:
        entries = _entries(
            tmp_path,
            monkeypatch,
            {"alpha": _pipeline(force_route=True, category="review", not_for="tiny diffs", triggers=["go now"])},
        )
        assert "  alpha FORCE (review) — Runs some phases. NOT: tiny diffs t:go now" in rm.format_compact(entries)

    def test_no_agent_slot_is_rendered(self) -> None:
        """Pipelines declare no agent pairing, so the skill line's agent= is absent."""
        section = _pipeline_section(rm.format_compact(rm.load_entries()))
        assert "agent=" not in section

    def test_not_for_prefix_is_not_doubled(self, tmp_path, monkeypatch) -> None:
        entries = _entries(tmp_path, monkeypatch, {"alpha": _pipeline(not_for="NOT: tiny diffs")})
        out = rm.format_compact(entries)
        assert "NOT: tiny diffs" in out and "NOT: NOT:" not in out

    def test_tiered_pipeline_line_matches_the_full_manifest(self, tmp_path, monkeypatch) -> None:
        """Pipelines always render FULL in tiered mode, so the lines are identical."""
        entries = _entries(tmp_path, monkeypatch, {"alpha": _pipeline(force_route=True, triggers=["go now"])})
        line = _line(rm.format_compact(entries), "alpha")
        assert line in rm.format_tiered(entries, set())

    def test_section_order_is_stable_in_every_mode(self) -> None:
        """The /do validator tokenizes between these headers; order is load-bearing."""
        entries = rm.load_entries()
        for out in (
            rm.format_compact(entries),
            rm.format_compact_mode(entries),
            rm.format_tiered(entries, set()),
        ):
            assert out.index("AGENTS:") < out.index("SKILLS:") < out.index("PIPELINES:")


# ---------------------------------------------------------------------------
# Router prose counts
# ---------------------------------------------------------------------------


class TestRouterProseCounts:
    """The /do prose quotes pipeline counts; a force_route flip must not silently falsify them."""

    def test_prose_force_count_matches_the_index(self) -> None:
        expected = sum(1 for d in _index_pipelines().values() if d.get("force_route"))
        match = re.search(r"A FORCE pipeline \((\d+) of the (\d+)\)", DO_SKILL.read_text(encoding="utf-8"))
        assert match, "router prose no longer states the FORCE pipeline count; update this test with it"
        assert int(match.group(1)) == expected, (
            f"skills/meta/do/SKILL.md says {match.group(1)} FORCE pipelines; "
            f"pipeline-index.json has {expected}. Update the router prose."
        )

    def test_prose_total_count_matches_the_index(self) -> None:
        expected = len(_index_pipelines())
        text = DO_SKILL.read_text(encoding="utf-8")
        match = re.search(r"(\d+) pipelines are available", text)
        assert match, "router prose no longer states the pipeline total; update this test with it"
        assert int(match.group(1)) == expected, (
            f"skills/meta/do/SKILL.md says {match.group(1)} pipelines are available; "
            f"pipeline-index.json has {expected}. Update the router prose."
        )
