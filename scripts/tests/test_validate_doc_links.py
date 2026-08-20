"""Negative-control tests for scripts/validate-doc-links.py.

Proves the validator rejects broken links and accepts valid links,
external URLs, and anchor-only references.

Run with: python3 -m pytest scripts/tests/test_validate_doc_links.py -v
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "validate-doc-links.py"


def _setup_repo(tmp_path: Path, doc_content: str, files: list[str] | None = None) -> Path:
    """Build a minimal repo tree with a docs/ markdown file and optional target files."""
    repo = tmp_path / "repo"
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir(parents=True)
    docs = repo / "docs"
    docs.mkdir()
    docs.joinpath("test.md").write_text(doc_content, encoding="utf-8")

    # Copy the validator into repo/scripts/ so REPO_ROOT resolves to repo/
    shutil.copy2(SCRIPT, scripts_dir / "validate-doc-links.py")

    for f in files or []:
        p = repo / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("stub\n", encoding="utf-8")
    return repo


def _run(repo: Path) -> subprocess.CompletedProcess[str]:
    script = repo / "scripts" / "validate-doc-links.py"
    return subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(repo),
    )


# ---------------------------------------------------------------------------
# Positive: all links resolve -> exit 0
# ---------------------------------------------------------------------------


def test_clean_links_pass(tmp_path: Path) -> None:
    content = "# Guide\n\nSee [setup](setup.md) for details.\n"
    repo = _setup_repo(tmp_path, content, files=["docs/setup.md"])
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# NEGATIVE: broken link -> exit 1
# ---------------------------------------------------------------------------


def test_broken_link_exits_one(tmp_path: Path) -> None:
    content = "# Guide\n\nSee [missing](nonexistent/path.md) for details.\n"
    repo = _setup_repo(tmp_path, content)
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "nonexistent/path.md" in result.stdout, result.stdout


def test_broken_absolute_link_exits_one(tmp_path: Path) -> None:
    content = "# Guide\n\nSee [missing](/docs/vanished.md) for details.\n"
    repo = _setup_repo(tmp_path, content)
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "vanished.md" in result.stdout, result.stdout


# ---------------------------------------------------------------------------
# Edge case: external and anchor-only links are skipped
# ---------------------------------------------------------------------------


def test_external_links_skipped(tmp_path: Path) -> None:
    content = "# Guide\n\nSee [docs](https://example.com/docs) and [mail](mailto:a@b.com).\n"
    repo = _setup_repo(tmp_path, content)
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_anchor_only_links_skipped(tmp_path: Path) -> None:
    content = "# Guide\n\nSee [section](#overview) for context.\n"
    repo = _setup_repo(tmp_path, content)
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr
