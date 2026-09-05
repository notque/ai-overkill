# PR Pipeline

Create pull requests with selective staging, meaningful commits, risk-selected review, and CI verification.

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
| `protected-org` | Risk-selected review plus organization requirements | **Create PR, report URL, stop** — merge is handled by org reviewers. | Use existing authorization; honor explicit repository approval requirements |
| `personal` | Risk-selected review; follow up only on changed or unresolved scope | Create PR after review passes | Auto-execute steps normally |

Use existing authorization for commit, push, and PR creation. Ask only for an uncovered action or an explicit applicable repository requirement.

**Gate**: Repo type classified. Policy determined.

### Phase 0.5: PREFLIGHT CHECKLIST

**Goal**: Fail fast on environment issues before attempting PR creation. Every check produces a specific, actionable error message -- not a generic "preflight failed."

PR creation can fail mid-way because the working tree is dirty, the branch is main, or `gh` isn't authenticated -- all discoverable before starting the pipeline. Catching these upfront avoids partial state (e.g., a commit pushed but no PR created).

Run 5 checks sequentially (verification status, clean working tree, correct branch, remote configured, `gh` authenticated). Abort on the first failure with a specific error message.

See **Preflight Checklist** below for the full check table, bash script, and note on Check 1 (verification status).

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

### Phase 2: REVIEW

Classify risk and use the review lanes in `../SKILL.md`. Review the staged diff directly for routine changes. For substantial changes, choose specialists through `right-size-review.py`. Preserve required high-risk review and operator sign-off. `--skip-review` skips optional review, not repository requirements.

Assess findings before fixing them. Fix confirmed issues, stage the fixes, and rerun affected checks. Blocking correctness and security issues prevent merge. Repeat review only for new changes or unresolved concerns; reuse clean review of unchanged work.

### Phase 2b: Optional cross-model review

Use the `codex-review` intent before merge when requested or when a second model can resolve a concrete uncertainty. Review the staged diff; do not repeat review already performed on that scope. `--skip-codex` skips this optional review.

Assess findings independently and fix agreed issues. If Codex is unavailable or errors, report the limitation; this optional phase does not block the pipeline. Invocation, model settings, and output details live in `codex-review.md`.

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

**Protected-org repos**: Follow applicable organization requirements. Existing user authorization covers the requested commit, push, and PR creation; ask only when an action is not covered or an explicit repository rule requires separate approval.

**Gate**: Commit created successfully. Message follows conventional format. (protected-org: authorization checked.)

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


**Gate**: Changes pushed to remote. Branch tracks upstream. (protected-org: authorization checked.)

### Phase 4b: REVIEW-FIX (personal repos)

Reuse Phase 2's review. If new findings or changes need follow-up, fix confirmed issues and rerun affected checks. Document unresolved nonblocking issues in Notes; blocking correctness and security issues prevent merge. Protected-org repos retain their own review gates.

See **Review-Fix Loop** below for commit and push handling.

### Phase 4c: RETRO (toolkit repo only)

**Goal**: Embed review findings in the responsible agents/skills to prevent recurrence.

**Skip condition**: If the repo is NOT the vexjoy-agent repo, skip this phase entirely. Detection: check if both `agents/` and `skills/` directories exist at the project root. If either is missing, skip directly to Phase 5.

Three steps: collect findings from Phases 2 and 4b, embed each in the responsible agent or skill file, and stage the updated files.

See **Retro and ADR Validation Phases** below for full steps, bash commands, and the finding-target table.

**Gate**: All review findings embedded in the responsible agent/skill files. Updated files staged for commit.

### Phase 4d: ADR VALIDATION (toolkit repo only)

**Goal**: Verify that all ADRs in the `adr/` directory have consistent format and valid status fields before the PR is created.

**Skip condition**: Same as Phase 4c -- only runs in the toolkit repo (both `agents/` and `skills/` directories exist at root).

Run `python3 ~/.claude/scripts/adr-status.py check`; fix any warnings and stage changes. Run `python3 ~/.claude/scripts/adr-status.py status` and include the summary in the PR body if the PR touches `adr/*.md` files.

See **Retro and ADR Validation Phases** below for full ADR commands and fix workflow.

**Gate**: `python3 ~/.claude/scripts/adr-status.py check` exits 0. All ADRs have valid format.

### Phase 5: CREATE PR

**Goal**: Create the pull request with meaningful title and body.

**Step 1: Generate PR content**

Analyze the full diff against the base branch and all commit messages to draft:
- Title: Short (under 70 chars), descriptive of the change
- Body: Summary bullets, test plan, review findings from Phase 2

**Step 1.5: Artifact-Driven PR Body Generation**

When planning artifacts exist (`task_plan.md`, review summaries, deviation logs), generate the PR body from them rather than writing freeform. Artifacts capture *intent*, which is more valuable to reviewers than a mechanical diff summary. Feed them into the three sections: the goal into Summary, the completed-task shapes into Changes, and context/rollback/deviations into Notes, so each line carries one fact. Tests run as GitHub Actions — the Checks tab is the test record, so leave verification output to CI rather than pasting it. Fall back to diff-based generation when no artifacts exist.

See **PR body inputs** below and `../SKILL.md` for the shared body rules.

**Step 2: Create PR**

This pipeline cannot create PRs without staged changes -- if nothing is staged, the earlier phases would have caught this.

Use the canonical **PR body** rules in `../SKILL.md`; preserve all material Notes caveats. Write and read back `$PR_BODY_FILE` using `gh-body-safety.md` before submitting.

```bash
CLAUDE_GATE_BYPASS=1 gh pr create --title "$PR_TITLE" --body-file "$PR_BODY_FILE"
```

Add `--draft` flag if draft mode was requested via `--draft`.


**Step 3: Capture PR URL**

Record and report the PR URL to the user.

**Gate**: PR created successfully. URL available. (protected-org: authorization checked.)

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

Use `ci-check.md` to inspect all applicable checks for the pushed head, not just the latest run. If checks fail, investigate and fix within existing authorization, rerun affected local checks, push, and verify the new head. Keep the PR open until all checks pass. A status-only request permits reporting, not edits.

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

See **Options Reference** below.

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

Review only changed or unresolved scope using the selected risk lane. Exit when clean. Do not impose a fixed number of reviewer rounds. Report any unresolved issue; blocking correctness and security issues prevent merge.

Stage fixes selectively. Prefer a new commit if earlier commits have external review or collaborators. Amend only the tip created and pushed by this workflow before external review; use `--force-with-lease`, never `--force`, and stop if the lease fails.

```bash
git add [fixed files]
git commit --amend --no-edit
CLAUDE_GATE_BYPASS=1 git push --force-with-lease
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

# PR body inputs

Use the canonical body rules in `../SKILL.md`. Read `task_plan.md` for the goal and completed tasks; include material ADR-076 deviations and required risk/verification caveats in Notes. Without artifacts, use the diff and commit messages. Do not manufacture planning files just to create a PR.

## Options Reference

| Option | Effect | Default |
|--------|--------|---------|
| `--skip-review` | Skip optional review; required repository checks remain. | OFF (review runs) |
| `--draft` | Create draft PR instead of ready PR | OFF (ready PR) |
| `--no-wait` | Skip Phase 6 CI verification | OFF (waits for CI) |
| `--title "..."` | Override generated PR title | Auto-generated |
| `--files "pattern"` | Stage only files matching pattern | All changed files |
