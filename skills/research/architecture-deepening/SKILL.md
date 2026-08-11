---
name: architecture-deepening
version: "1.2.0"
description: "Improve architecture across modules by deepening interfaces."
user-invocable: true
command: architecture-deepening
context: fork
allowed-tools:
  - Agent
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
routing:
  triggers:
    - improve architecture
    - improve codebase architecture
    - improve the codebase architecture
    - find architecture improvements
    - deepen architecture
    - find shallow modules
    - architecture improvement
    - module depth analysis
    - deepening opportunities
    - improve module interfaces
    - architecture deepening
  not_for: "local cleanup/refactoring (workflow or planning), feature design (feature-lifecycle), architecture overview/explanation (codebase-overview), or vague complexity reduction; requires cross-module interface or caller-burden evidence"
  pairs_with:
    - full-repo-review
    - adr-consultation
    - codebase-overview
  complexity: Medium
  category: analysis
---

# Architecture Deepening

Find shallow modules and propose deepening opportunities. Not a code review -- does not find bugs or style violations. Finds modules where the interface is too close to the implementation, where users must understand internals to use the API, and where small interface changes would absorb disproportionate complexity.

**When to use**: After codebase onboarding or review when improvement was requested, before a cross-module feature, after a fix exposes a missing test seam, or when callers repeatedly need source knowledge or multi-module coordination.

**Differs from full-repo-review**: Full-repo-review finds defects. This skill finds structural improvement opportunities. Pair well: run full-repo-review first to fix defects, then architecture-deepening to raise the bar.

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| Phase 1 scope/ranking, prior decisions, no-findings result; Phase 3 handoff | `maintenance-lifecycle.md` | Evidence-fed entry rules, recent-change scope, decision memory, candidate schema, typed delivery handoff |
| Phase 1, module analysis, vocabulary terms | `vocabulary.md` | Shared architecture vocabulary: module, depth, seam, leverage, locality, deletion test |
| Phase 2, interface alternatives, parallel exploration | `interface-design.md` | Parallel sub-agent pattern for exploring alternative interfaces |
| Phase 2-3, dependency analysis, testing strategy | `deepening-strategies.md` | Dependency categorization, safe deepening patterns, testing strategies |

## Instructions

Run phases in order until a terminal gate. Survey and design keep source code read-only; Write/Edit apply only to user-approved decision records after selection. Existing delivery workflows own code changes. The user selects candidates and decides whether a handoff proceeds.

Language-agnostic. Vocabulary and strategies apply to Go, Python, TypeScript, or any codebase with module boundaries.

### Phase 1: EXPLORE

**Goal**: Identify shallow modules -- where the interface exposes too much implementation detail.

**Step 1: Choose an evidence-fed scope**

Read `references/maintenance-lifecycle.md`. Use the user's named directory/package first. Otherwise start from the review, overview, feature, or fixed-bug evidence that triggered the run. With no such artifact, rank module paths changed in the last 50 commits and inspect the top bounded set. Recent change raises priority; it is not proof of shallowness. Widen once only when the initial scope has no usable evidence and the request is repository-wide.

Read prior architecture decisions before producing candidates. Suppress a matching stable rejection unless its recorded assumptions changed.

Then scan the chosen scope for module boundaries.

```bash
find . -name "go.mod" -o -name "package.json" -o -name "pyproject.toml" -o -name "__init__.py" -o -name "index.ts" -o -name "mod.rs" 2>/dev/null | head -50

# Exported symbols per package (Go)
grep -rn "^func [A-Z]" --include="*.go" | cut -d: -f1 | sort | uniq -c | sort -rn | head -20

# Public exports (TypeScript)
grep -rn "^export " --include="*.ts" --include="*.tsx" | cut -d: -f1 | sort | uniq -c | sort -rn | head -20
```

**Step 2: Apply shallowness signals**

