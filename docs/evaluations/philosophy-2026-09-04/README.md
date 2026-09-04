# Philosophy V1: rejected

**V1 was rejected.** It used 35.8% fewer loaded interpretation tokens, but lost meaning: eight cases had lower per-case scores after nine blind disagreements were independently resolved. The quality floor did not permit token savings or aggregate gains to compensate. The draft remains under revision; this evidence does not authorize a merge.

The philosophy body went from **5,951 to 897 words**. All 300 isolated worker runs were valid: 30 independently authored cases, five repeats per arm, with the same model and runtime settings. Two blind passes produced 600 original judgments. Final raw-record verification and disputed-only adjudication reproduction passed; no disagreement remains unresolved.

Median input-plus-output tokens fell from **21,866 to 14,037**, or **35.804445%**; the median paired saving was **7,834.5 tokens**, a different statistic. These are operational-interpretation costs when this document is loaded, not global toolkit savings, billed costs, autonomous tool compliance or live task success.

## Decision and spend

`VERDICT.json` records REJECT and the eight regressions: `dev01`, `dev09`, `dev11`, `dev20`, `hold02`, `hold07`, `hold09`, `hold10`. `assessment-original.json` retains the original INCONCLUSIVE result before adjudication. Both original votes and the independent reasoning remain intact. The precommitted rule required no per-case mean regression and no material principle loss; neither rubric nor threshold was relaxed.

Recorded CLI trial spend was **7,308,599 input-plus-output tokens**:

| Stage | Recorded tokens |
|---|---:|
| 300 workers | 5,385,121 |
| Calibration judges | 57,014 |
| 120 blind-judge calls | 1,866,464 |

`measurement-spend.json` retains separate input, output and cached-input counts. Cached input is part of input, not added again. Native-agent adjudication, authoring, orchestration, review and interrupted discovery calls have no usage records here; they are **unmetered, not free**. The recorded CLI sum is not a full experiment-total claim.

## Preserved evidence

- `frozen-inputs.tar.gz`: independent corpus with original checksums; exact arm, context and case inputs; submitted blind packets and private mapping; collection-source snapshots. Keep mapping and arm files out of blind judge inputs.
- `workers.tar.gz`: all 300 submitted prompts, raw events, final messages, result records, original manifest and digest-keyed input store.
- `calibration.tar.gz` and `judges.tar.gz`: complete original prompts, raw events, manifests, final judgments and result records for calibration and both measured judge passes.
- `final-evidence.tar.gz`: original assessment, final verdict, blind dispute input, adjudications, resolved scores, original independent audit source and chronological ledger.
- `verifier.tar.gz`: separately audited runner/judge/assessor from PR #956, commit `e72bc9907eda7384153795df6349cc31b52fe2f5`. These validate raw evidence; they are distinct from the collection-source snapshots.
- `archive-index.json`: per-member hashes, source provenance and adjudication hashes. `SHA256SUMS` verifies published files. Original corpus/source checksums remain separately preserved.
- `adjudication-rule.md`: exact rule frozen before final judgment inspection. `ledger.md` preserves the sequence and appended word-count correction. `independent-verification.md` describes the independent reproduction.

The top-level protocol, cases, calibration verdict and preliminary token profile are exact historical copies. The preliminary profile's “quality pending” text is preserved as history; **the final quality verdict is REJECT**. Its median-of-five-corpus-medians values (21,866.5 and 14,035.5) differ from the verified pooled per-run medians (21,866 and 14,037); both round to a 35.8% reduction. Raw data is unchanged. Use `VERDICT.json` for final metrics.

## Reproduce without model calls

From the repository root:

```bash
evidence_dir=docs/evaluations/philosophy-2026-09-04
(cd "$evidence_dir" && sha256sum -c SHA256SUMS)
replay_dir=$(mktemp -d)
for archive in frozen-inputs workers calibration judges final-evidence verifier; do
  tar -xzf "$evidence_dir/$archive.tar.gz" -C "$replay_dir"
done
python3 -B "$replay_dir/verifier/assess.py" assess --routing-results "$replay_dir/workers" --map "$replay_dir/experiment/judge-map.json" --judge-dir "$replay_dir/judges"
python3 -B docs/evaluations/philosophy-2026-09-04/verify.py --experiment "$replay_dir/experiment" --workers "$replay_dir/workers" --judges "$replay_dir/judges" --verifier "$replay_dir/verifier"
```

The raw assessor reproduces the original disagreement-bearing assessment. `verify.py` independently checks all 300 assignments and 600 original votes, applies only the nine disputed-check decisions, preserves agreed scores, recalculates every case/arm mean and token metric, and reproduces REJECT. It verifies the precommitted rule and blind-input hashes. This checks evidence linkage and arithmetic; it does not rejudge semantic decisions.

To rerun model sampling, use the preserved `source/runner.py` against `experiment/protocol.json` with a **new** output directory. This spends tokens; keep the original artifacts. The protocol resolves input paths relative to its directory. Original absolute paths in manifests are provenance keys backed by archived input bytes; raw verification does not need the original machine paths.

The worker runner comes from its original digest store. Judge/assessor collection sources were snapshotted and reportedly held unchanged during judging; their runtime manifests did not pin source hashes. The separate verifier is explicitly versioned. Runtime settings recorded `codex-cli 0.153.3`, `gpt-6-astra`, low effort, isolated ephemeral read-only sessions, ignored user rules/configuration and disabled automatic hooks/plugins/skill/project-document loading. These do not guarantee an immutable service-side model snapshot.

Original full/body word counts are **5,974/5,951**; frozen V1 full/body counts are **922/897**. The earlier 898-body note preceded a one-word final edit. Future revisions require a fresh independent holdout; the exposed original holdout is now development evidence. Any later promotion requires its own passing blind verdict and all required GitHub Actions on the exact head.
