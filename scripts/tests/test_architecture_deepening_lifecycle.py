"""Structural and runtime guards for architecture-deepening lifecycle enrichment."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

jsonschema = pytest.importorskip("jsonschema", exc_type=ImportError)

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL = REPO_ROOT / "skills" / "research" / "architecture-deepening" / "SKILL.md"
LIFECYCLE = SKILL.parent / "references" / "maintenance-lifecycle.md"
DO_SKILL = REPO_ROOT / "skills" / "meta" / "do" / "SKILL.md"
PRE_ROUTE = REPO_ROOT / "scripts" / "pre-route.py"
HANDOFF_SCHEMA = REPO_ROOT / "skills" / "shared-patterns" / "schemas" / "architecture-change-handoff.schema.json"
MEMORY_SCHEMA = SKILL.parent / "references" / "decision-memory-record.schema.json"
DECISION_MEMORY = SKILL.parent / "scripts" / "decision_memory.py"
HANDOFF = REPO_ROOT / "scripts" / "handoff.py"
SKILL_INDEX = REPO_ROOT / "skills" / "INDEX.json"
PIPELINE_INDEX = REPO_ROOT / "skills" / "workflow" / "references" / "pipeline-index.json"


def _load_decision_memory():
    sys.path.insert(0, str(DECISION_MEMORY.parent))
    spec = importlib.util.spec_from_file_location("architecture_decision_memory", DECISION_MEMORY)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_handoff():
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("neutral_handoff", HANDOFF)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _handoff(**overrides) -> dict:
    handoff = {
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
    handoff.update(overrides)
    return handoff


def _frontmatter() -> dict:
    text = SKILL.read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---", 2)[1])


def _pre_route(request: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(PRE_ROUTE), "--request", request, "--json-compact"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_architecture_deepening_remains_semantic_only() -> None:
    frontmatter = _frontmatter()
    routing = frontmatter["routing"]
    assert "force_route" not in routing
    assert frontmatter["command"] == "architecture-deepening"
    assert frontmatter["description"] == "Improve architecture across modules by deepening interfaces."
    assert {
        "improve architecture",
        "improve codebase architecture",
        "improve the codebase architecture",
        "find architecture improvements",
    } <= set(routing["triggers"])
    assert "reduce complexity" not in routing["triggers"]
    assert "reduce caller coordination" not in routing["triggers"]
    for boundary in ("vague complexity", "local cleanup", "feature design", "overview/explanation"):
        assert boundary in routing["not_for"]
    assert {"Write", "Edit"}.issubset(frontmatter["allowed-tools"])


def test_architecture_and_local_cleanup_both_fall_through_pre_route() -> None:
    for request in (
        "Improve architecture",
        "Improve codebase architecture",
        "Improve the codebase architecture",
        "Find architecture improvements",
        "Callers coordinate cache state and retries across three packages; simplify that boundary.",
        "Reduce cyclomatic complexity in this one function without changing behavior.",
    ):
        result = _pre_route(request)
        assert result["matched"] is False
        assert result["match_type"] == "fallthrough"


def test_lifecycle_contract_has_required_states_and_handoffs() -> None:
    text = LIFECYCLE.read_text(encoding="utf-8")
    for required in (
        "## Safe Entry Moments",
        "## Scope and Recent-Change Bias",
        "## Prior-Decision Read",
        "## No-Findings Result",
        "## Durable Decision Memory",
        "## Terminal States",
        "## Architecture Change Handoff",
        "behavior-preserving-refactor",
        "interface-migration",
        "next_skill",
        "next_pipeline",
        "systematic-refactoring",
        "feature-lifecycle",
    ):
        assert required in text


def test_do_reverts_unproven_explicit_route_and_automatic_stacking() -> None:
    text = DO_SKILL.read_text(encoding="utf-8")
    assert "cross module interface or caller coordination improvement→architecture-deepening" not in text
    assert "Stack `architecture-deepening` after the evidence source" not in text
    assert "Architecture-deepening remains an explicit semantic route" not in text


def test_handoff_schema_is_valid_and_accepts_each_successor() -> None:
    schema = json.loads(HANDOFF_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)

    cases = (
        _handoff(),
        _handoff(
            change_class="interface-migration",
            decision_artifact="docs/architecture-decisions.md",
            decision_scope="shared",
            success_criteria=[
                "Migrate both callers to the new interface.",
                "Keep a compatibility adapter until all callers move.",
                "Pass old and new contract tests during migration.",
            ],
            next_skill="feature-lifecycle",
            next_pipeline=None,
        ),
        _handoff(
            change_class="new-behavior",
            success_criteria=[
                "Expose the approved operation to callers.",
                "Keep existing behavior unchanged.",
                "Pass rollout and rollback checks.",
            ],
            next_skill="feature-lifecycle",
            next_pipeline=None,
        ),
        _handoff(
            result="rejected",
            change_class="close",
            decision_artifact="docs/architecture-decisions.md",
            decision_scope="shared",
            proposed_interface=None,
            migration=None,
            success_criteria=[],
            current_interface=None,
            next_skill=None,
            next_pipeline=None,
        ),
        _handoff(
            result="deferred",
            change_class="close",
            proposed_interface=None,
            migration=None,
            success_criteria=[],
            current_interface=None,
            next_skill=None,
            next_pipeline=None,
        ),
        _handoff(
            result="no-change",
            change_class="close",
            decision_artifact="docs/architecture-decisions.md",
            decision_scope="shared",
            proposed_interface=None,
            migration=None,
            success_criteria=[],
            next_skill=None,
            next_pipeline=None,
        ),
        _handoff(
            result="no-findings",
            candidate=None,
            change_class="close",
            current_interface=None,
            proposed_interface=None,
            migration=None,
            success_criteria=[],
            next_skill=None,
            next_pipeline=None,
        ),
    )
    for case in cases:
        validator.validate(case)


def test_handoff_successors_are_registered_skill_and_pipeline_names() -> None:
    skills = json.loads(SKILL_INDEX.read_text(encoding="utf-8"))["skills"]
    skill_names = set(skills)
    pipelines = json.loads(PIPELINE_INDEX.read_text(encoding="utf-8"))["pipelines"]
    assert {"workflow", "feature-lifecycle"} <= skill_names
    assert "systematic-refactoring" in pipelines


@pytest.mark.parametrize(
    "handoff",
    (
        _handoff(result="no-findings", candidate=None, change_class="interface-migration"),
        _handoff(change_class="close", next_skill=None, next_pipeline=None),
        _handoff(change_class="interface-migration", next_skill="workflow"),
        _handoff(decision_artifact=".local/architecture-decisions.md", decision_scope=None),
        _handoff(candidate="auth-interface"),
        _handoff(risk="medium"),
        _handoff(change_class="interface-migration", next_skill="feature-lifecycle", next_pipeline=None),
        _handoff(candidate="arch:v1:pkg//auth::Authenticate::duplicated-coordination"),
        _handoff(candidate="arch:v1:pkg%ZZ/auth::Authenticate::duplicated-coordination"),
        _handoff(decision_artifact="docs/architecture-decisions.md", decision_scope="local"),
        _handoff(decision_artifact=".local/architecture-decisions.md", decision_scope="shared"),
        _handoff(
            consultation_adr="adr/unneeded.md",
            consultation_adr_hash="sha256:" + "a" * 64,
        ),
        _handoff(
            result="no-change",
            change_class="close",
            proposed_interface=None,
            migration=None,
            success_criteria=[],
            consultation_adr="adr/unneeded.md",
            consultation_adr_hash="sha256:" + "a" * 64,
            next_skill=None,
            next_pipeline=None,
        ),
    ),
)
def test_handoff_schema_rejects_invalid_terminal_or_successor(handoff: dict) -> None:
    schema = json.loads(HANDOFF_SCHEMA.read_text(encoding="utf-8"))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(handoff, schema)


def test_decision_memory_round_trip_uses_canonical_exact_latest_entry(tmp_path: Path) -> None:
    memory = _load_decision_memory()
    fingerprint = memory.canonical_fingerprint("pkg/auth", "Authenticate", "duplicated-coordination")
    assert fingerprint == "arch:v1:pkg/auth::Authenticate::duplicated-coordination"

    store = tmp_path / "architecture-decisions.md"
    store.write_text(
        "# Decisions\n\n"
        "## 2026-08-01: first\n\n"
        f"- Fingerprint: {fingerprint}\n"
        "- Outcome: rejected\n"
        "- Decision: first decision\n\n"
        "## 2026-08-10: reconsidered\n\n"
        f"- Fingerprint: {fingerprint}\n"
        f"- Supersedes: 2026-08-01 and {fingerprint}\n"
        "- Outcome: selected\n"
        "- Decision: latest decision\n",
        encoding="utf-8",
    )

    latest = memory.find_latest(store, fingerprint)
    assert latest is not None
    assert "latest decision" in latest
    assert "first decision" not in latest


def test_decision_memory_rejects_unsafe_or_noncanonical_inputs() -> None:
    memory = _load_decision_memory()
    canonical = memory.canonical_fingerprint("pkg/auth", "Authenticate", "source-knowledge")
    assert memory.is_canonical_fingerprint(canonical)
    for invalid in (
        "arch:v1:pkg//auth::Authenticate::duplicated-coordination",
        "arch:v1:pkg%ZZ/auth::Authenticate::duplicated-coordination",
        "arch:v1:pkg%2Fauth::Authenticate::duplicated-coordination",
    ):
        assert not memory.is_canonical_fingerprint(invalid)
    with pytest.raises(ValueError):
        memory.canonical_fingerprint("../outside", "Public", "source-knowledge")
    with pytest.raises(ValueError):
        memory.canonical_fingerprint("pkg/auth", "", "source-knowledge")
    with pytest.raises(ValueError):
        memory.canonical_fingerprint("pkg/auth", "Public", "unstable-label")
    with pytest.raises(ValueError):
        memory.canonical_fingerprint("pkg/áuth", "Public", "source-knowledge")


@pytest.mark.parametrize(
    "field,value",
    (
        ("module", "/tmp/pwn"),
        ("module", "../outside"),
        ("module", "pkg/../../outside"),
        ("module", "pkg/auth;touch-pwn"),
        ("module", "pkg/auth$(id)"),
        ("module", "pkg/auth\nnext"),
        ("caller", "cmd/api|tee-pwn"),
        ("caller", "`touch-pwn`"),
        ("artifact", "/docs/architecture-decisions.md"),
        ("artifact", "docs/../outside.md"),
        ("artifact", "pyproject.toml"),
        ("adr", "adr/auth;touch-pwn.md"),
        ("adr", "../adr/auth.md"),
    ),
)
def test_handoff_schema_rejects_malicious_action_paths(field: str, value: str) -> None:
    handoff = _handoff()
    if field == "module":
        handoff["scope"]["modules"] = [value]
    elif field == "caller":
        handoff["scope"]["callers"] = [value]
    elif field == "artifact":
        handoff["decision_artifact"] = value
        handoff["decision_scope"] = "shared"
    else:
        handoff["risk"] = "medium"
        handoff["consultation_adr"] = value
        handoff["consultation_adr_hash"] = "sha256:" + "a" * 64

    schema = json.loads(HANDOFF_SCHEMA.read_text(encoding="utf-8"))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(handoff, schema)


@pytest.mark.parametrize(
    "overrides",
    (
        {"scope": {"modules": [], "callers": ["cmd/api"]}},
        {"scope": {"modules": ["pkg/auth"], "callers": []}},
        {"current_interface": ""},
        {"proposed_interface": None},
        {"proposed_interface": ""},
        {"migration": None},
        {"migration": ""},
        {"success_criteria": []},
        {"success_criteria": ["Only one check."]},
    ),
)
def test_selected_handoff_requires_actionable_design_data(overrides: dict) -> None:
    schema = json.loads(HANDOFF_SCHEMA.read_text(encoding="utf-8"))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_handoff(**overrides), schema)


@pytest.mark.parametrize(
    "handoff",
    (
        _handoff(
            result="no-findings",
            candidate=None,
            change_class="close",
            current_interface=None,
            proposed_interface=None,
            migration=None,
            success_criteria=[],
            decision_artifact="docs/architecture-decisions.md",
            decision_scope="shared",
            next_skill=None,
            next_pipeline=None,
        ),
        _handoff(
            result="no-findings",
            candidate=None,
            change_class="close",
            current_interface=None,
            proposed_interface=None,
            migration=None,
            success_criteria=[],
            risk="medium",
            next_skill=None,
            next_pipeline=None,
        ),
        _handoff(
            result="rejected",
            change_class="close",
            current_interface=None,
            proposed_interface="unused proposal",
            migration=None,
            success_criteria=[],
            next_skill=None,
            next_pipeline=None,
        ),
        _handoff(
            result="deferred",
            change_class="close",
            current_interface=None,
            proposed_interface=None,
            migration=None,
            success_criteria=["must be empty"],
            next_skill=None,
            next_pipeline=None,
        ),
        _handoff(
            result="no-change",
            change_class="close",
            proposed_interface=None,
            migration=None,
            success_criteria=[],
            risk="high",
            next_skill=None,
            next_pipeline=None,
        ),
    ),
)
def test_handoff_schema_rejects_invalid_result_specific_artifacts(handoff: dict) -> None:
    schema = json.loads(HANDOFF_SCHEMA.read_text(encoding="utf-8"))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(handoff, schema)


def test_high_risk_no_change_requires_registered_adr_fields() -> None:
    schema = json.loads(HANDOFF_SCHEMA.read_text(encoding="utf-8"))
    handoff = _handoff(
        result="no-change",
        change_class="close",
        proposed_interface=None,
        migration=None,
        success_criteria=[],
        risk="high",
        consultation_adr="adr/auth-interface.md",
        consultation_adr_hash="sha256:" + "a" * 64,
        next_skill=None,
        next_pipeline=None,
    )
    jsonschema.validate(handoff, schema)


def _memory_record(index: int = 1, *, scope: str = "shared") -> dict:
    return {
        "date": "2026-08-10",
        "outcome": "rejected",
        "fingerprint": f"arch:v1:pkg/module{index}::Public{index}::source-knowledge",
        "memory_scope": scope,
        "scope": {"modules": [f"pkg/module{index}"], "callers": [f"cmd/caller{index}"]},
        "decision": f"Keep the current boundary for candidate {index}.",
        "assumptions": ["The caller set is stable."],
        "alternatives": ["Keep the boundary.", "Move coordination behind the module."],
        "reopen_when": "A second external caller appears.",
        "supersedes": None,
        "evidence": [f"pkg/module{index}/api.py", f"cmd/caller{index}/main.py"],
    }


def test_decision_memory_schema_and_append_persist_scope(tmp_path: Path) -> None:
    memory = _load_decision_memory()
    schema = json.loads(MEMORY_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    record = _memory_record()
    memory.append_record(tmp_path, Path("docs/architecture-decisions.md"), record, MEMORY_SCHEMA)

    content = (tmp_path / "docs" / "architecture-decisions.md").read_text(encoding="utf-8")
    assert "- Memory scope: shared" in content
    assert record["fingerprint"] in content


def test_decision_memory_append_rejects_invalid_record_and_store(tmp_path: Path) -> None:
    memory = _load_decision_memory()
    invalid = _memory_record()
    invalid["alternatives"] = []
    with pytest.raises(ValueError):
        memory.append_record(tmp_path, Path("docs/architecture-decisions.md"), invalid, MEMORY_SCHEMA)
    with pytest.raises(ValueError):
        memory.append_record(tmp_path, Path("../outside.md"), _memory_record(), MEMORY_SCHEMA)
    with pytest.raises(ValueError):
        memory.append_record(
            tmp_path,
            Path("docs/architecture-decisions.md"),
            _memory_record(scope="local"),
            MEMORY_SCHEMA,
        )


def test_decision_memory_concurrent_appends_do_not_lose_records(tmp_path: Path) -> None:
    records_dir = tmp_path / "records"
    records_dir.mkdir()
    processes = []
    for index in range(8):
        record_path = records_dir / f"{index}.json"
        record_path.write_text(json.dumps(_memory_record(index)), encoding="utf-8")
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    str(DECISION_MEMORY),
                    "append",
                    "--repo-root",
                    ".",
                    "--store",
                    "docs/architecture-decisions.md",
                    "--record",
                    f"records/{index}.json",
                ],
                cwd=tmp_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )

    results = [process.communicate(timeout=20) + (process.returncode,) for process in processes]
    assert all(code == 0 for _stdout, _stderr, code in results), results
    content = (tmp_path / "docs" / "architecture-decisions.md").read_text(encoding="utf-8")
    for index in range(8):
        assert _memory_record(index)["fingerprint"] in content


def test_decision_memory_interrupted_replace_preserves_existing_store(tmp_path: Path, monkeypatch) -> None:
    memory = _load_decision_memory()
    store = tmp_path / "docs" / "architecture-decisions.md"
    store.parent.mkdir()
    original = "# Architecture Decisions\n\nexisting\n"
    store.write_text(original, encoding="utf-8")

    def interrupted_replace(_source, _destination, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(os, "replace", interrupted_replace)
    with pytest.raises(KeyboardInterrupt):
        memory.append_record(tmp_path, Path("docs/architecture-decisions.md"), _memory_record(), MEMORY_SCHEMA)
    assert store.read_text(encoding="utf-8") == original
    assert not list(store.parent.glob(".architecture-decisions.md.*.tmp"))


@pytest.mark.parametrize("symlink_component", ("store", "parent"))
def test_decision_memory_append_rejects_symlinked_store_paths(tmp_path: Path, symlink_component: str) -> None:
    memory = _load_decision_memory()
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    redirected = scripts / "run.sh"
    original = "#!/bin/sh\necho safe\n"
    redirected.write_text(original, encoding="utf-8")
    docs = tmp_path / "docs"
    if symlink_component == "store":
        docs.mkdir()
        (docs / "architecture-decisions.md").symlink_to(redirected)
    else:
        docs.symlink_to(scripts, target_is_directory=True)

    with pytest.raises(ValueError, match="symbolic link"):
        memory.append_record(
            tmp_path,
            Path("docs/architecture-decisions.md"),
            _memory_record(),
            MEMORY_SCHEMA,
        )
    assert redirected.read_text(encoding="utf-8") == original


def test_handoff_consumer_resolves_paths_and_rejects_symlink_escape(tmp_path: Path) -> None:
    handoff = _load_handoff()
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (tmp_path / "pkg").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        handoff.validate_handoff(_handoff(), tmp_path, HANDOFF_SCHEMA)


def test_handoff_consumer_rejects_symlinked_decision_artifact(tmp_path: Path) -> None:
    validator = _load_handoff()
    docs = tmp_path / "docs"
    scripts = tmp_path / "scripts"
    docs.mkdir()
    scripts.mkdir()
    redirected = scripts / "run.sh"
    redirected.write_text("#!/bin/sh\necho safe\n", encoding="utf-8")
    (docs / "architecture-decisions.md").symlink_to(redirected)
    handoff = _handoff(
        decision_artifact="docs/architecture-decisions.md",
        decision_scope="shared",
    )

    with pytest.raises(ValueError, match="symbolic link"):
        validator.validate_handoff(handoff, tmp_path, HANDOFF_SCHEMA)


def test_handoff_consumer_requires_matching_registered_consultation_adr(tmp_path: Path) -> None:
    validator = _load_handoff()
    adr = tmp_path / "adr" / "auth-interface.md"
    adr.parent.mkdir()
    adr.write_text("# ADR\n", encoding="utf-8")
    digest = f"sha256:{hashlib.sha256(adr.read_bytes()).hexdigest()}"
    session = {"adr_path": "adr/auth-interface.md", "adr_hash": digest}
    (tmp_path / ".adr-session.json").write_text(json.dumps(session), encoding="utf-8")
    handoff = _handoff(
        result="no-change",
        change_class="close",
        proposed_interface=None,
        migration=None,
        success_criteria=[],
        risk="high",
        consultation_adr="adr/auth-interface.md",
        consultation_adr_hash=digest,
        next_skill=None,
        next_pipeline=None,
    )
    validator.validate_handoff(handoff, tmp_path, HANDOFF_SCHEMA)

    session["adr_path"] = "adr/other.md"
    (tmp_path / ".adr-session.json").write_text(json.dumps(session), encoding="utf-8")
    with pytest.raises(ValueError):
        validator.validate_handoff(handoff, tmp_path, HANDOFF_SCHEMA)


def test_handoff_consumer_rejects_consultation_adr_symlink_escape(tmp_path: Path) -> None:
    validator = _load_handoff()
    adr_dir = tmp_path / "adr"
    docs_dir = tmp_path / "docs"
    adr_dir.mkdir()
    docs_dir.mkdir()
    redirected = docs_dir / "other.md"
    redirected.write_text("# Not an ADR\n", encoding="utf-8")
    adr = adr_dir / "link.md"
    adr.symlink_to(redirected)
    digest = f"sha256:{hashlib.sha256(redirected.read_bytes()).hexdigest()}"
    (tmp_path / ".adr-session.json").write_text(
        json.dumps({"adr_path": "adr/link.md", "adr_hash": digest}), encoding="utf-8"
    )
    handoff = _handoff(
        result="no-change",
        change_class="close",
        proposed_interface=None,
        migration=None,
        success_criteria=[],
        risk="high",
        consultation_adr="adr/link.md",
        consultation_adr_hash=digest,
        next_skill=None,
        next_pipeline=None,
    )

    with pytest.raises(ValueError, match="symbolic link"):
        validator.validate_handoff(handoff, tmp_path, HANDOFF_SCHEMA)


def test_handoff_consumer_rejects_symlinked_or_malformed_session_registry(tmp_path: Path) -> None:
    validator = _load_handoff()
    adr = tmp_path / "adr" / "auth-interface.md"
    adr.parent.mkdir()
    adr.write_text("# ADR\n", encoding="utf-8")
    digest = f"sha256:{hashlib.sha256(adr.read_bytes()).hexdigest()}"
    handoff = _handoff(
        result="no-change",
        change_class="close",
        proposed_interface=None,
        migration=None,
        success_criteria=[],
        risk="high",
        consultation_adr="adr/auth-interface.md",
        consultation_adr_hash=digest,
        next_skill=None,
        next_pipeline=None,
    )
    redirected = tmp_path / "registry.json"
    redirected.write_text(json.dumps({"adr_path": "adr/auth-interface.md", "adr_hash": digest}), encoding="utf-8")
    session = tmp_path / ".adr-session.json"
    session.symlink_to(redirected)
    with pytest.raises(ValueError, match="symbolic link"):
        validator.validate_handoff(handoff, tmp_path, HANDOFF_SCHEMA)

    session.unlink()
    session.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        validator.validate_handoff(handoff, tmp_path, HANDOFF_SCHEMA)


def test_feature_lifecycle_adopts_handoff_and_defers_consultation_to_implement_gate() -> None:
    design = (REPO_ROOT / "skills/process/feature-lifecycle/references/design.md").read_text(encoding="utf-8")
    implement = (REPO_ROOT / "skills/process/feature-lifecycle/references/implement.md").read_text(encoding="utf-8")
    architecture = SKILL.read_text(encoding="utf-8")
    assert "scripts/handoff.py validate" in design
    assert "Architecture Change Handoff" in design
    assert "adr-query.py register" in design
    assert "adr-query.py validate-registration" in implement
    assert "Run `adr-consultation` before `feature-lifecycle`" not in architecture
    assert "pre-IMPLEMENT consultation gate" in architecture
