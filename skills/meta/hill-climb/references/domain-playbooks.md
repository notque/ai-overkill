# Domain playbooks

Pre-filled SPEC blocks for the domains this loop meets most. Load in Phase 1 when
the request names a domain. Copy the block, replace the bracketed values with the
project's real paths and numbers, then run Phase 2 unchanged.

A playbook fills the spec; it never replaces the baseline. Every block still has
to survive the Phase 2 variance check on this machine.

Bench harnesses referenced below (`scripts/bench-frames.mjs`, `scripts/bench-http.py`)
print one number per run to stdout. Read `--help` before first use; if a flag here
does not match the script, the script wins.

---

## Game frame rate

| Field | Content |
|---|---|
| METRIC | **p1-low FPS** (1st-percentile frame rate), higher is better. Mean FPS hides stutter: a run that holds 120 FPS and drops six frames to 12 FPS still averages ~117, and the player feels only the drop. Equivalent framing: p99 frame time in ms, lower is better. |
| MEASURE | `node scripts/bench-frames.mjs --url http://127.0.0.1:<port>/<scene> --seconds 20 --metric p1-low` |
| FIXTURE | One scene, one scripted input trace, fixed entity count, fixed seed, fixed viewport and device-pixel-ratio, same browser build. Prove it: checksum the input trace and the scene file; record the seed and the resolution in the ledger. Discard the first run — shader and texture warm-up is not steady state. |
| FLOOR | Game boots, the scripted trace completes without an uncaught exception, and end-of-trace game state matches the baseline run (score, entity count, seed-derived positions). |
| Typical hot spots | Per-frame allocation driving GC pauses; draw calls not batched (no sprite atlas, no `InstancedMesh`); physics bodies active off-screen; per-frame `getBoundingClientRect` or layout reads; particle counts scaling with no pool. |
| Paired agent/skill | `phaser-gamedev` (2D), `threejs-builder` (3D), `performance-optimization-engineer` (browser runtime judgment). |

---

## HTTP API latency

| Field | Content |
|---|---|
| METRIC | **p99 response latency in ms**, lower is better. Mean latency hides the tail — the tail is what pages, retries, and times out. Track p50 alongside as an unaccepted observation, but climb on p99. |
| MEASURE | `python3 scripts/bench-http.py --url http://127.0.0.1:<port>/<route> --requests 2000 --concurrency <fixed> --metric p99` |
| FIXTURE | Fixed request corpus (same bodies, same auth, same order or same seed), seeded database restored from a dump with a recorded checksum, fixed concurrency, warmed connection pool, no external network in the measured path — stub or record third-party calls. |
| FLOOR | Contract and integration tests green; every benched request returns its baseline status code and response body shape. A latency win that changes a response is not a win. |
| Typical hot spots | N+1 queries; missing index on the filter column; JSON serialization of over-fetched rows; synchronous third-party calls inside the request; per-request connection setup; unbounded response size. |
| Paired agent/skill | `nodejs-api-engineer`, `database-engineer` (query and index work), `python-general-engineer` / `golang-general-engineer` by stack. |

---

## CI wall-clock

| Field | Content |
|---|---|
| METRIC | **Critical-path wall-clock in seconds**, lower is better — first job start to last job finish. The sum of job durations is the wrong number: it counts parallel work twice and rewards nothing a developer waits for. |
| MEASURE | `gh run view <run-id> --json jobs --jq '[.jobs[].completedAt] \| max' ` against the run's `startedAt`; median over the last N runs of the same workflow on the same runner class. |
| FIXTURE | Same workflow file, same commit range shape, same runner class (`ubuntu-latest` vs a larger runner are different fixtures), same cache state — declare cold or warm and keep it. Prove it: record runner label and cache-hit lines from the log. |
| FLOOR | The workflow still runs every job it ran at baseline, with the same test count and the same required checks. Deleting or skipping a job is a guardrail crossing, not an optimization. |
| Typical hot spots | Serial `needs:` edges that carry no real dependency; cache miss on every run (wrong key); full-history `fetch-depth: 0` clones; dependency install repeated per job; a single long job nobody split. |
| Paired agent/skill | `pr-workflow` (CI policy), `testing-automation-engineer` (job splitting), `kubernetes-helm-engineer` for self-hosted runner sizing. |

---

## Test-suite runtime

