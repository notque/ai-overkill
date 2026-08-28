# Evolution History -- Proposal Ledger and Distilled Lessons

> **Scope**: Distilled outcomes from evolution cycles 2026-05-09 through 2026-05-15. Prevents re-proposing failed ideas and preserves the decision criteria they produced. Load this reference during Phase 1 DIAGNOSE (Step 5: check prior outcomes) and Phase 2 PROPOSE (dedup against history).

---

## Distilled Lessons (from failed/shelved proposals)

These are the reusable decision criteria extracted from proposal evaluations. Each was validated by 3-persona critique.

| Lesson | Source | Score |
|--------|--------|-------|
| Skills need active routing triggers to receive traffic; CLAUDE.md guardrails and existing skills cover deployment decisions | execution-risk-manager (WEAK 1.33) |
| Skills need an existing workflow to attach to; unused skills have no adoption path | incident-postmortem-engine (WEAK 1.33) |
| Optimization skills need concrete cost evidence; "might save money" is not justification | prompt-optimization-lab (WEAK 1.0) |
| Timeout investigation needs a reproduction case before logging is the right lever | hook-timeouts-investigation (MODERATE 2.0) |
| Pure doc fixes score low in critique; bundle them with functional fixes in the same PR | fix-routing-guide-dead-ref (MODERATE 1.67) |
| Investigate hook logic before proposing cleanup; stale by date is not stale by reference | cleanup-adr-session-json (WEAK 1.0) |
| Premature documentation of unimplemented systems is derivative, not authoritative; defer until implementation exists | sprite-pipeline-phase1-reference (WEAK 1.33) |
| Improving an existing mechanism beats adding new ones; one-line quality fixes can be the unanimous outlier | hook-solution-field (STRONG 9/9, PR #644) |
| Advisory hooks must not mutate git state; sync enforcement belongs at the commit/push boundary (PreToolUse gate) not the write boundary (PostToolUse side-effect) | hook-auto-stage-index (WEAK 1.33) |
| Before padding triggers to pass a threshold, check whether the threshold itself is wrong for narrow-scope agent helpers | boost-undertriggered-entries (MODERATE 1.67) |

---

## Shelved Proposals -- Reactivation Conditions

Proposals shelved with explicit conditions for re-proposal. Check these before re-proposing the same idea.

| Proposal | Score | Condition for Reactivation |
|----------|-------|---------------------------|
| voice-gate-registration | MODERATE 2.0 | Fix hardcoded path `~/pgh/vexjoy-agent/scripts/scan-ai-patterns.py` to use relative or env-based resolution, validate with smoke-test harness |
| mcp-health-check-registration | WEAK 2/9 | Staging test showing clean backoff/unblock cycles before production registration |
| boost-undertriggered-entries | MODERATE 1.67 | Determine whether trigger minimum threshold should differ for narrow-scope agent helpers (e.g. threshold 3) vs user-facing skills (threshold 5) before adding triggers to avoid routing collisions |
| reference-loading-gate-registration | MODERATE 5/9 | **RESOLVED**: session dedup added, promoted to STRONG 3.0, shipped PR #647 |
| stale-stub-hook-cleanup | WEAK 4/9 | **RESOLVED**: grep confirmed no settings.json refs, stubs deleted, shipped PR #647 |

---

## Rejected Proposals -- Do Not Re-Propose

| Proposal | Reason | Reopen Condition |
|----------|--------|------------------|
| posttool-bash-injection-scan | Unanimous REJECT (0/9). Heuristic misses heredocs/rsync; no injection incidents recorded | Injection incident appears in learning DB |

---

## Cycle Summaries

| Date | Proposals | Built | Winners | Shelved | Focus | PRs |
|------|-----------|-------|---------|---------|-------|-----|
| 2026-05-09 | 5 | 2 | 2 | 3 | general (first cycle) | #618 |
| 2026-05-10 | 5 | 2 | 2 | 3 | general (follow-up) | #630, #631 |
| 2026-05-11 | 5 | 2 | 2 | 3 | hook system + joy-check | #638, #639 |
| 2026-05-14 | 5 | 1 | 1 | 4 | general | #644 |
| 2026-05-15 | 5 | 3 | 3 | 2 | hook harness + cleanup | #646, #647 |
| 2026-05-16 | 3 | 1 | 1 | 2 | infrastructure integrity (INDEX.json sync) | #653 |

**Win rate**: 11 winners / 28 proposals = 39.3%. Average winning score: 2.83/3.0.

---

## Winners Shipped

| Winner | Cycle | Consensus | PR | Impact |
|--------|-------|-----------|----|--------|
| hook-lifecycle-validator | 2026-05-09 | STRONG 3.0 | #618 | Structured [PASS]/[FAIL] output for hook scripts |
| skill-index-automation | 2026-05-09 | STRONG 3.0 | #618 | PostToolUse hook auto-regenerates INDEX.json on SKILL.md edits |
| routing-drift-diag | 2026-05-10 | STRONG 3.0 | #630 | diagnose-scripts.md Step 4 calls check-routing-drift.py |
| skill-index-hook deployment | 2026-05-10 | STRONG 3.0 | #631 | posttooluse-sync-skill-index.py wired into settings.json |
| bound unlimited-timeout hooks | 2026-05-11 | STRONG 3.0 | #638 | 11 hooks given explicit timeout bounds |
| PostToolUse joy-check warn | 2026-05-11 | STRONG 3.0 | #639 | joy-check warning hook on Write/Edit |
| hook solution field improvement | 2026-05-14 | STRONG 9/9 | #644 | Solution includes first 80 chars of error message |
| smoke-test-hooks.py harness | 2026-05-15 | STRONG 3.0 | #646 | Reads hooks from settings.json, fires with mock stdin, asserts exit codes |
| reference-loading-gate session dedup | 2026-05-15 | STRONG 3.0 | #647 | Warns once per component subtree per session |
| stale stub hook deletion | 2026-05-15 | STRONG 2.67 | #647 | 3 stub hooks removed after settings.json verification |
| INDEX.json sync gate + CI wire | 2026-05-16 | STRONG 3.0 (reasoned) | #653 | pretool-index-sync-check.py blocks commit when SKILL.md staged without INDEX.json; validate-index-integrity.py added to CI lint |
