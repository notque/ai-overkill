# PR Pipeline

A structured pipeline for creating high-quality pull requests with proper staging, meaningful commits, parallel review, and CI verification.

---

## Instructions

### Phase 0: CLASSIFY REPO

**Goal**: Determine repo type to apply the correct review and merge policy.

```bash
# Detect repo type using the classification script
REPO_TYPE=$(python3 ~/.claude/scripts/classify-repo.py --type-only)
```

| Repo Type | Review Policy | Merge Policy | Step Execution |
|-----------|--------------|--------------|----------------|
| `protected-org` | Phase 2 parallel review only (their reviewers handle comprehensive review) | **Create PR, report URL, stop** — merge is handled by org reviewers. | **Human-gated**: confirm commit message, push, and PR creation with user before each step |
| `personal` | Phase 2 parallel review + Phase 4b review-fix loop (max 3 iterations of `/pr-review` -> fix) | Create PR after review passes | Auto-execute steps normally |

Protected-org repos require user confirmation before EACH step (commit message approval, push approval, PR creation approval) because unauthorized actions in shared org repos can trigger CI storms, notify entire teams, or violate org policies. Never auto-execute any of these steps -- present the proposed action and wait for user approval.

**Gate**: Repo type classified. Policy determined.

### Phase 0.5: PREFLIGHT CHECKLIST

**Goal**: Fail fast on environment issues before attempting PR creation. Every check produces a specific, actionable error message -- not a generic "preflight failed."

PR creation can fail mid-way because the working tree is dirty, the branch is main, or `gh` isn't authenticated -- all discoverable before starting the pipeline. Catching these upfront avoids partial state (e.g., a commit pushed but no PR created).

Run 5 checks sequentially (verification status, clean working tree, correct branch, remote configured, `gh` authenticated). Abort on the first failure with a specific error message.

See `references/preflight-checklist.md` for the full check table, bash script, and note on Check 1 (verification status).

**Gate**: All preflight checks pass. Environment is ready for PR creation. Proceed to Phase 1.

### Phase 1: STAGE

**Goal**: Analyze working tree and stage appropriate changes.

**Step 1: Read and follow CLAUDE.md**

Before staging, read the repository's CLAUDE.md for commit and branch rules. These rules override defaults because each repo has its own conventions for branch naming, commit format, and file organization.

**Step 2: Inspect changes**

```bash
# See what's changed
git status --porcelain

# Review diff for context
git diff
git diff --cached
```

**Step 3: Block sensitive files**

Check every changed file against the blocklist. Sensitive files must be blocked here, before staging, because once committed they enter git history permanently -- removing them later requires history rewriting which is disruptive for all collaborators.

Blocklist:
- `.env`, `.env.*`
- `credentials.json`, `secrets.*`
- `*.pem`, `*.key`, `*.p12`
- Any file matching patterns in `.gitignore`

If sensitive files are detected, STOP and report to user. Do not stage them.

**Step 4: Stage changes**

Stage specific files by name -- never run `git add -A` or `git add .` because blind staging captures unrelated changes, build artifacts, and debug logs that obscure review and pollute history.

```bash
# Stage specific files (never git add -A blindly)
git add [files]
```

If the changeset spans 30+ files or multiple unrelated features, suggest the user split into focused PRs. Monolithic PRs are impossible to review effectively, carry high regression risk, and block other work.

**Gate**: Changes staged. No sensitive files included. Staged diff makes sense as a cohesive unit.

### Phase 2: REVIEW (Comprehensive Multi-Agent Review)

**Goal**: Catch ALL issues before they reach the commit. Run the review loop before creating the commit because post-merge fixes cost 2 PRs instead of 1.

**Skip condition**: Only if user explicitly passes `--skip-review`. One-line changes can still introduce security vulnerabilities or break business logic, so the default is always to review.

**Run the comprehensive-review pipeline:**

Call the Skill tool with `workflow`.

```
Pipeline: comprehensive-review
Scope: git diff --cached (staged changes)
Mode: review + fix (default)
```

This dispatches:
- **Wave 1**: 11 foundation agents in parallel (security, business logic, architecture, silent failures, test coverage, type design, code quality, comments, language specialist, docs validator, ADR compliance)
- **Wave 2**: 10 deep-dive agents with Wave 1 context (performance, concurrency, API contracts, dependencies, error messages, dead code, naming, observability, config safety, migration safety)

