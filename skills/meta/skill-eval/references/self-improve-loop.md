# Self-Improvement Loop

A closed-loop protocol for improving skills through variant generation, blind A/B testing, and empirical promotion. The loop takes an existing skill, generates targeted variants that each change one thing, tests them against the original on identical test cases, and promotes the winner only if it clears a quantitative bar.

This is the methodology reference for `skill-eval` Mode E (Self-improvement loop). The SKILL.md orchestrates; this file provides the detailed protocol.

---

## Prerequisites

Before entering the loop, confirm:

1. The target skill has a valid `SKILL.md` (run `python3 -m scripts.skill_eval.quick_validate <path/to/skill>`)
2. At least 3 test cases exist — either in `evals/` or you will create them in Phase 1
3. `docs/what-didnt-work.md` is readable — it holds the hypotheses already refuted for this skill
4. No prior failed hypothesis for this skill covers the same change (check Phase 1, Step 4)

---

## Phase 1: BASELINE

**Goal**: Establish the current skill's measurable performance so every variant has a bar to clear.

**Step 1: Select the target skill**

The user provides the skill name, or auto-detect from recent routing failures:

```bash
# Weakest routes by error rate — the skills worth improving first
python3 ~/.claude/scripts/learning-db.py route-health
python3 ~/.claude/scripts/learning-db.py route-stats --by skill
```

Confirm the skill directory and validate structure:

```bash
python3 -m scripts.skill_eval.quick_validate skills/{skill-name}
```

**Step 2: Run baseline test cases**

If `evals/` contains test cases for this skill, use them. Otherwise, create 3-5 realistic test prompts following the eval set quality guidance in the parent SKILL.md (rich, detailed prompts — not abstract one-liners).

Run the baseline:

```bash
python3 -m scripts.skill_eval.run_eval \
  --eval-set evals/{skill-name}-evals.json \
  --skill-path skills/{skill-name} \
  --runs-per-query 3 \
  --verbose
```

Save baseline results to `self-improve-workspace/{skill-name}/baseline/`.

**Step 3: Record baseline metrics**

Capture:
- Per-test-case pass/fail and trigger rates
- Output quality scores (if grader assertions exist)
- Token cost per run (from eval output)
- The skill's dispatch count and error rate from routing telemetry:

```bash
python3 ~/.claude/scripts/learning-db.py route-stats --by skill
```

**Step 4: Check for prior attempts**

Read the negative-results registry for previous self-improvement attempts on this skill to avoid re-testing failed hypotheses:

```bash
grep -n -i "{skill-name}" docs/what-didnt-work.md
ls evals/{skill-name}/ 2>/dev/null
```

If a hypothesis was already tested and lost, do not regenerate it in Phase 2.

**Gate**: Baseline established with at least 3 test cases. Metrics recorded. Prior attempts reviewed. Proceed only when gate passes.

---

## Phase 2: HYPOTHESIZE

**Goal**: Identify specific, testable improvements — each changing exactly one thing.

**Step 1: Analyze the skill**

Read the target skill's SKILL.md end-to-end. For each of these dimensions, note whether there is room for improvement:

| Dimension | What to look for |
|-----------|-----------------|
| Phase ordering | Would reordering phases improve logical flow? Does a later phase depend on context established too late? |
| Constraint placement | Are constraints inline at the point of failure, or buried in a preamble 200 lines away? |
| Failure mode specificity | Are failure modes concrete with before/after examples, or vague warnings? |
| Gate strictness | Are gates too loose (letting bad work through) or too strict (blocking valid work)? |
| Description accuracy | Does the frontmatter description trigger for the right queries and reject the wrong ones? |
| Reference loading | Are references loaded at the right phase, or too early (wasting routing-time tokens) or too late (missing context when needed)? |
| Instruction density | Are instructions lean (motivation + action) or bloated (redundant explanations, excessive examples)? |

**Step 2: Generate 2-3 variant hypotheses**

Each hypothesis must:
- Target exactly ONE dimension from the table above (isolation principle)
- State the change, the expected improvement, and the reasoning
- Be falsifiable — if the variant doesn't improve the target metric, the hypothesis is wrong

Format each hypothesis:

```
Hypothesis A: Moving the error-handling constraint from the preamble to Phase 2
  (where errors actually occur) should improve error-handling quality in outputs
  because constraints at point-of-use are more effective than front-loaded rules.

Hypothesis B: Replacing the vague anti-pattern "don't over-engineer" with a
  concrete before/after example should reduce over-engineering in outputs because
  specific examples are more actionable than abstract warnings.
```

**Example using a real toolkit skill** — improving the `quick` skill's description:

```
Hypothesis A: Shortening the description from "Zero-ceremony inline execution
  for 3 or fewer file edits" to "Quick inline edits, 1-3 files, no ceremony"
  should improve trigger rate for casual phrasing ("just fix this quick") because
  the shorter form matches how users actually talk.
```

**Step 3: Validate hypotheses against prior attempts**

