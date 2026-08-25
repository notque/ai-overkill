---
name: gm-brilliant-implementation
version: 1.1.1
description: "Run the full evidence-to-live implementation workflow for large, multi-system, multi-wave, or CPU-delegated 5 Star Booker GM programs."
agent: project-coordinator-engineer
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Task, Skill]
routing:
  force_route: true
  triggers: [large GM implementation, large GM feature, multi-system GM feature, multi-wave GM program, GM systems overhaul, CPU systems harmony, Auto Book multi-system improvement, delegated GM systems program, large 5 Star Booker GM feature]
  not_for: "Small isolated GM bugs, copy/style changes, one focused test failure, isolated data corrections, or one-file local behavior with no new authority, cross-system data flow, version envelope, or release wave. Use quick, the target project-context skill, or the focused testing/review skill."
  pairs_with: [game-design, feature-lifecycle, workflow, verification-before-completion]
  complexity: Comprehensive
  category: game-development
---

# GM brilliant implementation

Run large 5 Star Booker GM programs from current-state evidence through design,
implementation, exact live release, and player-feedback closure. This skill is
a thin control plane. It sequences existing expertise and preserves artifacts;
it does not replace project doctrine, game design, implementation, or deploy
owners.

## Instructions

Apply the applicability gate, load authority in the required order, then run
the seven canonical phases and all 34 runtime stages under their declared
dependencies and gates.

## Applicability gate

Use this workflow only when the request is GM work and at least one condition is
true:

1. Two or more player-facing or simulation systems change in one coordinated
   release.
2. Delegated or automatic CPU authority changes across resources, promises,
   policies, deadlines, or attention.
3. The work is explicitly multi-wave.
4. Authority or versioned data flow changes across backend, frontend,
   persistence, and release surfaces.

A single word such as `GM`, `CPU`, `simulation`, or `5 Star Booker` does not
qualify. Route a small isolated fix through `quick`, the target project-context skill, or the
specific test/review skill.

## Required loading order

Before a run, read:

1. The target repository's complete governing instructions.
2. Its project-local GM implementation skill, when present.
3. Its project-local GM UI skill before UI, copy, or mobile decisions.
4. The available account or target-local project-context skill for repository
   and release context.
5. [workflow-dag.md](references/workflow-dag.md) and
   [pipeline-spec.json](references/pipeline-spec.json).
6. The phase-local reference named below only when that phase begins.

If a local authority conflicts with this orchestration layer, stop and name the
authoritative source. Never copy or silently override the domain rule.

## Reference Loading Table

| Signal | Load | Why |
| --- | --- | --- |
| Start or resume any run | `references/workflow-dag.md`, `references/pipeline-spec.json` | Verify graph, hashes, dependencies, and applicability before progress |
| Create or validate checkpoints, envelope, approval, or ledger | `references/stage-contracts.md` | Use the exact orchestration schemas and allowlists |
| S09 finds delegated or automatic systems | `references/cpu-systems-harmony.md` | Apply all ten canonical obligations once through the versioned CPU artifact |
| Enter testing, review, staging, production, or live verification | `references/quality-gates.md` | Preserve focused, adversarial, release, and exact-live gates |

## Operator contract

The operator sees seven canonical phases:

`ADR -> RESEARCH -> COMPILE -> PLAN -> EXECUTE -> VALIDATE -> OUTPUT`

The coordinator executes the 34 runtime stages underneath them. Status reports
show canonical phase, active stage, owner, evidence, next action, and safe resume
point. Do not make the operator manage the raw graph.

### Phase 1: ADR and authority

Run these stages in dependency order:

#### Stage S01: Authority and current state

Load repository authority, working-tree state, current live/release state, prior
artifacts, and the explicit scope. Record evidence as observed, documented,
measured, or inferred.

**Gate**: Authority, branch/worktree, current state, and scope are unambiguous.

### Phase 2: RESEARCH and player truth

Run or reuse current evidence for:

#### Stage S02: Player evidence
#### Stage S03: Core-loop extraction
#### Stage S04: Player psychology and Fogg
#### Stage S05: Attribution audit
#### Stage S06: Choice and stakes
#### Stage S07: Progression and economy
#### Stage S08: Era, privacy, and trust
#### Stage S09: CPU system inventory
#### Stage S10: CPU conflict matrix
#### Stage S11: CPU one-brain/two-hands parity
#### Stage S12: CPU precedence and promise/policy preservation
#### Stage S13: CPU failure, receipts, and control transfer
#### Stage S14: CPU cross-system simulation and player-feeling review

