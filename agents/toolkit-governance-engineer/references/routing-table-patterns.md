# Routing Table Patterns Reference

> **Scope**: Routing table entry structure, intent-based descriptions, trigger conflicts, phantom route prevention, and index validation. Does not cover frontmatter field compliance (see frontmatter-compliance.md).
> **Version range**: all routing table versions
> **Generated**: 2026-04-15

---

## Overview

The routing system maps user intent to agents and skills via trigger phrases and metadata. Phantom routes (entries pointing to nonexistent components) and ambiguous triggers (two components claiming the same phrase) are the most common failure modes — both cause silent routing failures where the router selects a component that doesn't exist or picks the wrong one without warning.

---

## Routing Entry Structure

A complete routing entry in an agent's frontmatter:

```yaml
routing:
  triggers:
    - edit skill          # primary trigger phrase
    - update routing      # secondary trigger phrase
    - ADR management      # domain-specific trigger
  pairs_with:
    - adr-consultation    # agents commonly invoked together
    - routing-table-updater
  complexity: Medium
  category: meta
```

| Field | Required | Type | Purpose |
|-------|----------|------|---------|
| `triggers` | yes | list of strings | Intent phrases that route to this component |
| `pairs_with` | no | list of agent names | Agents frequently co-dispatched with this one |
| `complexity` | yes | `Low`/`Medium`/`High` | Selects execution strategy |
| `category` | yes | string | Groups components in coverage reports |

---

## Intent-Based Description Format

Routing table descriptions must answer three questions: **what**, **when to use**, **when NOT to use**.

```yaml
# Correct — answers what, when, and when-not
description: >
  Toolkit governance: edit skills, update routing tables, manage ADR lifecycle,
  enforce cross-component standards. Use for toolkit maintenance and internal
  consistency checks. NOT for application code review or new component creation.

# Wrong — only states what, no routing signal
description: Manages toolkit components
```

**Why**: The routing system uses the description for fuzzy intent matching. Explicit negative examples (`NOT for...`) prevent the router from selecting this agent for unrelated requests.

---

## Correct Patterns

### Filesystem Verification Before Adding Entry

Always verify the component file exists before adding or updating a routing entry.

```bash
# Verify agent exists
ls agents/toolkit-governance-engineer.md
ls agents/toolkit-governance-engineer/

# Verify skill exists
ls skills/meta/routing-table-updater/SKILL.md

# Verify all pairs_with entries exist
for name in adr-consultation routing-table-updater docs-sync-checker; do
  ls agents/${name}.md 2>/dev/null || ls skills/${name}/SKILL.md 2>/dev/null || echo "MISSING: ${name}"
done
```

**Why**: Adding a routing entry for a nonexistent component creates a phantom route. The router selects it, the component lookup fails, and the request falls through to a generic handler — often silently.

---

### Trigger Phrase Specificity

```yaml
# Correct — specific phrases that uniquely identify this agent's domain
triggers:
  - edit skill
  - update routing tables
  - ADR status transition
  - frontmatter compliance audit

# Wrong — generic phrases that match too many agents
triggers:
  - update
  - fix
  - check
  - manage
```

**Why**: Generic triggers cause ambiguous routing — the router must break ties arbitrarily, often selecting the wrong agent. Triggers should be specific enough that they wouldn't match any other agent.

---

### Category Values and Routing Coverage

```yaml
# Valid categories used in the toolkit
category: meta          # toolkit-internal maintenance agents
category: engineering   # code generation and modification agents
category: review        # analysis and review agents
category: operations    # infrastructure, deployment, monitoring agents
category: content       # writing, documentation, content agents
```

**Why**: Category drives coverage grouping in `agents/INDEX.json`. Components with unknown categories appear in an "uncategorized" bucket and are harder to discover.

---

## Pattern Catalog
<!-- no-pair-required: section header with no content -->

### Verify Component Exists Before Adding Route

**Detection**:
```bash
# Check all pairs_with entries exist
python3 -c "
import yaml, glob, os
for f in glob.glob('agents/*.md'):
    txt = open(f).read()
    if '---' not in txt: continue
    try:
        fm = yaml.safe_load(txt.split('---')[1])
        pairs = fm.get('routing', {}).get('pairs_with', [])
        for p in pairs:
            if not os.path.exists(f'agents/{p}.md') and not os.path.exists(f'skills/{p}/SKILL.md'):
                print(f'PHANTOM: {f} -> pairs_with: {p}')
    except: pass
"

# Quick grep for a specific missing component
grep -rn "pairs_with" agents/*.md | grep "deleted-agent-name"
```

