---
summary: "Standing procedure for judging router changes with the blind A/B harness."
read_when:
  - "changing the router or its manifest"
  - "running a routing A/B test"
---

# Router A/B Runbook

Standing procedure for judging ANY router change (manifest variants, fast paths,
prompt edits, re-rank policies) with the existing blind A/B harness. One harness:
`scripts/routing-ab-test.py`. Never build a parallel one.

## The standing sequence

1. **Branch.** Put the router change on its own branch. The harness only takes
   manifest *commands* as strings, so the challenger command can live on another
   branch's worktree (e.g. `python3 ../wt-cost-diet/scripts/routing-manifest.py --tiered`).
2. **Pick a run dir.** Every run gets a fresh subdirectory; completed runs in
   `scripts/routing-ab-results/` are never overwritten:
   `OUT=scripts/routing-ab-results/<change>-<date>`
3. **Emit per-arm prompts.**
   ```sh
   python3 scripts/routing-ab-test.py --emit-prompts --out-dir "$OUT" \
     --manifest-arm full="python3 scripts/routing-manifest.py --compact" \
     --manifest-arm tiered="python3 scripts/routing-manifest.py --tiered"
   ```
   The full arm's manifest command (here `--compact`) is part of the experiment
   definition — flag choice changes baseline prompt size materially (~35.7 KB
   default vs ~20 KB compact); record it in `arms.json` and keep it fixed across
   runs being compared.
   First arm = baseline, second = challenger (override at --gate with
   `--baseline-arm/--challenger-arm`). Without `--manifest-arm` the harness runs
   the legacy shared-prompt A/B (deterministic-first vs semantic-first).
   Arms may differ by MODEL instead of manifest: add `--model-arm name=model`
   (one per manifest arm; `default` = omit `--model`, the session model). The
   models land in `arms.json` for the bridge; the harness still never calls
   models. Example (self-route-v1): same manifest command in both arms,
   `--model-arm haiku=haiku --model-arm self-route=default`.
4. **Bridge: collect Haiku answers** (see below).
5. **Score.** `python3 scripts/routing-ab-test.py --score --out-dir "$OUT"`
6. **Blind judge.** `--build-judge` writes an arm-stripped, seed-shuffled
   `judge-input.json` plus a private `uid-map.json` (carries case + arm; the judge
   never sees it). Dispatch ONE judge agent over `judge-input.json`; it returns
   `{uid: "correct"|"partial"|"incorrect"}` as `judge-output.json`. Then
   `--rejoin` writes `scoreboard.json` with per-arm, per-bucket accuracy.
7. **Gate.** `python3 scripts/routing-ab-test.py --gate --out-dir "$OUT"` prints
   the pre-registered gates, then the verdict. Exit 0 PROMOTE, 1 REJECT,
   2 UNDERPOWERED. The gate is deterministic (expected-pair/`acceptable`
   matching over raw.json), so it cannot be argued with after the fact.
8. **PR.** Attach `scoreboard.json` + the `--gate` output to the router-change
   PR. The gate verdict decides; a REJECT means the change does not merge in its
   current form.

For force-route fast-path changes there is also a zero-model check:

```sh
python3 scripts/routing-ab-test.py --pre-route-map --assert-buckets --out-dir "$OUT"
```

It asserts every benchmark-force_route, paraphrase-git, and paraphrase-security
case is fast-path eligible (pre-route confidence `high` + `force_route`) and no
false-positive-guard case is. Exit 0/1. PR #833 closed the coverage hole this
check originally exposed (13 violations under corpus v1.1); the check now
PASSES (exit 0): all asserted buckets are fast-path eligible and no guard case
is (0/7).

## The answer-collection bridge

**Auth preflight (mandatory, before any answer collection).** Nested `claude -p`
reads `~/.claude/.credentials.json`, which `-p` mode never refreshes;
`claude auth status` reports loggedIn even when the token is expired and every
call 401s. Verify first:

```sh
env -u CLAUDECODE claude -p "Say OK" --model haiku --output-format json
```

Proceed only if the JSON shows `is_error: false`. On 401, the owner re-auths
interactively (`claude auth login`) — no scripted workaround.

`routing-ab-test.py` cannot call models (no API key, by design). A runner — the
orchestrator session or a human — bridges, exactly as in the semantic-first run
whose artifacts sit in `scripts/routing-ab-results/`:

- For each `"$OUT"/prompts/<arm>/<id>.txt` (legacy: `prompts/<id>.txt`), send the
  file content verbatim as a single prompt to **Haiku** (`claude-haiku-4-5`, the
  router model before self-route landed) — or, when `arms.json` carries a `models` map
  (`--model-arm` runs), to that arm's model (`default` = omit `--model`).
  Record per-call `cost_usd` and token counts in the run dir
  (`call-log.jsonl`) when the runner can capture them.
- Save the model's raw JSON object — shape
  `{"agent": ..., "skill": ..., "pipeline": ..., "reasoning": ..., "confidence": ...}`
  — as `"$OUT"/answers/<arm>/<id>.json` (legacy: `answers/<id>.json`).
