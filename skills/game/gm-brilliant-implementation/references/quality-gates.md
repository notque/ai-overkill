# Quality gates

## Before implementation

- Target instructions and local GM skills loaded completely.
- Current code, live state, player evidence, and prior feedback inventoried.
- One active short ADR and version envelope accepted.
- DAG/spec hashes match and applicability validates.
- CPU harmony passes when applicable.
- Single writers and worktree boundaries are explicit.

## Focused implementation gates

- Behavior-changing work has contract tests or a characterized baseline.
- Backend and frontend use one canonical rule/grade/result source.
- Deterministic seed/order/replay and CPU-ignore paths remain valid.
- 1981/2026 or target era goldens cover historical boundaries when relevant.
- 360px mobile, keyboard, semantics, contrast, and reduced motion are checked.
- Player-facing copy passes the target anti-AI/no-em-dash doctrine.
- Analytics measure benefit and harm; vanity metrics alone never pass.

## Adversarial review gate

Run independent code/perspective, system/integration, and security/privacy
lenses. Converge duplicates and classify findings. Any critical issue blocks.
Important issues must be fixed or explicitly returned to the active short ADR.

## Predeploy game-design gate

Apply these game-design packets to the implemented player moments:

1. Core Loop Extractor: cue to next intention still closes.
2. Craft Critique: presentation supports the promised fantasy.
3. Attribution Audit: players can connect cause, result, and next choice.
4. Fogg Behavior Audit: motivation, ability, and prompt align without coercion.

Fix concrete misses before deployment. Record observed/documented/measured/
inferred evidence and the smallest loop test.

## Release authorization

A valid scoped owner or fast-development approval record can satisfy the human
approval question. It cannot skip branch, worktree, privacy, focused tests,
protected-repository, rollback, canonical deploy, exact-SHA, service, health,
asset, or route guards.

## Single deploy lease

- One integration owner holds one target-project deploy coordinator/lock for
  staging and production.
- Immediately before acquisition, reread live SHA and every ready wave commit.
- Rebase or cherry-pick the accepted ready set into one clean integration
  candidate; record included and explicitly deferred commits.
- Broadcast the active owner, live base, candidate SHA, environments, and lease
  expiry to every active lane.
- Reject a second staging/production attempt, stale base, changed candidate,
  unlisted ready commit, missing lock proof, or non-owner deploy.
- Keep the lease through exact-live verification or rollback, then release it
  with the corresponding receipt.

## Staging and production proof

- Use only the target repository's supported deploy path.
- Require the valid active deploy-lease record before staging or production.
- Staging serves the intended SHA and passes health/assets/routes/contracts.
- Production deploys the exact staged candidate unless the repository contract
  explicitly rebuilds and proves equivalence.
- Verify release marker, service health, public assets, public/auth-gated routes,
  timing or response contracts, and rollback pointer.
- On failure, stop or rollback through the canonical path; never hand-edit live
  state without mirroring through the repository's emergency doctrine.

## Completion gate

Record exact live SHA, checks, review verdicts, release evidence, feedback
baseline/window, unresolved items, and next-wave dependencies. A missing
measurement remains `missing evidence`, never `done`.
