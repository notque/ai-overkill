---
name: subagent-driven-development
description: "Fresh-subagent-per-task execution with two-stage review gates."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
routing:
  triggers:
    - "subagent per task"
    - "fresh context execution"
    - "plan execution"
    - "execute plan with agents"
    - "fresh context per task"
  category: process
  pairs_with:
    - pair-programming
    - testing-agents-with-subagents
---

# Subagent-Driven Development Skill

Execute a plan with fresh implementers. Planning owns the plan format; this skill owns task dispatch and integration. Check requirements before code quality. Use the review lane in `skills/process/pr-workflow/SKILL.md` to choose direct or independent review; do not add another roster to a completed review.

## Instructions

### Phase 1: SETUP

**Step 1: Read plan and extract tasks**

Read the plan once. For each task, retain its full text, files, dependencies, and verification commands. Pass these inline rather than sending workers back to the plan.

**Step 2: Create TodoWrite**

Track all tasks as pending, in progress, or complete with TodoWrite or the harness's task tracker. Reuse the existing plan; do not create a second status artifact.

**Step 3: Gather scene-setting context**

Capture `git status`, project conventions from CLAUDE.md, relevant code patterns, dependencies, and setup requirements. Capture `BASE_SHA` with `git rev-parse HEAD` before the first implementer: it anchors the final integration diff. Include the context each worker needs in its dispatch.

**Step 4: Determine parallel vs sequential dispatch (scope-overlap check)**

```bash
python3 scripts/check-scope-overlap.py \
  --tasks '[{"id":"task-1","scope":["path/a.py"]},{"id":"task-2","scope":["path/b.py"]}]' \
  --human   # --check: exit 0 for no conflicts, 1 for conflicts
```

Each task has an `id` and `scope` path list. Directories include descendants; `"readonly": true` marks read-only tasks. Use the reported parallel groups, then account for dependencies: serialize overlapping writes and tasks that consume earlier results. Independent groups may run in parallel.

**Gate**: Full tasks, BASE_SHA, context, dependencies, and checked file scopes are ready.

### Phase 2: EXECUTE (Per-Task Loop)

**Step 1: Mark task in_progress**

Update the task tracker.

**Step 2: Dispatch implementer subagent**

Use `./implementer-prompt.md` with full task text, relevant context, deliverables, and checks. Resolve material questions from available evidence; ask the user only when their decision is needed.

Allocate one implementation worktree per task and reuse it for corrections. Before creating it, run the capacity guard from `worktree-agent`; at the hard threshold, reclaim accepted clean checkouts. Reviewers read the committed candidate with `git diff` or `git show` and need no worktree.

For executor-ready plans, append the template's **Executor-Ready Plans** contract. Keep the plan-creation SHA distinct from execution `BASE_SHA`. The implementer checks ancestry and context drift, runs each step's verify command, and stops for drift, two verification failures, scope violations, ambiguous or missing instructions, or test regression. The complete contract lives in `skills/process/planning/references/executor-ready-plan-template.md`; do not weaken it during dispatch.

Implementers understand the task, implement with TDD where appropriate, run relevant and required checks, self-review, and commit. Use `verification-before-completion` for verification rules. A still-valid passing check does not need repeating merely because the task reaches another phase.

**Step 3: Dispatch ADR compliance reviewer subagent**

Check the implementation against requirements and any applicable ADR: missing work, unwanted additions, and mismatches. For an independent review, use `./adr-reviewer-prompt.md`. For a direct review lane, the coordinator performs this check. Reuse review of the same candidate and scope.

Fix requirement failures before code-quality review. Reuse the task worktree and provide precise corrections. After three failed reviews at this stage, stop the loop, report the findings and attempted fixes, and request the decision needed to resolve the conflict.

**Step 4: Dispatch code quality reviewer subagent**

After requirements pass, check structure, meaningful tests, error handling, and bugs. For an independent review, use `./code-quality-reviewer-prompt.md`; otherwise review directly. Fix Critical and Important findings; Minor findings are optional. Recheck affected findings and behavior after fixes. After three failed reviews at this stage, stop and report the unresolved decision as in Step 3.

**Step 5: Mark task complete**

Record both results:

```text
Task [N]: [Title] -- COMPLETE
  ADR compliance: PASS
  Code quality: PASS
```

When no ADR applies, label the first result `Requirements: PASS` instead. Do not report an independent review if the check was direct. Continue with the next ready task.

After integration accepts the task, verify its worktree is clean and inactive, then run `git worktree remove -- <path>`. Preserve the branch until normal merged-branch cleanup proves it disposable.

**Gate**: Requirements and code quality pass; task status records completion.

### Phase 3: FINALIZE

**Step 1: Final integration review**

Review the combined `BASE_SHA..HEAD` diff for cross-task conflicts, duplicate utilities, incompatible patterns, and broken integration. Use independent review when the selected lane requires it or unresolved risk warrants it. Reuse completed review that covers this combined candidate. Run required integration checks and tests affected by combining the tasks.

**Step 2: Complete development workflow**

Follow the authorized completion path: `pr-workflow` for a PR, authorized merge, or keeping the branch. Do not ask again for an action already authorized.

**Gate**: Combined changes work together, required checks pass, and the requested delivery is complete.

## Error Handling

| Problem | Action |
|---|---|
| Worker lacks context | Supply the missing evidence or decision; include it in later dispatches where relevant. Resume the worker, or redispatch with complete context. |
| Review fails three times | Stop that loop, report findings and attempted fixes, and resolve the requirements or review criteria before retrying. |
| Workers conflict | Correct the declared scopes, rerun `check-scope-overlap.py`, resolve conflicts, serialize overlapping tasks, and rerun affected checks and review. |
| Executor-ready STOP | Preserve completed work, report the trigger and needed decision, and follow the executor contract rather than improvising. |
| Worker or session transfer | Use planning's `references/context-boundary.md`; use `session-handoff` for inline state and live processes, and planning pause/resume for plan artifacts. |

## References

- `implementer-prompt.md`: implementation dispatch and executor-ready contract.
- `skills/process/planning/references/executor-ready-plan-template.md`: plan schema, drift checks, verification, and STOP conditions.
- `adr-reviewer-prompt.md`: requirements review.
- `code-quality-reviewer-prompt.md`: code-quality review.