All findings are auto-fixed. The fix commit is applied to the staged changes before proceeding to Phase 3.

**If comprehensive-review finds CRITICAL issues that cannot be auto-fixed**: STOP and report to user. Do not proceed to commit.

**Gate**: Comprehensive review complete. All findings fixed or explained. No unresolved CRITICAL issues.

### Phase 2b: CROSS-MODEL REVIEW (auto-injected)

**Goal**: Get an independent second opinion from OpenAI Codex CLI to catch issues that same-model review might miss.

**Note**: The `codex-auto-review` UserPromptSubmit hook now automatically injects a reminder to run this phase whenever any review skill is invoked (`/systematic-code-review`, `/parallel-code-review`, `/pr-review`, `/full-repo-review`, etc.). This makes cross-model review standard across all review workflows, not just pr-workflow.

**Skip condition**: Skip if `codex` CLI is not installed (`which codex` fails), if user passes `--skip-codex`, or if the codex-review intent was already invoked as part of the current pipeline. This phase is additive -- it never blocks the pipeline, only adds signal.

**Invoke the pr-workflow codex-review intent:**

```
Invoke: /pr-workflow codex-review
Scope: git diff --cached (staged changes)
```

Codex runs in read-only sandbox mode with GPT-5.5 `high` reasoning by default (`xhigh` is opt-in for hard correctness analysis -- security/concurrency/migrations). It produces structured findings (CRITICAL / IMPROVEMENTS / POSITIVE / SUMMARY). Claude assesses each finding before incorporating -- Codex feedback is a second opinion, not authoritative.

**If Codex finds CRITICAL issues that Claude agrees with**: Fix them and re-stage before proceeding.
**If Codex is unavailable or errors**: Log the skip reason and proceed. This phase must never block the pipeline.

**Gate**: Cross-model review complete (or skipped). Any agreed-upon findings fixed.

### Phase 3: COMMIT

**Goal**: Create a meaningful commit with conventional format.

**Step 1: Analyze staged changes**

```bash
git diff --cached --stat
git diff --cached
```

**Step 2: Determine commit type and scope**

Map changes to conventional commit type: feat, fix, refactor, docs, test, chore, ci, style, perf.

**Step 3: Create commit**

Write the commit message now with full context -- "I'll fix the commit message later" never happens, and git history is permanent.

```bash
git commit -m "$(cat <<'EOF'
type(scope): concise description of WHAT changed

- Detail about WHY this change was made
- Additional context if multiple files changed
EOF
)"
```

Follow CLAUDE.md rules for commit messages. Never add "Generated with Claude Code", "Co-Authored-By: Claude", or similar attribution lines because they add noise and violate most project commit conventions.

**Protected-org repos**: Before executing the commit, present the proposed commit message to the user and wait for explicit approval. Show the full message and list of files that will be committed.

**Gate**: Commit created successfully. Message follows conventional format. (protected-org: user confirmed.)

### Phase 4: PUSH

**Goal**: Push changes to remote with proper branch setup.

**Step 1: Ensure correct branch**

Never push directly to main/master without explicit authorization -- this bypasses all review gates and can break the build for everyone.

```bash
# Check current branch
git branch --show-current

# If on main/master, create feature branch first
git checkout -b type/descriptive-branch-name
```

Use the `branch-name` intent (see `${CLAUDE_SKILL_DIR}/references/branch-name.md`) for compliant names.

**Step 2: Push with tracking**

Push with `-u` flag for new branches so subsequent pushes and PR creation can find the upstream automatically.

```bash
# CLAUDE_GATE_BYPASS=1 bypasses the git-submission-gate hook (this skill IS the gate)
CLAUDE_GATE_BYPASS=1 git push -u origin $(git branch --show-current)
```

**Step 3: Verify push**

Confirm push succeeded by checking output. If push fails (e.g., rejected), report error and stop.

**Protected-org repos**: Before executing the push, present the branch name, remote, and list of commits that will be pushed. Wait for user to confirm before executing `CLAUDE_GATE_BYPASS=1 git push`.

