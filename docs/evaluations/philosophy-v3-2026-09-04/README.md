# Philosophy V3: rejected

**The shorter document failed the meaning test.** One development case fell from a mean score of 1 to 2/3. All five candidate responses missed the required artifact inventory, counts and structured checkpoint; both blind judges agreed. The frozen rule allowed no per-case loss, so the 100 fresh workers were never started.

The unchanged V2 candidate has 1,127 body words, down from 5,951. When loaded for these interpretation tasks, median input-plus-output tokens fell from 21,751 to 14,190 (34.76%). That saving did not overcome the missing rule. There is no fresh or pooled 40-case result and no evidence of equivalent autonomous task performance.

## What was tested

V3 used 30 development cases, five repeats per arm and two blind judge passes. Six opaque calibration controls passed both times. One disputed check was resolved before arm reveal; agreed votes stayed unchanged. The lost artifact-contract check was not disputed.

V3 was a new protocol: it removed the generic length scaffold, used pooled per-run token medians, and gated fresh testing on development passing. Original rubric text and the V2 candidate stayed fixed. V1's meaning failure and V2's response-cap failure remain separate rejected results.

A separate six-task test checked real API, UI, bullet, sentence, release-note and form limits. All 60 outputs met their format constraints, and 120 blind semantic judgments showed no per-case regression or dispute. This test passed its own floor; it cannot override the meaning failure. The corpus author selected task classes before receiving aggregate V2 failure counts, but had no candidate text or responses. This prior-result exposure is a limitation, not perfect outcome blindness.

After reconnecting, the original corpus-author agent was unavailable. A fresh agent with no inherited conversation adjudicated the one masked development dispute. The copied rule permits independent adjudication; the protocol had named the corpus author. The substitution review explicitly records this deviation, after the resolution was locked and before comparative scoring. No competing adjudication was selected, and no rubric or floor changed.

## Recorded cost

| Comparison | CLI calls | Input plus output tokens |
|---|---:|---:|
| Meaning: workers, calibration and judges | 424 | 7,251,828 |
| Real output constraints: workers, calibration and judges | 92 | 1,554,696 |

All recorded CLI attempts have known usage. There were no recovery calls. Cached input is already included in input; it is not added twice. Native-agent authoring, adjudication, review and orchestration usage is unavailable, so these are measured CLI costs rather than a complete bill. Model aliases do not freeze the server-side model.

## Replay without model calls

From the repository root:

```bash
(cd docs/evaluations/philosophy-v3-2026-09-04 && sha256sum -c SHA256SUMS)
python3 -B docs/evaluations/philosophy-v3-2026-09-04/verify.py
```

The four archives preserve both complete campaign directories, split into worker and other experiment files. They include raw events, final answers, prompts, manifests, input stores, both original votes, masked packets, private mappings, frozen source, all reports, adjudication and resume receipts. Only Python caches are excluded. Keep private maps and candidate documents out of future blind judge inputs.

`archive-index.json` records every member's hash and length. The verifier safely extracts hash-checked files, checks both terminal freezes and all 126 preregistered source files, recounts all 516 CLI attempts, and replays calibration, raw worker verification, original votes, disputed-only adjudication and exact score/token calculations. Replays occur in a temporary copy; original records stay unchanged. They reproduce the archived reports without rejudging meaning or executing model-written code.

The two `FINAL-REPORT.json` copies are exact terminal records. Earlier progress estimates remain in the archives: the constraint campaign actually used 26 semantic judge batches, not the earlier estimate of 24. The final verdict is **REJECT**. No source change or promotion is authorized by this evidence.
