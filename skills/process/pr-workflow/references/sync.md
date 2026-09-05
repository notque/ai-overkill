# PR Sync Skill

Sync local changes to GitHub in a single command. Detects current state (main vs feature branch, staged vs unstaged changes, existing PRs), then executes the minimum steps needed: branch, commit, push, and create PR. Execute only the steps needed for the current state -- do not add extra commits, rebase, or reorganize history beyond what is required to sync.

## Usage

```
/pr-sync                           # Auto-detect everything
/pr-sync feature/new-auth          # Specify branch name
/pr-sync fix/bug-123 "Fix login"   # Specify branch and PR title
```

## Instructions

### Step 0: Read CLAUDE.md and Classify Repo

Read and follow the repository CLAUDE.md before any git operations, because repo-specific branch conventions, commit formats, or CI requirements override defaults in this skill.

Then determine repo type:

```bash
REPO_TYPE=$(python3 ~/.claude/scripts/classify-repo.py --type-only)
```

**Protected-org repos**: Follow applicable organization requirements. Existing user authorization covers the requested commit, push, and PR creation; ask only when an action is not covered or an explicit repository rule requires separate approval.

**Personal repos**: Use the risk-selected review lanes in `../SKILL.md` before creating the PR. Reuse review already completed for current changes.

### Step 1: Detect Current State

Always detect state before taking any action, because skipping detection risks creating nested branches, committing to the wrong branch, or duplicating work already done.

```bash
# Get current branch
CURRENT_BRANCH=$(git branch --show-current)

# Detect main branch name
MAIN_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "master")

# Check for uncommitted changes
HAS_CHANGES=$(git status --porcelain)

# Check for unpushed commits (include these in the push so nothing is left behind)
UNPUSHED=$(git log origin/$CURRENT_BRANCH..$CURRENT_BRANCH --oneline 2>/dev/null)

# Determine if on main/master
ON_MAIN=false
if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" ]]; then
    ON_MAIN=true
fi
```

If the branch is behind remote, warn the user before pushing so they can pull or rebase first and avoid a rejected push.

### Step 2: Create Branch (if on main)

Never commit directly to main/master -- always create a feature branch first, because direct main commits skip code review, make rollback harder, and can break CI for everyone.

If on main/master with changes, create a feature branch. If no branch name was provided, generate one from the changes or commit message.

Branch naming conventions:

| Change Type | Prefix | Example |
|-------------|--------|---------|
| New feature | `feature/` | `feature/add-auth` |
| Bug fix | `fix/` | `fix/login-error` |
| Documentation | `docs/` | `docs/update-readme` |
| Refactoring | `refactor/` | `refactor/cleanup-utils` |
| Chore/maintenance | `chore/` | `chore/update-deps` |

```bash
git checkout -b "$BRANCH_NAME"
```

If already on a feature branch, skip this step.

### Step 3: Stage and Commit

Stage files selectively by name rather than using `git add -A`, because blind staging catches unintended files -- build artifacts, `.env` files, editor configs, large binaries -- that pollute the repository and may leak secrets. Review `git status`, stage specific files, and verify with `git diff --cached` before committing.

Never commit `.env`, credentials, secrets, or API keys. Block these files and warn the user if they appear in the staging area.

All commit messages use conventional commit format (`type(scope): description`).

```bash
# Stage specific files (not git add -A)
git add path/to/changed/files

# Create commit with conventional format
git commit -m "type(scope): description"
```

If no uncommitted changes exist, skip to Step 4.


### Step 4: Push to Remote

All pushes use standard `git push`, never `--force`, because force pushing destroys remote history and teammates lose work. If push is rejected due to the branch being behind remote, pull with rebase and resolve conflicts rather than forcing.

```bash
# Push with upstream tracking (CLAUDE_GATE_BYPASS=1 bypasses the git-submission-gate hook)
CLAUDE_GATE_BYPASS=1 git push -u origin "$CURRENT_BRANCH"
```

If the user requested a rebase before push, run `git pull --rebase origin $MAIN_BRANCH` first, but this is off by default.


### Step 4a: ADR Decision Coverage (conditional -- ADR-094)

**Skip if**: No `.adr-session.json` exists in the working directory.

When an active ADR session exists, run the coverage check before the review loop:

```bash
python3 scripts/adr-decision-coverage.py --adr <active-adr-path> --diff-base main --human
```

If verdict is PARTIAL or FAIL, display uncovered decision points and ask whether to proceed or address gaps first. This runs once before the review loop, not on every iteration.

### Step 4b: Review and fix (personal repos)

