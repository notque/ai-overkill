"""Negative-control tests for scripts/validate-pipeline-index.py.

Proves the validator rejects every defect class (P1, P2, P3) and accepts
a clean pipeline-index.json. Tests the check() function directly with
explicit repo_root so file paths resolve inside the temp tree.

Run with: python3 -m pytest scripts/tests/test_validate_pipeline_index.py -v
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

# Import the script's check() function by path (script name has hyphens).
_spec = importlib.util.spec_from_file_location(
    "validate_pipeline_index",
    Path(__file__).resolve().parent.parent / "validate-pipeline-index.py",
)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
check = _mod.check


def _write_index(path: Path, pipelines: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"pipelines": pipelines}), encoding="utf-8")


def _write_doc(repo: Path, relpath: str, headings: list[str]) -> None:
    p = repo / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(f"## {h}" for h in headings) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Positive: clean pipeline -> no failures
# ---------------------------------------------------------------------------


def test_clean_pipeline_passes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    doc = "docs/my-pipeline.md"
    _write_doc(repo, doc, ["Phase 1: Setup", "Phase 2: Execute"])
    index = repo / "pipeline-index.json"
    _write_index(index, {"my-pipeline": {"file": doc, "phases": ["Setup", "Execute"]}})
    failures = check(index, repo)
    assert failures == [], failures


# ---------------------------------------------------------------------------
# NEGATIVE P1: missing file -> failure with MISSING-FILE
# ---------------------------------------------------------------------------


def test_p1_missing_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    index = repo / "pipeline-index.json"
    _write_index(index, {"ghost": {"file": "docs/nonexistent.md", "phases": ["Build"]}})
    failures = check(index, repo)
    assert len(failures) == 1, failures
    assert "MISSING-FILE" in failures[0], failures[0]
    assert "ghost" in failures[0], failures[0]


def test_p1_no_file_key(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    index = repo / "pipeline-index.json"
    _write_index(index, {"nofile": {"phases": ["Build"]}})
    failures = check(index, repo)
    assert len(failures) == 1, failures
    assert "MISSING-FILE" in failures[0], failures[0]


# ---------------------------------------------------------------------------
# NEGATIVE P2: phantom phase -> failure with PHANTOM-PHASE
# ---------------------------------------------------------------------------


def test_p2_phantom_phase(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    doc = "docs/real-pipeline.md"
    _write_doc(repo, doc, ["Phase 1: Setup"])
    index = repo / "pipeline-index.json"
    _write_index(index, {"real": {"file": doc, "phases": ["Setup", "Deploy"]}})
    failures = check(index, repo)
    assert len(failures) == 1, failures
    assert "PHANTOM-PHASE" in failures[0], failures[0]
    assert "Deploy" in failures[0], failures[0]


# ---------------------------------------------------------------------------
# NEGATIVE P3: no phases -> failure with NO-PHASES
# ---------------------------------------------------------------------------


def test_p3_empty_phases(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    doc = "docs/empty-pipeline.md"
    _write_doc(repo, doc, ["Overview"])
    index = repo / "pipeline-index.json"
    _write_index(index, {"empty": {"file": doc, "phases": []}})
    failures = check(index, repo)
    assert len(failures) == 1, failures
    assert "NO-PHASES" in failures[0], failures[0]


def test_p3_missing_phases_key(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    doc = "docs/nophases.md"
    _write_doc(repo, doc, ["Overview"])
    index = repo / "pipeline-index.json"
    _write_index(index, {"nophases": {"file": doc}})
    failures = check(index, repo)
    assert len(failures) == 1, failures
    assert "NO-PHASES" in failures[0], failures[0]
