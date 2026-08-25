# Pipeline Orchestration — Preferred Patterns

> **Scope**: Correct patterns for creating, scaffolding, and routing toolkit pipelines.

---

## Pattern Catalog

### Include Full Context Package in Every Sub-Agent Dispatch

Pass to every sub-agent: (1) full component list, (2) Discovery Report or Pipeline Spec, (3) inter-component relationships. Missing any one produces orphaned output. A/B test: agents without Discovery Report produced orphaned components in 40% of runs.

**Detection**:
```bash
grep -rn 'subagent_type' agents/ --include="*.md" | grep -v "spec\|manifest\|discovery"
```

---

### Run codebase-overview Before Scaffolding

Always Phase 1 before Phase 3. If existing agent covers 80%+, bind new skills instead of duplicating. Two agents with overlapping triggers produce non-deterministic routing.

**Detection**:
```bash
grep -rn 'codebase-overview' adr/ --include="*.md" | wc -l
```

---

### One Skill Per Subdomain

Decompose multi-subdomain domains into N skills, one per subdomain, same agent. Enables independent routing, context loading, and evaluation. A/B test: sequential single-skill lost 1.40 points vs parallel N-skill.

**Detection**:
```bash
grep -rn 'description:' skills/*/SKILL.md | grep ' and \| & ' | grep -v "test\|spec"
```

---

### Validate Chain Before Scaffolding

`validate-chain` on every chain before scaffolding. Catches type incompatibilities at design time.

```bash
python3 scripts/artifact-utils.py validate-chain --chain "research,draft,review,publish" --domain prometheus
```

**Detection**:
```bash
grep -rn 'validate-chain' adr/ --include="*.md"
```

---

### Integrate Routing in Same Session

Phase 4 is not optional. Call the Skill tool with `routing-table-updater`. Do this in the same session as Phase 3. Unrouted pipeline = invisible dead code.

**Detection**:
```bash
comm -23 \
  <(ls agents/*.md | xargs -I{} basename {} .md | sort) \
  <(grep -o '`[a-z-]*-engineer\|[a-z-]*-agent`' skills/meta/do/references/routing-tables.md | tr -d '`' | sort)
```

---

### Set allowed-tools in Every Agent Frontmatter

Match tools to role per ADR-063. Reviewers/research: read-only. Code modifiers: full access.

```yaml
# Reviewers/research — read-only
allowed-tools: [Read, Glob, Grep, WebSearch]

# Code-modifying — full access
allowed-tools: [Read, Glob, Grep, Edit, Write, Bash, Agent]
```

**Detection**:
```bash
grep -rL 'allowed-tools' agents/*.md
```

---

### Fan Out Independent Components in Parallel

Agent, skill, and hook files have no data dependencies during creation. Sequential dispatch wastes time.

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|------------|-----|
| `validate-chain: type mismatch at step N` | Output/input type incompatibility | Choose compatible step or add adapter |
| `routing-table-updater: trigger conflict` | Overlaps existing force-route | More specific triggers; preserve force-routes |
| `audit-tool-restrictions: missing allowed-tools` | No `allowed-tools` in frontmatter | Add role-appropriate list per ADR-063 |
| `adr-enforcement: hash mismatch` | Spec hash doesn't match ADR | Recompute: `adr-query.py hash --adr {path}` |
| `skill-creator: template section missing` | Missing frontmatter/operator context | Re-run with explicit template reference |
| Duplicate Component | Existing agent/skill covers purpose | Bind existing instead of creating new |
| Chain Validation Failure | Type incompatibilities | Re-invoke workflow (composition) with error |
| Domain Research Insufficient | < 2 subdomains | Fall back to single-pipeline mode |

---

## Detection Commands

```bash
# Sub-agents missing context package
grep -rn 'subagent_type' agents/ --include="*.md" | grep -v "spec\|manifest\|discovery"

# Missing tool restrictions (ADR-063)
grep -rL 'allowed-tools' agents/*.md

# Unregistered agents in routing
comm -23 \
  <(ls agents/*.md | xargs -I{} basename {} .md | sort) \
  <(grep -oP '[a-z-]+-engineer|[a-z-]+-agent' skills/meta/do/references/routing-tables.md | sort -u)

# Multi-subdomain skills (should be split)
grep -rn 'description:' skills/*/SKILL.md | grep ' and \| & '

# Missing chain validation in ADRs
grep -rn 'validate-chain' adr/ --include="*.md"
```

---

## See Also

- `orchestration-patterns.md` — fan-out/fan-in patterns and gate idioms
- `skills/workflow/references/step-menu.md` — valid steps and type signatures
- `scripts/artifact-utils.py` — chain validation and discovery
