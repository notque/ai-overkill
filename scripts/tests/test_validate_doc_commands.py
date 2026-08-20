"""Negative-control tests for scripts/validate-doc-commands.py.

Proves the validator rejects bad input (missing script references) and
accepts good input (existing script references, external paths).

Run with: python3 -m pytest scripts/tests/test_validate_doc_commands.py -v
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "validate-doc-commands.py"


def _setup_repo(tmp_path: Path, doc_content: str, scripts: list[str] | None = None) -> Path:
    """Build a minimal repo tree with a docs/ markdown file and optional script stubs."""
    repo = tmp_path / "repo"
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir(parents=True)
    docs = repo / "docs"
    docs.mkdir()
    docs.joinpath("test.md").write_text(doc_content, encoding="utf-8")

    # Copy the validator into repo/scripts/ so REPO_ROOT resolves to repo/
    shutil.copy2(SCRIPT, scripts_dir / "validate-doc-commands.py")

    for s in scripts or []:
        p = repo / s
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("#!/bin/bash\n", encoding="utf-8")
    return repo


def _run(repo: Path) -> subprocess.CompletedProcess[str]:
    script = repo / "scripts" / "validate-doc-commands.py"
    return subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(repo),
    )


# ---------------------------------------------------------------------------
# Positive: all referenced scripts exist -> exit 0
# ---------------------------------------------------------------------------


def test_clean_references_pass(tmp_path: Path) -> None:
    content = "# Guide\n\n```bash\npython3 scripts/deploy.py --dry-run\n```\n"
    repo = _setup_repo(tmp_path, content, scripts=["scripts/deploy.py"])
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# NEGATIVE: referenced script does not exist -> exit 1
# ---------------------------------------------------------------------------


def test_missing_script_exits_one(tmp_path: Path) -> None:
    content = "# Guide\n\n```bash\npython3 scripts/missing-script.py\n```\n"
    repo = _setup_repo(tmp_path, content)
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "missing-script.py" in result.stdout, result.stdout


def test_missing_sh_script_exits_one(tmp_path: Path) -> None:
    content = "# Guide\n\n```bash\n./scripts/missing.sh\n```\n"
    repo = _setup_repo(tmp_path, content)
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "missing.sh" in result.stdout, result.stdout


# ---------------------------------------------------------------------------
# Edge case: external/home paths are skipped, not flagged
# ---------------------------------------------------------------------------


def test_external_paths_skipped(tmp_path: Path) -> None:
    content = "# Guide\n\n```bash\npython3 ~/tools/setup.py\npython3 /tmp/scratch.py\n```\n"
    repo = _setup_repo(tmp_path, content)
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_variable_paths_skipped(tmp_path: Path) -> None:
    content = "# Guide\n\n```bash\npython3 $HOME/tools/setup.py\n```\n"
    repo = _setup_repo(tmp_path, content)
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr
