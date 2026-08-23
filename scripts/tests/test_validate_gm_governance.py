import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "validate-gm-governance.py"
SPEC = importlib.util.spec_from_file_location("validate_gm_governance", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _artifacts():
    rows = [
        {
            "row_id": "ML-10",
            "evidence_kind": "privacy_safe_volume",
            "required_threshold": 30,
            "window_count": 2,
            "eligible_denominator_required": True,
            "protocol_hash": "sha256:" + "1" * 64,
            "privacy_guard": "small_cell_suppressed",
            "interpretation_trigger": "two weak windows",
            "owner": "evidence-owner",
        }
    ]
    registry = {"rows": rows, "registry_hash": MODULE._hash(rows)}
    dispositions = [
        {
            "row_id": "ML-10",
            "threshold_registry_hash": registry["registry_hash"],
            "status": "evidence_blocked",
            "product_change_authorized": False,
        }
    ]
    row_dispositions = [{"row_id": "ML-10", "status": "superseded_refused"}]
    snapshot = {
        "scope_hash": "sha256:" + "2" * 64,
        "scope_count": 1,
        "release_sha": "a" * 40,
        "status_counts": {
            "done_live": 0,
            "valid_unfinished_implementation": 0,
            "superseded_refused": 1,
            "missing_unbound_evidence": 0,
        },
        "row_dispositions": row_dispositions,
        "row_disposition_hash": MODULE._hash(row_dispositions),
        "evidence_registry_hash": registry["registry_hash"],
        "supersedes": [],
        "verifier_receipt": "fixture",
    }
    return registry, dispositions, snapshot


def test_valid_artifacts_pass():
    assert MODULE.validate(*_artifacts(), exact_live="a" * 40) == []


def test_threshold_copy_and_hash_drift_fail():
    registry, dispositions, snapshot = _artifacts()
    dispositions[0]["required_threshold"] = 5
    dispositions[0]["threshold_registry_hash"] = "sha256:" + "0" * 64
    errors = MODULE.validate(registry, dispositions, snapshot, exact_live="a" * 40)
    assert any("copied threshold" in error for error in errors)
    assert any("registry hash drift" in error for error in errors)


def test_incomplete_or_stale_snapshot_fails():
    registry, dispositions, snapshot = _artifacts()
    snapshot["status_counts"]["done_live"] = 1
    snapshot["evidence_registry_hash"] = "sha256:" + "0" * 64
    snapshot["release_sha"] = "b" * 40
    errors = MODULE.validate(registry, dispositions, snapshot, exact_live="a" * 40)
    assert "snapshot counts do not exhaust scope" in errors
    assert "snapshot evidence registry hash drift" in errors
    assert "snapshot release differs from exact live" in errors
