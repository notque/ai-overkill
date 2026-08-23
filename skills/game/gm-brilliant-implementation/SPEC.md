# GM brilliant implementation specification

## Purpose

Provide one routable, resumable control plane for large 5 Star Booker GM
implementations that cross player design, simulation, CPU delegation,
architecture, UI, tests, release, and feedback.

## Scope

- Exactly seven canonical phases and 34 runtime stages.
- Large/multi-system/multi-wave GM implementation.
- Full CPU Systems Harmony for delegated or automatic systems.
- Backend/frontend convergence, focused verification, supported staging and
  production release, exact live proof, and feedback closure.

## Non-goals

- Small isolated bug, copy, style, test, or data fixes.
- Replacing project-local GM doctrine or existing domain skills.
- Defining deployment commands independent of the target repository.
- Becoming a mega-ADR, feature-state store, or blanket release authorization.

## Invariants

1. Target authority is loaded before diagnosis or mutation.
2. `project-coordinator-engineer` alone owns live runs.
3. Every stage binds an existing method owner and emits a typed checkpoint.
4. Required nodes cannot skip; conditional skips use deterministic declared
   predicates and the sole reason `predicate_false`.
5. The short typed chain and 34-node DAG validate together.
6. CPU systems preserve parity, deterministic precedence, promises/policies,
   soft failure, truthful receipts, control transfer, and a CPU-ignore path.
7. Implementation uses single-writer lanes and one integration convergence.
8. Authorization answers only the approval question; all safety guards run.
9. Completion requires exact live evidence and an honest feedback ledger.

## Success criteria

- Positive compound routes select the skill and named negative routes do not.
- Canonical chain passes the existing artifact validator.
- Runtime graph has 34 unique, acyclic, fully mapped nodes.
- All owner/skill bindings exist in the runtime manifest.
- Applicability schema rejects every malformed or inconsistent record described
  in `references/pipeline-spec.json`.
- Frontmatter, references, indexes, pipeline index, routing map, and mirrors pass
  deterministic validation.
- Structural evaluation earns grade B or higher.

## Authority

- Accepted ADR: `adr/gm-brilliant-implementation.md`
- Accepted hash: `sha256:ab9be2953f329f79875ba23a835e9637f1c9b8bc3dad97e2c65811951c446a4d`
- Machine contract: `references/pipeline-spec.json`
