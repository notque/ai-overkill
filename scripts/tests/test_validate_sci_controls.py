"""Regression tests for the SCI fortlogs control and evidence gates."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.validate_sci_controls import (
    CONTROL_FIELD_ORDER,
    CONTROL_FIELDS,
    EXPECTED_IDS,
    EXPECTED_SOURCE_FIXTURE,
    EXPECTED_SOURCE_SHA256,
    FIELD_LABELS,
    SOURCE_FIELDS,
    STATUS_STATEMENTS,
    attestation_sha256,
    render_markdown,
    validate_catalog,
    validate_markdown,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CATALOG = REPO_ROOT / "docs" / "sci-fortlogs-security-controls.json"
MARKDOWN = REPO_ROOT / "docs" / "sci-fortlogs-security-controls.md"


def _catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def _empty_manifest() -> dict:
    return {
        "manifest_version": 1,
        "approval_policy": "Evidence is approved independently.",
        "bindings": {},
    }


def _binding(
    control: dict,
    evidence_path: Path,
    repo_root: Path,
    *,
    name: str = "test-evidence",
    status: str = "verified",
    coverage: str = "full",
    binding_ids: list[str] | None = None,
) -> tuple[str, dict]:
    binding_id = f"{control['id']}:{name}"
    complete_binding_ids = sorted(binding_ids or [binding_id])
    statement = STATUS_STATEMENTS[status]
    relative_path = evidence_path.relative_to(repo_root)
    return binding_id, {
        "control_id": control["id"],
        "repository_path": relative_path.as_posix(),
        "lines": "1",
        "claim": "The first line directly supports the test claim.",
        "coverage": coverage,
        "sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
        "attestation": {
            "control_id": control["id"],
            "status": status,
            "statement": statement,
            "binding_ids": complete_binding_ids,
        },
        "review": {
            "status": "approved",
            "approved_by": "Independent Reviewer",
            "approved_at": "2026-08-07",
            "approval_reference": "review:test-approval",
            "attestation_sha256": attestation_sha256(control["id"], status, statement, complete_binding_ids),
        },
    }


def _set_answer(control: dict, status: str, binding_ids: list[str]) -> None:
    control["answer"]["status"] = status
    control["answer"]["statement"] = STATUS_STATEMENTS[status]
    control["answer"]["evidence"] = binding_ids


def test_catalog_has_every_supplied_control_once() -> None:
    controls = _catalog()["controls"]

    assert len(controls) == 24
    assert tuple(control["id"] for control in controls) == EXPECTED_IDS
    assert len({control["id"] for control in controls}) == len(controls)


def test_every_control_has_all_twenty_fields() -> None:
    for control in _catalog()["controls"]:
        assert set(control) == CONTROL_FIELDS, control["id"]


def test_catalog_passes_all_validation_gates() -> None:
    assert validate_catalog(_catalog(), REPO_ROOT) == []


def test_catalog_rejects_top_level_schema_drift() -> None:
    data = _catalog()
    data["unreviewed"] = True

    errors = validate_catalog(data, REPO_ROOT)

    assert any(error.startswith("catalog fields must be exactly") for error in errors)


def test_catalog_rejects_evidence_policy_drift() -> None:
    data = _catalog()
    data["evidence_policy"]["as_of"] = "2099-01-01"

    errors = validate_catalog(data, REPO_ROOT)

    assert "evidence_policy must exactly match the reviewed policy" in errors


def test_unknown_answer_cannot_assert_full_compliance() -> None:
    data = _catalog()
    data["controls"][0]["answer"]["statement"] = "This control is fully implemented."

    errors = validate_catalog(data, REPO_ROOT)

    assert "E-BCD.D_SCI_fortlogs: answer.statement must match the status-derived statement" in errors


def test_markdown_renders_all_twenty_fields_for_every_control() -> None:
    rendered = render_markdown(_catalog())

    assert rendered == MARKDOWN.read_text(encoding="utf-8")
    for field in CONTROL_FIELD_ORDER[:-1]:
        assert rendered.count(f"| {FIELD_LABELS[field]} |") == 24, field
    assert rendered.count("<summary>Regulations</summary>") == 24


def test_markdown_drift_is_rejected() -> None:
    data = _catalog()
    stale_markdown = MARKDOWN.read_text(encoding="utf-8") + "\nmanual edit\n"

    assert validate_markdown(data, stale_markdown) == [
        "Markdown is stale or manually edited; regenerate it from the canonical JSON"
    ]


def test_duplicate_or_missing_control_is_rejected() -> None:
    data = _catalog()
    data["controls"][-1] = copy.deepcopy(data["controls"][0])

    errors = validate_catalog(data, REPO_ROOT)

    assert "control IDs must be unique" in errors
    assert "control IDs or domain order differ from the supplied inventory" in errors


def test_every_supplied_value_is_locked_by_control_id() -> None:
    source = json.loads(EXPECTED_SOURCE_FIXTURE.read_text(encoding="utf-8"))["controls"]
    original = _catalog()
    index_by_id = {control["id"]: index for index, control in enumerate(original["controls"])}

    for control_id, expected in source.items():
        for field in expected:
            data = copy.deepcopy(original)
            control = data["controls"][index_by_id[control_id]]
            if field == "answer":
                control["answer"]["source_note"] = "changed source answer"
            elif isinstance(control[field], bool):
                control[field] = not control[field]
            elif control[field] is None:
                control[field] = "changed"
            elif isinstance(control[field], list):
                control[field] = [*control[field], "changed"]
            else:
                control[field] = f"{control[field]} changed"

            errors = validate_catalog(data, REPO_ROOT)

            assert f"{control_id}: supplied {field} differs from the immutable source fixture" in errors


def test_source_fixture_digest_is_pinned() -> None:
    assert hashlib.sha256(EXPECTED_SOURCE_FIXTURE.read_bytes()).hexdigest() == EXPECTED_SOURCE_SHA256


@pytest.mark.parametrize("invalid_status", [["verified"], {"status": "verified"}, 1, None])
def test_non_string_answer_status_returns_validation_error(invalid_status: object) -> None:
    data = _catalog()
    data["controls"][0]["answer"]["status"] = invalid_status

    errors = validate_catalog(data, REPO_ROOT)

    assert "E-BCD.D_SCI_fortlogs: answer.status must be a string" in errors


def test_existing_file_cannot_be_used_without_approved_binding(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("unrelated existing text\n", encoding="utf-8")
    data = _catalog()
    answer = data["controls"][0]["answer"]
    answer["status"] = "verified"
    answer["statement"] = STATUS_STATEMENTS["verified"]
    answer["evidence"] = ["README.md"]

    errors = validate_catalog(data, repo, evidence_manifest=_empty_manifest())

    assert "E-BCD.D_SCI_fortlogs: answer.evidence references unapproved binding 'README.md'" in errors


def test_direct_path_evidence_objects_are_rejected(tmp_path: Path) -> None:
    data = _catalog()
    answer = data["controls"][0]["answer"]
    answer["status"] = "partial"
    answer["statement"] = STATUS_STATEMENTS["partial"]
    answer["evidence"] = [{"repository_path": "README.md", "lines": "1", "claim": "Unreviewed path"}]

    errors = validate_catalog(data, tmp_path, evidence_manifest=_empty_manifest())

    assert "E-BCD.D_SCI_fortlogs: answer.evidence must contain only non-empty binding IDs" in errors


def test_approved_checksum_bound_evidence_is_admissible(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    evidence_path = repo / "approved-evidence.md"
    evidence_path.write_text("direct fortlogs evidence\n", encoding="utf-8")
    data = _catalog()
    control = data["controls"][0]
    binding_id, binding = _binding(control, evidence_path, repo)
    manifest = _empty_manifest()
    manifest["bindings"][binding_id] = binding
    _set_answer(control, "verified", [binding_id])

    assert validate_catalog(data, repo, evidence_manifest=manifest) == []


def test_partial_binding_cannot_support_verified_answer(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    evidence_path = repo / "partial-evidence.md"
    evidence_path.write_text("one part of the control\n", encoding="utf-8")
    data = _catalog()
    control = data["controls"][0]
    binding_id, binding = _binding(control, evidence_path, repo, coverage="partial")
    manifest = _empty_manifest()
    manifest["bindings"][binding_id] = binding
    _set_answer(control, "verified", [binding_id])

    errors = validate_catalog(data, repo, evidence_manifest=manifest)

    assert "E-BCD.D_SCI_fortlogs: verified answers require full coverage from every evidence binding" in errors


def test_wrong_control_binding_cannot_support_verified_answer(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    evidence_path = repo / "other-control-evidence.md"
    evidence_path.write_text("evidence for another control\n", encoding="utf-8")
    data = _catalog()
    target = data["controls"][0]
    other = data["controls"][1]
    binding_id, binding = _binding(other, evidence_path, repo)
    manifest = _empty_manifest()
    manifest["bindings"][binding_id] = binding
    _set_answer(target, "verified", [binding_id])

    errors = validate_catalog(data, repo, evidence_manifest=manifest)

    assert f"{target['id']}: evidence binding {binding_id!r} belongs to another control" in errors


def test_answer_status_change_invalidates_approval(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    evidence_path = repo / "approved-evidence.md"
    evidence_path.write_text("direct fortlogs evidence\n", encoding="utf-8")
    data = _catalog()
    control = data["controls"][0]
    binding_id, binding = _binding(control, evidence_path, repo)
    manifest = _empty_manifest()
    manifest["bindings"][binding_id] = binding
    _set_answer(control, "partial", [binding_id])

    errors = validate_catalog(data, repo, evidence_manifest=manifest)

    assert any("approved attestation must match the exact status" in error for error in errors)


def test_answer_statement_change_invalidates_approval(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    evidence_path = repo / "approved-evidence.md"
    evidence_path.write_text("direct fortlogs evidence\n", encoding="utf-8")
    data = _catalog()
    control = data["controls"][0]
    binding_id, binding = _binding(control, evidence_path, repo)
    manifest = _empty_manifest()
    manifest["bindings"][binding_id] = binding
    _set_answer(control, "verified", [binding_id])
    control["answer"]["statement"] = "Verified with changed wording."

    errors = validate_catalog(data, repo, evidence_manifest=manifest)

    assert f"{control['id']}: answer.statement must match the status-derived statement" in errors
    assert any("approved attestation must match the exact status" in error for error in errors)


def test_answer_binding_set_change_invalidates_approval(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    first_path = repo / "first-evidence.md"
    second_path = repo / "second-evidence.md"
    first_path.write_text("first evidence\n", encoding="utf-8")
    second_path.write_text("second evidence\n", encoding="utf-8")
    data = _catalog()
    control = data["controls"][0]
    first_id = f"{control['id']}:first"
    second_id = f"{control['id']}:second"
    binding_ids = sorted([first_id, second_id])
    _, first = _binding(control, first_path, repo, name="first", binding_ids=binding_ids)
    _, second = _binding(control, second_path, repo, name="second", binding_ids=binding_ids)
    manifest = _empty_manifest()
    manifest["bindings"] = {first_id: first, second_id: second}
    _set_answer(control, "verified", [first_id])

    errors = validate_catalog(data, repo, evidence_manifest=manifest)

    assert any("approved attestation must match the exact status" in error for error in errors)


@pytest.mark.parametrize(
    ("field", "invalid_value", "expected_fragment"),
    [
        ("approved_at", "2026-8-7", "must be an ISO date"),
        ("approved_at", "not-a-date", "must be an ISO date"),
        ("approval_reference", "looks approved", "must be an HTTPS URL"),
        ("approval_reference", "http://insecure.example/review", "must be an HTTPS URL"),
        ("approval_reference", "https:///missing-host", "must be an HTTPS URL"),
        ("approval_reference", "https://", "must be an HTTPS URL"),
        ("approval_reference", "https://?approval=1", "must be an HTTPS URL"),
        ("approval_reference", "HTTPS://example.com/review", "must be an HTTPS URL"),
    ],
)
def test_approval_metadata_syntax_is_enforced(
    tmp_path: Path,
    field: str,
    invalid_value: str,
    expected_fragment: str,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    evidence_path = repo / "approved-evidence.md"
    evidence_path.write_text("direct fortlogs evidence\n", encoding="utf-8")
    data = _catalog()
    control = data["controls"][0]
    binding_id, binding = _binding(control, evidence_path, repo)
    binding["review"][field] = invalid_value
    manifest = _empty_manifest()
    manifest["bindings"][binding_id] = binding
    _set_answer(control, "verified", [binding_id])

    errors = validate_catalog(data, repo, evidence_manifest=manifest)

    assert any(expected_fragment in error for error in errors)


def test_approval_metadata_external_verification_limit_is_documented() -> None:
    manifest = json.loads((REPO_ROOT / "docs" / "sci-fortlogs-evidence-manifest.json").read_text(encoding="utf-8"))
    rendered = render_markdown(_catalog())

    assert "not externally verified" in manifest["approval_policy"]
    assert "not externally verified" in rendered


def test_https_approval_reference_with_hostname_is_accepted(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    evidence_path = repo / "approved-evidence.md"
    evidence_path.write_text("direct fortlogs evidence\n", encoding="utf-8")
    data = _catalog()
    control = data["controls"][0]
    binding_id, binding = _binding(control, evidence_path, repo)
    binding["review"]["approval_reference"] = "https://review.example.test/approvals/123"
    manifest = _empty_manifest()
    manifest["bindings"][binding_id] = binding
    _set_answer(control, "verified", [binding_id])

    assert validate_catalog(data, repo, evidence_manifest=manifest) == []


def test_evidence_checksum_drift_is_rejected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    evidence_path = repo / "approved-evidence.md"
    evidence_path.write_text("direct fortlogs evidence\n", encoding="utf-8")
    data = _catalog()
    control = data["controls"][0]
    binding_id, binding = _binding(control, evidence_path, repo)
    binding["sha256"] = "0" * 64
    manifest = _empty_manifest()
    manifest["bindings"][binding_id] = binding
    _set_answer(control, "verified", [binding_id])

    errors = validate_catalog(data, repo, evidence_manifest=manifest)

    assert any("sha256 does not match" in error for error in errors)
    assert any("references unapproved binding" in error for error in errors)


def test_control_owner_cannot_approve_own_evidence(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    evidence_path = repo / "approved-evidence.md"
    evidence_path.write_text("direct fortlogs evidence\n", encoding="utf-8")
    data = _catalog()
    control = data["controls"][0]
    binding_id, binding = _binding(control, evidence_path, repo)
    binding["review"]["approved_by"] = f" {control['owner'].upper()} "
    manifest = _empty_manifest()
    manifest["bindings"][binding_id] = binding
    _set_answer(control, "verified", [binding_id])

    errors = validate_catalog(data, repo, evidence_manifest=manifest)

    assert any("must be approved by someone other than the control owner" in error for error in errors)


def test_symlink_escape_outside_repository_is_rejected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside-evidence.md"
    outside.write_text("outside repository\n", encoding="utf-8")
    symlink = repo / "escaped-evidence.md"
    symlink.symlink_to(outside)
    data = _catalog()
    control = data["controls"][0]
    binding_id, binding = _binding(control, symlink, repo, status="partial", coverage="partial")
    manifest = _empty_manifest()
    manifest["bindings"][binding_id] = binding
    _set_answer(control, "partial", [binding_id])

    errors = validate_catalog(data, repo, evidence_manifest=manifest)

    assert any("repository_path resolves outside the repository" in error for error in errors)
    assert any("references unapproved binding" in error for error in errors)