**Signal**:
```yaml
routing:
  pairs_with:
    - old-reviewer-agent    # renamed or deleted 3 months ago
    - legacy-skill-name     # skill was removed in a cleanup
```

**Why this matters**: The router follows `pairs_with` hints when orchestrating multi-agent workflows. A phantom entry either causes a lookup failure or triggers a fallback to a generic agent, breaking the intended workflow.

**Preferred action:**

Before committing a routing change, run `ls agents/{name}.md 2>/dev/null || ls skills/{name}/SKILL.md 2>/dev/null || echo "MISSING"` for every component in `pairs_with`. Update stale names to their current filenames, or remove entries for components that no longer exist.

**Preferred action**: Run the detection script above. For each phantom entry, either update to the current component name or remove the entry.

---

### Differentiate Trigger Phrases Across Agents

**Detection**:
```bash
# Find duplicate trigger phrases across all agents
python3 -c "
import yaml, glob
from collections import defaultdict
triggers = defaultdict(list)
for f in glob.glob('agents/*.md'):
    txt = open(f).read()
    if '---' not in txt: continue
    try:
        fm = yaml.safe_load(txt.split('---')[1])
        for t in fm.get('routing', {}).get('triggers', []):
            triggers[t.lower()].append(f)
    except: pass
for t, files in triggers.items():
    if len(files) > 1:
        print(f'CONFLICT: \"{t}\" claimed by: {files}')
"
```

**Signal**:
```
CONFLICT: "update routing" claimed by: agents/toolkit-governance-engineer.md, agents/routing-table-updater.md
```

**Why this matters**: The router cannot deterministically select between two agents claiming the same trigger. Resolution depends on ordering or scoring, which is non-obvious and changes silently when the index regenerates.

**Preferred action:**

Run the duplicate trigger detection script before adding any new trigger phrase. If a conflict is found, make one agent's trigger more specific (e.g., change `update routing` to `update routing tables for skill`) or consolidate the two agents into one umbrella component with a `references/` subdirectory.

**Preferred action**: Differentiate the triggers. One agent keeps the general phrase; the other uses a more specific variant. Or consolidate the two agents if their domains truly overlap.

---

### Regenerate INDEX.json After Component Changes

**Detection**:
```bash
# Count registered agents vs filesystem agents
registered=$(python3 -c "import json; d=json.load(open('agents/INDEX.json')); print(len(d.get('agents', {})))" 2>/dev/null)
on_disk=$(ls agents/*.md | grep -v README | wc -l)
echo "Registered: $registered, On disk: $on_disk"

# List agents on disk but not in index
python3 -c "
import json, glob, os
idx = json.load(open('agents/INDEX.json'))
registered = set(idx.get('agents', {}))  # 'agents' is a dict keyed by agent name
for f in glob.glob('agents/*.md'):
    name = os.path.basename(f).replace('.md','')
    if name not in registered and name != 'README':
        print(f'UNREGISTERED: {name}')
"
```

**Why this matters**: An unregistered component exists on disk but is invisible to the routing system. It can never be selected, even if its triggers perfectly match a user's intent.

**Preferred action:**

Regenerate `agents/INDEX.json` immediately after any agent add, rename, or delete. Run `python3 scripts/generate-agent-index.py` and verify the registered count matches the on-disk count using the detection commands above.

**Preferred action**: Regenerate `INDEX.json` after any agent/skill add, rename, or delete. The regeneration script rebuilds from filesystem state.

---

### Move All Four Registration Invariants Together

A PR that adds a skill plus a hook has to update four places at once. Each holds its own copy of facts the others also hold, and CI fails on whichever one lags.

**Detection**:
```bash
# Both skill-path maps carry their own copy of the mapping table
grep -c SKILL_MAPPING scripts/fix-skill-paths.py scripts/migrate-skills-to-folders.py

# Both routers carry their own semantic-guard table
grep -n "^SEMANTIC_GUARDS" scripts/pre-route.py scripts/index-router.py

# Counts claimed in prose vs counts on disk
python3 scripts/validate-doc-counts.py
```

**Signal**: CI fails on a doc-count claim; or the new skill force-routes from one router and falls through the other; or a path-fixing script rewrites every skill path except the new one.

