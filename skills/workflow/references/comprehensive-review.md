---
description: "Four-wave code review pipeline for large or high-risk changes."
effort: high
user-invocable: false
command: /comprehensive-review
allowed-tools:
  - Agent
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - TaskCreate
  - TaskUpdate
  - TaskList
  - EnterWorktree
routing:
  triggers:
    - comprehensive review
    - full code review
    - review everything
    - review and fix
    - thorough review
    - multi-agent review
    - complete code review
    - 20-agent review
    - 25-agent review
    - per-package review
    - 3-wave review
    - 4-wave review
    - adversarial review
    - "full code review"
    - "review all packages"
  pairs_with:
    - systematic-code-review
    - parallel-code-review
    - systematic-code-review
  complexity: Complex
  category: review
---

# Comprehensive Code Review v4 — Four-Wave Hybrid Architecture

Four-wave review with per-package deep analysis and adversarial challenge. Wave 0 auto-discovers packages and dispatches one language-specialist agent per package to read ALL code in that package. Wave 1 (12 foundation agents) runs in parallel with Wave 0 context. Wave 2 (10 deep-dive agents) receives Wave 0+1 findings for targeted analysis. Wave 3 (4-5 adversarial agents) challenges Wave 1+2 consensus. All findings are aggregated with wave-agreement labels, deduplicated, and auto-fixed.

**vs `/parallel-code-review`**: 3 agents (security, business, arch) — report only
**vs `/comprehensive-review`**: 25+ agents in 4 waves — per-package + cross-cutting + adversarial AND fix everything

---

## Flags

- **--review-only**: Skip fix phase, report only
- **--skip-wave0**: Skip Wave 0 per-package review (faster, less thorough)
- **--wave1-only**: Run only Wave 1 (12 agents), skip Wave 0, Wave 2, and Wave 3
- **--focus [files]**: Review only specified files instead of full diff
- **--severity [critical|high|medium|all]**: Only report/fix findings at or above severity
- **--org-conventions**: Pass organization-specific convention flags to reviewer-language-specialist

---

## Phase 0.5: STATIC ANALYSIS (Mandatory Prerequisite)

Run deterministic static analysis BEFORE dispatching any review agents. Linters catch syntactic issues that LLM agents miss. Findings feed into Wave 1 as input context.

**Step 1: Detect language and run linters**

```bash
# Go repos (check for go.mod)
if [ -f go.mod ]; then
    golangci-lint run ./... 2>&1 || true
    # Fallback if golangci-lint not installed
    if ! command -v golangci-lint &>/dev/null && [ -f Makefile ]; then
        make check 2>&1 || true
    fi
fi

# Python repos (check for pyproject.toml or setup.py)
if [ -f pyproject.toml ] || [ -f setup.py ]; then
    ruff check . 2>&1 || true
fi

# TypeScript repos (check for tsconfig.json)
if [ -f tsconfig.json ]; then
    npx tsc --noEmit 2>&1 || true
fi
```

**Step 2: Auto-fix trivial findings**

Auto-fixable findings (gofmt, goimports, ruff format) should be fixed BEFORE agent review begins — prevents agents from wasting time on formatting.

```bash
# Go: auto-fix formatting
if [ -f go.mod ]; then
    golangci-lint run --fix ./... 2>&1 || true
fi

# Python: auto-fix formatting
if [ -f pyproject.toml ] || [ -f setup.py ]; then
    ruff check --fix . 2>&1 || true
fi
```

**Step 3: Capture remaining findings for Wave 1 context**

Save non-auto-fixable lint findings to pass as context to all Wave 1 agents. Include these in every Wave 1 dispatch prompt as "Static analysis findings (pre-verified, not from LLM)."

**Gate**: Static analysis complete. Auto-fixes applied. Remaining findings captured. Proceed to Phase 1.

---

## Phase 1: SCOPE

**Goal**: Determine what to review, discover packages, initialize findings directory.

**Step 1: Identify changed files**

