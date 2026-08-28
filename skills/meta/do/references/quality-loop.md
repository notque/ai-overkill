# Quality Loop Pipeline

The canonical pipeline for all Medium+ code modifications. The quality-loop is the **outer orchestration** — it wraps the agent+skill that `/do` Phase 2 selected. The agent provides domain expertise. The quality-loop adds every verification, review, and lifecycle gate around it.

```
quality-loop (14 phases)
 0  ADR             — architectural decision record (creation requests)
 1  PLAN            — task_plan.md with approach + acceptance criteria
 2  IMPLEMENT       — agent+skill builds the change (worktree isolated)
 3  TEST            — deterministic: lint, tests, build, vet
 4  REVIEW          — 3 parallel reviewers (security, domain, architecture)
 5  INTENT VERIFY   — adversarial: does the diff match the original request?
 6  LIVE VALIDATE   — Playwright: does it render correctly? (web projects only)
 7  FIX             — fresh agent fixes CRITICALs (separate commits)
 8  RETEST          — re-run tests after fixes (loop to 7, max 3)
 9  PR              — push branch, create PR with findings in body
10  CODEX REVIEW    — cross-model second opinion via Codex CLI (GPT-5.4)
11  ADR RECONCILE   — compare ADR decision vs what was actually built
12  RECORD          — capture learnings, graduate review findings
13  CLEANUP         — move ADR to completed, clear artifacts, clean worktree
```

## When This Applies

- All code modification requests at Medium+ complexity (implementation, bug fix, feature addition, refactoring)
- Does NOT apply to: Trivial (direct), Simple (quick/fast), review-only tasks, research, debugging-only, content creation
- Force-route skills (go-patterns, feature-lifecycle, etc.) are used INSIDE PHASE 2, not excluded from the loop

## Task Tracking

At pipeline start, create a task for each phase using TaskCreate. This makes progress visible to the user and provides a checklist the orchestrator follows.

```
TaskCreate: "PHASE 0: ADR"           — "Write architectural decision record"
TaskCreate: "PHASE 1: PLAN"          — "Write task_plan.md with approach + acceptance criteria"
TaskCreate: "PHASE 2: IMPLEMENT"     — "Agent+skill builds the change"
TaskCreate: "PHASE 3: TEST"          — "Run deterministic test suite"
TaskCreate: "PHASE 4: REVIEW"        — "3 parallel reviewers (security, domain, architecture)"
TaskCreate: "PHASE 5: INTENT VERIFY" — "Adversarial: does diff match request?"
TaskCreate: "PHASE 6: LIVE VALIDATE" — "Playwright validation (web projects only)"
TaskCreate: "PHASE 7: FIX"           — "Fix CRITICAL findings"
TaskCreate: "PHASE 8: RETEST"        — "Re-run tests after fixes"
TaskCreate: "PHASE 9: PR"            — "Push branch, create PR"
TaskCreate: "PHASE 10: CODEX REVIEW" — "Cross-model second opinion"
TaskCreate: "PHASE 11: ADR RECONCILE"— "Compare decision vs implementation"
TaskCreate: "PHASE 12: RECORD"       — "Capture learnings"
TaskCreate: "PHASE 13: CLEANUP"      — "Move ADR to completed, clear artifacts"
```

As each phase begins, mark it `in_progress`. When it completes, mark it `completed`. If a phase is skipped (e.g., PHASE 0 for non-creation requests, PHASE 6 for non-web projects), mark it `completed` with a note "skipped — not applicable."

This tracking is mandatory — it's how the user knows where the pipeline is and what's left.

## Pipeline Phases

### PHASE 0 — ADR

Write an architectural decision record before touching code. Only for creation requests ("create", "new", "scaffold", "build").

- Write ADR at `adr/{kebab-case-name}.md` with: Context, Decision, Consequences, Implementation Checklist
- Register via `python3 ~/.claude/scripts/adr-query.py register adr/{name}.md`
- The implementation checklist becomes the verification target for PHASE 10

