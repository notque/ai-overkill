---
summary: "Design principles behind every agent, skill, hook, and workflow."
read_when:
  - "making a design decision"
  - "creating or restructuring components"
---

# Design Philosophy

The decisions that shaped every agent, skill, hook, and pipeline. Not guidelines. Architecture. A coherent viewpoint enables iteration better than unconnected rules ever will.

For what I do, these principles are non-negotiable. For what you do, they might be different. But this is what works here, tested against real output, measured against real failures.

---

## Zero-Expertise Operation

The system requires no specialized knowledge from the user. Say what you want done. The system handles the rest.

- "Fix this bug" triggers: classify, select debugging agent, apply methodology, branch, test, review, PR. User never chooses an agent.
- "Review this PR" dispatches specialized reviewers (security, business logic, architecture, performance). User never configures reviewers.
- "Write a blog post about X" researches, drafts in calibrated voice, validates. User never loads a voice profile.

**Test:** Does this feature require the user to know something internal? If yes, redesign it.

**Automation corollary.** Anything that can fire automatically and fails safe, should. Automation that can delete or overwrite starts add-only and earns its destructive path — Warn-Only Gates (below) applied to automation. The sync hook proved why: stale cleanup repeatedly removed a support-directory link before regression tests pinned the add-only invariant (citation in Warn-Only Gates). Rule for this document: every invariant asserted here cites the test that enforces it, not the commit that intended it. Second rule: evidence that the system missed a principle names lifecycle debt, never repeal. The gap goes on the build list; the principle stands until an experiment refutes it. The sync incident reads exactly that way — corollary sound, enforcement lagged. Gates enforce via hooks. Context injects via SessionStart/UserPromptSubmit. Learning happens via PostToolUse capture. The user describes intent. The system does everything else.

---

## Plain English Is the Interface

Plain English is the primary interface, not a fallback. "Make this faster" routes identically to "/do dispatch performance-agent with profiling skill against src/server.go."

- Users should never need system-prompt preambles. If they do, routing failed.
- If rephrasing a natural request into structured format produces better results, that is a router bug.

**Test:** A first-time user's request vs. the same request rewritten by someone who read every agent file. If the rewritten version routes better, fix routing.

---

## Everything That Can Be Deterministic, Should Be

The foundational principle. LLMs orchestrate deterministic programs. They do not simulate them.

| Problem type | Handler | Examples |
|---|---|---|
| Solved (deterministic, measurable) | Scripts | File searching, test execution, build validation, data parsing, frontmatter checking |
| Unsolved (contextual, judgment-requiring) | LLMs | Contextual diagnosis, design decisions, pattern interpretation, code review |

**Four-layer architecture:**

| Layer | Role | Example |
|---|---|---|
| Router | Classifies and dispatches | `/do` skill |
| Agent | Domain-specific constraints | `golang-general-engineer` |
| Skill | Deterministic methodology/workflow | `systematic-debugging` |
| Script | Concrete operations with predictable output | `scripts/learning-db.py` |

For large mechanical sweeps: if the change can be expressed as detector + rewrite rule, use a script. LLMs handle only exceptions requiring judgment.

**Test:** Is this operation deterministic? Same input, same output? If yes, it belongs in a script.

### State Boundary

LLM context is a view, not storage. It should contain only the facts needed for the current judgment.

| State shape | Home | Why |
|---|---|---|
| Structured, queryable, recurring, high-volume | SQLite, JSON, generated indexes, event logs | Schema, queries, dedupe, pruning, and deterministic replay |
| Unstructured, interpretive, reasoning-shaping | Agent files, skill references, ADRs, prose notes | Nuance matters more than SELECT clauses |
| Ephemeral working context | Prompt/session context | Short-lived view for the current task |

If data needs filtering, aggregation, confidence, retention, or replay, store it outside the prompt. If context shapes judgment and resists a stable schema, keep it as prose and load it on demand.

**Test:** Would a script reasonably run a query against this state? If yes, it belongs in a structured store. Would a table strip out the reason the context matters? If yes, it belongs in prose.

### Routing confidence and force_route

Deterministic pre-route matches `force_route` triggers only: a match that survives the semantic guards routes at high confidence, everything else falls through to the semantic route — see `determine_confidence` in [`scripts/pre-route.py`](../scripts/pre-route.py) and the per-skill `force_route` flag in skills/INDEX.json (schema: `scripts/generate-skill-index.py`).