```bash
# For unstaged changes:
git diff --name-only

# For staged changes:
git diff --cached --name-only

# For PR context:
gh pr view --json files -q '.files[].path' 2>/dev/null

# Fallback: recent commits
git diff --name-only HEAD~1
```

**Step 2: Detect organization conventions**

```bash
REPO_TYPE=$(python3 ~/.claude/scripts/classify-repo.py --type-only 2>/dev/null || echo "personal")
```

If the repo belongs to a protected organization: set convention flags for the rest of this review. Wave 1 Agent 9 (`reviewer-language-specialist`) gets organization-specific flags appended. Log: "Organization conventions detected."

**Step 2b: Compute the review tier (work-proportional sizing)** — scale agents to diff scope, because a 3-file change does not earn a 27-agent four-wave review.

```bash
FILES=$(git diff --name-only | grep -c . || echo 0)
PKGS=$(git diff --name-only | sed 's#/[^/]*$##;s#^[^/]*$#.#' | sort -u | grep -c . || echo 0)
python3 scripts/right-size-review.py --files "$FILES" --packages "$PKGS"
```

The script returns `{tier, waves, agent_estimate, wave3_on_critical}`. Tier governs which waves run:

| Tier | Scope | Waves run | Agents |
|------|-------|-----------|--------|
| 1 | 1-5 files, 1 pkg | none here — use `/parallel-code-review` (3 agents) | 3 |
| 2 | 6-20 files, 1-2 pkg | Wave 1 only | 12 |
| 3 | 21-50 files, 3-5 pkg | Wave 1 + Wave 2 subset (5 of 10); Wave 3 only if a CRITICAL is found | 17 (+Wave 3 on CRITICAL) |
| 4 | 50+ files, 5+ pkg | Wave 1 + Wave 2 + Wave 3 (full) | 27 |

The larger of the file-tier and package-tier wins (a few files across many packages is still a wide change). **Escalate one tier on any CRITICAL finding**: if any wave surfaces a CRITICAL, run the next-higher tier's waves before finalizing — Tier 2 adds Wave 2; Tier 3 adds Wave 3. This is the safety valve: sizing reduces spend on small diffs without capping depth when a real risk appears.

When `--severity` or `--focus` flags are set, or no tier signal is computable, fall back to the full four-wave behavior (backwards-compatible default).

**Step 3: Initialize findings directory** — critical for surviving context compaction between waves

```bash
REVIEW_DIR="/tmp/claude-review/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$REVIEW_DIR"
echo "Review findings directory: $REVIEW_DIR"
```

All subsequent phases MUST write their findings to `$REVIEW_DIR/` and read prior wave findings from there.

**Step 4: Create task_plan.md**

Read `${CLAUDE_SKILL_DIR}/references/output-templates.md` for the task_plan.md template. Fill it in with actual file count, package count, detected org, and mode.

**Gate**: Files identified, packages discovered, findings directory created, plan created. Proceed to Phase 1b.

---

## Phase 1b: WAVE 0 DISPATCH — Per-Package Deep Review

**Skip if**: `--skip-wave0` or `--wave1-only` flag is set.

Read `${CLAUDE_SKILL_DIR}/references/wave-0-per-package.md` for:
- Package discovery commands by language
- Agent selection table
- The complete per-package agent dispatch prompt
- Batch size rules (max 10 agents per message)
- Wave 0 aggregate output format

**Dispatch**: One language-specialist agent per discovered package. Each reads ALL files in its package. Batches of up to 10 agents per message.

**Gate**: All per-package agents dispatched and completed. Proceed to Phase 1c.

---

## Phase 1c: WAVE 0 AGGREGATE

Collect Wave 0 findings into a per-package summary. Read `${CLAUDE_SKILL_DIR}/references/wave-0-per-package.md` for the aggregate output format.

**Step 1**: Collect all per-package agent outputs. Extract: package path, health rating, findings with severity.

**Step 2**: Identify cross-package patterns (e.g., "5 packages have inconsistent error handling"). These are especially valuable for Wave 1+2 agents.

**Step 3: Save Wave 0 findings to disk** — this step is mandatory