For non-creation requests (bug fixes, refactoring, feature additions to existing components): if an active ADR session exists (`.adr-session.json`), load it for context. No new ADR needed.

**Gate:** For creation requests: ADR exists and is registered. For non-creation: no gate. Proceed to PHASE 1.

### PHASE 1 — PLAN

Write the execution plan before implementation.

- Create `task_plan.md` with: approach, files to modify, acceptance criteria, risks
- The plan feeds into PHASE 2 (what to implement), PHASE 5 (what to verify), and PHASE 10 (what was promised)

**Gate:** `task_plan.md` exists with acceptance criteria. Proceed to PHASE 2.

### PHASE 2 — IMPLEMENT

Dispatch the agent+skill that `/do` Phase 2 selected with one implementation worktree. The quality-loop does not choose the agent — it uses whatever the router already picked (e.g., `golang-general-engineer` + `go-patterns` for Go work, `python-general-engineer` + `python-quality-gate` for Python work).

- Run `worktree_capacity.py --strict` from `references/worktree-rules.md` before checkout creation.
- Create feature branch in worktree
- Reuse this checkout for correction rounds. Dispatch read-only reviewers from the repository root using the committed candidate; review allocates no checkout.
- Agent uses its own skill and reference files for domain-specific implementation
- Agent commits on the feature branch
- Inject worktree rules into agent prompt (see `references/worktree-rules.md`)
- Include "commit your changes on the branch" in agent prompt

**State artifact:** Before proceeding, write `quality-loop-state.md` in the worktree root:
```
agent: <domain-agent-name>
skill: <skill-name>
request: <original user request verbatim>
branch: <feature-branch-name>
```
This artifact is read by PHASE 5 (intent verification), PHASE 7 (fix agent selection), and PHASE 10 (ADR reconciliation).

**Gate:** Agent commits exist on feature branch AND `quality-loop-state.md` written; proceed to PHASE 3. If agent failed to commit, halt and report.

### PHASE 3 — TEST

**Verification means execution, not reasoning.** Run the command. Do not reason about whether the command would pass. Do not summarize the expected output. Execute the check, paste the exit code, paste the relevant output. A verification phase that produces a verdict without an observed tool result is not a verification — it is a guess with a rigor aesthetic.

Run deterministic test suite. Language auto-detected from changed files.

Detection and commands:
- Go files changed: `go test ./...` (from repo root), `go vet ./...`
- TypeScript files changed: `tsc --noEmit`, then `npx vitest run` if vitest config exists
- Python files changed: `ruff check . --config pyproject.toml`, `ruff format --check . --config pyproject.toml`, `python -m pytest` if pytest config exists
- If Playwright config exists: `npx playwright test`
- If Makefile has `check` target: `make check`
- **Toolkit agent/skill files changed** (`agents/*.md` or `skills/*/SKILL.md`): run structure validation:
  - `python3 scripts/validate-references.py --agent {name}` for each changed agent
  - `python3 -m pytest scripts/tests/test_reference_loading.py -k {name}` for reference loading tests
  - These catch broken reference declarations before merge — a soft CLAUDE.md instruction converted into a deterministic gate

Run ALL applicable test suites — a change may touch multiple languages.

Capture: exit codes, failure output, test counts.

**Gate:** Record results. If tests fail, mark failures as CRITICAL findings for PHASE 7. Proceed to PHASE 4.

### PHASE 4 — REVIEW

Dispatch 3 parallel review agents against the diff (feature branch vs main):

1. **Security reviewer** (reviewer-system) — injection vectors, auth issues, secret exposure, input validation
2. **Business logic reviewer** (reviewer-domain) — correctness, edge cases, domain rules, error handling
3. **Architecture reviewer** (reviewer-perspectives) — design patterns, coupling, API contracts, performance

Each reviewer produces findings as:
- CRITICAL: Must fix before merge
- IMPROVEMENT: Should fix, not blocking
- POSITIVE: Good patterns to reinforce

