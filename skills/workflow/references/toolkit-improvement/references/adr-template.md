# ADR Template

Standard format for ADRs created by the toolkit improvement pipeline. Copy this
structure for each ADR. The Validation Requirements and Failure Remediation Protocol
sections are mandatory and must appear verbatim (with only the skill names adjusted
if the ADR affects non-skill components).

---

## File naming

```
adr/NNN-short-descriptive-slug.md
```

Where `NNN` is the next available number (`ls adr/ | grep -E '^[0-9]' | sort | tail -1`
then increment by 1).

Also create `adr/short-descriptive-slug.md` as a one-line redirect to the numbered file.
This satisfies the ADR creation gate hook which looks for `adr/{component-name}.md`.

---

## Template

```markdown
# ADR-NNN: [Title]

## Status
Proposed

## Date
YYYY-MM-DD

## Context

[2-3 paragraph explanation of the problem. Include:]
- What the evaluation found
- The critique's disposition (CONFIRM / DOWNGRADE / DISMISS / ELEVATE) and reasoning
- Why the issue matters in practice — concrete scenario, not theoretical risk
- File and line references for every claim

### Finding [ID]: [Short title]

**Verdict: [CONFIRMED | DOWNGRADED from HIGH to MEDIUM | etc.]**

[Detailed description of the finding with file:line evidence. Quote relevant code
snippets where they help clarify the issue.]

**Why this matters:**
[Concrete impact — what breaks, who is affected, under what conditions]

## Decision

### [Decision title]

[Concrete implementation plan. Not "improve the code" but "replace X with Y in
file Z because reason W".]

[Include before/after code snippets for non-trivial changes.]

[If multiple changes, use numbered subsections:]

### 1. [First change]
[Description + code]

### 2. [Second change]
[Description + code]

## Components

| Component | Action | Description |
|-----------|--------|-------------|
| `path/to/file.py` | Modify | What specifically changes |
| `path/to/other.py` | Modify | What specifically changes |

## Execution Plan

_The implementing agent follows this section step-by-step. Every task must be
granular enough to complete in a single agent dispatch._

### Agents, Skills & Pipelines to Use

| Step | Agent | Skill/Pipeline | Purpose |
|------|-------|---------------|---------|
| 1 | `[agent-name]` | `[skill-name]` | [What this step accomplishes] |
| 2 | `[agent-name]` | `[skill-name]` | [What this step accomplishes] |
| ... | ... | ... | ... |

_Select agents from `agents/INDEX.json`. Select skills from `skills/INDEX.json`
and `skills/INDEX.json (workflow section)`. Prefer specialized agents over general-purpose.
If no suitable agent exists, note the gap — it may itself warrant a new agent._

### Implementation Task List

_Granular, ordered steps. Each step should be independently verifiable._

- [ ] **Step 1**: [Action verb] [specific file:line] — [what changes]
  - Agent: `[agent-name]` | Skill: `[skill-name]`
  - Verify: [how to confirm this step succeeded]
- [ ] **Step 2**: [Action verb] [specific file:line] — [what changes]
  - Agent: `[agent-name]` | Skill: `[skill-name]`
  - Verify: [how to confirm this step succeeded]
- [ ] **Step 3**: Regenerate INDEX files
  - Run: `python3 scripts/generate-skill-index.py` and/or `python3 scripts/generate-agent-index.py`
  - Verify: `python3 scripts/routing-benchmark.py --verbose` passes
- [ ] **Step 4**: Run quality gate
  - Skill: `/skill-eval` on affected components
  - Verify: Score >= baseline (captured in Step 0)
- [ ] **Step 5**: Commit + PR via `/pr-sync`
  - Verify: All CI checks pass

### Workflow

_If this ADR creates a new component (skill, pipeline, agent, hook), specify
the creation workflow:_

| Phase | What Happens | Gate |
|-------|-------------|------|
| 1. Design | Read PHILOSOPHY.md, draft component | ADR approved |
| 2. Implement | Write files using domain agent | Files exist |
| 3. Integrate | Add triggers, regen INDEX, update routing tables | No trigger collisions |
| 4. Validate | Run /skill-eval (baseline vs post) | Score >= baseline |
| 5. Review | Run /pr-review (3 rounds max) | No blockers |
| 6. Ship | /pr-sync → CI → merge | All checks pass |
| 7. Record | Route the run's patterns to the files that own them | Edits landed |

_If this ADR only modifies existing components, use phases 2-7 (skip Design)._
_If no new workflow is needed, write "N/A — modification only, standard PR flow."_

### Execution Mode

_Specify how the implementing agent should run:_

| Mode | When to Use | How |
|------|------------|-----|
| **Worktree** | Independent changes that don't conflict with other ADRs | `isolation: "worktree"` on Agent tool — gives the agent an isolated repo copy |
| **In-place** | Changes that depend on other ADR outputs | Standard agent dispatch on a feature branch |
| **Parallel batch** | Multiple independent ADRs being implemented simultaneously | Dispatch via `subagent-driven-development` skill, each in a worktree |

**Worktree is the default for ADR implementation.** Each ADR gets its own isolated
worktree so agents can work in parallel without stepping on each other. The
orchestrator creates a target branch first, passes it to all agents, and merges
worktree branches afterward.

**Branch naming**: `feat/adr-NNN-short-slug` (e.g., `feat/adr-103-hook-silent-failure`)

**Parallel execution rules** (from ADR-093):
1. Orchestrator creates target branch BEFORE dispatching agents
2. Each agent prompt includes the branch name explicitly
3. All agents commit to that branch (or their worktree branch merges to it)
4. Orchestrator verifies convergence after all agents complete

**Worktree agent rules** (from ADR-126): When dispatching worktree agents, include the
worktree rules in each prompt. See `skills/meta/do/references/worktree-rules.md`. Key
rules: verify CWD contains `.claude/worktrees/`, create branch before edits, ignore
auto-plan hooks, stage specific files only, never touch the main worktree.

## Router Integration Checklist

_Required for any ADR that creates or modifies a skill, pipeline, or agent._

- [ ] Frontmatter triggers added/updated in component YAML
- [ ] INDEX.json regenerated (`generate-skill-index.py` or `generate-agent-index.py`)
- [ ] Entry added to `skills/meta/do/references/routing-tables.md`
- [ ] Trigger collision check passed (no duplicate triggers across force-routed entries)
- [ ] Pipeline companion map updated (if component pairs with existing pipelines)
- [ ] Quick-reference examples added to routing tables
- [ ] `routing-benchmark.py --verbose` passes in CI

_If this ADR does NOT create or modify a routable component, write "N/A — no routing changes" and skip._

## Consequences

### Positive
- [Concrete improvement]
- [Another improvement]

### Negative
- [Tradeoff or risk introduced]
- [Churn cost if applicable]

## Validation Requirements

**Skill Evaluator Gate**: Any skill or agent changes resulting from this ADR MUST be
validated using the skill evaluator (`/skill-eval`) before merging:

1. **Baseline capture**: Run `/skill-eval` on the affected skill(s) BEFORE implementation
   to establish a baseline score
2. **Post-implementation evaluation**: Run `/skill-eval` on the modified skill(s) AFTER
   implementation
3. **Pass criteria**: The post-implementation score MUST meet or exceed the baseline
   score. Regressions are blockers.
4. **Review evidence**: Include skill-eval output (before/after scores) in the PR
   description as proof of non-regression

This gate ensures that improvements to the toolkit's infrastructure do not inadvertently
degrade the quality of skill descriptions, trigger accuracy, or routing behavior. The
skill evaluator tests trigger matching, description clarity, and structural compliance —
the exact properties most likely to be affected by the changes in this ADR.

### Failure Remediation Protocol

If the skill evaluator score **regresses** (post-implementation < baseline):

1. **STOP** — Do not merge. The regression is a blocker.
2. **Dispatch 3 parallel perspective agents** to analyze the failure:
   - **Agent A (Contrarian)**: Challenge whether the change was necessary at all.
     Propose a simpler alternative that preserves the baseline score.
   - **Agent B (Domain Specialist)**: Analyze WHY the score dropped — which specific
     triggers, descriptions, or structural elements degraded? Propose targeted fixes.
   - **Agent C (User Advocate)**: Evaluate from the end-user perspective — does the
     change make the skill harder to discover or invoke? Propose routing improvements.
3. **Synthesize**: Collect all three perspectives. Identify the fix that addresses the
   root cause without over-engineering.
4. **Re-implement**: Apply the synthesized fix.
5. **Re-evaluate**: Run `/skill-eval` again. The new score must meet or exceed the
   original baseline.
6. **Max iterations**: 3 remediation cycles. If the score still regresses after 3
   attempts, escalate to the user with all three perspective reports and ask for a
   decision.

This loop ensures that no ADR implementation degrades the toolkit's routing
effectiveness, and that failures are diagnosed from multiple angles rather than
brute-forced.

### Risks
- [Specific risk from this ADR's implementation]
- [Another risk]
```

