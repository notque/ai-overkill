# Rejected shared writing simplification

The candidate in PR #959 is rejected. Its token reduction passed the frozen efficiency gate, but two holdout cases regressed under the required zero per-case utility regression rule. The branch retains this negative evidence; the source change must remain unmerged.

| Measurement | Result |
| --- | --- |
| Workers | 18 cases × 5 repeats × 2 arms = 180 valid responses |
| Blind judgments accepted | 360, with five disputed checks independently adjudicated before arm unmasking |
| Median input + output | 13,631.5 baseline → 13,422.5 candidate |
| Saving | 209 tokens / 1.533%; target ≥1%, absolute saving >11 tokens |
| Holdout04 mean utility | 1.0000 → 0.9333 |
| Holdout05 mean utility | 0.8000 → 0.6667 |
| Critical violations | Zero in both arms |
| Shared response contract | All 180 exact JSON responses, at most 180 answer words; maximum 126 |

This measures output interpretation and writing with the full original versus candidate base instructions. It provides no autonomous execution or compliance claim. The model was `gpt-6-astra`, low reasoning, with the same common contract in both arms. The generic routing assessor's 5%/300-run policy was never substituted for this trial's frozen 1%/180-run policy.

## Evidence and replay

`evidence.tar.gz` contains 2,364 byte-preserved files: both instruction sources, common contract, protocol, corpus and rubrics, frozen harnesses, all 180 worker records and raw streams, both complete attempted judge campaigns including three timeouts, calibration (including an ineligible first calibration with labeled IDs), the single recovery attempt, assembled evidence with origin hashes, approval records, locked blind adjudications, final and earlier incomplete reports, and analysis scripts. `ARTIFACT-SHA256SUMS` identifies every archived file. No failed attempt or unknown usage was dropped.

Run from the repository root with Python 3.12 or later:

```sh
(cd docs/evaluations/base-writing-2026-09-04 && sha256sum -c SHA256SUMS)
python3 docs/evaluations/base-writing-2026-09-04/reproduce.py
```

The replay extracts to a temporary directory, checks every artifact hash, then runs the frozen offline interpreter against the archive. Historical absolute paths are translated only at file access; archived bytes and hashes remain unchanged. It verifies the raw response/judge records, exact calibration, recovery origins, adjudication lock, utility and token calculations, and requires an exact match with `RECOVERY-REPORT.json`. It makes no model calls. The recorded interpreter is trusted executable code, like the repository's other analysis tools.

## Disclosed recovery amendment

The first judging campaign had 70 valid batches and two timeouts. A fresh complete campaign had 71 valid batches and one timeout. Before arm outcomes were read, an independent reviewer approved one post-launch transport-only recovery of that sole latest timeout, with identical packets, pass, model, schema, and 300-second timeout. The recovery succeeded. All 71 valid latest batches were retained unchanged; none of the first campaign's votes were used. This is an explicit infrastructure amendment, not an untouched preregistered campaign. The original incomplete reports remain archived.

The five semantic disagreements were independently adjudicated using only anonymous packets, frozen rubrics and both votes. The decisions were hash-locked before arm mapping. Undisputed scores remained unchanged; none of the five disputes concerned critical violations. Both regressions persisted in the resulting complete assessment.

## Experiment spend

Known usage totals **4,587,095 input tokens**, including **3,620,992 cached input tokens**, and **160,567 output tokens**: **4,747,662 input + output tokens**. Cached input is a subset, not an additional charge in this total. All generation, calibration, failed campaigns and the recovery are counted. Three timed-out attempts have unknown additional usage. Coordinating-agent overhead is unavailable and is not asserted to be zero.
