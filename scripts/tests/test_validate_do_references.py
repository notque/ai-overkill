"""Tests for scripts/validate-do-references.py — /do control-law name integrity.

The validator asserts every component name in skills/meta/do/SKILL.md's verb
maps, fallback clauses, error handling, and Phase 3 rows resolves in
skills/INDEX.json, agents/INDEX.json, or the pipeline index. These tests prove
both directions: the shipped file passes, and re-introducing a phantom name
(the exact defect class this validator exists to block) fails the build.

Run with: python3 -m pytest scripts/tests/test_validate_do_references.py -v
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "validate-do-references.py"
SKILL_FILE = REPO_ROOT / "skills" / "meta" / "do" / "SKILL.md"
REFS_DIR = SKILL_FILE.parent / "references"
COLD_REFS = ("error-handling.md", "routing-telemetry.md")
SKILLS_INDEX = REPO_ROOT / "skills" / "INDEX.json"
AGENTS_INDEX = REPO_ROOT / "agents" / "INDEX.json"


def _run(skill_file: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--skill-file", str(skill_file), "--repo-root", str(REPO_ROOT)],
        capture_output=True,
        text=True,
    )


def _skill_copy(tmp_path: Path, old: str, new: str) -> Path:
    """Copy the real SKILL.md (+ cold refs) with one substring swapped; assert the swap hit."""
    text = SKILL_FILE.read_text(encoding="utf-8")
    assert old in text, f"fixture drift: {old!r} not in SKILL.md — update this test"
    out = tmp_path / "SKILL.md"
    out.write_text(text.replace(old, new), encoding="utf-8")
    refs = tmp_path / "references"
    refs.mkdir(exist_ok=True)
    for name in COLD_REFS:
        shutil.copy(REFS_DIR / name, refs / name)
    return out


@pytest.fixture(autouse=True)
def _require_indices() -> None:
    if not (SKILLS_INDEX.exists() and AGENTS_INDEX.exists()):
        pytest.skip("INDEX.json not generated — run scripts/generate-skill-index.py and generate-agent-index.py")


def test_shipped_skill_file_passes() -> None:
    """The repo's /do SKILL.md carries no phantom component names."""
    result = _run(SKILL_FILE)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "all resolve" in result.stdout


def test_phantom_in_verb_map_fails(tmp_path: Path) -> None:
    """Re-introducing the audited phantom 'audit-report' exits 1 and names it."""
    modified = _skill_copy(tmp_path, "audit→systematic-code-review", "audit→audit-report")
    result = _run(modified)
    assert result.returncode == 1
    assert "audit-report" in result.stdout


def test_phantom_in_phase3_row_fails(tmp_path: Path) -> None:
    """A Phase 3 enhancement row naming a nonexistent skill exits 1."""
    anchor = "| Objective with done-criteria"
    modified = _skill_copy(tmp_path, anchor, "| frobnicate signal | Stack `made-up-skill-zz` |\n" + anchor)
    result = _run(modified)
    assert result.returncode == 1
    assert "made-up-skill-zz" in result.stdout


def test_phantom_pipeline_in_overrides_fails(tmp_path: Path) -> None:
    """A pipeline annotation naming a nonexistent pipeline exits 1."""
    modified = _skill_copy(tmp_path, "(systematic-debugging pipeline)", "(not-a-real-pipeline pipeline)")
    result = _run(modified)
    assert result.returncode == 1
    assert "not-a-real-pipeline" in result.stdout


def test_voice_profile_names_accepted(tmp_path: Path) -> None:
    """voice-* names pass: profiles are user-level skills outside the repo index."""
    modified = _skill_copy(tmp_path, "voice-example-profile", "voice-zz-test-profile")
    result = _run(modified)
    assert result.returncode == 0, result.stdout + result.stderr


def test_stale_prose_term_fails(tmp_path: Path) -> None:
    """A PROSE_TERMS entry with zero occurrences in scope exits 1 — a stale
    allowlist entry would let a future phantom silently reuse the name."""
    modified = _skill_copy(tmp_path, "HARD — non-negotiable", "HARD")
    result = _run(modified)
    assert result.returncode == 1
    assert "STALE ALLOWLIST" in result.stdout
    assert "non-negotiable" in result.stdout


def test_missing_region_anchor_fails(tmp_path: Path) -> None:
    """Restructuring an anchored region away fails loudly, not silently."""
    modified = _skill_copy(tmp_path, "## Error Handling", "## Renamed Section")
    result = _run(modified)
    assert result.returncode == 1
    assert "anchor not found" in result.stdout


def test_phantom_in_cold_reference_fails(tmp_path: Path) -> None:
    """A phantom name in a scanned cold reference file exits 1 and names it."""
    modified = _skill_copy(tmp_path, "# /do - Smart Router", "# /do - Smart Router")
    ref = tmp_path / "references" / "error-handling.md"
    text = ref.read_text(encoding="utf-8")
    anchor = "verification-before-completion"
    assert anchor in text, "fixture drift: update this test"
    ref.write_text(text.replace(anchor, "made-up-verifier-zz", 1), encoding="utf-8")
    result = _run(modified)
    assert result.returncode == 1
    assert "made-up-verifier-zz" in result.stdout


def test_missing_cold_reference_fails(tmp_path: Path) -> None:
    """Deleting a scanned cold reference fails loudly — coverage cannot drop."""
    modified = _skill_copy(tmp_path, "# /do - Smart Router", "# /do - Smart Router")
    (tmp_path / "references" / "routing-telemetry.md").unlink()
    result = _run(modified)
    assert result.returncode == 1
    assert "cold reference not found" in result.stdout
