# Feature Plan Phase

Transform a design document into a wave-ordered implementation plan with tasks assigned to domain agents. Phase 2 of the feature lifecycle (design > **plan** > implement > validate > release). This skill decomposes only -- it never implements code. Implementation is the responsibility of the implement phase.

## Instructions

### Phase 0: PRIME

1. Read and follow the repository CLAUDE.md before any other work.

2. Check feature state:
   ```bash
   python3 ~/.claude/scripts/feature-state.py status FEATURE
   ```
   Verify current phase is `plan` and `design` is in completed phases. A design document must exist before planning can begin -- there are no requirements to decompose without one, and skipping design guarantees a plan built on assumptions.

3. Load design artifact:
   ```bash
   ls .feature/state/design/*-FEATURE.md
   ```
   Read the design document.

4. Load L0, L1, and plan-phase context:
   ```bash
   python3 ~/.claude/scripts/feature-state.py context-read FEATURE L1 --phase plan
   ```

**Gate**: Design doc loaded. Feature in plan phase. All state operations use `python3 ~/.claude/scripts/feature-state.py` -- never manipulate state files directly.

### Phase 1: EXECUTE (Task Decomposition)

**Step 1: Identify Components**

From the design document, extract:
- Components to build/modify
- Dependencies between components
- Domain agents assigned in design

**Step 2: Create Wave-Ordered Tasks**

Group tasks by dependency wave -- Wave N must complete before Wave N+1 begins. Scope each task to 2-5 minutes of agent work; larger tasks get split, smaller tasks get merged. Do not collapse all tasks into a single wave -- that loses parallelization opportunities and masks true dependencies.

```markdown
# Implementation Plan: [Feature Name]

## Wave 1 (no dependencies)
### T1: [Task title]
- **Agent**: golang-general-engineer
- **Duration**: 3 min
- **Files**: /absolute/path/to/file.go
- **Operations**: [specific changes]
- **Verification**: `go build ./...` exits 0
- **Parallel-safe**: true (no file conflicts with T2)

### T2: [Task title]
- **Agent**: typescript-frontend-engineer
- **Duration**: 4 min
- **Files**: /absolute/path/to/component.tsx
- **Operations**: [specific changes]
- **Verification**: `npm run typecheck` exits 0
- **Parallel-safe**: true

## Wave 2 (depends on Wave 1)
### T3: [Task title]
- **Agent**: golang-general-engineer
- **Dependencies**: T1
- **Duration**: 5 min
- **Files**: /absolute/path/to/handler.go
- **Operations**: [specific changes]
- **Verification**: `go test ./...` exits 0
- **Parallel-safe**: false (shares files with T4)
```

**Step 3: File Conflict Analysis**

For each wave, check if any two tasks modify the same files. This analysis is not optional -- skipping it causes parallel execution to corrupt files when two agents write to the same path.

- If yes: mark `Parallel-safe: false` and add ordering constraint
- If no: mark `Parallel-safe: true`

**Step 4: Agent Routing Verification**

Every implementation task must specify which domain agent handles it. The agent assignment is authoritative -- do not override domain agent routing after assignment.

For each task, verify the assigned agent exists:
- Check against known agent triggers
- If uncertain, default to the closest domain agent
- Log routing decisions

**Step 5: Define Goal-Backward Success Criteria**

Before moving to validation, define "What must be TRUE when this is complete?" as **observable behaviors**, not implementation tasks. Success criteria are the verification target -- they define *when you're done*. Implementation tasks define *how you get there*. Conflating the two means "all tasks complete" can diverge from "goal achieved."

Each plan MUST include a `## Success Criteria` section with observable outcomes:

```markdown
## Success Criteria
<!-- What must be TRUE when this plan is fully implemented? -->
<!-- Each criterion must be observable/verifiable -- not an implementation task -->

1. [Observable behavior 1]
2. [Observable behavior 2]
3. [Observable behavior 3]
```

| Bad (implementation-focused) | Good (behavior-focused) |
|------------------------------|------------------------|
| "Implement resetPassword function" | "Users can reset their password via email link" |
| "Add database migration" | "The users table has a reset_token column with TTL" |
| "Write unit tests" | "All new functions have tests that pass, covering happy path and error cases" |
| "Refactor the handler" | "The /api/orders endpoint returns responses in under 200ms for 1000 concurrent users" |
| "Update the config" | "The service reads database credentials from environment variables, not hardcoded values" |

**Why behavior-focused**: An executor can complete every implementation task perfectly and still miss the goal if the tasks were wrong. Behavior-focused criteria catch that gap -- they're the acceptance test for the plan itself.

**Step 6: Apply Deep Work Rules to Every Task**

Every task in the plan must satisfy three rules. These exist because vague tasks create a hidden cost: the executor spends time interpreting the task instead of executing it, asks clarifying questions that block progress, or worse -- guesses wrong and builds the wrong thing.

**Rule 1: Concrete Actions Only**

No vague verbs ("align," "ensure," "handle," "improve") without specifying what concretely happens. If the task description doesn't tell the executor exactly what to do, it's not a task -- it's a wish.

