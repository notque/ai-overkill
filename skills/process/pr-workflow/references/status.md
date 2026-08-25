# PR Status Skill

Collect git state, PR metadata, CI status, reviews, and merge readiness in ordered steps, then present a unified status report. This is a **read-only** skill -- it never modifies files, branches, or PR state because status checks that mutate state create surprising side effects and belong to other skills (pr-sync, pr-fix).

---

## Instructions

### Phase 1: Prerequisites

Verify `gh` CLI is available and authenticated before any PR queries. Without `gh`, PR metadata, CI checks, and review data are all inaccessible, so there is no point proceeding with a partial report.

```bash
command -v gh &> /dev/null || { echo "GitHub CLI (gh) not installed. Install: https://cli.github.com/"; exit 1; }
gh auth status &> /dev/null || { echo "GitHub CLI not authenticated. Run: gh auth login"; exit 1; }
```

> **Gate**: If either check fails, report the specific missing prerequisite with the installation/auth URL and stop. Do not attempt partial status without `gh`.

### Phase 2: Branch Identification

Always report which branch is being checked -- users often forget what branch they are on, and every subsequent step depends on correct branch context.

```bash
CURRENT_BRANCH=$(git branch --show-current)
MAIN_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "master")
```

If on the main branch, report that and optionally list recent PRs. No further phases needed.

### Phase 3: Local State

Fetch before comparing local and remote state. Stale local refs produce inaccurate ahead/behind counts that mislead the user into thinking their branch is up to date when it is not.

```bash
# Working tree status
DIRTY=$(git status --porcelain)
if [[ -z "$DIRTY" ]]; then
    echo "Clean working tree"
else
    FILE_COUNT=$(echo "$DIRTY" | wc -l)
    echo "$FILE_COUNT files modified"
fi

# Fetch first -- comparing against stale refs gives wrong counts
git fetch origin --quiet
AHEAD=$(git rev-list origin/$CURRENT_BRANCH..$CURRENT_BRANCH --count 2>/dev/null || echo "0")
BEHIND=$(git rev-list $CURRENT_BRANCH..origin/$CURRENT_BRANCH --count 2>/dev/null || echo "0")
BEHIND_MAIN=$(git rev-list $CURRENT_BRANCH..origin/$MAIN_BRANCH --count 2>/dev/null || echo "0")
```

Show how many commits the branch is behind the base branch -- this surfaces rebase needs early.

> **Constraint**: If the branch has never been pushed, there will be no remote tracking branch. In that case, report local branch state (modified files, commits) and suggest pushing with `git push -u origin [branch]`.

### Phase 4: PR Metadata

```bash
PR_JSON=$(gh pr view --json number,title,state,url,reviewDecision,statusCheckRollup,mergeable,reviews 2>/dev/null)

if [[ -z "$PR_JSON" ]]; then
    echo "No PR exists for this branch"
else
    PR_NUMBER=$(echo "$PR_JSON" | jq -r '.number')
    PR_TITLE=$(echo "$PR_JSON" | jq -r '.title')
    PR_STATE=$(echo "$PR_JSON" | jq -r '.state')
    PR_URL=$(echo "$PR_JSON" | jq -r '.url')
fi
```

If no PR exists, report the branch state and suggest creating one. Skip Phases 5-7.

> **Constraint**: If `gh pr view` fails, distinguish "no pull requests found" from a network/auth error. For network/auth errors, report the error and suggest `gh auth status`. Never invent a status when a command fails -- false status is worse than no status.

### Phase 5: CI Status

Show individual check names with pass/fail status so the user can see exactly which checks need attention.

```bash
gh pr checks --json name,state,conclusion 2>/dev/null | jq -r '.[] | "\(.conclusion // .state) \(.name)"'
```

> **Constraint**: If this command fails, report that CI data is unavailable rather than guessing. Saying "CI passing" when the command returned an error destroys trust in the report.

### Phase 6: Claude Review

Check for Claude Code review comments on the PR -- these automated reviews often contain actionable feedback that human reviewers may not catch.

