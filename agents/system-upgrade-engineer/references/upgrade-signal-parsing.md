# Upgrade Signal Parsing Reference

> **Scope**: Extracting actionable upgrade items from Claude Code release notes, user goal changes, and learning.db retro candidates. Does NOT cover component implementation — only parsing and classification.
> **Version range**: Claude Code releases, all versions
> **Generated**: 2026-04-15 — verify signal categories against current release format

---

## Overview

Upgrade signals arrive in three forms: Claude Code release notes (feature additions, deprecations,
breaking changes), user goal-change statements (new workflows to support), and retro-driven signals
from the learning.db graduation queue. Each form requires a different parsing strategy. The most
common failure is treating a feature mention as an upgrade requirement without identifying *which
component type* is affected.

---

## Signal Type Classification

| Signal Form | Entry Point | Affected Components | Urgency Heuristic |
|-------------|-------------|--------------------|--------------------|
| Claude Code release note | `feat:` / `fix:` / `BREAKING:` prefix | Hooks (new events), agents (new capabilities), routing tables | BREAKING = Critical; new tool = Important; fix = Minor |
| User goal change | "from now on", "whenever X", "always Y" | Hooks (behavioral automation), agents (routing triggers) | User-stated = Critical |
| Retro graduation | `learning.db` candidates with `status=candidate` | Agent failure modes, skill instructions | Recurrence count drives priority |

---

## Pattern Table: Release Note Keywords → Component Types

| Keyword Pattern | Component Type | Change Action |
|-----------------|---------------|---------------|
| `new tool:`, `added tool` | Agents with `allowed-tools` | Add to `allowed-tools` list |
| `deprecated:`, `removed:` | Any component using deprecated API | `deprecate` or `upgrade` |
| `BREAKING:` + tool name | All hooks using that tool | `upgrade` — verify event schema |
| `hook event:`, `new event type` | Hooks registered for that event | `create-new` or `upgrade` |
| `model:`, `default model changed` | Agents with hardcoded model names | `upgrade` — update model field |
| `compaction`, `context window` | Hooks monitoring session state | `upgrade` — adjust thresholds |

---

## Correct Patterns

### Building a Change Manifest from a Release Note

Parse each actionable item as a triple: (what changed, which component types are affected, urgency tier).

```markdown
## Change Manifest — Claude Code vX.Y

| Signal | Component Types | Change Action | Tier |
|--------|----------------|--------------|------|
| New `Write` tool event type in PostToolUse | Hooks with PostToolUse | Upgrade event schema | Critical |
| Deprecated `--json` flag in bash | Scripts using bash --json | Upgrade call sites | Important |
| New Claude model released (e.g. `claude-<family>-<version>`) | Agents with model: sonnet | Review model field | Minor |
```

**Why**: A manifest without the component-type column causes the AUDIT phase to scan everything.
Scoping to component types cuts audit time from O(all) to O(affected).

---

### Parsing a User Goal-Change Statement

Extract the automation trigger and the behavioral change. Map trigger → hook event type.

```markdown
User: "from now on when a file is renamed, update all imports"

Parse:
- Trigger: file renamed (PostToolUse on Write/Edit with path change detection)
- Behavior: update imports (new hook, requires Bash tool)
- Affected: hooks/posttool-rename-sweep.py (exists — upgrade) OR new hook (create-new)
- Urgency: Critical (user-stated)
```

**Why**: Goal-change statements always imply automation (hooks), not one-time actions.
If no existing hook covers the trigger, `create-new` is the right action.

---

### Classifying Retro-Driven Signals

Query learning.db for graduated patterns and map to component updates.

```bash
# Find retro candidates with recurrence > 2
python3 scripts/learning-db.py list --status candidate --min-count 3

# Find patterns associated with specific component type
python3 scripts/learning-db.py list --component-type agent --status candidate
```

Map recurrence count to tier:
- Count >= 5: Critical (pattern is systemic, not one-off)
- Count 2-4: Important
- Count 1: Minor (may be noise)

---

<!-- no-pair-required: section header, not a standalone failure mode block -->
## Pattern Catalog

### Require At Least One Signal Before Proceeding

**Detection**:
```bash
# Look for empty Change Manifest tables in task_plan.md
grep -A 5 "Change Manifest" task_plan.md | grep -c "^|"
# Should be > 1 (header row + at least one data row)
```

**Why this matters**: A zero-signal manifest means the trigger was too vague. The AUDIT phase will
scan all components with no scoping, producing noise and wasting time. Phase 1 instructions
explicitly say: "If you extracted 0 actionable signals, do not proceed."

Do instead: Ask the user for specifics. Quote the exact feature or change being referenced.

---

### Verify Interface Change Before Scheduling Upgrade

**Signal**: A release note mentions "improved JSON output" and the agent
immediately schedules upgrades to every script that uses JSON.

**Why this matters**: Not every mention is a breaking change. Only changes that alter the
interface (tool signature, event schema, model name) require upgrades.

Do instead: For each signal, ask: "Does this change the interface a component depends on?"
If no: Minor or skip. If yes: Important or Critical.

---

### Separate Signal Types by Source in Manifest

**Signal**: A single Change Manifest combining release-note signals, user
goal-change statements, and retro signals without flagging their source.

**Why this matters**: Each signal type has different urgency heuristics and different component
scope. Mixing them without source labels causes the PLAN phase to assign wrong tiers.

Do instead: Separate into sections by signal type. Label each row with its source.

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| "No signals found in changelog" | Input too vague (e.g., "update for the new Claude") | Ask for specific feature or change name |
| AUDIT scanning all 120+ components | Signal type column missing from manifest | Add component-type column before proceeding |
| Change action undefined for a signal | Signal classified but action not specified | Force a choice: deprecate / upgrade / create-new / inject-pattern |
| Tier not assigned | Urgency heuristic skipped | Apply: BREAKING=Critical, new=Important, fix=Minor |

---

## Detection Commands Reference

```bash
# Find retro candidates with recurrence > 2
python3 scripts/learning-db.py list --status candidate --min-count 3

# Check learning.db for agent-specific patterns
python3 scripts/learning-db.py list --component-type agent --status candidate

# Verify Change Manifest has data rows
grep -A 5 "Change Manifest" task_plan.md | grep -c "^|"

# Find components using a deprecated pattern (replace PATTERN)
grep -rn 'PATTERN' agents/ skills/ hooks/ --include="*.md" --include="*.py"
```
