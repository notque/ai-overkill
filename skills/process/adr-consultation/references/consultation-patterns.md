# ADR Consultation — Core Patterns

> **Scope**: Correct patterns for multi-agent consultation orchestration: dispatch, synthesis, verdict
> aggregation, and concern classification. Does NOT cover ADR authoring or architecture review criteria.
> **Version range**: Standard mode (3 agents), Complex mode (5 agents)
> **Generated**: 2026-04-15

---

## Overview

ADR consultation dispatches multiple reviewers in parallel and synthesizes their independent
verdicts into a single PROCEED or BLOCKED gate. The most common failure modes are: dispatching
agents sequentially (negates parallelism), synthesizing from return context instead of disk files
(makes consultation non-reproducible), and rationalizing blocking concerns away (defeats the
gate's purpose).

---

## Pattern Table

| Pattern | Mode | Use When | Avoid When |
|---------|------|----------|------------|
| Parallel 3-agent dispatch | Standard | All ADRs — default | Never skip; use Complex if needed |
| Parallel 5-agent dispatch | Complex | New subsystem, major API change | Routine config/refactor decisions |
| File-based synthesis | All | Synthesizing verdicts | Context-only (non-reproducible) |
| Hard block on severity:blocking | All | Any blocking concern found | Never — it is not advisory |

---

## Correct Patterns

### Single-Message Parallel Dispatch

Dispatch all agents in ONE response message. Sequential dispatch triples wall-clock time
with no cross-perspective benefit.

```markdown
<!-- Correct: single message, three Task calls -->
Task 1: reviewer-perspectives (contrarian) → writes adr/{name}/reviewer-perspectives-contrarian.md
Task 2: reviewer-perspectives (user-advocate) → writes adr/{name}/reviewer-perspectives-user-advocate.md
Task 3: reviewer-perspectives (meta-process) → writes adr/{name}/reviewer-perspectives-meta-process.md
```

**Why**: Agents assess independently. Sequential dispatch introduces timing artifacts where
earlier agents' results could leak into later agents' context, undermining independence.

---

### File-Based Synthesis

Read agent responses from disk, not from Task return context.

```bash
# Correct: read from files after all agents complete
cat adr/{name}/reviewer-perspectives-contrarian.md
cat adr/{name}/reviewer-perspectives-user-advocate.md
cat adr/{name}/reviewer-perspectives-meta-process.md
```

**Why**: Task return context is ephemeral. Files persist across sessions. Synthesis from
context cannot be re-read or audited by future sessions — it vanishes when the context window
is cleared. File-based synthesis is reproducible and auditable.

---

### Concern Severity Classification

Classify every concern into exactly one of three severities:

| Severity | Meaning | Effect on verdict |
|----------|---------|-------------------|
| `blocking` | Must resolve before implementation | BLOCKED verdict — hard gate |
| `important` | Should address; non-blocking | PROCEED with caveats |
| `minor` | Nice-to-have improvement | PROCEED; note for implementer |

```markdown
<!-- concerns.md entry format -->
## Concern N: [Title]
- **Raised by**: [agent name and lens]
- **Severity**: blocking | important | minor
- **Description**: [specific risk or problem]
- **Resolution**: UNRESOLVED
```

---

### Verdict Aggregation

Aggregate agent verdicts using the most conservative rule. NEEDS_CHANGES is not a soft PROCEED.

```
All 3 PROCEED              → PROCEED with confidence
2 PROCEED + 1 NEEDS_CHANGES → Address changes, then PROCEED
Any BLOCK                  → BLOCKED — resolve before any implementation
Mixed NEEDS_CHANGES        → Address concerns before proceeding
```

**Why**: Treating NEEDS_CHANGES as PROCEED silently discards real concerns. Each NEEDS_CHANGES
from an agent means that agent identified something that must change. Multiple NEEDS_CHANGES
from different agents on different dimensions means the decision needs more work.

---

### Orchestrator-Level Concern Detection

After reading all three agent files, identify cross-cutting concerns that individual agents
missed because they assessed separately.

```bash
# Check for cross-cutting patterns after reading all three files:
# 1. Do two agents raise the same concern with different names?
# 2. Does agent A's "acceptable tradeoff" create agent B's "blocking concern"?
# 3. Are there emergent coupling issues visible only when combining all perspectives?
```

Document orchestrator-level concerns in `concerns.md` under a separate section:

```markdown
## Orchestrator Concern N: [Cross-Cutting Issue]
- **Raised by**: synthesis orchestrator (cross-cutting)
- **Severity**: [determined by impact, not by which agent raised it]
```

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| `ls adr/{name}/ → No such file` | Consultation directory not created before dispatch | Run `mkdir -p adr/{name}` before dispatching agents |
| Agent file missing after dispatch | Agent timed out or failed to write | Re-run failed agent individually; check for path typos in prompt |
| `cat .adr-session.json → No such file` | No active ADR session; user invoked without specifying ADR | Run `ls adr/*.md` and ask user to specify which ADR |
| Synthesis shows PROCEED but concerns.md has `blocking` | Rationalization failure mode | Override to BLOCKED; address concern in ADR; re-run |
| Two agents raised identical concern under different names | Cross-cutting concern missed by individual agents | Consolidate in concerns.md as orchestrator-level; elevate severity |

---

## Detection Commands Reference

```bash
# Verify consultation directory exists before dispatch
ls adr/{name}/ 2>/dev/null || echo "MISSING — run mkdir -p adr/{name}"

# Count written agent files (standard: expect 3)
ls adr/{name}/reviewer-perspectives-*.md 2>/dev/null | wc -l

# Check for blocking concerns in concerns.md
grep -c "Severity.*blocking" adr/{name}/concerns.md 2>/dev/null

# Check for prior consultation results
ls -lt adr/{name}/ 2>/dev/null | head -10

# Verify synthesis and concerns files exist
ls adr/{name}/synthesis.md adr/{name}/concerns.md 2>/dev/null
```

---

## Phase 3 Artifact Templates

### concerns.md template

```markdown
# Concerns: {adr-name}

## Concern 1: [Title]
- **Raised by**: reviewer-perspectives (contrarian) | reviewer-perspectives (user-advocate) | reviewer-perspectives (meta-process)
- **Severity**: blocking | important | minor
- **Description**: [What's wrong or at risk]
- **Resolution**: UNRESOLVED

Resolution states (update as concerns are addressed):
- UNRESOLVED — not yet addressed
- RESOLVED: {description} — addressed in implementation
- ACCEPTED: {description} — accepted as a known limitation
- DEFERRED: {description} — will address in future work

## Concern 2: [Title]
...
```

### synthesis.md template

```markdown
# Consultation Synthesis: {adr-name}

## ADR Path
adr/{adr-name}.md

## ADR Hash
sha256:{digest}

## Verdict: [PROCEED | BLOCKED]

## Agent Verdicts
| Agent | Verdict |
|-------|---------|
| reviewer-perspectives (contrarian) | [verdict] |
| reviewer-perspectives (user-advocate) | [verdict] |
| reviewer-perspectives (meta-process) | [verdict] |

## Areas of Agreement
[Where all agents agree — positive or negative.]

## Areas of Disagreement
[Where agents see the same aspect differently.]

## Blocking Concerns
[Concerns with severity: blocking. These MUST be resolved before implementation.]

## Important Concerns
[Concerns with severity: important. Should be addressed; non-blocking.]

## Minor Concerns
[Concerns with severity: minor. Nice-to-have improvements.]

## Synthesis Rationale
[Why the overall verdict is PROCEED or BLOCKED, given the above.]
```

---

## Phase 4 Verdict Display

### BLOCKED verdict

```
═══════════════════════════════════════════════════════════════
 ADR CONSULTATION: BLOCKED
═══════════════════════════════════════════════════════════════

 ADR: {adr-name}
 Consultation: adr/{adr-name}/

 BLOCKING CONCERNS — do not proceed to implementation:

 1. [{raised by}] {concern title}
    {description}

 2. [{raised by}] {concern title}
    {description}

 Next Steps:
   - Address each blocking concern in the ADR
   - Re-run /adr-consultation to verify concerns are resolved
   - Do NOT dispatch feature-lifecycle implement phase until PROCEED verdict
═══════════════════════════════════════════════════════════════
```

### PROCEED verdict

```
═══════════════════════════════════════════════════════════════
 ADR CONSULTATION: PROCEED
═══════════════════════════════════════════════════════════════

 ADR: {adr-name}
 Consultation: adr/{adr-name}/

 Verdict: PROCEED — no blocking concerns found.

 Agent Verdicts:
   - reviewer-perspectives (contrarian):    [verdict]
   - reviewer-perspectives (user-advocate): [verdict]
   - reviewer-perspectives (meta-process):  [verdict]

 Important Concerns (non-blocking):
   [{raised by}] {concern title} — {brief description}

 Consultation artifacts:
   - adr/{adr-name}/reviewer-perspectives-contrarian.md
   - adr/{adr-name}/reviewer-perspectives-user-advocate.md
   - adr/{adr-name}/reviewer-perspectives-meta-process.md
   - adr/{adr-name}/synthesis.md
   - adr/{adr-name}/concerns.md
═══════════════════════════════════════════════════════════════
```

---

## See Also

- `consultation-preferred-patterns.md` — ADR quality failure modes that reviewers should catch
- `skills/review/parallel-code-review/SKILL.md` — Fan-out/fan-in pattern this skill adapts
- `agents/reviewer-perspectives.md` — Perspectives agent (contrarian, user-advocate, meta-process lenses)
