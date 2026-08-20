"""Negative-control tests for scripts/check-routing-drift.py.

Proves the drift checker rejects missing-from-manifest and unresolvable
skills, and accepts a clean setup. Uses a self-contained temp tree with
stub INDEX.json and routing-manifest.py.

Run with: python3 -m pytest scripts/tests/test_check_routing_drift.py -v
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "check-routing-drift.py"


def _setup_repo(
    tmp_path: Path,
    skills: dict[str, dict],
    manifest_skills: list[str] | None = None,
) -> Path:
    """Build a minimal repo tree with INDEX.json, a stub routing-manifest.py,
    and SKILL.md files for each skill. manifest_skills controls which names
    the stub manifest emits (defaults to all skill names)."""
    repo = tmp_path / "repo"
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir(parents=True)

    # Copy the real script so REPO_ROOT resolves to repo/
    shutil.copy2(SCRIPT, scripts_dir / "check-routing-drift.py")

    # Write skills/INDEX.json
    index_dir = repo / "skills"
    index_dir.mkdir(parents=True)
    index_data = {"skills": skills}
    (index_dir / "INDEX.json").write_text(json.dumps(index_data), encoding="utf-8")

    # Create SKILL.md stubs for each skill entry that has a file field
    for entry in skills.values():
        file_field = entry.get("file", "")
        if file_field:
            p = repo / file_field
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("# Stub\n", encoding="utf-8")

    # Create a stub routing-manifest.py that prints skill names
    if manifest_skills is None:
        manifest_skills = list(skills.keys())
    manifest_lines = "\n".join(f"  - {name}: does things" for name in manifest_skills)
    manifest_script = scripts_dir / "routing-manifest.py"
    manifest_script.write_text(
        f"#!/usr/bin/env python3\nprint('''{manifest_lines}''')\n",
        encoding="utf-8",
    )

    # Stub generate-skill-index.py (not needed when INDEX.json exists)
    (scripts_dir / "generate-skill-index.py").write_text(
        "#!/usr/bin/env python3\npass\n",
        encoding="utf-8",
    )

    return repo


def _run(repo: Path) -> subprocess.CompletedProcess[str]:
    script = repo / "scripts" / "check-routing-drift.py"
    return subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(repo),
    )


# ---------------------------------------------------------------------------
# Positive: all indexed skills appear in manifest -> exit 0
# ---------------------------------------------------------------------------


def test_clean_setup_passes(tmp_path: Path) -> None:
    skills = {
        "deploy": {"file": "skills/deploy/SKILL.md", "description": "deploy"},
        "review": {"file": "skills/review/SKILL.md", "description": "review"},
    }
    repo = _setup_repo(tmp_path, skills)
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# NEGATIVE: skill absent from routing manifest -> exit 1
# ---------------------------------------------------------------------------


def test_missing_from_manifest_exits_one(tmp_path: Path) -> None:
    skills = {
        "visible": {"file": "skills/visible/SKILL.md", "description": "ok"},
        "invisible": {"file": "skills/invisible/SKILL.md", "description": "missing"},
    }
    repo = _setup_repo(tmp_path, skills, manifest_skills=["visible"])
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "invisible" in result.stdout, result.stdout


# ---------------------------------------------------------------------------
# NEGATIVE: indexed skill's SKILL.md does not exist on disk -> exit 1
# ---------------------------------------------------------------------------


def test_unresolvable_skill_exits_one(tmp_path: Path) -> None:
    skills = {
        "good": {"file": "skills/good/SKILL.md", "description": "ok"},
        "ghost": {"file": "skills/ghost/SKILL.md", "description": "phantom"},
    }
    repo = _setup_repo(tmp_path, skills, manifest_skills=["good", "ghost"])
    # Remove the SKILL.md that _setup_repo created for ghost
    ghost_file = repo / "skills" / "ghost" / "SKILL.md"
    ghost_file.unlink()
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "ghost" in (result.stdout + result.stderr), result.stdout + result.stderr
