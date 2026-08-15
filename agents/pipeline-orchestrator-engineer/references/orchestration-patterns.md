# Pipeline Orchestration — Fan-Out/Fan-In Patterns

> **Scope**: Dispatching parallel sub-agents, collecting outputs, enforcing phase gates. Orchestrator role only.

---

## Pattern Table

| Pattern | When | Avoid When |
|---------|------|------------|
| Fan-out by creator type | 3+ independent components | Single component |
| Context package pre-flight | Every sub-agent dispatch | Never skip |
| Hard gate before fan-in | Phase 3→4 transition | Never skip |
| ADR hash embed | Domain pipelines (full 7-phase) | Simple single-skill pipelines |
| Sequential within sub-agent | One component depends on another | Same-type components (parallel) |

---

## Fan-Out by Creator Type

Group components by creator, dispatch one sub-agent per type in parallel.

```
Orchestrator
  ├── skill-creator (all new agents + skills)    ← parallel
  ├── hook-development-engineer (all hooks)       ← parallel
  └── Direct (Python scripts)                     ← parallel

Gate: wait for ALL three before Phase 4 INTEGRATE
```

---

## Context Package Structure

Every sub-agent dispatch must include all four fields:

```python
Agent(
  description="Create {N} skills for {domain}",
  prompt=f"""
  ## Context Package

  ### Components to Create
  {component_list}

  ### Discovery Report
  {discovery_report}

  ### Inter-Component Relationships
  {relationships}

  ### Template Reference
  Follow skills/meta/skill-creator/references/agent-template.md for agents. Standard frontmatter + operator context for skills.

  ### Architecture Rules
  See skills/workflow/references/architecture-rules.md.
  Critical: Rule 12 (parallel research), Rule 18 (ADR hash), ADR-063 (tool restrictions).
  """
)
```

Sub-agents start with no shared context. Without discovery report → duplicates. Without relationships → orphaned files. Without template → non-compliant output.

---

## Phase Gate Enforcement

```bash
# Gate: Phase 3 → Phase 4
for component in "${expected_components[@]}"; do
  if [[ ! -f "$component" ]]; then
    echo "GATE FAIL: $component missing"
    exit 1
  fi
done

python3 scripts/validate-references.py --agent {name}

for hook in hooks/{pipeline-name}*.py; do
  python3 -c "import ast; ast.parse(open('$hook').read())" || echo "Syntax error: $hook"
done
```

---

## ADR Context Injection

```bash
adr_context=$(python3 ~/.claude/scripts/adr-query.py context \
  --adr adr/{pipeline-name}.md --role skill-creator)
```

Manual injection only needed when sub-agent needs full role-targeted ADR context beyond session-level auto-injection.

---

## Simple vs. Domain Pipeline Decision

```
Single skill/agent with one clear purpose?
  YES → Simple: Phase 0 → Phase 1 (legacy discover) → Phase 3 → Phase 4

  NO / broad domain →
    Domain: Full 7-phase flow with subdomain decomposition,
    validate-chain, ADR hash gate, test-runner, retro.
```

---

## Pattern Catalog

### Wait for All Sub-Agents Before Integration
**Signal**: Starting Phase 4 after only 2 of 3 sub-agents complete.
**Fix**: Hard gate — wait for ALL dispatched agents before any integration step. No acceptable partial state.

### Create ADR Before Starting Domain Pipelines
**Signal**: Starting Phase 1 without `adr/pipeline-{name}.md`.
**Fix**: Phase 0 is always first. Create ADR, register session: `python3 ~/.claude/scripts/adr-query.py register --adr adr/{pipeline-name}.md`

