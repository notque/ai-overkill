---
description: "Trace pipeline test failures to generator root causes."
user-invocable: false
agent: pipeline-orchestrator-engineer
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Agent
routing:
  triggers:
    - pipeline retro
    - trace failures
    - generator improvement
    - three-layer fix
    - fix generator
  pairs_with:
    - workflow
  complexity: Medium
  category: meta
---

# Pipeline Retro

## Purpose

Close the self-improvement loop for the pipeline generator. When the workflow test-runner phase reports failures, this skill traces each failure to its root cause in the generation chain, proposes fixes at the **generator** level (not the artifact level), then regenerates and re-tests to prove the fix works.

This skill implements the **Three-Layer Pattern** from `adr/self-improving-pipeline-generator.md`:

```
Layer 1: ARTIFACT -- Fix the specific generated skill
  -> SKIP (teaches the system nothing; the fix dies with this one pipeline)

Layer 2: GENERATOR -- Fix the rules, templates, chain composition, or step menu
  -> DO (root cause fix that propagates to ALL future pipelines)

Layer 3: VALIDATION -- Regenerate the affected skills + re-test
  -> PROVE (empirical evidence the fix actually works end-to-end)
```

The critical discipline: route every fix through the generator so all future pipelines benefit. Direct skill patches teach the system nothing; generator-level fixes propagate to all future pipelines. This is what makes the system self-improving rather than self-patching.

---

## Instructions

### Input

This skill requires:
- **Test Report Path**: Path to the workflow test-runner output directory containing `manifest.json` and `content.md`
- **Pipeline Spec Path**: Path to the Pipeline Spec JSON used to generate the pipelines
- **Domain**: The domain name (e.g., `prometheus`, `rabbitmq`)

These are provided by `pipeline-orchestrator-engineer` when invoking Phase 6 (RETRO).

### Phase 1: INGEST (Load Test Results)

**Goal**: Load the test runner report and build a failure inventory.

**Hardcoded Constraint**: If all results are PASS, produce a minimal report and exit—skip directly to the final report.

**Step 1**: Read the test runner `manifest.json`. Extract:
- `status`: overall pipeline test status
- `metrics.pass_count`, `metrics.fail_count`, `metrics.partial_count`
- `metrics.subdomains_tested`: list of subdomain names tested

**Step 2**: Read the test runner `content.md`. For each subdomain result:
- Extract the verdict (PASS, FAIL, PARTIAL)
- Extract the failure trace (if FAIL or PARTIAL)
- Extract the skill name that was tested
- Extract the test target that was used

**Step 3**: Filter for actionable failures:
- PASS results: skip (nothing to analyze)
- FAIL results: full root cause analysis needed
- PARTIAL results: analyze the failing dimensions only

**Step 4**: If all results are PASS:
- Produce a minimal report: "No retro needed. All N subdomains passed."
- Write the report artifact and exit after the minimal report is produced.

**Step 5**: Group failures by pattern similarity. Look for:
- Same failure type across multiple subdomains (suggests a generator-level issue, not a subdomain issue)
- Same chain step failing across multiple subdomains (suggests a template or step menu issue)
- Same dimension scoring low across subdomains (suggests a systematic quality gap)

Save the failure inventory to `/tmp/pipeline-retro-{domain}/failure-inventory.md`.

**Gate**: Failure inventory complete. At least one FAIL or PARTIAL result to analyze. Proceed to Phase 2.

### Phase 2: TRACE (Root Cause Analysis)

**Goal**: For each failure, trace it to a specific link in the 5-link generation chain.

**Hardcoded Constraint**: Trace every failure to a specific link before proposing a generator fix. Fixing the wrong link wastes a regeneration cycle. The 5-link chain analysis ensures you fix the root cause, not a symptom.

The generation chain has 5 links. Each link is a component of the pipeline generator that contributed to the final output. The failure was introduced at one of these links -- the goal is to identify which one.

**The 5 Links**:

| Link | Component | What It Controls | Files to Examine |
|------|-----------|-----------------|-----------------|
| 1. Domain Research | `workflow` skill (research phase) | Subdomain discovery, task type classification | The domain research artifact from Phase 1 |
| 2. Chain Composition | `workflow` skill (composition phase) | Step selection, step ordering, type compatibility | The Pipeline Spec JSON |
| 3. Scaffolder Template | `generated-skill-template.md` | Phase implementation patterns, chain-to-phase mapping | `skills/workflow/references/generated-skill-template.md` |
| 4. Architecture Rules | `architecture-rules.md` | Structural constraints on generated components | `skills/workflow/references/architecture-rules.md` |
| 5. Step Menu | `step-menu.md` | Available step types, output schemas, type compatibility | `skills/workflow/references/step-menu.md` |

