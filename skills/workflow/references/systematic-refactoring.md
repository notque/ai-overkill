---
description: "Safe 5-phase refactoring with test characterization and learning."
user-invocable: false
context: fork
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash
  - Grep
  - Glob
success-criteria:
  - "Characterization tests pass before and after changes"
  - "Zero references to old names remaining in codebase"
  - "Full test suite passes after each incremental step"
  - "No behavioral changes (only structural improvements)"
  - "All import paths and cross-references updated"
  - "Refactoring pattern recorded in the refactoring log"
routing:
  triggers:
    - "refactor safely"
    - "rename symbol"
    - "extract function"
    - "refactor"
    - "simplify this"
    - "restructure code"
    - "reduce complexity"
    - "split this file"
    - "restructure"
    - "move to separate file"
  category: process
---

# Systematic Refactoring Pipeline

> **Promoted from**: `skills/systematic-refactoring/SKILL.md` (original 4-phase skill)

Safe, verifiable refactoring through 5 explicit phases with mandatory gates. Each phase has gates that prevent common refactoring mistakes: breaking behavior, incomplete migrations, or orphaned code.

---

## Architecture Handoff Intake

When architecture-deepening supplies an `Architecture Change Handoff` JSON path, validate it before reading any action-bearing field:

```bash
python3 scripts/handoff.py validate \
  --repo-root . \
  --handoff 'adr/handoffs/{handoff-name}.json' \
  --expected-skill workflow \
  --expected-pipeline systematic-refactoring
```

The consumer check resolves module, caller, decision-store, handoff, and consultation ADR paths against the repository and rejects traversal, controls, shell metacharacters, symlink escapes, stale ADR hashes, and unregistered ADRs. After it passes, use its module/caller scope as the refactor boundary, its current/proposed interface and migration as the target plan, and its success criteria as extra VERIFY gates. Stop on any mismatch; do not repair or reinterpret the handoff in this workflow.

---

## Instructions

### Phase 1: CHARACTERIZE

**Goal**: Document current behavior with tests before touching any code.

**Key Constraint**: Write characterization tests first — establish a green test suite that captures current behavior before changing anything.

**Artifact**: Characterization test suite (green).

```
===============================================================
 PHASE 1: CHARACTERIZE
===============================================================

 Target Code:
   - File: [path/to/file.ext]
   - Element: [function/class/module being refactored]
   - Lines: [start-end]

 Current Behavior:
   - Purpose: [what it does]
   - Inputs: [parameters/dependencies]
   - Outputs: [return values/side effects]
   - Callers: [N files/functions use this]

 Existing Tests:
   - Coverage: [X% of target code]
   - Test files: [list of relevant test files]

 Characterization Tests Written:
   - [ ] Happy path covered
   - [ ] Edge cases covered
   - [ ] Error cases covered
   - [ ] Integration points covered

 Test Execution:
   $ [test command]
   Result: ALL PASS (required to proceed)

 CHARACTERIZE complete. Proceeding to PLAN...
===============================================================
```

**Actions in this phase:**
1. Read the code to be refactored completely
2. Find all callers with Grep (be exhaustive — string refs, configs, reflection)
3. Run existing tests, note coverage gaps
4. Write characterization tests for uncovered behavior
5. Verify all tests pass

**GATE**: Test suite exists that verifies current behavior. ALL tests GREEN. Zero gaps in coverage. Proceed only when gate passes.

---

### Phase 2: PLAN

**Goal**: Identify refactoring targets, define incremental steps with rollback points.

**Key Constraints**: Only refactor what's directly requested. Keep changes minimal and focused. No speculative improvements. Make one atomic change per commit. Break into smallest possible atomic changes with clear dependencies and rollback procedures for each step.

**Artifact**: `refactor-plan.md`

```
===============================================================
 PHASE 2: PLAN
===============================================================

 Refactoring Type: [rename | extract | restructure | migrate]

 Target State:
   - [Description of end state]

 Incremental Steps:
   1. [First atomic change]
      - Files affected: [list]
      - Risk: LOW/MEDIUM/HIGH
      - Rollback: [how to undo]

   2. [Second atomic change]
      - Files affected: [list]
      - Risk: LOW/MEDIUM/HIGH
      - Rollback: [how to undo]

   ... [continue for all steps]

 Dependencies:
   Step 2 depends on: Step 1
   Step 3 depends on: Step 2
   ...

 Risks:
   - [Potential issue 1]: [mitigation]
   - [Potential issue 2]: [mitigation]

 PLAN complete. Proceeding to REFACTOR...
===============================================================
```

**Actions in this phase:**
1. Define the exact end state (no scope creep)
2. Break into smallest possible atomic changes
3. Identify dependencies between steps
4. Define rollback procedure for each step
5. Estimate risk level for each step
6. Write `refactor-plan.md` to project root

**GATE**: `refactor-plan.md` exists with clear sequence of atomic changes, rollback points, and scope strictly bounded. No speculative improvements included. Proceed only when gate passes.

---

### Phase 3: REFACTOR

**Goal**: Apply changes incrementally, run tests after each step. Tests must stay green throughout.

**Key Constraints**: Run validation after every change — tests must pass before proceeding. Make one atomic change per commit. Phase gates enforced: each step must pass before the next begins.

