# Design brief: gm-brilliant-implementation

## Decision

- **Complexity tier:** Comprehensive
- **Runtime agent:** `project-coordinator-engineer`
- **Creation agent:** `pipeline-orchestrator-engineer`
- **User-invocable:** true
- **Accepted ADR:** `adr/gm-brilliant-implementation.md`
- **Accepted ADR hash:** `sha256:ab9be2953f329f79875ba23a835e9637f1c9b8bc3dad97e2c65811951c446a4d`

The user explicitly requires a first-class skill. The component is a thin GM
control plane: it owns stage order, typed artifacts, gates, checkpoints,
cross-system convergence, and release evidence. Existing skills and the target
repository remain the method authorities.

## Discovery result

The runtime manifest contained 184 routable components: 113 skills, 43 agents,
and 28 pipelines. No existing component owns a server-authored GM feature from
player evidence through game-design diagnosis, CPU-system harmony,
implementation, exact live release, feedback, and completion ledger.

- `game-design` owns diagnosis and design decisions.
- `feature-lifecycle` owns a generic feature lifecycle.
- `game-pipeline` owns browser-game scaffold/assets/audio/QA/deploy concerns,
  not server-side GM logic.
- Project-local `gm-implementation` owns 5 Star Booker implementation doctrine.
- The target/account project-context skill owns repository and deployment context.
- `workflow` owns general DAG execution.

The independent research and ADR consultation gates confirmed the new skill's
boundary and corrected runtime ownership: `pipeline-orchestrator-engineer`
creates pipelines; `project-coordinator-engineer` runs this accepted DAG.

## Structure

The operator-facing typed spine is:

`ADR -> RESEARCH -> COMPILE -> PLAN -> EXECUTE -> VALIDATE -> OUTPUT`

It expands to exactly 34 runtime stages defined in `references/workflow-dag.md`
and `references/pipeline-spec.json`. The canonical chain and detailed DAG are
validated together but remain separate representations.

## Required references

- `references/workflow-dag.md`
- `references/pipeline-spec.json`
- `references/stage-contracts.md`
- `references/cpu-systems-harmony.md`
- `references/quality-gates.md`

## Hardcoded behavior

- Load target-repository instructions and project-local GM skills first.
- Route only compound large/multi-system/multi-wave GM work.
- Keep small isolated work on focused routes.
- Run all required nodes; skip a conditional node only through its declared,
  deterministic false predicate and audited `predicate_false` record.
- Preserve one-brain/two-hands parity and a CPU-ignore path.
- Use one short active decision ADR per wave/system; never a mega-ADR.
- Use isolated single-writer implementation lanes and converge once.
- Treat scoped owner authorization as the approval record only, never as a
  release-safeguard bypass.
- Finish with exact live evidence and a feedback/completion ledger.

## Approval record

The owner explicitly requested creation, routing, commit, and push. That
directive satisfies the formal create-new decision and workflow confirmation.
