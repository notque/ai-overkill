"""Private skill deployment must reach dispatch without changing the public index."""

import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("discovery_sync", ROOT / "hooks/sync-to-user-claude.py")
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


def skill(path, name):
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Test skill.\n---\n")


def test_deployed_private_skill_becomes_dispatchable(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    source = repo / "skills"
    skill(source / "meta" / "public-skill", "public-skill")
    private = tmp_path / "private" / "voice"
    skill(private / "skills" / "private-editor", "private-editor")
    (source / "voice").symlink_to(private, target_is_directory=True)
    malformed = private / "skills" / "broken"
    malformed.mkdir()
    (malformed / "SKILL.md").write_text("---\nname: [broken\n---\n")
    skill(private / "skills" / "retired", "retired")
    (private / "skills" / "retired" / "SKILL.md").write_text("---\nname: retired\npromoted_to: public-skill\n---\n")
    public = {"version": "2.0", "skills": {"public-skill": {"file": "skills/meta/public-skill/SKILL.md"}}}
    public_bytes = json.dumps(public)
    (source / "INDEX.json").write_text(public_bytes)
    deployed = tmp_path / ".claude" / "skills"
    skill(deployed / "private-editor", "private-editor")
    skill(deployed / "custom", "custom")
    custom = {"file": "skills/custom/SKILL.md", "description": "Keep local metadata"}
    (source / "INDEX.local.json").write_text(
        json.dumps({"skills": {"custom": custom, "removed": {"file": "skills/removed/SKILL.md"}}})
    )

    assert sync._refresh_local_skill_index(repo)
    local = json.loads((source / "INDEX.local.json").read_text())
    assert local["skills"]["custom"] == custom
    assert local["skills"]["private-editor"]["file"] == "skills/private-editor/SKILL.md"
    assert "public-skill" in local["skills"]
    assert "broken" not in local["skills"]
    assert "retired" not in local["skills"]
    assert "missing" not in local["skills"]
    assert "removed" not in local["skills"]
    assert (source / "INDEX.json").read_text() == public_bytes
    assert not sync._refresh_local_skill_index(repo)

    runtime = tmp_path / ".codex" / "skills"
    for name in ("private-editor", "public-skill"):
        skill(runtime / name, name)
    sync._sync_codex_runtime_skill_indexes(source, runtime)
    published = json.loads((runtime / "INDEX.json").read_text())["skills"]
    assert set(published) == {"private-editor", "public-skill"}
    for entry in published.values():
        assert (runtime.parent / entry["file"]).is_file()


def test_discovery_failure_preserves_overlay(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    skills = repo / "skills"
    skills.mkdir(parents=True)
    local = skills / "INDEX.local.json"
    local.write_text('{"skills": {"custom": {}}}')
    before = local.read_bytes()
    with pytest.raises(RuntimeError, match="Skill discovery failed"):
        sync._refresh_local_skill_index(repo)
    assert local.read_bytes() == before
