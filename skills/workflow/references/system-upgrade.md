---
description: "6-phase pipeline for adapting agents, skills, and hooks to changes."
user-invocable: false
agent: system-upgrade-engineer
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
    - system upgrade
    - upgrade agents
    - claude update
    - upgrade skills
    - adapt workflow
    - system health
  pairs_with:
    - agent-upgrade
    - agent-evaluation
  complexity: Complex
  category: meta
---

# System Upgrade Pipeline

## Overview

This skill orchestrates systematic upgrades to the agent/skill/hook/script ecosystem when external changes warrant adaptation. It is a **top-down** upgrade mechanism—triggered by Claude Code releases, user goal changes, or routing telemetry that shows components failing—complementing the **bottom-up** `agent-upgrade` pipeline that fixes one component at a time.

Present the ranked plan in Phase 3. Continue when the user has already authorized that scope; ask only for uncovered actions or material scope changes. A plan-only request stops at the plan.

---

## Instructions

### Phase 1: CHANGELOG

**Goal**: Parse the external change and extract actionable upgrade signals.

**Determine trigger type** from user's input:

| Trigger Type | Signals | Input Format |
|-------------|---------|--------------|
| `claude-release` | "claude update", "new version", "release notes", "shipped X" | Version number or release notes text |
| `goal-change` | "I now want", "we're moving to", "new focus", "deprecate X" | User's description of the change |
| `telemetry-driven` | "routes are failing", "fix the weak agents", `/retro routing` showed weak routes | `learning-db.py route-health` output |

**For `claude-release`**: Extract from user's input or web search for Claude Code release notes:
- New hook event types (e.g., `Notification`, `ToolResult`)
- New tool capabilities or changed defaults
- New slash command patterns
- Deprecated features or behaviors
- New frontmatter fields for agents/skills

**For `goal-change`**: Parse the user's statement into:
- What domains/workflows are now in scope (NEW)
- What domains/workflows are no longer in scope (DEPRECATED)
- What patterns should be applied everywhere (ENFORCE)

**For `telemetry-driven`**: Read routing telemetry for components that carry traffic and fail on it:
```bash
python3 ~/.claude/scripts/learning-db.py route-health
python3 ~/.claude/scripts/learning-db.py route-stats --by errors
```
Read the outcome basis before the rates — a rate computed mostly from neutral outcomes describes the scorer, not the component. A route with many dispatches and a high error rate is an upgrade signal; a route with none is a retirement candidate.

**Output**: A structured "Change Manifest"—a list of change signals with type, description, and likely affected component types.

**Gate**: Change Manifest has at least 1 actionable signal. If zero signals found, report to user and stop.

---

### Phase 2: AUDIT

**Goal**: Scan the codebase and identify which components are affected by the Change Manifest.

**Step 0**: Check for incremental mode.

```bash
python3 ~/.claude/scripts/upgrade-diff.py
```

Evaluate the JSON output:
- If `mode` is `"incremental"` and `total_changed > 0`: scope the audit to only the files listed in `changed`. Skip Step 1 (audit depth) and proceed directly to Step 2 using only these components.
- If `mode` is `"incremental"` and `total_changed == 0`: report "No components changed since last upgrade" to the user and **stop**. No further phases are needed. (This prevents wasted effort when nothing has changed since the last upgrade.)
- If `mode` is `"full"` (first run or `--full` flag): proceed with existing full audit behavior starting at Step 1.

**Step 1**: Determine audit depth.
- **Default**: 10 most-recently-modified agents + all hooks + all relevant skills. This balances thoroughness with speed, focusing on components most likely to need changes.
- **Comprehensive**: all agents + all skills + all hooks. (Enable only if user says "comprehensive" or "all"; full audits are slower but ensure complete coverage.)

```bash
# Get most recently modified agents
ls -t agents/*.md | head -10

# Get all hooks
ls hooks/*.py

# Get relevant skills based on change signals
```

