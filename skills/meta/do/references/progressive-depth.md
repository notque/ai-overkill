# Progressive Depth Routing

Start every task at the shallowest viable depth. Escalate only when evidence demands it. A 2-line fix stays a 2-line fix. A task that reveals hidden complexity gets escalated to full skill methodology.

The router's initial complexity classification is a *starting point*, not a commitment. Uncertainty about depth is normal — the correct response is to start shallow and let the work surface the real complexity, not to guess high "just to be safe."

---

## Depth Levels

### Level 0: Inline

Router handles directly. No agent dispatched.

**When**: The user named an exact file path to read, or asked a question answerable from conversation context.

**Examples**: "Read `scripts/index-router.py`", "What branch am I on?", "Show me the last commit."

### Level 1: Quick Trivial

Use `quick --trivial` for tasks that appear to be 1-3 file edits.

**When**: The change looks self-contained — a bug fix, a config tweak, adding a small block of code. The agent attempts the fix and watches for escalation signals.

**Examples**: "Fix the typo in docs/router-ab-runbook.md", "Add a --verbose flag to index-router.py", "Update the version number in SKILL.md."

**Escalation signals** (any one triggers escalation):
- More than 3 files need changes
- Test failures reveal deeper issues than the original fix
- Architectural questions arise (e.g., "should this be a new module?")
- The fix has side effects in other modules
- The agent is uncertain about the correct approach

### Level 2: Methodical

Dispatch agent with domain-appropriate skill (full phase-gated workflow).

**When**: Level 1 escalated, or the router classifies the task as Medium complexity. The task requires understanding multiple files, running tests, or following a multi-step methodology.

**Examples**: "Refactor the routing system to support plugin skills", "Add webhook support to the notification service", "Debug why CI fails on the go-patterns tests."

### Level 3: Pipeline

Multi-agent pipeline with planning, execution, and review.

**When**: Level 2 escalated due to cross-cutting concerns, or the router classifies as Complex. The task spans multiple domains, requires coordination between agents, or involves architectural decisions.

**Examples**: "Implement a new feature lifecycle for the toolkit", "Migrate the entire test suite from Jest to Vitest", "Add multi-repo support to the routing system."

---

## Escalation Signal Format

When an agent at any level determines it needs escalation, it must emit a structured signal — not silently produce degraded output:

```
[ESCALATION-NEEDED]
Current level: 1 (Fast)
Reason: Found 7 files need changes, original estimate was 2
Recommended level: 2 (Methodical)
Work completed so far: Fixed the primary file (docs/router-ab-runbook.md), discovered 6 other references that need matching updates
```

The router receives this signal, preserves the work completed so far, and re-dispatches at the recommended level with context about what was already done.

---

## User Escape Hatch

Users can override depth at any time during routing or execution:

| User says | Effect |
|-----------|--------|
| "go deeper" / "use full workflow" | Escalate to Level 2 (Methodical) |
| "keep it simple" / "just fix it" | Stay at current level, skip enhancements |
| "full pipeline" | Escalate to Level 3 (Pipeline) |
| "start over deeper" | Abandon current work, restart at specified level |

The escape hatch exists because the user has context the router lacks. An override is a routing signal: the routing hooks record the dispatch and score its outcome on the next turn, so the corrected depth shows up in `learning-db.py route-health` without any extra step.

---

## Mapping to Router Classification

Progressive depth modifies how classification maps to execution, not the classification itself:

| Router classification | Default depth | Progressive depth |
|-----------------------|---------------|-------------------|
| Trivial | Inline | Level 0: Inline (same) |
| Simple | Agent + skill | Level 1: Quick Trivial (start shallow, escalate if needed) |
| Medium | Agent + skill | Level 2: Methodical (or Level 1 if task looks simpler than Medium) |
| Complex | Pipeline | Level 3: Pipeline (or Level 2 if task looks simpler than Complex) |

The key change: **Simple and Medium tasks start at Level 1 when the scope is ambiguous.** If the agent can finish at Level 1, it does — saving the overhead of full skill methodology. If it cannot, the escalation signal triggers Level 2 with no work lost.

---

## Patterns to Detect and Fix

| Failure Mode | Why it fails | Correct behavior |
|--------------|-------------|------------------|
| Starting at Level 2 "just to be safe" | Defeats the purpose; burns tokens on methodology the task doesn't need | Start at Level 1, let evidence drive escalation |
| Escalating without evidence | Phantom complexity; the agent imagines problems that don't exist | Must cite a concrete escalation signal |
| Silent degradation | Shallow agent produces wrong output instead of escalating | Agent must emit `[ESCALATION-NEEDED]` when hitting limits |
| Ignoring user override | User said "go deeper" but agent continues at current level | User overrides are immediate and unconditional |
| Re-doing completed work after escalation | Level 2 agent restarts from scratch instead of building on Level 1 output | Escalation signal includes "work completed so far" — Level 2 continues from there |