**Gate**: Changes pushed to remote. Branch tracks upstream. (protected-org: user confirmed.)

### Phase 4b: REVIEW-FIX LOOP (personal repos only)

**Goal**: Iteratively review and fix issues until clean or max 3 iterations reached.

**Skip condition**: If `REPO_TYPE == "protected-org"`, skip this phase entirely. Protected-org repos have their own PR gates. This phase cannot be skipped for personal repos -- even with `--skip-review` (which only skips Phase 2), this loop always runs because it is the final quality gate before PR creation.

**Loop**: Up to 3 iterations of `/pr-review` -> fix -> amend commit -> push. After iteration 3, exit and document remaining issues in the PR body.

See `references/review-fix-loop.md` for the full loop logic, steps 1-5 with code blocks, result table, and iteration report format.

**Gate**: Review-fix loop complete. Either clean (0 issues) or max 3 iterations reached with remaining issues documented.

### Phase 4c: RETRO (toolkit repo only)

**Goal**: Embed review findings in the responsible agents/skills to prevent recurrence.

**Skip condition**: If the repo is NOT the vexjoy-agent repo, skip this phase entirely. Detection: check if both `agents/` and `skills/` directories exist at the project root. If either is missing, skip directly to Phase 5.

Three steps: collect findings from Phases 2 and 4b, embed each in the responsible agent or skill file, and stage the updated files.

See `references/retro-adr-phases.md` for full steps, bash commands, and the finding-target table.

**Gate**: All review findings embedded in the responsible agent/skill files. Updated files staged for commit.

### Phase 4d: ADR VALIDATION (toolkit repo only)

**Goal**: Verify that all ADRs in the `adr/` directory have consistent format and valid status fields before the PR is created.

**Skip condition**: Same as Phase 4c -- only runs in the toolkit repo (both `agents/` and `skills/` directories exist at root).

Run `python3 ~/.claude/scripts/adr-status.py check`; fix any warnings and stage changes. Run `python3 ~/.claude/scripts/adr-status.py status` and include the summary in the PR body if the PR touches `adr/*.md` files.

See `references/retro-adr-phases.md` for full ADR commands and fix workflow.

**Gate**: `python3 ~/.claude/scripts/adr-status.py check` exits 0. All ADRs have valid format.

### Phase 5: CREATE PR

**Goal**: Create the pull request with meaningful title and body.

**Step 1: Generate PR content**

Analyze the full diff against the base branch and all commit messages to draft:
- Title: Short (under 70 chars), descriptive of the change
- Body: Summary bullets, test plan, review findings from Phase 2

**Step 1.5: Artifact-Driven PR Body Generation**

When planning artifacts exist (`task_plan.md`, review summaries, deviation logs), generate the PR body from them rather than writing freeform. Artifacts capture *intent*, which is more valuable to reviewers than a mechanical diff summary. Feed them into the three sections: the goal into Summary, the completed-task shapes into Changes, and context/rollback/deviations into Notes, so each line carries one fact. Tests run as GitHub Actions — the Checks tab is the test record, so leave verification output to CI rather than pasting it. Fall back to diff-based generation when no artifacts exist.

See `references/pr-templates.md` for the full artifact table, PR body template, and fallback guidance.

**Step 2: Create PR**

This pipeline cannot create PRs without staged changes -- if nothing is staged, the earlier phases would have caught this.

**PR body structure is mandatory.** `gh pr create --body` bypasses `.github/pull_request_template.md` (GitHub applies that file only to the web UI and to a bare `gh pr create`). Reproduce the template's three sections in the `--body` string, in order: **Summary → Changes → Notes**. This keeps PR bodies consistent across models.

**Write for density.** Each Changes line states one fact, declaratively (verb + what + where), so a reviewer scans the body fast; Summary states the goal and why. Write one line per change in Changes (give shape and count for many sub-items, e.g. "add 21 trigger phrases", and let the diff enumerate them). Omit Notes for routine PRs and drop the section when nothing qualifies; note it, one terse line per point, when a reviewer cannot infer the signal from the diff (a non-obvious decision, a deliberate omission, a follow-up, a gotcha, "supersedes #N") or when a risk/verification trigger holds — manual verification was performed, part of the change sits outside CI coverage, migration/rollout ordering matters, or a security-sensitive surface changed (e.g. `Not covered by CI — terraform plan is manual`). Skip what is always true (a PR can be reverted; CI runs the tests). Tests run as GitHub Actions and the Checks tab is the test record; reviewer verdicts likewise show on the PR, so leave command output to CI and keep it out of the body. See the SKILL.md "Write for Density" rules for the full vibe and worked example.

