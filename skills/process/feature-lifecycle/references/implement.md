# Feature Implement Phase

Execute the implementation plan by dispatching tasks to domain agents wave by wave. Phase 3 of the feature lifecycle (design > plan > **implement** > validate > release).

## Instructions

### Phase 0: PRIME

1. Read and follow the repository CLAUDE.md before any implementation work begins.

2. Verify feature state -- a plan must exist before implementation can start:
   ```bash
   python3 ~/.claude/scripts/feature-state.py status FEATURE
   ```
   Verify current phase is `implement` and `plan` is completed. All state operations throughout this skill go through `feature-state.py` because it is the single source of truth for lifecycle phase tracking.

3. Load the plan artifact from `.feature/state/plan/` and the design artifact from `.feature/state/design/`. Read the exact repository-relative ADR path and `sha256:` hash from the design's `## Architecture ADR` section; never locate the ADR by fuzzy filename matching.

4. **Consultation Gate** (every architecture-origin feature; all other Medium+ work):
   - Extract the feature name and task complexity from the plan. Read `## Architecture Change Handoff` in the design. The exact `"origin": "architecture-deepening"` field marks architecture-origin and persists across phases.
   - A Simple architecture-origin feature must run this gate. A Simple feature whose design records no architecture origin may proceed to step 5. Medium+ work always runs this gate.
   - Validate the exact design ADR through the canonical containment, hash, and registration check:

     ```bash
     python3 scripts/adr-query.py validate-registration \
       --repo-root . \
       --adr 'adr/{feature-slug}.md' \
       --hash 'sha256:{digest}'
     ```

     A missing path/hash, absolute or escaping path, changed ADR, or different active registration blocks implementation.
   - Derive the consultation directory only from the validated ADR stem. Do not reuse a consultation for a different path or hash.
   - If `adr/{feature-slug}/synthesis.md` does not exist, run `adr-consultation` now against that validated ADR. This is the single pre-IMPLEMENT consultation point; architecture-deepening and feature DESIGN must not run an earlier duplicate consultation.
   - Read the synthesis and confirm it names the same ADR path and hash, then check the verdict.
        - If verdict is "PROCEED", gate passes, continue.
        - If verdict is "BLOCKED", **BLOCK**: Print "Consultation blocked implementation. Resolve concerns in adr/{adr-name}/concerns.md before implementing." and STOP.

5. Load L1 implement context (along with L0 and plan/design artifacts, this provides the full context needed for accurate implementation):
   ```bash
   python3 ~/.claude/scripts/feature-state.py context-read FEATURE L1 --phase implement
   ```

6. Capture BASE_SHA for later diff validation:
   ```bash
   git rev-parse HEAD
   ```

**Gate**: Plan loaded. Feature in implement phase. BASE_SHA captured. Proceed.

### Phase 1: EXECUTE (Wave Dispatch)

**For each wave in the plan, in strict order** -- complete every task in Wave N before starting Wave N+1, because later waves depend on artifacts produced by earlier ones and out-of-order execution causes missing-dependency failures:

**Step 1: Dispatch Tasks**

For each task in the wave:

1. Check if task is marked parallel-safe in the plan AND parallel mode is enabled. Only dispatch parallel-safe tasks simultaneously -- dispatching all tasks in parallel causes file conflicts and data corruption when tasks touch overlapping files.

2. Dispatch to the domain agent assigned in the plan via Task tool. Each task gets a fresh agent dispatch (no reusing agents across tasks) because shared context between tasks causes subtle pollution where fixes for one task leak assumptions into another:

```
Agent(
  subagent_type="[agent-from-plan]",
  prompt="Implement the following task:\n\n[TASK DETAILS FROM PLAN]\n\nFiles: [FILES]\nOperations: [OPERATIONS]\nVerification: [VERIFICATION COMMAND]\n\nContext from design: [RELEVANT DESIGN CONTEXT]",
  description="Implement [task title]"
)
```

Use the agent specified in the plan, never override it -- the plan assigns agents based on domain expertise alignment determined during planning.

3. After each task completes, verify the output matches the plan specification (expected files, function signatures, behavior). Catching spec drift per-task is far cheaper than discovering it after the entire wave.

**Step 2: Handle Deviations**

Classify every deviation by tier and act accordingly. Ignoring small deviations lets them compound into architectural problems across waves:

| Tier | Examples | Action |
|------|----------|--------|
| Tier 1: Auto-Fix | Bug, type error, missing import | Auto-apply, record in retro |
| Tier 2: Blocking | Missing dependency, config issue | Auto-fix if possible, record |
| Tier 3: Architectural | Schema change, API change, scope expansion | **STOP**, present to user |

Tier 3 deviations require user input because they represent scope or design changes that the plan did not authorize:
```bash
python3 ~/.claude/scripts/feature-state.py gate FEATURE implement.architectural-deviation
```

**Step 3: Wave Checkpoint**

After all tasks in a wave complete, run the project's test suite (or relevant subset). Skipping this causes failures to compound silently across waves, making root-cause identification exponentially harder:

1. Run tests
2. If tests fail: identify which task caused the failure, route back to that agent for a fix
3. If tests pass: proceed to next wave

**Step 4: Progress Report**

After each wave, report status:
```
Wave N complete: X/Y tasks passed
  T1: [agent] pass
  T2: [agent] pass
  T3: [agent] fail (deviation: [description])
```

**Gate**: All waves complete. All tasks verified. Proceed to Validate.

### Phase 2: VALIDATE (Implementation Review)

Quick validation before the formal validation phase:
- [ ] All planned files were created/modified
- [ ] All verification commands pass
- [ ] No unplanned files were modified (check `git diff --name-only BASE_SHA..HEAD`)
- [ ] No Tier 3 deviations unresolved

**Gate**: Implementation complete. Proceed to Checkpoint.

### Phase 3: CHECKPOINT

1. Save implementation artifact (summary of what was built):
   ```bash
   echo "IMPL_SUMMARY" | python3 ~/.claude/scripts/feature-state.py checkpoint FEATURE implement
   ```

2. **Record learnings** -- if this phase produced non-obvious insights, record them:
   ```bash
   python3 ~/.claude/scripts/learning-db.py record TOPIC KEY "VALUE" --category design
   ```

3. Advance:
   ```bash
   python3 ~/.claude/scripts/feature-state.py advance FEATURE
   ```

4. Suggest next step:
   ```
   Implementation complete. Run /feature-lifecycle to continue to the validate phase.
   ```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| No plan found | Plan phase not completed | Run plan phase first |
| Consultation not completed | Architecture-origin or Medium+ feature has no synthesis for the validated design ADR path and hash | Run `adr-consultation` at the pre-IMPLEMENT gate |
| ADR validation fails | Design ADR is missing, unsafe, changed, or not the active registration | Return to DESIGN; register the canonical feature ADR and refresh the recorded hash |
| Consultation blocked | synthesis.md verdict is BLOCKED | Resolve concerns in adr/{name}/concerns.md |
| Agent dispatch fails | Agent not available or task malformed | Retry with more context, escalate if 3 failures |
| Wave test failure | Task broke existing tests | Route back to responsible agent for fix |
| Tier 3 deviation | Architectural decision needed | Stop, present options to user |
