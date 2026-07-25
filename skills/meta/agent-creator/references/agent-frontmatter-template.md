# Agent Frontmatter Template

> **Scope**: Complete annotated YAML frontmatter template for vexjoy-agent operator `.md` files. Covers all required fields, valid values, complexity tier definitions, and INDEX.json registration.
> **Load when**: writing agent frontmatter, auditing field compliance, or diagnosing routing failures.

---

## Complete Annotated Template

```yaml
---
# Required: lowercase letters, numbers, hyphens only. Must match the directory
# name under agents/ if a references/ directory exists.
name: my-agent-name

# Required: quoted string. Answers: what does this agent do, when should it
# be selected, and what is it NOT for. Colons and commas require double quotes.
# Length: 60–120 chars. No "Use when:" or "Use for:" prefix.
description: "Domain-specific work: concrete capability A, capability B. Not for X or Y."

# Optional: color shown in routing UI. Standard values: blue, green, yellow,
# red, purple, orange. Omit if the agent has no visual grouping.
color: blue

# Optional: model override. Omit to use the session default.
# Values: sonnet (implementation/lighter work), opus (reviews/analysis/deep work).
# Model-selection policy: /do SKILL.md, Model Selection. Haiku is retired.
model: sonnet

routing:
  # Required: list of 3–6 intent phrases matching natural speech.
  # Each phrase should uniquely identify this agent's domain.
  triggers:
    - specific phrase users would say
    - another natural phrase
    - domain-specific action phrase

  # Optional: 2–4 agents commonly co-dispatched with this one.
  # Each entry must exist on disk before committing (verify with ls).
  pairs_with:
    - other-agent-name
    - another-agent-name

  # Required. Case-sensitive. Exactly one of: Low, Medium, High.
  # Low: single-file edits, read-only audits, fast lookups
  # Medium: multi-file edits, routing table updates, moderate orchestration
  # High: full compliance sweeps, ADR consultations, heavy orchestration
  complexity: Medium

  # Required. String. Use these standard values:
  # meta, engineering, review, operations, content
  category: meta

# Required for agents. List must match the agent's actual role (ADR-063).
# Reviewers: [Read, Glob, Grep]
# Engineers: [Read, Edit, Write, Bash, Glob, Grep]
# Orchestrators: [Read, Agent, Bash]
# Skill-invokers: [Read, Bash, Glob, Grep]
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash
  - Glob
  - Grep

# Required for skills, optional for agents. Default: false.
# false = router-dispatched (user never types the name)
# true = user types it directly as a slash-command entry point
user_invocable: false
---
```

---

## Field Reference Table

| Field | Required | Type | Valid values |
|-------|----------|------|-------------|
| `name` | yes | string | lowercase, hyphens, numbers |
| `description` | yes | quoted string | 60–120 chars; no "Use when:" prefix |
| `color` | no | string | blue, green, yellow, red, purple, orange |
| `model` | no | string | sonnet, opus |
| `routing.triggers` | yes | list | 3–6 natural-speech phrases |
| `routing.pairs_with` | no | list | agent names that exist on disk |
| `routing.complexity` | yes | enum | Low, Medium, High (case-sensitive) |
| `routing.category` | yes | string | meta, engineering, review, operations, content |
| `allowed-tools` | yes (agents) | list | tool names from the ADR-063 role table |
| `user_invocable` | no | boolean | true, false (default: false) |

---

## Complexity Tier Definitions

| Tier | Load strategy | Example agents |
|------|---------------|----------------|
| `Low` | Single dispatch, minimal context | Reviewer reading one file, simple lookup |
| `Medium` | Multi-step dispatch, moderate context loading | Routing table update, 2–3 file edits |
| `High` | Full orchestration, large reference sets | Compliance sweep, ADR consultation, cross-repo analysis |

---

## Description Craft

The router sees `name` and `description` first — often the only fields it consults before short-listing. A weak description fails to route reliably even when the body is correct.

A strong description does three jobs in 60–120 characters:

| Job | What to include | Example |
|-----|-----------------|---------|
| State the **intent** | The user goal, not internals | "Diagnose canary deployment health" |
| Name **adjacent terms** | 2–3 phrases the user might actually say | "canary, rollout, traffic split" |
| Mark a **false-positive boundary** | One thing this agent is NOT for, with a redirect | "Not for: editing manifests — see kubernetes-helm-engineer" |

### Pattern

```yaml
description: "<intent verb + domain object>: <2–3 adjacent terms>. Not for <off-domain task> — see <other-agent>."
```

### Examples

| Bad | Why it fails | Better |
|-----|--------------|--------|
| `"Helps with Kubernetes"` | No intent, no adjacent terms, no boundary | `"Diagnose canary rollouts: traffic-split health, baseline comparison, rollback signals. Not for manifest edits — see kubernetes-helm-engineer."` |
| `"Use this skill when you need to write Go code"` | Banned "Use this skill when" prefix; no adjacent terms | `"Go feature work: idiomatic patterns, table-driven tests, error wrapping, race-free concurrency."` |
| `"Reviews stuff"` | No domain, no intent, no adjacent terms | `"Code review: convention checks, dead-code detection, performance regressions. Not for security audits — see reviewer-system."` |

### Test the description against routing

After writing, run a mental should-trigger / should-not-trigger pass:

| Phrase | Should this agent route? | Does the description signal that? |
|--------|--------------------------|------------------------------------|
| 3 phrases a user would naturally say | Yes | Adjacent terms cover at least 2 of the 3 |
| 2 near-misses (similar wording, off-domain) | No | Boundary clause excludes them |

Record these phrases in the SCAFFOLD phase notes — they become the activation-eval cases. See `references/agent-eval-design.md` for the full activation-vs-output-eval pattern.

---

## Validation Commands

```bash
# YAML parse — pinpoints broken field
python3 -c "import yaml; yaml.safe_load(open('agents/{name}.md').read().split('---')[1]); print('OK')"

# Find agents missing allowed-tools
grep -rL "allowed-tools" agents/*.md

# Find descriptions with unquoted colons
grep -n "^description: [^\"'].*:" agents/*.md

# Find wrong complexity casing
grep -rn "complexity:" agents/*.md | grep -vE "complexity: (Low|Medium|High)"

# Find phantom pairs_with entries
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
```

---

## INDEX.json Registration

After writing the agent file, register it in the routing index. The router cannot discover unregistered agents.

```bash
# Regenerate agents index
python3 scripts/generate-agent-index.py

# Verify the new agent appears
python3 -c "
import json
d = json.load(open('agents/INDEX.json'))
agents = d.get('agents', [])
print(f'Registered: {len(agents)}')
names = [a.get('name') for a in agents] if isinstance(agents, list) else list(agents.keys())
print('my-agent-name' in names and 'FOUND' or 'MISSING')
"
```

Skills also need registration in `skills/INDEX.json`:

```bash
python3 scripts/generate-skill-index.py
```

---

## Post-Write Checklist

After writing an agent `.md` file, run these in order:

1. YAML parse: `python3 -c "import yaml; yaml.safe_load(open('agents/{name}.md').read().split('---')[1])"`
2. Positive framing: `python3 scripts/validate_positive_instruction_docs.py` (scans all tracked .md files)
3. Reference structure: `python3 scripts/validate-references.py --agent {name}` (if references/ exists)
4. pairs_with existence: verify each listed agent/skill exists on disk
5. INDEX registration: `python3 scripts/generate-agent-index.py`
6. Trigger conflicts: run duplicate trigger detection from `agents/toolkit-governance-engineer/references/routing-table-patterns.md`
7. Description triggers on adjacent terms: confirm 3 should-trigger phrases route to this agent and 2 near-miss phrases route elsewhere (mental pass at minimum; record both lists in the SCAFFOLD notes)
8. Activation + output eval cases recorded: the should-trigger / should-not-trigger / near-miss phrases from step 7 are saved as eval seeds per `references/agent-eval-design.md`

All eight steps must pass before the agent is committed.
