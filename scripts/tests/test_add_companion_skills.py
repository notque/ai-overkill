"""Tests for typed companion-section generation."""

import importlib.util
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "add-companion-skills.py"
SPEC = importlib.util.spec_from_file_location("add_companion_skills", SCRIPT)
acs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acs)
DIRECTIVE = re.compile(r"Call the Skill tool with `([a-z0-9][a-z0-9-]*)`\.")


def test_classify_pairs_keeps_agents_and_pipelines_out_of_skills():
    indexes = (
        {"verification-before-completion": {}},
        {"feature-pipeline": {}},
        {"reviewer-code": {}},
    )
    assert acs.classify_pairs(["verification-before-completion", "feature-pipeline", "reviewer-code"], indexes) == (
        ["verification-before-completion"],
        ["feature-pipeline"],
        ["reviewer-code"],
    )


def test_callable_skill_wins_same_name_pipeline_overlap():
    indexes = ({"voice-writer": {}}, {"voice-writer": {}}, {})
    assert acs.classify_pairs(["voice-writer"], indexes) == (["voice-writer"], [], [])


def test_unknown_pair_fails_closed():
    with pytest.raises(ValueError, match="does not resolve"):
        acs.classify_pairs(["missing"], ({}, {}, {}))


def test_skill_section_uses_exact_action_contract():
    section = acs.build_section(
        ["verification-before-completion"],
        "Skills",
        {"verification-before-completion": {"description": "Verify before completion."}},
    )
    assert section.count("Call the Skill tool with `verification-before-completion`.") == 1


def test_agent_and_pipeline_sections_contain_no_skill_call():
    agent = acs.build_section(["reviewer-code"], "Agents", {"reviewer-code": {"short_description": "Review."}})
    pipeline = acs.build_section(
        ["feature-pipeline"], "Pipelines", {"feature-pipeline": {"description": "Feature phases."}}
    )
    assert "Call the Skill tool with" not in agent + pipeline
    assert "Skill tool cannot invoke" in agent
    assert "not the Skill tool" in pipeline


def test_skill_sections_require_skill_tool_permission():
    source = "---\nallowed-tools:\n  - Read\n---\n\nBody\n"
    updated = acs.ensure_skill_tool(source, ["verification-before-completion"])
    assert "allowed-tools:\n  - Read\n  - Skill\n" in updated
    assert acs.ensure_skill_tool(updated, ["verification-before-completion"]) == updated


def test_generated_agent_skill_calls_are_indexed_and_permitted():
    indexed = set(json.loads(acs.SKILL_INDEX.read_text(encoding="utf-8"))["skills"])
    for path in sorted(acs.AGENTS_DIR.glob("*.md")):
        source = path.read_text(encoding="utf-8")
        calls = DIRECTIVE.findall(source)
        frontmatter, _ = acs.parse_frontmatter(source)
        assert set(calls) <= indexed, f"{path.name} calls a non-skill component"
        assert not calls or "Skill" in frontmatter.get("allowed-tools", []), f"{path.name} cannot call Skill"
