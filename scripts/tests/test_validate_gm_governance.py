import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "validate-gm-governance.py"
SPEC = importlib.util.spec_from_file_location("validate_gm_governance", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
LIVE = "0" * 40
RA_IDS = [
    "RA-S07",
    "RA-S08",
    "RA-S11",
    "RA-S12",
    "RA-S13",
    "RA-S14",
    "RA-S15",
    "RA-S16",
    "RA-S17",
    "RA-S18",
    "RA-S19",
    "RA-S20",
    "RA-S21",
    "RA-S22",
    "RA-S24",
    "RA-M01",
    "RA-M02",
    "RA-M03",
    "RA-M04",
    "RA-M05",
    "RA-M06",
    "RA-M07",
    "RA-M08",
    "RA-M09",
    "RA-R05",
    "RA-R07",
    "RA-R08",
    "RA-R10",
    "RA-R11",
    "RA-R13",
    "RA-N01",
    "RA-N02",
    "RA-N03",
    "RA-N06",
    "RA-N07",
    "RA-N09",
    "RA-UX11",
    "RA-PERF01",
    "RA-AC01",
    "RA-AC02",
]
AUDIT_IDS = sorted(
    RA_IDS
    + [f"ML-{n:02d}" for n in range(1, 25)]
    + [f"LIVE-FIX{n:02d}" for n in range(1, 5)]
    + [f"FB-S{n:02d}" for n in range(1, 9)]
    + [f"FB-P{n:02d}" for n in range(1, 11)]
)
EVIDENCE_IDS = sorted(["ML-04", "ML-08", "ML-10", "ML-24", "FB-S02", "FB-S03"])
REFUSED_IDS = {
    "ML-12",
    "RA-M02",
    "RA-M03",
    "RA-M04",
    "RA-M07",
    "RA-M08",
    "RA-M09",
    "RA-R07",
    "RA-R13",
    "RA-S19",
    "RA-S21",
}


def _artifacts():
    rows = [
        {
            "row_id": row_id,
            "evidence_kind": "privacy_safe_volume" if row_id in {"ML-10", "FB-S02", "FB-S03"} else "unprompted_human",
            "required_threshold": 30 if row_id in {"ML-10", "FB-S02", "FB-S03"} else (8 if row_id == "ML-24" else 5),
            "window_count": 2 if row_id in {"ML-10", "FB-S02"} else 1,
            "eligible_denominator_required": row_id in {"ML-10", "FB-S02", "FB-S03"},
            "protocol_hash": "sha256:" + "1" * 64,
            "privacy_guard": "small_cell_suppressed" if row_id in {"ML-10", "FB-S02", "FB-S03"} else "none_needed",
            "interpretation_trigger": "declared external evidence gate",
            "owner": "evidence-owner",
        }
        for row_id in EVIDENCE_IDS
    ]
    registry = {"schema_version": 1, "rows": rows}
    registry["registry_hash"] = MODULE._hash({"schema_version": 1, "rows": rows})
    dispositions = [
        {
            "row_id": row["row_id"],
            "threshold_registry_hash": registry["registry_hash"],
            "evidence_kind": row["evidence_kind"],
            "observed_threshold": 0,
            "observed_window_count": 0,
            "eligible_denominator": 0 if row["eligible_denominator_required"] else None,
            "protocol_hash": row["protocol_hash"],
            "privacy_guard": row["privacy_guard"],
            "status": "evidence_blocked",
            "allowed_actions": ["measure", "recruit", "run_protocol", "reproduce"],
            "product_change_authorized": False,
            "scoped_decision_hash": None,
            "owner": "evidence-owner",
            "next_evaluation": "when the canonical threshold is met",
        }
        for row in rows
    ]
    consumer_rows = [
        {"consumer_id": "completion-ledger", "artifact_hash": "sha256:" + "2" * 64, "row_ids": EVIDENCE_IDS}
    ]
    consumers = {"schema_version": 1, "threshold_registry_hash": registry["registry_hash"], "consumers": consumer_rows}
    consumers["consumer_manifest_hash"] = MODULE._hash(consumers)
    scope = {"schema_version": 1, "row_ids": AUDIT_IDS}
    scope["scope_hash"] = MODULE._hash({"schema_version": 1, "row_ids": AUDIT_IDS})
    refused = REFUSED_IDS
    row_dispositions = [
        {"row_id": row_id, "status": "superseded_refused" if row_id in refused else "done_live"} for row_id in AUDIT_IDS
    ]
    snapshot = {
        "schema_version": 1,
        "scope_hash": scope["scope_hash"],
        "scope_count": 86,
        "release_sha": LIVE,
        "status_counts": {
            "done_live": 75,
            "valid_unfinished_implementation": 0,
            "superseded_refused": 11,
            "missing_unbound_evidence": 0,
        },
        "row_dispositions": row_dispositions,
        "row_disposition_hash": MODULE._hash(row_dispositions),
        "evidence_registry_hash": registry["registry_hash"],
        "evidence_consumer_manifest_hash": consumers["consumer_manifest_hash"],
        "predecessor_hash": None,
        "verifier_receipt": "exact-live fixture",
    }
    snapshot["snapshot_hash"] = MODULE._hash(snapshot)
    manifest = {"schema_version": 1, "current_snapshot_hash": snapshot["snapshot_hash"], "snapshots": [snapshot]}
    return registry, dispositions, consumers, scope, manifest


def test_exact_86_row_closure_fixture_passes():
    assert len(AUDIT_IDS) == 86
    assert len(set(AUDIT_IDS)) == 86
    assert set(AUDIT_IDS) >= REFUSED_IDS
    assert {"FB-P06", "FB-P07", "FB-P08"}.isdisjoint(REFUSED_IDS)
    assert MODULE.validate(*_artifacts(), exact_live=LIVE) == []


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda a: a[2].update(threshold_registry_hash="sha256:" + "9" * 64), "consumer registry hash drift"),
        (lambda a: a[2]["consumers"][0]["row_ids"].append("UNKNOWN"), "unknown registry row"),
        (lambda a: a[2]["consumers"][0].update(required_threshold=5), "consumer 0 fields mismatch"),
        (lambda a: a[2]["consumers"][0].update(privacy_guard="none_needed"), "consumer 0 fields mismatch"),
    ],
)
def test_consumer_manifest_rejects_drift_and_copied_thresholds(mutate, message):
    artifacts = list(copy.deepcopy(_artifacts()))
    mutate(artifacts)
    assert any(message in error for error in MODULE.validate(*artifacts, exact_live=LIVE))