**Step 2**: For each change signal in the Change Manifest, search for affected components:

```bash
# Example: "new Notification hook event" signal
grep -l "PostToolUse\|PreToolUse\|SessionStart" hooks/*.py
grep -rn "event_type\|hook_event" hooks/

# Example: "user wants Go concurrency everywhere" signal
grep -l "goroutine\|concurrency" agents/*.md skills/*/SKILL.md
```

**Step 3**: For each affected component, classify the required change:

| Change Type | Description | Effort |
|------------|-------------|--------|
| `deprecate` | Component is now obsolete or superseded | Low |
| `upgrade` | Component needs modification to use new capability | Medium |
| `create-new` | Gap identified—new component needed | High |
| `inject-pattern` | Add a new hardcoded behavior or rule | Low-Medium |

**Step 4**: Produce the **Audit Report**—a list of affected components with their change type and rationale.

**Gate**: Audit Report produced. Proceed to Phase 3.

---

### Phase 3: PLAN

**Goal**: Present a ranked plan and check it against the user’s authorized scope.

**Step 1**: Sort the Audit Report by priority:

| Tier | Criteria | Examples |
|------|----------|---------|
| **Critical** | Broken functionality or security | Hook that references deprecated event type |
| **Important** | Missing new capability that changes quality | Agent not using new hook capability |
| **Minor** | Style alignment or cosmetic | Agent missing new optional frontmatter field |

**Step 2**: Present the ranked plan to the user:

```
SYSTEM UPGRADE PLAN
===================

Trigger: [claude-release | goal-change | telemetry-driven]
Change: [brief description]

Proposed Changes (Ranked):

CRITICAL (must fix):
  1. hooks/routing-decision-recorder.py — Add Notification event handler [upgrade, ~30min]
  2. hooks/pretool-subagent-warmstart.py — Update for new tool event format [upgrade, ~20min]

IMPORTANT (should fix):
  3. agents/hook-development-engineer.md — Document Notification event type [inject-pattern, ~15min]
  4. skills/engineering/go-patterns/SKILL.md — Apply the new pattern from the release notes [inject-pattern, ~10min]

MINOR (nice to have):
  5. agents/skill-creator.md — Add new frontmatter field docs [upgrade, ~5min]

Total: 5 changes across 5 components
Parallel dispatch: 3 groups (hooks, agents, skills)

Proceed with implementation? (or modify the plan)
```

**Step 3**: Apply existing authorization. If the user requested implementation of these changes, proceed without another confirmation. Present uncovered changes separately and ask before doing them. Honor plan-only, interactive, and stop requests; continue independent authorized work while waiting.

**Gate**: Plan presented and implementation scope authorized. Use an assigned feature branch or create one before editing.

```bash
git checkout -b chore/system-upgrade-$(date +%Y-%m-%d)
```

---

### Phase 4: IMPLEMENT

**Goal**: Execute the approved plan by dispatching domain agents for each change. (Reuse domain agents; the upgrade engineer orchestrates while specialists execute. Parallel fan-out when 3+ changes target the same domain.)

**Step 1**: Group changes by domain agent that should handle them:

| Change Domain | Domain Agent |
|--------------|-------------|
| Hook modifications | hook-development-engineer |
| Agent upgrades | skill-creator |
| Skill upgrades | skill-creator |
| Routing changes | routing-table-updater |
| Pattern injection | skill-creator or direct Edit |

**Step 2**: Dispatch parallel agents for independent groups. Use a single message with multiple Agent tool calls for changes that don't depend on each other.

For each dispatched agent, provide:
- The specific component to modify (file path)
- The exact change to make (from Phase 3 plan)
- The rationale (from the Change Manifest)
- The relevant context (surrounding code, other files that reference this component)

**Step 3**: For low-effort changes (inject-pattern, Minor tier), make direct edits rather than dispatching agents. Batch these into one pass. (This avoids overhead for simple changes while reserving agents for complex work.)