**For each failure**:

**Step 1**: Read the generated skill that failed:
```
skills/{skill_name}/SKILL.md
```

**Step 2**: Read the Pipeline Spec entry for that subdomain. Find the chain that was composed for it.

**Step 3**: Read the failure trace from the test runner report. Identify:
- Which phase of the generated skill produced the bad output?
- What was wrong with the output (structural error, content gap, validation failure)?
- Was the test target appropriate for this subdomain?

**Step 4**: Walk the chain backward from the failure to the root cause. For each link, ask:

| Link | Question | If Yes -> Classification |
|------|----------|------------------------|
| 5. Step Menu | Is the chain missing a step type that would have prevented this failure? | `missing-step` |
| 4. Architecture Rules | Is there a rule that should have prevented this pattern but doesn't exist? | `missing-rule` |
| 3. Scaffolder Template | Did the template produce an incorrect phase implementation for this step type? | `template-bug` |
| 2. Chain Composition | Did the chain have the wrong steps or wrong step order for this task type? | `chain-error` |
| 1. Domain Research | Did domain research misclassify the subdomain or miss critical information? | `research-miss` |

Walk from Link 5 backward to Link 1. The FIRST link whose output introduced the problem is the root cause. Why: Fixing upstream links is more impactful (affects more future pipelines) but also riskier. We want the most specific fix possible -- the link closest to the failure that can resolve it.

**Step 5**: If the failure cannot be attributed to any of the 5 links, classify it as `test-target-issue`. This means the test target was insufficient, not the generator. Examples:
- Test target was too domain-specific for the generated pipeline to handle
- Test target required external tools or APIs not available in the test environment
- Test target was ambiguous (multiple valid outputs, grader penalized a valid one)

Save the trace analysis to `/tmp/pipeline-retro-{domain}/trace-analysis.md`.

**Gate**: Every failure has a root cause classification. Each classification cites the specific evidence (file, line, content) that supports it. Proceed to Phase 3.

### Phase 3: PROPOSE (Generator Fixes -- Layer 2)

**Goal**: For each root cause, propose a specific fix to the generator component.

**Hardcoded Constraint**: Every rule added to `architecture-rules.md` must cite the specific test failure that proved it necessary. Rules earn their place through data. Rules without evidence accumulate into bloat that slows every future generation.

**Hardcoded Constraint**: For complex fixes (new step types, restructured chains), present for review rather than auto-applying. For trivial fixes (template typos, missing rules with clear evidence), apply directly.

**Fix Proposals by Classification**:

**`research-miss`** -- Domain research failed to discover the right information.
- Target: `skills/workflow/SKILL.md` (research phase)
- Propose: Adding a new research agent aspect, modifying discovery prompts, or expanding the subdomain classification criteria
- Evidence required: Show what the research missed and how it led to the downstream failure

**`chain-error`** -- Chain composition selected wrong steps or wrong order.
- Target: `skills/workflow/references/canonical-chains.md` (pattern library) or `skills/workflow/references/step-menu.md` (step definitions)
- Propose: Adding a new canonical chain pattern, modifying step ordering rules, or adding a profile gate
- Evidence required: Show the chain that was composed, the step that was wrong, and the correct alternative

**`template-bug`** -- The generated-skill-template produced an incorrect phase implementation.
- Target: `skills/workflow/references/generated-skill-template.md`
- Propose: Fixing the chain-to-phase mapping for the affected step family, correcting template variable substitution, or adding missing template sections
- Evidence required: Show the template output vs. what it should have produced

**`missing-rule`** -- Architecture rules lack coverage for this case.
- Target: `skills/workflow/references/architecture-rules.md`
- Propose: A new rule with full format: Rule N, BANNED/REQUIRED statement, evidence citation, test/enforcement guidance
- Evidence required: The failure trace that proves the rule is necessary. Per the ADR: "Rules earn their place through data."

**`missing-step`** -- The step menu lacks a step type that was needed.
- Target: `skills/workflow/references/step-menu.md`
- Propose: A new step entry with: name, output schema, consumes, parallel flag, when-to-use description
- Evidence required: Show the gap in the chain that a new step type would fill, and why existing steps cannot cover it
- NOTE: Step menu changes are always presented for review, never auto-applied. Step menu changes affect the type system of ALL pipeline composition. A bad step type is worse than a missing one.

