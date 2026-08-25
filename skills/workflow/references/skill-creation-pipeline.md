---
description: "5-phase skill creation pipeline with quality gates."
user-invocable: false
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
  - Agent
  - Edit
  - Write
routing:
  force_route: true
  triggers:
    - create skill pipeline
    - new skill formal
    - skill with gates
    - "create skill formally"
    - "new skill with gates"
    - "skill creation pipeline"
    - "formal skill creation"
  pairs_with:
    - agent-evaluation
    - routing-table-updater
  complexity: Medium
  category: meta
---

# Skill Creation Pipeline

## Overview

This pipeline wraps `skill-creator` with explicit discovery, design review, and validation gates. It is the **formal path** for creating new skills — as opposed to ad-hoc creation — and should be used whenever skill quality, uniqueness, or routing correctness is important. The pipeline does not replace the creator agent; it provides the scaffolding around it.

---

## Instructions

### Phase 1: DISCOVER

**Goal**: Prevent duplication by scanning the existing skill and agent indexes
before any files are written. DISCOVER **must complete before any SKILL.md is
written — no exceptions**.

**Step 1**: Extract the domain keywords from the user's request. These are the
terms that describe what the skill does (e.g., "code review", "branch naming",
"Go testing", "PR creation").

**Step 2**: Search `skills/INDEX.json` for existing skills with overlapping
descriptions or triggers.

```bash
# Search INDEX for keyword overlap
grep -i "<keyword>" /path/to/skills/INDEX.json
```

Also search `agents/INDEX.json` for agents that already handle this domain as
part of their core capability.

**Step 3**: Check for active ADR session. If `.adr-session.json` exists, run
`python3 ~/.claude/scripts/adr-query.py list` to find related ADRs. If
an active session exists, read relevant sections via
`adr-query.py context --role skill-creator`. If creating a skill as part of
a pipeline, verify the ADR hash before proceeding.

**Step 4**: **Umbrella domain check** (consolidation gate). Before estimating
overlap percentages, check whether the requested skill's domain is already covered
by an umbrella skill with a `references/` directory.

```bash
# Check for existing umbrella skills in the domain
ls skills/ | grep "<domain-prefix>"
ls skills/<domain-skill>/references/ 2>/dev/null
```

If an umbrella skill exists for this domain:
- The new skill MUST be added as a reference file on the existing umbrella skill,
  not created as a separate skill
- Pattern: `skills/{domain}/references/{sub-concern}.md`
- Preferred pattern: `skills/{domain}-{sub-concern}/SKILL.md`
- Report: "Domain umbrella exists at skills/{name}/. Adding reference file instead
  of creating new skill."
- Skip to a modified Phase 3 that writes the reference file and updates the
  umbrella SKILL.md with a pointer to it

If no umbrella skill exists, continue with overlap estimation below.

