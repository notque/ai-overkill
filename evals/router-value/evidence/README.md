# Initial calibration evidence

Collected with Codex CLI 0.153.3, gpt-6-astra, low effort, 2026-09-04. This is evaluator calibration, not evidence for a production reduction.

`baseline-calibration.jsonl.gz` contains 100 baseline-only routing-stage records (20 development cases, five repetitions). `baseline-noise.json` reports the five corpus median token samples. The randomized comparison uses a separate output directory. These baseline records predate input/resume-validation hardening and retain their original hashes.

`judge-calibration-streams.jsonl.gz` preserves seven fresh judge calls, their prompts and raw streams. `calibration-judgments.jsonl` contains 28 judgments from two passes over 14 opaque controls. Both judges classify every good/bad control and critical boundary correctly, and duplicate answers agree. The exact-vector mismatches in `judge-calibration-verdict.json` are retained; see ../CALIBRATION_ADJUDICATION.md for independent explanation of overlapping criteria. Raw streams were revalidated with the hardened usage parser; judging instructions did not change.

No winning treatment is asserted by these files. Runtime sandbox preflight cannot execute nested terminal commands in this container. A host-applied patch prototype was rejected because importing generated Python into its checker allowed forged results and unconstrained execution. No generated-code execution validator is shipped or claimed here. Fixture calibration runs only the known original/reference examples.

`name-only-rejection.json` and `name-only-stopped-trial.jsonl.gz` retain the rejected first context candidate: 165/300 trajectories completed before a structural counterexample stopped it. Twelve local definitions differed from canonical files and one local agent had no canonical file, so matching names could hide local knowledge. No A/B effect estimate or promotion is claimed from that incomplete trial.

The compressed archives preserve submitted prompts and raw event streams alongside result records. Hashes identify the original source/configuration; these trials predate the final instrument hardening and are calibration or rejection evidence only.