Use `game-design` for the complete player-path method. For S03, S04, and S05,
load Core Loop Extractor, Fogg Behavior Audit, and Attribution Audit packets.
Use [cpu-systems-harmony.md](references/cpu-systems-harmony.md) for S09-S14.
If S09 proves there is no CPU scope, S10-S14 may become `not_applicable` only
through the exact predicate and audit contract in the pipeline spec.

**Gate**: The evidence inventory, player loop, design risks, and every applicable
CPU obligation have a verdict, owner, and disproof or test route.

### Phase 3: COMPILE the implementation contract

Run:

#### Stage S15: ADR and version envelope
#### Stage S16: Architecture and data flow
#### Stage S17: Simulation, determinism, and CPU-ignore path
#### Stage S18: Mobile-360 information architecture
#### Stage S19: Distinctive visual design
#### Stage S20: Accessibility and reduced motion
#### Stage S21: Copy and anti-AI editing
#### Stage S22: Analytics and KPI guards

Use one short active decision ADR per wave or system. Bind architecture to
`architecture-deepening`, visual work to `distinctive-frontend-design`, copy to
the target's anti-AI editing method, and UI behavior to the target's GM UI
doctrine plus its vanilla-JS game frontend method when available. The implementation envelope and
ledger contain coordination facts and links, never architecture rationale or
future authorization.

**Gate**: The versioned contract has single writers, typed flows, deterministic
simulation, mobile/accessibility behavior, player-facing presentation, and
benefit plus welfare metrics.

### Phase 4: PLAN the wave

#### Stage S23: Wave and worktree plan

Use `feature-lifecycle`, `planning`, and `subagent-driven-development` to map
dependencies, file ownership, isolated worktrees, integration order, focused
tests, rollback, and release evidence. Parallel lanes must not write the same
file. Backend and frontend applicability comes only from S16's deterministic
surface map; at least one lane must run.

**Gate**: Every task has one owner, inputs, outputs, tests, stop rule, rollback,
and a conflict-free integration edge. Name exactly one integration and deploy
coordinator for the whole active release train. Parallel waves may prepare
commits, but they may not stage or deploy independently.

### Phase 5: EXECUTE and converge

Run:

#### Stage S24: Backend implementation
#### Stage S25: Frontend implementation
#### Stage S26: Integration

Use test-driven development where behavior changes. Each lane commits only its
owned files. Converge in one clean integration branch/worktree, preserve user
changes, and reject stale-input checkpoints. A conditional lane may skip only
with the declared false predicate and a complete audit record.

Before S26 completes, the integration owner rereads the live SHA, inventories
every ready wave commit, and rebases or cherry-picks the accepted set into one
clean candidate. Record included and deferred commits, then validate the
complete ready-artifact closure. A commit name or cherry-picked tip is not
closure proof. For every ready artifact, compare the candidate with its
declared prerequisite commit closure and either its exact file-set/content hash
or its full source-diff hash. Reject a candidate that omits a prerequisite
parent's files or state, even when a later child commit applies cleanly. A ready
parallel wave cannot start a competing release from the same or an older live
base.

**Gate**: The integrated commit implements the accepted envelope, preserves the
CPU-ignore path and project doctrine, and contains no unrelated files.

### Phase 6: VALIDATE and release

Run:

#### Stage S27: Focused tests
#### Stage S28: Adversarial perspective, system, and security reviews
#### Stage S29: Predeploy game-design gate
#### Stage S30: Emergency staging
#### Stage S31: Staging verification
#### Stage S32: Production deployment
#### Stage S33: Exact live verification

S28 fans out independent `parallel-code-review`, `multi-persona-critique`,
system, integration, and `security-review` lenses, then converges findings.
S29 applies Core Loop Extractor, Craft Critique, Attribution Audit, and Fogg
Behavior Audit to the implemented moments and fixes concrete misses before
release. Use only the target repository's supported deploy and rollback paths.

