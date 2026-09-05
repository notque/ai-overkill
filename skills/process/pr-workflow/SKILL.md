---
name: pr-workflow
description: |
  Pull request lifecycle: commit, codex review, sync, review, fix, status,
  cleanup, and PR mining. Use when user wants to commit changes, get a
  second-opinion code review from Codex, push changes, create a PR, check PR
  status, fix review comments, clean up branches after merge, or mine tribal
  knowledge from PR reviews. Use for "commit my changes", "codex review",
  "push my changes", "create a PR", "pr status", "fix PR comments",
  "clean up branches", "mine PRs", or "address feedback".
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Task
  - Skill
  - AskUserQuestion
routing:
  force_route: true
  not_for: "general disagreement ('push back on a design'), committing to an idea ('commit to this approach'), pushing out the door, push notifications, social media reviews, metaphorical commit/merge ('commit to a decision', 'merge ideas in your head', 'merge the branches in your head', 'move forward and commit'), 'commit' meaning resolve/decide rather than git-commit — only for git push/commit/PR operations"
  triggers:
    - "push changes"
    - "push my changes"
    - "push to GitHub"
    - "push to remote"
    - "create PR"
    - "sync to GitHub"
    - "PR status"
    - "branch status"
    - "merge readiness"
    - "fix PR comments"
    - "resolve PR feedback"
    - "pr-fix"
    - "cleanup branches"
    - "clean up branches"
    - "merged branches"
    - "delete merged branch"
    - "prune branches"
    - "mine PRs"
    - "extract review comments"
    - "tribal knowledge"
    - "process PR feedback"
    - "address review comments"
    - "submit PR"
    - "create pull request"
    - "send for review"
    - "open PR"
    - "generate branch name"
    - "validate branch name"
    - "name branch"
    - "branch convention"
    - "git branch name"
    - "check CI"
    - "CI status"
    - "actions status"
    - "did CI pass"
    - "build status"
    - "CI passed"
    - "stage and commit"
    - "stage files commit"
    - "stage modified commit"
    - "commit staged"
    - "commit changes"
    - "commit these"
    - "commit my changes"
    - "commit my files"
    - "codex review"
    - "second opinion"
    - "code review codex"
    - "gpt review"
    - "cross-model review"
    - "git push"
    - "push to origin"
    - "push my branch"
    - "push the branch"
    - "ship it"
    - "ship this"
    - "ship this work"
    - "merge these fixes"
    - "merge this work"
    - "merge this in"
    - "make a pull request"
    - "draft a PR"
    - "draft pr"
    - "publish my changes"
    - "publish this"
    - "publish my work"
    - "let's get this reviewed"
    - "send this to GitHub"
    - "send to github"
    - "wrap up and merge"
    - "wrap this up and merge"
    - "land PR"
    - "land the PR"
    - "land this PR"
    - "merge contributor PR"
    - "rebase and merge PR"
    - "update changelog"
    - "release notes"
    - "curate changelog"
    - "decision brief"
    - "owner decision brief"
    - "authorization tier"
  category: git-workflow
  pairs_with:
    - verification-before-completion
    - code-linting
    - systematic-code-review
---

# PR Workflow Skill

Umbrella skill for the entire pull request lifecycle. Routes to the correct reference based on the PR task requested.

## Reference Loading Table

Detect the user's intent and load the appropriate reference file:

