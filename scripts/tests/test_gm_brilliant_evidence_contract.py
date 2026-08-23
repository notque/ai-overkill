"""Regression guards for GM exact-state and evidence-gate schemas."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "skills" / "game" / "gm-brilliant-implementation" / "references" / "pipeline-spec.json"


def _spec():
    return json.loads(SPEC.read_text(encoding="utf-8"))


def test_exact_state_incident_schema_has_closed_severe_trigger_set():
    schema = _spec()["exact_state_incident_schema"]
    assert schema["additional_fields"] is False
    assert set(schema["severity_triggers"]) == {
        "state_loss",
        "blocked_core_action",
        "duplicate_write",
        "sustained_5xx",
        "truth_breach",
        "accessibility_blocker",
        "none",
    }
    assert schema["product_change_dispositions"] == ["repair_now"]
    rejection = " ".join(schema["reject_when"])
    for guard in ("independent confirmation", "bounded repair scope", "rollback pointer", "stop condition"):
        assert guard in rejection


def test_evidence_gate_refuses_direct_or_under_threshold_product_work():
    schema = _spec()["evidence_gate_schema"]
    assert schema["additional_fields"] is False
    assert schema["product_change_authorized"] is False
    assert set(schema["allowed_actions"]) == {"measure", "recruit", "run_protocol", "reproduce"}
    rejection = " ".join(schema["reject_when"])
    assert "below required threshold" in rejection
    assert "eligible denominator" in rejection
    assert "small-cell suppression" in rejection
    assert "product_change_authorized is true" in rejection
    assert "threshold_registry_hash" in schema["required_fields"]


def test_threshold_registry_is_single_source_and_hash_bound():
    schema = _spec()["evidence_gate_registry_schema"]
    assert schema["rows_sorted_by"] == "row_id bytewise"
    assert schema["consumer_reference_fields"] == ["row_id", "threshold_registry_hash"]
    rejection = " ".join(schema["reject_when"])
    assert "consumer registry hash differs" in rejection
    assert "secondary artifact threshold conflicts" in rejection


def test_completion_snapshot_has_one_authority_and_exhaustive_counts():
    schema = _spec()["completion_snapshot_schema"]
    assert schema["additional_fields"] is False
    assert schema["current_snapshot_count"] == 1
    assert set(schema["status_fields"]) == {
        "done_live",
        "valid_unfinished_implementation",
        "superseded_refused",
        "missing_unbound_evidence",
    }
    rejection = " ".join(schema["reject_when"])
    assert "status counts do not sum to scope_count" in rejection
    assert "more than one current snapshot exists" in rejection
    assert "release_sha differs from exact live" in rejection
