# Evals

Blind A/B testing framework for evaluating new skills before they merge into the toolkit.

## Purpose

Every new skill must prove it adds measurable value over Claude's default behavior (no skill loaded). Visual code review alone misses subtle quality regressions -- the first A/B test caught 2 critical bugs that review missed (ADR-127). This directory holds the test plans, scoring rubrics, and case files for each evaluation.

## Methodology

1. **Parallel execution**: Each test case runs two variants -- one with the skill loaded, one without (baseline). For three-way comparisons, a third variant uses an existing alternative skill.
2. **Blind evaluation**: Outputs are labeled A/B (or X/Y/Z) with randomized assignment. The evaluator never knows which variant produced which output.
3. **Integer scoring**: Each output is scored 1-5 on skill-specific dimensions, then dimension averages are compared.
4. **60% win condition**: The skill variant must win on 60%+ of test cases to pass. Ties count against the new skill -- it must prove it adds value.
5. **Statistical reliability**: Each variant runs 3 times per case (`--runs-per-query 3`).

Verdict thresholds:
- **PASS** (>= 60%): Skill adds measurable value, proceed to merge.
- **MARGINAL** (40-59%): Skill needs improvement before merge.
- **FAIL** (< 40%): Skill does not add value over baseline.

## Adding a New Evaluation

1. Create a subdirectory: `evals/<skill-name>-eval/` (or a descriptive grouping name).
2. Add a `README.md` with the test plan: skills under test, claims, metrics, win conditions.
3. Add a `scoring-rubric.md` defining dimensions with 1-5 anchor descriptions.
4. Add `*-cases.md` files with concrete test prompts (5-7 cases per skill).
5. Run the eval using the `skill-eval` toolchain (see execution steps in each test plan).

## Directory Structure

```
evals/
  README.md                  # This file
  new-skills-ab-test/        # Canonical example evaluation
    README.md                # Test plan (progressive depth, explanation traces, multi-persona critique)
    scoring-rubric.md        # Blind evaluation rubric with dimension anchors
    *-cases.md               # Test case files per skill
  dense-complete-writing/    # Writing-standard A/B + Completeness clause race
    README.md                # Test plan and findings
    scoring-rubric.md        # 20-point coverage rubric + 0-100 dense-and-complete axis
    clause-race-cases.md     # Skill-creation task + 11 arms
```

See `new-skills-ab-test/` for the canonical example of a well-structured evaluation.

## Per-PR Skill-Eval Ablation

ADR skill-eval-pr-ablation. When a PR edits a skill, run its eval before vs.
after the edit to measure the delta. CI cannot run evals (the runner shells to
the `claude` CLI, absent on GitHub runners), so the real ablation runs locally.
CI only posts a coverage map.

### Mapping convention (changed skill -> eval)

`scripts/detect-skill-changes.py --base <ref> --head <ref> --format json` lists
the skills changed in a range and maps each to an eval. Resolution order, first
hit wins:

1. exact dir: `evals/<skill>/` exists.
2. `-eval` suffix: `evals/<skill>-eval/` exists.
3. README mention: the skill name appears as a whole word (case-insensitive) in
   any `evals/*/README.md`.
4. no match -> the skill is reported as **uncovered** (a gap to consider, not a
   failure).

The mapper always exits 0. Uncovered skills are data, not errors.

### Running the ablation locally

```bash
make skill-eval-ablation BASE=<ref> HEAD=<ref> [SKILL=<name>] [RUNS=3] [RECORD=1]
```

For each mapped skill it runs the eval against the base content, then the head
content, and prints the delta:

```
planning  base 58% -> head 67%  (+9, eval=evals/new-skills-ab-test, runs=3)
```

The command restores the working tree on every exit path; a crashed run leaves
no base content checked out.

`RECORD=1` writes one row per run to `learning.db` (topic `eval:<dir>`,
`git_commit_sha` = head SHA), so eval history becomes a queryable time-series.
Use the repository's learning DB CLI to query it:

```bash
python3 scripts/learning-db.py telemetry-query \
  --topic "eval:evals/new-skills-ab-test" --git-sha <head-sha> --format json
```

The command reads the per-run `telemetry_runs` rows on current databases. It
also reads the older `learnings` fallback written by degraded ablation runs;
fallback JSON rows have `"storage": "learnings"`, parsed `pass_rate`, `runs`,
`base_sha`, and `head_sha` fields. When both representations exist for the
same topic/key, the per-run telemetry rows are authoritative and the fallback
summary is not duplicated.

If PR-A's telemetry envelope columns are absent, `--record` degrades to a no-op
against those columns: it still writes the row (envelope packed into `value`)
and appends one JSON line to `~/.claude/eval-ablations.log`. No run is lost; it
never fails.

### Opt-in pre-push hook

Off by default — ablation spends real model calls. Install it explicitly:

```bash
make skill-eval-install-hook      # writes .git/hooks/pre-push (advisory)
```

Even installed, the hook acts only when `VEXJOY_SKILL_EVAL_PREPUSH=1`; otherwise
it does nothing. It never blocks the push (`exit 0` always). Re-installing is
idempotent and never clobbers a foreign pre-push hook.
