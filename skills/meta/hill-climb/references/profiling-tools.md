# Profiling tools by domain

Load in Phase 3. Locate the cost before changing anything; guessing at hot spots
is the dominant failure of optimization work.

## Python

| Goal | Command | Read |
|---|---|---|
| CPU, running process | `py-spy record -o prof.svg --pid <pid>` | Flame graph width = sample share |
| CPU, one run | `py-spy record -o prof.svg -- python3 bench.py` | Same, no code change needed |
| CPU, deterministic | `python3 -m cProfile -o out.prof bench.py` then `snakeviz out.prof` | `tottime` for self cost, `cumtime` for subtree |
| Wall-clock by call | `pyinstrument bench.py` | Tree by wall time, async-aware |
| Memory | `memray run -o out.bin bench.py` then `memray flamegraph out.bin` | Allocation sites, peak RSS |
| Memory, stdlib only | `tracemalloc` snapshots around the region | Deltas between snapshots |

Trap: `cProfile` adds per-call overhead that distorts many-small-calls code. Confirm
a `cProfile` finding with `py-spy` before acting on it.

## Go

| Goal | Command |
|---|---|
| CPU | `go test -bench=. -cpuprofile cpu.out` then `go tool pprof -http=: cpu.out` |
| Memory | `go test -bench=. -memprofile mem.out -benchmem` |
| Compare runs | `benchstat before.txt after.txt` — reports deltas with p-values |
| Live service | `go tool pprof http://127.0.0.1:6060/debug/pprof/profile?seconds=30` |

`benchstat` is the accept/revert oracle for Go: it reports whether a delta
survives variance. Prefer it over eyeballing two numbers.

## Browser runtime, frame rate, memory

In this harness use the Chrome DevTools MCP tools:

| Goal | Tool |
|---|---|
| Record a trace | `mcp__chrome-devtools__performance_start_trace` / `performance_stop_trace` |
| Explain a finding | `mcp__chrome-devtools__performance_analyze_insight` |
| Heap | `mcp__chrome-devtools__take_heapsnapshot` |
| Page-level score | `mcp__chrome-devtools__lighthouse_audit` |

Read long tasks, layout thrash (forced reflow), and script-evaluation share.
Frame-rate work reads the frame timeline, not the summary score. Pair with the
`performance-optimization-engineer` agent for Core Web Vitals domain judgment.

## Bundle size

| Bundler | Tool |
|---|---|
| webpack | `webpack-bundle-analyzer` |
| rollup / vite | `rollup-plugin-visualizer` |
| any, from source maps | `source-map-explorer dist/*.js` |

Measure the compressed transfer size, not the raw byte count — gzip and brotli
change which win is real.

## Test runtime

| Runner | Command |
|---|---|
| pytest | `pytest --durations=25` |
| vitest | `vitest run --reporter=verbose` |
| go | `go test -json ./... ` and sort by elapsed |

Look for fixture setup repeated per test, real sleeps, network calls, and
missing parallelism before micro-optimizing test bodies.

## CI wall-clock

Pull per-job and per-step durations from the CI API (`gh run view <id> --json jobs`).
The metric is the critical path through the job graph, not the sum of job times.
Common wins: cache restore, job splitting, dropping serial dependencies,
right-sizing runners. Confirm each against the graph before claiming it.

## Token cost

Attribute tokens per prompt component: system prompt, injected context, tool
results, conversation history. Measure with per-call token counts across a fixed
request corpus. The usual costs are unbounded tool output, duplicated manifests,
and reference files loaded when not needed.

## Universal traps

| Trap | Check |
|---|---|
| Profiling a warm-up run | Discard the first run; measure steady state, or measure cold deliberately |
| Profiler overhead dominates | Compare profiled and unprofiled wall time; large gaps invalidate the shares |
| Optimizing a 3% hot spot | Amdahl's law caps the win at that share; go to the top of the profile |
| Wrong workload profiled | Confirm the fixture used for profiling is the FIXTURE from the spec |