| Field | Content |
|---|---|
| METRIC | **Wall-clock seconds for the full suite**, lower is better, measured at the parallelism developers actually use. Per-test mean hides the one 90-second fixture that dominates. |
| MEASURE | `pytest -p no:randomly -q --durations=25` timed end to end, or `vitest run` / `go test ./...` — wrapped so the run prints one number. Median of N ≥ 10; wall-clock is noisy. |
| FIXTURE | Same test selection (no `-k`, no new markers), same worker count, same database or container state, same seed for randomized ordering. Prove it: record the collected-test count and assert it is unchanged every iteration. |
| FLOOR | Same number of tests collected, all passing, coverage not below baseline. Speedups that come from collecting fewer tests are the classic false win. |
| Typical hot spots | Session fixtures rebuilt per test; real `sleep` instead of condition-based waiting; network or container startup inside tests; no parallelism (`-n auto`, `--pool=threads`); import-time work in test modules. |
| Paired agent/skill | `testing-automation-engineer`, `condition-based-waiting` (sleep removal), `vitest-runner`, `python-quality-gate`. |

---

## Bundle size

| Field | Content |
|---|---|
| METRIC | **Compressed transfer bytes of the initial route**, lower is better — brotli, or gzip if that is what the CDN serves. Raw byte count is the wrong number: it misprices duplicated strings, and total `dist/` size is the wrong scope when only the entry chunk blocks paint. |
| MEASURE | `<build command> && brotli -c dist/assets/index-*.js \| wc -c` — deterministic, no sampling needed, but confirm the build is reproducible by running it twice. |
| FIXTURE | Pinned lockfile, pinned bundler version, same build mode and env vars, same target list. Prove it: checksum the lockfile; if two consecutive builds differ in bytes, fix the build before climbing. |
| FLOOR | The app builds, the route renders, and the e2e smoke path passes. Dropping a polyfill or a locale is a behavior change, not a size win, unless the user accepts the dropped support. |
| Typical hot spots | A date, icon, or lodash library imported whole; duplicate versions of one dependency; moment/luxon-style locale bundles; source maps or dev-only code shipped; no route-level code splitting. |
| Paired agent/skill | `performance-optimization-engineer`, `typescript-frontend-engineer`. |

---

## Memory footprint

| Field | Content |
|---|---|
| METRIC | **Peak RSS in MB under a fixed workload**, lower is better. Steady-state RSS is a different metric and answers a different question; pick one. For leak hunting the metric is RSS slope across repeated identical cycles, and the target is a flat line. |
| MEASURE | `memray run -o out.bin bench.py && memray stats out.bin` for Python; `/usr/bin/time -v <cmd>` for peak RSS of any process; `mcp__chrome-devtools__take_heapsnapshot` for browser heap. |
| FIXTURE | Same workload size, same concurrency, same allocator and runtime version, same GC settings. Prove it: record the input row count and the runtime version; RSS is meaningless across a runtime upgrade. |
| FLOOR | Full functional suite green, and no new latency or throughput regression beyond tolerance — memory is usually traded against speed, so name the speed bound as a floor condition. |
| Typical hot spots | Whole result set loaded instead of streamed; unbounded cache or memo dict; retained listeners and closures; large intermediate copies in a transform chain; per-object overhead where a compact array would do. |
| Paired agent/skill | `python-general-engineer`, `golang-general-engineer`, `database-engineer` for streaming query patterns. |

---

## LLM token cost per task

| Field | Content |
|---|---|
| METRIC | **Median total tokens per completed task** across a fixed request corpus, lower is better — input plus output, weighted by price if models differ. Tokens per call is the wrong number: a change that halves per-call size and doubles the call count wins on the wrong axis. |
| MEASURE | Replay a pinned request corpus, sum per-call token counts, print the median across requests. Attribute by component: system prompt, injected context, tool results, history. |
| FIXTURE | Frozen request corpus (n ≥ 30) with a recorded checksum, pinned model id, pinned temperature/seed where the API offers one, same tool set. Prove it: token counts vary run to run, so treat this as a sampled metric and take the baseline spread seriously. |
| FLOOR | Task success rate on the corpus does not drop. Cheaper wrong answers are not an improvement — the floor is a scored eval, not a smoke test. |
| Typical hot spots | Unbounded tool output pasted into context; a manifest duplicated in the system prompt and the harness listing; reference files loaded when the branch does not need them; full conversation history resent; retries on malformed output. |
| Paired agent/skill | `skill-eval` (corpus scoring), `toolkit-governance-engineer` (manifest and reference trimming). |

---

## Game design quality (with `game-design`)

`game-design`'s `references/autonomous-improvement.md` is already half this loop:
the 61 capability packets are a profiler for player experience, and the published
**Fix now** class is a queue of safe, reversible, scoped candidates. What it lacks
is a number: it stops when the queue empties, not when a metric hits target, and
it has no accept/revert rule. Bolt hill-climb on for that half.

| hill-climb phase | Source |
|---|---|
| PROFILE | The capability sweep. Each finding is a written hypothesis with evidence, player moment, severity, and smallest viable change — exactly the Phase 3 shape. |
| ITERATE | The Fix-now queue, in priority order. One item per iteration; Fix-next, Decision-required, and Research-required items are not iteration candidates. |
| MEASURE | Supplied here. Pick one proxy below and hold it for the whole loop. |
| STOP | Supplied here: target hit, budget exhausted, or plateau at K — not queue exhaustion alone. |