```bash
CLAUDE_COMMENTS=$(gh pr view --json comments --jq '[.comments[] | select(
  (.author.login == "claude") or
  ((.author.login == "github-actions[bot]") and (.body | test("PR Review:|Claude|claude-code-action"; "i")))
)] | length')

if [[ "$CLAUDE_COMMENTS" -gt 0 ]]; then
    echo "Claude review completed ($CLAUDE_COMMENTS comments)"
else
    CLAUDE_WORKFLOW=$(gh run list --workflow=claude.yml --limit 1 --json conclusion,status --jq '.[0]' 2>/dev/null)
    if [[ -n "$CLAUDE_WORKFLOW" ]]; then
        STATUS=$(echo "$CLAUDE_WORKFLOW" | jq -r '.status // .conclusion')
        echo "Claude review status: $STATUS"
    else
        echo "No Claude review configured"
    fi
fi
```

### Phase 7: Human Reviews

Show reviewer names with their review state so the user knows who has reviewed and what the outcome was.

```bash
gh pr view --json reviews --jq '.reviews[] | "\(.author.login): \(.state)"'
gh pr view --json reviewDecision --jq '.reviewDecision'
```

Report conflicts, required approvals, and blocking checks to give a complete merge readiness picture:

```bash
gh pr view --json mergeable --jq '.mergeable'
```

### Phase 8: Status Report

Format all collected information into a structured report. Show every section that was gathered; if a section failed to load, say so explicitly rather than silently omitting it -- a partial report without explanation hides problems the user needs to know about.

```
PR STATUS
=========

Branch: [current] -> [base] ([N commits behind])

Local State:
  [clean/modified] working tree
  [ahead/behind] remote

PR #[N]: "[title]"
  State: [Open/Closed/Merged]
  URL: [url]

  CI Status:
    [pass/fail] [check-name] (per check)

  Claude Review:
    [status]

  Reviews:
    [reviewer]: [state] (per reviewer)

  Merge Status:
    [mergeable/conflicts/approvals needed]
```

> **Gate**: The report must include all sections. If any data-gathering phase returned an error, the report must state what information is unavailable and why, not silently drop the section.

---

## Reference Material

### Examples

**Feature Branch with Open PR**
User says: "/pr-status"
Actions:
1. Verify gh CLI available, fetch latest
2. Report branch `feature/auth` is 2 behind main
3. Show PR #45 is open, CI passing, 1 approval, no conflicts
4. Report ready to merge
Result: Complete status showing merge-ready PR

**No PR Exists**
User says: "/pr-status"
Actions:
1. Verify gh CLI, identify branch `fix/typo`
2. Report 3 modified files, 1 commit not pushed
3. Report no PR exists for this branch
Result: Branch state shown, suggest creating PR

**On Main Branch**
User says: "/pr-status"
Actions:
1. Detect current branch is main
2. List recent PRs if requested
3. Suggest switching to a feature branch
Result: Brief report noting user is on main

---

## Error Handling

### Error: "gh CLI Not Installed or Not Authenticated"
Cause: GitHub CLI missing or `gh auth login` not completed
Solution:
1. Report the specific missing prerequisite
2. Provide installation/auth URL
3. Stop -- do not attempt partial status without gh

### Error: "No Remote Tracking Branch"
Cause: Branch exists locally but has never been pushed
Solution:
1. Report local branch state (modified files, commits)
2. Note that no remote tracking branch exists
3. Suggest pushing with `git push -u origin [branch]`

### Error: "gh pr view Fails with Non-Zero Exit"
Cause: No PR exists for the branch, or network/auth issue
Solution:
1. Check if error is "no pull requests found" vs network error
2. For no PR: report branch state, suggest creating one
3. For network/auth: report the error, suggest `gh auth status`

---

## References

- PR creation and push: Call the Skill tool with `pr-workflow`. Use its Sync intent.
- Fixing review comments: Call the Skill tool with `pr-workflow`. Use its Fix intent.
- Code review: Call the Skill tool with `systematic-code-review`.
