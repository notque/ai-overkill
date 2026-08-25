# Component Audit Checklists Reference

> **Scope**: Per-component-type audit checklists for agents, skills, hooks, and routing tables. Covers what to inspect, detection commands, and stale-pattern signals.
> **Version range**: vexjoy-agent, all versions
> **Generated**: 2026-04-15 — adapt checks to current frontmatter schema

---

## Overview

The AUDIT phase scans affected component types to identify what needs upgrading, deprecating,
or creating. The default scope is the 10 most-recently-modified agents + all hooks + affected
routing tables. Comprehensive audit (all 120+ components) is opt-in. The most common failure
is reading file names without opening the components — that detects presence, not stale patterns.

---

## Pattern Table: Scope by Change Signal

| Signal Type | Default Audit Scope | Skip |
|-------------|--------------------|----|
| New Claude tool available | All agents with `allowed-tools` list | Skills, hooks without tool use |
| New hook event type | All hooks matching event type | Agents, skills |
| Deprecated API | All components using that API string | Unrelated components |
| Routing trigger added | routing tables + affected agents | Hooks, scripts |
| Model name change | All agents with `model:` frontmatter | Hooks, routing tables |

---

## Agent Audit Checklist

For each agent in scope, check these fields in order:

```bash
# 1. Check model field is current
grep "^model:" agents/*.md | grep -v "sonnet\|opus"

# 2. Check allowed-tools for deprecated tools
grep -A 10 "allowed-tools:" agents/*.md | grep "deprecated_tool_name"

# 3. Check routing triggers for gaps (compare against routing table)
grep -A 20 "triggers:" agents/*.md

# 4. Check pairs_with for removed agents/skills
grep -A 10 "pairs_with:" agents/*.md

# 5. Check for outdated entries (patterns already resolved in prior upgrades)
grep -rn "Anti-Pattern" agents/*.md
```

**Per-agent audit fields to verify**:

| Field | Check | Stale Signal |
|-------|-------|-------------|
| `model:` | Is this a current model name? | Model ID no longer in active release |
| `allowed-tools:` | Are all listed tools still available? | Tool removed from Claude Code |
| `routing.triggers` | Does at least one trigger match the user's actual phrasing? | All triggers are technical jargon users never say |
| `routing.pairs_with` | Do all listed components still exist? | Agent or skill in the list no longer in the repo |
| `version:` | Is version incremented after substantive changes? | Version stuck at `1.0.0` across many commits |

---

## Skill Audit Checklist

Skills are invoked via the Skill tool by name. Check:

```bash
# 1. Find skills with no routing triggers (unroutable)
grep -L "triggers:" skills/*/SKILL.md

# 2. Find skills referencing removed scripts
grep -rn "python3 scripts/" skills/*/SKILL.md | while read match; do
  script=$(echo "$match" | grep -oP 'scripts/[^ ]+\.py')
  [ -f "$script" ] || echo "MISSING: $script in $match"
done

# 3. Check phase count matches header count
grep -c "^## Phase\|^### Phase" skills/*/SKILL.md
```

**Per-skill audit fields**:

| Field | Check | Stale Signal |
|-------|-------|-------------|
| Phase references | Do all script calls resolve to real files? | `FileNotFoundError` at runtime |
| Agent dispatch | Do dispatched agents still exist? | Agent removed but skill still dispatches it |
| Output contract | Does the output schema match what downstream tools expect? | Silent data loss in pipelines |

---

## Hook Audit Checklist

Hooks are the most fragile components — they fire on every tool call and exit code matters.

```bash
# 1. Find hooks with syntax errors (will kill sessions)
for f in hooks/*.py; do python3 -c "import ast; ast.parse(open('$f').read())" 2>&1 | grep -v "^$" && echo "SYNTAX ERROR: $f"; done

# 2. Find hooks registered in settings but not deployed to ~/.claude/hooks/
python3 -c "
import json, os
s = json.load(open(os.path.expanduser('~/.claude/settings.json')))
for event_hooks in s.get('hooks', {}).values():
    for h in event_hooks:
        p = h.get('command', '')
        if 'hooks/' in p:
            fname = p.split('hooks/')[-1].split()[0]
            if not os.path.exists(os.path.expanduser(f'~/.claude/hooks/{fname}')):
                print(f'NOT DEPLOYED: {fname}')
"

# 3. Find hooks that import missing modules
grep -rn "^from hooks\.\|^import hooks\." hooks/*.py

# 4. Check exit codes are consistent
grep -n "sys.exit" hooks/*.py | grep -v "sys.exit(0)\|sys.exit(1)\|sys.exit(2)"
```