```bash
cat > "$REVIEW_DIR/wave0-findings.md" << 'WAVE0_EOF'
[Paste the complete Wave 0 Per-Package Findings Summary here]
WAVE0_EOF
echo "Saved Wave 0 findings: $(wc -l < "$REVIEW_DIR/wave0-findings.md") lines"
```

**Gate**: Wave 0 summary built, saved to `$REVIEW_DIR/wave0-findings.md`. Proceed to Phase 1.5.

---

## Phase 1.5: LIBRARY CONTRACT VERIFICATION (Go repos only)

**Skip for non-Go repos** (no `go.mod`).

**Goal**: Before Wave 1, verify that code assumptions about imported library behavior are actually true. Catches the LLM blind spot where agents reason from protocol knowledge instead of reading library source.

**Step 1: Scan changed code for library assumptions** — look for:
- Comments claiming library behavior ("X will retry", "Y returns error on Z")
- Error handling that assumes specific error types from imported libraries
- Control flow that depends on library lifecycle (reconnect, rebalance, retry)

**Step 2: Dispatch a single `golang-general-engineer` agent** (model: sonnet):

```
You are a library contract verifier. Your job is to read library source code
and verify whether the changed code's assumptions about library behavior are correct.

Changed files: [list from Phase 1]
Library assumptions found: [list from Step 1]

For each assumption:
1. Find the library in GOMODCACHE: cat $(go env GOMODCACHE)/path/to/lib@version/file.go
2. Read the relevant source code
3. Determine if the assumption is VERIFIED or UNVERIFIED
4. Provide evidence (file:line in library source)

Output a Library Contract Report as a markdown table:
| Assumption | Location | Verified? | Evidence |
```

**Step 3**: Save to `$REVIEW_DIR/library-contracts.md`. Include in every Wave 1 agent dispatch prompt alongside Wave 0 findings.

**Gate**: Library contract verification complete (or skipped). Proceed to Phase 2a.

---

## Phase 2a: WAVE 1 DISPATCH

**ALL 12 Wave 1 agent dispatches MUST be in ONE message for true parallelism.**

Read `${CLAUDE_SKILL_DIR}/references/wave-1-foundation.md` for:
- Complete agent roster (12 agents with focus areas)
- Architecture reviewer selection by language
- Standard agent prompt template (with Wave 0 context injection)
- Agent-specific prompt additions (mandatory caller tracing, assertion depth checks, etc.)

**Step 0: Load Wave 0 findings from disk** (guards against context compaction):

```bash
WAVE0_CONTEXT=$(cat "$REVIEW_DIR/wave0-findings.md" 2>/dev/null || echo "Wave 0 skipped — no per-package context available")
```

Inject `$WAVE0_CONTEXT` into each agent prompt. Also inject static analysis findings and library contract report (if Go repo).

Include in every Wave 1 and Wave 2 agent dispatch prompt: "The only valid review dispositions are FIX NOW, FIX IN FOLLOW-UP (with mandatory tracking artifact), or NOT AN ISSUE (with evidence). 'Acceptable', 'valid but deferred', and 'conservative' are NOT valid dispositions."

**Gate**: All 12 Wave 1 agents dispatched in a single message. Wait for all to complete. Proceed to Phase 2b.

---

## Phase 2b: WAVE 0+1 AGGREGATE

Read `${CLAUDE_SKILL_DIR}/references/wave-1-foundation.md` for the Wave 0+1 combined summary format.

**Step 1**: Collect all Wave 1 agent outputs. Extract findings with severity, file, description, fix.

**Step 2**: Build combined Wave 0+1 summary (Wave 0 per-package findings + Wave 1 cross-cutting findings). Identify overlapping findings between waves — duplicates validate both agents' analysis.

**Step 3: Save to disk** — mandatory:

```bash
cat > "$REVIEW_DIR/wave1-findings.md" << 'WAVE1_EOF'
[Paste ALL Wave 1 agent outputs]
WAVE1_EOF

cat > "$REVIEW_DIR/wave01-summary.md" << 'WAVE01_EOF'
[Paste the Wave 0+1 Findings Summary]
WAVE01_EOF

echo "Saved Wave 1 findings: $(wc -l < "$REVIEW_DIR/wave1-findings.md") lines"
echo "Saved Wave 0+1 summary: $(wc -l < "$REVIEW_DIR/wave01-summary.md") lines"
```

**Gate**: Wave 0+1 summary built, saved to `$REVIEW_DIR/wave01-summary.md`. Proceed to Phase 3a.

---

## Phase 3a: WAVE 2 DISPATCH

**Tier gate**: Skip Wave 2 entirely at Tier 1. At Tier 3, dispatch a **5-agent subset** (highest-signal deep-dive roles) instead of all 10 — unless a CRITICAL was found in Wave 0/1, which escalates Tier 3 to the full 10. Tiers 2 and 4 dispatch per their wave list (Tier 2 ends after Wave 1; Tier 4 runs all 10). The full 10 remain the default when no tier signal is present.

**ALL Wave 2 agent dispatches for the selected count MUST be in ONE message.**

Read `${CLAUDE_SKILL_DIR}/references/wave-2-deep-dive.md` for:
- Complete agent roster (10 agents with focus areas and Wave 1 context used)
- Standard agent prompt template (with Wave 0+1 context injection)
- Agent-specific context instructions

**Step 0: Load Wave 0+1 findings from disk**:

```bash
WAVE01_SUMMARY=$(cat "$REVIEW_DIR/wave01-summary.md" 2>/dev/null || echo "ERROR: Wave 0+1 summary not found — cannot proceed with Wave 2")
```

If the file is missing, re-read `$REVIEW_DIR/wave0-findings.md` and `$REVIEW_DIR/wave1-findings.md` and rebuild the summary before proceeding.

**Gate**: All 10 Wave 2 agents dispatched in a single message. Wait for all to complete. Proceed to Phase 3b.

---

## Phase 3b: WAVE 0+1+2 AGGREGATE

**Step 0: Reload all prior wave findings from disk**:

```bash
WAVE0=$(cat "$REVIEW_DIR/wave0-findings.md" 2>/dev/null || echo "")
WAVE1=$(cat "$REVIEW_DIR/wave1-findings.md" 2>/dev/null || echo "")
echo "Loaded Wave 0: $(echo "$WAVE0" | wc -l) lines, Wave 1: $(echo "$WAVE1" | wc -l) lines"
```

**Step 1**: Combine Wave 0 per-package, Wave 1 cross-cutting, and Wave 2 deep-dive findings.

**Step 2: Deduplicate** — if two or more agents flagged the same file:line, keep the highest severity, merge fix recommendations, note which agents found it (reinforces importance). Prefer Wave 2 fixes when they add Wave 0+1 context.

**Step 3: Classify by severity**:

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Security vulnerability, data loss risk, breaking change | Fix immediately |
| HIGH | Significant bug, logic error, silent failure, data race | Fix before merge |
| MEDIUM | Quality issue, missing test, comment rot, naming drift | Fix (auto) |
| LOW | Style preference, minor simplification, documentation | Fix (auto) |

**Step 4**: Build preliminary summary matrix. Read `${CLAUDE_SKILL_DIR}/references/output-templates.md` for the full matrix format.

**Step 5: Save to disk** — mandatory:

```bash
cat > "$REVIEW_DIR/wave2-findings.md" << 'WAVE2_EOF'
[Paste ALL Wave 2 agent outputs]
WAVE2_EOF

cat > "$REVIEW_DIR/wave012-summary.md" << 'WAVE012_EOF'
[Paste the preliminary summary matrix + all classified findings]
WAVE012_EOF

echo "Saved Wave 2 findings: $(wc -l < "$REVIEW_DIR/wave2-findings.md") lines"
echo "Saved Wave 0+1+2 summary: $(wc -l < "$REVIEW_DIR/wave012-summary.md") lines"
```

**Gate**: Wave 0+1+2 summary built, saved to `$REVIEW_DIR/wave012-summary.md`. Proceed to Phase 3c.

