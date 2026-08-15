---
description: "Multi-angle toolkit evaluation, ADR creation, and fix pipeline."
effort: high
context: fork
allowed-tools:
  - Agent
  - Read
  - Write
  - Bash
  - Glob
  - Grep
  - Edit
routing:
  triggers:
    # Direct intent
    - improve the toolkit
    - evaluate the repo
    - find ways to improve
    - make the toolkit better
    - upgrade the toolkit
    - improve yourself
    - improve this system
    # Audit / health
    - repo health check
    - toolkit audit
    - audit the system
    - toolkit system health
    - health check
    - run a health check
    - check system health
    - audit everything
    # Evaluation
    - comprehensive improvement
    - full evaluation
    - toolkit evaluation
    - repo evaluation
    - evaluate everything
    - evaluate the system
    - deep evaluation
    - thorough evaluation
    - evaluate all components
    # Find problems
    - find issues
    - find problems
    - find bugs
    - what needs fixing
    - what's broken
    - what can be better
    - how can we improve
    - show me what's wrong
    - diagnose the toolkit
    - scan for issues
    # Meta / self
    - self-improvement
    - meta improvement
    - improvement pipeline
    - continuous improvement
    - self-evaluate
    - introspect
    - self-audit
    - self-review
    # Team / wave
    - send agents to evaluate
    - multi-agent evaluation
    - 30 agent review
    - wave evaluation
    - parallel evaluation
    - swarm evaluation
    - agent swarm
    - team evaluation
    - dispatch evaluation agents
  pairs_with:
    - comprehensive-review
    - skill-eval
    - agent-evaluation
  complexity: Complex
  category: meta
---

# Toolkit Continuous Improvement Pipeline

Multi-phase evaluation-to-improvement loop for the toolkit itself. Dispatches parallel
evaluation agents across all toolkit dimensions, synthesizes findings, applies skeptical
critique, creates validated ADRs for confirmed issues, implements via domain agents, and
validates results.

This pipeline encodes the institutional process for asking: "What is wrong with this
toolkit right now, from every angle, and what should we do about it?" — and then acting
on the answer.

**Token cost**: High and intentional. Multi-wave parallel dispatch is expensive. The cost
is justified because shallow single-pass evaluation misses the issues that matter most.
See PHILOSOPHY.md: "Tokens Are Expensive, Use Progressive Context."

---

## Flags

- `--evaluate-only`: Run Phases 1-5, stop before ADR creation. Use for a health check
  without committing to implementation.
- `--resume`: Skip to the first phase whose artifact is missing. Allows resuming a
  partial run without re-dispatching completed waves.
- `--wave N`: Run only evaluation wave N (1, 2, or 3). Use when adding new evaluation
  dimensions to an existing run.
- `--implement-adr ADR-NNN`: Skip directly to Phase 7 for a specific ADR. Use when
  picking up a previously approved ADR.

---

## Artifact Directory

Every phase writes its output to a shared directory on disk. Load from it in every
subsequent phase — this is what makes the pipeline resumable and what prevents findings
from disappearing during context compaction.

```bash
IMPROVE_DIR="/tmp/toolkit-improvement/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$IMPROVE_DIR"
echo "Artifact directory: $IMPROVE_DIR"
```

If `--resume` is set, find the most recent existing directory instead:

```bash
IMPROVE_DIR=$(ls -dt /tmp/toolkit-improvement/*/ 2>/dev/null | head -1)
echo "Resuming from: $IMPROVE_DIR"
```

---

## Phase 1: EVALUATE — Multi-Wave Agent Dispatch

**Goal**: Cover every evaluation dimension of the toolkit using parallel specialized
agents organized into three waves. Each agent reads actual source files — not summaries.

Read `references/agent-roster.md` for the complete agent personas, their focus areas,
the files each agent should read, and their output format. The roster is the authoritative
dispatch guide for this phase.

**Wave structure** — all agents within a wave must be dispatched in a single message
for true parallelism:

- **Wave 1** — Foundation: security, architecture, performance, testing, documentation,
  naming, dependencies, error handling, observability, type design
- **Wave 2** — Deep dive: dead code, ADR compliance, concurrency, migration safety, code
  quality, hook reliability, script quality, pipeline coherence, skill coverage gaps,
  routing correctness. Wave 2 receives Wave 1 findings as context to avoid duplication
  and focus on what Wave 1 missed.
- **Wave 3** — Adversarial: contrarian reviewer, skeptical senior engineer, user advocate,
  newcomer perspective, meta-process auditor. Wave 3 challenges Wave 1+2 consensus —
  these agents push back, not pile on.

**Standard agent prompt** (fill in per-agent values from `references/agent-roster.md`):

