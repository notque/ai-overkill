---
name: hill-climb
description: |
  Metric-driven optimization loop: baseline a number, profile the cost, then
  accept or revert one change per iteration on measured evidence until the
  target is hit or the curve plateaus. Use when the user says "make this
  faster", "reduce memory", "speed up CI", "get p99 under 200ms", "improve the
  frame rate", "cut the bundle size", "make the tests run quicker", or "reduce
  token cost". Requires one number, a repeatable command that prints it, and a
  fixed dataset; the loop stops and says so when the harness is too noisy to
  measure the improvement being chased.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Skill
  - Agent
routing:
  not_for: "one-shot micro-optimizations with no measurement (just make the edit), work with no measurable metric or no repeatable measure command, correctness bugs and crashes (debugging skills), boolean done-criteria loops with no continuous metric (objective-loop), capacity planning and infrastructure sizing"
  triggers:
    - "make this faster"
    - "speed this up"
    - "reduce memory usage"
    - "speed up CI"
    - "make the build faster"
    - "make the tests run quicker"
    - "get p99 under"
    - "reduce latency"
    - "improve the frame rate"
    - "cut the bundle size"
    - "reduce token cost"
    - "optimize until it hits"
    - "profile and optimize"
    - "performance regression"
    - "hill climb on this metric"
  complexity: Complex
  category: meta
  pairs_with:
    - objective-loop
    - verification-before-completion
    - test-driven-development
    - performance-optimization-engineer
    - phaser-gamedev
    - threejs-builder
    - game-design
    - nodejs-api-engineer
    - testing-automation-engineer
---

# Hill Climb

The toolkit's metric-driven optimization loop. One number moves; everything else
stays fixed. Each iteration states one hypothesis, makes one change, runs the
correctness floor, re-measures, and either accepts the change or reverts it. The
ledger of what was tried and what failed ships with the code.

Sibling to `objective-loop`: that loop verifies boolean criteria and reschedules;
this loop optimizes a continuous metric against variance. Route here whenever the
goal is a number moving in a direction.

## Phase 1: SPEC

Fill these fields from the request. Interview only for what is missing.

| Field | Meaning | Required | Default |
|---|---|---|---|
| METRIC | One number, with units and direction (lower or higher is better) | yes | — |
| MEASURE | A deterministic command that prints that number, repeatable | yes | — |
| TARGET | The value that ends the loop | yes | — |
| FLOOR | Correctness gate command(s) that must exit 0 every iteration | yes | — |
| FIXTURE | Dataset, workload, or input identity, pinned to a commit or checksum | yes | — |
| Variance tolerance | Spread below which a delta means nothing | no | 2x the baseline spread |
| Iteration budget | Iterations before a forced stop | no | 8 |
| Plateau threshold K | Consecutive non-improving iterations that stop the loop | no | 3 |

Rules:

- One METRIC per loop. Two numbers with a trade-off need one of them promoted to the FLOOR (for example: "p99 latency drops, memory stays under 500 MB").
- MEASURE prints the number and nothing that requires interpretation. Wrap noisy tools in a script that emits one value.
- A hill climb against a varying dataset measures nothing. Pin FIXTURE before Phase 2 — same input rows, same seed, same machine class, same warm/cold state.
- FLOOR is executed, not asserted. Name the command.
- A domain playbook fills this table fast: `references/domain-playbooks.md` carries pre-filled blocks for frame rate, API latency, CI time, test runtime, bundle size, memory, token cost, and game-design quality.
- A judgment score can be the METRIC only under the frozen-rubric contract in that reference: rubric frozen at SPEC time, graded in a fresh context by an agent that did not author the change, wider accept threshold. Without a freezable rubric the request is not hill-climbable — that reference names where it goes instead.

Gate: all required fields hold concrete values. Proceed to Phase 2.

## Phase 2: BASELINE

Run MEASURE N times (N ≥ 5, N ≥ 10 for wall-clock metrics) before changing any
code. Record every sample, the median, and the spread (max − min, or p95 − p5).

| Condition | Action |
|---|---|
| Spread < target improvement | Proceed. Set the variance tolerance from the spread. |
| Spread ≥ target improvement | **Stop.** Report that the harness is too noisy to hill-climb on. |

A noisy-harness stop is a correct outcome, not a failure. Report the measured
spread, name the likely noise sources (shared CI runners, thermal throttling,
network calls, unpinned data, garbage-collection timing), and offer to stabilize
the harness first. Never proceed by averaging harder and hoping.

Gate: baseline median and spread written to the ledger. Proceed to Phase 3.

## Phase 3: PROFILE

Locate the cost before changing anything. Guessing at hot spots is the dominant
failure mode of optimization work.

| Domain | Tooling |
|---|---|
| Python CPU | `py-spy record`, `cProfile` + `snakeviz`, `pyinstrument` |
| Python memory | `memray`, `tracemalloc` |
| Go | `pprof` (`-cpuprofile`, `-memprofile`), `go test -bench -benchmem`, `benchstat` |
| Browser runtime and frame rate | Chrome DevTools performance trace; in this harness `mcp__chrome-devtools__performance_start_trace`, `performance_stop_trace`, `performance_analyze_insight`, `take_heapsnapshot` |
| Bundle size | `webpack-bundle-analyzer`, `rollup-plugin-visualizer`, `source-map-explorer` |
| Test runtime | `pytest --durations=25`, `vitest --reporter=verbose`, `go test -json` timings |
| CI wall-clock | Per-job and per-step durations from the CI API; critical-path analysis across the job graph |
| Token cost | Per-call token counts by prompt component; context-size attribution |

