# Upgrade Orchestration Failure Modes Reference

> **Scope**: Common orchestration failures in the 6-phase system-upgrade workflow: premature implementation, approval gate bypass, inline edits, and scope creep. Covers detection and remediation.
> **Version range**: system-upgrade-engineer, all versions
> **Generated**: 2026-04-15

---

## Overview

The system-upgrade workflow has mandatory gates and specialist dispatch rules. The most damaging
failures are silent: implementing outside authorized scope, making domain changes inline
instead of delegating to specialists, and running full-repo audits for scoped changes. These
produce either unauthorized bulk edits or subtly incorrect results that bypass domain validation.

---

<!-- no-pair-required: section header, not a standalone failure mode block -->
## Failure Mode Catalog

### Implementing Without Authorized Scope

**What it looks like**: Applying changes outside the user’s request or skipping the ranked PLAN presentation.

**Why wrong**: The user must control which upgrades happen. Requiring a second approval for an accepted plan also blocks requested work.

Do instead: Follow `skills/workflow/references/system-upgrade.md` Phase 3. Present the ranked table, continue within existing authorization, and ask about uncovered changes. Honor interactive and plan-only requests.

---

### Implementing Domain Changes Inline

**What it looks like**: Directly editing `hooks/posttool-rename-sweep.py` instead of
dispatching `hook-development-engineer`. Writing new agent frontmatter inline instead of
dispatching `skill-creator`.

Do instead: dispatch `hook-development-engineer` for hook changes, `skill-creator` for agent
and skill changes, and `routing-table-updater` for routing table changes. Details follow.

**Detection**:
```bash
# Look for direct file edits to domain files in agent output logs
grep -rn "Edit\|Write" hooks/*.py agents/*.md --include="*.py" --include="*.md" 2>/dev/null
# system-upgrade-engineer should only create task_plan.md and branch setup files
```

**Why wrong**: Domain specialists (hook-development-engineer, skill-creator) carry template
conventions, event schema knowledge, and frontmatter validation that inline edits bypass.
A hook written inline without hook-development-engineer's exit code contract knowledge will
likely use wrong exit codes. An agent written inline will miss required frontmatter fields.

Do instead:
- Hook changes → dispatch `hook-development-engineer`
- Agent/skill changes → dispatch `skill-creator`
- Routing table changes → dispatch `routing-table-updater` skill
- Only create `task_plan.md` and branch setup files directly

---

### Not Scoping the Audit to Signal-Identified Components

**Detection**:
```bash
# Check if audit scanned all components for a targeted change
grep -c "Scanned\|checked\|audited" task_plan.md
# An audit for 2-hook changes should reference < 20 components, not 120+

# Check signal column presence in Change Manifest
grep "Component Types\|component type" task_plan.md
# Should be present — if missing, audit had no scope
```

**Why wrong**: Auditing all 120+ skills for a 2-hook change produces noise proportional to
scope. When every component appears in the audit, the PLAN phase cannot distinguish affected
from unaffected. Tier assignment degrades to noise.

Do instead: Build the Change Manifest with a "Component Types" column first. Default scope
is 10 most-recently-modified agents + all hooks + affected routing tables. Comprehensive
audit only with the explicit "comprehensive" keyword from the user.

---

### Skipping Required Validation

**What it looks like**: Shipping directly after IMPLEMENT without checking changed behavior and affected contracts.

**Why wrong**: Neither a smaller file nor a model score proves correctness.

Do instead: Follow the pipeline’s VALIDATE phase and report real checks and findings. Scoring is optional; required checks and blocking findings still govern delivery.

---

### Force-Pushing or Committing to Main

**Detection**:
```bash
# Confirm current branch is not main before any writes
git branch --show-current
# Should NEVER be main during an upgrade run

# Check no force-push flags in recent git commands
history | grep "push --force\|push -f"
```

**Why wrong**: Commits to main bypass branch protection and review. Force-push to main
overwrites upstream state and is unrecoverable without a backup. The branch naming
convention (`chore/system-upgrade-YYYY-MM-DD`) exists to ensure all changes go through PR.