```bash
CLAUDE_GATE_BYPASS=1 gh pr create --title "type(scope): description" --body "$(cat <<'EOF'
## Summary
[State the goal plainly: 1-3 sentences or a few crisp bullets, one fact per line. Name the ADR/issue if any.]

## Changes
- `path/or/area` — what changed [one line per change; give shape + count for many sub-items]

## Notes
[Omit for routine PRs (drop the section when nothing qualifies). Note it, one terse line per point, when a reviewer cannot infer the signal from the diff: a non-obvious decision, a deliberate omission, a follow-up, a gotcha, "supersedes #N". Note it too when a risk/verification trigger holds — manual verification was performed; part of the change sits outside CI coverage; migration/rollout ordering matters; a security-sensitive surface changed (e.g. `Not covered by CI — terraform plan is manual`). Skip what is always true (a PR can be reverted; CI runs the tests).]
EOF
)"
```

Add `--draft` flag if draft mode was requested via `--draft`.

**Protected-org repos**: Before creating the PR, present the title, body, and target branch to the user. Wait for explicit approval before executing `gh pr create`.

**Step 3: Capture PR URL**

Record and report the PR URL to the user.

**Gate**: PR created successfully. URL available. (protected-org: user confirmed.)

**Protected-org repos**: After creating the PR, report the URL and **STOP the pipeline**. Do not wait for CI or attempt any merge operations. Output:
```
PR PIPELINE COMPLETE (protected-org repo)

Protected-org repo detected -- PR created for human review.
PR: https://github.com/your-org/your-repo/pull/123

Next steps are handled by org CI gates and human reviewers.
This pipeline will NOT auto-merge protected-org PRs.
```

### Phase 6: VERIFY (personal repos only)

**Goal**: Wait for CI and report final status. Always check CI status before marking the pipeline complete because merging without CI confirmation risks shipping broken code.

```bash
# Get the latest workflow run for this branch
gh run list --branch $(git branch --show-current) --limit 1

# Wait for completion (timeout 10 minutes)
gh run watch [run-id] --exit-status
```

If CI fails, report which checks failed and the PR URL. Keep the PR open and stop before cleanup. This pipeline reports CI failures but does not fix them -- diagnosing CI requires different context than PR creation.

If CI passes and user requested merge:
```bash
CLAUDE_GATE_BYPASS=1 gh pr merge --merge --delete-branch
```

**HARD RULE**: Merge a PR only after CI passes. The `ci-merge-gate.py` hook enforces this mechanically -- it blocks `gh pr merge` when checks are failing or pending. Investigate the root cause (date-dependent fixtures, flaky tests) rather than bypassing the gate when CI fails on an "unrelated" test; treating CI as "probably flaky" masks real failures and normalizes broken builds.

If `--no-wait` was passed, skip this phase and report the PR URL immediately.

**Gate**: CI green + merged (if requested). Proceed to Phase 7.

### Phase 7: CLEANUP

**Goal**: Delete the feature branch after successful merge or PR creation.

For personal repos where CI passed and PR was merged:
```bash
# Switch to main and pull
git checkout main
git pull origin main

# Delete local branch
git branch -d <branch-name>

# Delete remote branch
CLAUDE_GATE_BYPASS=1 git push origin --delete <branch-name>

# Prune stale tracking refs
git fetch --prune
```

For personal repos where PR was created but not yet merged: skip cleanup (branch is still active).

For protected-org repos: skip cleanup (their processes handle branch lifecycle).

**ADR status update (ADR-095)**: If `.adr-session.json` exists and the PR was merged:
1. Read the active ADR path from `.adr-session.json`
2. Update status from "Proposed" to "Accepted" in the ADR file
3. Move the ADR file to `adr/completed/`
4. Clear `.adr-session.json`
5. Report: `ADR updated: {name} -> Accepted, moved to completed/`

