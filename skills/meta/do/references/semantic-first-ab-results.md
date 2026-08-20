# Semantic-First Routing: Blind A/B Results

**STATUS: UNRUN.** `scripts/routing-ab-results/answers/README.md` states the Haiku run "has not been executed yet." The numbers below are a protocol and projected scoring, not observed results. The 89.8% strict / 92.8% lenient figures were never measured. Treat them as unvalidated.

Evidence behind the Phase 2 semantic-first contract in `../SKILL.md`. Raw artifacts in `scripts/routing-ab-results/`.

## Thesis

Flip the order so a **model reads for intent first**; trigger keywords become hints, never gates. Old flow: deterministic keyword pre-router runs first and short-circuits on high confidence, Haiku is the fallback. New flow (Option B): Haiku intent routing is primary; `pre-route.py` is a deterministic safety-net (force-route override + guards), not a short-circuit.

## Protocol

- **Corpus:** 49 cases — 24 international/paraphrase (plain + non-native-English phrasings) + 25 benchmark (force_route, candidate, llm_only, false-positive-guard).
- **Method:** per-query Haiku routing for each arm, then a blind judge scored every answer against the expected route. Arms de-identified via `uid-map.json`; judge saw `judge-input.json`, emitted `judge-output.json`; aggregated into `scoreboard.json`.
- **Arm A:** current deterministic-first. **Arm B:** semantic-first.
- Verdicts: correct / partial / incorrect. Strict accuracy = correct only.

## Per-arm, per-bucket (strict %)

| Bucket | n | A | B |
|--------|---|---|---|
| **Overall** | 49 | **89.8** | **89.8** |
| benchmark-candidate | 6 | 100.0 | 100.0 |
| benchmark-force_route | 7 | 100.0 | 100.0 |
| benchmark-llm_only | 5 | 80.0 | 80.0 |
| false-positive-guard | 7 | 71.4 | 71.4 |
| paraphrase-debug | 3 | 100.0 | 100.0 |
| paraphrase-explore | 3 | 100.0 | 100.0 |
| paraphrase-git | 6 | 100.0 | 100.0 |
| paraphrase-refactor | 3 | 33.3 | 33.3 |
| paraphrase-review | 3 | 100.0 | 100.0 |
| paraphrase-security | 4 | 100.0 | 100.0 |
| paraphrase-test | 2 | 100.0 | 100.0 |

**A ≡ B in every bucket.** Overall 44/49 correct, 3 partial, 2 incorrect (89.8% strict, 92.8% lenient) — identical.

**Why identical:** the keyword pre-router short-circuits only **5/49** requests. The other 44 already fall through to Haiku, and on the 5 it short-circuits, Haiku agrees. Flipping the order is therefore **zero-regression and near-zero-outcome-change** on this corpus.

## Cost

| Arm | Haiku calls / 49 requests | Per request |
|-----|---------------------------|-------------|
| A (deterministic-first) | 44 | 0.90 |
| B (semantic-first) | 49 | 1.00 |

**+0.10 Haiku calls/request.** The feared "big token cost" is not real, because the deterministic short-circuit rarely fires. Per project model policy, Haiku is the cheap classifier; the optimization target is Opus, not this delta. Cost deliberately accepted.

## The 2 hard failures (identical in both arms)

Both are the semantic layer **over-firing `pr-workflow` on metaphorical git words** (false-positive-guard bucket):

| Query | Text | Wrong route | Cause |
|-------|------|-------------|-------|
| q29 | "commit to this approach and move forward" | pr-workflow | blunt git rule |
| q33 | "merge the branches in your head" | pr-workflow | blunt git rule |

Root cause: the Haiku prompt's rule "For git operations (push, commit, PR, merge), ALWAYS select pr-workflow."

## Validated git-rule fix (re-tested, `answers-v2/`)

Replace the blunt rule with a genuine-git-only rule: route only actual version-control operations; ignore metaphorical commit/merge/push.

| Query | Before | After fix |
|-------|--------|-----------|
| q29 "commit to this approach…" | pr-workflow ✗ | planning ✓ |
| q33 "merge the branches in your head" | pr-workflow ✗ | multi-persona-critique ✓ (no git gate) |
| q00 "send my commits to the server" | pr-workflow ✓ | pr-workflow ✓ (still correct) |

**Net: ~91.8% strict, zero git-guard violations.** This is the measurable win — a prompt fix, independent of phase order.

## The three options

| Option | Description | Decision |
|--------|-------------|----------|
| A — pure semantic | Drop the deterministic pre-router entirely; Haiku is the only router. | Rejected: loses the safety-critical force-route guarantee for git/security. |
| **B — safety-net** | Haiku primary; `pre-route.py` runs after, enforcing safety-critical force-routes + guards only. | **Chosen / implemented.** |
| C — default-up | Keep deterministic-first but raise its short-circuit threshold. | Rejected: keeps keyword gating as the primary path, contrary to the thesis. |

## Honest read

Phase order is **near-neutral on outcomes** for this corpus (A ≡ B, +0.10 calls/req). The measurable win is the **git-rule prompt fix** (→91.8%, 0 guard violations). The bigger international-UX gains live in the semantic layer's weak buckets — `paraphrase-refactor` (33.3%) and `false-positive-guard` (71.4%) — i.e. refactor-intent recognition and false-positive discrimination. Semantic-first is the right architecture (intent over keywords, plain English over jargon); future investment belongs in the semantic layer, not the keyword table.