---

## Phase 3c: WAVE 3 DISPATCH — Adversarial Perspectives

**Tier gate**: Wave 3 runs unconditionally at Tier 4. At Tier 3 it runs **only if a CRITICAL finding exists** in the Wave 0+1+2 summary (the CRITICAL-escalation safety valve). Skip Wave 3 at Tiers 1-2 unless a CRITICAL escalated the tier upward. When no tier signal is present, Wave 3 runs (backwards-compatible default).

```bash
if grep -qi "CRITICAL" "$REVIEW_DIR/wave012-summary.md" 2>/dev/null; then
    echo "CRITICAL present — Wave 3 adversarial review required regardless of tier."
fi
```

**ALL Wave 3 agent dispatches MUST be in ONE message.**

Read `${CLAUDE_SKILL_DIR}/references/wave-3-adversarial.md` for:
- Complete agent roster (4-5 agents with adversarial roles)
- SAPCC conditional detection script
- Standard adversarial prompt template (with Wave 0+1+2 context injection)
- Agent-specific challenge focus instructions
- Wave agreement label definitions (UNANIMOUS / MAJORITY / CONTESTED)

**Step 0: Load Wave 0+1+2 findings from disk**:

```bash
WAVE012_SUMMARY=$(cat "$REVIEW_DIR/wave012-summary.md" 2>/dev/null || echo "ERROR: Wave 0+1+2 summary not found — cannot proceed with Wave 3")
```

If the file is missing, rebuild from `$REVIEW_DIR/wave0-findings.md`, `$REVIEW_DIR/wave1-findings.md`, and `$REVIEW_DIR/wave2-findings.md` before proceeding.

**Gate**: All Wave 3 agents dispatched in a single message (4-5 agents). Wait for all to complete. Proceed to Phase 3d.

---

## Phase 3d: FULL AGGREGATE — Wave Agreement Synthesis

**Step 0: Reload all prior wave findings from disk**:

```bash
WAVE0=$(cat "$REVIEW_DIR/wave0-findings.md" 2>/dev/null || echo "")
WAVE1=$(cat "$REVIEW_DIR/wave1-findings.md" 2>/dev/null || echo "")
WAVE2=$(cat "$REVIEW_DIR/wave2-findings.md" 2>/dev/null || echo "")
WAVE012=$(cat "$REVIEW_DIR/wave012-summary.md" 2>/dev/null || echo "")
```

**Step 1: Process Wave 3 challenges** (from `${CLAUDE_SKILL_DIR}/references/wave-3-adversarial.md`):
- AGREE → reinforces finding
- CHALLENGE → flag for human review
- DOWNGRADE → reduce severity if multiple Wave 3 agents agree
- DISMISS → drop if 2+ Wave 3 agents dismiss AND no Wave 1+2 agent rated CRITICAL

**Step 2**: Label every finding UNANIMOUS / MAJORITY / CONTESTED. Read `${CLAUDE_SKILL_DIR}/references/wave-3-adversarial.md` for the label criteria.

**Step 3**: Create a "Contested Findings" section listing each CONTESTED finding with both sides' evidence and recommended disposition.

**Step 4**: Build final summary matrix. Read `${CLAUDE_SKILL_DIR}/references/output-templates.md` for the full matrix format.

**Step 5: Save all findings to disk**:

```bash
cat > "$REVIEW_DIR/wave3-findings.md" << 'WAVE3_EOF'
[Paste ALL Wave 3 agent outputs]
WAVE3_EOF

cat > "$REVIEW_DIR/final-report.md" << 'REPORT_EOF'
[Paste the full summary matrix + all classified findings + agreement labels + contested section]
REPORT_EOF

echo "Saved Wave 3 findings: $(wc -l < "$REVIEW_DIR/wave3-findings.md") lines"
echo "Saved final report: $(wc -l < "$REVIEW_DIR/final-report.md") lines"
ls -la "$REVIEW_DIR/"
```