Write one hypothesis before the edit, in this shape: *"X consumes N% of METRIC
because Y; doing Z should recover about M."* Hypothesis first, edit second.

Gate: profile output captured, one hypothesis written to the ledger. Proceed to Phase 4.

## Phase 4: ITERATE

Per iteration, in order:

1. State one hypothesis (from Phase 3, or re-profiled after the last accept).
2. Make one change. One change per iteration — bundled changes cannot be attributed.
3. Run FLOOR. Red floor ends the iteration: revert, log, next.
4. Run MEASURE the same N times as the baseline, same fixture, same conditions.
5. Compare the new median to the current best.

| Floor | Metric vs best | Action |
|---|---|---|
| Green | Improved beyond variance tolerance | Accept. New best. Log. |
| Green | Improved within variance tolerance | Revert. Noise, not a win. Log as inconclusive. |
| Green | Worse or unchanged | Revert. Log the negative result — it is the valuable part. |
| Red | Any | Revert. Log the floor failure. |

**Guardrails (hard rules).** Never move the number by moving the goalposts:

- Never edit, shrink, reseed, or re-sample the FIXTURE.
- Never relax, skip, mark-xfail, or delete a FLOOR test.
- Never shrink the workload, lower the iteration count, or cut the input size.
- Never change MEASURE mid-loop; a changed measure invalidates the baseline and restarts the loop.
- Never cache away work the metric is supposed to include, or move it outside the measured region, unless the user accepts that as the intended change.
- Never accept on a single sample.

Hitting a guardrail is a stop-and-report event, not a judgment call. If the only
visible path to TARGET crosses one, stop and put the conflict to the user.

Gate: iteration logged with accept/revert and evidence. Loop until a Phase 5 stop condition fires.

## Phase 5: LEDGER

`.hillclimb/<slug>/ledger.md` is append-only and written every iteration.
Entries are never edited retroactively. Template and field rules:
`references/ledger.md`.

Per iteration record: hypothesis, change summary (files touched), metric median
and spread, delta vs baseline, delta vs best, floor status, accepted or reverted,
and why.

The ledger ships with the code. It tells the next person what was tried and what
did not work, which is what stops the same dead end being re-walked. Keep
`.hillclimb/` unstaged unless the user asks for the ledger in the repo.

## Phase 6: STOP

| Condition | Report |
|---|---|
| TARGET hit | Baseline → final value, accepted changes in order with their deltas, floor green, ledger path |
| Iteration budget exhausted | Best achieved value, remaining gap to TARGET, next hypothesis in the queue |
| Plateau: K consecutive non-improving iterations | Best achieved value, the hot spots the profiler still shows, and what a next attempt would need |
| Noisy harness (Phase 2) | Measured spread, noise sources, harness-stabilization proposal |
| Guardrail conflict (Phase 4) | The guardrail, the change that would have crossed it, and the decision put to the user |

On plateau, name the shape of the next attempt honestly: a different algorithm,
a different data structure, an accepted architectural change, or "the remaining
cost is irreducible at this design." Do not silently keep grinding past K.

## Error Handling

| Error | Cause | Solution |
|---|---|---|
| MEASURE prints varying numbers for identical code | Unpinned fixture, shared machine, network in the measured path | Return to Phase 2; pin the fixture or stabilize the harness before iterating |
| FLOOR was already red at baseline | Pre-existing failure | Stop. Fix correctness first — a hill climb over a red floor accepts nothing |
| Metric improves but the floor flakes intermittently | Flaky test in FLOOR | Treat as red; stabilize or replace that gate. Never downgrade a flaky gate to make an accept stick |
| Large win from one change looks too good | Work was cached, skipped, or moved out of the measured region | Verify the workload still executes: assert output equality against the baseline run before accepting |
| Ledger missing on resume | `.hillclimb/` removed mid-loop | Re-run Phase 2 baseline; do not resume from memory |

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| Writing or resuming the ledger | `references/ledger.md` | Append-only template, slug rules, resume protocol |
| Choosing a profiler, or reading its output | `references/profiling-tools.md` | Per-domain commands, output reading, common traps |
| Phase 1 in a named domain — frame rate, API latency, CI time, test runtime, bundle size, memory, token cost, game-design quality | `references/domain-playbooks.md` | Pre-filled METRIC/MEASURE/FIXTURE/FLOOR blocks and typical hot spots |
| The metric is a judgment score, or the request may not be measurable at all | `references/domain-playbooks.md` | Frozen-rubric contract and the not-hill-climbable boundary |

## References

- `${CLAUDE_SKILL_DIR}/references/ledger.md` — ledger template and resume protocol
- `${CLAUDE_SKILL_DIR}/references/profiling-tools.md` — per-domain profiling commands and traps
- `${CLAUDE_SKILL_DIR}/references/domain-playbooks.md` — pre-filled SPEC blocks per domain, rubric-metric contract, not-hill-climbable boundary