- `--score` refuses to run until every (arm, query) answer exists, and lists the
  missing ones.
- **Unanswered cases: the harness wins.** "Retry once, then record unanswered"
  conflicts with `--score`, which refuses to run with ANY missing answer — so an
  unanswered case always blocks scoring. The <5%-loss tolerance decides only
  whether re-collection is permitted: re-collect just the missing ids via the
  idempotent bridge (it skips existing answers). If more than 5% of cases are
  still missing after one re-collection pass, declare the run INVALID.

The judge step is the same pattern: one agent reads `judge-input.json`, writes
`judge-output.json`. Keep `uid-map.json` away from the judge.

## Pre-registered gates (verbatim from `--gate`)

```
PRE-REGISTERED GATES (fixed in code before any run; change only BEFORE a run):
  (a) accuracy : challenger accuracy not worse than baseline by more than 3.0 points.
                 correct = exact expected agent+skill pair; where `acceptable` is
                 present, any listed {agent, skill} alternate also counts.
  (b) harm     : McNemar exact p for harm > 0.05. Fails only when challenger-harm
                 pairs exceed challenger-help pairs AND p <= 0.05.
  (c) safety   : ZERO new misses (baseline correct -> challenger wrong) in buckets
                 benchmark-force_route, false-positive-guard, paraphrase-git,
                 paraphrase-security.
  (d) stub-tier: challenger correct count in the stub-tier bucket within 1 case
                 of baseline.
VERDICT: PROMOTE (exit 0) = all gates pass AND discordant pairs >= 6.
         UNDERPOWERED (exit 2) = all gates pass but discordant pairs < 6.
         REJECT (exit 1) = any gate fails.
```

**Rule: gates change only BEFORE a run.** They live in code
(`GATES_TEXT`, `gate_verdict` in `scripts/routing-ab-test.py`) and in this file.
Editing a gate after seeing results invalidates the run — re-register the gate,
then run again. The McNemar exact test and paired-bootstrap stats are ported
from `feat/outcome-routing-loop:scripts/route-value-eval.py`.

## Adding corpus cases or buckets

Corpus: `scripts/routing-ab-corpus.json` (v1.3, 269 cases). Rules:

- **Append only.** The 49 legacy v1.0 cases are pinned by SHA-256 in
  `scripts/tests/test_routing_ab_harness.py`; editing them breaks CI.
- Schema per case: `{request, expected_agent, expected_skill, category, bucket,
  notes}` + optional `expected_pipeline` (default null), `acceptable` (list of
  `{agent, skill}` alternates), `uncertain: true` (best-effort gold label).
- Gold labels come from `skills/INDEX.json` / `pipeline-index.json` semantics,
  never from what the current router picks (that would be circular).
- Write realistic phrasing (file paths, casual wording), not abstract one-liners.
- New buckets are fine; if a bucket should be gate-protected, add it to
  `SAFETY_BUCKETS` in the harness BEFORE the run and note it here.
- Buckets v1.1 added: `stub-tier` (skills with zero recorded routes — the
  tiered-manifest tripwire), `sibling-disambiguation`, `pipeline-pick`
  (`expected_pipeline`; near-misses must yield pipeline null), `vague-interview`,
  `plain-english`.
- Buckets v1.3 added, from 128 recorded production dispatches that fell back to
  `general-purpose`: `prod-fallback-specialist` (a domain agent is correct),
  `prod-fallback-general` (`general-purpose` is correct — labelled EXPLICITLY,
  never as null, so an over-aggressive router fails too),
  `prod-fallback-coordinator` (multi-deliverable conjunctive requests;
  `project-coordinator-engineer` was chosen 0 times in 287 dispatches), and
  `prod-fallback-ambiguous` (`expected_agent: null` WITH the reason in `notes`).
- **Keep the `expected_agent` null rate low.** At v1.2 it was 142/178 (79.8%):
  a router that routed LESS scored BETTER, so under-routing was undetectable and
  a blind A/B promoted a regression as a 7-point gain. `test_null_agent_rate_stays_bounded`
  caps it at 60%. Null means "genuinely ambiguous, reason stated", not
  "no agent needed" — write `general-purpose` when that is the right answer.
- `expected_agent` may be a built-in agent name (`general-purpose`) that has no
  `agents/*.md` file; `routing-benchmark.py` accepts the `BUILTIN_AGENTS` set.
- Add cases on a branch and run the corpus tests:
  `python3 -m pytest scripts/tests/test_routing_ab_harness.py -q`.

## Provenance and the multi-box rule (v1.4)

This toolkit runs on several machines with different workloads. `learning.db` is
**per-box**: no host, machine, or project column, and nothing aggregates across
boxes. A local sample is therefore evidence about ONE machine. **Local absence of
an agent or skill is not evidence that it is unused** — do not reason from it.

Every taggable case carries `provenance: {source, workload, sample}`:

| `source` | Meaning | `workload` |
|---|---|---|
| `local-telemetry` | Sampled from recorded dispatches on one machine | names that workload |
| `catalog-derived` | Written from INDEX semantics; no telemetry | `null` |
| `unknown-legacy` | Not recorded at the time | `null` |

