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
  candidate; record included and explicitly deferred artifacts and commits.
- Validate every included artifact's complete prerequisite closure using its
  declared exact path-set/content-tree hashes or full normalized source-diff
  hash. A present top commit, matching subject, or clean cherry-pick is not
  proof that its parent prerequisites landed.
- Recompute the aggregate candidate closure after conflict resolution and
  immediately before staging. Reject missing paths, unexpected deletions,
  undeclared overlap, or a closure hash that differs from the lease record.
- Broadcast the active owner, live base, candidate SHA, environments, and lease
  expiry to every active lane.
- Reject a second staging/production attempt, stale base, changed candidate,
  unlisted ready artifact, incomplete prerequisite/file-set/diff closure,
  missing lock proof, or non-owner deploy.
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

## Conditional defect and evidence gate

- A reported defect enters implementation only with an exact-state
  reproduction record: release SHA, state-class fingerprint, environment,
  deterministic steps, expected/observed result, severity, privacy-safe
  evidence hash, and independent confirmation.
- `repair_now` is allowed only for reproduced state loss, blocked core action,
  duplicate write, sustained 5xx spike, truth-boundary breach, or accessibility
  blocker. The active incident owner, rollback pointer, bounded repair scope,
  and stop condition are mandatory.
- An actively observed production emergency may be contained before full
  reproduction only when containment is narrower than continued harm. It may
  not authorize feature work, and the incident record must be completed during
  containment.
- Human and volume-dependent rows remain `evidence_blocked` until their exact
  threshold is met. Zero observations are no signal. Qualitative rows require
  the declared unprompted protocol; analytics rows require the declared
  eligible denominator and privacy/small-cell guard.
- While blocked, the only allowed work is privacy-safe measurement,
  recruitment, protocol execution, or reproduction. UI, simulation, economy,
  copy, and progression changes are refused as speculative.
- Define each threshold once in a canonical evidence-gate registry. Every
  disposition cites its row ID plus registry hash. The bounded consumer
  manifest contains only consumer identity, artifact hash, row IDs, and the
  registry hash; its closed schema rejects copied threshold fields. Narrative
  reports link to a validated consumer receipt and are not parsed as prose.

## Canonical completion snapshot

- Preserve release history as evidence, but keep exactly one current snapshot.
- The snapshot records scope hash, exact release SHA, exhaustive status counts,
  row-disposition hash, evidence-registry hash, superseded snapshot hashes, and
  the verifier receipt.
- Counts must equal the declared scope cardinality. Each row appears exactly
  once. Evidence-gated questions retain their future trigger but cannot appear
  as valid unfinished implementation.
- A new release atomically replaces the current snapshot and links its
  predecessor. Appended prose, document position, or a heading such as “final”
  cannot override the machine-readable current snapshot.
