# Hill-climb ledger

The ledger is the loop's memory and half its deliverable. Write it at Phase 2 and
append at every iteration. Entries are append-only: never edit a past entry.

Path: `.hillclimb/<slug>/ledger.md`. The slug is a short kebab-case name for the
metric and target, for example `ci-wallclock-under-6m` or `import-p99-500ms`.
Keep `.hillclimb/` unstaged unless the user asks for the ledger in the repo.

## Template

```markdown
# Hill climb: <slug>

| Field | Value |
|---|---|
| METRIC | p99 import latency, ms, lower is better |
| MEASURE | `python3 bench/import_p99.py --fixture fixtures/10k.jsonl` |
| TARGET | <= 500 |
| FLOOR | `pytest -q tests/importer` exits 0 |
| FIXTURE | `fixtures/10k.jsonl` sha256 3f9a... , seed 42, local runner |
| Variance tolerance | 18 ms (2x baseline spread) |
| Iteration budget | 8 |
| Plateau K | 3 |

## Baseline

| Samples | Median | Spread |
|---|---|---|
| 812, 798, 806, 821, 803, 809 | 806 ms | 23 ms |

Noise check: target improvement 306 ms > spread 23 ms. Proceed.

## Profile

py-spy record, 30s: `json.loads` in `parse_row` 41% of samples; `validate()`
regex recompiled per row, 22%.

## Iterations

### Iteration 1 — ACCEPTED

| Field | Value |
|---|---|
| Hypothesis | `validate()` recompiles its regex per row (22% of samples); hoisting to module scope should recover ~150 ms |
| Change | `importer/validate.py`: module-level `re.compile` |
| Median | 661 ms (spread 21 ms) |
| Delta vs baseline | -145 ms |
| Delta vs best | -145 ms |
| Floor | green (`pytest -q tests/importer`, exit 0) |
| Verdict | ACCEPTED — improvement 145 ms exceeds tolerance 18 ms |

### Iteration 2 — REVERTED

| Field | Value |
|---|---|
| Hypothesis | Batching writes 500 at a time cuts commit overhead |
| Change | `importer/sink.py`: batched commits |
| Median | 655 ms (spread 25 ms) |
| Delta vs best | -6 ms |
| Floor | green |
| Verdict | REVERTED — 6 ms is inside tolerance 18 ms; not distinguishable from noise |

## Stop

Condition: TARGET hit / budget exhausted / plateau / noisy harness / guardrail conflict.
Best value, accepted changes in order, remaining hot spots, next hypothesis.
```

## Field rules

| Field | Rule |
|---|---|
| Hypothesis | Written before the edit, never after. Names the cost, its share, and the expected recovery |
| Change | Files touched, one change per iteration. Bundled changes cannot be attributed |
| Median / spread | Same sample count and conditions as the baseline, every time |
| Delta vs best | The accept decision reads this one, not delta vs baseline |
| Floor | The command and its exit code, pasted. A claim is not a floor result |
| Verdict | ACCEPTED, REVERTED, or INCONCLUSIVE, with the number that decided it |

## Resume protocol

Resume from the ledger, never from conversation memory:

1. Read the header table — the spec is frozen there.
2. Read the last iteration entry; confirm the working tree matches its verdict
   (accepted changes present, reverted changes absent). `git status --short`.
3. Re-run MEASURE once and compare to the recorded best. A large mismatch means
   the tree or the fixture drifted — re-baseline rather than continue.
4. Continue at the next iteration number.

Negative results carry the ledger's value. A reverted iteration is recorded in
full: it is what stops the next person re-walking the same dead end.