Use the risk-selected review lane in `../SKILL.md`. Reuse completed review; repeat only for new changes or unresolved findings. Fix confirmed issues and rerun affected checks. Document nonblocking unresolved issues in Notes; blocking correctness and security issues prevent merge.

Never amend externally reviewed or shared commits. Only the tip created and pushed by this workflow may be amended before external review, using `--force-with-lease`. Stop if the lease fails; never use `--force`. Otherwise use a new fix commit. Protected-org repos retain their own review gates.

### Step 5: Create or Update PR

Generate the PR title from the branch name or first commit when not provided by the user. Never create a PR with an empty description, because reviewers need context to understand the changes and a missing test plan signals incomplete work.

Use the canonical **PR body** rules in `../SKILL.md`; preserve all material Notes caveats. Write and read back `$PR_BODY_FILE` using `gh-body-safety.md` before submitting.

```bash
EXISTING_PR=$(gh pr list --head "$CURRENT_BRANCH" --json number --jq '.[0].number')
if [[ -z "$EXISTING_PR" ]]; then
    CLAUDE_GATE_BYPASS=1 gh pr create --title "$PR_TITLE" --body-file "$PR_BODY_FILE"
else
    gh pr view "$EXISTING_PR" --json url --jq .url
fi
```

If the user requested a draft PR, add `--draft` to `gh pr create`. If auto-assign reviewers was requested, assign based on CODEOWNERS.

Always show the PR URL after creation for easy access.


### Step 6: Post-Merge ADR Status Update (conditional -- ADR-095)

**Skip if**: No `.adr-session.json` exists, or the PR was only created (not merged).

After a PR is merged (confirmed via `gh pr view --json state`), update the ADR lifecycle:

```bash
# 1. Read active ADR path
ADR_PATH=$(python3 -c "import json; print(json.load(open('.adr-session.json'))['adr_path'])")

# 2. Update status to Accepted
sed -i 's/^## Status$/&/' "$ADR_PATH"  # (use Edit tool in practice)

# 3. Move to completed/
mv "$ADR_PATH" adr/completed/

# 4. Clear session
rm .adr-session.json
```

Report: `ADR updated: {name} -> Accepted, moved to completed/`

This is local-only (ADR files are gitignored). No branch or PR needed.

### Report

Return the PR URL, what changed, review result, and any unresolved issue. For protected-org repos, leave merge to the organization's reviewers unless separately authorized under its rules.

## Error Handling

### Error: "Push rejected - branch behind remote"
Cause: Remote branch has commits not present locally (teammate pushed, or previous rebase).
Solution:
1. Run `git pull --rebase origin $CURRENT_BRANCH`
2. Resolve any conflicts if they arise
3. Retry the push
4. If conflicts are complex, inform the user and show the conflicting files

### Error: "gh: not authenticated"
Cause: GitHub CLI is not authenticated or token expired.
Solution:
1. Run `gh auth status` to confirm
2. Instruct user to run `gh auth login`
3. Do not proceed with PR creation until auth is confirmed

### Error: "No changes to commit"
Cause: All changes are already committed, or working tree is clean.
Solution:
1. Check for unpushed commits with `git log origin/$BRANCH..$BRANCH`
2. If unpushed commits exist, skip to push step
3. If no unpushed commits, check if PR exists and show its status
4. If nothing to do, report clean state to user

### Error: "Branch name already exists"
Cause: A branch with the generated name already exists locally or on remote.
Solution:
1. Check if user is already on that branch (`git branch --show-current`)
2. If different branch, append a suffix (e.g., `-v2`) or ask user for alternative name
3. Never silently overwrite an existing branch

### Error: "Cannot delete branch used by worktree"
Cause: A git worktree references the branch, blocking deletion during PR merge or cleanup.
Solution:
1. Run `git worktree list` to identify the worktree using the branch
2. Run `git worktree remove <path>` to detach the worktree
3. Retry the branch deletion or PR merge with `--delete-branch`
4. This commonly happens when worktree agents (`isolation: "worktree"`) created the branch

### Error: "git push says up-to-date but changes are missing on remote"
Cause: `git push origin master` reports "up-to-date" when HEAD is on a different branch. Git pushes the named remote ref, not the current branch, so feature branch commits are never pushed.
Solution:
1. Always push the current branch: `git push -u origin $(git branch --show-current)`
2. Never hardcode branch names in push commands
3. Verify after push: `git log origin/$(git branch --show-current)..HEAD` should show 0 commits
---

## References

- `/pr-review` -- Comprehensive PR review (used in the review-fix loop)
- `/pr-cleanup` -- Post-merge branch cleanup
- `scripts/classify-repo.py` -- Repo classification for workflow gating
- `scripts/adr-decision-coverage.py` -- ADR decision coverage checker
