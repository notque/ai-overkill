# GM brilliant implementation workflow DAG

The operator-facing chain is `ADR -> RESEARCH -> COMPILE -> PLAN -> EXECUTE ->
VALIDATE -> OUTPUT`. The machine-readable source for nodes and dependencies is
`pipeline-spec.json`; this file explains execution and convergence.

## Graph

```text
S01
 ├─ S02 ─┬─ S03 ─┬─ S06 ─ S07 ─┐
 │       ├─ S04 ─┘              │
 │       ├─ S05                 ├─ S15 ─ S16 ─┬─ S17 ─┐
 │       └─ S08                 │             │       │
 └─ S09 ─ S10 ─┬─ S11 ─┐       │             └───────┼─ S23
               ├─ S12 ─┼─ S14 ─┘                     │
               └─ S13 ─┘                             │
S03/S04/S06/S15 ─ S18 ─ S19 ─┬─ S20 ────────────────┤
                               └─ S21 ────────────────┤
S03/S05/S07/S15 ─ S22 ───────────────────────────────┘
S23 ─┬─ S24 ─┐
     └─ S25 ─┴─ S26 ─ S27 ─ S28 ─ S29 ─ S30 ─ S31 ─ S32 ─ S33 ─ S34
```

Conditional nodes still participate in dependency convergence through a valid
`not_applicable` checkpoint. No consumer runs until every dependency is either
`complete` or validly `not_applicable`.

## Canonical phase mapping

| Canonical phase | Runtime stages |
| --- | --- |
| ADR | S01 |
| RESEARCH | S02-S14 |
| COMPILE | S15-S22 |
| PLAN | S23 |
| EXECUTE | S24-S26 |
| VALIDATE | S27-S33 |
| OUTPUT | S34 |

## Parallel lanes

- S03, S04, S05, and S08 may run after S02 in separate read-only evidence
  lanes. S06 consumes S03 and S04.
- S11, S12, and S13 may run after S10. S14 is their join.
- S17, S18/S19/S20/S21, and S22 may progress after their declared inputs.
- S24 and S25 may run in isolated worktrees after S23. They may not share a
  writer. S26 is the only integration join. One named integration owner also
  owns the release train; parallel waves deliver commits to that owner and do
  not deploy.
- S28 fans out independent perspectives, system, integration, and security
  reviews. The stage completes only after a converged verdict.

## Stop rules

Stop on unresolved authority, stale hashes, unknown dependencies, graph cycles,
missing joins, shared writers, invalid applicability, a failed CPU obligation,
critical review findings, failed release guards, wrong live SHA, unhealthy
services, or a route/asset contract failure. Preserve the last valid checkpoint
and report the canonical phase, active node, owner, evidence, next action, and
safe resume condition.

## Resume rules

Resume uses the exact pipeline spec hash and node input hashes. A changed input
invalidates that node and all descendants. Identical complete nodes are reused.
Failed nodes retry at most three times. A deploy resumes only through the target
repository's supported deploy or rollback command.

Before S30, acquire one project deploy coordinator/lock, reread the live SHA,
collect all ready accepted commits into one clean candidate, and broadcast the
lease. The same owner holds it through S33 or rollback. Any concurrent deploy,
stale base, changed candidate, or unaccounted ready commit stops the graph.

## Deterministic validation

The validator must prove:

1. Exactly 34 unique IDs S01-S34 exist.
2. Every dependency exists and the graph is acyclic.
3. Every node maps to exactly one canonical phase in nondecreasing phase order.
4. Every node declares owner, method owner, artifact, applicability, and
   consumer impact.
5. Every declared consumer is reachable, or is the terminal `none` marker.
6. All required nodes are `always`; only S10-S14, S24, and S25 are conditional.
7. Conditional evaluation satisfies the exact schema in `pipeline-spec.json`.
8. S26 converges S24/S25, S14 converges S11-S13, and S34 is the sole terminal.
9. S34 cannot complete until `scripts/validate-gm-governance.py` validates the
   registry, dispositions, canonical scope, full snapshot manifest, and exact
   live SHA and emits its receipt.
