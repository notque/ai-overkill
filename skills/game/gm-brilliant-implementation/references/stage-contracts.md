# Stage contracts

Every runtime stage consumes versioned artifacts and emits one checkpoint. This
file defines orchestration schemas only; domain methods stay in their owning
skills and target-repository instructions.

## Checkpoint schema

```json
{
  "node_id": "S24",
  "spec_hash": "sha256:<64 lowercase hex>",
  "input_hashes": ["sha256:<64 lowercase hex>"],
  "output_hash": "sha256:<64 lowercase hex>",
  "owner": "project-coordinator-engineer",
  "status": "complete",
  "attempt": 1,
  "rollback_pointer": "git:<sha-or-null>",
  "applicability": {},
  "started_at": "RFC3339 timestamp",
  "completed_at": "RFC3339 timestamp"
}
```

`attempt` is 1-3. `output_hash` is null only before completion or on a valid
skip. A rollback pointer is required for any mutation and null for read-only
evidence. Timestamps describe execution but never determine simulation results.

## Applicability audit schema

The object has exactly nine fields:

| Field | Contract |
| --- | --- |
| `node_id` | One declared ID S01-S34 |
| `predicate_id` | `always`, `cpu_system_scope_present`, `backend_change_required`, or `frontend_change_required` |
| `result` | Boolean only |
| `evidence_hash` | Exact canonical source hash, `sha256:` plus 64 lowercase hex |
| `evaluated_spec_hash` | Exact current envelope spec hash |
| `owner` | Exact declared stage owner |
| `consumer_impact` | Non-empty declared downstream ID array, or `["none"]` for S34 |
| `status` | `ready`, `complete`, or `not_applicable` |
| `skip_reason` | null, or exactly `predicate_false` for a valid skip |

No additional fields are accepted. The deterministic Boolean functions and
complete rejection list live in `pipeline-spec.json` and are binding.

## Progress record

Expose only:

```json
{
  "canonical_phase": "EXECUTE",
  "active_node": "S24",
  "owner": "project-coordinator-engineer",
  "evidence": ["artifact path or hash"],
  "next_action": "bounded action",
  "resume_condition": "specific verified condition"
}
```

Do not expose the full graph as required operator state.

## Implementation envelope allowlist

- repository, branch, base SHA, candidate SHA;
- scope, version, schema version, active wave;
- spec and artifact hashes;
- links to one active short decision ADR per wave/system;
- approval-record link;
- rollback pointer.

It cannot hold architecture rationale, future-system decisions, or future-wave
authorization.

## Completion ledger allowlist

- stage status, dependencies, owners, timestamps;
- artifact links and hashes;
- current-scope approval;
- failures, attempts, stop reasons, rollback evidence;
- exact live verification;
- feedback aggregates and valid unfinished items.

## Approval record

Record authority source, approver or session identity, repository, branch and/or
exact SHA, environment, authorized action, scope, time, expiry or consumption,
and envelope version. It answers only the approval question. A scope, hash, or
environment change invalidates it. Every repository and release safeguard still
runs.

## Deploy lease record

Before S30, emit one record with exactly these fields:

```json
{
  "repository": "canonical repository identity",
  "environment_scope": ["staging", "production"],
  "integration_owner": "one agent or operator identity",
  "coordinator_or_lock": "project deploy coordinator or lock receipt",
  "acquired_at": "RFC3339 timestamp",
  "expires_at": "RFC3339 timestamp",
  "live_sha_at_acquire": "40 lowercase hex",
  "candidate_sha": "40 lowercase hex",
  "included_commits": ["40 lowercase hex"],
  "ready_artifacts": [{
    "artifact_id": "stable wave artifact ID",
    "source_base_sha": "40 lowercase hex",
    "source_head_sha": "40 lowercase hex",
    "prerequisite_commits": ["40 lowercase hex"],
    "closure_mode": "file_set or full_diff",
    "path_set_hash": "sha256:<64 lowercase hex> or null",
    "content_tree_hash": "sha256:<64 lowercase hex> or null",
    "source_diff_hash": "sha256:<64 lowercase hex> or null"
  }],
  "ready_artifact_manifest_hash": "sha256:<64 lowercase hex>",
  "candidate_closure_hash": "sha256:<64 lowercase hex>",
  "deferred_ready_commits": [],
  "broadcast_receipt": "artifact path or sha256 hash",
  "status": "active"
}
```

`file_set` sorts repository-relative paths bytewise, hashes that path list into
`path_set_hash`, and hashes each path plus its candidate blob or deletion marker
into `content_tree_hash`. `full_diff` hashes the normalized binary-capable diff
from `source_base_sha` through the full prerequisite closure to
`source_head_sha`. Exactly one mode's hash set is non-null. The manifest hash
covers every artifact record in stable `artifact_id` order. The candidate
closure hash covers the recomputed results for all included artifacts plus the
aggregate live-base-to-candidate diff, so conflict resolutions cannot reuse a
pre-resolution receipt.

The validator rejects missing or extra fields, multiple owners, an unproved
coordinator/lock, expiry at or before acquisition, a candidate absent from the
included set, duplicate commits, a live SHA that differs from the last read,
an unlisted ready commit, a deferred ready commit without an explicit stop
reason in the wave ledger, a ready artifact with a missing prerequisite commit
or path, any recomputed file-set/content/diff/manifest/candidate hash mismatch,
undeclared overlapping artifact paths without an approved aggregate resolution,
a candidate that changes after staging, or any staging/production attempt by a
non-owner. A top commit or commit subject never satisfies these checks by
itself. `status` may move from `active` only
to `released_after_live` or `released_after_rollback`, with the S33 or rollback
receipt. Approval and deploy lease are separate records.

## Artifact ownership

Each stage's artifact name, owner, dependencies, consumer impact, and method
owners are in `pipeline-spec.json`. When a method-owner contract changes, update
the binding and validation fixture, not a copied checklist here.
