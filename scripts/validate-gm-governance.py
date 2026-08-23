#!/usr/bin/env python3
"""Validate GM evidence registries, dispositions, and completion snapshots."""

import argparse
import hashlib
import json
from pathlib import Path

STATUSES = {
    "done_live",
    "valid_unfinished_implementation",
    "superseded_refused",
    "missing_unbound_evidence",
}
REGISTRY_FIELDS = {
    "row_id",
    "evidence_kind",
    "required_threshold",
    "window_count",
    "eligible_denominator_required",
    "protocol_hash",
    "privacy_guard",
    "interpretation_trigger",
    "owner",
}
SNAPSHOT_FIELDS = {
    "scope_hash",
    "scope_count",
    "release_sha",
    "status_counts",
    "row_dispositions",
    "row_disposition_hash",
    "evidence_registry_hash",
    "supersedes",
    "verifier_receipt",
}


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _hash(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def validate(registry, dispositions, snapshot, exact_live=None):
    errors = []
    rows = registry.get("rows") if isinstance(registry, dict) else None
    if not isinstance(rows, list) or not rows:
        return ["registry rows must be a non-empty array"]
    ids = [row.get("row_id") for row in rows if isinstance(row, dict)]
    if len(ids) != len(rows) or ids != sorted(ids) or len(ids) != len(set(ids)):
        errors.append("registry row IDs must be unique and bytewise sorted")
    registry_hash = _hash(rows)
    if registry.get("registry_hash") != registry_hash:
        errors.append("registry hash mismatch")
    by_id = {row.get("row_id"): row for row in rows if isinstance(row, dict)}
    for row_id, row in by_id.items():
        if set(row) != REGISTRY_FIELDS:
            errors.append(f"{row_id}: registry fields mismatch")

    if not isinstance(dispositions, list) or len(dispositions) != len(rows):
        errors.append("dispositions must cover every registry row exactly once")
        dispositions = dispositions if isinstance(dispositions, list) else []
    disposition_ids = [row.get("row_id") for row in dispositions if isinstance(row, dict)]
    if len(disposition_ids) != len(set(disposition_ids)) or set(disposition_ids) != set(ids):
        errors.append("disposition row coverage mismatch")
    for row in dispositions:
        if not isinstance(row, dict) or row.get("row_id") not in by_id:
            continue
        if row.get("threshold_registry_hash") != registry_hash:
            errors.append(f"{row.get('row_id')}: registry hash drift")
        if "required_threshold" in row:
            errors.append(f"{row.get('row_id')}: copied threshold is forbidden")
        if row.get("status") == "evidence_blocked" and row.get("product_change_authorized") is not False:
            errors.append(f"{row.get('row_id')}: blocked evidence authorizes product work")

    if not isinstance(snapshot, dict) or set(snapshot) != SNAPSHOT_FIELDS:
        errors.append("snapshot fields mismatch")
        snapshot = snapshot if isinstance(snapshot, dict) else {}
    counts = snapshot.get("status_counts")
    if not isinstance(counts, dict) or set(counts) != STATUSES:
        errors.append("snapshot status fields mismatch")
    elif sum(counts.values()) != snapshot.get("scope_count"):
        errors.append("snapshot counts do not exhaust scope")
    if snapshot.get("scope_count") != len(snapshot.get("row_dispositions", [])):
        errors.append("snapshot row dispositions do not exhaust scope")
    if snapshot.get("evidence_registry_hash") != registry_hash:
        errors.append("snapshot evidence registry hash drift")
    if snapshot.get("row_disposition_hash") != _hash(snapshot.get("row_dispositions", [])):
        errors.append("snapshot row disposition hash mismatch")
    if exact_live is not None and snapshot.get("release_sha") != exact_live:
        errors.append("snapshot release differs from exact live")
    if not isinstance(snapshot.get("supersedes"), list):
        errors.append("snapshot supersedes must be an array")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    parser.add_argument("--dispositions", required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--exact-live", required=True)
    args = parser.parse_args()
    errors = validate(_load(args.registry), _load(args.dispositions), _load(args.snapshot), args.exact_live)
    for error in errors:
        print(f"FAIL: {error}")
    if errors:
        raise SystemExit(1)
    print("PASS: GM governance artifacts are consistent")


if __name__ == "__main__":
    main()