**Step 4b**: For each potentially overlapping skill (that is NOT an umbrella match),
read its SKILL.md description and phase list. Estimate overlap percentage based on:
- Same domain verbs (review, create, debug, deploy)
- Same target artifact (Go files, PRs, branches, agents)
- Same phase structure (does the existing skill already cover what's needed?)

If an existing skill covers >=70% of the requested domain, surface the overlap
and recommend extending rather than creating. Proceed only after a deliberate
"create new" decision (threshold is 70% overlap).

**Step 5**: Identify the skill's group prefix. Run `ls skills/ | grep {domain}`
to find the group. Examples: voice skills start with `voice-`, Go skills with
`go-`, PR skills with `pr-`, writing/content skills with `writing-`, review
skills with `review-`. New skills **must use the same prefix as related existing
skills**. If no group exists, the new skill starts one. The directory name and
the `name:` frontmatter field must match exactly.

**Step 6**: Report findings.

```
DISCOVER RESULTS
================

Request: [user's skill description in one line]
Keywords: [extracted keywords]
Group/Prefix: [identified prefix, e.g., voice-, go-, pr-]
ADRs checked: [Y/N, count if any found]
Existing skills checked: [N]
Umbrella domain check: [No umbrella found | Umbrella exists: skills/{name}/]

[If umbrella domain exists:]
  Domain umbrella found: skills/{name}/
  Existing references: [list of references/*.md files]
  Action: Adding reference file skills/{name}/references/{sub-concern}.md
  Skipping DESIGN/SCAFFOLD — writing reference file directly.

[If no overlap found:]
  No overlap found. Safe to create new skill.
  Proceeding to DESIGN.

[If overlap found (no umbrella):]
  Overlap detected:

  skills/[name]/SKILL.md — [estimated overlap]% overlap
    Description: [first 2 lines of their description]
    Why it overlaps: [1 sentence]

  Recommendation: [Extend existing skill | Create new skill]
  Reason: [1 sentence]
```

**Gate**: If overlap ≥70% with any existing skill, present the recommendation
and wait for the user's decision. If the user says "create new anyway" or
"extend" the existing skill, act accordingly. If <70% overlap or user confirms
new creation, proceed to Phase 2. (To skip DISCOVER entirely, enable with
"skip discover" or "I've already checked for duplicates" — use only when the
skill name is intentionally novel.)

---

### Phase 2: DESIGN

**Goal**: Choose the complexity tier and produce a complete design brief before
any SKILL.md content is written. **Design brief must be saved before Phase 3
begins** — writing a skill without a tier decision and phase list produces
inconsistent results.

**Step 1**: Classify the skill's complexity tier using these characteristics.

| Tier | Characteristics | Phase Count | Fan-Out |
|------|----------------|-------------|---------|
| **Simple** | Single-step or linear workflow, no coordination | 1–3 phases | None |
| **Medium** | Multi-step with optional branching or parallel work | 3–5 phases | Optional |
| **Complex** | Multi-agent coordination, fan-out required | 5+ phases | Required |
| **Comprehensive** | Cross-system pipeline, multi-phase with full validation | 5+ phases + validation | Multi-agent |

Use these signals to classify:
- "Generate one file" → Simple
- "Review then fix" → Medium
- "Parallel agents + verdict synthesis" → Complex
- "Full lifecycle with before/after scoring" → Comprehensive

**Step 2**: Draft the design brief.

```
DESIGN BRIEF: [skill-name]
==========================

Complexity Tier: [Simple | Medium | Complex | Comprehensive]
Agent Binding:   skill-creator (default) or [other agent if domain-specific]
User-Invocable:  [true | false]

Phases:
  1. [Phase name]: [one-line description]
  2. [Phase name]: [one-line description]
  ...

Reference Files Needed:
  - [file or "none"]

Key Behaviors (Hardcoded):
  - [behavior]
```

**Step 3**: Tier confirmation logic. If the tier is unambiguous given the request,
auto-select and note the reason in the brief. If ambiguous (the request could
reasonably fit two tiers), present both options and ask the user to choose before
proceeding. Tier errors are cheaper to fix in DESIGN than after SCAFFOLD —
ask for confirmation on edge cases. (To skip confirmation, enable with "auto" or
"no confirmation needed" — use only for intentional auto-approval.)

**Step 4**: Save the design brief.

Write to `skills/{name}/design-brief.md`. This file is the single source of
truth for Phase 3.

**Gate**: Design brief saved. Tier confirmed (either auto-selected with rationale
or user-confirmed). Proceed to Phase 3.

---

### Phase 3: SCAFFOLD

**Goal**: Generate the SKILL.md file from the confirmed design brief.

**Step 1**: Read the saved design brief from `skills/{name}/design-brief.md`.

**Step 2**: Generate the SKILL.md following the structural patterns from
the agent template (`skills/meta/skill-creator/references/agent-template.md`). Include these sections in this order:

1. **Frontmatter** with `name`, `description`, `version`, `user-invocable`,
   `agent`, `allowed-tools` (required fields)
2. **Overview** (1–2 sentences on purpose and context)
3. **Instructions** with one `### Phase N: PHASENAME` section per phase in the
   design brief. Each phase must end with a **Gate** statement:
   `**Gate**: [condition]. [action].`
4. **Error Handling** with 2–3 named error cases (Cause, Solution pattern)
5. **References** (links to related files, skills, agents)

Omit these outdated sections — they are being removed from the template:
- "Operator Context" (hardcoded/default/optional behaviors)
- "What This Skill CAN/CANNOT Do"
- "Preferred Patterns" tables and rationalization-detection tables

**Step 3**: Integrate constraints inline with each phase's reasoning and gate
logic rather than in separate subsections. For example:
- In Phase 1, explain why DISCOVER must complete first and what checks to run
- In Phase 2, note when tier confirmation is needed vs. auto-selected
- In Phase 4, explain why agent-evaluation scores must be ≥75 before proceeding

**Step 4**: Write to `skills/{name}/SKILL.md`.

**Gate**: File written. Confirm path exists before proceeding to Phase 4.

---

### Phase 4: VALIDATE

**Goal**: Score the new skill against the agent-evaluation rubric. **Score must
be ≥75 (grade B or above) before proceeding to Phase 5.** Self-assessment
("this looks good") does not satisfy this gate — agent-evaluation scoring is
mandatory.

**Step 1**: Call the Skill tool with `agent-evaluation`. Evaluate the new SKILL.md.

Call the Skill tool with `agent-evaluation`. Point it at `skills/{name}/SKILL.md`. This
produces a score breakdown across six criteria (total 100 points). The skill
must score ≥75 to proceed to integration.

**Step 2**: Report the score.

```
VALIDATE RESULTS
================

Skill: skills/{name}/SKILL.md
Score: [N]/100
Grade: [A (90+) | B (75–89) | C (60–74) | F (<60)]

Breakdown:
  Structure:         [N]/20
  Reference Files:   [N]/10
  Error Handling:    [N]/15
  Content Depth:     [N]/30
  Joy-Check:         [pending — run Step 3]

[If grade A or B:]
  Gate passed. Proceeding to INTEGRATE.

[If grade C or F:]
  Gate failed. Returning to SCAFFOLD.
  Fix required: [list specific missing sections or weak areas from breakdown]
  Iterations remaining: [3 | 2 | 1]
```

**Step 3**: Run positive framing validation on the generated skill.

Call the Skill tool with `joy-check`. Use instruction mode on `skills/{name}/SKILL.md`. This validates that
the skill's instructions use positive framing (action-based) instead of prohibition-heavy
wording. Positive framing makes instructions more actionable and easier for agents to
internalize because it tells the agent what to do instead of only naming what to avoid.

After running, update the Joy-Check line in the Step 2 report from `[pending]` to
`[PASS]` or `[N lines flagged]`.

Joy-check is advisory, not blocking — flagged lines do not prevent proceeding to INTEGRATE
when the quality score is ≥75. However, flagged lines should be addressed in the same
iteration as any quality fixes to avoid accumulating framing debt:
- List the specific lines flagged
- If returning to SCAFFOLD for a quality score failure (Step 4), include joy-check fixes
  in the same pass — this counts toward the same 3-iteration limit

**Step 4**: If grade C or below:
- List the specific sections that are weak or missing
- Return to Phase 3 with explicit instructions to fix those sections
- Re-run Phase 4 after the fix
- Track iterations. Max 3 iterations — after 3 failed attempts to reach 75+,
  surface the full scoring breakdown to the user and ask whether to continue
  or redesign from Phase 2. Tier errors discovered late are expensive to fix.

(To skip validation entirely, enable with "skip validation" or "quick creation"
— use only when accepting the risk of lower quality at integration time.)

**Gate**: Score ≥75 (grade B or above). Proceed to Phase 5.

---

### Phase 5: INTEGRATE

**Goal**: Wire the validated skill into the routing system. **INDEX.json update
is non-optional** — a skill that exists on disk but not in the index is invisible
to routing.

**Step 1**: Add to `skills/INDEX.json`.

Read the current INDEX.json and append an entry for the new skill:

```json
{
  "name": "skill-name",
  "path": "skills/skill-name/SKILL.md",
  "description": "[first line of the frontmatter description]",
  "user-invocable": true,
  "agent": "skill-creator"
}
```

Validate JSON syntax before proceeding:
```bash
python3 -c "import json; json.load(open('skills/INDEX.json'))"
```

**Step 2**: Check whether the skill needs a routing entry in `/do`.

A routing entry is needed if:
- The skill is user-invocable AND
- The skill has natural trigger phrases that aren't already routed elsewhere

If a routing entry is needed:
- Call the Skill tool with `routing-table-updater`. Otherwise, instruct the user to add the entries manually.
- Report routing-table changes explicitly, including what was added or updated, so the user can review the effect before it lands

If no routing entry is needed (internal skill, or triggers already covered):
- Note this in the output and proceed.

**Step 3**: Confirm integration.

```
INTEGRATE COMPLETE
==================

Skill:   skills/{name}/SKILL.md
Index:   Added to skills/INDEX.json
Routing: [Added triggers: "..." | No routing entry needed | Routing update pending]

Grade at integration: [B | A]
Score:  [N]/100

New skill is ready to use.
```

**Gate**: INDEX.json updated and validated. Routing status reported. Phase 5 complete.

---

## Error Handling

### Error: "Overlap detected but user wants to proceed"
Cause: Existing skill covers ≥70% of the domain but user explicitly wants a
separate skill (e.g., different scope, different agent binding, different audience).
Solution: Document the distinction in the design brief's "Why this is not X"
section. Proceed with a clear rationale for the new skill's existence.

### Error: "SCAFFOLD produces skill below grade B after 3 iterations"
Cause: The complexity tier may be wrong, the phase structure may be incoherent,
or the domain is too narrow to support a full Operator Context + Error Handling
section.
Solution: Return to Phase 2 (DESIGN). Reconsider the tier — Simple skills rarely
need elaborate error handling. If the skill is genuinely too narrow, consider
whether it should be a section within an existing skill rather than a standalone
SKILL.md.

### Error: "agent-evaluation skill not available"
Cause: `agent-evaluation` is not in the current session's tool set or the skill
file is missing.
Solution: Perform a manual rubric check against the 6 criteria table. Document
the manual score and proceed if ≥75. Flag that automated validation was skipped.

### Error: "INDEX.json malformed after update"
Cause: JSON edit introduced a syntax error.
Solution: Run `python3 -c "import json; json.load(open('skills/INDEX.json'))"` to
validate. Fix the syntax before completing Phase 5.

---

## Examples

### Example 1: Simple skill, no overlap
User: "Create a skill for generating conventional commit messages."
Actions: Phase 1 scans INDEX — finds `git-commit-flow` but it handles the full
commit workflow, not message generation specifically; overlap ~40%, under
threshold. Phase 2 selects Simple tier (1–2 phases: gather context, generate
message). Design brief saved. Phase 3 scaffolds a 2-phase SKILL.md. Phase 4
scores 81/100 (grade B). Phase 5 adds to INDEX.json, notes routing trigger
"commit message" should be added.

### Example 2: Overlap detected, extend recommended
User: "Create a skill for reviewing Go PRs."
Actions: Phase 1 scans INDEX — finds `go-patterns` with 85% overlap (same
domain, same artifact, same review steps). DISCOVER gate fires: recommends
extending `go-patterns` rather than creating a duplicate. User agrees and
redirects to editing the existing skill instead.

### Example 3: Complex tier, multiple iterations
User: "Create a skill that runs security, performance, and architecture reviews
in parallel and synthesizes a final verdict."
Actions: Phase 1 finds no overlap. Phase 2 selects Complex tier (5 phases:
GATHER, DISPATCH, COLLECT, SYNTHESIZE, REPORT). Design brief saved. Phase 3
first scaffold scores 64/100 (C — missing Operator Context subsections and Error
Handling). Returns to Phase 3 with specific fixes. Second scaffold scores 82/100
(B). Phase 4 passes. Phase 5 integrates with routing trigger "parallel review".

---

## References

- [agent-template.md](../../skill-creator/references/agent-template.md) - Template for agent and skill structural patterns
- [agent-evaluation](../../skills/meta/agent-evaluation/SKILL.md) - Rubric-based scoring used in Phase 4 VALIDATE
- [routing-table-updater](../../skills/meta/routing-table-updater/SKILL.md) - Routing integration used in Phase 5 INTEGRATE