---

## Notes for ADR writers

**Context section must cite files**: Every claim in Context must have a file:line
reference. "The code does X" without a location is not verifiable.

**Include the critique verdict**: If the critique agent rated this finding DOWNGRADE
or CONFIRM, say so explicitly. This shows the operator that the finding survived
scrutiny before the ADR was written.

**Decision must be implementable**: A domain agent will read the Decision section and
execute it. "Improve error handling" is not implementable. "Replace bare `except:` on
line 47 of hooks/foo.py with `except (json.JSONDecodeError, OSError) as e:` and log
the error to stderr" is implementable.

**Components table is the source of truth**: The implementing agent only touches files
listed in the Components table. If a file is not listed, it will not be modified. Make
the table complete.

**Validation Requirements are mandatory**: Copy the Validation Requirements and Failure
Remediation Protocol sections verbatim for every ADR. Only adjust the skill names if
the ADR affects non-skill components (e.g., if it only modifies Python scripts with no
skill impact, note that skill-eval is not applicable for this ADR and explain why).

**Router integration is mandatory for new components**: If the ADR creates or modifies
any skill, pipeline, or agent, the Implementation Task List MUST include ALL of these
routing integration steps:

1. **Frontmatter triggers**: Add routing triggers to the component's YAML frontmatter
2. **INDEX.json regeneration**: Run the appropriate generator script:
   - Skills: `python3 scripts/generate-skill-index.py`
   - Pipelines: `python3 scripts/generate-skill-index.py` (handles both)
   - Agents: `python3 scripts/generate-agent-index.py`
3. **Routing table entry**: Add entry to `skills/meta/do/references/routing-tables.md`
4. **Trigger collision check**: Verify no trigger phrases overlap with existing entries
5. **Pipeline companion map**: If the new component pairs with existing pipelines, add to the companion map
6. **Quick-reference examples**: Add representative "user says X → routes to Y" examples
7. **CI validation**: Run `python3 scripts/routing-benchmark.py --verbose` to verify no regressions

Every ADR that creates a routable component without these steps will produce a component
that exists on disk but is invisible to `/do` — the most common source of "it exists but
nobody can find it" bugs in the toolkit.
