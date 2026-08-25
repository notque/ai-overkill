---
description: "5-phase agent/skill improvement: AUDIT, DIFF, PLAN, IMPLEMENT, RE-EVALUATE."
user-invocable: false
argument-hint: "<agent-or-skill-name>"
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
  - Agent
  - Edit
  - Write
routing:
  triggers:
    - upgrade agent
    - improve agent
    - agent upgrade
    - fix agent quality
    - align agent to template
  pairs_with:
    - agent-evaluation
    - system-upgrade
  complexity: Medium
  category: meta
---

# Agent Upgrade Pipeline

## Overview

This skill upgrades a single target agent or skill through a scored, gated pipeline.
It is a **bottom-up** quality mechanism — triggered when a specific component needs
improvement — complementing the **top-down** `system-upgrade` pipeline that handles
multi-component changes driven by external events.

---

## Instructions

### Phase 1: AUDIT

**Goal**: Establish a baseline quality score for the target agent or skill.

**Step 1**: Identify the target file from the user's input.

```
# Common target patterns:
agents/golang-general-engineer.md
agents/python-general-engineer.md
skills/engineering/go-patterns/SKILL.md
```

If the user names an agent without a path, resolve it:
```bash
ls agents/ | grep [name]
ls skills/ | grep [name]
```

**Step 2**: Call the Skill tool with `agent-evaluation`. Evaluate the target file to get the baseline score (0–100) and grade (A/B/C/F).
This is critical because without a baseline, there is no way to verify improvement. "Looks better" is not a quality claim.

**Step 3**: Scan for retro entries targeting this agent:
```bash
python3 ~/.claude/scripts/learning-db.py search "[agent-name]" 2>/dev/null || echo "No retro candidates found"
```

**Step 4**: Check for staleness markers in the target file:
- Missing frontmatter fields: `context`, `model`, `user-invocable` (for skills)
- Operator Context section absent or incomplete (no Hardcoded/Default/Optional subsections)
- Version references to deprecated patterns
- Hook event types that have been superseded

**Output**:
```
AUDIT COMPLETE
==============
Target: [file path]
Baseline: [score]/100 ([grade])

Known gaps detected:
  - [gap 1]
  - [gap 2]
  ...

Retro candidates: [N found | none]
```

**Gate**: Baseline score recorded. Proceed to Phase 2.

---

### Phase 2: DIFF

**Goal**: Gap analysis against current patterns, templates, and peers.

**Step 1**: Compare target against the agent template structure. Read the template:
```bash
# Read the agent template
cat skills/meta/skill-creator/references/agent-template.md | head -50
```

Check for required sections. For agents:
- Frontmatter with `routing:` block (triggers, pairs_with, complexity, category)
- Operator Context with all three subsections (Hardcoded, Default, Optional)
- Error Handling section

For skills:
- Frontmatter with `agent:`, `allowed-tools:`, `user-invocable:`
- Operator Context section
- Phase-by-phase instructions with gates
- Error Handling section

**Step 2**: Assess Operator Context completeness:

| Subsection | Present? | Complete? |
|------------|----------|-----------|
| Hardcoded Behaviors | ? | ? |
| Default Behaviors | ? | ? |
| Optional Behaviors | ? | ? |

**Step 3**: Identify retro graduation candidates from Phase 1 scan. For each candidate:
- Note the learning (what pattern or behavior should be embedded)
- Identify where in the target it should be added (new hardcoded behavior, key pattern, error handling rule)

**Step 4**: Peer consistency check. Find 2–3 agents in the same category:
```bash
# For a Go agent, compare against other Go agents
grep -l "golang\|go\b" agents/*.md | grep -v [target] | head -3
```
Read peer Operator Context and structure. Note patterns present in peers but missing in target.

**Output**: Diff report — categorized list of gaps:

```
DIFF REPORT
===========
Target: [file path]

Missing Sections:
  - [section name]: [description of what's needed]

Outdated Patterns:
  - [pattern]: [current form] → [correct form]

Operator Context Gaps:
  - [missing behavior]: [description]

Retro Graduation Candidates:
  - [retro entry]: → [where it belongs in the agent]

Peer Inconsistencies:
  - [pattern in peers]: [missing from target]
```

**Gate**: Diff report produced. Proceed to Phase 3.

---

### Phase 3: PLAN

**Goal**: Prioritize improvements and get user approval before any changes.

**Step 1**: Rank all gaps from Phase 2 by tier:

| Tier | Criteria | Examples |
|------|----------|---------|
| **Critical** | Broken structure, missing required sections | No Operator Context, broken frontmatter |
| **Important** | Missing patterns that meaningfully affect quality | Missing Hardcoded behaviors, ungraduated retro with score ≥ 6 |
| **Minor** | Style alignment, peer consistency, optional fields | Missing optional frontmatter field, peer wording alignment |

**Step 2**: Present the ranked plan to the user:

```
AGENT UPGRADE PLAN
==================
Target: [file path]
Baseline: [score]/100 ([grade])

Proposed Improvements (Ranked):

CRITICAL (must fix):
  1. Add Operator Context section — Hardcoded/Default/Optional subsections absent [~20min]
  2. Add Error Handling section — 3 unhandled failure modes identified [~15min]

IMPORTANT (should fix):
  3. Graduate retro entry: "[learning summary]" → new Hardcoded behavior [~10min]
  4. Add missing frontmatter field: `model: sonnet` [~2min]

MINOR (nice to have):
  5. Align "What This Agent CANNOT Do" wording to peer style [~5min]

Total: 5 improvements
Estimated quality delta: +12 to +18 points

Proceed with implementation? (or specify which items to include/exclude)
```

