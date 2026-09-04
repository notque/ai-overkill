# Philosophy V2: rejected on the frozen response contract

**V2 was rejected.** All 400 worker records passed raw runtime verification, but only 375 met the frozen response contract. Twenty-five answers exceeded its 180-word limit: **21 of 200 candidate responses (10.5%) versus 4 of 200 baseline responses (2%)**, an observed increase of 8.5 percentage points. The overages ranged from 181 to 189 whitespace-separated words. The requirement was not waived, and no semantic judging of worker responses was performed.

This is a measured instruction-following failure under this experiment's contract. It does not establish preserved or lost philosophical meaning. The candidate remains exactly SHA256 `e8c33c22987ba0a3cbaa8cbe24314d3b5162a07c0bb2c7b8263b131868f671e3`; this evidence update does not change it or authorize promotion.

## Frozen decision

`inputs/contract.txt` required exactly one JSON object containing an `answer` string of at most 180 words. The protocol required all 400 workers to pass both raw verification and that response contract. The counter in `analyze.py` used `len(answer.split()) <= 180`, and `analysis-freeze.json` pinned its source before worker outputs. All answers otherwise had the required JSON shape. `VERDICT.json` preserves REJECT; no alternative count convention or threshold was substituted after results.

The corpus contained 30 development cases and 10 independently authored fresh cases, five repeats per arm. The candidate author did not inspect fresh task responses or semantic outcomes. Publishing byte-preserved archives does not confer permission to use fresh material for candidate tuning; keep original mappings, tasks and source documents out of subsequent blind judge inputs.

## Cost and limits

The preregistered cost statistic was the median of five per-repeat corpus medians, each formed from 40 input-plus-output totals. It fell from **21,859 to 14,301 tokens (34.576%)**. The 7,558-token saving exceeded the required 20% reduction and the 15-token noise threshold, but passing cost did not overcome the failed response-contract floor. This is not the pooled-median statistic used in the final V1 report.

Recorded CLI spend:

| Stage | Calls | Input plus output tokens |
|---|---:|---:|
| Workers | 400 | 7,236,407 |
| Calibration judges | 4 | 58,137 |
| Worker semantic judges | 0 | 0 |
| Total measured | 404 | **7,294,544** |

All recorded attempts have known usage; none were silently replaced. Cached input is already part of input and is not added twice. Authoring, orchestration and independent review outside these CLI records remain unmetered, not free. The sum is measured trial spend, not a complete project bill or proof of production savings. Model aliases do not identify an immutable server-side snapshot.

Calibration had six controls judged in two passes, yielding twelve exact judgments. This establishes the recorded calibration outcome only; worker meaning remains unmeasured. The published rejection needs no paid semantic judging to stand.

## Evidence and reproduction

- `workers.tar.gz`: all original worker prompts, raw events, final outputs, result records, assignments and digest-keyed frozen inputs.
- `calibration.tar.gz`: original four calibration calls, prompts, streams, output schemas, judgments and recorded usage.
- `experiment.tar.gz`: exact protocol, preregistration, response contract, counter and source freezes, arm/case inputs, original harness, private maps, rubrics, reports, amendments and final verdict. The separately prepared judging sources are preserved as unused preparation; they made no worker-semantic calls.
- `corpus.tar.gz`: byte-preserved original and fresh corpus material with original source checksums. Do not expose oracle or fresh material to candidate authors or model workers.
- `archive-index.json`: SHA256 and length of every archived member plus archive hashes. `SHA256SUMS` verifies published files.
- Top-level verdict, protocol, preregistration, freeze and reports are exact historical copies. Absolute source paths remain provenance keys; frozen bytes make reproduction independent of those machine paths.

From the repository root, without model calls:

```bash
(cd docs/evaluations/philosophy-v2-cap-2026-09-04 && sha256sum -c SHA256SUMS)
python3 -B docs/evaluations/philosophy-v2-cap-2026-09-04/verify.py
```

The verifier extracts hash-checked files into a temporary directory, checks original source freezes, validates all worker records against their frozen input store, independently checks raw final messages and usage, reproduces the cap counts, validates the twelve calibration judgments, and recalculates measured spend. It fails on mismatched coverage, source hashes, outputs or totals. It does not rejudge meaning or run submitted model code.

## Separate next comparison

A new preregistered V3 comparison keeps the candidate unchanged, removes the generic length scaffold, and evaluates retained meaning plus measured total tokens. It also changes the primary cost statistic to pooled per-run medians and stages development before fresh evaluation; it is a new protocol, not a rescue of V2. Development, fresh and pooled gates, plus a separately reviewed real-output-constraint experiment, must pass before any promotion. Those verdicts remain pending. V1's semantic rejection and V2's contract rejection stay intact; no merge is authorized by this package.
