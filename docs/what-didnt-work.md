---
summary: "Negative-results registry of failed experiments."
read_when:
  - "before retrying an old idea"
  - "recording a failed experiment"
---

# What didn't work

Negative-results registry. A list of experiments that lost, so the next session skips a known-dead path.

When to add: you tried something and it failed, weakened, or got reverted. Record it here before you forget. Newest on top.

Format: one `## YYYY-MM-DD <experiment>` section with the four bold fields below. Evidence must be a location (`file:line`, eval path, PR #, or `learning.db topic/key`), not a claim.

```markdown
## YYYY-MM-DD <experiment, one line>

- **Expectation**: what we predicted.
- **What happened**: the observed result.
- **Evidence**: file:line, eval path, PR number, or learning.db topic/key.
- **Decision**: rejected | deferred | revisit-if <condition>.
```

Add new entries under the Post-seed experiments section; a CI test pins the seed-entry count (evidence: PR #798).

Query it: read this file, run `grep -c '^## 2026' docs/what-didnt-work.md`, or run `/retro what-didnt-work` (prints the file; optionally mirrors a one-line pointer into learning.db for FTS search). Check it before re-running an experiment.

---

## Post-seed experiments

Experiments recorded after the seed set. Same four bold fields; `###` headings keep the seed-count checks in `scripts/tests/test_negative_results_registry.py` stable. Newest on top.

### 2026-08-27 Instruction-compliance measured on a surface that cannot show compliance

- **Expectation**: scanning Agent dispatches for phase banners (M01) and the routing banner (M03) would measure whether the orchestrator followed those mandatory instructions.
- **What happened**: the hook runs on `PostToolUse:Agent` and scans only the dispatch prompt and the subagent report. Both banners are main-thread orchestrator output and appear in neither string, so the detector could never register compliance. Recorded skip rates were 99.3% and 100% by construction: M03 read compliant 7 times in 3,444 observations. The `skip-rate` dashboard then applied its own rule and printed `CONVERT TO GATE` for five instructions, recommending blocking gates against violations that never happened. M05/M06 had a second version of the same defect. They detect whether a directive reached the prompt, not whether output followed it, and they were scored across all 3,444 dispatches when the directive ships on only ~341 `/do`-routed ones.
- **Evidence**: `hooks/instruction-compliance.py` (surface), `scripts/learning-db.py` skip-rate threshold, PR #925, PR #927.
- **Decision**: rejected. An instrument declares `observable` for its surface and records nothing where it cannot see; a rate states its denominator. Never gate on a metric whose detector has not been shown capable of a positive reading.

### 2026-08-27 Injection floor set above birth confidence starved the learning pool for 27 days

- **Expectation**: a 0.70 confidence floor would inject only well-established learnings.
- **What happened**: error learnings are born at 0.55, and confidence rises only via a +0.10 boost applied when a learning is injected. A floor above the birth value is a one-way ratchet. A new learning never injects, so it never boosts, so it never crosses the floor, while `confidence-decay.py` pulls it down 0.05 per 30 days. 392 of 427 live error learnings sat at exactly 0.55. Combined with 103 rows suppressed by non-durable `graduated_to` sentinels (97 of them `session-artifact`), the injectable pool fell to 2 rows and `activations` went from 9,755 in July to 1 in August. Nothing raised an error: `record_activations_safe` swallows every exception unless `debug=True`, and `validate-learning-effectiveness.py` reported PASS at 52.1/100 while its Activation Coverage sub-score sat at 2.9/100.
- **Evidence**: `hooks/lib/learning_db_v2.py` birth-confidence table and `INJECTION_MIN_CONFIDENCE`; `learning.db` `activations` by month; PR #926, PR #927.
- **Decision**: rejected. Any injection threshold must sit below the lowest birth confidence, enforced by a test (`hooks/tests/test_injection_floor.py`). A blended health score must fail when a component sub-score flatlines, not average it away.

### 2026-08-15 Deterministic pre-router promoted and demoted 9 times without a corpus null-model score

- **Expectation**: each pre-route.py change would improve routing accuracy.
- **What happened**: 9 promotion/demotion cycles between 2026-03-23 and 2026-08-15 (commits `82d3cb15`, `3ad11088`, `2e8b9e71`, `869a786b`, `f8e6187c`, `97cc2d4d`, `3479fa02`, `52847a9f`, `7b09fc3c`, `7152afb1`). No cycle published the corpus null-model baseline score, so each change was evaluated against the previous change rather than against a standing baseline. The reversals compounded.
- **Evidence**: git log of `scripts/pre-route.py` between 2026-03-23 and 2026-08-15; commits listed above.
- **Decision**: rejected. A change to routing behavior needs a corpus whose null-model score is published, or it will be reversed.

### 2026-08-15 /do SKILL.md halved twice by blind A/B PROMOTE on a 79.8% null corpus

- **Expectation**: reducing SKILL.md size would improve routing via shorter context.
- **What happened**: PRs #860 and #861 each promoted a variant that halved SKILL.md. The evaluation corpus was 79.8% `expected_agent: null`, so most test cases accepted any route. The smaller skill lost routing information that mattered for the 20.2% with real expectations. Restored to larger form in PR #911.
- **Evidence**: PRs #860, #861 (PROMOTE), PR #911 (restore); `scripts/routing-ab-corpus.json` null-rate.
- **Decision**: rejected. A corpus where 80% of cases have no expected answer cannot validate a reduction.

### 2026-08-15 F821 disabled on untested false-positive claim, re-enabled with 2 real findings

- **Expectation**: F821 (undefined name) ruff check was producing false positives.
- **What happened**: F821 was disabled 2026-03-17 (commit `a739987b`) on the claim of false positives, with no evidence of actual false positives recorded. Re-enabled 2026-08-15 (commit `b4b05ee8`); 2 findings surfaced, both real.
- **Evidence**: commit `a739987b` (disable), commit `b4b05ee8` (re-enable); ruff output on re-enable.
- **Decision**: rejected. Disabling a lint rule requires evidence of false positives, not a claim.

### 2026-04-15 Routing telemetry wrote nothing for 21 days

- **Expectation**: routing-decision-recorder hook would capture route decisions to learning.db.
- **What happened**: from 2026-03-25 to 2026-04-15, the hook used `--category routing-decision` (commit `90304c3a`), which was an invalid category. Every record exited with code 2. Zero rows written for 21 days.
- **Evidence**: commit `90304c3a`; `hooks/routing-decision-recorder.py` exit code 2 on invalid category.
- **Decision**: rejected. Telemetry that writes nothing is invisible without a liveness check. A write-then-read probe on first use would have caught this on day 1.

### 2026-08-15 semantic-first A/B cited at 89.8/92.8 while answers/README.md says it was never executed

- **Expectation**: the semantic-first ordering A/B would produce measured accuracy numbers.
- **What happened**: `skills/meta/do/references/semantic-first-ab-results.md` reports 89.8% strict / 92.8% lenient. `scripts/routing-ab-results/answers/README.md` states "the live Haiku run requires an agent-dispatch capability and has not been executed yet." The `answers/` directory contains only the README, no answer files. The numbers were projected from protocol design, not observed from execution.
- **Evidence**: `scripts/routing-ab-results/answers/README.md`; `skills/meta/do/references/semantic-first-ab-results.md` now records only the unrun protocol.
- **Decision**: rejected. Marking the reference file as UNRUN. Numbers from an unexecuted A/B are projections, not evidence.

### 2026-07-04 same-context fixing vs fresh-agent fixing (quality-loop Phase 7)

- **Expectation**: the Lovable-article claim (the agent that evaluated a finding fixes it best in the same context, with no re-discovery cost) beats Phase 7's fresh-agent design on fix correctness or latency.
- **What happened**: 8 paired trials (16 sonnet runs) on a seeded-bug fixture (8 Python modules, one test-pinned bug each). Both arms 8/8 correct, zero collateral damage, indistinguishable tool-call counts (~3 per trial): the finding text alone re-discovered every bug in one Read. Blind opus judge leaned same-ctx 4-2 (+2 ties), but 6/8 verdicts turned on a fixture artifact (which arm scrubbed the "Bug:" docstring), and one diff pair was character-identical; sign test p ~= 0.69. Correctness hit ceiling, so the run judges the corpus, not the variants. The same-ctx arm was also simulated (reviewer reasoning injected into a fresh prompt), not a true warm-context continuation.
- **Evidence**: `scripts/routing-ab-results/fix-strategy-v1/VERDICT.md` (per-trial data, diffs, judge output); fixture `fixtures/fix-strategy-ab/`.
- **Decision**: revisit-if a hardened corpus (multi-file bugs, misleading findings, fixes that break other tests) drops the fresh baseline below ~80% AND a true same-context arm (session continuation, not reasoning injection) is built. Until then Phase 7 keeps the fresh agent.

### 2026-06-12 fact-check skill blind A/B on the original (easy) eval corpus

- **Expectation**: a skill carrying journalist-grade verification methodology beats a bare sonnet baseline on a 6-fixture closed-book claim-verification corpus.
- **What happened**: dead tie, 19/19 catches, 0/0 false alarms, 28/28 labels both arms. The corpus was ceiling-bound: obvious seeded errors, 2 sources per fixture, every claim settled by direct lookup, so methodology had nothing to add. A hardened corpus (distractor sources, unit/timeframe drift, context-stripped quotes, genuine source conflicts, false-alarm traps; 46 claims) separated the arms: skill passed the pre-registered bar with catches 34 vs 33, FA 2-2, label-correct 38 vs 32. The skill's measured edge is adjudication-vocabulary discipline, not raw catch rate.
- **Evidence**: workflow runs `wf_ebaac077-b9c` (round 1) and `wf_e65eb0da-6f1` (round 2); eval corpus in PR #811.
- **Decision**: rejected the easy corpus, kept the skill. Rule of thumb validated: a null A/B verdict on an easy corpus judges the eval, not the variant. Harden until the baseline drops below ceiling before accepting a null.

### 2026-06-11 review-contract-provenance port from steipete/agent-scripts

- **Expectation**: an explicit review contract plus git provenance commands (master-list rank 4+5: Review Contract + provenance method into `systematic-code-review`; contributor trust block into `parallel-code-review`) beats the baseline review skills in a blind A/B.
- **What happened**: blind A/B (2 swapped-label rounds, fable arms + judges, auth-diff review task): baseline won 2-0. Variant rejected; no PR opened.
- **Evidence**: branch `feat/review-contract-provenance` (pushed, unmerged); workflow run `wf_d2f09dbd-850`; master list `tmp/agent-scripts-master-list.json`.
- **Decision**: rejected. Keep baseline `systematic-code-review`/`parallel-code-review` unchanged; revisit-if a stronger variant and a larger A/B.

## 2026-06-05 Provenance footers on every answer

- **Expectation**: per-answer footers (source tier, confidence, reviewed-by, freshness, owner) improve auditability.
- **What happened**: refuted for a single-user toolkit. The metadata is already captured internally in learning.db via hooks (`routing-decision-recorder`, `routing-outcome-recorder`, `review-capture`) and is queryable through `learning-db.py`. Footers add friction with no new value and fight the Dense-Complete Writing standard.
- **Evidence**: verified detail `skills-design` / "Provenance footers"; `skills/meta/do/SKILL.md` lines 461-467 (hook capture, not in output).
- **Decision**: rejected.

## 2026-06-05 Strict knowledge/process skill split

- **Expectation**: partition each complex skill into a knowledge-only semantic router plus a separate process executor.
- **What happened**: refuted. The toolkit composes agent + skill at dispatch time, and most skills are intentionally hybrid (`/do` routes and orchestrates; `planning` interviews and executes). The `pairs_with` field already documents relationships declaratively. A forced binary split adds structure with no working gain.
- **Evidence**: verified detail `skills-design` / "Pairwise knowledge + process skill splitting"; `skills/process/planning/SKILL.md` lines 92-95 (`pairs_with`); `skills/meta/do/SKILL.md` line 280.
- **Decision**: rejected.

## 2026-06-05 Eval-doc caveats left as unindexed prose

- **Expectation**: nothing. This is the gap that motivates the registry.
- **What happened**: real eval caveats (for example the N=1 pilot note) sit as prose in eval READMEs, unsearchable. This registry indexes future ones. Back-filling old eval caveats is out of scope for this PR.
- **Evidence**: `evals/dense-complete-writing/README.md:25-26`.
- **Decision**: revisit-if a second eval produces a coverage-collapse result (then back-fill the old caveats).

---

## Program notes (blog-learnings implementation)

Operational dead-ends from the implementation program. Reverted approaches and runtime quirks, not experiment hypotheses, so they sit below the dated seed entries. Same six fields, lighter heading.

### 2026-06-05 Installed .git/hooks/* update on generator-change merge

- **Expectation**: merging an `install.sh` generator change (e.g. a new staleness notice in the installed git hook) updates the already-installed `.git/hooks/*` for that repo.
- **What happened**: installed `.git/hooks/*` are install-time artifacts written by `install_git_hook`; they do NOT regenerate on a code merge. PR #751's staleness notice was absent live after PR #740's merge because the installed hook predated #751 and was never rewritten.
- **Evidence**: PR #751; PR #740; `install.sh` `install_git_hook`; program negative-notes log, 2026-06-05.
- **Decision**: rejected. After merging `install.sh` generator changes, rerun `install.sh` (or `install_git_hook`) to rewrite the installed `.git/hooks/*`; merging the generator alone does not update them.

### 2026-06-05 Post-merge git pull as live hook deployment

- **Expectation**: pulling main after a merge puts the changed hooks live in `~/.claude` immediately via the post-merge sync hook.
- **What happened**: the post-merge hook is deliberately no-clobber (commit 18e6d03c) so it adds new items but never overwrites existing `~/.claude` hooks. Freshly merged telemetry capture stayed inert (0 rows) until `sync-to-user-claude.py` was run manually on SessionStart; the next probe then wrote the first `telemetry_runs` row.
- **Evidence**: commit 18e6d03c; `hooks/sync-to-user-claude.py`; program negative-notes log, 2026-06-05.
- **Decision**: rejected. After merging hook changes mid-session, run `sync-to-user-claude.py` (or restart the session) before expecting live hook behavior; the no-clobber pull alone will not deploy them.

### 2026-06-05 Workflow args global on the Windows runtime

- **Expectation**: the Workflow tool `args` param is exposed to the script as the `args` global.
- **What happened**: both launches failed in 9ms with "undefined is not an object (evaluating 'args.prs')". `args` was never delivered, for inline script and `scriptPath` invocations alike.
- **Evidence**: program negative-notes log, 2026-06-05.
- **Decision**: rejected. Hardcode run config as a `const` inside the script file; do not parameterize Workflow scripts via `args` on this runtime version.

### 2026-06-05 gh auth login --with-token from stored git PAT

- **Expectation**: authenticate the gh CLI non-interactively by piping the git-credential-manager PAT into `gh auth login --with-token`.
- **What happened**: login validation rejected the token for missing `read:org` scope (the push-capable PAT has `repo` only). `hosts.yml` stayed absent and the first ship run failed.
- **Evidence**: program negative-notes log, 2026-06-05.
- **Decision**: rejected. Export `GH_TOKEN` from `git credential fill` per session; gh honors it without the `read:org` validation, and `repo` scope covers pr create/checks/merge.

### 2026-06-05 VEXJOY_SECURITY_REVIEW_SKIP via Bash inline env-prefix

- **Expectation**: a bash inline prefix (`VAR=1 git commit ...`) or `export` in the Bash tool would let the PreToolUse security-review hook see the skip var.
- **What happened**: the var never reached the hook. The Claude Code runtime intercepts any Bash string containing "git commit", spawns the hook from the runtime process env (not the tool subshell), and blocks before the inline assignment runs.
- **Evidence**: program negative-notes log, 2026-06-05.
- **Decision**: rejected. Set the var in the PowerShell process (`$env:VEXJOY_SECURITY_REVIEW_SKIP="1"`) before `git commit`; PowerShell's process env propagates to the runtime-spawned hook. Use the override only for the auditable self-scan case.

### 2026-06-05 Windows fcntl-less concurrency tests

- **Expectation**: full local pytest of `test_routing_decision_recorder.py` would be green.
- **What happened**: the `TestBridgeConcurrency` parallel-append tests fail on Windows. `routing_outcome_state` serializes with `fcntl.flock`, which is absent on win32, so the lock is a no-op and concurrent appends race. Identical failures reproduce on a clean main checkout; CI's Linux runner passes them.
- **Evidence**: `hooks/lib/routing_outcome_state.py`; program negative-notes log, 2026-06-05.
- **Decision**: revisit-if the toolkit adds a win32 lock fallback. Treat as a pre-existing Windows-only environment limit, not a PR regression; trust CI's Linux run for these tests.

### 2026-06-05 Probe learnings table for git_commit_sha telemetry columns

- **Expectation**: PR-A would add named envelope columns (`git_commit_sha`, `model_id`, `skill_version`) to the `learnings` table, so a `--record` path could probe `PRAGMA table_info(learnings)` and update them.
- **What happened**: PR-A (#741) shipped the envelope as a dedicated `telemetry_runs` table (schema v5, `git_sha` column) with a `record_telemetry_run()` API. `learnings` never gets `git_commit_sha`, so the probe always found it absent and degraded to a log file. The with-envelope test passed only because the fixture hand-added the column, certifying a path production never takes.
- **Evidence**: PR #741; `learning-db.py telemetry-query`; program negative-notes log, 2026-06-05.
- **Decision**: rejected. Probe `telemetry_runs` existence; write via `record_telemetry_run()` and keep a human-readable summary row in `learnings`. Fixtures build the real schema.