Read `references/vocabulary.md` for full vocabulary. A module is shallow when:
- Interface nearly as complex as implementation (high surface-area-to-depth ratio)
- Users must read source to understand how to call it
- Setup requires knowledge of internal state
- Error messages expose implementation details
- Multiple modules must coordinate for a single logical operation

For each candidate, cite the interface, caller burden, affected callers, change evidence, and prior-decision match. Score each: **HIGH** (clear shallowness, high-leverage fix), **MEDIUM** (some shallowness, moderate leverage), **LOW** (minor, low impact). Rank only candidates that meet the evidence floor in `maintenance-lifecycle.md`.

**Step 3: Identify seams**

For HIGH-scored modules, identify seams -- natural boundaries where the module could absorb more responsibility. See `references/vocabulary.md` for seam types (data, protocol, temporal).

**Gate**: Emit either (a) ranked, evidence-backed candidates with seam analysis or (b) the no-findings record plus its terminal typed handoff from `maintenance-lifecycle.md`. Validate no-findings inline through `scripts/handoff.py validate --stdin`; it creates no file. Both pass. No-findings closes the run; candidate count is never padded.

---

### Phase 2: PRESENT CANDIDATES

**Goal**: Show findings, let the user choose, then explore alternatives for selected candidates.

**Step 1: Present findings table**

```markdown
| Rank | Module | Depth Score | Evidence | Seam | Leverage | Prior Decision |
|------|--------|-------------|----------|------|----------|----------------|
| 1 | pkg/config | HIGH | 12 callers construct the same internal shape | Data seam | High | none |
| 2 | internal/auth | MEDIUM | 4 callers coordinate refresh state | Protocol seam | Medium | assumptions changed |
```

For each: what it does today, why it is shallow, the exact interface and caller evidence, where the seam is, leverage, change likelihood, and any prior decision.

**Step 2: Get user input**

Ask which candidate to explore, reject, or defer. Stop before interface design until the user chooses. Rejection and deferral may close immediately with a terminal handoff. Persist them only when the durability test passes and the user approves the write.

**Step 3: Explore interface alternatives**

Read `references/interface-design.md` and `references/deepening-strategies.md`. Design 2-3 alternative interfaces per candidate:
- New interface signature (function names, parameters, return types)
- What moves behind the interface (what callers no longer need to know)
- Deletion test result: what caller code can be deleted
- Trade-offs: flexibility lost, edge cases needing escape hatches

**Gate**: A selected candidate has at least 2 alternatives with deletion-test results. Rejection or deferral is a valid terminal result after its close handoff; durable state is optional and consent-gated.

---

### Phase 3: DESIGN CONVERSATION

**Goal**: Grill the chosen approach until the best deepening emerges. Collaborative design, not presentation.

**Step 1: Challenge each alternative**

- **Locality**: Does this keep related things together or scatter responsibility?
- **Escape hatches**: What happens when a caller needs old flexibility? Clean override path or workarounds?
- **Migration**: Incremental adoption or all-or-nothing?
- **Testing**: How to test the deepened module? See `references/deepening-strategies.md`.
- **Second-order effects**: Does deepening here create new shallowness elsewhere?

**Step 2: Iterate until convergence**

Use at most 3 design rounds. Continue until:
- Agreement on a specific approach, OR
- User decides current structure is acceptable after examining alternatives

Each round narrows the design space. If round 3 does not converge, stop and ask whether to select, defer, or close as no-change. This lifecycle has no prototype state; a requested prototype starts a separately approved workflow after deferral.

**Step 3: Document the decision**

```markdown
## Deepening Decision: {module name}

**Current interface**: {what callers see today}
**Proposed interface**: {what callers would see after}
**What moves behind the interface**: {details callers no longer manage}
**Deletion test**: {what caller code can be removed}
**Migration path**: {incremental adoption plan}
**Trade-offs accepted**: {flexibility traded for simplicity}
**Next skill**: {workflow | feature-lifecycle | null}
**Next pipeline**: {systematic-refactoring | null}
```

