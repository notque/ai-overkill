"""Security and ownership boundaries for architecture lifecycle artifacts."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HANDOFF = REPO_ROOT / "scripts" / "handoff.py"
ADR_QUERY = REPO_ROOT / "scripts" / "adr-query.py"
ARTIFACT_WRITER = REPO_ROOT / "scripts" / "repository_artifact.py"
DECISION_MEMORY = REPO_ROOT / "skills" / "research" / "architecture-deepening" / "scripts" / "decision_memory.py"
HANDOFF_SCHEMA = REPO_ROOT / "skills" / "shared-patterns" / "schemas" / "architecture-change-handoff.schema.json"
MEMORY_SCHEMA = (
    REPO_ROOT / "skills" / "research" / "architecture-deepening" / "references" / "decision-memory-record.schema.json"
)


def _load(path: Path, name: str):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _handoff(**overrides) -> dict:
    value = {
        "origin": "architecture-deepening",
        "result": "selected",
        "candidate": "arch:v1:pkg/auth::Authenticate::duplicated-coordination",
        "change_class": "behavior-preserving-refactor",
        "scope": {"modules": ["pkg/auth"], "callers": ["cmd/api"]},
        "risk": "low",
        "decision_artifact": None,
        "decision_scope": None,
        "consultation_adr": None,
        "consultation_adr_hash": None,
        "current_interface": "Callers coordinate token refresh and retries.",
        "proposed_interface": "Authenticate owns token refresh and retries.",
        "migration": "Move one caller at a time.",
        "success_criteria": [
            "Delete duplicated refresh coordination from two callers.",
            "Keep authentication behavior and compatibility tests green.",
        ],
        "next_skill": "workflow",
        "next_pipeline": "systematic-refactoring",
    }
    value.update(overrides)
    return value


def _no_findings() -> dict:
    return _handoff(
        result="no-findings",
        candidate=None,
        change_class="close",
        scope={"modules": ["pkg/auth"], "callers": []},
        current_interface=None,
        proposed_interface=None,
        migration=None,
        success_criteria=[],
        next_skill=None,
        next_pipeline=None,
    )


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def _run(script: Path, *args: str, cwd: Path, input_text: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )


def test_neutral_handoff_boundary_owns_shared_schema() -> None:
    assert HANDOFF.is_file()
    assert HANDOFF_SCHEMA.is_file()
    architecture_root = REPO_ROOT / "skills" / "research" / "architecture-deepening"
    assert not (architecture_root / "references" / "handoff.schema.json").exists()


def test_handoff_rejects_candidate_module_scope_contradiction(tmp_path: Path) -> None:
    result = _run(
        HANDOFF,
        "validate",
        "--repo-root",
        ".",
        "--stdin",
        cwd=tmp_path,
        input_text=json.dumps(_handoff(scope={"modules": ["pkg/billing"], "callers": ["cmd/api"]})),
    )
    assert result.returncode == 2
    assert "candidate module" in result.stderr


def test_decision_memory_rejects_fingerprint_module_scope_contradiction(tmp_path: Path) -> None:
    memory = _load(DECISION_MEMORY, "architecture_decision_memory_scope")
    record = {
        "date": "2026-08-10",
        "outcome": "rejected",
        "fingerprint": "arch:v1:pkg/auth::Authenticate::source-knowledge",
        "memory_scope": "shared",
        "scope": {"modules": ["pkg/billing"], "callers": ["cmd/api"]},
        "decision": "Keep the current boundary.",
        "assumptions": ["The caller set is stable."],
        "alternatives": ["Keep the boundary.", "Move coordination behind the module."],
        "reopen_when": "A second external caller appears.",
        "supersedes": None,
        "evidence": ["pkg/billing/api.py"],
    }
    with pytest.raises(ValueError, match="fingerprint module"):
        memory.append_record(tmp_path, Path("docs/architecture-decisions.md"), record, MEMORY_SCHEMA)


def test_no_findings_stdin_validation_writes_nothing(tmp_path: Path) -> None:
    marker = tmp_path / "marker.txt"
    marker.write_text("unchanged\n", encoding="utf-8")
    before = _snapshot(tmp_path)
    result = _run(
        HANDOFF,
        "validate",
        "--repo-root",
        ".",
        "--stdin",
        cwd=tmp_path,
        input_text=json.dumps(_no_findings()),
    )
    assert result.returncode == 0, result.stderr
    assert _snapshot(tmp_path) == before
    assert not (tmp_path / "adr").exists()


def test_handoff_writer_rejects_symlinked_adr_root_without_touching_outside(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside-handoffs"
    outside.mkdir()
    marker = outside / "keep.txt"
    marker.write_text("safe\n", encoding="utf-8")
    (tmp_path / "adr").symlink_to(outside, target_is_directory=True)
    result = _run(
        HANDOFF,
        "write",
        "--repo-root",
        ".",
        "--handoff",
        "adr/handoffs/auth.json",
        "--stdin",
        cwd=tmp_path,
        input_text=json.dumps(_handoff()),
    )
    assert result.returncode == 2
    assert marker.read_text(encoding="utf-8") == "safe\n"
    assert sorted(path.name for path in outside.iterdir()) == ["keep.txt"]


def test_generic_writer_rejects_symlinked_allowed_root_without_touching_outside(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside-artifacts"
    outside.mkdir()
    marker = outside / "feature.md"
    marker.write_text("original\n", encoding="utf-8")
    (tmp_path / "adr").symlink_to(outside, target_is_directory=True)
    result = _run(
        ARTIFACT_WRITER,
        "write",
        "--repo-root",
        ".",
        "--allowed-root",
        "adr",
        "--path",
        "adr/feature.md",
        cwd=tmp_path,
        input_text="replacement\n",
    )
    assert result.returncode == 2
    assert marker.read_text(encoding="utf-8") == "original\n"


def test_adr_register_rejects_session_symlink_and_preserves_target(tmp_path: Path) -> None:
    adr = tmp_path / "adr" / "feature.md"
    adr.parent.mkdir()
    adr.write_text("# ADR\n", encoding="utf-8")
    outside = tmp_path.parent / f"{tmp_path.name}-session-target.json"
    outside.write_text('{"keep": true}\n', encoding="utf-8")
    (tmp_path / ".adr-session.json").symlink_to(outside)
    result = _run(
        ADR_QUERY,
        "register",
        "--repo-root",
        ".",
        "--adr",
        "adr/feature.md",
        cwd=tmp_path,
    )
    assert result.returncode != 0
    assert outside.read_text(encoding="utf-8") == '{"keep": true}\n'


def test_adr_register_interrupted_write_preserves_existing_session(tmp_path: Path, monkeypatch) -> None:
    query = _load(ADR_QUERY, "adr_query_interrupted_registration")
    adr = tmp_path / "adr" / "feature.md"
    adr.parent.mkdir()
    adr.write_text("# ADR\n", encoding="utf-8")
    session = tmp_path / ".adr-session.json"
    original = '{"keep": true}\n'
    session.write_text(original, encoding="utf-8")

    def interrupted_write(*_args, **_kwargs):
        raise OSError("simulated interruption before replace")

    monkeypatch.setattr(query, "atomic_write_text", interrupted_write)
    with pytest.raises(OSError, match="simulated interruption"):
        query.cmd_register(Namespace(repo_root=tmp_path, adr="adr/feature.md"))
    assert session.read_text(encoding="utf-8") == original


def test_adr_register_is_atomic_under_concurrency(tmp_path: Path) -> None:
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir()
    processes = []
    expected: set[tuple[str, str]] = set()
    for index in range(8):
        adr = adr_dir / f"feature-{index}.md"
        adr.write_text(f"# ADR {index}\n", encoding="utf-8")
        digest = f"sha256:{hashlib.sha256(adr.read_bytes()).hexdigest()}"
        expected.add((f"adr/feature-{index}.md", digest))
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    str(ADR_QUERY),
                    "register",
                    "--repo-root",
                    ".",
                    "--adr",
                    f"adr/feature-{index}.md",
                ],
                cwd=tmp_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )
    results = [process.communicate(timeout=20) + (process.returncode,) for process in processes]
    assert all(code == 0 for _stdout, _stderr, code in results), results
    session = json.loads((tmp_path / ".adr-session.json").read_text(encoding="utf-8"))
    assert (session["adr_path"], session["adr_hash"]) in expected


def test_adr_registration_validation_is_owned_by_adr_query(tmp_path: Path) -> None:
    adr = tmp_path / "adr" / "feature.md"
    adr.parent.mkdir()
    adr.write_text("# ADR\n", encoding="utf-8")
    registered = _run(
        ADR_QUERY,
        "register",
        "--repo-root",
        ".",
        "--adr",
        "adr/feature.md",
        cwd=tmp_path,
    )
    assert registered.returncode == 0, registered.stderr
    digest = f"sha256:{hashlib.sha256(adr.read_bytes()).hexdigest()}"
    validated = _run(
        ADR_QUERY,
        "validate-registration",
        "--repo-root",
        ".",
        "--adr",
        "adr/feature.md",
        "--hash",
        digest,
        cwd=tmp_path,
    )
    assert validated.returncode == 0, validated.stderr


def test_generic_handoff_consumer_survives_architecture_package_deletion(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    shared = tmp_path / "skills" / "shared-patterns" / "schemas"
    shared.mkdir(parents=True)
    for source in (HANDOFF, ADR_QUERY, ARTIFACT_WRITER):
        shutil.copy2(source, tmp_path / "scripts" / source.name)
    shutil.copy2(HANDOFF_SCHEMA, shared / HANDOFF_SCHEMA.name)
    result = _run(
        tmp_path / "scripts" / "handoff.py",
        "validate",
        "--repo-root",
        ".",
        "--stdin",
        cwd=tmp_path,
        input_text=json.dumps(_no_findings()),
    )
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "skills" / "research" / "architecture-deepening").exists()


def test_simple_architecture_origin_cannot_skip_feature_consultation() -> None:
    design = (REPO_ROOT / "skills/process/feature-lifecycle/references/design.md").read_text(encoding="utf-8")
    implement = (REPO_ROOT / "skills/process/feature-lifecycle/references/implement.md").read_text(encoding="utf-8")
    assert '"origin": "architecture-deepening"' in design
    assert "architecture-origin" in implement
    assert "Simple architecture-origin" in implement
    assert "If complexity is Simple, skip this gate" not in implement