| Field | Content |
|---|---|
| METRIC | One packet-defined proxy, not a vibe. Counting metrics (lower is better): friction-register count at or above a fixed severity (packet 19), flow-audit finding count (17), failure-loop repair backlog (12). Coverage metrics (higher is better): goal density per session minute against the packet-21 map, KPI coverage percentage (26), FTUE beat completion rate on a playtest cohort (20). Rubric metrics are allowed under the contract in the next section. |
| MEASURE | For counting and coverage metrics, re-run the single owning packet against the current build and print the count — the same packet, the same rubric text, the same scope, every iteration. For FTUE completion, the number comes from instrumentation over a fixed cohort, not from a re-read of the code. |
| FIXTURE | Pinned build commit, pinned player path and segment, pinned packet scope (which capabilities count toward the metric), and pinned packet text. A sweep that widens mid-loop lowers the count for free. Prove it: record the packet IDs and the build SHA in the ledger. |
| FLOOR | Game builds and the affected player path completes; the harm guard the autonomous-improvement cycle defines for that change stays green (no confusion, abandonment, spend pressure, accessibility regression, or social-abuse surface introduced); the retention safety checks still pass. |
| Typical hot spots | Dead steps before the first meaningful action; unclear goal or reward copy at a decision point; unrecoverable failure states; goal-density gaps mid-session; instrumentation that never measured player understanding. |
| Paired agent/skill | `game-design` (owns the sweep and the queue), `phaser-gamedev` / `threejs-builder` (implementation), `joy-check` (framing of player-facing copy). |

Order of operations: run the autonomous-improvement cycle through step 3 first,
so a real queue exists, then enter hill-climb at Phase 1 with the metric chosen
from that queue's own findings. Do not invent a design metric before the sweep.

---

## Rubric metrics

The boundary is not "design work cannot be hill-climbed." It is: **no frozen,
independently-gradeable rubric, no hill climb.** With one, a judgment metric is a
legitimate METRIC — `objective-loop` already carries this contract for its
`rubric` criterion type, and this loop mirrors it.

| Guard | Rule |
|---|---|
| Frozen at SPEC | The rubric text is written in Phase 1 and copied verbatim into the ledger. Changing one word mid-loop ends the run and restarts the baseline — an edited rubric is an edited fixture. |
| Fresh-context grading | A rubric score is graded by a sub-agent that did not author the change, with no view of the hypothesis or the diff rationale, citing evidence for the score. Self-grading is the failure mode that makes rubric loops manufacture progress; a worker's own pass claim is never a score. |
| Wider accept threshold | Grader variance exceeds command-metric variance. Baseline with N ≥ 5 independent gradings of the unchanged artifact, set the variance tolerance from that spread, and accept only on a delta clearly beyond it. A one-point move on a ten-point rubric is usually noise. |
| Same evidence every time | The grader sees the same artifact scope, the same prompt, and the same rubric each iteration. Anything else compares two different measurements. |
| Ranking preference | Prefer an exit code over a fresh-context grader, and a fresh-context grader over self-critique. Use a rubric only where no mechanical check exists. |

Fitting rubric METRICs: player-comprehension score on a fixed FTUE recording,
documentation-clarity score on a fixed page set, review-quality score against a
frozen defect list, answer-quality score across a frozen eval corpus
(`skill-eval`, `agent-evaluation` — there the corpus is the FIXTURE).

## Not hill-climbable

What stays outside is narrower than "taste" and sharper than "design": work where
no rubric can be frozen because the goal itself is the thing being decided.
One-shot creative direction. Art style. Narrative voice. The first choice of what
the game is. Pointing a measurement loop at these does not measure them — it
invents a proxy, optimizes the proxy, and hands back a confident false answer with
a ledger attached, which is worse than no answer.

The tell: you cannot write the rubric without first making the creative decision
the rubric is supposed to judge.

| Request | Right destination |
|---|---|
| "What should this look like?", art style, moodboard | `design`, `distinctive-frontend-design`, `game-design` emotion packets |
| "Is the voice right?", narrative tone, framing | `joy-check`, `voice-validator`, `multi-persona-critique` |
| "What game should this be?", core creative direction | `game-design`, `planning` |
| "Is this the right architecture?" | `planning`, `adr-consultation` |

Two things that look outside and are not. A taste question often hides a
measurable one: "the game feels bad" is frequently p1-low FPS or input latency —
confirm the number with the user, then climb it. And a judgment question with a
frozen rubric and a fresh grader is inside, under the contract above.
