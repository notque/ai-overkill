# Agent Comparison — Phase 5: OPTIMIZE (Autoresearch)

## Overview

Phase 5 runs an automated optimization loop that improves a markdown target's frontmatter `description` using trigger-rate eval tasks, then selects the best measured variants through beam search or single-path search.

This phase is for routing/trigger optimization, not full code-generation benchmarking. Invoke it when the user says "optimize this skill", "optimize the description", or "run autoresearch". The existing manual A/B comparison (Phases 1-4) remains the path for full agent benchmarking.

---

## Step 1: Validate Optimization Target and Goal

Confirm the target file exists, has YAML frontmatter with a `description`, and the optimization goal is clear:

```bash
# Target must be a markdown file with frontmatter description
test -f skills/{target}/SKILL.md
rg -n '^description:' skills/{target}/SKILL.md

# Goal should be specific and measurable
# Good: "improve error handling instructions"
# Bad: "make it better"
```

---

## Step 2: Prepare Trigger-Rate Eval Tasks

```bash
python3 skills/meta/agent-comparison/scripts/optimize_loop.py \
    --target skills/{target}/SKILL.md \
    --goal "{optimization goal}" \
    --benchmark-tasks skills/meta/agent-comparison/references/optimization-tasks.example.json \
    --train-split 0.6 \
    --verbose
```

Supported task schemas:
- Flat `tasks` list with optional `"split": "train" | "test"` per task
- Top-level `train` and `test` arrays

Every task must include:
- `query`: the routing prompt to test
- `should_trigger`: whether the target should trigger for that prompt

If no split markers are present, the loop does a reproducible random split with seed `42`.

---

## Step 3: Run Baseline Evaluation

The loop automatically evaluates the unmodified target against the train set before starting iteration. This establishes the score to beat, and records a held-out baseline if test tasks exist.

---

## Step 4: Enter Optimization Loop

The `optimize_loop.py` script handles the full loop:
- Calls `generate_variant.py` to propose a new frontmatter `description` through `claude -p`
- Evaluates each variant against train tasks
- Runs either:
  - single-path hill climbing: `--beam-width 1 --candidates-per-parent 1`
  - beam search with top-K retention: keep the best `K` improving candidates each round
- Accepts variants that beat their parent by more than `--min-gain` (default 0.02)
- Rejects variants that don't improve or break hard gates
- Checks held-out test set every `--holdout-check-cadence` rounds for Goodhart divergence
- Stops on convergence (`--revert-streak-limit` rounds without any ACCEPT), Goodhart alarm, or max iterations

```bash
python3 skills/meta/agent-comparison/scripts/optimize_loop.py \
    --target skills/{target}/SKILL.md \
    --goal "{optimization goal}" \
    --benchmark-tasks skills/meta/agent-comparison/references/optimization-tasks.example.json \
    --max-iterations 20 \
    --min-gain 0.02 \
    --train-split 0.6 \
    --beam-width 3 \
    --candidates-per-parent 2 \
    --revert-streak-limit 8 \
    --holdout-check-cadence 5 \
    --report optimization-report.html \
    --output-dir evals/iterations \
    --verbose
```

Omit `--model` to use Claude Code's configured default model, or pass it explicitly if you need a specific override.

The `--report` flag generates a live HTML dashboard that auto-refreshes every 10 seconds, showing a convergence chart, iteration table, and review/export controls.

### Recommended Modes

- Short default optimization: default flags only
- Fast single-path optimization: `--beam-width 1 --candidates-per-parent 1 --max-iterations 3 --revert-streak-limit 3`
- True autoresearch sweep: `--max-iterations 20 --beam-width 3 --candidates-per-parent 2 --revert-streak-limit 20`
- Conservative search with strict keeps: raise `--min-gain` above `0.02`
- Exploratory search that accepts small wins: use `--min-gain 0.0`

### Live Eval Defaults

Live eval defaults are intentionally short:
- one optimization round
- three trigger-eval runs per query
- one trigger-eval worker
- no holdout cadence unless explicitly requested

For real repo skills at `skills/<name>/SKILL.md`, the live evaluator prefers an isolated git worktree so the candidate content is scored at the real skill path. This is the default `--eval-mode auto` behavior and avoids scoring the installed skill instead of the candidate. The registered-skill path also evaluates the current working copy, not just `HEAD`, so local uncommitted edits are measured correctly.