Before S30, the named integration owner must acquire the target project's
deploy coordinator/lock and emit the deploy-lease record defined in
[stage-contracts.md](references/stage-contracts.md). The owner then rereads the
live SHA, collects all ready accepted commits, rebuilds one clean integration
candidate when the base changed, and broadcasts the candidate SHA and lease.
Only that owner may run staging or production while the lease is active.
Reject concurrent attempts, a stale base, an unlisted ready commit, a candidate
SHA mismatch, an expired lease, an incomplete ready-artifact/file-set closure,
or a lock the project cannot prove it holds. Recompute the candidate closure
after any integration conflict resolution and immediately before staging.
Release the lease only after exact-live verification or completed rollback.

Explicit owner authorization or a valid fast-development approval record can
satisfy the approval question without another pause. It never disables branch,
privacy, test, rollback, deploy, exact-SHA, service, health, asset, or route
guards. See [quality-gates.md](references/quality-gates.md).

**Gate**: Production serves the exact intended SHA; services, health, assets,
routes, and authorized contracts are verified, with rollback evidence present.

### Phase 7: OUTPUT and learn

#### Stage S34: Feedback, retro, and completion ledger

Collect a privacy-safe post-live delta, distinguish new regressions from prior
feedback, retain every valid unfinished item, record metric and welfare guards,
and call the learning skill. Call the Skill tool with `retro`. Report exact live SHA, evidence, decisions, changes, tests,
release proof, feedback window, and next wave.

For conditional defects and human/volume-dependent evidence, use the binding
incident and evidence-disposition records in `references/stage-contracts.md`.
Never turn a zero-volume signal, an unreproduced report, or an unmet research
threshold into speculative product work. A severe repair-now lane opens only
after the exact-state reproduction record proves its trigger, except for an
actively observed production emergency where containment is the narrowest safe
action and the record is completed during containment.

Store every threshold once in the run's canonical evidence-gate registry.
Disposition records and the bounded consumer manifest cite the registry hash
and row IDs without copying threshold fields. Narrative reports link to a
validated consumer receipt; the validator does not parse arbitrary prose.
Before closure, emit one canonical
completion snapshot after the append-only history and validate that its row
counts exhaust the scope exactly. A later release replaces the current snapshot
and links the prior snapshot; it does not add another competing authority block.
Runs resumed from a pre-1.1 checkpoint must rerun S34 and emit the 1.1 registry,
scope, disposition, and snapshot-manifest artifacts before completion.

**Gate**: The ledger is complete, narrow, hash-linked, honest about every
unfinished or unmeasured claim, and every conditional row has a machine-checkable
trigger plus refusal disposition. The canonical snapshot and reference-only
consumer manifest validate. The run is complete.

## Checkpoint and resume pattern

After every stage, write the stage contract from
[stage-contracts.md](references/stage-contracts.md): input/output hashes, owner,
status, attempt count, applicability audit, and rollback pointer. Resume only
when the spec and inputs still match. Retry a failed stage at most three times;
otherwise stop with preserved evidence and a concrete next action.

## Preferred patterns

| Prefer | Avoid |
| --- | --- |
| Existing skill owns method; this skill owns handoff | Copying domain checklists into this skill |
| One short ADR per active wave/system | A pipeline mega-ADR |
| Closed deterministic applicability | Free-form `not applicable` claims |
| Single-writer lanes, one convergence point | Agents editing a shared file concurrently |
| Exact live SHA and route evidence | “Deploy succeeded” without proof |
| Truthful bounded CPU receipts | Automation claiming more than it applied |

## Error handling

### Authority or doctrine conflict

Stop. Name both sources, identify the higher authority, preserve artifacts, and
route the conflict to the owning skill or repository decision process.

### Applicability record invalid

Do not skip or execute the node. Report the rejected field, source artifact,
spec hash, and owning stage. Repair the source contract, then reevaluate.

### Review or release gate fails

Do not declare completion. Fix within the same accepted envelope when safe;
otherwise rollback through the canonical path and record a new bounded wave.

### Resume input is stale

Invalidate the affected node and all consumers. Reuse only checkpoints whose
input, output, and spec hashes still match.

## References

- [Pipeline specification](references/pipeline-spec.json)
- [Workflow DAG](references/workflow-dag.md)
- [Stage contracts](references/stage-contracts.md)
- [CPU Systems Harmony](references/cpu-systems-harmony.md)
- [Quality gates](references/quality-gates.md)
- [Anti-rationalization core](../../shared-patterns/anti-rationalization-core.md)
- `skills/game/game-design/SKILL.md`
- `skills/process/feature-lifecycle/SKILL.md`
- `skills/workflow/SKILL.md`
- `agents/project-coordinator-engineer.md`