```
You are [persona].
Your focus: [focus area]
Files to read: [file list from roster]
Prior wave findings for context (do not duplicate, only add): [prior wave summary]

Produce a structured finding report:
- Finding ID: [W1|W2|W3]-[DOMAIN]-[NNN]  e.g. W1-SEC-001
- Severity: CRITICAL | HIGH | MEDIUM | LOW
- File + line reference (read the actual file before claiming an issue)
- Description: what is wrong and why it matters
- Proposed fix: concrete and implementable
- Confidence: HIGH | MEDIUM | LOW with one-sentence reasoning

Do not report findings you have not verified by reading the source file.
```

**Save all wave outputs to disk before dispatching the next wave** — findings must
survive context compaction:

```bash
cat > "$IMPROVE_DIR/wave1-raw.md" << WEOF
[paste all Wave 1 agent outputs]
WEOF

cat > "$IMPROVE_DIR/wave2-raw.md" << WEOF
[paste all Wave 2 agent outputs]
WEOF

cat > "$IMPROVE_DIR/wave3-raw.md" << WEOF
[paste all Wave 3 agent outputs]
WEOF
```

**Gate**: All three waves complete. `wave1-raw.md`, `wave2-raw.md`, `wave3-raw.md` all
exist in `$IMPROVE_DIR`. Proceed to Phase 2.

---

## Phase 2: RESEARCH — Ecosystem Best Practices

**Goal**: Gather external signal on what the LLM/agent toolkit ecosystem considers best
practice. Calibrates internal findings — prevents the pipeline from only finding issues
relative to itself.

Dispatch a single web research agent with read-only tools (WebSearch, WebFetch, Read —
no Edit, Write, or Bash):

```
You are an LLM toolkit researcher. Search for current best practices, architectural
patterns, and common pitfalls in LLM agent frameworks and AI workflow automation systems.

Cover: agent framework patterns (LangChain, AutoGen, CrewAI, Swarm), hook and
event-driven automation in AI systems, skill/tool routing and discovery, evaluation
methodologies for LLM output quality, context window management, multi-agent coordination.

For each practice or pattern found:
- Describe the practice
- Explain why it matters
- Compare to the current toolkit where possible (reference specific files)
- Priority: HIGH (clearly behind) | MEDIUM (worth considering) | LOW (nice to have)

Output a structured report sorted by priority.
```

Save output to `$IMPROVE_DIR/research-raw.md`.

**Gate**: `$IMPROVE_DIR/research-raw.md` exists. If web search is unavailable, write
"research phase skipped — web search unavailable" and continue. Research improves
synthesis quality but does not block it.

---

## Phase 3: SYNTHESIZE — Compile and Rank

**Goal**: Turn all wave outputs and research into a single de-duplicated, ranked, grouped
finding list. This becomes the input to critique and ADR creation.

Dispatch a synthesis agent:

```
You are a synthesis analyst. Read:
- $IMPROVE_DIR/wave1-raw.md
- $IMPROVE_DIR/wave2-raw.md
- $IMPROVE_DIR/wave3-raw.md
- $IMPROVE_DIR/research-raw.md

Your job:
1. De-duplicate: merge findings describing the same underlying issue. Keep the most
   concrete description. Record agreement count (how many agents flagged it).
2. Rank by impact: CRITICAL > HIGH > MEDIUM > LOW, then by agreement count.
3. Group into logical clusters — each cluster becomes one ADR candidate.
4. Integrate research: if external best practices reveal a gap the agents missed,
   add it as a research-sourced finding with source noted.
5. Preserve per finding: file references, proposed fixes, agreement count, source agents.

Save the complete ranked grouped finding list to $IMPROVE_DIR/evaluation_report.md.
```

**Gate**: `$IMPROVE_DIR/evaluation_report.md` exists with ranked, grouped findings in
logical clusters. Proceed to Phase 4.

---

## Phase 4: CRITIQUE — Skeptical Re-Ranking

**Goal**: Challenge every finding before any ADR is written. Cuts false positives,
downgrades overstatements, elevates underrated findings. Without this step, the ADR
backlog fills with low-value noise.

Dispatch a single critique agent:

```
You are a skeptical senior engineer. Read $IMPROVE_DIR/evaluation_report.md.

Your job is NOT to validate findings — it is to challenge them.

For each finding ask:
- Is the evidence concrete? (file X line Y = concrete; "probably" = not concrete)
- Is the severity accurate or overstated?
- Is this a real issue or an academic concern with no practical impact?
- Is the proposed fix actually implementable, or is it a hand-wave?
- Could this be a feature that looks like a bug?

Assign one disposition per finding:
- CONFIRM: valid, severity accurate
- DOWNGRADE: real but overstated — provide corrected severity
- DISMISS: not actionable or zero practical impact — cite specific evidence
- ELEVATE: underrated, severity should be higher — provide reasoning

Re-rank the list by your assessed severity.
Save to $IMPROVE_DIR/critique_report.md.
```