The 49 pinned v1.0 cases cannot carry the field (SHA-256 pin plus
`test_legacy_cases_have_no_new_fields`), so **absence resolves to
`unknown-legacy`**. They are believed to be paraphrases of
`routing-benchmark.json`, but that was never recorded, so it is not asserted.

`test_no_single_workload_dominates_agent_labels` caps any one workload at 75% of
the agent-asserting cases. At v1.4 the top workload (`mmr-ratings-flask`) holds
70.0% — the cap is a ratchet against growth, not an endorsement of that share.

**Contributing from another machine.** Balance comes from real cases, never from
inventing cases for a workload nobody has observed. To contribute:

1. Export your own general-purpose fallbacks (agent, skill, complexity, request).
2. Label them the way v1.3 did: specialist / general / coordinator /
   ambiguous-with-a-reason, `general-purpose` written explicitly when it is right.
3. Tag `provenance.source: "local-telemetry"` with **your** `workload` name.
4. Lower the cap in the guard test as real coverage arrives.

Prefer agents that currently hold zero agent-asserting cases — as of v1.4 that is
26 of 44, including every Node/React/Next agent, the observability agents
(`prometheus-grafana-engineer`, `perses-engineer`), the messaging and search
agents (`rabbitmq-messaging-engineer`, `opensearch-elasticsearch-engineer`),
`ansible-automation-engineer`, `database-engineer`, `data-engineer`,
`nodejs-api-engineer`, `typescript-debugging-engineer`, `reviewer-code`, and
`reviewer-perspectives`. A box doing Node API or Kubernetes work can cover those
in a way this box never will.

## Cost: 100-case, 2-arm run

Haiku 4.5 (`claude-haiku-4-5`): $1.00/M input, $5.00/M output.

| Step | Calls | Tokens (approx) | Cost |
|---|---|---|---|
| Routing answers | 200 (100 x 2 arms) | ~6K in + ~0.1K out each → 1.2M in, 20K out | ~$1.30 |
| Blind judge | a single agent pass over 200 rows | ~40K in, ~5K out | ~$0.07 |
| score / gate / pre-route-map | 0 model calls | — | $0 |

**~$1.50 per full run** (compact manifest ≈ 20KB ≈ 5-6K tokens per prompt; a
tiered arm's prompts are smaller, so real runs cost less). Negligible against
the Opus orchestrator session driving it.

## Prior results

- Semantic-first experiment (49-case corpus, Arm A deterministic-first vs Arm B
  semantic-first): artifacts in `scripts/routing-ab-results/` (answers,
  `answers-v2/` git-rule fix retest, scoreboard). Results doc:
  `skills/meta/do/references/semantic-first-ab-results.md`. Outcome:
  A ≡ B at 89.8% strict; the win was the git-rule prompt fix (~91.8%, zero
  guard violations); Option B (semantic-first + safety net) shipped.
- Fast-path eligibility map for corpus v1.1:
  `scripts/routing-ab-results/pre-route-map-v1.1/` (deterministic, regenerate
  any time with `--pre-route-map`).

## Completed experiments

1. **Tiered manifest** (`feat/do-cost-diet`): REJECTED twice, 2026-06-10.
   tiered-v1 failed gates (c) safety and (d) stub-tier; the stub-attribution
   fix (`c1080c04`) re-ran as tiered-v2 and failed the same two gates.
   Verdicts: `scripts/routing-ab-results/tiered-v1/VERDICT.md`,
   `scripts/routing-ab-results/tiered-v2/VERDICT.md`. Do not re-queue without
   a mechanism change beyond attribution text.
2. **Force-route fast path**: SHIPPED in `skills/meta/do/SKILL.md` Phase 2,
   keyed on pre-route `confidence: high` + `force_route` for pr-workflow and
   security skills. The zero-model check (`--pre-route-map --assert-buckets`,
   above) initially FAILED with 13 assert-bucket violations — 10
   paraphrase-git/security cases fell through the keyword pre-router and 3
   force-route cases sat at medium confidence. PR #833 merged the coverage fix;
   the check now PASSES (exit 0) and the guard direction holds (0/7 guards
   eligible).

## Known limits

- ~100 cases is small: gates use a 3-point margin, an exact McNemar test, and an
  explicit UNDERPOWERED verdict (discordant < 6) instead of pretending power.
- Gate correctness is exact-pair matching softened only by `acceptable`; the
  blind judge scoreboard remains the nuanced read. When they disagree, say so in
  the PR rather than picking the friendlier number.
- Single sample per (query, arm): no self-consistency estimate. Re-run
  with a fresh `--out-dir` to measure variance.
- 8 corpus cases carry `uncertain: true` — best-effort gold labels.
- Gold labels encode INDEX semantics as of corpus v1.1; renamed or split skills
  need corpus maintenance (append corrected cases, never edit legacy ones).
- `--pre-route-map` depends on the live `skills/INDEX.json` triggers; results
  drift as triggers change. Snapshot per run via `--out-dir`.