| Rejected (vague) | Accepted (concrete) |
|-------------------|---------------------|
| "Align the API response" | "Add `created_at` field to the API response struct and populate it from the database timestamp" |
| "Ensure error handling" | "Wrap the `fetchUser` call in try/catch, return 404 for UserNotFound, 500 for all other errors" |
| "Handle edge cases" | "Add nil-check for `user.Profile` before accessing `user.Profile.Avatar`; return default avatar URL if nil" |
| "Improve performance" | "Add database index on `orders.user_id` column; batch the N+1 query in `listOrders` into a single JOIN" |

**Rule 2: Self-Contained Execution**

The executor should be able to complete the task from the action text alone, without needing to ask clarifying questions. Never reference external context ("as discussed," "per the meeting," "as mentioned") -- the agent has no access to that context. If a task requires context not present in the task description, that context must be added inline.

Test: Can a domain agent with no prior conversation context execute this task? If not, add the missing context.

**Rule 3: Observable Completion**

Each task has a way to verify it's done. If you can't describe how to check whether the task is complete, the task is too vague.

| Verifiable | Not Verifiable |
|------------|----------------|
| "Add route to router" -- check route table | "Improve code quality" -- no measurable criterion |
| "Add `user_id` column to orders table" -- check schema | "Clean up the module" -- what does "clean" mean? |
| "Return 429 when rate limit exceeded" -- test with curl | "Make it more robust" -- robust against what? |

**Gate**: Tasks decomposed with waves, agents, parallel safety flags, success criteria defined, and all tasks pass deep work rules.

### Phase 2: VALIDATE

Check gate: `python3 ~/.claude/scripts/feature-state.py gate FEATURE plan.plan-approval`

**Step 1: Requirements Coverage Gate**

Before running the rest of validation, verify that every stated requirement is covered by at least one task. An uncovered requirement is a **blocker**, not a warning -- partial coverage guarantees partial delivery. A plan that covers 8 of 10 requirements looks "mostly done" but delivers an incomplete feature. Catching gaps here costs minutes; catching them later costs hours or days.

The coverage check works as follows:

1. **Extract requirements** from the design document's goal statement and any requirements/acceptance-criteria sections
2. **Map each requirement** to the task(s) that address it
3. **Report unmapped requirements** as plan defects that must be resolved before proceeding

```markdown
## Requirements Coverage Matrix

| # | Requirement | Covered By | Status |
|---|-------------|------------|--------|
| R1 | [requirement from design] | T1, T3 | COVERED |
| R2 | [requirement from design] | T2 | COVERED |
| R3 | [requirement from design] | -- | UNCOVERED |
```

**Coverage must be 100%**. If any requirement is UNCOVERED:
- Add tasks to cover the missing requirement, OR
- Explicitly document why the requirement is deferred (with a follow-up ticket reference)
- Proceed to approval only after every requirement is covered or explicitly deferred with a follow-up ticket reference

**Step 2: Structural Validation Checklist**

Validation checklist:
- [ ] Every task has an assigned domain agent
- [ ] Every task has absolute file paths
- [ ] Every task has a verification command
- [ ] Every task is scoped to 2-5 minutes
- [ ] Wave ordering respects dependencies
- [ ] File conflicts are sequenced correctly
- [ ] Design components are fully covered by tasks
- [ ] Requirements coverage is 100% (from Step 1)
- [ ] Success criteria are behavior-focused, not implementation-focused
- [ ] Every task passes deep work rules (concrete actions, self-contained, observable completion)

**Step 3: Deep Work Rules Audit**

Scan every task in the plan against the three deep work rules:

| Rule | Check | Rejection Signal |
|------|-------|-----------------|
| Concrete actions | Does the task specify exactly what to do? | Vague verbs: "align," "ensure," "handle," "improve," "clean up" without concrete details |
| Self-contained | Can the assigned agent execute without asking questions? | References to "the discussion," "as mentioned," or context not in the task text |
| Observable completion | Is there a way to verify the task is done? | No verification command, no observable outcome described |

If any task fails a rule, rewrite it before proceeding. Do not approve plans with vague tasks -- they create execution debt that compounds across waves.

If gate is `human`: present plan to user for approval. Plan approval cannot be skipped unless explicitly configured with auto-approve.
If gate is `auto`: verify all checklist items pass.

**Gate**: Requirements 100% covered. All tasks pass deep work rules. Plan approved. Proceed to Checkpoint.

### Phase 3: CHECKPOINT

1. Save plan artifact:
   ```bash
   echo "PLAN_CONTENT" | python3 ~/.claude/scripts/feature-state.py checkpoint FEATURE plan
   ```

2. Advance:
   ```bash
   python3 ~/.claude/scripts/feature-state.py advance FEATURE
   ```

3. Suggest next step:
   ```
   Plan complete. Run /feature-lifecycle to continue to the implement phase.
   ```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| No design doc found | Design phase not completed | Run design phase first |
| Feature not in plan phase | Phase mismatch | Check status, advance if needed |
| Agent not found | Invalid agent assignment | Check agents/INDEX.json, use closest match |
