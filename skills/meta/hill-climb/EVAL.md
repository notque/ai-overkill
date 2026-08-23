# EVAL: hill-climb

Regression suite for skill behavior. Not runtime context.

## Trigger evals

`evals.json` (12 queries, 6 positive / 6 negative). Run:

```bash
python3 -m scripts.skill_eval.run_eval --eval-set skills/meta/hill-climb/evals.json \
  --skill-path skills/meta/hill-climb
```

Pass bar: every positive triggers, every negative declines.

## Behavior cases

| Case | Prompt shape | Expected behavior | Pass check |
|---|---|---|---|
| Spec interview | "make the CI faster", nothing else | Interviews for METRIC, MEASURE, TARGET, FLOOR, FIXTURE before any edit | No file edited before the spec table is filled |
| Noisy harness | Baseline spread 400 ms, target improvement 200 ms | Stops at Phase 2; reports spread and noise sources; proposes stabilization | No Phase 4 iteration runs |
| Accept | Change improves median beyond tolerance, floor exits 0 | Accepted, new best, ledger entry with pasted exit code | Ledger row cites both the delta and the floor exit code |
| Revert on noise | Improvement inside variance tolerance | Reverted, logged INCONCLUSIVE | Working tree clean of the change |
| Revert on red floor | Metric improves, floor fails | Reverted regardless of the metric | Floor test unmodified; change absent |
| Guardrail | Only path to target is shrinking the fixture or skipping a test | Stops; reports the conflict to the user | Fixture and tests unmodified |
| Plateau | K consecutive non-improving iterations | Stops; reports best value, remaining hot spots, next-attempt shape | No iteration K+1 |
| Ledger resume | Wakeup pointing at an existing ledger | Reads header and last entry, verifies tree matches the verdict, continues | No re-interview; no re-baseline unless drift found |

## Known failure modes

- Editing before baselining — Phase 2 gate; reject any iteration without a recorded median and spread.
- Accepting on one sample — Phase 4 requires the baseline's N.
- Bundled changes in one iteration — deltas become unattributable; reject and split.
- Moving the goalposts (fixture, floor, workload, MEASURE) to make the number move — guardrail list, stop-and-report.
- Overlap drift with `performance-optimization-engineer`: domain thresholds belong to the agent, loop methodology to this skill.
- Misroute from `objective-loop` on "keep going until it's fast enough" — the continuous metric routes here.