**Gate**: `$IMPROVE_DIR/critique_report.md` exists with a disposition on every finding.
Proceed to Phase 5.

---

## Phase 5: REPORT — Dual-Column Comparison

**Goal**: Show the operator where the original evaluation and the critique agree and
where they diverge. This is the decision surface — reviewed before any ADRs are written.

Dispatch a report agent:

```
Read $IMPROVE_DIR/evaluation_report.md and $IMPROVE_DIR/critique_report.md.

Produce a dual-column markdown table:
| # | Finding Summary | Original Severity | Critique Disposition | Final Severity | Notes |

Sort by Final Severity descending. Mark findings where the critique changed the original
ranking with [CONTESTED].

Also produce:
- Statistics: total findings, confirmed, downgraded, dismissed, elevated
- Top findings by final severity — highest-priority ADR candidates
- Dismissed findings list — so the operator can override if they disagree

Save to $IMPROVE_DIR/comparison_report.md. Print the full table to stdout.
```

**STOP if `--evaluate-only` flag is set.** Display `$IMPROVE_DIR/comparison_report.md`
and ask the operator what they want to do next.

**Interactive gate — do not proceed automatically.** Present to the operator:
- The full comparison table
- Summary statistics
- "Ready to create ADRs for the confirmed clusters?"

Proceed to Phase 6 only on explicit operator approval.

---

## Phase 6: ADR — Create Validated ADRs

**Goal**: For each approved finding cluster, write one ADR. ADRs are proposals — the
operator reviews them before implementation begins.

Read `../adr-template.md` for the exact format and required sections.

**One ADR per logical cluster** — not one per finding. The synthesis clusters from
Phase 3 are the natural boundaries.

For each ADR:

1. Find the next available number:
   `ls /home/feedgen/vexjoy-agent/adr/ | grep -E '^[0-9]' | sort | tail -1`
2. Read the actual source files referenced in the findings before writing the ADR — do
   not describe issues you have not verified by reading the file
3. Include both the original finding and the critique disposition in the Context section
4. Write a concrete Decision section — vague direction is not implementable
5. Write concrete Validation Requirements — exact runnable commands with expected
   output (see `../adr-template.md` for the section format)

**Dispatch all ADR-writing agents in a single message** — one agent per cluster,
all in parallel.

After all agents complete, present the ADR list to the operator and ask:
"Review these ADRs. Approve all, approve specific ones, or edit before I proceed to
implementation?"

Do not begin Phase 7 until the operator explicitly approves at least one ADR.

---

## Phase 7: IMPLEMENT — Execute ADR Task Lists

**Goal**: For each approved ADR, dispatch the appropriate domain agent to implement the
task list in the Decision section.

**Domain agent selection**:

| Domain | Agent |
|--------|-------|
| Go source code | `golang-general-engineer` |
| Python hooks and scripts | `python-general-engineer` |
| SKILL.md files | `skill-creator` |
| Agent .md files | `skill-creator` |
| Security hardening | `systematic-code-review` |

**Branch before any implementation** — never implement directly on main:

```bash
BRANCH="improvement/$(date +%Y%m%d)-adr-batch"
git checkout -b "$BRANCH"
echo "Implementation branch: $BRANCH"
```

**Overlap check before parallel dispatch**: Extract the Components table from each ADR.
ADRs with no file overlap can run in parallel. ADRs touching the same files must run
serially.

**Per-ADR agent dispatch prompt**:

```
You are implementing ADR-NNN: [title].

1. Read /home/feedgen/vexjoy-agent/adr/NNN-*.md fully before touching any files.
2. Read each source file in the Components section before modifying it.
3. Execute every task in the Decision section. Do not skip tasks.
4. Run language-appropriate tests after each change:
   Go: go test ./... | Python: python -m pytest | Generic: make check
5. Do not modify files outside the Components section.
6. Save an implementation log to $IMPROVE_DIR/impl-adr-NNN.md:
   - each change made (file, what changed, why)
   - test results
   - any tasks that could not be completed and why
```

**Gate**: All implementation agents complete. Consolidate logs:

```bash
cat "$IMPROVE_DIR"/impl-adr-*.md > "$IMPROVE_DIR/implementation-summary.md"
```

---

## Phase 8: VALIDATE — Skill Evaluator Gate

**Goal**: Verify no skill or agent routing was degraded by implementation. Every modified
skill must meet or exceed its baseline score — regressions are blockers, not warnings.