Do instead: Run `git checkout -b chore/system-upgrade-YYYY-MM-DD` before Phase 4. Never
use `--force` or `-f` on push. If already on main, stash and create branch before proceeding.

---

### Reporting Regression as "Necessary"

**Detection**:
```bash
# Check VALIDATE section for score drops paired with justification phrases
grep -A 3 "score.*lower\|regressed\|dropped" task_plan.md | grep -i "necessary\|intentional\|expected\|trade-off"
# These phrases in the same context indicate a rationalized regression
```

**Why wrong**: Regressions are user decisions, not agent decisions. When a component
scores lower after modification, the agent's job is to surface it clearly, not to
rationalize it away. The user may have context that makes the tradeoff acceptable;
the agent does not have that context.

Do instead: Report the regression factually: "Component X scored N before, M after (delta -K).
Cause: [specific change]. Recommend: revert or acknowledge." Then wait.

---

## Parallel Dispatch Patterns

### When to Fan Out

Dispatch parallel Agent calls when:
- 3 or more independent changes of the same type (e.g., 4 hooks need the same upgrade)
- Changes target different component types (hook + agent + routing table, no interdependency)
- A/B comparison of two upgrade approaches

```markdown
## Parallel Group Assignment (Phase 3 output format)

| Tier | Component | Change Type | Effort | Group |
|------|-----------|------------|--------|-------|
| Critical | hooks/rename-sweep.py | upgrade | S | Group A |
| Critical | hooks/branch-safety.py | upgrade | S | Group A |
| Important | agents/hook-dev-engineer.md | inject-pattern | M | Group B |
| Important | skills/routing-table-updater | upgrade | M | Group B |
| Minor | routing-tables.md | update | S | Group C |
```

Dispatch Group A in a single message (parallel). Wait for completion. Then Group B. Then C.

### When NOT to Fan Out

Use a single agent when:
- Change B depends on output from Change A (sequential dependency)
- Both agents would edit the same file (race condition)
- The approval gate has not yet been cleared

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| Session deadlock after hook deploy | Hook deployed before syntax verification | `python3 -m py_compile hook.py` before `cp` to `~/.claude/hooks/` |
| PR merge fails — CI checks failed | Ruff lint or format error in .py files created during upgrade | `ruff check . && ruff format --check .` before push |
| Agent dispatch returns empty output | Dispatched specialist had insufficient context | Re-dispatch with narrower scope and explicit file paths |
| Routing gap after upgrade | New agent not added to routing tables | Call the Skill tool with `routing-table-updater`. Do this after every new agent. |
| Component scores unchanged (no improvement) | Upgrade changed names but not behavior | Verify upgrade touched functional content, not just formatting |

---

## Phase Gate Summary

| Phase | Gate | Consequence of Skipping |
|-------|------|------------------------|
| Phase 1 → Phase 2 | 0 signals check | Audit scans everything with no focus |
| Phase 2 → Phase 3 | All components opened and checked | Plan tier assignments are wrong |
| Phase 3 → Phase 4 | Plan presented and scope authorized | Unauthorized bulk edits |
| Phase 4 → Phase 5 | Branch exists, not main | Risk of main commit or force push |
| Phase 5 → Phase 6 | Required checks pass and blocking findings resolved | Regressions ship without user awareness |

---

## Detection Commands Reference

```bash
# Confirm not on main before writes
git branch --show-current

# Check Phase 3 plan was presented before writes
grep "PLAN\|approval\|proceed" task_plan.md

# Verify agent-evaluation was run (Phase 5)
grep "agent-evaluation\|score.*before\|score.*after" task_plan.md

# Check for regression rationalization phrases
grep -i "necessary\|intentional\|expected trade" task_plan.md

# Verify no inline domain edits (system-upgrade-engineer should not edit hook files directly)
git diff --name-only HEAD | grep "^hooks/" | head -5
# Should be empty — hooks should only be touched by hook-development-engineer
```