| Invariant | Lives in | Fails as |
|-----------|----------|----------|
| Component counts | `README.md`, `docs/*.md` — checked by `scripts/validate-doc-counts.py` | CI count mismatch |
| `SKILL_MAPPING` | `scripts/fix-skill-paths.py` **and** `scripts/migrate-skills-to-folders.py` | Path rewrites skip the new skill |
| `SEMANTIC_GUARDS` | `scripts/pre-route.py` **and** `scripts/index-router.py` | Routing differs between the two routers |
| Trigger specificity | The new skill's `routing.triggers` | A single-word `force_route` trigger hijacks unrelated requests (see Trigger Phrase Specificity above) |

**Why this matters**: Each pair duplicates the same fact in two files. Updating one and not its twin produces a component that is half-registered — it routes in one code path and vanishes in the other, with no error anywhere.

**Preferred action**: Update all four before pushing, then run `validate-doc-counts.py` **after** merging main. Two branches that each add a component both bump the same README number from 78 to 79, and git reports a conflict where both sides read 79 while the true merged value is 80. Resolving that conflict by taking either side leaves the count wrong; recount from the filesystem instead.

---

### Remove Self-References from pairs_with

**Detection**:
```bash
# Find pairs_with that reference the agent itself
python3 -c "
import yaml, glob, os
for f in glob.glob('agents/*.md'):
    name = os.path.basename(f).replace('.md','')
    txt = open(f).read()
    if '---' not in txt: continue
    try:
        fm = yaml.safe_load(txt.split('---')[1])
        pairs = fm.get('routing', {}).get('pairs_with', [])
        if name in pairs:
            print(f'CIRCULAR: {name} pairs_with itself')
    except: pass
"
```

**Why this matters**: An agent that lists itself in `pairs_with` causes a routing loop when the orchestrator resolves co-dispatch recommendations.

**Preferred action:**

List only OTHER agents in `pairs_with` that are genuinely co-dispatched alongside this one. Run the circular reference detection script after editing any agent's frontmatter to catch self-references before committing.

**Preferred action**: Remove the self-reference from `pairs_with`.

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Router selects generic handler for specific request | Phantom route in `pairs_with` | Run phantom detection script; remove or update stale entries |
| Two agents both invoked for same trigger phrase | Duplicate triggers | Run conflict detection script; differentiate trigger phrases |
| Agent on disk but never routed | Not in INDEX.json | Regenerate INDEX.json from filesystem |
| `pairs_with` agent lookup fails at runtime | Component renamed or deleted | Glob for current name; update pairs_with or remove entry |
| INDEX.json count mismatch after cleanup | Stale entries after agent deletion | Regenerate INDEX.json; verify `registered == on_disk` |

---

## Detection Commands Reference

```bash
# Find phantom pairs_with references
python3 -c "
import yaml, glob, os
for f in glob.glob('agents/*.md'):
    txt = open(f).read()
    if '---' not in txt: continue
    try:
        fm = yaml.safe_load(txt.split('---')[1])
        for p in fm.get('routing', {}).get('pairs_with', []):
            if not os.path.exists(f'agents/{p}.md') and not os.path.exists(f'skills/{p}/SKILL.md'):
                print(f'PHANTOM: {f} -> {p}')
    except: pass
"

# Find duplicate trigger phrases
python3 -c "
import yaml, glob
from collections import defaultdict
triggers = defaultdict(list)
for f in glob.glob('agents/*.md'):
    txt = open(f).read()
    if '---' not in txt: continue
    try:
        fm = yaml.safe_load(txt.split('---')[1])
        for t in fm.get('routing', {}).get('triggers', []):
            triggers[t.lower()].append(f)
    except: pass
for t, files in triggers.items():
    if len(files) > 1: print(f'CONFLICT: \"{t}\" in {files}')
"

# Find unregistered agents
python3 -c "
import json, glob, os
idx = json.load(open('agents/INDEX.json'))
registered = set(idx.get('agents', {}))  # 'agents' is a dict keyed by agent name
for f in glob.glob('agents/*.md'):
    name = os.path.basename(f).replace('.md','')
    if name not in registered and name != 'README': print(f'UNREGISTERED: {name}')
"
```

---

## See Also

- `frontmatter-compliance.md` — required fields, tool restrictions, YAML parse error fixes
- `agents/INDEX.json` — coverage index; source of truth for registered components
- `docs/PHILOSOPHY.md` — specialist selection and deterministic execution principles
