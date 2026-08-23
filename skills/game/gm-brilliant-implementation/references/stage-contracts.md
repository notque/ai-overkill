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

## Artifact ownership

Each stage's artifact name, owner, dependencies, consumer impact, and method
owners are in `pipeline-spec.json`. When a method-owner contract changes, update
the binding and validation fixture, not a copied checklist here.
