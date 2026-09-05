<!-- pairs_with: do, workflow -->

# Workflow Patterns Catalog

Canonical catalog the orchestrator loads to decide whether to escalate to a multi-agent workflow, and which named pattern fits. Navigation only — each row points to the machinery that already implements it. Do not re-spec mechanics here.

**Terminology:** "workflow" is the canonical umbrella term for a structured multi-phase, multi-agent flow. "pipeline" is the retained legacy alias for the same concept — kept for back-compat (routing keys, JSON fields, manifest sections, hook strings still use it). Use "workflow" in new prose; do not rename code identifiers.

## When NOT to Use a Workflow (cost gate)

Ask first: **does this really need more compute?** A workflow spends N agents and review passes. Most requests do not earn it.

| Skip the workflow when | Do instead |
|---|---|
| Single file, single concern, mechanical edit | `quick` — one agent, direct |
| One agent+skill satisfies the request | direct dispatch (/do Phase 4 default) |
| Lookup, status check, count, single rename | `thinking:fast`, direct agent |
| No independent subtasks and no adversarial need | direct dispatch |

Escalate to a workflow only when the request has independent subtasks, needs orthogonal verification, or names "comprehensive / thorough / adversarial / tournament."

## The 6 Composable Patterns

Each maps to existing HAVE machinery. Load the linked file for mechanics.

| Pattern | What it does | Existing home (load this) |
|---|---|---|
| Classify-and-act | Route by type up front; or classify-at-end (judge output, re-route) | `/do` Phase 1 CLASSIFY + Phase 4 evaluation; `skills/meta/do/references/lazy-completion-detector.md` for classify-at-end |
| Fan-out-and-synthesize | Independent agents in parallel, barrier, one synthesizer | `fan-out-workflow.js`; dispatch multiple Agent tools in one message (prose floor) |
| Adversarial verification | Executor builds, fresh skeptic refutes the result | quality-loop PHASE 5 (intent-verify) + PHASE 7 (focused fixes) |
| Generate-and-filter | Over-generate candidates, a gate keeps survivors | voice-writer HOOK-GATE / VARIETY-GATE; `right-size-review.py` tiering |
| Tournament | N agents attempt the SAME task; pairwise judges pick a winner per round | `tournament-workflow.md` |
| Loop-until-done | Repeat until a hard completion test passes | quality-loop PHASE 8 RETEST (after relevant fixes) + verification-before-completion as the completion bar; `/loop` for interval re-run |

## The 3 Failure Modes Workflows Fight

These are agentic-execution failures (a single agent declaring victory wrong). They are NOT the universal output failures in `skills/shared-patterns/llm-domain-failure-modes-base.md` (hallucination, overconfidence, generic template) — contrast, do not re-add.

| Failure mode | Symptom | Control + when to escalate |
|---|---|---|
| Agentic laziness | Stops at partial progress ("fixed 20 of 50"), declares done | `skills/meta/do/references/lazy-completion-detector.md` — scope-vs-objective check at evaluation; escalate to re-dispatch the remainder |
| Self-preferential bias | Agent reviews its own work, rates it good | quality-loop focused independent review when risk or a blind spot warrants it |
| Goal drift | Output answers a nearby question, not the asked one | quality-loop PHASE 5 intent-verify (already covered); escalate when the diff diverges from request |

## Repeatable Workflows: completion bar + /loop

- Completion bar — quality-loop PHASE 8 RETEST + verification-before-completion: the workflow loops until the objective is provably met, not until the agent feels done. (Upstream Claude Code ships a `/goal` command for this; not wired in this toolkit — use the quality-loop gate.)
- `/loop` — interval re-run (continuous triage, polling). Pair with the completion bar so each cycle has a provable stop test.

## Token-Budget Directive (optional)

Prepend a hard cap when cost matters: "use Nk tokens" (e.g. "use 10k tokens"). Caps total spend across the fan-out; agents prioritize against it. Distinct from /do's advisory `orchestration.token_budget` (soft, per-prompt).

## Untrusted-Source Triage: quarantine

When a workflow reads untrusted/public content, isolate the reader from privileged actions. See `quarantine-pattern.md`.

## Model-Routing Classifier

For mixed-difficulty batches, dispatch a classifier agent that researches each task, then routes it: scripts for deterministic work, harness-native low-risk readers (opus/low under Claude Code, terra/high under Codex CLI), and harness-native high-risk for synthesis. Cross-provider dispatch is manual-only. The canonical model-selection table in `/do` defines exceptions, escalation targets, and the start-low-escalate-on-miss discipline.