**Gate:** All 3 reviewers complete. Proceed to PHASE 5.

### PHASE 5 — INTENT VERIFY

**Verification means execution, not reasoning.** Run the command. Do not reason about whether the command would pass. Do not summarize the expected output. Execute the check, paste the exit code, paste the relevant output. A verification phase that produces a verdict without an observed tool result is not a verification — it is a guess with a rigor aesthetic.

Adversarial verification: does the diff accomplish what the user actually asked for?

Dispatch one read-only verifier agent that reads the original user request from `quality-loop-state.md` (written in PHASE 2) and compares it against the actual diff. The verifier answers:

1. Does the diff accomplish what the user requested?
2. Are there aspects of the request that the implementation missed?
3. Are there changes in the diff that go beyond what was requested?

Any gap between request and implementation is a CRITICAL finding — because passing tests don't prove the code does what the user actually asked for. This implements the verifier pattern from PHILOSOPHY.md: "planner (read-only), executor (full access), verifier (read-only, adversarial intent)."

**Gate:** Intent verification complete. Proceed to PHASE 6.

### PHASE 6 — LIVE VALIDATE

**Verification means execution, not reasoning.** Run the command. Do not reason about whether the command would pass. Do not summarize the expected output. Execute the check, paste the exit code, paste the relevant output. A verification phase that produces a verdict without an observed tool result is not a verification — it is a guess with a rigor aesthetic.

Behavioral verification for web projects. **Skip if not a web project.**

When the project has a dev server (detected by: `package.json` with `dev` or `start` script, Hugo config, or `docker-compose.yml` with web service), spin up the dev server and use Playwright to visit changed routes/pages.

- Only run when Playwright is installed AND a dev server config exists
- Timeout: 60 seconds for server startup, 30 seconds per page
- If dev server fails to start, skip with a warning (not a CRITICAL)
- Uses the `e2e-testing` or `wordpress-live-validation` skill methodology
- Playwright test failures are IMPROVEMENT-level unless they reproduce a PHASE 3 failure, in which case CRITICAL

**Gate:** Collect all findings from PHASES 3-6. If any CRITICAL findings, proceed to PHASE 7. If no CRITICALs, skip to PHASE 9.

### PHASE 7 — FIX

For each CRITICAL finding, dispatch a fresh domain agent to fix it.

- Each fix is a separate commit with a message referencing the finding
- Read `quality-loop-state.md` to determine which domain agent PHASE 2 used — do not rely on session memory
- Fresh agent context — not the same agent that made the mistake — because the original agent has anchoring bias toward its own implementation
- Include the specific CRITICAL finding text in the agent prompt

**Gate:** All CRITICAL findings addressed with commits. Proceed to PHASE 8.

### PHASE 8 — RETEST

Run the same test suite as PHASE 3.

- If all tests pass AND no new issues: proceed to PHASE 9
- If tests fail: loop back to PHASE 7

**Loop counter:** Maximum 3 FIX→RETEST iterations. After 3 loops:
- **HALT** — block PR creation until unresolved CRITICALs are addressed
- Display remaining CRITICAL findings to the user
- Ask: "Quality loop exhausted 3 fix iterations with unresolved CRITICALs. Create PR anyway? (findings will be listed in PR body)"
- Only proceed to PHASE 9 if user confirms
- Log the loop exhaustion to learning.db

A pipeline that promises quality enforcement must not silently ship CRITICALs. The user must consciously choose to proceed.

**Gate:** All tests green after fixes. Proceed to PHASE 9. If tests fail, loop to PHASE 7 (max 3 iterations per the loop counter above).

### PHASE 9 — PR

Push branch and create PR via pr-workflow skill.

PR body includes:
- Summary of the change
- Review findings (all CRITICAL, IMPROVEMENT, POSITIVE from PHASES 4-6)
- Test results (pass/fail counts from PHASES 3 and 8)
- Intent verification result (PHASE 5)
- Fix iterations (how many FIX→RETEST loops were needed)