ADRs are gitignored (local-only), so this is a local file operation, not a git operation.

**Gate**: Branch cleaned up (or skipped if PR is still open). Pipeline complete.

### Worktree Agent Awareness

When this pipeline runs inside a worktree agent (dispatched with `isolation: "worktree"`), the worktree creates a local branch that persists after the agent completes. This branch blocks `gh pr merge --delete-branch` and `git branch -d`. The dispatching agent or cleanup skill must run `git worktree remove <path>` before merging the PR or deleting the branch. If you are creating a PR from a worktree, note this in the PR body so the caller knows cleanup is required.

### Options Reference and Examples

See `references/pr-templates.md` for the full options reference table and all 4 usage examples (Standard PR, Draft PR, Trivial Change, Protected-Org).

---

## Error Handling

### Error: "Push Rejected by Remote"
Cause: Branch is behind remote, or branch protection rules block the push
Solution:
1. Check if branch needs rebase: `git log --oneline origin/main..HEAD`
2. If behind, rebase onto latest main: `git pull --rebase origin main`
3. If protection rules, verify branch name is not main/master
4. Retry push after resolving

### Error: "gh pr create Fails"
Cause: No upstream tracking, gh not authenticated, or PR already exists for branch
Solution:
1. Verify gh auth: `gh auth status`
2. Check if PR exists: `gh pr list --head $(git branch --show-current)`
3. If PR exists, report URL instead of creating duplicate
4. If auth issue, instruct user to run `gh auth login`

### Error: "Sensitive File Detected in Staging"
Cause: User's changes include .env, credentials, keys, or other secrets
Solution:
1. STOP immediately -- exclude the sensitive file from staging
2. Report which file(s) were blocked and why
3. Ask user to confirm exclusion or add to .gitignore
4. Resume pipeline with sensitive files excluded

### Error: "CI Timeout Exceeded"
Cause: CI workflow takes longer than 10 minutes or is stuck
Solution:
1. Report current CI status (pending/running)
2. Provide the PR URL so user can monitor manually
3. Suggest: `gh run watch [run-id]` for manual monitoring
4. Mark pipeline as complete with "CI pending" status

---

# Appendix: Reference Details

The following sections were previously loaded on-demand from separate reference files.

---

# Preflight Checklist

Full details for Phase 0.5 of the PR Pipeline.

## Check Table

Run all checks sequentially. Abort on the first failure.

| # | Check | Command | Failure Action |
|---|-------|---------|---------------|
| 1 | Verification status (did quality gates pass?) | Check for recent test/build output or verification artifacts | Abort: "Run verification first -- no evidence that quality gates passed." |
| 2 | Clean working tree (no uncommitted changes) | `git status --porcelain` | Abort: "Working tree is dirty. Uncommitted files:\n{list}. Stage or stash before running PR pipeline." |
| 3 | Correct branch (not main/master) | `git branch --show-current` | Abort: "Currently on {branch}. Create a feature branch first: `git checkout -b type/description`" |
| 4 | Remote configured for current branch | `git config --get branch.$(git branch --show-current).remote` | Abort: "No remote configured for branch. Push with: `git push -u origin $(git branch --show-current)`" |
| 5 | `gh` CLI authenticated | `gh auth status 2>&1` | Abort: "GitHub CLI not authenticated. Run: `gh auth login`" |

## Bash Script

```bash
# Preflight check sequence
echo "Running preflight checklist..."

# Check 1: Verification status
# Look for verification artifacts (test output, build logs) — if the project
# has a test suite and no recent verification evidence exists, warn.
# This is a soft gate: skip if no test infrastructure is detected.

# Check 2: Clean working tree
DIRTY=$(git status --porcelain)
if [ -n "$DIRTY" ]; then
    echo "PREFLIGHT FAIL: Working tree is dirty."
    echo "$DIRTY"
    echo "Stage or stash uncommitted changes before running PR pipeline."
    exit 1
fi

# Check 3: Not on main/master
BRANCH=$(git branch --show-current)
if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
    echo "PREFLIGHT FAIL: On branch '$BRANCH'."
    echo "Create a feature branch: git checkout -b type/description"
    exit 1
fi

# Check 4: Remote configured
REMOTE=$(git config --get "branch.$BRANCH.remote" 2>/dev/null)
if [ -z "$REMOTE" ]; then
    echo "PREFLIGHT FAIL: No remote configured for branch '$BRANCH'."
    echo "Push with: git push -u origin $BRANCH"
    exit 1
fi

# Check 5: gh CLI authenticated
if ! gh auth status >/dev/null 2>&1; then
    echo "PREFLIGHT FAIL: GitHub CLI not authenticated."
    echo "Run: gh auth login"
    exit 1
fi

echo "Preflight checklist PASSED."
```

