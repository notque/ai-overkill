"""Tests for scripts/generate-routing-map.py.

Validates the static routing map generator: table rendering, --check
detection of missing entries, empty descriptions, stale maps, and
pairs_with resolution.

Run with: python3 -m pytest scripts/tests/test_generate_routing_map.py -v
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "generate-routing-map.py"

_spec = importlib.util.spec_from_file_location("generate_routing_map", SCRIPT)
assert _spec and _spec.loader
grm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(grm)


def _surfaces(
    agents: dict | None = None,
    skills: dict | None = None,
    pipelines: dict | None = None,
) -> dict[str, list[dict]]:
    """Build a surfaces dict from raw INDEX-shaped dicts."""
    result: dict[str, list[dict]] = {"agents": [], "skills": [], "pipelines": []}
    for section, raw in [("agents", agents), ("skills", skills), ("pipelines", pipelines)]:
        if not raw:
            continue
        for name, data in raw.items():
            result[section].append(
                {
                    "name": name,
                    "description": data.get("description", ""),
                    "triggers": data.get("triggers", []),
                    "force_route": bool(data.get("force_route", False)),
                    "not_for": data.get("not_for", ""),
                    "pairs_with": data.get("pairs_with", []),
                }
            )
    return result


class TestImportable:
    """The script exposes generate_map and check_map."""

    def test_has_generate_map(self) -> None:
        assert callable(getattr(grm, "generate_map", None))

    def test_has_check_map(self) -> None:
        assert callable(getattr(grm, "check_map", None))


class TestTableRendering:
    """Markdown table output from generate_map."""

    def test_contains_all_three_sections(self) -> None:
        s = _surfaces(
            agents={"a1": {"description": "Agent one.", "triggers": ["go"]}},
            skills={"s1": {"description": "Skill one.", "triggers": ["do"]}},
            pipelines={"p1": {"description": "Pipeline one.", "triggers": ["run"]}},
        )
        md = grm.generate_map(s)
        assert "## AGENTS (1)" in md
        assert "## SKILLS (1)" in md
        assert "## PIPELINES (1)" in md

    def test_entry_appears_in_table(self) -> None:
        s = _surfaces(agents={"test-agent": {"description": "Test agent.", "triggers": ["test", "check"]}})
        md = grm.generate_map(s)
        assert "| test-agent |" in md
        assert "test, check" in md

    def test_force_route_shown(self) -> None:
        s = _surfaces(skills={"fr": {"description": "Forced.", "triggers": ["x"], "force_route": True}})
        md = grm.generate_map(s)
        assert "| yes |" in md

    def test_pipe_escaped(self) -> None:
        s = _surfaces(agents={"a": {"description": "A | B.", "triggers": ["t"]}})
        md = grm.generate_map(s)
        assert "A \\| B." in md


class TestCheckFindings:
    """check_map detects common defects."""

    def test_empty_description_flagged(self) -> None:
        s = _surfaces(agents={"bad": {"description": "", "triggers": ["x"]}})
        findings = grm.check_map(s)
        assert any("empty description" in f for f in findings)

    def test_zero_triggers_flagged(self) -> None:
        s = _surfaces(skills={"notrig": {"description": "Has a desc.", "triggers": []}})
        findings = grm.check_map(s)
        assert any("zero triggers" in f for f in findings)

    def test_pairs_with_phantom_flagged(self) -> None:
        s = _surfaces(
            agents={"real": {"description": "Real.", "triggers": ["r"], "pairs_with": ["nonexistent"]}},
        )
        findings = grm.check_map(s)
        assert any("resolves to nothing" in f for f in findings)

    def test_pairs_with_valid_not_flagged(self) -> None:
        s = _surfaces(
            agents={"a1": {"description": "A.", "triggers": ["x"], "pairs_with": ["s1"]}},
            skills={"s1": {"description": "S.", "triggers": ["y"]}},
        )
        findings = grm.check_map(s)
        pairs_findings = [f for f in findings if "resolves to nothing" in f]
        assert len(pairs_findings) == 0

    def test_stale_map_flagged(self, monkeypatch) -> None:
        s = _surfaces(agents={"a": {"description": "A.", "triggers": ["x"]}})
        monkeypatch.setattr(grm, "MAP_PATH", Path("/tmp/nonexistent-routing-map-test.md"))
        findings = grm.check_map(s)
        assert any("stale" in f for f in findings)

    def test_clean_map_no_stale_finding(self, tmp_path, monkeypatch) -> None:
        s = _surfaces(agents={"a": {"description": "A.", "triggers": ["x"]}})
        map_file = tmp_path / "routing-map.md"
        map_file.write_text(grm.generate_map(s), encoding="utf-8")
        monkeypatch.setattr(grm, "MAP_PATH", map_file)
        findings = grm.check_map(s)
        assert not any("stale" in f for f in findings)


class TestRealRepo:
    """Smoke tests against the live repo INDEX files."""

    def test_load_all_entries_returns_three_surfaces(self) -> None:
        surfaces = grm.load_all_entries()
        assert "agents" in surfaces
        assert "skills" in surfaces
        assert "pipelines" in surfaces
        assert len(surfaces["agents"]) > 0
        assert len(surfaces["skills"]) > 0
        assert len(surfaces["pipelines"]) > 0

    def test_generate_map_produces_all_sections(self) -> None:
        md = grm.generate_map()
        assert "## AGENTS" in md
        assert "## SKILLS" in md
        assert "## PIPELINES" in md

    def test_check_cli_rejects_stale_map(self, tmp_path) -> None:
        stale = tmp_path / "routing-map.md"
        stale.write_text("stale\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--check", "--map-path", str(stale)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, result.stdout + result.stderr
        assert "stale" in result.stderr

    def test_missing_indexes_fail_closed_without_overwriting_map(self, tmp_path) -> None:
        repo = tmp_path / "fresh-clone"
        map_file = repo / "docs" / "routing-map.md"
        map_file.parent.mkdir(parents=True)
        map_file.write_text("preserve me\n", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo-root", str(repo)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1
        assert "cannot be generated" in result.stderr
        assert map_file.read_text(encoding="utf-8") == "preserve me\n"

    def test_missing_generated_indexes_are_regenerated_before_render(self, tmp_path) -> None:
        repo = tmp_path / "fresh-clone"
        scripts = repo / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "generate-skill-index.py").write_text(
            'from pathlib import Path\nPath("skills").mkdir(exist_ok=True)\n'
            'Path("skills/INDEX.json").write_text(\'{"skills":{"s":{"description":"S","triggers":["s"]}}}\')\n',
            encoding="utf-8",
        )
        (scripts / "generate-agent-index.py").write_text(
            'from pathlib import Path\nPath("agents").mkdir(exist_ok=True)\n'
            'Path("agents/INDEX.json").write_text(\'{"agents":{"a":{"description":"A","triggers":["a"]}}}\')\n',
            encoding="utf-8",
        )
        pipeline_index = repo / "skills" / "workflow" / "references" / "pipeline-index.json"
        pipeline_index.parent.mkdir(parents=True)
        pipeline_index.write_text(
            '{"pipelines":{"p":{"description":"P","triggers":["p"]}}}',
            encoding="utf-8",
        )

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo-root", str(repo)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        rendered = (repo / "docs" / "routing-map.md").read_text(encoding="utf-8")
        assert "## AGENTS (1)" in rendered
        assert "## SKILLS (1)" in rendered
        assert "## PIPELINES (1)" in rendered

    @pytest.mark.parametrize(
        "bad_content",
        [b"{", b"[]", b'{"skills":[]}', b'{"skills":{"bad":[]}}', b"\xff"],
        ids=["malformed-json", "wrong-root-shape", "wrong-surface-shape", "wrong-entry-shape", "invalid-utf8"],
    )
    def test_invalid_required_index_fails_closed_without_overwrite(self, tmp_path, bad_content: bytes) -> None:
        repo = tmp_path / "repo"
        (repo / "skills").mkdir(parents=True)
        (repo / "agents").mkdir()
        pipeline_index = repo / "skills" / "workflow" / "references" / "pipeline-index.json"
        pipeline_index.parent.mkdir(parents=True)
        (repo / "skills" / "INDEX.json").write_bytes(bad_content)
        (repo / "agents" / "INDEX.json").write_text('{"agents":{}}', encoding="utf-8")
        pipeline_index.write_text('{"pipelines":{}}', encoding="utf-8")
        map_file = repo / "docs" / "routing-map.md"
        map_file.parent.mkdir()
        map_file.write_text("preserve me\n", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo-root", str(repo)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1
        assert "required skills index" in result.stderr
        assert map_file.read_text(encoding="utf-8") == "preserve me\n"


class TestPrivateNameFiltering:
    """Private component names never reach the public map; typos still do.

    Fixture names only. The real private names live outside this repo and
    must never be written into a tracked file.
    """

    PRIVATE = frozenset({"fixture-private-skill"})

    def _surfaces_with_pairs(self, pairs: list[str]) -> dict[str, list[dict]]:
        return _surfaces(
            skills={
                "joy-fixture": {
                    "description": "A public skill.",
                    "triggers": ["fixture"],
                    "pairs_with": pairs,
                }
            }
        )

    def test_private_pairs_with_is_absent_from_rendered_map(self) -> None:
        surfaces = self._surfaces_with_pairs(["fixture-private-skill"])
        rendered = grm.generate_map(surfaces, private=self.PRIVATE)
        assert "fixture-private-skill" not in rendered
        assert "joy-fixture" in rendered

    def test_public_pairs_with_survives_rendering(self) -> None:
        surfaces = self._surfaces_with_pairs(["some-public-skill"])
        rendered = grm.generate_map(surfaces, private=self.PRIVATE)
        assert "some-public-skill" in rendered

    def test_entry_named_private_is_dropped_entirely(self) -> None:
        surfaces = _surfaces(
            skills={
                "fixture-private-skill": {"description": "P", "triggers": ["p"]},
                "joy-fixture": {"description": "A public skill.", "triggers": ["fixture"]},
            }
        )
        rendered = grm.generate_map(surfaces, private=self.PRIVATE)
        assert "fixture-private-skill" not in rendered
        assert "## SKILLS (1)" in rendered

    def test_private_pairs_with_raises_no_check_finding(self, tmp_path) -> None:
        surfaces = self._surfaces_with_pairs(["fixture-private-skill"])
        map_path = tmp_path / "routing-map.md"
        map_path.write_text(grm.generate_map(surfaces, private=self.PRIVATE), encoding="utf-8")

        findings = grm.check_map(surfaces, map_path, private=self.PRIVATE)

        assert findings == []

    def test_unknown_public_pairs_with_still_raises_a_check_finding(self, tmp_path) -> None:
        surfaces = self._surfaces_with_pairs(["no-such-public-skill"])
        map_path = tmp_path / "routing-map.md"
        map_path.write_text(grm.generate_map(surfaces, private=self.PRIVATE), encoding="utf-8")

        findings = grm.check_map(surfaces, map_path, private=self.PRIVATE)

        assert any("no-such-public-skill" in f and "resolves to nothing" in f for f in findings)

    def test_private_and_typo_are_separated_in_one_entry(self, tmp_path) -> None:
        surfaces = self._surfaces_with_pairs(["fixture-private-skill", "no-such-public-skill"])
        map_path = tmp_path / "routing-map.md"
        map_path.write_text(grm.generate_map(surfaces, private=self.PRIVATE), encoding="utf-8")

        findings = grm.check_map(surfaces, map_path, private=self.PRIVATE)

        assert len(findings) == 1
        assert "no-such-public-skill" in findings[0]

    def test_private_name_set_comes_from_the_leak_gate(self) -> None:
        """No second definition of "private": the gate is the only source."""
        gate_spec = importlib.util.spec_from_file_location(
            "_leak_gate_under_test", REPO_ROOT / "hooks" / "pretool-private-name-leak-gate.py"
        )
        assert gate_spec and gate_spec.loader
        gate = importlib.util.module_from_spec(gate_spec)
        gate_spec.loader.exec_module(gate)

        assert grm.private_names(REPO_ROOT) == frozenset(gate._private_names(REPO_ROOT))

    def test_shipped_map_carries_no_private_name(self) -> None:
        """The committed public artifact contains no locally private name."""
        rendered = (REPO_ROOT / "docs" / "routing-map.md").read_text(encoding="utf-8").lower()
        for name in grm.private_names(REPO_ROOT):
            assert name not in rendered

    def test_empty_private_set_is_a_no_op(self) -> None:
        """CI and public installs have no private tree; output is unchanged."""
        surfaces = self._surfaces_with_pairs(["fixture-private-skill"])
        assert grm.strip_private(surfaces, frozenset()) is surfaces