Only fires when PHASE 8 passes clean (or user confirmed after max loops).

**Gate:** PR created and CI triggered. Wait for merge before proceeding to PHASE 10.

### PHASE 10 — CODEX REVIEW

Cross-model second opinion on the PR. Uses the `pr-workflow` skill's codex-review intent to get a review from OpenAI Codex CLI (GPT-5.4 xhigh), providing a perspective independent of the Claude reviewers in PHASE 4.

- Pass the PR number, the ADR (if exists), and the full review context from PHASES 4-6
- Codex receives: the diff, the original request, the Claude review findings, and the ADR decision
- Codex produces: CRITICAL/IMPROVEMENTS/POSITIVE findings from a fresh model perspective
- Any new CRITICAL findings from Codex loop back to PHASE 7 (FIX) → PHASE 8 (RETEST) before merge

The value of cross-model review: Claude reviewers share inference patterns. A different model family catches blind spots that same-family reviewers miss. This is the same principle as having both static analysis and LLM review — orthogonal verification surfaces.

**Gate:** Codex review complete. If new CRITICALs found, loop to PHASE 7. If clean, proceed to merge, then PHASE 11.

### PHASE 11 — ADR RECONCILE

After PR is merged, compare what was planned against what was built.

**When ADR exists** (creation requests):
1. Read the original ADR from `adr/{name}.md`
2. Read the merged diff (`git diff main~1..main`)
3. Compare the ADR's Decision and Implementation Checklist against the actual implementation
4. For each checklist item: mark as completed, partially completed, or deviated
5. Note any deviations from the original decision (scope changes, alternative approaches taken, unexpected discoveries)
6. Add a `## Implementation Notes` section documenting what actually happened vs what was planned

**When no ADR exists** (non-creation requests):
- Compare `task_plan.md` acceptance criteria against the merged diff
- Note any deviations from the plan

**Gate:** Reconciliation documented. Proceed to PHASE 12.

### PHASE 12 — RECORD

Capture everything learned from this pipeline run.

- Record pipeline outcome to learning.db: phases executed, loop iterations, CRITICAL count, total agent dispatches
- Graduate any review findings that were fixed in this PR (immediate graduation per `/do` Phase 5 rules)
- Record the reconciliation outcome (how closely implementation matched plan/ADR)

```bash
SUMMARY_FILE=$(mktemp); printf '%s' "quality-loop: [summary of pipeline outcome]" > "$SUMMARY_FILE"
python3 ~/.claude/scripts/learning-db.py learn --skill do --value-file "$SUMMARY_FILE"
rm -f "$SUMMARY_FILE"
```

**Gate:** At least one learning recorded. Proceed to PHASE 13.

### PHASE 13 — CLEANUP

Close the loop. Remove temporary artifacts, finalize ADR lifecycle.

**ADR lifecycle** (when ADR exists):
- Change ADR status from `PROPOSED` to `Accepted`
- Move ADR to `adr/completed/{name}.md`
- Clear `.adr-session.json`

**Artifact cleanup:**
- Remove `quality-loop-state.md` from worktree
- Remove `task_plan.md` (work is complete)
- Confirm the task is inactive and the checkout is clean, then run `git worktree remove -- <accepted-worktree-path>`; the branch remains recoverable
- Run `bash scripts/worktree-cleanup.sh --force` after the checkout removal

**Gate:** ADR in completed (if applicable). Artifacts cleaned. Pipeline complete.

## Learning Integration

Each phase logs to learning.db:

```bash
SUMMARY_FILE=$(mktemp); printf '%s' "quality-loop PHASE_N: [outcome summary]" > "$SUMMARY_FILE"
python3 ~/.claude/scripts/learning-db.py learn --skill do --value-file "$SUMMARY_FILE"
rm -f "$SUMMARY_FILE"
```

## Worktree Isolation

- Phases 2–8 run in the same worktree
- Phase 9 (PR) runs pr-workflow from the main checkout using the feature branch
- Phases 10–12 run from the main checkout after merge
