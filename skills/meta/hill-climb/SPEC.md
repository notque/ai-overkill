# SPEC: hill-climb

Maintainer contract. Not runtime context — load only when changing this skill.

## Purpose

Move one measured number to a target: baseline with variance, profile the cost,
then accept or revert one change per iteration on measured evidence, stopping on
target, budget, or plateau. The ledger of hypotheses and negative results is a
deliverable alongside the code.

## Scope

- Spec capture: METRIC, MEASURE, TARGET, FLOOR, FIXTURE, variance tolerance, iteration budget, plateau K.
- Baseline with N samples; noisy-harness stop when spread >= the improvement being chased.
- Profile-before-edit; per-domain tooling table; per-domain pre-filled SPEC playbooks.
- One-hypothesis-per-iteration accept/revert loop against variance tolerance and a green floor.
- Append-only ledger at `.hillclimb/<slug>/ledger.md`.
- Honest stop reports on plateau and budget exhaustion.

## Non-goals

- Boolean done-criteria loops with no continuous metric (`objective-loop`).
- Correctness bugs and crashes (debugging skills).
- Domain performance knowledge — Core Web Vitals thresholds and web tactics stay in `performance-optimization-engineer`; this skill carries methodology only.
- One-shot micro-optimizations with no measurement.
- Capacity planning and infrastructure sizing.

## Invariants

1. One METRIC per loop; competing numbers become FLOOR conditions.
2. FIXTURE is pinned before the baseline and never edited, reseeded, or resampled during the loop.
3. Baseline precedes any change; spread >= the target improvement stops the loop as a noisy harness — a correct outcome, not a failure.
4. Profile precedes edit; one written hypothesis precedes each change.
5. One change per iteration; bundled changes cannot be attributed.
6. Accept requires both a green FLOOR and an improvement beyond variance tolerance. Everything else reverts.
7. Guardrails are stop-and-report, not judgment calls: no fixture edits, no relaxed or deleted floor tests, no shrunk workload, no mid-loop MEASURE change, no single-sample accepts.
8. The ledger is append-only; entries are never edited retroactively; reverted iterations are recorded in full.
9. Resume reads the ledger, never conversation memory.
10. Plateau at K consecutive non-improving iterations stops the loop with a named next-attempt shape.
11. A rubric METRIC is frozen at SPEC time, recorded verbatim in the ledger, and graded in a fresh context by an agent that did not author the change; editing the rubric mid-loop ends the run.

## Dependencies

- `references/ledger.md` — ledger contract and resume protocol.
- `references/profiling-tools.md` — per-domain profiling commands.
- `references/domain-playbooks.md` — pre-filled SPEC blocks, rubric-metric contract, not-hill-climbable boundary.
- Optional harness: `mcp__chrome-devtools__performance_*` for browser metrics.
- Pairs: `objective-loop`, `verification-before-completion`, `test-driven-development`.

## Success criteria

- Routes on metric phrasing ("make this faster", "get p99 under X"); declines correctness bugs, unmeasurable requests, and boolean objective loops (`evals.json`).
- "Make the CI faster" produces filled METRIC/MEASURE/TARGET/FLOOR before any edit.
- A noisy harness stops the loop with the measured spread reported.
- Every accept in the ledger cites a floor exit code and a delta beyond tolerance.