**Step 3**: Wait for user approval before Phase 4. The gate exists because the user may have strong opinions about which improvements are appropriate, and the approval step keeps mass edits aligned with that decision.
- "yes", "proceed", "go ahead", "do it" → proceed with all items
- User specifies subset (e.g., "skip 5 and 6") → update plan, proceed with approved subset
- "no" or "stop" → stop and summarize what was decided

**Gate**: User approval received. Proceed to Phase 4.

---

### Phase 4: IMPLEMENT

**Goal**: Apply the approved improvements to the target file.

**Step 1**: Read the current target file in full before making any edits. Never edit from memory. This prevents collisions when the file changes between Phase 3 and Phase 4.

**Step 2**: For each approved improvement, apply in order of tier (Critical first):

**For missing sections** (add from agent-template patterns):
- Operator Context: Add the three-subsection structure. Populate Hardcoded with behaviors that ARE enforced, Default with on-by-default behaviors, Optional with opt-in behaviors.
- Error Handling: Add 2–4 concrete error cases with Cause + Solution format.

**For retro graduations**:
- Add the learning as a new Hardcoded behavior (if it should always apply) or a new pattern/rule in the relevant section.
- Preserve the original voice and specificity of the retro entry — don't paraphrase it into generic advice. Only graduate retro entries with score ≥ 6 that are directly relevant to the target agent's domain.

**For outdated patterns**:
- Update to current convention. Reference the peer agents or template for the correct form.

**For peer inconsistencies**:
- Align to the majority pattern observed across peers. If peers themselves are inconsistent, align to the most recent or highest-scoring peer.

**Step 3**: Run positive framing validation on the modified agent or skill.

After applying all approved improvements, validate the target file's framing. Call the Skill tool with `joy-check`. Use instruction mode. This ensures that new or modified content uses positive framing per ADR-127.
Positive framing produces instructions agents act on rather than rules they work around.

If joy-check flags lines in the NEW content (content that was just added/modified):
- Fix those lines as part of this same implementation pass
- Do not flag pre-existing content that was not part of the upgrade scope

If joy-check flags lines in EXISTING content (not modified by this upgrade):
- Note them in the upgrade report but do not fix them (out of scope for this upgrade)

**Step 4**: Change the following only when the user explicitly directs it, because domain logic changes require deliberate user decision rather than opportunistic bundling:
- Routing triggers (`triggers:` frontmatter field)
- Domain coverage statements
- Core methodology or phase structure (for skills)
- Agent pairing recommendations (`pairs_with:`)

**Gate**: All approved items implemented. No pending items from the approved plan.

---

### Phase 5: RE-EVALUATE

**Goal**: Score the updated agent and compute quality delta.

**Step 1**: Call the Skill tool with `agent-evaluation`. Evaluate the modified file and record the after score and grade.

**Step 2**: Compute delta:
```
delta = after_score - baseline_score
```

**Step 3**: If delta is negative (regression):
- Show the exact diff of changes applied
- Report which change likely caused the regression
- Ask user whether to revert the specific change or proceed anyway
- Offer the revert path instead of applying it automatically, because the user may have context that justifies the regression

**Step 4**: Report upgrade completion:

```
UPGRADE COMPLETE
================
[agent-name or skill-name]
  Before: [baseline_score] ([baseline_grade])
  After:  [after_score] ([after_grade])
  Delta:  +[N] points

Improvements applied: [N/N approved items]

Items applied:
  ✓ [improvement 1]
  ✓ [improvement 2]
  ○ [improvement N — skipped by user]
```

If the delta is positive, the upgrade is complete. If the delta is zero or negative and the user has not already acknowledged it, surface the regression report before closing.

**Gate**: After score recorded and delta computed. If positive, upgrade complete. If negative, user has acknowledged the regression before closing.

---

## Error Handling

### Error: "agent-evaluation skill unavailable or errors out"
Cause: The `agent-evaluation` skill has a dependency issue or the target file is malformed.
Solution: Read the target file manually and apply the scoring rubric from the CLAUDE.md quality gates section (Structure 20pts, Operator Context 15pts, Error Handling 15pts, Reference Files 10pts, Validation Scripts 10pts, Content Depth 30pts). Produce a manual score. Note it as manually derived in the report.

### Error: "No learning.db entries found for this agent"
Cause: No relevant learnings in the database for this agent's domain.
Solution: Skip retro graduation step and note it in the diff report. Learnings accumulate naturally during work.

### Error: "Agent template not found in repository"
Cause: Template file not at expected path (`skills/meta/skill-creator/references/agent-template.md`).
Solution: Use the highest-scoring agent (from recent agent-evaluation runs or MEMORY.md) as the de facto template for structural comparison. Note the substitution in the diff report.

### Error: "Regression detected in Phase 5 (delta is negative)"
Cause: One or more applied improvements reduced the evaluation score.
Solution: Show the diff, identify the likely culprit change, and ask the user whether to revert it. Keep rollback user-driven and proceed only after the user makes a decision.

### Error: "User approves plan but target file changes between Phase 3 and Phase 4"
Cause: Another process or agent modified the file during the gap.
Solution: Re-read the file before editing. If the baseline state has changed materially, re-run Phase 1–2 and re-present the plan.

---

## References

- [agent-evaluation](../../skills/meta/agent-evaluation/SKILL.md) - Objective scoring skill used in Phase 1 (baseline) and Phase 5 (re-evaluate)
- [system-upgrade](../system-upgrade/SKILL.md) - Top-down multi-component upgrade pipeline (complements this bottom-up single-agent pipeline)
- [agent-template](../../skill-creator/references/agent-template.md) - Structural template used for gap analysis in Phase 2
- [learning-db.py](../../scripts/learning-db.py) - Script for querying retro graduation candidates