Cross-reference each hypothesis with the registry entries read in Phase 1 Step 4. Drop any hypothesis that duplicates a previously-failed attempt.

**Gate**: 2-3 hypotheses generated, each targeting one dimension, each with clear expected outcome, none duplicating prior failures. Proceed only when gate passes.

---

## Phase 3: GENERATE VARIANTS

**Goal**: Create minimal-diff variants of the skill, one per hypothesis.

**Step 1: Create variant directory structure**

```bash
mkdir -p self-improve-workspace/{skill-name}/variants/{variant-letter}
```

**Step 2: Generate each variant**

For each hypothesis, copy the original SKILL.md and apply ONLY the change that hypothesis targets:

```bash
cp skills/{skill-name}/SKILL.md \
   self-improve-workspace/{skill-name}/variants/a/SKILL.md
```

Edit the copy to implement Hypothesis A. The diff between original and variant should be small and targeted — if you find yourself rewriting large sections, the hypothesis is too broad. Split it.

Name convention: `{skill-name}-variant-{letter}` (e.g., `quick-variant-a`, `roast-variant-b`).

**Step 3: Verify variant diffs are minimal**

For each variant, confirm the change is isolated:

```bash
diff skills/{skill-name}/SKILL.md \
     self-improve-workspace/{skill-name}/variants/a/SKILL.md
```

If the diff touches more than the targeted dimension, the variant is contaminated. Fix it before proceeding — multi-variable changes make it impossible to attribute improvement.

**Step 4: Validate variant structure**

```bash
python3 -m scripts.skill_eval.quick_validate \
  self-improve-workspace/{skill-name}/variants/a
```

Each variant must pass structural validation. A variant that breaks frontmatter parsing is not a valid test.

**Gate**: All variants created, diffs are small and targeted, structural validation passes. Proceed only when gate passes.

---

## Phase 4: BLIND A/B TEST

**Goal**: Run identical test cases through original and every variant, grade blind, collect scores.

**Step 1: Run each variant through the same test cases**

For each variant, run the EXACT same eval set used in Phase 1:

```bash
# Original (already done in Phase 1, reuse results)
# Variant A
python3 -m scripts.skill_eval.run_eval \
  --eval-set evals/{skill-name}-evals.json \
  --skill-path self-improve-workspace/{skill-name}/variants/a \
  --runs-per-query 3 \
  --verbose
```

Save results to `self-improve-workspace/{skill-name}/results/variant-a/`.

Use isolated worktree agents when running variants so they don't contaminate each other or the original skill's state. Each variant runs in its own subprocess.

**Step 2: Blind evaluation**

Spawn a grader subagent using `agents/comparator.md` for paired comparison. For each test case, the comparator receives:
- Output from the original (labeled "Output 1")
- Output from the variant (labeled "Output 2")
- Assignment of labels is randomized per test case — the comparator must not know which is original

The comparator scores on the rubric dimensions from the parent SKILL.md (correctness, error handling, idioms, documentation, testing — or domain-appropriate dimensions).

**Step 3: Collect paired scores**

For each test case and each variant, record:

| Test Case | Original Score | Variant Score | Winner | Margin |
|-----------|---------------|---------------|--------|--------|
| case-1    | 4.2           | 4.5           | Variant | +0.3   |
| case-2    | 3.8           | 3.6           | Original | -0.2  |
| case-3    | 4.0           | 4.1           | Variant | +0.1   |

Save to `self-improve-workspace/{skill-name}/results/variant-a/scores.json`.

**Gate**: All variants tested on all test cases. Paired scores collected. Blind evaluation complete. Proceed only when gate passes.

---

## Phase 5: PROMOTE OR KEEP

**Goal**: Make a data-driven decision, record the outcome either way.

**Step 1: Calculate win rates**

For each variant:

```
win_rate = (test cases where variant beats original) / (total test cases)
max_regression = max drop on any single rubric dimension across all test cases
```

**Step 2: Apply promotion criteria**

A variant wins if and only if BOTH conditions are met:
1. **Win rate >= 60%** — variant beats original on a majority of test cases
2. **No dimension regresses by more than 1 point** — a variant that improves Phase 3 output but breaks Phase 1 output is not a winner

If multiple variants qualify, promote the one with the highest win rate. On ties, prefer the variant with the smallest diff (simpler change).

**Step 3a: If winner found — PROMOTE**

1. Replace the original SKILL.md with the winning variant:

```bash
cp self-improve-workspace/{skill-name}/variants/{winner}/SKILL.md \
   skills/{skill-name}/SKILL.md
```

2. Validate the replacement:

```bash
python3 -m scripts.skill_eval.quick_validate skills/{skill-name}
```

3. Record the win in the eval artifact: write the hypothesis, win rate `{win_rate}%` (`{wins}/{total}` cases), and what changed to `evals/{skill-name}/README.md`. The commit message below carries the same figures.

4. Commit on a feature branch:

