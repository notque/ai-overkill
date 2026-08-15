---
user-invocable: false
description: "Three-phase task orchestration: BRAINSTORM, WRITE-PLAN, EXECUTE-PLAN."
success-criteria:
  - "Plan validated by the planning umbrella's check intent before execution"
  - "All plan tasks completed and marked done"
  - "Full test suite passes after execution"
  - "No TODO/FIXME markers in new code"
  - "Deliverables match stated goal in task plan"
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Task
routing:
  triggers:
    - orchestrate
    - complex task
    - plan and execute
    - break this down
    - multi-step implementation
  pairs_with:
    - planning
    - research-pipeline
  complexity: Complex
  category: meta
---

# Workflow Orchestrator Skill

## Purpose

Orchestrate complex multi-step software development tasks using the BRAINSTORM / WRITE-PLAN / EXECUTE-PLAN pattern. Breaks ambiguous or complex work into well-defined, verifiable subtasks with clear progress tracking.

## Instructions

### Three-Phase Workflow Overview

1. **BRAINSTORM**: Refine requirements, explore approaches, select best option
2. **WRITE-PLAN**: Create detailed task breakdown with verification steps
3. **VALIDATE-PLAN**: Run the planning umbrella's check intent with bounded revision loop
4. **EXECUTE-PLAN**: Execute tasks sequentially or in parallel, verify each step

### Phase 1: BRAINSTORM

