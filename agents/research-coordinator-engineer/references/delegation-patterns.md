# Delegation Patterns Reference

> **Scope**: Subagent instruction templates and parallel execution for research-coordinator-engineer.
> **Version range**: Claude Code SDK (Task tool / Agent tool)
> **Generated**: 2026-04-13

---

## Pattern Table

| Pattern | Use When | Subagent Count | Instruction Length |
|---------|----------|---------------|-------------------|
| Standard parallel dispatch | 3+ independent streams | 3 | 100-200 words each |
| Deep-dive single stream | Narrow topic needing depth | 1–2 | 200-300 words |
| Broad coverage dispatch | Comparison or enumeration | 1 per item, max 7 | 80-150 words each |
| Fallback sequential | Dependencies between streams | 1 at a time | Full detail |

---

## Correct Patterns

### Standard Parallel Dispatch (3 Concurrent)

Deploy all independent subagents in a single message. Sequential dispatch wastes N x latency instead of 1 x latency.

```python
# Deploy all 3 in one message
Task(subject="Research GPU availability 2025-2030",
    content="""Focus on GPU/TPU availability from major cloud providers.
    Include chip production forecasts from TSMC, Samsung, Intel.
    SCOPE: Only compute chips. NOT general semiconductor market.
    DELIVERABLE: 350-500 word summary with 3+ statistics.
    SOURCES: Cloud provider reports, semiconductor analysts (2024-2025).""")

Task(subject="Research energy requirements for AI data centers",
    content="""Power consumption per GPU cluster, grid capacity constraints,
    cooling technology advances.
    SCOPE: Energy for AI compute only. NOT general data center trends.
    DELIVERABLE: 350-500 word summary with 3+ statistics.
    SOURCES: IEA reports, data center operators, academic papers (2024-2025).""")

Task(subject="Research regulatory environment for AI infrastructure",
    content="""Permitting timelines, environmental review, export controls.
    SCOPE: Regulations affecting infrastructure build. NOT AI product regulation.
    DELIVERABLE: 350-500 word summary with specific jurisdictions/timelines.
    SOURCES: Federal Register, EU legislation, news coverage (2024-2025).""")
```

---

### Instruction Required Components

Every instruction needs all five:

```markdown
[1] SCOPE: What is IN scope (one specific sentence)
[2] OUT-OF-SCOPE: What to ignore (prevents scope creep)
[3] REQUIRED DATA POINTS: Concrete data to seek (not just narrative)
[4] DELIVERABLE FORMAT: Word count + format + quality bar
[5] SOURCE GUIDANCE: Where to look + source tier preference
```

---

### Adaptive Instruction After Initial Findings

When Wave 1 reveals gaps, Wave 2 instructions address them explicitly:

```markdown
Research AI data center energy with focus on ACTUAL METERED DATA:
- Find published case studies with metered power figures
- Gap from Wave 1: found projections but no verified metered data
DELIVERABLE: List of 5+ specific measured data points with source and date.
```

---

## Pattern Catalog

### Define Explicit Scope Boundaries

**Detection**:
```bash
grep -rL "OUT OF SCOPE\|Not in scope\|Exclude" research/*/instructions/ 2>/dev/null
```

**Signal**: `"Research AI trends in 2025."` — No scope = no boundary = subagent covers everything tangentially related.

**Preferred action**: "Research AI model training compute trends for frontier models (GPT-4 class+) in 2024-2025. Focus: training run sizes in FLOP, hardware configs, cost estimates. NOT inference, edge AI, or models below 10B params. DELIVERABLE: 300-400 words with 2+ training run statistics."

---

### Dispatch Independent Streams in Parallel

**Detection**:
```bash
grep -i "wait for\|after.*completes\|once.*done" research/*/plan.md
```

Three independent topics sequentially = 3x latency for no reason. Move all Task calls into one message.

---

### Specify Deliverable Format

**Detection**:
```bash
grep -rL "word\|paragraph\|bullet\|table" research/*/instructions/ 2>/dev/null
```

"Provide your findings" accepts any output, makes synthesis unpredictable.

**Preferred action**: "DELIVERABLE: 300-500 word summary with: (1) current status, (2) key restrictions, (3) timeline outlook."

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Overlapping subagent content | No scope differentiation | Add OUT-OF-SCOPE to every instruction |
| 100 words vs 1000 words | No word count spec | Add word count range |
| Subagent drifts | Scope lacks boundaries | Add clear out-of-scope statement |
| Synthesis slow | Incompatible output formats | Standardize deliverable format |
| Wave 2 duplicates Wave 1 | No Bayesian update | Reference Wave 1 gaps in Wave 2 |
| >20 subagents | Over-scoped query | Merge topics or reduce scope |

---

## Subagent Count Decision Tree

```
Simple (single data point) → 1 subagent
Medium (3-5 streams) → 3 concurrent
Complex (6-10 streams) → 5-7 concurrent, group by theme
Very complex (>10) → STOP: restructure. Hard limit: 20.
```

---

## Detection Commands Reference

```bash
grep -rL "OUT OF SCOPE\|Not in scope" research/*/instructions/ 2>/dev/null
find research/ -name "*.md" -path "*/instructions/*" -exec \
  awk 'NF{w+=NF} END{if(w<50)print FILENAME": "w" words"}' {} \; 2>/dev/null
grep -in "wait for\|step [0-9]\+: deploy" research/*/plan.md 2>/dev/null
```

---

## See Also

- `query-classification.md` — Determines subagent count and style
- `error-catalog.md` — Common delegation failures
