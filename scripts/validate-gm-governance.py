#!/usr/bin/env python3
"""Validate GM evidence gates and the complete snapshot authority chain."""

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "skills/game/gm-brilliant-implementation/references/pipeline-spec.json"
HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load {path}: {exc}") from exc


def _hash(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def _is_int(value, minimum=0):
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _fields(value, required, label, errors):
    if not isinstance(value, dict) or set(value) != set(required):
        errors.append(f"{label} fields mismatch")
        return False
    return True


def validate(registry, dispositions, consumers, scope, manifest, exact_live, spec=None):
    errors = []
    spec = spec or _load(SPEC_PATH)
    rs = spec["evidence_gate_registry_schema"]
    cs = spec["evidence_consumer_manifest_schema"]
    ds = spec["evidence_gate_schema"]
    ss = spec["completion_snapshot_schema"]

    if not _fields(registry, rs["required_fields"], "registry", errors):
        registry = registry if isinstance(registry, dict) else {}
    rows = registry.get("rows")
    if not isinstance(rows, list) or not rows:
        errors.append("registry rows must be a non-empty array")
        rows = []
    ids = []
    for index, row in enumerate(rows):
        if not _fields(row, rs["required_row_fields"], f"registry row {index}", errors):
            continue
        row_id = row["row_id"]
        ids.append(row_id)
        if not isinstance(row_id, str) or not row_id.strip():
            errors.append(f"registry row {index}: invalid row_id")
        if row["evidence_kind"] not in ds["evidence_kinds"]:
            errors.append(f"{row_id}: unknown evidence kind")
        if not _is_int(row["required_threshold"], 1) or not _is_int(row["window_count"], 1):
            errors.append(f"{row_id}: invalid threshold/window count")
        if not isinstance(row["eligible_denominator_required"], bool):
            errors.append(f"{row_id}: denominator requirement must be Boolean")
        if not HASH_RE.fullmatch(str(row["protocol_hash"])):
            errors.append(f"{row_id}: malformed protocol hash")
        for field in ("privacy_guard", "interpretation_trigger", "owner"):
            if not isinstance(row[field], str) or not row[field].strip():
                errors.append(f"{row_id}: empty {field}")
    if ids != sorted(ids) or len(ids) != len(set(ids)):
        errors.append("registry row IDs must be unique and bytewise sorted")
    registry_hash = _hash({"schema_version": registry.get("schema_version"), "rows": rows})
    if registry.get("registry_hash") != registry_hash:
        errors.append("registry hash mismatch")
    by_id = {row.get("row_id"): row for row in rows if isinstance(row, dict)}

    if not isinstance(dispositions, list):
        errors.append("dispositions must be an array")
        dispositions = []
    disposition_ids = []
    allowed_actions = set(ds["allowed_actions"])
    for index, row in enumerate(dispositions):
        if not _fields(row, ds["required_fields"], f"disposition {index}", errors):
            continue
        row_id = row["row_id"]
        disposition_ids.append(row_id)
        source = by_id.get(row_id)
        if source is None:
            errors.append(f"{row_id}: no registry row")
            continue
        if row["threshold_registry_hash"] != registry_hash:
            errors.append(f"{row_id}: registry hash drift")
        if row["evidence_kind"] != source["evidence_kind"]:
            errors.append(f"{row_id}: evidence kind drift")
        if not _is_int(row["observed_threshold"]):
            errors.append(f"{row_id}: observed threshold must be a nonnegative integer")
        if not _is_int(row["observed_window_count"]):
            errors.append(f"{row_id}: observed window count must be a nonnegative integer")
        if row["eligible_denominator"] is not None and not _is_int(row["eligible_denominator"]):
            errors.append(f"{row_id}: eligible denominator is malformed")
        if row["protocol_hash"] != source["protocol_hash"] or row["privacy_guard"] != source["privacy_guard"]:
            errors.append(f"{row_id}: protocol/privacy drift")
        expected_guard = "small_cell_suppressed" if source["evidence_kind"] == "privacy_safe_volume" else "none_needed"
        if source["privacy_guard"] != expected_guard:
            errors.append(f"{row_id}: evidence kind/privacy guard mismatch")
        if row["status"] not in ds["statuses"]:
            errors.append(f"{row_id}: unknown status")
        actions = row["allowed_actions"]
        if not isinstance(actions, list) or len(actions) != len(set(actions)) or not set(actions) <= allowed_actions:
            errors.append(f"{row_id}: disallowed or duplicate action")
        if row["product_change_authorized"] is not False:
            errors.append(f"{row_id}: disposition directly authorizes product work")
        if not isinstance(row["owner"], str) or not row["owner"].strip():
            errors.append(f"{row_id}: empty owner")
        if not isinstance(row["next_evaluation"], str) or not row["next_evaluation"].strip().lower().startswith(
            "when "
        ):
            errors.append(f"{row_id}: invalid next evaluation")
        threshold_met = (
            _is_int(source["required_threshold"], 1)
            and isinstance(source["eligible_denominator_required"], bool)
            and _is_int(row["observed_threshold"])
            and _is_int(row["observed_window_count"])
            and row["observed_threshold"] >= source["required_threshold"]
            and row["observed_window_count"] >= source["window_count"]
            and (
                not source["eligible_denominator_required"]
                or _is_int(row["eligible_denominator"], source["required_threshold"])
            )
        )
        if row["status"] == "threshold_met" and not threshold_met:
            errors.append(f"{row_id}: threshold_met without threshold/denominator proof")
        if row["status"] == "evidence_blocked" and threshold_met:
            errors.append(f"{row_id}: evidence_blocked despite completed threshold")
        decision = row["scoped_decision_hash"]
        if decision is not None and not HASH_RE.fullmatch(str(decision)):
            errors.append(f"{row_id}: malformed scoped decision hash")
        if row["status"] == "evidence_blocked" and decision is not None:
            errors.append(f"{row_id}: blocked evidence has a scoped decision")
    if disposition_ids != ids:
        errors.append("dispositions must cover registry rows once in bytewise order")

    if not _fields(consumers, cs["required_fields"], "consumer manifest", errors):
        consumers = consumers if isinstance(consumers, dict) else {}
    consumer_rows = consumers.get("consumers")
    if not isinstance(consumer_rows, list) or not consumer_rows:
        errors.append("consumer manifest consumers must be a non-empty array")
        consumer_rows = []
    consumer_ids = []
    for index, consumer in enumerate(consumer_rows):
        if not _fields(consumer, cs["required_consumer_fields"], f"consumer {index}", errors):
            continue
        consumer_id = consumer["consumer_id"]
        consumer_ids.append(consumer_id)
        if not isinstance(consumer_id, str) or not consumer_id.strip():
            errors.append(f"consumer {index}: invalid consumer_id")
        if not HASH_RE.fullmatch(str(consumer["artifact_hash"])):
            errors.append(f"{consumer_id}: malformed artifact hash")
        row_ids = consumer["row_ids"]
        if not isinstance(row_ids, list) or not row_ids:
            errors.append(f"{consumer_id}: row_ids must be a non-empty array")
            continue
        if row_ids != sorted(row_ids) or len(row_ids) != len(set(row_ids)):
            errors.append(f"{consumer_id}: row IDs must be unique and bytewise sorted")
        if any(row_id not in by_id for row_id in row_ids):
            errors.append(f"{consumer_id}: unknown registry row")
    if consumer_ids != sorted(consumer_ids) or len(consumer_ids) != len(set(consumer_ids)):
        errors.append("consumer IDs must be unique and bytewise sorted")
    if consumers.get("threshold_registry_hash") != registry_hash:
        errors.append("consumer registry hash drift")
    consumer_hash = _hash(
        {key: consumers.get(key) for key in ("schema_version", "threshold_registry_hash", "consumers")}
    )
    if consumers.get("consumer_manifest_hash") != consumer_hash:
        errors.append("consumer manifest hash mismatch")

    if not isinstance(scope, dict) or set(scope) != {"schema_version", "row_ids", "scope_hash"}:
        errors.append("scope fields mismatch")
        scope = scope if isinstance(scope, dict) else {}
    scope_ids = scope.get("row_ids") if isinstance(scope.get("row_ids"), list) else []
    if scope_ids != sorted(scope_ids) or len(scope_ids) != len(set(scope_ids)):
        errors.append("scope row IDs must be unique and bytewise sorted")
    scope_hash = _hash({"schema_version": scope.get("schema_version"), "row_ids": scope_ids})
    if scope.get("scope_hash") != scope_hash:
        errors.append("scope hash mismatch")

    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "current_snapshot_hash", "snapshots"}:
        errors.append("snapshot manifest fields mismatch")
        manifest = manifest if isinstance(manifest, dict) else {}
    snapshots = manifest.get("snapshots") if isinstance(manifest.get("snapshots"), list) else []
    snapshot_by_hash = {}
    for index, snapshot in enumerate(snapshots):
        if not _fields(snapshot, ss["required_fields"], f"snapshot {index}", errors):
            continue
        claimed_hash = snapshot["snapshot_hash"]
        if not HASH_RE.fullmatch(str(claimed_hash)):
            errors.append(f"snapshot {index}: malformed snapshot hash")
        if claimed_hash != _hash({key: value for key, value in snapshot.items() if key != "snapshot_hash"}):
            errors.append(f"snapshot {index}: hash mismatch")
        if claimed_hash in snapshot_by_hash:
            errors.append("duplicate snapshot hash")
        snapshot_by_hash[claimed_hash] = snapshot
        counts = snapshot["status_counts"]
        if (
            not isinstance(counts, dict)
            or set(counts) != set(ss["status_fields"])
            or not all(_is_int(value) for value in counts.values())
        ):
            errors.append(f"snapshot {index}: status fields/types mismatch")
            counts = {}
        row_dispositions = snapshot["row_dispositions"]
        snap_ids = (
            [row.get("row_id") for row in row_dispositions if isinstance(row, dict)]
            if isinstance(row_dispositions, list)
            else []
        )
        if snap_ids != scope_ids or len(snap_ids) != len(row_dispositions or []):
            errors.append(f"snapshot {index}: row scope mismatch")
        actual_counts = {status: 0 for status in ss["status_fields"]}
        for snap_row in row_dispositions if isinstance(row_dispositions, list) else []:
            status = snap_row.get("status") if isinstance(snap_row, dict) else None
            if status not in actual_counts:
                errors.append(f"snapshot {index}: unknown row status")
                continue
            actual_counts[status] += 1
            if snap_row.get("row_id") in ids:
                disposition = dispositions[ids.index(snap_row["row_id"])]
                if status == "valid_unfinished_implementation" and (
                    disposition["status"] != "threshold_met" or not disposition["scoped_decision_hash"]
                ):
                    errors.append(f"{snap_row.get('row_id')}: evidence gate cannot be unfinished implementation")
        if counts != actual_counts or sum(counts.values()) != snapshot["scope_count"]:
            errors.append(f"snapshot {index}: counts do not match row dispositions")
        if snapshot["scope_count"] != len(scope_ids) or snapshot["scope_hash"] != scope_hash:
            errors.append(f"snapshot {index}: scope mismatch")
        if snapshot["row_disposition_hash"] != _hash(row_dispositions):
            errors.append(f"snapshot {index}: row disposition hash mismatch")
        if snapshot["evidence_registry_hash"] != registry_hash:
            errors.append(f"snapshot {index}: evidence registry hash drift")
        if snapshot["evidence_consumer_manifest_hash"] != consumer_hash:
            errors.append(f"snapshot {index}: evidence consumer manifest hash drift")
        if not SHA_RE.fullmatch(str(snapshot["release_sha"])):
            errors.append(f"snapshot {index}: malformed release SHA")
        predecessor = snapshot["predecessor_hash"]
        if predecessor is not None and not HASH_RE.fullmatch(str(predecessor)):
            errors.append(f"snapshot {index}: malformed predecessor hash")
    current = manifest.get("current_snapshot_hash")
    if current not in snapshot_by_hash:
        errors.append("current snapshot pointer is missing or stale")
    elif snapshot_by_hash[current]["release_sha"] != exact_live:
        errors.append("current snapshot release differs from exact live")
    visited = set()
    cursor = current
    while cursor in snapshot_by_hash and cursor not in visited:
        visited.add(cursor)
        cursor = snapshot_by_hash[cursor]["predecessor_hash"]
    if cursor is not None:
        errors.append("snapshot predecessor chain is missing or cyclic")
    if visited != set(snapshot_by_hash):
        errors.append("snapshot manifest contains competing/unlinked snapshots")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    parser.add_argument("--dispositions", required=True)
    parser.add_argument("--consumers", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--snapshot-manifest", required=True)
    parser.add_argument("--exact-live", required=True)
    args = parser.parse_args()
    try:
        errors = validate(
            _load(args.registry),
            _load(args.dispositions),
            _load(args.consumers),
            _load(args.scope),
            _load(args.snapshot_manifest),
            args.exact_live,
        )
    except (KeyError, TypeError, ValueError) as exc:
        errors = [f"malformed input: {exc}"]
    for error in errors:
        print(f"FAIL: {error}")
    if errors:
        raise SystemExit(1)
    print("PASS: GM governance artifacts are consistent")


if __name__ == "__main__":
    main()