## Note on Check 1 (Verification Status)

This is context-dependent. If the project has a test suite (`go test`, `npm test`, `pytest`, etc.), look for evidence that tests were run recently (e.g., verification report files, recent test output in the session). If no test infrastructure exists, this check passes by default. The goal is to prevent submitting code that was never tested, not to block projects without tests.

---

# Review-Fix Loop

Full details for Phase 4b of the PR Pipeline (personal repos only).

## Loop Logic

Up to 3 iterations of `/pr-review` -> fix -> amend commit -> push.

```
ITERATION = 0
MAX_ITERATIONS = 3

while ITERATION < MAX_ITERATIONS:
    ITERATION += 1

    Step 1: Run /pr-review
    Step 2: If no issues found -> EXIT LOOP (proceed to Phase 5)
    Step 3: Fix all reported issues
    Step 4: Stage fixes, amend commit, force push to branch
    Step 5: Report iteration results
```

## Step 1: Run `/pr-review`

Invoke the `/pr-review` command, which launches specialized review agents (code-reviewer, silent-failure-hunter, comment-analyzer, etc.) and captures retro learnings.

## Step 2: Evaluate Results

| Result | Action |
|--------|--------|
| No issues found | **Exit loop**. Proceed to Phase 5 (CREATE PR). |
| Issues found (iteration < 3) | Fix issues in Step 3, then re-review. |
| Issues remaining after iteration 3 | **Exit loop**. Include remaining issues in PR body as known items. Proceed to Phase 5. |

## Step 3: Fix Reported Issues

Address each issue found by the review. This includes:
- Code quality fixes (naming, style, error handling)
- Documentation updates (stale references, missing README entries)
- Test gaps (if flagged)

## Step 4: Amend and Push

```bash
git add [fixed files]
git commit --amend --no-edit
CLAUDE_GATE_BYPASS=1 git push --force-with-lease
```

## Step 5: Iteration Report Format

```
REVIEW-FIX ITERATION [N/3]
  Found: [X issues]
  Fixed: [Y issues]
  Remaining: [Z issues]
  Status: [CLEAN | FIXING | MAX ITERATIONS REACHED]
```

---

# Retro and ADR Validation Phases

Full details for Phase 4c (RETRO) and Phase 4d (ADR VALIDATION) of the PR Pipeline.
Both phases apply to the vexjoy-agent repo only.

---

## Phase 4c: RETRO

**Detection**: Both `agents/` and `skills/` directories exist at project root.

```bash
# Detect toolkit repo
if [ -d "agents" ] && [ -d "skills" ]; then
    echo "Toolkit repo detected -- RETRO phase required"
else
    echo "Not toolkit repo -- skipping RETRO phase"
    # Skip to Phase 5
fi
```

### Step 1: Collect Review Findings

Gather all findings from Phase 2 (REVIEW) and Phase 4b (REVIEW-FIX LOOP) that were identified and fixed. Include:
- Security findings that were addressed
- Code quality issues that were corrected
- Business logic errors that were fixed
- Methodology gaps that were exposed

For each finding, identify the **responsible agent or skill** -- the component whose instructions should have prevented the issue.

### Step 2: Embed in the responsible agent or skill

Write the finding into the component that should have prevented it, in this PR, as a reviewed edit. A review finding in this repo is a structural fix, so it lands in the file directly — no staging store in between.