### Match Pipeline Complexity to Request Scope
**Signal**: Creating 4 sub-agents, a hook, and 3 scripts for a one-skill request.
**Fix**: Apply 80% rule — if existing agent covers 80%+, bind new skills to it.

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|------------|-----|
| `Agent tool: unknown subagent_type` | New agent not available until session restart | Restart Claude Code |
| Hook import fails | Syntax error or wrong path | `python3 -m py_compile hooks/X.py` |
| `routing-table-updater: no triggers` | Missing `routing.triggers` in frontmatter | Add triggers to frontmatter |
| Orphaned component | Wrong output path | Check actual vs expected path; rename |
| `validate-chain: unknown step type` | Step not in step-menu.md | `python3 scripts/artifact-utils.py list-steps` |

---

## Detection Commands

```bash
# Verify components created after Phase 3
for f in agents/{name}.md skills/{name}/SKILL.md hooks/{name}*.py; do
  [[ -f "$f" ]] && echo "OK: $f" || echo "MISSING: $f"
done

# Find unindexed agents
comm -23 \
  <(ls agents/*.md | xargs -I{} basename {} .md | sort) \
  <(python3 -c "import json; [print(a['name']) for a in json.load(open('agents/INDEX.json'))['agents']]" | sort)

# Check ADR session registered
ls -la .adr-session.json 2>/dev/null || echo "ADR session not registered"
```

---

## Phase 4 — Integration Verification Checklist

- All agents in `agents/INDEX.json`
- Routing entries match triggers in `skills/meta/do/SKILL.md` and `skills/meta/do/references/routing-tables.md`
- All hooks syntactically valid Python
- All skills follow frontmatter + operator context pattern
- No orphaned components

---

## Phase 3 — Creator Sub-Agent Table

| Creator | Components | Template |
|---------|-----------|----------|
| `skill-creator` | Agent manifests + skill SKILL.md + references | `skills/meta/skill-creator/references/agent-template.md` / standard skill format |
| `hook-development-engineer` | Python hooks | `hooks/lib/hook_utils.py` conventions |
| Direct (orchestrator) | Python scripts | `scripts/` conventions |

Each sub-agent receives: component list, Discovery Report/Pipeline Spec, bound skills/agents, architecture patterns, inter-component relationships.

---

## ADR Template (Phase 0)

```markdown
# ADR: Pipeline {Name}

## Status
PROPOSED | ACCEPTED | IMPLEMENTED | DEPRECATED

## Context
[Why needed, what triggered creation]

## Decision
[Pipeline design: components, flow, triggers]

## Component Manifest
[Agents, skills, hooks, scripts — updated during discovery]

## Constraints
[Architecture rules, reuse requirements, naming conventions]

## Consequences
[Routing changes, new triggers, affected pipelines]

## Test Plan
[Validation approach]
```

---

## Capabilities Summary

**CAN Do**: Orchestrate complete pipelines; plan component graphs; fan out to skill-creator and hook-development-engineer in parallel; detect/reuse existing components; integrate into /do routing; research domains for subdomains; compose valid chains; validate chain compatibility.

**CANNOT Do**: Write domain business logic; modify existing pipelines directly; create pipelines without routing integration; compose chains without validation; create monolithic single-skill for multi-subdomain domains.

---

## Output Format — Planning Schema

**Required Sections**: (1) Discovery Report, (2) Pipeline Spec (domain), (3) Execution Plan, (4) Integration Checklist, (5) Completion Report, (6) Session Restart Notice.

**Session Restart Notice (MANDATORY)** — last output after every pipeline creation:

```
SESSION RESTART REQUIRED
New agent '{agent-name}' was created and synced to ~/.claude/agents/.
Claude Code compiles available subagent types at session startup:
agents added during a session are NOT available as subagent_type
until the next session.

To use this pipeline:
  1. Restart Claude Code (Ctrl+C, then rerun `claude`)
  2. Then invoke: /do {trigger phrase}

The agent will be available immediately after restart.
```

---

## See Also

- `preferred-patterns.md` — pipeline creation mistakes
- `skills/workflow/references/step-menu.md` — valid steps and type signatures
- `skills/workflow/references/architecture-rules.md` — architecture rules
- `scripts/artifact-utils.py` — discovery, chain validation
