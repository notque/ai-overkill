#!/usr/bin/env python3
"""Validate the SCI fortlogs catalog, source fixture, evidence, and Markdown."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = REPO_ROOT / "docs" / "sci-fortlogs-security-controls.json"
DEFAULT_MARKDOWN = REPO_ROOT / "docs" / "sci-fortlogs-security-controls.md"
DEFAULT_MANIFEST = REPO_ROOT / "docs" / "sci-fortlogs-evidence-manifest.json"
EXPECTED_SOURCE_FIXTURE = REPO_ROOT / "scripts" / "data" / "sci_fortlogs_expected_source.json"
EXPECTED_SOURCE_SHA256 = "06bde85f4424a28c867bb4f631b2fe8c93e5aca61ff37344beb7562e5a0dc7c9"

EXPECTED_IDS = (
    "E-BCD.D_SCI_fortlogs",
    "E-BCD.E_SCI_fortlogs",
    "E-BCD.F_SCI_fortlogs",
    "E-BCD.J_SCI_fortlogs",
    "E-CM01_SCI_fortlogs",
    "E-CM02_SCI_fortlogs",
    "E-CM03_SCI_fortlogs",
    "E-CM05_BTP_SCI_fortlogs",
    "E-SA02_SCI_fortlogs",
    "E-SA03_SCI_fortlogs",
    "E-SA04_SCI_fortlogs",
    "E-SA05_SCI_fortlogs",
    "E-SEM01_Conv",
    "E-SEM02_CCS",
    "E-SEM03_CCS",
    "E-SEM04_SCI",
    "E-SEM04_SCI_INT_fortlogs",
    "E-SEM06_SCI_fortlogs",
    "E-SPM01_SCI_fortlogs",
    "E-SPM02_SCI_fortlogs",
    "E-SM03_SCI",
    "E-UAM01_SCI_fortlogs",
    "E-UAM02_SCI_fortlogs",
    "E-UAM03_CCS_SCI_fortlogs",
)

CONTROL_FIELD_ORDER = (
    "id",
    "name",
    "description",
    "answer",
    "domain",
    "shared",
    "provider",
    "owner",
    "delegates",
    "frequency",
    "automation",
    "purpose",
    "draft",
    "internal",
    "control_design",
    "organization",
    "valid_from",
    "valid_to",
    "labels",
    "regulations",
)
CONTROL_FIELDS = set(CONTROL_FIELD_ORDER)
CATALOG_FIELDS = {"catalog", "evidence_policy", "controls"}
SOURCE_FIELDS = set(CONTROL_FIELD_ORDER) - {"id"}
ANSWER_FIELDS = {"status", "statement", "source_note", "evidence", "missing_evidence"}
VALID_STATUSES = {"verified", "partial", "unknown", "not_applicable"}
STATUS_STATEMENTS = {
    "verified": "Verified by approved repository evidence.",
    "partial": "Partially evidenced by approved repository evidence.",
    "unknown": "Not evidenced in this repository.",
    "not_applicable": "Not applicable based on approved scope evidence.",
}
EXPECTED_EVIDENCE_POLICY = {
    "as_of": "2026-08-07",
    "repository": "notque/vexjoy-agent",
    "status_definitions": STATUS_STATEMENTS,
    "confidence_notes": (
        "Green and yellow source annotations are preserved as source_note values. "
        "They are confidence notes, not evidence."
    ),
    "evidence_bindings": (
        "Evidence-backed answers require approved manifest bindings whose attestations cover the exact "
        "control ID, status, statement, and complete binding-ID set."
    ),
    "regulations": (
        "The source stated that regulations were collapsed but did not supply their values; "
        "null preserves that omission."
    ),
}
STRING_FIELDS = CONTROL_FIELDS - {
    "answer",
    "shared",
    "delegates",
    "draft",
    "internal",
    "regulations",
}
FIELD_LABELS = {
    "id": "ID",
    "name": "Name",
    "description": "Description",
    "answer": "Answer",
    "domain": "Domain",
    "shared": "Shared",
    "provider": "Provider",
    "owner": "Owner",
    "delegates": "Delegates",
    "frequency": "Frequency",
    "automation": "Automation",
    "purpose": "Purpose",
    "draft": "Draft",
    "internal": "Internal",
    "control_design": "Control Design",
    "organization": "Organization",
    "valid_from": "Valid from",
    "valid_to": "Valid to",
    "labels": "Labels",
    "regulations": "Regulations",
}
MANIFEST_FIELDS = {"manifest_version", "approval_policy", "bindings"}
BINDING_FIELDS = {
    "control_id",
    "repository_path",
    "lines",
    "claim",
    "coverage",
    "sha256",
    "attestation",
    "review",
}
ATTESTATION_FIELDS = {"control_id", "status", "statement", "binding_ids"}
REVIEW_FIELDS = {"status", "approved_by", "approved_at", "approval_reference", "attestation_sha256"}
VALID_COVERAGE = {"full", "partial", "not_applicable"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
LOCAL_APPROVAL_REFERENCE = re.compile(r"^(?:review|ticket|pr):[A-Za-z0-9][A-Za-z0-9._/#-]*$")


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def attestation_sha256(control_id: str, status: str, statement: str, binding_ids: list[str]) -> str:
    """Digest the complete answer attestation with binding IDs in set order."""
    payload = {
        "binding_ids": sorted(binding_ids),
        "control_id": control_id,
        "statement": statement,
        "status": status,
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _valid_approval_date(value: Any) -> bool:
    if not _nonempty_string(value):
        return False
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return parsed.isoformat() == value


def _valid_approval_reference(value: Any) -> bool:
    if not _nonempty_string(value) or any(character.isspace() for character in value):
        return False
    if LOCAL_APPROVAL_REFERENCE.fullmatch(value):
        return True
    if not value.startswith("https://"):
        return False
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
    except ValueError:
        return False
    return parsed.scheme == "https" and bool(hostname)


def _load_json(path: Path, label: str) -> tuple[Any | None, list[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, [f"{label} invalid: {exc}"]


def _load_expected_source() -> tuple[Any | None, list[str]]:
    try:
        raw = EXPECTED_SOURCE_FIXTURE.read_bytes()
    except OSError as exc:
        return None, [f"expected source fixture invalid: {exc}"]
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_SOURCE_SHA256:
        return None, [
            "expected source fixture digest changed; source updates require explicit fixture and digest review"
        ]
    try:
        return json.loads(raw), []
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, [f"expected source fixture invalid: {exc}"]


def _parse_line_range(line_spec: Any, prefix: str) -> tuple[tuple[int, int] | None, list[str]]:
    if not _nonempty_string(line_spec):
        return None, [f"{prefix}.lines must be a positive line or range"]
    start_text, separator, end_text = line_spec.partition("-")
    try:
        start = int(start_text)
        end = int(end_text) if separator else start
    except ValueError:
        return None, [f"{prefix}.lines must be a positive line or range"]
    if start < 1 or end < start:
        return None, [f"{prefix}.lines must be a positive ascending line or range"]
    return (start, end), []


def _resolve_evidence_file(repo_root: Path, repository_path: Any, prefix: str) -> tuple[Path | None, list[str]]:
    if not _nonempty_string(repository_path):
        return None, [f"{prefix}.repository_path must be a non-empty string"]
    relative_path = Path(repository_path)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        return None, [f"{prefix}.repository_path must be a repository-relative path"]
    try:
        resolved_root = repo_root.resolve(strict=True)
        resolved_path = (resolved_root / relative_path).resolve(strict=True)
    except OSError as exc:
        return None, [f"{prefix}.repository_path cannot be resolved: {exc}"]
    if not resolved_path.is_relative_to(resolved_root):
        return None, [f"{prefix}.repository_path resolves outside the repository"]
    if not resolved_path.is_file():
        return None, [f"{prefix}.repository_path is not a file: {relative_path}"]
    return resolved_path, []


def _validate_source_fixture(data: dict[str, Any], expected_source: Any) -> list[str]:
    if not isinstance(expected_source, dict) or set(expected_source) != {"fixture_version", "controls"}:
        return ["expected source fixture must contain exactly fixture_version and controls"]
    if expected_source["fixture_version"] != 1:
        return ["expected source fixture version must be 1"]
    expected_controls = expected_source["controls"]
    if not isinstance(expected_controls, dict):
        return ["expected source fixture controls must be keyed by control ID"]
    errors: list[str] = []
    if tuple(expected_controls) != EXPECTED_IDS:
        errors.append("expected source fixture IDs or order differ from the supplied inventory")

    actual_controls = {
        control.get("id"): control
        for control in data.get("controls", [])
        if isinstance(control, dict) and isinstance(control.get("id"), str)
    }
    for control_id, expected in expected_controls.items():
        prefix = f"{control_id}: expected source"
        if not isinstance(expected, dict) or set(expected) != SOURCE_FIELDS:
            errors.append(f"{prefix} fields must be exactly {sorted(SOURCE_FIELDS)}")
            continue
        actual = actual_controls.get(control_id)
        if actual is None or set(actual) != CONTROL_FIELDS:
            continue
        for field, expected_value in expected.items():
            if field == "answer":
                answer = actual["answer"]
                actual_value = answer.get("source_note") if isinstance(answer, dict) else None
            else:
                actual_value = actual[field]
            if actual_value != expected_value:
                errors.append(f"{control_id}: supplied {field} differs from the immutable source fixture")
    return errors


def _validate_manifest(
    manifest: Any,
    controls_by_id: dict[str, dict[str, Any]],
    repo_root: Path,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_FIELDS:
        return {}, [f"evidence manifest fields must be exactly {sorted(MANIFEST_FIELDS)}"]
    if manifest["manifest_version"] != 1:
        return {}, ["evidence manifest version must be 1"]
    if not _nonempty_string(manifest["approval_policy"]):
        return {}, ["evidence manifest approval_policy must be a non-empty string"]
    bindings = manifest["bindings"]
    if not isinstance(bindings, dict):
        return {}, ["evidence manifest bindings must be keyed by binding ID"]

    errors: list[str] = []
    admissible: dict[str, dict[str, Any]] = {}
    for binding_id, binding in bindings.items():
        prefix = f"evidence binding {binding_id!r}"
        if not _nonempty_string(binding_id):
            errors.append("evidence binding IDs must be non-empty strings")
            continue
        if not isinstance(binding, dict) or set(binding) != BINDING_FIELDS:
            errors.append(f"{prefix} fields must be exactly {sorted(BINDING_FIELDS)}")
            continue
        control_id = binding["control_id"]
        if not isinstance(control_id, str) or control_id not in controls_by_id:
            errors.append(f"{prefix}.control_id is not in the catalog: {control_id!r}")
            continue
        if not _nonempty_string(binding["claim"]):
            errors.append(f"{prefix}.claim must be a non-empty string")
        if not isinstance(binding["coverage"], str) or binding["coverage"] not in VALID_COVERAGE:
            errors.append(f"{prefix}.coverage must be one of {sorted(VALID_COVERAGE)}")
        if not isinstance(binding["sha256"], str) or not SHA256.fullmatch(binding["sha256"]):
            errors.append(f"{prefix}.sha256 must be a lowercase SHA-256 digest")

        computed_attestation: str | None = None
        attestation = binding["attestation"]
        if not isinstance(attestation, dict) or set(attestation) != ATTESTATION_FIELDS:
            errors.append(f"{prefix}.attestation fields must be exactly {sorted(ATTESTATION_FIELDS)}")
        else:
            attested_status = attestation["status"]
            attested_statement = attestation["statement"]
            attested_bindings = attestation["binding_ids"]
            if attestation["control_id"] != control_id:
                errors.append(f"{prefix}.attestation.control_id must match the binding control")
            if not isinstance(attested_status, str) or attested_status not in {
                "verified",
                "partial",
                "not_applicable",
            }:
                errors.append(f"{prefix}.attestation.status must be evidence-backed")
            elif attested_statement != STATUS_STATEMENTS[attested_status]:
                errors.append(f"{prefix}.attestation.statement must match its status-derived statement")
            if (
                not isinstance(attested_bindings, list)
                or not attested_bindings
                or not all(_nonempty_string(item) for item in attested_bindings)
            ):
                errors.append(f"{prefix}.attestation.binding_ids must be a non-empty list of binding IDs")
            elif len(set(attested_bindings)) != len(attested_bindings):
                errors.append(f"{prefix}.attestation.binding_ids must be unique")
            elif attested_bindings != sorted(attested_bindings):
                errors.append(f"{prefix}.attestation.binding_ids must use stable sorted order")
            elif binding_id not in attested_bindings:
                errors.append(f"{prefix}.attestation.binding_ids must include this binding")
            if (
                _nonempty_string(attestation["control_id"])
                and _nonempty_string(attested_status)
                and _nonempty_string(attested_statement)
                and isinstance(attested_bindings, list)
                and all(_nonempty_string(item) for item in attested_bindings)
            ):
                computed_attestation = attestation_sha256(
                    attestation["control_id"],
                    attested_status,
                    attested_statement,
                    attested_bindings,
                )

        review = binding["review"]
        if not isinstance(review, dict) or set(review) != REVIEW_FIELDS:
            errors.append(f"{prefix}.review fields must be exactly {sorted(REVIEW_FIELDS)}")
        else:
            if review["status"] != "approved":
                errors.append(f"{prefix}.review.status must be approved")
            if not _nonempty_string(review["approved_by"]):
                errors.append(f"{prefix}.review.approved_by must be a non-empty string")
            if not _valid_approval_date(review["approved_at"]):
                errors.append(f"{prefix}.review.approved_at must be an ISO date (YYYY-MM-DD)")
            if not _valid_approval_reference(review["approval_reference"]):
                errors.append(
                    f"{prefix}.review.approval_reference must be an HTTPS URL or review:/ticket:/pr: reference"
                )
            review_digest = review["attestation_sha256"]
            if not isinstance(review_digest, str) or not SHA256.fullmatch(review_digest):
                errors.append(f"{prefix}.review.attestation_sha256 must be a lowercase SHA-256 digest")
            elif computed_attestation is None or review_digest != computed_attestation:
                errors.append(f"{prefix}.review.attestation_sha256 does not match the complete attestation")
            approved_by = review.get("approved_by")
            owner = controls_by_id[control_id].get("owner")
            if (
                _nonempty_string(approved_by)
                and _nonempty_string(owner)
                and approved_by.strip().casefold() == owner.strip().casefold()
            ):
                errors.append(f"{prefix} must be approved by someone other than the control owner")

        resolved_path, path_errors = _resolve_evidence_file(repo_root, binding["repository_path"], prefix)
        errors.extend(path_errors)
        line_range, line_errors = _parse_line_range(binding["lines"], prefix)
        errors.extend(line_errors)
        if resolved_path is not None:
            actual_digest = hashlib.sha256(resolved_path.read_bytes()).hexdigest()
            if actual_digest != binding["sha256"]:
                errors.append(f"{prefix}.sha256 does not match {binding['repository_path']}")
        if resolved_path is not None and line_range is not None:
            try:
                line_count = len(resolved_path.read_text(encoding="utf-8").splitlines())
            except (OSError, UnicodeDecodeError) as exc:
                errors.append(f"{prefix}.repository_path must be readable UTF-8 text: {exc}")
            else:
                if line_range[1] > line_count:
                    errors.append(f"{prefix}.lines is outside {binding['repository_path']} (1-{line_count})")
        if not any(error.startswith(prefix) for error in errors):
            admissible[binding_id] = binding
    return admissible, errors


def _validate_answer_evidence(
    control_id: str,
    answer: dict[str, Any],
    admissible_bindings: dict[str, dict[str, Any]],
) -> list[str]:
    evidence = answer["evidence"]
    if not isinstance(evidence, list):
        return [f"{control_id}: answer.evidence must be a list of approved binding IDs"]
    errors: list[str] = []
    if not all(_nonempty_string(binding_id) for binding_id in evidence):
        errors.append(f"{control_id}: answer.evidence must contain only non-empty binding IDs")
        return errors
    if len(set(evidence)) != len(evidence):
        errors.append(f"{control_id}: answer.evidence binding IDs must be unique")
    referenced_bindings: list[dict[str, Any]] = []
    for binding_id in evidence:
        binding = admissible_bindings.get(binding_id)
        if binding is None:
            errors.append(f"{control_id}: answer.evidence references unapproved binding {binding_id!r}")
        elif binding["control_id"] != control_id:
            errors.append(f"{control_id}: evidence binding {binding_id!r} belongs to another control")
        else:
            referenced_bindings.append(binding)

    status = answer["status"]
    if isinstance(status, str) and status in {"verified", "partial", "not_applicable"} and not evidence:
        errors.append(f"{control_id}: {status} answers require an approved evidence binding")
    if status == "unknown" and evidence:
        errors.append(f"{control_id}: an answer with approved evidence must not remain unknown")
    expected_binding_ids = sorted(evidence)
    for binding in referenced_bindings:
        attestation = binding["attestation"]
        if (
            attestation["control_id"] != control_id
            or attestation["status"] != status
            or attestation["statement"] != answer["statement"]
            or attestation["binding_ids"] != expected_binding_ids
        ):
            errors.append(
                f"{control_id}: approved attestation must match the exact status, statement, and binding-ID set"
            )
    if status == "verified" and any(binding["coverage"] != "full" for binding in referenced_bindings):
        errors.append(f"{control_id}: verified answers require full coverage from every evidence binding")
    if status == "not_applicable" and any(binding["coverage"] != "not_applicable" for binding in referenced_bindings):
        errors.append(f"{control_id}: not_applicable answers require not_applicable evidence coverage")
    return errors


def validate_catalog(
    data: Any,
    repo_root: Path = REPO_ROOT,
    expected_source: Any | None = None,
    evidence_manifest: Any | None = None,
) -> list[str]:
    """Return every catalog, immutable-source, and evidence validation error."""
    if not isinstance(data, dict):
        return ["catalog root must be an object"]
    errors: list[str] = []
    if set(data) != CATALOG_FIELDS:
        errors.append(f"catalog fields must be exactly {sorted(CATALOG_FIELDS)}")
    if data.get("catalog") != "SCI fortlogs security controls":
        errors.append("catalog name must be exactly 'SCI fortlogs security controls'")
    if data.get("evidence_policy") != EXPECTED_EVIDENCE_POLICY:
        errors.append("evidence_policy must exactly match the reviewed policy")
    controls = data.get("controls")
    if not isinstance(controls, list):
        return [*errors, "controls must be a list"]

    if expected_source is None:
        expected_source, fixture_errors = _load_expected_source()
        errors.extend(fixture_errors)
    if evidence_manifest is None:
        evidence_manifest, manifest_errors = _load_json(DEFAULT_MANIFEST, "evidence manifest")
        errors.extend(manifest_errors)

    ids = [control.get("id") if isinstance(control, dict) else None for control in controls]
    if len(controls) != len(EXPECTED_IDS):
        errors.append(f"expected {len(EXPECTED_IDS)} controls, found {len(controls)}")
    string_ids = [control_id for control_id in ids if isinstance(control_id, str)]
    if len(string_ids) != len(ids):
        errors.append("control IDs must be strings")
    elif len(set(string_ids)) != len(string_ids):
        errors.append("control IDs must be unique")
    if tuple(ids) != EXPECTED_IDS:
        errors.append("control IDs or domain order differ from the supplied inventory")

    controls_by_id: dict[str, dict[str, Any]] = {}
    for index, control in enumerate(controls):
        control_id = ids[index] if isinstance(ids[index], str) and ids[index] else f"control[{index}]"
        if not isinstance(control, dict):
            errors.append(f"{control_id}: control must be an object")
            continue
        if set(control) != CONTROL_FIELDS:
            errors.append(f"{control_id}: fields must be exactly {sorted(CONTROL_FIELDS)}")
            continue
        controls_by_id[control_id] = control

        for field in STRING_FIELDS:
            if not _nonempty_string(control[field]):
                errors.append(f"{control_id}: {field} must be a non-empty string")
        for field in ("shared", "draft", "internal"):
            if not isinstance(control[field], bool):
                errors.append(f"{control_id}: {field} must be a boolean")
        if not isinstance(control["delegates"], list) or not control["delegates"]:
            errors.append(f"{control_id}: delegates must be a non-empty list")
        elif not all(_nonempty_string(delegate) for delegate in control["delegates"]):
            errors.append(f"{control_id}: delegates must contain non-empty strings")
        if control["regulations"] is not None:
            errors.append(f"{control_id}: regulations must be null because the source omitted them")

        answer = control["answer"]
        if not isinstance(answer, dict) or set(answer) != ANSWER_FIELDS:
            errors.append(f"{control_id}: answer fields must be exactly {sorted(ANSWER_FIELDS)}")
            continue
        status = answer["status"]
        if not isinstance(status, str):
            errors.append(f"{control_id}: answer.status must be a string")
        elif status not in VALID_STATUSES:
            errors.append(f"{control_id}: invalid answer status: {status}")
        elif answer["statement"] != STATUS_STATEMENTS[status]:
            errors.append(f"{control_id}: answer.statement must match the status-derived statement")
        if answer["source_note"] is not None and not _nonempty_string(answer["source_note"]):
            errors.append(f"{control_id}: answer.source_note must be null or a non-empty string")
        if not _nonempty_string(answer["missing_evidence"]):
            errors.append(f"{control_id}: answer.missing_evidence must be a non-empty string")

    if expected_source is not None:
        errors.extend(_validate_source_fixture(data, expected_source))
    admissible_bindings: dict[str, dict[str, Any]] = {}
    if evidence_manifest is not None:
        admissible_bindings, manifest_errors = _validate_manifest(evidence_manifest, controls_by_id, repo_root)
        errors.extend(manifest_errors)
    for control_id, control in controls_by_id.items():
        answer = control["answer"]
        if isinstance(answer, dict) and set(answer) == ANSWER_FIELDS:
            errors.extend(_validate_answer_evidence(control_id, answer, admissible_bindings))
    return errors


def _markdown_text(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, list):
        return "<br>".join(_markdown_text(item) for item in value) or "n/a"
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _render_answer(answer: dict[str, Any]) -> str:
    evidence = answer["evidence"] or ["None"]
    source_note = answer["source_note"] if answer["source_note"] is not None else "n/a"
    parts = (
        f"Status: {_markdown_text(answer['status'])}",
        f"Statement: {_markdown_text(answer['statement'])}",
        f"Source note: {_markdown_text(source_note)}",
        f"Evidence bindings: {_markdown_text(evidence)}",
        f"Missing evidence: {_markdown_text(answer['missing_evidence'])}",
    )
    return "<br>".join(parts)


def render_markdown(data: dict[str, Any]) -> str:
    """Render every catalog field in stable domain and control order."""
    lines = [
        "# SCI fortlogs security controls",
        "",
        "This file is generated from `sci-fortlogs-security-controls.json`; manual edits fail validation.",
        "",
        "All evidence-backed statuses require an independently approved, checksum-bound entry in "
        "`sci-fortlogs-evidence-manifest.json`. Each approval is bound to the exact control ID, status, "
        "statement, and complete binding-ID set. Approval metadata syntax and declared reviewer separation "
        "are validated locally; reviewer identity, date, and reference are not externally verified. Human "
        "review must confirm them and assess whether each cited line supports its claim.",
        "",
        "Green and yellow source notes are preserved as confidence notes, not evidence. Regulations remain "
        "collapsed because their source values were not supplied.",
        "",
    ]
    current_domain: str | None = None
    for control in data["controls"]:
        if control["domain"] != current_domain:
            current_domain = control["domain"]
            lines.extend((f"## {current_domain}", ""))
        lines.extend(
            (
                f"### {control['id']}",
                "",
                "| Field | Value |",
                "|---|---|",
            )
        )
        for field in CONTROL_FIELD_ORDER[:-1]:
            value = _render_answer(control[field]) if field == "answer" else _markdown_text(control[field])
            lines.append(f"| {FIELD_LABELS[field]} | {value} |")
        regulations = (
            "Not supplied (collapsed in source)."
            if control["regulations"] is None
            else _markdown_text(control["regulations"])
        )
        lines.extend(
            (
                "",
                "<details>",
                "<summary>Regulations</summary>",
                "",
                regulations,
                "",
                "</details>",
                "",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def validate_markdown(data: dict[str, Any], markdown: str) -> list[str]:
    """Require the checked-in Markdown to equal the deterministic JSON rendering."""
    if markdown != render_markdown(data):
        return ["Markdown is stale or manually edited; regenerate it from the canonical JSON"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", nargs="?", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--render-markdown", action="store_true")
    args = parser.parse_args()

    data, errors = _load_json(args.catalog, "SCI control catalog")
    manifest, manifest_errors = _load_json(args.manifest, "evidence manifest")
    errors.extend(manifest_errors)
    expected_source, fixture_errors = _load_expected_source()
    errors.extend(fixture_errors)
    if data is not None:
        errors.extend(validate_catalog(data, expected_source=expected_source, evidence_manifest=manifest))
        if args.render_markdown:
            if errors:
                for error in errors:
                    print(f"- {error}", file=sys.stderr)
                return 1
            print(render_markdown(data), end="")
            return 0
        try:
            markdown = args.markdown.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"SCI control Markdown invalid: {exc}")
        else:
            errors.extend(validate_markdown(data, markdown))

    if errors:
        print("SCI control catalog invalid:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        f"SCI control catalog valid: {len(data['controls'])} controls, "
        f"{len(CONTROL_FIELDS)} fields each, Markdown current"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