---

## Step 5: Present Results in UI

If you passed `--report optimization-report.html`, open the generated file in a browser. The report shows:
- Progress dashboard (status, baseline vs best, accepted/rejected counts)
- Convergence chart (train solid line, held-out dashed line, baseline dotted)
- Iteration table with verdict, composite score, delta, and change summary
- Expandable inline diffs per iteration (click any row)

---

## Step 6: Review Accepted Snapshots

Not all ACCEPT iterations are real improvements — some may be harness artifacts. The user reviews the accepted iterations as candidate snapshots from the original target:
- Inspect each accepted iteration's diff in the report
- Use "Preview Combined" only as a comparison aid in the UI
- Use "Export Selected" to download a review JSON describing the selected snapshot diff
- In beam mode, review the retained frontier candidates first; they are the strongest candidates from the latest round

---

## Step 7: Apply Selected Improvements to Target File

Apply one reviewed improvement to the original target file.

- If you want the best single accepted variant, use `evals/iterations/best_variant.md`.
- Beam search still writes a single `best_variant.md`: the highest-scoring accepted candidate seen anywhere in the run.
- Choose scope deliberately:
  - `description-only` for routing-trigger work
  - `body-only` for behavioral work on the skill instructions themselves
- If you exported selected diffs, treat that JSON as review material only. It is not auto-applied by the current tooling, and the current workflow does not support merging multiple accepted diffs into a generated patch.

```bash
# Review the best accepted variant before applying
cat evals/iterations/best_variant.md | head -20

# Replace the target with the best accepted variant
cp evals/iterations/best_variant.md skills/{target}/SKILL.md
```

---

## Step 8: Run Final Evaluation on Full Task Set (Train + Test)

After applying improvements, run a final evaluation on ALL tasks (not just train) to verify the improvements generalize. Use evaluation-only mode by rerunning the optimizer with `--max-iterations 0`, which records the baseline for the current file without generating fresh variants:

```bash
python3 skills/meta/agent-comparison/scripts/optimize_loop.py \
  --target skills/{target}/SKILL.md \
  --goal "{same goal}" \
  --benchmark-tasks {full-task-file}.json \
  --max-iterations 0 \
  --report optimization-report.html \
  --output-dir evals/final-check \
  --verbose
```

Compare final scores to the baseline to confirm net improvement. In beam mode, the final report and `results.json` also include:
- `beam_width`
- `candidates_per_parent`
- `holdout_check_cadence`
- per-iteration frontier metadata (`selected_for_frontier`, `frontier_rank`, `parent_iteration`)

---

## Step 9: Report the run

State the outcome in the final report: `{target}` improved `{baseline}` → `{best}` over `{iterations}` iterations, `{accepted}/{total}` candidates accepted, stop reason `{reason}`, and the change summaries. `results.json` in the run directory is the durable record.

---

## Gate

Optimization complete. Results reviewed. Cherry-picked improvements applied and verified against full task set. Outcome reported and `results.json` written.

---

## Current Reality Check

The current optimizer is in a solid state for:
- deterministic proof runs
- isolated live evaluation of existing registered skills
- short live optimization of `read-only-ops`, with the accepted description change now applied and validated against `references/read-only-ops-short-tasks.json`
- short live body optimization of `socratic-debugging`, with the accepted instruction-body update now applied and validated against `references/socratic-debugging-body-short-tasks.json`, now producing clean skill-triggered first-turn outputs instead of fallback chatter

One live-harness caveat remains:
- temporary renamed skill copies do not yet show reliable live trigger improvements through the dynamic command alias path

That caveat does not affect deterministic proof runs or live checks against existing registered skills, but it does mean the current system is stronger for optimizing real in-repo skills than arbitrary renamed temp clones.

For body optimization runs, the blind evaluator now rejects responses that:
- never triggered the target skill
- mention blocked skill/tool access
- fall back into generic "I'll guide you directly" behavior

---

## Optional Extensions

These are off by default. Enable explicitly when needed:
- **Multiple Runs**: Run each benchmark 3x to account for variance
- **Blind Evaluation**: Hide agent identity during quality grading
- **Extended Benchmark Suite**: Run additional domain-specific tests
- **Historical Tracking**: Compare against previous benchmark runs