`force_route: true` belongs on umbrella, setup, and methodology skills where a single high-specificity trigger phrase carries unambiguous intent (`pr-workflow`, `install`, `quick`). Domain task skills earn confidence through multiple trigger matches — preventing misroute when phrases like "fix" or "review" overlap.

### Semantic Routing Is Settled; So Is Who Reads the Manifest

`/do` Phase 2 routes by reading intent with a model. Two claims hide here, each with its own evidence. Keep them separate.

**SETTLED: semantic routing beats keyword routing.** Dropping the semantic layer for pure deterministic `pre-route.py` keyword routing collapses strict routing accuracy **63.3% → 34.7%**. Keywords score **0% on every paraphrase bucket** — "send my commits to the server" carries no keyword trigger — so **22 of 49 requests** lose their correct agent+skill and fall to a skill-less general handler. (Drop-Haiku A/B, 2026-05-29, corpus n=49, report `tmp/drophaiku-ab-report.md`, recorded via PR #715; companion ordering A/B in `skills/meta/do/references/semantic-first-ab-results.md`.) Skill discovery contributes none of this value — the harness already injects the full `available-skills` list, with descriptions, into every session. The semantic layer earns its keep on agent+skill *pairing*, safety-critical force-routes that drag git/security work through the quality gates (lint/tests/CI), the quality-loop wrapper, complexity classification, parallel decomposition, and task-spec injection. Cost at the time: ~+0.1 Haiku calls/request; since self-route landed, an in-session manifest read.

**SETTLED: orchestrator self-route beats the Haiku sub-dispatch.** The n=49 tie (63.3% vs 63.3%, 2026-05-29) broke at n=99: the self-route-v1 blind A/B (2026-06-10, byte-identical full-manifest prompts, only the routing model differing) scored self-route **57.6% vs 49.5%** (+8.1, help 13 / harm 5, McNemar p=0.0963), zero new safety-bucket misses, stub-tier improved 9→12 — every pre-registered gate passed: **PROMOTE**. Mechanism: the main model holds agent attribution on one-line manifest entries where Haiku drops it — the exact failure that REJECTED both tiered-manifest runs. The Haiku hop bought a cheaper price per routing call and nothing else; by the program's own rule ("if it isn't improving the router, remove it") it is deleted from /do Phase 2 Step 0 — the orchestrator routes off the manifest in-session. Per-call self-route measured 11.2x in sub-dispatch form, but production deletes the dispatch hop entirely; the manifest read is the whole marginal routing cost, which is why the manifest trim below now carries the savings. Verdict: `scripts/routing-ab-results/self-route-v1/VERDICT.md` (PR #776); harness home stays docs/router-ab-runbook.md.

**Known follow-up.** The honest cost is the manifest, not the router: the routing manifest duplicates skill descriptions the native `available-skills` list already carries. Trim it to router-only metadata (FORCE flags, agent pairings, `not_for`) — that, not removing the router, is the real optimization.

**OPEN: structural bets before scalar tweaks.** Hypothesis: when sequencing A/Bs, run the bets that change the system's shape (remove the Haiku step, drop verb dispatch) before the bets that tune it (trim a directive). A structural verdict reshapes every later experiment; a scalar verdict tunes a shape that may not survive. Evidence so far is external only — no in-house run has tested the ordering. Validation: the model-era recalibration A/Bs, which re-run the standing experiments under the new model line in exactly this order.

---

## Triple-Validation Extraction Gate

When an LLM extracts patterns, it produces more than belongs in the final artifact. A pattern earns its place only if it passes three checks:

1. **Recurrence.** Appears in 2+ distinct samples/contexts. One occurrence is anecdote, not rule.
2. **Generative power.** Predicts new decisions the source has not produced yet. Description-only traits are summaries, not models.
3. **Exclusivity.** Distinguishes the subject from peers. A "rule" every Go codebase or tech blogger shares is background, not domain knowledge.

Applied as a deterministic phase, not a vibe check. Five high-confidence traits beat twenty plausible ones.

**Test:** Can you name which of the three checks this pattern passed? If not, it has not earned its place.

---

## Deterministic Phase Checkpoints

Between any parallel-gather phase and any synthesis phase, insert a script. The script walks the artifact directory, counts what is there, computes ratios, surfaces conflicts, emits a Markdown table. The table is the gate. Synthesis does not begin until the table looks right.

The script answers questions the LLM should not guess: source counts per agent, primary-to-secondary ratios, single-source claims, contradictions between sources.

The gate is structural, not advisory. A phase the script flags as incomplete does not advance because the table is the artifact the next phase reads, and the next phase's instructions require passing counts.

**Test:** Is there a script between your gather and synthesis? Does it emit a table? Does the pipeline stop on failing counts?

---

## Breadth Over Depth

Tokens buy more value as specialists in parallel than as longer prompts to a single agent.

| Principle | Implication |
|---|---|
| Narrow focused context beats unfocused lengthy context | Each agent loads only the references its current task needs |
| Progressive disclosure | Reference files live on disk, load when the phase needs them, not at session start |
| Eager routing is non-negotiable | Dispatching agents is the core execution model, not a cost to avoid |
| More relevant context > more context | Under-loading is as wrong as over-loading |
| A dispatch moves work, never copies it | Dispatch shifts work from the expensive model to a cheap one; duplicating context across both pays for the same tokens twice |

**Test:** Is this agent loading context it will not use for this specific task? If yes, move it to a reference file and load conditionally. Does this dispatch move work from the expensive model to a cheap one, or duplicate context across both? If duplicate, inline it. The Haiku manifest round-trip (above) is the miss this test would have caught: the manifest re-sends skill descriptions the orchestrator already holds.

---

## The Router Is the Management Layer

`/do` is a management layer for the harness, implemented in prompt-space. Inventory its jobs:

| Job | What the router does |
|---|---|
| Intent classification | Reads the request, names the task class |
| Agent + skill selection | Pairs the domain agent with its methodology skill |
| Workflow composition | Picks the pipeline, fans out, dictates the roster |
| Parallel decomposition | Splits independent work across agents |
| Policy enforcement | Force-routes; quality gates (lint/tests/CI) on git and security work |
| Communication discipline | The mandatory density/completeness injection in every handoff |
| Resource policy | Model per task class, token budgets |
| Learning capture | Routing decisions and outcomes into learning.db |

Jobs migrate by kind — Everything Deterministic (above) applied to the router's own work. Judgment jobs (intent reading, complexity classification, decomposition) stay in prompt-space. Mechanical jobs (injection assembly, marker stamping, roster table lookups, banner emission) move to hooks and scripts as they prove deterministic. Hooks are harness code: programs that run on lifecycle events, outside prompt-space. The PreToolUse injection hooks already in production (`pretool-subagent-warmstart.py`, the reference-loading gate) prove the pattern.

The harness verdict: build no separate harness. Harness-by-accretion through hooks keeps the six-CLI portability a custom harness would forfeit. Revisit when a need appears that the hook surface cannot give — true scheduling, mid-flight arbitration between agents, enforced (not advisory) budgets.

**OPEN: the harness owns the inner loop; we build only the outer.** The inner agent loop — message, tool call, write-back, repeat — is harness code. Hypothesis: our layer is the outer loop on top of it, and no framework belongs in between. Validation: the revisit triggers above. The claim stands until true scheduling, mid-flight arbitration, or enforced budgets demand a loop the harness cannot host.

**OPEN: a loop is an agent loop only if the decider sees what actually happened.** Hypothesis: outer-loop decisions read observed execution results appended to state, never the worker's self-report, and the stop condition is verified criteria, not the model's own done-signal — deliberately stricter than the inner loop's `end_turn`. Validation: the objective-loop skill (in flight on its own branch) running real objectives in production.

**Test:** Is this router job deterministic? Same input, same output? Move it to a hook or script. Does it need judgment? It stays in the skill.

---

## Knowledge Lives in Agents, Authored by Humans

The base LLM is a generalist. An agent's job is to close the gap with actual expert knowledge, not by declaring "I am an expert in X."

**High-context (carries information):** Version-specific idiom tables, concrete failure mode catalogs with detection commands, error-to-fix mappings from real incidents, project-specific conventions from PR history.

**Thin wrappers (carries nothing):** "You are an expert Go developer," general best practices the model already knows, padding to fill sections.

Progressive disclosure: main agent file stays navigable (≤600 lines, ~10k words). Reference files cap at ≤500 lines so each loads cleanly without crowding context. Deep reference material lives in `references/`, loaded on demand.

**Test:** Remove the motivational preamble. Does quality change? (No.) Remove a domain-specific failure mode table. Does quality change? (Yes.)

### Human Owns Definitions; Claude Drafts

Skill descriptions, agent profiles, and INDEX entries are hand-authored. When LLM auto-generation of definitions was tested on evals, accuracy fell net-negative. The system scaffolds and suggests; humans decide. No auto-generation hook exists: `skill-creator` stages output for human review before merge, and `CONTRIBUTING.md` holds the quality bar (specific, verifiable, battle-tested, minimal, dense) every definition must clear.

---

## Structural Enforcement

Instructions can be rationalized past. Exit codes cannot.

| Mechanism | Best for | Why |
|---|---|---|
| Hooks (exit 2 = block) | Binary gates: file exists? format valid? bypass var set? | Deterministic, unbypassable, sub-50ms |
| LLM instructions | Judgment calls: right approach? sufficient quality? route here? | Contextual, nuanced, adaptable |

Gates are automated, not advisory. Hook fails = pipeline stops. Hooks are fragile to deploy, reliable in operation.

**OPEN: verification ranks exit code > fresh-context grader > self-critique.** Hypothesis: an exit code is the strongest verdict; where no mechanical check exists, the next best is a grader reading the work in a fresh context; self-critique sits below both and earns no rung — grading work in the context that produced it inherits that context's rationalizations. Validation: the objective-loop skill (in flight) runs real objectives; compare criteria outcomes on the grader path against the mechanical path.

**Test:** Can the model rationalize past this gate? If yes, make it a hook.

---

## Warn-Only Gates Beat Blocking Gates

A gate is a hard stop; a safeguard is an observable alert. Most checks should be safeguards. Anything that blocks a merge must prove its worth and ship with an explicit escalation path. New checks start advisory and graduate to blocking only via a dedicated ADR and operator sign-off.

This is how the system is built, not an aspiration. `hooks/stop-drift-guard.py` detects toolkit drift and re-wakes the session async — it never blocks. The post-merge sync hook is add-only: it adds new items, never overwrites. That invariant is enforced by `TestSupportDirSurvivesCleanup` in `hooks/tests/test_sync_to_user_claude.py` (PR #762), added after stale cleanup repeatedly removed a support-directory link. The add-only intent dates to commit 8d7c8b00 in `install.sh`; the invariant held only once a test enforced it — which is why this document cites tests, not intentions. `hooks/session-learning-recorder.py` warns when a substantive session captured zero learnings, then exits clean. When PR #747 weighed a blocking re-run check for the negative-results registry, it deferred to a future ADR with a documented escalation path rather than ship a hard stop.

**Test:** Does this check stop work on failure? If the failure is advisory, make it warn and exit 0; reserve blocking for gates that earned an ADR.

---

## Everything Pipelines

Complex work decomposes into phases. Phases have gates. Gates prevent cascading failures.

**Why:** Saved artifacts per phase. Gates enforce prerequisites. Independent phases parallelize. Failures isolate. Progress is visible and resumable.

**When to pipeline:** 3+ distinct phases, mixed deterministic/LLM work, intermediate artifacts have value, benefits from parallel execution.

**When NOT to:** Reading a file by path, simple lookups, one-step operations.

**Standard template:** GATHER (parallel agents) -> COMPILE (structure) -> EXECUTE (do the work) -> VALIDATE (deterministic + LLM) -> DELIVER (output + validation report).

**Test:** Does this task have independently-failing phases? Does an intermediate artifact have value even if later phases fail? If yes, pipeline it.

---

## Maintenance as Governance

One-line doc PRs are system health, not chores. A registry entry or a README count fix is the feedback loop that surfaces drift early; invest in it to prevent rot.

The loop is designed, not incidental. `scripts/validate-doc-counts.py` runs as a CI gate and `hooks/stop-drift-guard.py` re-checks counts when a component is added or removed — together they turn a stale script-count claim in the README into a failing check and a one-line fix. PR #748 dogfooded the whole capture→store→query→display path through a single boring-fix registry entry: a mistake surfaced, got recorded as a negative result, was reviewed, and merged. The tiny PR proved the loop works end to end.

**Test:** Is this fix "too small to bother"? If it closes a drift the system can detect, it is governance — ship it.

---

## Components Earn Their Keep

One Domain, One Component governs creation. This governs retirement. A component's value is measured in routes carried; the route-weights and route-events telemetry is the detector (read it via `scripts/learning-db.py` route-health). Zero routes over a long window means shelf-ware: a candidate for demotion to a stub in the manifest, archival, or deletion — with demand-driven reactivation when traffic returns. As of 2026-06-10, the live working set — roughly four agents and six skills — carries nearly all routed traffic across 129 routable skills (134 on disk; 5 demoted to references). A dated observation, not a permanent number. Recursive Measurement applies to the catalog itself: a component nobody routes to is context every session still pays for.

Hooks need this governance most: a hook is the easiest component to create and the hardest to manage. Managing, correcting, and retiring hooks is named, recurring debt. The detector seed exists — the hook-health CI job (`scripts/validate-hook-health.py`, gating in `.github/workflows/test.yml`) — and the route-events/learning instrumentation pattern generalizes to hook firings. A hook nobody can attribute a benefit to is shelf-ware with side effects — worse than a shelf-ware skill, because it executes.

**Test:** When did this component last carry a route? If the telemetry can't answer, fix the telemetry. If the answer is "never in a long window," demote it.

---

## Density — The Dense-Complete Writing standard

High fidelity, minimum words. The standard is Bertrand Russell's five prose rules ("How I Write"): shortest accurate word, cut words carrying no instruction, plain English, concrete over abstract, heavy qualifications in separate sentences. A sixth rule, Completeness, guards the floor: treat content as fixed and wording as negotiable — carry every required point through the draft, then choose the shortest plain words that say those points exactly. It is the structural guide for everything we do — every part of every agent, every thinking turn, every generation: output, plain text, the model's own thinking, skill and instruction files, code comments. Prefer tables and lists for structured content, paragraphs for reasoning.

Minimalism drops information for aesthetics. Density keeps all information and drops everything else.

**Evidence.** Three blind dual-track (Claude + Codex) A/B runs tested whether the standard helps. A Go token-bucket task showed no effect — correctness was ceiling-bound, every variant passed build, vet, and race. A skill-authoring task showed the payoff: the guidance arm (PHILOSOPHY.md + standard) beat control by +6.4/60, won 80% of cross-arm pairwise comparisons, Cliff's delta +0.60 (2026-05-31, artifact: `evals/dense-complete-writing/README.md`). Lesson: the standard pays off on prose and judgment work, not ceiling-bound code. One treatment run over-compressed — thinnest skill, dropped detail — which motivated a Completeness clause. A clause race then tested control plus ten candidate phrasings (five Codex, five Claude) on one complex skill task (`log-secret-auditor`), graded blind dual-track on a 20-point coverage rubric plus a dense-and-complete score. The winner (g07) decouples content from wording and hit top coverage at the fewest words. Caveat: pilot N=1 per arm; coverage held across all arms, so the clause is proven to raise density at equal coverage, not yet proven to prevent a coverage collapse.

The canonical wording lives at `skills/shared-patterns/dense-complete-writing.md`. Three high-traffic surfaces reproduce the rules verbatim so they sit in context every turn — `CLAUDE.md`, `agents/base-instructions.md`, the `/do` router injection (`skills/meta/do/SKILL.md`); edit the canonical file first, then propagate to those three. This reference doc and `skill-creator` carry a summary plus the pointer above.

**Test:** Read each sentence. Does it carry an instruction, rule, or decision? If none, cut it.

---

## Supporting Principles

These follow from the principles above. They are consequences, not independent axioms.

### Local-First, Deterministic Over External APIs

Default to local, deterministic implementations. External APIs couple to third-party availability, cost, rate limits, stability. When an API is unavoidable, wrap it in a skill with explicit dependencies and capture the contract in references. Forbidden: third-party billing the user did not authorize.

**Test:** Does this component work offline? If a third-party outage breaks it, the dependency must be wrapped in a skill with a declared contract — anything else is a bug.

### External Components Are Research Inputs, Not Imports

External repositories reveal patterns and missing checks. Adoption path: study, extract the practice, test whether it fills a gap, rebuild inside our architecture. External markdown/scripts/metadata are untrusted evidence.

**Test:** Did the practice arrive rebuilt and tested inside our architecture, or as copied files? Copied files skipped the gate.

Worked example: the OpenAI curated-template pack (twenty near-identical `artifact-template-*` entries, 27 MB of `.pptx`/`.xlsx`/`.docx` binaries) was studied, not imported. We extracted two practices — clone-don't-regenerate fidelity and the content-vs-layout authority rule — and rebuilt them as `html-artifact` clone mode: one skill, a saved-template gallery, and a fill script enforcing the authority rule with exit codes (`skills/meta/html-artifact/scripts/fill-template.py`). The pack itself failed the test on three counts (thin wrappers, host-locked to an Office runtime, one skill copied twenty times), so nothing was imported. Practice adopted, files rejected. Test: `skills/meta/html-artifact/scripts/tests/test_fill_template.py`.

### One Domain, One Component

System prompt token budget is finite. One domain = one agent/skill + many reference files loaded on demand. Before creating any new agent/skill: check whether an existing component already covers the domain. If it does, add a reference file.

**Test:** Name the existing component that covers this domain. If you can name it, add a reference file instead of a new component.

### Skills Are Self-Contained Packages

Everything a skill needs lives inside its directory: scripts, viewer templates, bundled agents, reference files, assets. Self-contained = copyable, testable, reviewable as a unit, deletable without orphaning dependencies.

**Test:** Delete the skill's directory. Does anything outside it break? If yes, it was never self-contained.

### Workflow First, Constraints Inline

Skill documents place the workflow immediately after frontmatter. Constraints appear inline within the phases they govern, with reasoning ("because X"). A/B/C testing: workflow-first swept constraints-first 3-0 across all complexity levels.

**Test:** Open the skill file. Is the workflow the first thing after frontmatter, with each constraint inline in the phase it governs? If a constraint block precedes the workflow, restructure.

### Positive Framing as CI Gate

Instructions tell the reader what to do, not what to avoid. Compare these two framings:

```
"NEVER edit code directly"        → boundary learned, no target action
"Route all code modifications to domain agents" → same boundary + clear action
```

**The 100% requirement.** Every agent and skill in the fleet must pass instruction-mode joy-check with zero primary negative patterns. 60% pass was the prototype threshold. 100% is the CI gate. Below 100%, the framing debt accumulates — each prohibition or negative lead added to a skill reduces the signal quality for every downstream invocation.

**What the CI gate catches:**

```
| Pattern                  | Example                        | Positive rewrite                                   |
|--------------------------|--------------------------------|----------------------------------------------------|
| NEVER (caps)             | "NEVER edit code directly"     | "Route all code modifications to domain agents"    |
| do NOT / Do NOT          | "Do NOT use git add -A"        | "Stage files by name: git add specific-file.py"    |
| must NOT                 | "Hooks must NOT block tools"   | "exit 0 on errors to keep tools available"          |
| FORBIDDEN                | "FORBIDDEN Patterns"           | "Hard Gate Patterns"                                |
| Don't at instruction start | "Don't skip validation"      | "Run validation before marking complete"            |
| Avoid heading/bullet     | "### Patterns to Avoid"        | "### Preferred Patterns"                            |
| Anti-Pattern heading     | "## Anti-Patterns"             | "## Preferred Patterns"                             |
```

**Contextual exceptions** (not flagged): subordinate negatives after a positive instruction ("Credentials stay in .env files, never in code"), negatives in fenced code blocks, blockquoted lines, technical terms.

**Implementation:** `scripts/validate_positive_instruction_docs.py` is the deterministic engine. `scripts/tests/test_joy_check_instruction_mode.py` runs golden fixtures (each pattern, each exception) and a parametrized fleet scan. The `joy-check` CI job in `.github/workflows/test.yml` gates all PRs.

**Test:** Run `python3 scripts/validate_positive_instruction_docs.py` — exit code 1 means violations exist. Fix them before merging.

### Both Deterministic AND LLM Evaluation

**Tier 1 (fast, free, CI-friendly):** Frontmatter parses? Files exist? Required sections present?
**Tier 2 (deep, nuanced, expensive):** Content useful? Failure modes domain-specific or filler?

Neither tier replaces the other. Pipeline: deterministic first, fix, LLM evaluation, fix, final score.

**Test:** Did Tier 1 run and pass before Tier 2 graded? LLM scores on artifacts that fail deterministic checks are wasted tokens.

**Ceiling-bound evals judge nothing.** An A/B where the baseline scores at or near ceiling returns a null verdict on the eval, not the variant. Two in-house cases: the Go token-bucket density run (every arm passed build/vet/race — no effect measurable) and the fact-check skill round 1 (dead tie 19/19 catches both arms on an easy corpus; the hardened corpus — distractor sources, unit drift, false-alarm traps — separated the arms and the skill passed its pre-registered bar; evidence: `docs/what-didnt-work.md` 2026-06-12 entry, PR #811). Before accepting a null result, check the baseline's score against ceiling; harden the corpus until the baseline drops below it.

### Anti-Rationalization as Infrastructure

The biggest risk: rationalization. "Already done" (assumption). "Code looks correct" (looking, not testing). "Should work" (should, not does). Auto-injected into every code modification, review, security, and testing task. An agent can rationalize past an instruction. It cannot rationalize past an exit code.

**Test:** Is the completion claim backed by an exit code or by "should work"? Only the exit code counts.

### Model Policy by Task Class

Owner model-selection policy (ADR `model-selection-policy`; operational table in `skills/meta/do/SKILL.md`, Model Selection):

**Harness-native routing:** each harness defaults to its own provider's model lane. Cross-provider dispatch is manual-only, never automatic. Start low, escalate on miss — high tiers cost 3-6x per Pass@1 point where measured. Plan budget ($200/month per provider) makes cost a first-class constraint. Three decision axes: the current session model (the harness runs Opus 5, the owner-directed Anthropic-lane default at every task class), DeepSWE Pass@1 (agentic completion) where a model has been measured, and owner-observed felt quality (opus > gpt-5.5 marginal); ties resolve in favor of felt quality.

| Task class | Anthropic lane (Claude Code) | OpenAI lane (Codex CLI) |
|---|---|---|
| Deterministic | Scripts — no LLM dispatch | Scripts — no LLM dispatch |
| Low-risk | `opus` / `low` (Opus 5, unmeasured) | `gpt-5.6-terra` / `high` (54 P@1 / $1.13) |
| Standard | `opus` / `medium` (unmeasured) | `gpt-5.6-sol` / `high` (69 / $3.47) |
| High-risk | `opus` / `high` (unmeasured) | `gpt-5.6-sol` / `xhigh` (71 / $4.70) |
| Max-power | `opus` / `xhigh` (unmeasured) | `gpt-5.6-sol` / `max` (73 / $8.39) |

The `/do` table is canonical and records the full DeepSWE Pass@1 / cost / tokens / steps data, including the prior Opus-4.8 / Sonnet-5 measurements kept for manual picks. Opus 5 has no DeepSWE run yet, so its pts/USD is uncomputable and the selection rests on the session-model and owner-directive axes; effort still follows start-low-escalate-on-miss. Max-power requires `manual_model_override=true` in both lanes. Sonnet is manual-only. Legacy `gpt-5.5` and non-default GPT-5.6 points are manual-only. Haiku is retired (routing was Haiku pre-#777; self-route since — `scripts/routing-ab-results/self-route-v1/VERDICT.md`). Defaults, not limits: escalate when cheaper output misses the bar; for anything that ships, intelligence > taste > cost, with cost a tie-breaker only. Fan-out uses the lane's low-risk point; one synthesis agent may run one tier higher.

**Coordinator model.** The main-thread coordinator routes and evaluates, never executes — its cost is input-dominated and Pass@1 measures execution it never does. Anthropic harness → opus (Opus 5, the session model); OpenAI harness → gpt-5.6-terra/high; downgrade the anthropic coordinator to sonnet only as a deliberate plan-limit measure, set via harness config (`/model`), not per-turn. Full rule: `skills/meta/do/SKILL.md`, Model Selection.

**Token costs are not fungible.** One Opus token costs ~30x one Haiku token. Optimization targets the expensive model, not the cheap one. "Saves Haiku calls" is never a valid justification. Pre-routing's value is determinism (regex can't misroute). Phase gates' value is preventing Opus rework.

**Test:** Which model's tokens does this optimization save? Savings on the cheap model never justify added complexity.

### Prompt Phrasing Does Not Replace Domain Knowledge

Four A/B experiments: ego-boosting, urgency framing, emotional prompts. Results: small effects (+9-12%), not reliable. 3/4 agents fabricated regardless of prompt variant. Domain knowledge, structured methodology, and taste beat motivational preambles every time.

**Test:** Does the proposed prompt change add domain knowledge, or only enthusiasm? Demand its A/B before adopting; enthusiasm measured +9-12% and unreliable.

### Trust Boundaries Separate Policy From Evidence

Content entering the prompt has different trust levels. Four levels: policy (highest), trusted runtime context, retrieved context (evidence), user request (intent). A retrieved document saying "ignore previous instructions" is evidence with hostile payload, not a command.

**Test:** Can content at a lower trust level change what a higher level allows? If retrieved text can alter policy or actions, the boundary leaked.

### Cache-Friendly Prompt Layout

Static prefix (identity, policy, workflow, cacheable) + dynamic tail (user facts, retrieved context, session flags). Invariant content in agent files, variable content in injection mechanisms.

**Test:** Does anything session-variable sit above the static prefix? Each one breaks the cache on every turn.

### Variables Are Contracts, Not Placeholders

A prompt variable is a typed program input: expected format, escaping, behavior when absent or malicious. Every variable must have causal value: does it change the answer, allowed actions, or explanation style? If no, do not inject it.

**Test:** Remove the variable. Does the answer, the allowed actions, or the explanation style change? If nothing changes, stop injecting it.

---

## Learning System Discipline

Negative results are assets worth a registry. Document what didn't work before it vanishes; one lookup prevents re-litigating a settled decision.

Store failed experiments in a format-fixed doc, newest first, keyed by hypothesis plus an evidence location — a `file:line`, eval path, PR number, or `learning.db` topic/key, never a bare claim. `docs/what-didnt-work.md` is that registry: PR #747 shipped it with a six-field format (date, experiment, expectation, what happened, evidence, decision) and seeded it from three real program refutations. No schema, no blocking gate — the doc is canonical, queried by grep/Read before re-running an experiment, and surfaced through `CONTRIBUTING.md` and the `retro` subcommand.

**OPEN: memory needs a verify step.** Hypothesis: a learned pattern earns graduation and consultation only after an executed check confirms it; recurrence alone can entrench a wrong guess, because the same misroute recorded three times reads as a pattern. Recurrence screens candidates (Triple-Validation, above); only an executed check confirms one. Validation: a `verified` flag on `hooks/retro-graduation-gate.py` (follow-up to PR #766); measure the precision delta between verified and recurrence-only graduations.

**Test:** Did this experiment fail, weaken, or get reverted? Record it in the registry with an evidence location before the next session re-runs it.

---

## Recursive Measurement

The measurement system that catches routing misses must itself be measured. If negative results from a program don't land in the registry built during that program, the learning system failed — measure at program scale, not just per session.

The blog-learnings program is its own test case. Early PRs shipped the telemetry envelope and routing-outcome capture; later PRs had to appear in that measurement. PR #747's registry was seeded with real negatives from the program itself — two refuted recommendations plus the post-merge-sync gotcha. Closure runs end to end: `hooks/routing-decision-recorder.py` → `hooks/routing-outcome-finalizer.py` → `scripts/learning-db.py route-health`, each with a visible correctness metric.

**Test:** Did this program's own misses and dead ends get captured by the tooling it built? If not, the tooling is unproven.

---

## Operational Gotchas & Recovery

Three failure modes need three detectors. **Loud failures** raise errors or exceptions — caught by tool error flags and `hooks/error-learner.py` classification. **Silent failures** succeed locally but hand the user a wrong answer — caught only by user reaction, where `hooks/routing-outcome-finalizer.py` runs high-precision rejection detection to avoid false positives. **Misroutes** pick the wrong agent for the right problem. Silent failure is the central enemy: it leaves no error to grep, so route-health tracks the outcome basis and silent-success share explicitly (PR #743). Recognizing which mode you face decides how to recover.

**Routing misclassification.** Wrong agent selected. Signal: unexpected agent in routing banner, or output mismatched to domain. Recovery: re-invoke with explicit domain context.

**Hook deadlock.** Hook points to nonexistent file. Every tool call returns exit 2. Recovery: check `~/.claude/settings.json`, verify `.py` file exists.

**Merged is not deployed.** A `git pull` merges code but does not make freshly-merged hooks live. The post-merge hook is deliberately no-clobber (commit 18e6d03c): it adds new items but never overwrites existing `~/.claude` hooks. Signal: merged telemetry or hook changes stay inert (e.g., zero new rows) until synced. Recovery: after merging hook changes mid-session, run `hooks/sync-to-user-claude.py` or restart the session before expecting live behavior.

**Pipeline stall.** Phase gate blocks on missing/malformed prerequisite artifact. Signal: same phase reruns without advancing. Recovery: check/fix the expected artifact file.

**Learning compounding.** Misroute recorded in learning.db reinforces wrong routing in future sessions. Signal: same misroute recurs across sessions. Recovery: query and delete/reweight incorrect entries via `scripts/learning-db.py`.

**Stale INDEX files.** New agent/skill added without regenerating INDEX. Router can't find it. Recovery: run `scripts/generate-agent-index.py` and `scripts/generate-skill-index.py`.