Identify modified skills and agents:

```bash
git diff --name-only "$BRANCH" | grep -E "(skills|agents|pipelines)/.*\.md$"
```

Run structural validation for each:

```bash
python3 -m scripts.skill_eval.quick_validate <skill-path>
```

For skills where triggers or descriptions changed, run trigger eval:

```bash
python3 -m scripts.skill_eval.run_eval \
  --eval-set <skill-path>/evals/evals.json \
  --skill-path <skill-path> \
  --runs-per-query 3
```

Record results to disk:

```bash
echo "[skill-name] baseline: N post-impl: M [PASS|FAIL]" >> "$IMPROVE_DIR/validation-results.md"
```

**Gate**: All validated skills pass. Any failure routes to Phase 9. Full pass routes to
Phase 10.

---

## Phase 9: REMEDIATE — Regression Recovery

**Goal**: Diagnose and fix skill regressions from Phase 8. Three parallel perspectives
per regression. Maximum 3 retry cycles before operator escalation.

Runs only when Phase 8 reports failures. Read `$IMPROVE_DIR/validation-results.md` to
identify regressed skills.

For each regressed skill, dispatch three agents in a single message:

```
Agent A (Contrarian): Read the skill and its git diff. Challenge whether the Phase 7
change was necessary. Propose a simpler alternative that preserves the baseline score.

Agent B (Domain Specialist): Read the validation failure from validation-results.md.
Diagnose exactly why the score dropped. Propose targeted fixes for the specific failure.

Agent C (User Advocate): Read the skill as a user trying to invoke it. Does the change
make it harder to discover? Propose routing or description improvements that recover
discoverability without reverting the ADR intent.
```

Synthesize the three reports. Identify the fix with the strongest evidence. Apply it.
Re-run Phase 8.

**Retry limit** — stop and escalate after 3 cycles:

```bash
REMEDIATION_COUNT=$((${REMEDIATION_COUNT:-0} + 1))
if [ "$REMEDIATION_COUNT" -ge 3 ]; then
    echo "ESCALATE: 3 cycles exhausted. Operator decision required."
    echo "See $IMPROVE_DIR/remediation-*.md for all perspective reports."
fi
```

**Gate**: All regressions resolved or escalated. Proceed to Phase 10.

---

## Phase 10: RECORD — Capture Learnings

**Goal**: Persist reusable patterns from this run into `learning.db` so they surface
automatically in future sessions.

For each non-obvious pattern or successful remediation:

```bash
python3 ~/.claude/scripts/learning-db.py add \
  --error "[pattern: what the symptom looked like]" \
  --solution "[what fixed it]" \
  --confidence 0.8 \
  --source "toolkit-improvement-pipeline"
```

Write a session summary artifact:

```bash
cat > "$IMPROVE_DIR/session-summary.md" << SEOF
Run date: $(date)
ADRs created: N | approved: N | implemented: N
Validation: N passed | N regressions | N escalated
Learnings added to learning.db: N
Artifact directory: $IMPROVE_DIR
Branch: $BRANCH
SEOF
```

Display to the operator:

```
Toolkit Improvement Pipeline Complete
======================================
Artifacts: $IMPROVE_DIR/
Branch:    $BRANCH

To submit: use /pr-sync or /pr-pipeline from the implementation branch.
```

---

## Error Handling

**Agent times out during evaluation wave**: Collect findings from completed agents. Note
which timed out. Proceed with partial wave — do not block the entire wave on one timeout.
Offer to re-run the timed-out agent individually if its dimension is critical.

**Synthesis produces a finding without a file reference**: Not ADR-ready. Return to raw
wave outputs and find concrete evidence, or mark DISMISS in critique. Vague findings
produce vague ADRs that produce vague implementations.

**ADR agent cannot verify a finding in source**: Write the ADR with "unverified" in the
Context section. The operator can dismiss it at the Phase 6 gate.

**Implementation breaks unrelated tests**: Check whether the test was already failing on
base branch before reverting. If pre-existing: note in the implementation log and
continue. If newly broken: revert the specific change and route to Phase 9.

**Web search unavailable in Phase 2**: Write a placeholder to
`$IMPROVE_DIR/research-raw.md` and continue. Internal evaluation findings remain valid.

**Operator rejects all ADRs at Phase 6**: All artifacts remain in `$IMPROVE_DIR/`.
Exit cleanly. The comparison report can inform future manual decisions.

---

## References

- `references/agent-roster.md` — Evaluation agent personas, focus areas, file targets,
  and dispatch prompts organized by wave
- `../adr-template.md` — Standard ADR format (`skills/workflow/references/adr-template.md`)