| Intent | Trigger phrases | Reference |
|--------|----------------|-----------|
| **Sync** (default) | "push", "create PR", "sync", "ship this" | `${CLAUDE_SKILL_DIR}/references/sync.md` |
| **Pipeline** | "submit PR", "full PR", "end-to-end PR", "open PR" | `${CLAUDE_SKILL_DIR}/references/pipeline.md` |
| **Fix** | "fix PR comments", "address review", "pr-fix", "resolve feedback" | `${CLAUDE_SKILL_DIR}/references/fix.md` |
| **Status** | "pr status", "branch status", "is my PR ready", "check CI" | `${CLAUDE_SKILL_DIR}/references/status.md` |
| **Cleanup** | "clean up branches", "delete merged branch", "prune" | `${CLAUDE_SKILL_DIR}/references/cleanup.md` |
| **Feedback** | "process PR feedback", "address reviews", "what did reviewers say" | `${CLAUDE_SKILL_DIR}/references/feedback.md` |
| **Miner** | "mine PRs", "extract review comments", "tribal knowledge", "reviewer patterns" | `${CLAUDE_SKILL_DIR}/references/miner.md` |
| **Branch name** | "generate branch name", "validate branch name", "name branch", "branch convention", "git branch name" | `${CLAUDE_SKILL_DIR}/references/branch-name.md` |
| **CI check** | "check CI", "CI status", "actions status", "did CI pass", "build status", "CI passed" | `${CLAUDE_SKILL_DIR}/references/ci-check.md` |
| **Commit** | "commit changes", "stage and commit", "commit my changes", "commit my files", "commit these" | `${CLAUDE_SKILL_DIR}/references/commit.md` |
| **Codex review** | "codex review", "second opinion", "code review codex", "gpt review", "cross-model review" | `${CLAUDE_SKILL_DIR}/references/codex-review.md` |
| **Land** | "land PR", "land the PR", "merge contributor PR", "rebase and merge PR" | `${CLAUDE_SKILL_DIR}/references/land-pr.md` |
| **Body safety** | any `gh` call writing or reading a PR/issue body | `${CLAUDE_SKILL_DIR}/references/gh-body-safety.md` |
| **Changelog** | "update changelog", "release notes", "curate changelog" | `${CLAUDE_SKILL_DIR}/references/changelog-curation.md` |
| **Decision brief** | "decision brief", "authorization tier", "ask the owner", "is it decision-ready" | `${CLAUDE_SKILL_DIR}/references/owner-decision-briefs.md` |
| **Risk classify** | automatic pre-review step; also "classify PR risk", "pr risk", "risk check" | `${CLAUDE_SKILL_DIR}/references/pr-risk-policy.md` |
| **INDEX conflict** | "INDEX.json conflict", "INDEX conflict on rebase", "two PRs regenerated INDEX", "regenerate INDEX after rebase" | `${CLAUDE_SKILL_DIR}/references/index-conflict-resolution.md` |

**Default action**: When invoked with no arguments or ambiguous intent, load `sync.md` (the most common PR use case).

## Review scope

Before dispatching reviewers, load `references/pr-risk-policy.md`. It owns risk classification, roster selection, and review reuse. Preserve explicit user and `/do` rosters and repository requirements; do not start a second review at each PR phase.

## PR body

Use **Summary → Changes → Notes**, following `.github/pull_request_template.md`. Passing `--body` or `--body-file` supplies the body instead of loading that template.

- **Summary:** State what changes and why in 1–3 plain sentences; name the relevant issue or ADR.
- **Changes:** One fact per line: what changed and where. Summarize large lists by shape and count; let the diff enumerate them.
- **Notes:** Include non-obvious decisions, deliberate omissions, follow-ups, gotchas, superseded PRs, and material plan deviations. Also include manual verification, gaps in CI coverage, migration/rollout ordering, and security-sensitive changes. Omit the section only when none apply.

Keep command dumps out of the body; GitHub Checks records CI results. Retain verification facts that CI does not establish, such as “Apply the column migration before deploying” or “Not covered by CI — Terraform plan checked manually.”

Use existing planning artifacts for intent and completed work; otherwise use the diff and commits. Describe the final change, not the conversation or abandoned approaches unless they explain a tradeoff.

Write the body to a temporary file with a quoted heredoc, then pass `--body-file`, following `${CLAUDE_SKILL_DIR}/references/gh-body-safety.md`. Read the body back before submitting it.

## Execution

Load the matching reference and execute within the user's existing authorization. Ask only for an uncovered action or an explicit applicable repository requirement; do not ask again for actions already authorized. Preserve repository branch protection and review requirements.