**`test-target-issue`** -- The test target was inadequate.
- Target: The test runner configuration, not the generator
- Propose: Better test targets or adjusted grading criteria
- Note: This is a test target fix, not a generator fix. Document it in the report and leave generator components unchanged.

**For each proposed fix**:

1. Write the proposed change as a diff (what to add/modify, in which file)
2. Cite the failure trace that justifies the change
3. Classify the fix complexity:
   - **Trivial**: Template typo, missing rule with clear evidence -> can auto-apply
   - **Moderate**: New canonical chain pattern, template mapping fix -> can auto-apply with review
   - **Complex**: New step type, restructured chain logic -> present for review, require explicit approval before applying

Save proposed fixes to `/tmp/pipeline-retro-{domain}/proposed-fixes.md`.

**Gate**: Every failure with a generator root cause has a proposed fix. Every fix cites specific evidence. Complex fixes are flagged for review. Proceed to Phase 4.

### Phase 4: REGENERATE (Layer 3 -- Prove the Fix)

**Goal**: Apply generator fixes and regenerate affected pipelines to prove the fixes work.

**Hardcoded Constraint**: Mark a generator fix as complete only after regenerating the affected skill and re-testing. A fix that doesn't improve test results isn't a fix -- it's a guess. Layer 3 is what distinguishes this from wishful thinking.

**Step 1: Classify and apply fixes**

For each proposed fix:

| Complexity | Action |
|-----------|--------|
| Trivial | Apply directly. Log the change. |
| Moderate | Apply directly. Log the change. Flag for post-retro review. |
| Complex | Present to user for approval. Apply only after confirmation. |

If the user rejects a complex fix, log the rejection and skip regeneration for that failure.

**Step 2: Re-run chain composition for affected subdomains**

After applying generator fixes:

1. Call the Skill tool with `workflow`. Run its composition phase for the affected subdomains only (not the entire domain, unless a step menu change affects all chains).
2. Validate the new chains with `scripts/artifact-utils.py validate-chain`
3. If validation fails: the fix introduced a type incompatibility. Revert the fix and investigate further.

**Step 3: Re-run scaffolder for affected skills**

1. Call the Skill tool with `workflow`. Run its scaffolder phase for the affected subdomain skills only.
2. The scaffolder reads the updated generator components (template, rules, step menu) automatically

**Step 4: Re-run test runner for regenerated skills**

1. Call the Skill tool with `workflow`. Run its test-runner phase for the regenerated skills.
2. Collect new test results

**Step 5: Compare before/after**

For each regenerated skill, compare:

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Overall verdict | FAIL/PARTIAL | ? | Improved/Same/Worse |
| Per-dimension scores | (from test runner) | (from test runner) | +/- per dimension |

**Decision logic**:
- **All improved or same**: Fix is validated. Proceed to report.
- **Some improved, some worse**: The fix may have side effects. Flag the regressions in the report. Consider reverting if regressions outweigh improvements.
- **All worse or same-as-before**: The fix was wrong. Revert ALL changes to generator components. Log the failed fix attempt in the report.

**Step 6: Revert on failure**

If the fix must be reverted:
1. Restore the original generator files (template, rules, step menu, canonical chains)
2. Log the revert in the report with the reason
3. Add the failure to an "open items" list for manual investigation

**Gate**: Regenerated skills produce better test results than the originals, OR fixes have been reverted with documented reasons. Proceed to Phase 5.

### Phase 5: REPORT

**Goal**: Produce the retro report as a dual-layer artifact.

**Default Behavior**: Clean up intermediate analysis files after the retro report is produced.

**Default Behavior**: When multiple failures share the same root cause, propose one fix that addresses all of them rather than N separate fixes.

**Step 1: Create manifest.json**

```json
{
  "schema": "learning-record",
  "step": "REPORT",
  "phase": 5,
  "status": "complete",
  "verdict": null,
  "metrics": {
    "failures_analyzed": 0,
    "root_causes": {
      "research-miss": 0,
      "chain-error": 0,
      "template-bug": 0,
      "missing-rule": 0,
      "missing-step": 0,
      "test-target-issue": 0
    },
    "fixes_applied": 0,
    "fixes_reverted": 0,
    "fixes_pending_review": 0,
    "regeneration_improved": 0,
    "regeneration_same": 0,
    "regeneration_worse": 0,
    "rules_added": 0
  },
  "inputs": ["test-runner-report-path"],
  "outputs": ["content.md"],
  "timestamp": "ISO-8601"
}
```

