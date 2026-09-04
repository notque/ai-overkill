# Router reduction corpus

30 fresh cases: 20 development, 10 holdout. Written without inspecting any candidate reduction. Prompts and rubrics are separate. Never include rubric files in executor input. Neither role names nor number of agents is a correctness target. /do remains the entrypoint.

## Recommended protocol

1. Freeze and hash corpus and treatment before running. Use development cases for iteration; keep holdout outcomes hidden until final selection.
2. Run the identical executor contract plus each prompt against baseline and treatment in isolated fresh sessions. Match current model, effort, tools, token ceiling and repository snapshot. Randomize opaque condition IDs and case order with a recorded seed. Do not expose baseline/treatment labels to graders.
3. Score each listed criterion 0 or 1 from actual output. Score only substantiated behavior; omission of a needed boundary is a miss, explicit violation of a critical failure is a safety failure. Report per-case earned/possible, macro-average normalized score, critical-failure count, clarification quality, prompt/output tokens, tools and elapsed time separately. Do not infer success from shorter output alone.
4. A routing-only pass cannot establish execution reliability. This PR provides no safe generated-code executor. Execution-backed promotion must wait for a real isolation boundary and authoritative out-of-process checker. Keep tests/rubrics inaccessible to any future executor. Other cases also require appropriate repository/integration fixtures before execution claims.
5. For edge cases, use two independent blind graders and adjudicate disagreement against the user's request, not route-name agreement. Re-run with randomized order before claiming a win. Report small sample limitations; do not fit to holdout.

Six small fixture pairs are supplied for trusted calibration (four dev, two holdout). They avoid networks, secrets, third-party dependencies, and production effects. Scoring proposed routes or calibrating authored examples does not count as executing generated changes. Fixtures contain no expected answers.

## Trusted fixture calibration only

The checker scripts import Python in their own host process. Run them only against the known authored originals, reference solutions, and trusted regression-test variants. Never pass generated or otherwise untrusted code: it could access checker state or forge the result. A host-applied patch prototype was rejected for this reason and is not shipped. The checks cover untouched endpoint source and external telemetry/config identifiers in the trusted examples; they establish no isolation or network-effect guarantee.

`calibration_results.json` records that all six original buggy fixtures fail and all six reference solutions pass. `reference_solutions/` is oracle material, never executor context.

## Reproduce from a checkout

From this directory, run `python3 -B calibrate.py` to recheck all six trusted original/reference pairs without modifying corpus files. Use `--output <path>` only when a saved record is wanted. From the repository root, run `python3 -B -m pytest scripts/tests/test_router_value_corpus.py -q` to check frozen prompt hashes, schema separation, duplicate blind controls, trusted calibration and protected-effect regressions. Corpus authoring generators are omitted: frozen JSONL, reference solutions and checkers are the reproducible inputs.

Judge packets have opaque IDs and contain no condition labels or expected scores. Keep `calibration-expected.json` and `CALIBRATION_ADJUDICATION.md` separate from blind judge inputs. The adjudication explains two compound-criterion overlaps in the original calibration vectors without changing their frozen bytes.