**Step 5a: Write the machine-readable finding counts** — the post-Wave-3 TOTAL row of the summary matrix you just built. These are the ROI inputs; Step 5b reads them. Use the deduplicated final counts, NOT grep over the report.

```bash
# Replace the three values with the TOTAL (post-Wave 3) CRITICAL/HIGH/MEDIUM
# finding counts from the matrix above (e.g. 2 3 5). Integers only,
# space-separated, one line.
printf '%s %s %s\n' "$CRITICAL_TOTAL" "$HIGH_TOTAL" "$MEDIUM_TOTAL" > "$REVIEW_DIR/findings-count.txt"
```

**Step 5b: Emit the rightsizing capture banner** — closes the review-tier-ROI loop (ADR: review-tier-roi). Read the deduplicated finding counts from Step 5a and re-run the sizer with `--findings` so `routing-decision-recorder` captures the per-tier yield. Without this line, `review-roi` reports insufficient data forever.

Read the counts from `findings-count.txt` — the TOTAL row, real findings. Do NOT `grep -c` the report: `grep -c` counts LINES containing the word, so the severity legend, matrix rows, and prose like "highly"/"medium-sized" all inflate the count.

```bash
# findings-count.txt holds three integers: CRITICAL HIGH MEDIUM (from Step 5a).
read -r C H M < "$REVIEW_DIR/findings-count.txt"
python3 scripts/right-size-review.py --files "$FILES" --packages "$PKGS" --findings "${C}C/${H}H/${M}M"
```

The printed `rightsizing: ... findings=NC/NH/NM` line is the capture banner. Append `tokens=` / `wall_clock_s=` to it from PR-A's telemetry envelope when those values are known; absent, they store as n/a.

**Step 6**: Show the matrix, agreement summary, and CONTESTED findings BEFORE proceeding to fixes. If `--review-only`, stop here.

For CONTESTED findings: "Wave 3 challenges these N findings. Fix them anyway, skip them, or decide individually?"

**Gate**: All findings classified, deduplicated, agreement-labeled, saved to `$REVIEW_DIR/final-report.md`. User informed of contested findings. Proceed to Phase 4.

---

## Phase 4: FIX

**NO DEFERRED FIXES. Fix EVERY finding. Zero "out of scope." Zero "will fix later."**

The only acceptable reason not to fix a finding: applying it breaks tests AND an alternative fix also breaks tests. Even then, BLOCKED items must be fewer than 10% of total findings.

**Step 0: Load findings from disk**:

```bash
cat "$REVIEW_DIR/final-report.md"
```

If missing, rebuild: `cat "$REVIEW_DIR/wave0-findings.md" "$REVIEW_DIR/wave1-findings.md" "$REVIEW_DIR/wave2-findings.md" "$REVIEW_DIR/wave3-findings.md"`

**Wave Agreement Handling**:

| Agreement Level | Fix Behavior |
|-----------------|-------------|
| UNANIMOUS | Fix without hesitation |
| MAJORITY | Fix, include Wave 3 challenge as code comment if challenge has merit |
| CONTESTED | Fix only if user approved during Phase 3d. Follow per-finding decisions. |

**Step 1: Create branch**

```bash
git checkout -b review-fixes/$(date +%Y%m%d-%H%M%S)
```

Or use `EnterWorktree` for full isolation.

**Step 2: Fix ALL findings by severity (CRITICAL first)**

Order: CRITICAL → HIGH → MEDIUM → LOW. Every level gets fixed — LOW is not optional.

For each fix:
1. State which finding is being addressed (wave, agent, severity, file:line)
2. Apply the fix
3. Verify it compiles/parses
4. Run relevant tests

```bash
# After each fix batch:
# Go:
go build ./... && go vet ./... && go test ./...
# Python:
python -m py_compile file.py && python -m pytest
# TypeScript:
npx tsc --noEmit && npx vitest run
# Generic:
make check 2>/dev/null || make test 2>/dev/null
```

**Step 3**: Apply simplifications (run `reviewer-code-simplifier` on already-fixed files) and docs fixes LAST — docs should reflect final code state.