| Finding Target | Update Location | Section to Modify |
|---------------|----------------|-------------------|
| Agent produced bad code | `agents/{name}.md` | Preferred patterns or verification guidance |
| Skill methodology gap | `skills/{name}/SKILL.md` | Instructions or preferred patterns |
| Router missed a pattern | `skills/meta/do/SKILL.md` | Routing tables or Force-Routes |
| Hook failed to catch | `hooks/{name}.py` | Detection logic |

Write the pattern at the right abstraction level -- generalize from the specific bug to the class of bug (e.g., "validate all CLI inputs" not "validate subreddit names in _cmd_classify").

### Step 3: Stage Retro Changes

```bash
# Stage updated agent/skill files alongside the code changes
git add agents/{updated-agent}.md
git add skills/{updated-skill}/SKILL.md
```

These changes will be included in the existing commit (amend in next push cycle) or in a new commit if Phase 4b already completed cleanly.

---

## Phase 4d: ADR VALIDATION

**Detection**: Same as Phase 4c -- only runs in the toolkit repo (both `agents/` and `skills/` directories exist at root).

### Step 1: Run ADR Format Check

```bash
python3 ~/.claude/scripts/adr-status.py check
```

If exit code 1 (warnings found):
- Review each warning (missing headings, empty status)
- Fix formatting issues in the ADR files
- Stage the fixes: `git add adr/`

### Step 2: Run ADR Status Report

```bash
python3 ~/.claude/scripts/adr-status.py status
```

Include the status summary in the PR body if the PR touches any `adr/*.md` files. This gives reviewers an at-a-glance view of ADR state.

---

# PR Templates and Examples

Full details for Phase 5 (CREATE PR) of the PR Pipeline: artifact-driven body generation, templates, and all usage examples.

---

## Artifact-Driven PR Body Generation

When planning artifacts exist, generate the PR body from them rather than writing freeform. Artifacts capture *intent* (why the change was made), which is more valuable to reviewers than a mechanical diff summary. Summarize each artifact into dense lines — one fact per line — so a reviewer scans the body fast. Pull the goal, the completed-task shapes, and any context a reviewer needs beyond the diff; let the diff and the linked reports carry the rest. Tests are covered by CI — the Checks tab is the test record, so leave command output to CI rather than pasting it.

Check for artifacts in this order and build the PR body from what's available:

| Artifact | PR Section Generated | How to Extract |
|----------|---------------------|----------------|
| `task_plan.md` | **Summary** (from Goal section) and **Changes** (from completed tasks) | Read the Goal and Phases sections; state the goal plainly; write one line per completed item (shape + count for many sub-items) |
| Deviation logs (ADR-076 repair actions) | **Notes** (deviations) | List repair actions taken and why the original plan changed, one terse line each — these are non-obvious by nature |
| Context a reviewer cannot infer (non-obvious decision, deliberate omission, follow-up, gotcha, supersedes) or a risk/verification trigger (manual verification performed, CI-coverage gap, migration/rollout ordering, security-surface change) | **Notes** (required on trigger) | One terse line each. Omit Notes for routine PRs and drop the section when nothing qualifies; note it when an artifact surfaces non-obvious context or a risk/verification trigger holds (e.g. `Not covered by CI — terraform plan is manual`). Skip what is always true (a PR can be reverted; CI runs the tests). Verification reports and review summaries stay in CI — the Checks tab carries the result |

**Fallback**: If no artifacts exist, fall back to diff-based generation -- summarize changes from the diff and commit messages. This is the existing behavior and remains the default for ad-hoc PRs without planning artifacts.

## PR Body Template (Artifact-Driven)

Follows the canonical three-section structure from `.github/pull_request_template.md` (Summary / Changes / Notes), with each section populated from artifacts. Deviation logs and reviewer context fold into **Notes**.

```markdown
## Summary
<!-- From task_plan.md Goal section, or from commit messages if no plan. State the goal plainly: 1-3 sentences, one fact per line. Name the ADR/issue if any. -->
[Goal statement: what changed and why, plainly, in 1-3 sentences.]

## Changes
<!-- From task_plan.md completed phases/tasks. One line per change: verb + what + where. Give shape + count for many sub-items. -->
- `path/or/area` — [completed task description]
- `path/or/area` — [completed task description]

## Notes
<!-- Omit for routine PRs (drop the section when nothing qualifies). Note it, one terse line per point, when an artifact surfaces something a reviewer cannot infer from the diff: a non-obvious decision, a deliberate omission, a follow-up, a gotcha, "supersedes #N", a deviation log (ADR-076). Note it too when a risk/verification trigger holds — manual verification was performed; part of the change sits outside CI coverage; migration/rollout ordering matters; a security-sensitive surface changed (e.g. `Not covered by CI — terraform plan is manual`). Skip what is always true (a PR can be reverted; CI runs the tests). -->
[Optional context a reviewer cannot infer from the diff.]
```

