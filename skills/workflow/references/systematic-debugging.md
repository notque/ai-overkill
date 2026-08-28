---
description: "Evidence-based 5-phase debugging: OBSERVE, HYPOTHESIZE, TEST, FIX, RECORD."
effort: high
user-invocable: false
context: fork
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit, Task]
success-criteria:
  - "Bug is reproducible with a specific test or command"
  - "Root cause identified with evidence (not speculation)"
  - "Fix verified by running the reproduction step"
  - "No regressions in related test suite"
  - "Debug pattern recorded to the knowledge base"
routing:
  triggers:
    - "debug"
    - "find root cause"
    - "reproduce bug"
    - "fix this bug"
    - "this is broken"
    - "not working"
    - "why is this broken"
    - "getting an error"
    - "unexpected behavior"
    - "investigate error"
  category: process
---

# Systematic Debugging Pipeline

> **Promoted from**: `skills/systematic-debugging/SKILL.md` (original 4-phase skill)

Evidence-based 5-phase debugging pipeline with mandatory gates between each phase. No phase may be skipped. Each phase produces artifacts that survive context resets.

---

## Instructions

### Phase 1: OBSERVE

**Goal**: Reproduce the bug, collect error messages, stack traces, and environmental context.

**Artifact**: `debug-observations.md`

**Core Principle**: Reproduce first, always. Create a reliable reproduction before attempting any fix. This prevents you from chasing the wrong problem and ensures you can verify any fix actually works.

**Step 1: Document the bug**

```markdown
## Bug: [Brief Description]
Expected: [What should happen]
Actual: [What actually happens]
Environment: [OS, language version, dependencies]
```

**Step 2: Create minimal reproduction**

- Strip to essentials -- remove unrelated code
- Use smallest dataset that shows the bug
- Isolate from external services where possible

**Step 3: Verify consistency**

Run reproduction **3 times**. If inconsistent, identify variables (timing, randomness, concurrency) and add controls to make it deterministic. Consistency is not optional -- if you can't reproduce it reliably, you cannot verify a fix.

**Step 4: Check knowledge base**

At the start of every new debug investigation, before forming any hypotheses:

1. Check if `.debug-knowledge-base.md` exists in the project root
2. If it exists, search for keyword matches against the current symptom signature
3. Matches are **hypothesis candidates**, not confirmed diagnoses
4. List any matches in `debug-observations.md` with the note: "Prior resolution found -- verify applicability before assuming same root cause"

**Step 5: Create persistent debug file**

Create `.debug-session.md` with immutable Symptoms and Reproduction Steps sections. This file survives context resets.

| Section Type | Sections | Mutation Rule |
|-------------|----------|---------------|
| IMMUTABLE | Symptoms, Reproduction Steps | Write once at session start, never modify |
| APPEND-ONLY | Evidence, Eliminated Hypotheses | Add new entries, never remove or edit existing ones |
| OVERWRITE | Current Hypothesis, Next Action | Replace on each iteration |

**GATE**: Bug reproduces 100% with documented steps. `debug-observations.md` exists with symptoms, environment, and reproduction steps. Proceed only when gate passes.

---

### Phase 2: HYPOTHESIZE

**Goal**: Generate 3-5 candidate root causes ranked by likelihood.

**Artifact**: Updated `debug-observations.md` with hypotheses section.

**Core Principle**: Form evidence-based hypotheses, not random guesses. Each hypothesis must have concrete evidence supporting it, and each must be testable. One change at a time -- multiple simultaneous changes hide which one fixed it.

**Step 1: List components involved in the failure**

```markdown
## Components
1. [Component A] - [Role]
2. [Component B] - [Role]
3. [Component C] - [Role]
```

**Step 2: Binary search to narrow scope**

Test components in combinations to find minimal failing set:
- A alone -> PASS/FAIL?
- A + B -> PASS/FAIL?
- A + B + C -> PASS/FAIL?

When adding a component causes failure, that component (or its interaction) contains the bug.

**Step 3: Trace execution path**

Add targeted logging at decision points in the suspect component. Run and analyze:
- Where does execution diverge from expected?
- What values are unexpected at critical points?
- Are exceptions being caught silently?

**Step 4: Form ranked hypotheses**

```markdown
## Hypothesis: [Specific, testable statement]
Evidence: [What observations support this]
Test: [How to confirm or refute]
Likelihood: [HIGH/MEDIUM/LOW]
```

Generate 3-5 hypotheses. Rank by likelihood based on evidence gathered so far.

**Step 5: Update persistent debug file**

Write current top hypothesis and next action to `.debug-session.md` BEFORE taking any debugging action. This creates an audit trail that survives context resets.

**Pattern Trap**: Always validate with data before making changes. "I can see the bug" misses edge cases and is not evidence. Form a hypothesis, test it with data, then decide.

**GATE**: At least 3 hypotheses documented with supporting evidence and test plans. Identified smallest code path and input that reproduces the bug. Proceed only when gate passes.

---

### Phase 3: TEST

**Goal**: Write the minimal reproduction test, verify it fails (red).

**Artifact**: Reproduction test + test results

**Core Principle**: Verify the bug with a test before attempting any fix. The test is the oracle that tells you when the bug is truly fixed. If 5+ consecutive Read/Grep/Glob calls occur without an Edit/Write/Bash action, STOP and explain what you're looking for and why before proceeding. Document the justification in `.debug-session.md` under Current Hypothesis -- this creates an audit trail of investigation decisions.

