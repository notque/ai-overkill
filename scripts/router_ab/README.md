# Router value evaluation

This harness measures whether a proposed policy change preserves useful routing decisions. `/do` remains the central router. This PR adds evaluation infrastructure only; a startup-catalog reduction would be a separate PR after appropriate evidence and GitHub Actions pass.

Run commands from the repository root. `evals/router-value/protocol.example.json` is a wiring example with **identical policies in both arms**, one development case and five repeats. It cannot show a reduction benefit. Real experiments supply their own frozen policy/context files, case list, decision thresholds and output directories. Do not read holdout results while choosing a candidate.

## Routing and blind judging

```bash
python3 scripts/router_ab/runner.py validate --protocol evals/router-value/protocol.example.json --output /tmp/router-value-example/routes
python3 scripts/router_ab/runner.py run --protocol evals/router-value/protocol.example.json --output /tmp/router-value-example/routes --cases dev
python3 scripts/router_ab/assess.py prepare --routing-results /tmp/router-value-example/routes --packets /tmp/router-value-example/blind.jsonl --map /tmp/router-value-example/private-map.json --suite dev --rubrics evals/router-value
python3 scripts/router_ab/judge.py --packets /tmp/router-value-example/blind.jsonl --out /tmp/router-value-example/judges --rubrics evals/router-value --passes 2
```

Use `assess.py prepare` to associate independent rubrics and check coverage; raw runner exports alone are not judge-ready. The private map, arm prompts, usage and policy files must stay outside judge inputs. Always pass the rubric directory explicitly. Failed, missing, malformed and timed-out assignments remain in the denominator; do not filter down to successful model replies.

Calibrate judges before scoring measured decisions:

```bash
python3 scripts/router_ab/judge.py --packets evals/router-value/judge-calibration.jsonl --out /tmp/router-value-example/calibration --rubrics evals/router-value --passes 2 --calibration
python3 evals/router-value/check_judge_calibration.py --judgments /tmp/router-value-example/calibration/judgments.jsonl
```

The comparison requires correct good/bad separation, intended failed criteria, critical flags and exact-duplicate consistency. Two documented compound-criterion penalties are allowed; see [calibration adjudication](../../evals/router-value/CALIBRATION_ADJUDICATION.md). Frozen vectors remain available for audit.

## Routing assessment and unavailable execution evidence

```bash
python3 scripts/router_ab/assess.py assess --routing-results /tmp/router-value-example/routes --judge-dir /tmp/router-value-example/judges --map /tmp/router-value-example/private-map.json
```

Execution-backed promotion is unavailable until a real isolated executor and an authoritative out-of-process checker are implemented. A discarded prototype imported generated Python into the host checker, allowing submitted code to access evaluator state or forge success. It is not shipped. Do not bypass sandbox restrictions or use the trusted-fixture scripts to evaluate generated code.

The six fixture pairs calibrate only known buggy originals against authored reference solutions. Those checks establish fixture behavior; they are not generated execution evaluations and cannot satisfy an execution gate. Code reductions remain **PENDING_EXECUTION** for promotion. The assessor may report **REVIEW_READY** for routing evidence only, with unresolved prerequisites and no production authorization. Appropriate execution evidence, independent calibration, review, and all required GitHub Actions checks remain separate requirements. The one-case example is only a plumbing check.

## Isolation and reproducibility

All model calls use `gpt-6-astra` at low effort, recorded with the installed Codex CLI version. The alias is explicit but is not a guarantee of an immutable server-side model snapshot. Calls use:

- `--ignore-user-config --ignore-rules`: avoid local configuration and rule contamination.
- `--ephemeral --disable hooks --disable plugins`: avoid persisted sessions and ambient hook/plugin instructions.
- `-c skills.include_instructions=false -c project_doc_max_bytes=0`: prevent automatic skill and project-document loading.
- `-a never -s read-only`, fresh temporary working directories: no approval pauses or model writes. Routing/judging tool activity invalidates a run. Unknown tool items and any completion with missing or malformed usage fail closed.
- `--json`, explicit model/effort, captured final output: retain usage, failures and provenance rather than reconstructing them from prose.

The protocol resolves case, policy and common-context paths relative to its own directory. Freeze these inputs before sampling. Manifests record assignments, input digests and runtime settings; retain the exact input bytes and digest-keyed input store alongside raw records. Resume must reject changed inputs or mismatched cached results. Use a fresh output directory after a policy, fixture, checker or protocol change. Never expose reference solutions, evaluators or rubric/score files to executors.

Routing and judging launch each CLI in its own POSIX process group. A timeout sends TERM to that group, allows bounded cleanup, and then sends KILL to remove remaining children. Partial streams remain evidence of an invalid attempt; absent completion usage stays unknown. Copy `process_control.py` alongside either harness when preparing frozen trial sources. This is process lifecycle cleanup, not a sandbox: children that deliberately leave the group are outside its guarantee, and local termination does not establish provider-side billing or cancellation latency. The trusted fake-CLI regression in `test_process_control.py` reproduces the old orphan and verifies cleanup without model calls.

This is a routing-policy simulation, not a full recursive `/do` run with normal agents, skills and hooks. It measures scoped decisions; it does not establish completed-task correctness, production behavior, integration safety, or savings across all tasks. Repeated samples of a small case set are not independent evidence of broad generalization.