---

## Examples

### Example 1: Standard PR Submission (personal repo)

User says: "Submit a PR for these changes"

Actions:
1. Classify repo from remote URL (CLASSIFY REPO)
2. `git status`, review changes, stage files (STAGE)
3. Launch 3 parallel reviewers on staged diff (REVIEW)
4. Create conventional commit from staged changes (COMMIT)
5. Push branch to remote with tracking (PUSH)
6. Run review-fix loop: `/pr-review` -> fix -> re-review, up to 3 iterations (REVIEW-FIX LOOP)
7. Embed review findings in the responsible agents/skills (RETRO, toolkit repo only)
8. Validate ADR format consistency (ADR VALIDATION, toolkit repo only)
9. Create PR with summary and review findings (CREATE PR)
10. Wait for CI, report status (VERIFY)

Result: PR URL with CI status and review-fix iteration count

### Example 2: Draft PR for Work in Progress (personal repo)

User says: "Open a draft PR for what I have so far"

Actions:
1. Classify repo (CLASSIFY REPO)
2. Stage current changes, skip incomplete files if noted (STAGE)
3. Run parallel review (REVIEW)
4. Commit with `wip:` or appropriate prefix (COMMIT)
5. Push to feature branch (PUSH)
6. Run review-fix loop (REVIEW-FIX LOOP)
7. Embed review findings in the responsible agents/skills (RETRO, toolkit repo only)
8. Validate ADR format consistency (ADR VALIDATION, toolkit repo only)
9. Create PR with `--draft` flag (CREATE PR)
10. Report PR URL, skip CI wait if `--no-wait` (VERIFY)

Result: Draft PR URL

### Example 3: Trivial Change with Skip Parallel Review (personal repo)

User says: "Quick PR for this typo fix, skip review"

Actions:
1. Classify repo (CLASSIFY REPO)
2. Stage the single file change (STAGE)
3. Skip Phase 2 parallel review (--skip-review)
4. Commit: `fix(docs): correct typo in README` (COMMIT)
5. Push to branch (PUSH)
6. Run review-fix loop -- Phase 4b still runs even with --skip-review (REVIEW-FIX LOOP)
7. Embed review findings in the responsible agents/skills (RETRO, toolkit repo only)
8. Validate ADR format consistency (ADR VALIDATION, toolkit repo only)
9. Create PR with minimal body (CREATE PR)
10. Wait for CI (VERIFY)

Result: PR URL for typo fix

### Example 4: Protected-Org Repo (human-gated workflow)

User says: "Submit a PR for these changes" (in a protected-org repo)

Actions:
1. Classify repo -> protected-org detected (CLASSIFY REPO)
2. Stage files (STAGE)
3. Run parallel review (REVIEW)
4. Present commit message -> user confirms -> create commit (COMMIT, human-gated)
5. Present push details -> user confirms -> push to remote (PUSH, human-gated)
6. Skip Phase 4b (protected-org repos use their own review gates)
7. Present PR title/body -> user confirms -> create PR (CREATE PR, human-gated)
8. **STOP**. No CI wait, no merge. Report PR URL.

Result: PR URL. Next steps handled by org CI gates and human reviewers.

---

## Options Reference

| Option | Effect | Default |
|--------|--------|---------|
| `--skip-review` | Skip Phase 2 (parallel subagent review) for trivial changes. Phase 4b review-fix loop still runs. | OFF (review runs) |
| `--draft` | Create draft PR instead of ready PR | OFF (ready PR) |
| `--no-wait` | Skip Phase 6 CI verification | OFF (waits for CI) |
| `--title "..."` | Override generated PR title | Auto-generated |
| `--files "pattern"` | Stage only files matching pattern | All changed files |