```
===============================================================
 PHASE 3: REFACTOR - Step [N] of [Total]
===============================================================

 Step [N]: [description]

 Changes Made:
   - [file1.ext]: [specific change]
   - [file2.ext]: [specific change]

 Test Execution:
   $ [test command]
   Result: PASS / FAIL

 If PASS:
   Step [N] complete
   Commit: [commit message if applicable]
   Proceeding to Step [N+1]...

 If FAIL:
   Step [N] failed
   Rolling back...
   Investigating failure before retry

===============================================================
```

**Actions in this phase:**
1. Make ONE atomic change (no more)
2. Run ALL tests
3. If pass: commit, move to next step
4. If fail: rollback, investigate, fix, retry
5. Repeat until all steps complete

**GATE**: ALL planned steps executed. Tests GREEN after every step. No step skipped or combined. Zero errors on retry. Proceed only when gate passes.

---

### Phase 4: VERIFY

**Goal**: Full test suite, diff summary, confirm no behavior change.

**Key Constraints**: Always preserve external API unless explicitly requested. Remove dead code: clean up orphaned code after migration. Grep confirms ZERO references to old location. Never leave incomplete migrations.

```
===============================================================
 PHASE 4: VERIFY
===============================================================

 Full Test Suite:
   $ [comprehensive test command]
   Result: [PASS/FAIL]

 Behavior Verification:
   - [ ] Original functionality preserved
   - [ ] No new failures introduced
   - [ ] Performance acceptable

 Cleanup Verification:
   - [ ] No orphaned code
   - [ ] No unused imports
   - [ ] No dead references
   - [ ] Old names completely removed

 Caller Verification:
   $ grep -r "[old_name]" --include="*.ext"
   Result: [No matches / N remaining references]

 Documentation:
   - [ ] Comments updated
   - [ ] README updated (if applicable)
   - [ ] API docs updated (if applicable)

 Final Status: COMPLETE / INCOMPLETE

 Summary:
   - Files changed: [N]
   - Lines changed: [+X/-Y]
   - Steps completed: [N/Total]
   - Tests: [X passed, Y total]

===============================================================
```

**GATE**: Full test suite passes. Zero references to old names. No orphaned code. No behavior changes detected. External API preserved. All temporary test files cleaned up (keep only files explicitly needed). Proceed only when gate passes.

---

### Phase 5: RECORD

**Goal**: Record refactoring patterns in the repo where future sessions will read them.

**Key Constraint**: Complete recording — future refactors benefit from past patterns. No need to record? That's the signal you should record. Document what almost went wrong or required extra care.

**Step 1: Record refactoring pattern**

```markdown
## [Date] [Refactoring Type]: [Brief Description]
**Pattern**: [rename | extract | inline | restructure | migrate]
**Scope**: [N files, M callers]
**Steps**: [N atomic steps]
**Key Decision**: [Most important choice made and why]
**Gotcha**: [What almost went wrong or required extra care]
```

**Step 2: Clean up**

- Remove `refactor-plan.md` (plan executed)
- Remove temporary test files or debug outputs
- Keep characterization tests (they add permanent value)

**Output**: `Refactoring pattern recorded.`

**GATE**: Learning database entry exists with pattern type, scope, key decision, and gotcha. Temporary files cleaned up. Characterization tests retained.

---

## Refactoring Patterns

### Pattern 1: Rename (Function, Variable, File)

```
Phase 1: Find all usages with Grep
Phase 2: Plan order (definition first, then callers)
Phase 3: Execute with replace_all where safe
Phase 4: Verify no old name references remain
Phase 5: Record pattern and any gotchas
```

### Pattern 2: Extract (Function, Module, Class)

```
Phase 1: Identify code to extract, write tests
Phase 2: Plan new location, interface design
Phase 3:
  - Step 1: Create new location with copy
  - Step 2: Update callers one by one
  - Step 3: Remove old code
Phase 4: Verify all callers use new location
Phase 5: Record extraction pattern
```

### Pattern 3: Inline (Remove Abstraction)

```
Phase 1: Find all usages, understand all variations
Phase 2: Plan inline order (start with simplest callers)
Phase 3:
  - Step 1: Inline at first call site
  - Step 2: Repeat for each call site
  - Step 3: Remove now-unused function
Phase 4: Verify no remaining references
Phase 5: Record inline pattern
```

### Pattern 4: Change Signature

```
Phase 1: Find all callers, understand usage patterns
Phase 2: Plan migration (add new, migrate, remove old)
Phase 3:
  - Step 1: Add new signature alongside old
  - Step 2: Migrate callers one by one
  - Step 3: Remove old signature
Phase 4: Verify all callers use new signature
Phase 5: Record migration pattern
```

## Error Handling

### Test Failure During Refactor
Stop immediately, rollback current step, investigate root cause, fix and retry OR revise plan.

### Incomplete Caller Migration
Do not remove old code until ALL callers migrated. Use Grep to verify zero remaining references. Check for dynamic references (strings, reflection). Be exhaustive: identify ALL callers upfront using Grep before moving forward.

### Unexpected Dependencies
Stop and return to PLAN phase. Add new dependencies to plan. May need to add intermediate steps. Never continue if dependencies shift mid-refactoring.

### Small Changes, Easy to Skip
Small renames break string refs and configs. Grep for all references including strings. Never assume "this is too small to need the full process."

### Mixing Refactoring with Fixes
Separate concerns: This is ONLY refactoring, behavior unchanged. Do refactoring first (safe commit with tests proving no behavior change), then fix bugs separately (behavior change commit). Never combine.

## References