def test_exact_86_row_fixture_passes_through_cli(tmp_path):
    registry, dispositions, consumers, scope, manifest = _artifacts()
    paths = {}
    for name, value in (
        ("registry", registry),
        ("dispositions", dispositions),
        ("consumers", consumers),
        ("scope", scope),
        ("manifest", manifest),
    ):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        paths[name] = path
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(paths["registry"]),
            "--dispositions",
            str(paths["dispositions"]),
            "--consumers",
            str(paths["consumers"]),
            "--scope",
            str(paths["scope"]),
            "--snapshot-manifest",
            str(paths["manifest"]),
            "--exact-live",
            LIVE,
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: GM governance artifacts are consistent" in result.stdout


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda a: a[1][0].update(status="threshold_met"), "threshold_met without"),
        (lambda a: a[1][0].update(allowed_actions=["implement"]), "disallowed"),
        (lambda a: a[1][0].update(product_change_authorized=True), "directly authorizes"),
        (lambda a: a[1][0].update(protocol_hash="bad"), "protocol/privacy drift"),
        (lambda a: a[1][0].update(eligible_denominator="many"), "denominator is malformed"),
        (lambda a: a[1][0].update(owner=""), "empty owner"),
        (lambda a: a[0]["rows"][0].update(required_threshold="30"), "invalid threshold"),
        (lambda a: a[3]["row_ids"].append(a[3]["row_ids"][0]), "scope row IDs"),
        (lambda a: a[4]["snapshots"][0]["row_dispositions"].pop(), "row scope mismatch"),
        (lambda a: a[4]["snapshots"][0].update(release_sha="f" * 40), "current snapshot release"),
    ],
)
def test_adversarial_contract_rejections(mutate, message):
    artifacts = list(copy.deepcopy(_artifacts()))
    mutate(artifacts)
    assert any(message in error for error in MODULE.validate(*artifacts, exact_live=LIVE))


def test_two_currents_or_missing_predecessor_fail():
    registry, dispositions, consumers, scope, manifest = copy.deepcopy(_artifacts())
    second = copy.deepcopy(manifest["snapshots"][0])
    second["release_sha"] = "1" * 40
    second["predecessor_hash"] = "sha256:" + "9" * 64
    second["snapshot_hash"] = MODULE._hash({key: value for key, value in second.items() if key != "snapshot_hash"})
    manifest["snapshots"].append(second)
    errors = MODULE.validate(registry, dispositions, consumers, scope, manifest, LIVE)
    assert any("competing/unlinked" in error or "predecessor chain" in error for error in errors)


def test_stale_current_pointer_fails():
    registry, dispositions, consumers, scope, manifest = copy.deepcopy(_artifacts())
    manifest["current_snapshot_hash"] = "sha256:" + "9" * 64
    assert "current snapshot pointer is missing or stale" in MODULE.validate(
        registry, dispositions, consumers, scope, manifest, LIVE
    )


def test_evidence_gate_cannot_be_unfinished_without_threshold_and_decision():
    registry, dispositions, consumers, scope, manifest = copy.deepcopy(_artifacts())
    row_id = EVIDENCE_IDS[0]
    snapshot = manifest["snapshots"][0]
    row = next(item for item in snapshot["row_dispositions"] if item["row_id"] == row_id)
    row["status"] = "valid_unfinished_implementation"
    snapshot["status_counts"]["superseded_refused"] -= 1
    snapshot["status_counts"]["valid_unfinished_implementation"] += 1
    snapshot["row_disposition_hash"] = MODULE._hash(snapshot["row_dispositions"])
    snapshot["snapshot_hash"] = MODULE._hash({key: value for key, value in snapshot.items() if key != "snapshot_hash"})
    manifest["current_snapshot_hash"] = snapshot["snapshot_hash"]
    assert any(
        "cannot be unfinished implementation" in error
        for error in MODULE.validate(registry, dispositions, consumers, scope, manifest, LIVE)
    )


def test_malformed_shapes_return_errors_not_exceptions():
    assert MODULE.validate({}, [None], {}, {}, {"snapshots": "bad"}, LIVE)