**Hook exit code contract**:

| Exit Code | Meaning | When to Use |
|-----------|---------|-------------|
| `0` | Allow — no message shown to user | Normal pass-through |
| `1` | Block — show stderr to user as warning | Soft gate (user can override) |
| `2` | Block — show stderr as error | Hard gate (cannot override) |

**Critical**: Exit code `2` on every PreToolUse deadlocks the session entirely. Hooks with
syntax errors silently return non-zero. Always verify with `python3 -c "import ast; ast.parse(...)"`.

---

## Routing Table Audit Checklist

Routing tables live in `skills/meta/do/references/routing-tables.md` and companion files.

```bash
# 1. Find agents referenced in routing table that no longer exist
python3 -c "
import re
table = open('skills/meta/do/references/routing-tables.md').read()
agents = re.findall(r'\|\s*([a-z][a-z-]+engineer|[a-z][a-z-]+agent)\s*\|', table)
import os
for a in set(agents):
    if not os.path.exists(f'agents/{a}.md'):
        print(f'MISSING AGENT IN TABLE: {a}')
"

# 2. Find agents in repo not present in routing table
grep -rh "^name:" agents/*.md | awk '{print $2}' | while read name; do
  grep -q "$name" skills/meta/do/references/routing-tables.md || echo "NOT IN TABLE: $name"
done

# 3. Find routing table entries with no trigger keywords
grep -B 1 "No trigger\|no keywords\|\[\]" skills/meta/do/references/routing-tables.md
```

---

<!-- no-pair-required: section header, not a standalone failure mode block -->
## Pattern Catalog

### Open and Read Component Frontmatter During Audit

**Detection**:
```bash
# Check if AUDIT report cites specific fields (it should, not just filenames)
grep -c "triggers:\|allowed-tools:\|model:" task_plan.md
# Should be > 0 for a real audit
```

**Why this matters**: File existence confirms a component exists; it does not confirm it's stale or
current. Triggers that are never phrased by actual users will never route. A model name frozen
at an old value will use the wrong capability tier.

Do instead: Open and read each component's frontmatter and body. Check specific fields.

---

### Scope Audit to Affected Component Types

**Detection**:
```bash
# Detect if audit report lists all 120+ components for a 2-hook change
wc -l task_plan.md
# An audit for 2 hooks should not produce a 500-line task plan
```

**Why this matters**: Auditing 120+ skills for a single hook event change produces noise and makes
it impossible to distinguish affected from unaffected components. Tier assignment degrades.

Do instead: Scope audit to the component types identified in the Change Manifest signal column.

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| Session deadlocks on every tool call | Hook with exit code 2 deployed to `~/.claude/hooks/` with syntax error | `python3 -c "import ast; ast.parse(...)"` on every hook before deploying |
| Agent dispatch fails silently | `pairs_with` references a removed component | Audit `pairs_with` for all in-scope agents |
| Routing gap — user triggers fall through to default | Routing table references old trigger text | Call the Skill tool with `routing-table-updater`. Do this after agent changes. |
| Script call at runtime raises FileNotFoundError | Skill references moved or deleted script | `find scripts/ -name "*.py"` and reconcile all skill references |

---

## Detection Commands Reference

```bash
# Agents: stale model name
grep "^model:" agents/*.md | grep -v "sonnet\|opus"

# Hooks: syntax errors
for f in hooks/*.py; do python3 -m py_compile "$f" 2>&1 | grep -v "^$" && echo "ERROR: $f"; done

# Hooks: undeployed (registered in settings but missing from ~/.claude/hooks/)
# (see full command in Hook Audit Checklist section above)

# Routing table: agents referenced but missing
# (see full command in Routing Table Audit Checklist section above)

# Skills: broken script references
grep -rn "python3 scripts/" skills/*/SKILL.md
```