**PHASE GATE: Proceed to WRITE-PLAN phase only after:**
- [ ] Requirements have been clarified (or user confirmed they're clear)
- [ ] At least 2 approaches have been considered
- [ ] Selected approach has documented rationale
- [ ] Constraints and dependencies are identified

**Purpose**: Transform ambiguous requirements into clear, actionable plans through Socratic refinement. This phase prevents rework by establishing shared understanding before any code is written.

**Constraint**: Only create tasks for work that's directly requested. Keep plans simple and focused. No speculative features or flexibility that wasn't asked for. This prevents scope creep and wasted tokens.

#### Step 1: Understand Requirements

Ask clarifying questions **one at a time** to understand:
- What is the actual problem being solved?
- What are the success criteria?
- What constraints exist (time, resources, compatibility)?
- What parts of the system are affected?

Prefer **multiple choice questions** when possible -- easier to answer than open-ended. Open-ended only when truly necessary.

**Example Multiple Choice**:
```
How should auth tokens be stored?
1. In-memory only (simpler, lost on restart)
2. Database (persistent, more setup)
3. Redis (fast, external dependency)
```

#### Step 2: Identify Constraints and Dependencies

Document:
- **Technical Constraints**: Language versions, library compatibility, API limitations
- **System Dependencies**: Files that must be modified together
- **External Dependencies**: Services, databases, APIs that must be available
- **Compatibility Requirements**: Backward compatibility, migration needs

**Constraint**: Read and follow repository CLAUDE.md files before orchestration. Project instructions override default behaviors. This ensures alignment with local norms.

#### Step 3: Generate Multiple Approaches

Brainstorm 2-3 approaches with pros, cons, complexity, and risk for each.

```markdown
## Approach 1: [Name]
**Pros**: [List advantages]
**Cons**: [List disadvantages]
**Complexity**: [Low/Medium/High]
**Risk**: [Low/Medium/High]
```

#### Step 4: Select Best Approach

Choose the approach that best balances complexity vs. benefit, risk vs. needs, time vs. deadline, and maintainability vs. short-term gains.

Document the selected approach, rationale for choosing it, how it addresses constraints, and why alternatives were rejected.

**Gate**: Requirements clarified, at least 2 approaches considered, selected approach has documented rationale, and constraints identified. Proceed to WRITE-PLAN.

### Phase 2: WRITE-PLAN

**PHASE GATE: Proceed to VALIDATE-PLAN phase only after:**
- [ ] All tasks have absolute file paths (no relative paths)
- [ ] All tasks have verification commands
- [ ] All tasks are scoped to 2-5 minutes
- [ ] Dependencies between tasks are documented
- [ ] Plan has been saved to a file

**Purpose**: Break down the selected approach into executable, verifiable tasks. This phase produces a concrete artifact that can be validated before execution.

**Constraints**:
- Every task must include a verification step that confirms successful completion
- Individual tasks must be scoped to 2-5 minutes of work (break larger work into multiple tasks)
- Tasks with dependencies must explicitly list prerequisite task IDs
- All tasks must specify absolute file paths, never relative paths or wildcards
- Save all plans to `plan/active/{plan-name}.md` instead of temp files. This enables plan discovery, tracking, and cleanup workflows.

**Why**: Time-bounded tasks ensure focus. Absolute paths enable independent subagent execution. Verification commands prevent silent failures. Explicit dependencies catch circular dependencies before execution.

#### Step 1: Create Task Breakdown

Break work into tasks that are:
- **Atomic**: Each task does ONE thing
- **Time-Bounded**: 2-5 minutes per task
- **Verifiable**: Has clear success/failure criteria
- **Explicit**: Specifies exact file paths and operations

**Task format** (use this in plans):

```markdown
### T1: Create database migration for user preferences
- **Duration**: 3 minutes
- **Dependencies**: None
- **Files**: `/absolute/path/to/migrations/0001_user_preferences.py`
- **Operations**: Create migration file, add model, define schema
- **Verification**: `python manage.py check` exits 0
```

#### Step 2: Identify Task Dependencies

Create dependency graph. Tasks with no dependencies can potentially run in parallel. Tasks must wait for all dependencies to complete. Circular dependencies are not allowed.

```
T1 -> T2 -> T4
  \-> T3 -/
```

**Note on parallelization**: If independent task groups exist, note them in the plan. Suggest parallel execution mode to user if it would provide meaningful speedup. This is optional behavior (OFF by default) -- sequential is safer.

#### Step 3: Define Verification Steps

Each task must have:
- **Command**: Exact command to verify success
- **Expected Output**: What should happen if successful
- **Success Criteria**: How to determine pass/fail

#### Step 4: Document the Plan

Save plans to the `plan/active/` directory using kebab-case descriptive names.

**Plan format**:

```markdown
# Plan: [Descriptive Title]

**Status**: Draft
**Created**: YYYY-MM-DD
**Priority**: [Low/Medium/High]
**Complexity**: [Low/Medium/High]

## Summary
[One-sentence description of the work]

## Context
[Why this work is needed]

## Requirements
- [ ] Requirement 1
- [ ] Requirement 2

## Implementation Tasks

### T1: [Task title]
- **Duration**: X minutes
- **Dependencies**: None
- **Files**: `/absolute/path/to/file.py`
- **Operations**: [Specific operations]
- **Verification**: `command` exits 0

### T2: [Task title]
- **Duration**: X minutes
- **Dependencies**: T1
- **Files**: `/absolute/path/to/file.py`
- **Operations**: [Specific operations]
- **Verification**: `command` exits 0

## Dependency Graph
T1 -> T2

## Notes
(Add notes during execution)
```

**Save location**: `plan/active/{descriptive-name}.md`

**Gate**: All tasks have absolute file paths, verification commands, 2-5 minute scope, documented dependencies, and plan saved to file. Proceed to VALIDATE-PLAN.

### Phase 2.5: VALIDATE-PLAN

**PHASE GATE: Proceed to EXECUTE-PLAN phase only after:**
- [ ] Plan-checker has evaluated the plan
- [ ] All blocker-severity findings are resolved (or documented as accepted risks after 3 revision iterations)
- [ ] Context-budget estimate confirms plan is achievable within ~50% of remaining context

**Purpose**: Catch plan-level defects before they waste an execution cycle. A poorly structured plan -- vague tasks, missing dependencies, implicit ordering -- produces predictable execution failures. Validating before execution is cheaper than discovering problems mid-implementation.

**Constraint**: Monitor estimated context usage and adjust execution behavior by zone. Plans should target completion within 50% of context. Why: context exhaustion mid-execution produces silently degraded output with no recovery path.

| Context Used | Zone | Behavior |
|-------------|------|----------|
| 0-30% | PEAK | Full execution, all quality gates, comprehensive verification |
| 30-50% | GOOD | Full execution, all quality gates. Target plan completion within this zone. |
| 50-70% | DEGRADING | Prioritize remaining critical tasks. Skip optional verification. Warn user. |
| 70%+ | POOR | Complete only in-progress task. Create handoff artifacts ([Session Handoff](../../adr/069-session-handoff-system.md)). Stop accepting new tasks. |

Zone transitions trigger explicit log entries: "Entering DEGRADING zone at ~52% context usage. 3 tasks remaining. Prioritizing critical path." These zones are planning heuristics based on estimated usage, not precise measurements.

#### Step 1: Run Plan Validation

Invoke the [planning umbrella's check intent](../../planning/references/check.md) against the saved plan. The check intent evaluates the plan across its verification dimensions, including:
- Every task has a clear completion criterion
- Task dependencies are explicit (no implicit ordering)
- No task depends on an artifact that no prior task produces
- Scope is bounded (no open-ended tasks like "improve performance")
- Plan is achievable within ~50% of remaining context (context-budget check)

The check intent produces a PASS/BLOCK verdict with structured findings.

#### Step 2: Bounded Revision Loop

If the check intent finds issues:

```
CHECK -> issues found -> REVISE plan -> CHECK again -> max 3 iterations
```

1. Review each finding (dimension, severity, description, fix hint)
2. Revise the plan to address blocker-severity findings first, then warnings
3. Re-run the check intent on the revised plan
4. Repeat up to **3 iterations maximum**

If issues persist after 3 iterations, log the remaining issues as accepted risks in the plan's Notes section and proceed to execution. An imperfect plan executed is better than a perfect plan never started. The 3-iteration limit prevents infinite planning loops -- if a plan cannot pass validation in 3 revisions, the issues are likely structural and will surface clearly during execution.

#### Step 3: Log Validation Outcome

Record in the plan file:
- Check intent verdict (PASS / PASS-WITH-WARNINGS / BLOCK-OVERRIDDEN)
- Number of revision iterations used
- Any accepted risks from unresolved findings

**Gate**: Plan-checker evaluated, all blocker-severity findings resolved or documented as accepted risks after 3 iterations, and context-budget estimate confirms achievability. Proceed to EXECUTE-PLAN.

### Phase 3: EXECUTE-PLAN

**PHASE GATE: Mark workflow complete only after:**
- [ ] All tasks have been attempted
- [ ] All verification commands have been run
- [ ] All passing tasks are logged with status
- [ ] Any failures have been documented with root cause
- [ ] Regression checks have passed for prior task groups
- [ ] Final status report has been generated

**Purpose**: Execute tasks from the plan, verify each step, handle blockers. Each task is verified against its success criteria, and cross-task regressions are detected.

**Constraints**:
- After each task execution, report completion status and any blockers encountered
- Every autonomous deviation is logged with: the rule number that authorized it, what was changed, and why
- Report facts without self-congratulation. Show command output rather than describing it. Be concise but informative.
- Report progress after each task completion
- Detect and report blockers immediately when encountered

#### Step 1: Load and Validate Plan

Read the plan from `plan/active/{plan-name}.md` and verify:
- All tasks have absolute file paths
- All tasks have verification commands
- Dependencies are valid (no circular refs)
- Plan status is "Draft" or "In Progress"
- Plan validation has been completed via the planning umbrella's check intent (Phase 2.5)

Update plan status to "In Progress".

#### Step 2: Execute Tasks in Order

**For each task**:
1. **Check Dependencies**: Verify all prerequisite tasks completed successfully
2. **Report Start**: Log task start and current context-budget zone
3. **Execute Operations**: Perform the task operations
4. **Apply Deviation Rules**: If unexpected issues arise during execution, classify by rule number (1-3: auto-fix with logged justification; 4: stop and ask user). See Deviation Rules below.
5. **Run Verification**: Execute verification command
6. **Evaluate Result**: Check against success criteria
7. **Report Completion**: Log task status and overall progress (e.g., "2/6 tasks complete")

**Deviation Rules** (numbered rules governing what the orchestrator may do autonomously during execution versus what requires human approval. Why: without explicit boundaries, the orchestrator either over-escalates (asking about typos) or under-escalates (silently making architectural changes)):

| Rule | Category | Action | Example |
|------|----------|--------|---------|
| 1 | Bug fix | Auto-fix | Typo in variable name, missing import, off-by-one error |
| 2 | Missing critical functionality | Auto-add if clearly required by the plan | A function referenced in the plan but not yet created |
| 3 | Blocking issue | Auto-fix environmental/dependency problems | Missing package, wrong version, permission issue |
| 4 | Architectural change | **STOP and ask user** | Changing a data model, adding a new service, altering an API contract |

Rules 1-3 are autonomous -- the orchestrator handles them without user input. Rule 4 is a hard stop. Every autonomous deviation is logged with: the rule number that authorized it, what was changed, and why.

#### Step 3: Regression Gate

Before verifying the current task group, re-run verification checks for prior completed task groups. Why: Task 5 may silently break what Task 3 built. Independent per-task verification misses cross-task regressions that compound into harder-to-diagnose failures later.

**Regression check protocol**:

```
After Task Group 1 executes -> verify Group 1
After Task Group 2 executes -> verify Group 1 (regression) -> verify Group 2
After Task Group 3 executes -> verify Groups 1+2 (regression) -> verify Group 3
```

**When a regression is detected**:
1. Identify which task in the current group broke which prior task's verification
2. Attempt autonomous repair on the current group's task, constrained to not re-break the prior task. Apply Deviation Rules to classify the fix (typically Rule 1: bug fix).
3. If repair fails after the repair budget (default: 2 attempts), ESCALATE with the specific regression identified -- include both what broke and what caused it.

**Scaling for large plans**: Full regression checking on every prior group is the default for plans with 5 or fewer task groups. For plans with more than 5 groups, check only the immediately preceding group to avoid consuming excessive context on re-verification. The tradeoff: less thorough regression detection, but more context available for actual execution.

**Task groups**: In sequential execution, each task is its own group. When wave-based parallel execution is enabled, each wave forms a task group. Regression checks happen between groups, not between individual tasks within a group.

#### Step 4: Handle Verification Failures

If verification fails:

1. **Report Failure**: Document the error output and analysis
2. **Classify by Deviation Rule**: Determine if the failure falls under Rule 1-3 (auto-fix) or Rule 4 (stop and ask). This classification happens before strategy selection -- if it's Rule 4, ESCALATE immediately regardless of repair budget.
3. **Select Strategy** (decision tree, for Rule 1-3 failures only):
   - **RETRY**: Error is specific and actionable (typo, missing import, wrong arg) -- fix and re-verify. Consumes 1 repair attempt.
   - **DECOMPOSE**: Retry failed and task has independent sub-parts -- break into sub-tasks (in-memory only, never modify the plan file). Consumes 1 repair attempt.
   - **PRUNE**: Task is genuinely unnecessary or already satisfied by prior task -- skip with documented justification.
   - **ESCALATE**: Error is vague/systemic, budget exhausted, or sub-tasks also failed -- ask user. Mandatory when repair budget (default: 2 attempts) is exhausted.
4. **Log Deviation**: Record every repair action (rule number, strategy, error, outcome, attempts consumed) in the execution summary.

#### Step 5: Handle Blockers

When encountering a blocker that cannot be automatically resolved, document the blocker type, details, and impact on downstream tasks. Ask user for resolution before proceeding.

#### Step 6: Report Final Status

After all tasks attempted, report:
- Total tasks, completed, failed, blocked counts
- Per-task summary with status
- Deviation log (all autonomous fixes with rule numbers)
- Regression check results (pass/fail per group)
- Context-budget zone at completion
- Overall execution result

After successful execution, prompt user about plan lifecycle:
1. **Archive** to `plan/completed/YYYY-MM/` -- work is done
2. **Keep active** -- more work needed or waiting for merge
3. **Abandon** to `plan/abandoned/` -- decided not to proceed (ask for reason)

**Gate**: All tasks attempted, all verification commands run, passing tasks logged, failures documented with root cause, regression checks passed, and final status report generated. Workflow complete.

## Error Handling

### Verification Failure Strategy

**Level 1: Auto-Fix** (Deviation Rules 1-3):
- Missing import, syntax error, simple typo (Rule 1)
- Missing function clearly required by the plan (Rule 2)
- Dependency or environment issue (Rule 3)
- Fix and retry verification

**Level 2: Rollback** (if changes broke something):
- Execute rollback commands from task definition
- Restore to pre-task state

**Level 3: User Escalation** (Deviation Rule 4, or budget exhausted):
- Architectural changes require explicit user approval
- Document the failure and what was attempted
- Request user guidance

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| Task verification timeout | Verification command took >2 minutes | Break task into smaller subtasks |
| Circular dependency detected | Tasks form a dependency cycle | Restructure tasks to remove cycle |
| File path is relative | Task used `./` path | Convert to absolute path |
| Task duration exceeds 5 min | Task too large for atomic execution | Break into multiple smaller tasks |
| Check-intent blocker after 3 revisions | Plan has structural issues that revision cannot fix | Log as accepted risk, proceed with awareness, or ask user to restructure |
| Regression detected | Current task broke prior task's verification | Identify the breaking change, repair without re-breaking prior task |
| Context entering DEGRADING zone | >50% context consumed with tasks remaining | Prioritize critical-path tasks, skip optional verification, warn user |
| Context entering POOR zone | >70% context consumed | Complete only in-progress task, create handoff artifacts, stop |

### Error: Task verification timeout
**Cause**: Verification command took longer than 2 minutes to complete
**Solution**: Break the task into smaller subtasks with faster verification commands. If the verification inherently requires long execution (e.g., full test suite), increase timeout or switch to a smoke-test verification for the individual task.

### Error: Circular dependency detected
**Cause**: Tasks form a dependency cycle where Task A depends on Task B and Task B depends on Task A (directly or transitively)
**Solution**: Restructure the dependency graph to remove the cycle. Identify which task can be executed first with partial inputs, or extract the shared dependency into a new prerequisite task.

### Error: Check-intent blocker persists after 3 revisions
**Cause**: Plan has structural issues (vague scope, missing dependencies, unbounded tasks) that incremental revision cannot fix
**Solution**: Log remaining issues as accepted risks in the plan's Notes section and proceed to execution. The 3-iteration limit prevents infinite planning loops. If issues are fundamental, ask user to restructure the task scope.

## References

This skill uses these shared patterns:
- [Gate Enforcement](../shared-patterns/gate-enforcement.md) - Phase transition rules
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

Related skills and ADRs:
- [Planning umbrella — check intent](../../planning/references/check.md) - Pre-execution plan validation (ADR-074)
- [ADR-076: Autonomous Repair Mechanism](../../adr/076-autonomous-repair-mechanism.md) - Repair strategies and budget enforcement
- [ADR-079: Workflow Orchestrator Enhancements](../../adr/079-workflow-orchestrator-enhancements.md) - Plan validation, context budget, deviation rules, regression gates
- [ADR-069: Session Handoff System](../../adr/069-session-handoff-system.md) - Handoff artifacts for POOR context zone