**Step 4: If a fix breaks tests**:
1. Revert the specific fix
2. Try an ALTERNATIVE fix for the same finding
3. If alternative also fails: mark "BLOCKED — breaks tests, alternative also failed"
4. Continue with remaining fixes
5. BLOCKED items must be <10% of total

**Reject all deferral rationalizations**: "pre-existing bug", "needs follow-up PR", "architectural change required", "acceptable risk", "test-only code", "standard pattern" — if an agent found it, fix it.

**Step 5: Commit**

```bash
git add -A
git commit -m "fix: apply comprehensive review findings (N fixes across M files)"
```

**Gate**: ALL findings fixed. Tests pass. Zero deferred. Commit created on branch.

---

## Phase 5: REPORT

Write `comprehensive-review-report.md`. Read `${CLAUDE_SKILL_DIR}/references/output-templates.md` for the full report template.

Display findings directory path to user:

```
Review findings persisted at: $REVIEW_DIR/
  wave0-findings.md   — Per-package deep review results
  wave1-findings.md   — Foundation agent results (12 agents)
  wave01-summary.md   — Combined Wave 0+1 context for Wave 2
  wave2-findings.md   — Deep-dive agent results (10 agents)
  wave012-summary.md  — Combined Wave 0+1+2 context for Wave 3
  wave3-findings.md   — Adversarial challenge results (4-5 agents)
  final-report.md     — Aggregated, deduplicated, agreement-labeled
```

**Gate**: Report written, findings persisted. Display summary to user. Review complete.

---

## Error Handling

**Agent Times Out**: Report findings from completed agents immediately. Note which timed out. Offer to re-run separately. Proceed with partial results — keep the entire wave moving.

**Fix Breaks Tests**: Revert the specific fix. Try an ALTERNATIVE approach for the same finding. If alternative also fails, mark BLOCKED. Continue. BLOCKED must be <10%.

**Conflicting Fixes**: Prefer security fix over style. Prefer correctness over simplification. Wave 2 fixes with Wave 0+1 context generally have better understanding. Apply higher-severity agent's fix — never skip.

**No Changed Files**: Ask user "Which files would you like reviewed?" If "everything", scan all source files. Warn about scope.

**No Packages Discovered**: Skip Wave 0 silently. Proceed to Wave 1 with note: "Wave 0 skipped — no package structure detected." Wave 1 and Wave 2 still run normally.

**Too Many Packages (>30)**: Report count and batch requirement. Proceed with batching — quality matters more than speed. Consider filtering to packages containing changed files if reviewing a PR.

**Wave Finds No Findings**: Good news. Still dispatch subsequent waves with note: "Wave [N] found no issues. Perform independent analysis." Empty findings confirm quality.

---

## When to Use Which

| Situation | Use This |
|-----------|----------|
| Any PR, any language, full review+fix+challenge | `/comprehensive-review` (4 waves) |
| Fast review, skip per-package | `/comprehensive-review --skip-wave0` (3 waves: 1+2+3) |
| Quick review, 12 agents only | `/comprehensive-review --wave1-only` |
| Quick 3-reviewer check, no fix | `/parallel-code-review` |
| PR comment validation | `/pr-review-address-feedback` |
| Sequential deep dive | `systematic-code-review` skill |

---

## Native Workflow variant (option for wide reviews)

`comprehensive-review-workflow.js` (this directory) implements the same four waves as a deterministic native Workflow script. It is an **option, not a replacement** — this markdown flow remains the documented fallback and works without the Workflow tool.

Prefer the JS variant when tier >= 3 (or 5+ files / 2+ review categories). It scales waves to the right-sizing tier, returns schema-validated typed findings per wave (reusing the shapes in `skills/shared-patterns/schemas/`), passes Wave 1 findings to Wave 2 in-memory via `pipeline()`/`parallel()` instead of `$REVIEW_DIR/*.md` round-trips, runs a per-finding adversarial verify before synthesis, and bounds the Phase 4 fix loop by the native token `budget`. Use this markdown flow at lower tiers or when the Workflow tool is unavailable.