```bash
git add skills/{skill-name}/SKILL.md
git commit -m "improve({skill-name}): {what changed} — A/B winner ({win_rate}%)"
```

5. If the skill's frontmatter `description` changed, regenerate the routing index:

```bash
python3 scripts/generate-skill-index.py
```

**Step 3b: If no winner — KEEP original**

1. Record the negative result in `docs/what-didnt-work.md`, newest first, in the registry's six-field format. This is what prevents re-testing the same hypothesis:

```
## {YYYY-MM-DD} self-improve {skill-name} variant-{letter}
- Expectation: {hypothesis summary}
- What happened: win rate {win_rate}% ({wins}/{total} cases)
- Evidence: evals/{skill-name}/
- Decision: rejected — {why it lost}
```

2. Keep the original SKILL.md unchanged.

3. If all variants lost, report to the user: the skill's current form held up against all tested alternatives. This is a valid outcome — not every skill needs changing.

**Gate**: Decision made (promote or keep). Outcome recorded — a win in `evals/{skill-name}/`, a loss in `docs/what-didnt-work.md`. If promoted, replacement validated and committed. Proceed only when gate passes.

---

## Patterns to Detect and Fix

| Failure Mode | Why it's wrong | What to do instead |
|-------------|---------------|-------------------|
| Changing multiple things per variant | Can't attribute improvement to any single change | One hypothesis, one change, one variant |
| Testing without baseline | No basis for comparison; can't calculate win rate | Always run Phase 1 first |
| Promoting on vibes | "This one feels better" is not evidence | Require quantitative win rate >= 60% |
| Ignoring regressions | A variant that improves one dimension but breaks another nets negative | Check max regression on every dimension |
| Re-testing failed hypotheses | Wastes time on changes already proven ineffective | Read `docs/what-didnt-work.md` before generating variants |
| Large diffs between original and variant | Multiple changes confound results; can't learn what worked | Keep diffs minimal and targeted |
| Testing with too few cases | 1-2 test cases give unstable win rates | Minimum 3 test cases for any comparison |
| Skipping blind evaluation | Knowing which is "yours" biases grading | Randomize labels for the comparator |

---

## Integration Points

**Negative-results registry** — Every loss goes to `docs/what-didnt-work.md` with an evidence location, every win to `evals/{skill-name}/`. Both are read at Phase 1 Step 4 of the next run, which is what stops a refuted hypothesis coming back.

**Routing telemetry** — `learning-db.py route-health` and `route-stats --by skill` name which skills carry traffic and which fail on it, so the loop starts on a skill that matters.

**Routing table** — If a promoted variant changes the skill's frontmatter `description`, the routing index must be regenerated:

```bash
python3 scripts/generate-skill-index.py
```

**skill-creator enrichment loop** — The self-improvement loop complements the enrichment loop in `skill-creator`. Enrichment adds new reference content; self-improvement optimizes the existing SKILL.md structure. Run enrichment first when the skill lacks depth, then self-improvement when the skill has content but suboptimal structure.

---

## Workspace Layout

```
self-improve-workspace/{skill-name}/
├── baseline/                  # Phase 1 eval results
│   ├── eval-results.json
│   └── metrics.json
├── hypotheses.md              # Phase 2 documented hypotheses
├── variants/
│   ├── a/
│   │   └── SKILL.md           # Variant A (one change)
│   ├── b/
│   │   └── SKILL.md           # Variant B (different change)
│   └── c/
│       └── SKILL.md           # Variant C (if needed)
├── results/
│   ├── variant-a/
│   │   ├── eval-results.json
│   │   └── scores.json        # Paired comparison scores
│   ├── variant-b/
│   │   └── ...
│   └── summary.json           # Win rates, promotion decision
└── decision.md                # Final decision + reasoning
```

---

## Example: Improving the `quick` Skill

Walk-through of the full loop applied to a real toolkit skill.

**Phase 1 — Baseline**: Run 4 test cases against `skills/process/quick/SKILL.md`. Baseline trigger rate: 75% (3/4 cases trigger correctly). One failure: the query "just tweak the import line" does not trigger `quick --trivial`.

**Phase 2 — Hypothesize**:
- Hypothesis A: Add "tweak" and "quick fix" to the description's trigger vocabulary. Expected: trigger rate improves for casual phrasing.
- Hypothesis B: Reorder the phases so the file-count check happens before loading context. Expected: faster rejection of out-of-scope requests (more than 3 files).

**Phase 3 — Generate**: Create `quick-variant-a` (description change only) and `quick-variant-b` (phase reorder only). Diffs are 2 lines and 8 lines respectively.

**Phase 4 — Blind A/B**: Run all 4 test cases through both variants. Comparator grades blind.

**Phase 5 — Decide**:
- Variant A: wins 3/4 cases (75% win rate), no regressions. Promoted.
- Variant B: wins 1/4 cases (25% win rate). Recorded as a negative result in `docs/what-didnt-work.md`.

Commit: `improve(fast): add casual trigger vocabulary — A/B winner (75%)`