Read `references/maintenance-lifecycle.md` and emit its typed `Architecture Change Handoff`. Emission means returning the complete JSON contract even when execution is read-only; persistence is a separate authorized action. Include `"origin": "architecture-deepening"`. A rejected input is not a terminal architecture result: emit no handoff, authorize no path, and dispatch no successor when fingerprint, containment, symlink, or provenance validation fails. For action-bearing results when writes are authorized, pipe that same JSON to `scripts/handoff.py write --stdin`; this neutral boundary validates the schema, decoded candidate module, paths, successor, and ADR provenance before its repository-anchored atomic writer makes the first write under `adr/handoffs/`. Validate no-findings with `scripts/handoff.py validate --stdin` and keep it inline. Classify bounded behavior-preserving work with `next_skill: workflow` and `next_pipeline: systematic-refactoring`; classify public or cross-module interface migration and new behavior with `next_skill: feature-lifecycle` and a null pipeline; close no-change results with both fields null. Every selected handoff contains non-empty repository-relative module and caller paths, current/proposed interface, migration, and measurable criteria for `verification-before-completion`.

For a MEDIUM/HIGH behavior-preserving refactor or HIGH-risk no-change result, create one canonical ADR through `scripts/repository_artifact.py write`, register it, capture its hash, run `adr-query.py validate-registration`, and consult it before terminal dispatch. For interface migration or new behavior, leave consultation fields null and dispatch the handoff to feature DESIGN. Feature DESIGN adopts it, creates/registers the canonical feature ADR, and the pre-IMPLEMENT consultation gate consults every architecture-origin feature once, including Simple work.

When the durability test passes and the user approves persistence, create a schema-valid JSON decision record and use only `decision_memory.py append`. The command records shared/local scope, locks, re-reads, and atomically fsyncs the update. Offer `docs/architecture-decisions.md` for shared memory or `.local/architecture-decisions.md` for discoverable ignored memory. Do not edit either store directly.

**Gate**: Design conversation completed or a terminal non-selected result recorded. Decision and typed handoff contain every required field. Human approved the next workflow before dispatch.

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| No shallow modules found | Well-structured or too small codebase | Valid outcome. Suggest re-running after next major feature. |
| Recent-change scan is empty | New repository, shallow history, or named scope is dormant | Use the named/originating evidence scope. Report no findings if that scope also misses the evidence floor. |
| Too many candidates | Pervasive shallowness | Focus on 5 highest-leverage (most callers benefit). Split into sessions by subsystem. |
| Prior rejection matches a candidate | Survey rediscovered a settled decision | Suppress it unless recorded assumptions changed; cite the decision in the no-findings or candidate record. |
| Artifact root or target is a symlink | A handoff or ADR write could escape the repository | Reject the input before the first write; do not defer or dispatch an invalid artifact request. |
| User disagrees with assessment | Model misjudged boundaries or caller patterns | Ask user to explain design intent. Complexity may be intentional (performance, backward compatibility). |
| Design conversation does not converge | Fundamental trade-off disagreement | Defer or close as no-change. Start any prototype only as a separately approved workflow. |

---

## References

- [Vocabulary](references/vocabulary.md) -- Shared architecture vocabulary: module, depth, seam, leverage, locality, deletion test
- [Interface Design](references/interface-design.md) -- Patterns for exploring alternative interfaces
- [Deepening Strategies](references/deepening-strategies.md) -- Dependency categorization and testing strategies for safe deepening
- [Maintenance Lifecycle](references/maintenance-lifecycle.md) -- Entry evidence, recent-change scope, decision memory, no-findings result, and typed delivery handoff
- [Handoff Schema](../../shared-patterns/schemas/architecture-change-handoff.schema.json) -- Machine-checkable terminal-state and successor contract
- [Decision-Memory Record Schema](references/decision-memory-record.schema.json) -- Machine-checkable durable record contract