**Step 4**: Track completion. Mark each planned item as done as agents complete.

**Gate**: All approved changes implemented. No pending items.

---

### Phase 5: VALIDATE

**Goal**: Verify the changed behavior and preserve useful knowledge.

**Step 1**: Review the diff for lost domain rules, broken references, and changed contracts. Run the relevant existing tests and required repository checks. Reuse passing results for unchanged inputs.

Call the Skill tool with `verification-before-completion`. It owns verification requirements. Use `agent-evaluation` when the user requests scoring or a concrete uncertainty needs it; model scoring is not a default release gate.

```
VALIDATION REPORT
=================

[component]
  Checks: [commands and results]
  Findings: [fixed issues or remaining gaps]
  Evaluation: [scores if requested, otherwise not run]
```

**Step 2**: Fix confirmed regressions within scope and rerun affected checks. Report unresolved findings; blocking correctness or security issues prevent delivery. Ask when resolving a finding requires an unapproved tradeoff.

**Gate**: Required checks pass and blocking findings are resolved. Proceed to Phase 6.

---

### Phase 6: DEPLOY

**Goal**: Deliver through the authorized PR workflow, then sync the accepted revision.

**Step 1**: Call the Skill tool with `pr-workflow`. It owns selective staging, review reuse, commit, push, CI, and merge requirements. Stage only this task's files. Do not install an unreviewed feature branch into the live user configuration.

**Step 2**: If merge and local sync are authorized, verify all required checks on the current PR head, merge, and update the designated integration checkout. With parallel workers, the coordinator alone syncs the main checkout and installed configuration. If the request ends at PR creation, report that state and leave live installation unchanged.

**Step 3**: After successful integration and sync, record the accepted revision from that checkout:
```bash
python3 scripts/upgrade-diff.py --record
```

**Step 5**: Produce completion summary:

```
SYSTEM UPGRADE COMPLETE
=======================

Trigger: [type and description]
Branch:  chore/system-upgrade-YYYY-MM-DD
PR:      [URL]

Changes Applied:
  ✓ [N] Critical
  ✓ [N] Important
  ○ [N] Minor (skipped/deferred)

Validation: [required checks and results; scores only if requested]

Next Upgrade: Run /system-upgrade after next Claude Code release
              or when /retro routing shows several weak routes
```

**Gate**: The authorized delivery state is confirmed. Record the upgrade SHA only after integration and sync. Report a PR-only result as awaiting integration.

---

## Error Handling

### Error: "No actionable signals in Change Manifest"
Cause: The changelog/goal statement didn't produce clear change signals.
Solution: Ask user to be more specific. "Claude Code shipped X" → "what specific feature in X applies to our hooks/agents?"

### Error: "Domain agent returned incomplete work"
Cause: Dispatched agent didn't finish all changes in its group.
Solution: Re-dispatch with more specific instructions. Check agent output for errors. Continue to Phase 5 only after the required work is complete.

### Error: "Regression detected in Phase 5"
Cause: A component scored lower after modification.
Solution: Show the diff of changes to the user. Offer to revert the specific component and wait for the user's choice.

### Error: "Sync script not found"
Cause: `hooks/sync-to-user-claude.py` missing or broken.
Solution: Manually copy modified files to `~/.claude/` equivalent directories. Report the broken sync script for future fixing.

---

## References

- [agent-upgrade](./agent-upgrade.md) - Bottom-up single-agent upgrade pipeline (complements this top-down system pipeline)
- [agent-evaluation](../../skills/meta/agent-evaluation/SKILL.md) - Objective scoring skill used in Phase 5 validation
- [pr-pipeline](./pr-pipeline.md) - PR creation pipeline used in Phase 6 deploy
- [upgrade-diff.py](../../scripts/upgrade-diff.py) - Incremental diff script for scoping audits
- [learning-db.py](../../scripts/learning-db.py) - Read-only CLI for routing telemetry (`route-health`, `route-stats`)