**Step 2: Create content.md**

```markdown
# Pipeline Retro Report: {domain}

## Summary

| Metric | Value |
|--------|-------|
| Failures analyzed | N |
| Root causes identified | N |
| Generator fixes applied | N |
| Fixes reverted | N |
| Fixes pending review | N |
| Rules added | N |

## Root Cause Distribution

| Classification | Count | Affected Subdomains |
|---------------|-------|-------------------|
| research-miss | N | subdomain-a, subdomain-b |
| chain-error | N | subdomain-c |
| template-bug | N | subdomain-d |
| missing-rule | N | subdomain-e |
| missing-step | N | (none) |
| test-target-issue | N | subdomain-f |

## Trace Analysis

### {subdomain-name}: {verdict}

**Failure**: {one-sentence description of what failed}
**Root cause**: {classification} at Link {N} ({link name})
**Evidence**: {file:line or specific content that proves the root cause}
**Fix proposed**: {description of the generator fix}
**Fix applied**: Yes/No/Pending review
**Regeneration result**: Improved/Same/Worse/Not attempted

[Repeat for each failure]

## Generator Changes Applied

### Rules Added to architecture-rules.md

**Rule {N}: {name}**
- BANNED/REQUIRED: {statement}
- Evidence: {failure trace reference}
- Impact: {what future pipelines this prevents}

### Template Changes

- {file}: {description of change}
- Evidence: {failure trace reference}

### Chain Composition Changes

- {file}: {description of change}
- Evidence: {failure trace reference}

## Regeneration Results

| Subdomain | Before | After | Delta | Status |
|-----------|--------|-------|-------|--------|
| {name} | FAIL | PASS | +improved | validated |
| {name} | PARTIAL | PARTIAL | same | reverted |

## Open Items

Failures that could not be resolved in this retro cycle:

- {subdomain}: {reason it remains open}

## Appendix: Evidence Index

| Evidence ID | Source | Description |
|-------------|--------|-------------|
| E1 | test-runner content.md, section X | {brief description} |
| E2 | skills/{skill}/SKILL.md, Phase N | {brief description} |
```

Save the report to the pipeline run directory alongside the test runner output.

**Gate**: Report artifacts exist. Retro complete.

---

## Error Handling

### Error: No Test Runner Report Found
**Cause**: The test runner was not invoked before the retro, or the report path is wrong.
**Solution**: Verify the test runner report path. If the report doesn't exist, this skill cannot run -- report the error to the orchestrator and suggest re-running the `workflow` skill (test-runner phase) first.

### Error: Generated Skill File Missing
**Cause**: During Phase 2 trace analysis, the generated skill file doesn't exist at the expected path.
**Solution**: The scaffolder may have failed silently or used a different path. Check `skills/` for the skill name. If truly missing, classify as a scaffolder failure (not a retro-analyzable failure) and report to the orchestrator.

### Error: Chain Validation Fails After Fix
**Cause**: A generator fix introduced a type incompatibility in the pipeline chain.
**Solution**: Revert the fix. The type system is the foundation of chain composition -- a fix that breaks types is worse than the original failure. Log the revert and add to open items.

### Error: Regeneration Produces Worse Results
**Cause**: The proposed fix addressed a symptom, not the root cause, or introduced a side effect.
**Solution**: Revert ALL generator changes from this retro cycle. Log the failed attempt with before/after comparison. Add to open items for deeper investigation.

### Error: All Failures Classify as test-target-issue
**Cause**: The test targets were inadequate, not the generator.
**Solution**: This is not a generator problem. Report the finding and suggest better test targets. Leave generator components unchanged.

---

## References

- **Pipeline Orchestrator**: [agents/pipeline-orchestrator-engineer.md](../../agents/pipeline-orchestrator-engineer.md) -- The agent that invokes this skill as Phase 6
- **Three-Layer Pattern ADR**: [adr/self-improving-pipeline-generator.md](../../adr/self-improving-pipeline-generator.md) -- Design rationale for Layer 1/2/3 discipline
- **Workflow Skill**: [skills/workflow/SKILL.md](../SKILL.md) -- Consolidated workflow skill (replaces chain-composer, pipeline-scaffolder, pipeline-test-runner, domain-research)
