# Independent philosophy V1 verification — 2026-09-04

Verified the final REJECT aggregation without model calls or changes to experiment artifacts.

- The current PR956 raw-integrity assessor accepts all 300 routing records and their matched judge manifests, batch prompts, raw streams, final messages, scores and usage. There are zero failed routing records and 600 original judgments, exactly two per packet.
- The locked adjudication file is named `adjudications.json` in the source directory. Its SHA256 is `37da040d59f803def3c2175d056a336744e357e2f00e3307c59a5baf1320d424`. Its rule and blind-input hashes match the preserved files.
- Recomputed all scores directly from original votes. Exactly nine packets contain one disputed check each. Applied only those nine decisions; checked that every undisputed check retains its original agreed score. The adjudication's copied original judgments match the actual votes.
- Independently recomputed all 60 case/arm means, each from exactly five runs. Every saved packet utility and case mean matches. Eight cases regress: dev01, dev09, dev11, dev20, hold02, hold07, hold09 and hold10.
- Recomputed all token metrics from validated worker records. Median input plus output tokens fall from 21,866 to 14,037: a 35.804445% reduction in medians, or 35.8% rounded. The median paired saving is 7,834.5 tokens. These are different statistics. Cached input remains included in input tokens; this is not a billed-cost or production-savings claim.
- `VERDICT.json` correctly records REJECT, no unresolved disputes and no production authorization. Token savings do not offset the per-case quality regressions.

This verifies arithmetic, evidence linkage and disputed-only application. It does not independently rejudge the semantic adjudication decisions or establish live-agent compliance.

Reproduction script: `verify.py`. From the repository root, extract the archives as shown in [the evidence README](README.md), preserving its `replay_dir` variable, then run:

```bash
python3 -B docs/evaluations/philosophy-2026-09-04/verify.py --experiment "$replay_dir/experiment" --workers "$replay_dir/workers" --judges "$replay_dir/judges" --verifier "$replay_dir/verifier"
```

The experiment directory must include `adjudication-rule.md`, `disputed-blind.json`, `adjudications.json`, `adjudicated-scores.json`, `VERDICT.json` and `judge-map.json`. No paid calls occur. The script fails if recorded aggregates, unchanged scores, usage, coverage or integrity checks differ.

Assessor source hashes used for this verification:

- `assess.py`: `d35ad8fbf45d1a7e4ac087f3f5cbb117491f26bf2270d2312324cf8c768d829f`
- `judge.py`: `01da7fd984a84e71c08f4b3a5c173d666b73fe6cc67b2b78c2f9fef964fc6666`
- `runner.py`: `f2fa499b11d4f641c6603762c8870520b48f2abc0c09f1d97f9ba39d6a5dedbc`

Publication note: the independent script was formatted to repository standards and its metric-loop variable bound explicitly as a default argument. The published script was rerun against the extracted archives; it does not change adjudication or scoring requirements. Original audit source is preserved in `final-evidence.tar.gz`.
