<!-- pairs_with: do, quality-loop -->

# Lazy-Completion Detector

A check the orchestrator runs against an agent's "done" claim before accepting it. Scope: the **agentic-laziness** failure mode ONLY.

**Terminology:** "workflow" is canonical; "pipeline" is the legacy alias for the same concept.

## Scope (read first)

This file fills ONE gap: laziness — an agent stops at partial progress and declares done. The other two agentic failure modes are already covered elsewhere; this file does NOT re-cover them:

- **Goal drift** → `skills/meta/do/references/quality-loop.md` PHASE 5 (INTENT VERIFY): adversarial check that the diff matches the original request.
- **Self-preferential bias** → quality-loop PHASE 7 (FIX): use independent context when a specific blind spot warrants it; fresh-agent fixing is not mandatory.

Do not duplicate those controls here.

## The Laziness Failure

An agent reports success after partial work: "fixed 20 of 50 items," then declares done. Tests on the 20 pass, so PHASE 3 stays green and the gap survives.

## The Check

After an agent returns and before declaring the task done, compare **claimed scope** against **objective scope**:

| Step | Action |
|---|---|
| 1. Extract objective count | From the request: how many items/files/cases were in scope? ("all 50 lint errors", "every endpoint") |
| 2. Extract claimed count | From the agent's report and diff: how many did it actually touch? |
| 3. Compare | claimed < objective → INCOMPLETE, not done |
| 4. Re-dispatch | Fix: send a fresh agent the REMAINDER (objective minus claimed) with the same skill stack; re-run the check until claimed == objective |

Reject the early false-positive "done" at evaluation time. A passing test on a subset is not completion of the whole.

## When to Escalate

- Objective scope is enumerable (a count, a file list, "all X") and the claim covers less → re-dispatch the remainder.
- Objective scope is open-ended (no countable target) → fall back to quality-loop PHASE 5 intent-verify; this detector does not apply.

## Wiring

Run at `/do` Phase 4 EXECUTE evaluation, after an agent returns, before "done." Inside the quality-loop, run alongside PHASE 8 RETEST.