**Step 1: Write reproduction test**

Create a test that captures the exact bug behavior:

```python
def test_regression_[issue]():
    """Root cause: [hypothesis]. Fix: [pending]."""
    result = buggy_function(trigger_input)
    assert result == expected  # This should FAIL
```

**Step 2: Test each hypothesis**

For each hypothesis (highest likelihood first):

```markdown
## Testing: [Hypothesis]
Experiment: [What I did]
Result: CONFIRMED / REFUTED
Evidence: [What I observed]
```

If REFUTED: Move to next hypothesis. Append to Eliminated Hypotheses in `.debug-session.md`.
If CONFIRMED: Proceed to Phase 4.

**Step 3: Code inspection checklist**

For the confirmed hypothesis area:
- [ ] Off-by-one errors?
- [ ] Null/None values unhandled?
- [ ] Exceptions caught silently?
- [ ] Race conditions possible?
- [ ] Resources released properly?
- [ ] Input assumptions violated?

**GATE**: Reproduction test exists and is RED (failing). Root cause hypothesis confirmed with evidence. Can explain WHY bug occurred. Proceed only when gate passes.

---

### Phase 4: FIX

**Goal**: Implement fix, verify test turns green. Ensure no regressions.

**Artifact**: Green test + passing full suite

**Core Principle**: Fix only the confirmed root cause. No speculative improvements, no "while I'm here" changes. Simple changes cause complex regressions -- complete all verification steps. If a specific test passes but the full suite fails, you have introduced regressions. Run the full suite every time.

**Step 1: Make the smallest possible fix**

Address only the confirmed root cause. No speculative improvements.

**Step 2: Verify reproduction test passes**

Run the reproduction test. It must turn GREEN. If it doesn't, the fix didn't work and you need to return to Phase 2 with new hypotheses.

**Step 2a: Revert on failed fix**

If the fix attempt fails (test stays RED) or creates more breakage than it solves (new failures outweigh the one fixed):

1. Revert all changes made since Phase 1 -- `git checkout -- <files>` or `git stash` the fix attempt. The codebase returns to its pre-fix state before any new hypothesis is tried.
2. Append the revert reason to `.debug-session.md` Eliminated Hypotheses -- record which hypothesis was tried, what broke, and why it was reverted.
3. Return to Phase 2 with narrowed scope -- the failed attempt is evidence; use it to rule out the hypothesis and rank the remaining candidates.

**Step 3: Test edge cases**

Test boundary values, empty input, null, maximum values. Verify the fix works beyond the exact reproduction case.

**Step 4: Run full test suite**

Verify no regressions. ALL tests must pass. Tests relied on buggy behavior, or fix changed API contract? If tests expected buggy behavior -> update tests. If fix exposed other bugs -> apply 5-phase process to each.

**Step 5: Test related functionality**

Check similar patterns that might share the same root cause. A root cause can appear in multiple places.

**Step 6: Document fix summary**

```markdown
## Fix Summary
Bug: [description]
Root Cause: [exact cause]
Fix: [changes made]
Files: [modified files]
Testing: reproduction passes, edge cases pass, full suite passes
```

**GATE**: Reproduction test is GREEN. Full test suite passes with zero regressions. Fix is minimal and addresses only the confirmed root cause. Proceed only when gate passes.

---

### Phase 5: RECORD

**Goal**: Record the pattern and fix in the repo's knowledge base for future sessions.

**Artifact**: Updated `.debug-knowledge-base.md`

**Step 1: Record to knowledge base**

Append entry to `.debug-knowledge-base.md`:

```markdown
## [Date] [Brief Description]
**Keywords**: [comma-separated terms: error messages, component names, symptom descriptions]
**Symptom**: [What was observed]
**Root Cause**: [What was actually wrong]
**Resolution**: [What fixed it]
**Files**: [Which files were involved]
```

**Step 2: Clean up**

- Remove `.debug-session.md` (investigation complete)
- Remove temporary debug logs and profiling output
- Keep only the regression test and knowledge base entry

**Output**: `Bug pattern recorded in .debug-knowledge-base.md.`

**GATE**: Knowledge base entry exists with keywords, symptom, root cause, and resolution. `.debug-session.md` cleaned up. Temporary files removed.

---

## Error Handling

### Error: "Cannot Reproduce Bug"
Cause: Environmental differences, timing-dependent, or randomness
Solution:
1. Match environment exactly (OS, versions, dependencies)
2. Look for race conditions or async timing issues
3. Introduce determinism (fixed seeds, mocked time)
4. If intermittent: add monitoring to catch it in-flight

### Error: "Fix Breaks Other Tests"
Cause: Tests relied on buggy behavior, or fix changed API contract
Solution:
1. If tests expected buggy behavior -> update tests
2. If fix exposed other bugs -> apply 5-phase process to each
3. If API changed -> restore compatibility or update all callers

### Error: "Root Cause Still Unclear After Isolation"
Cause: Isolation not narrow enough, or multiple contributing factors
Solution:
1. Return to Phase 2 with narrower scope
2. Add logging at lower abstraction levels
3. Use debugger to step through execution
4. Consult `references/debugging-patterns.md` for common patterns

---

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/debugging-patterns.md`: Common bug patterns by category
- `${CLAUDE_SKILL_DIR}/references/tools.md`: Language-specific debugging tools
- `${CLAUDE_SKILL_DIR}/references/isolation-techniques.md`: Advanced isolation strategies
