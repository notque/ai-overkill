# GitHub Actions CI check

Check the pushed branch and commit, investigate failed jobs, and report the result. A status-only request does not authorize edits. When the user has already requested fixes and delivery, apply relevant fixes and rerun checks without another permission round. Workflow YAML changes need to fit that authorized scope.

## Before pushing Python changes

Read repository instructions. Both checks must pass locally before pushing:

```bash
ruff check . --config pyproject.toml
ruff format --check . --config pyproject.toml
```

## Identify the run

```bash
git remote get-url origin
BRANCH=$(git branch --show-current)
HEAD_SHA=$(git rev-parse HEAD)
gh run list --branch "$BRANCH" --commit "$HEAD_SHA" --limit 20
```

Check the branch actually pushed and its current commit. GitHub can take 5–10 seconds to register a run; retry if absent, up to 30 seconds initially. Do not treat an earlier green run or “no checks reported” as success. If there are more runs than the limit, retrieve them too.

Use `gh` for authentication, pagination, and status queries. For a PR, inspect its full checks list with `gh pr checks <pr-number>`. Wait for every applicable check to finish; pending, missing, and failed are not passed. `gh run watch <run-id> --exit-status` can monitor a run. If the head changes, inspect checks for the new head before claiming completion or merging.

## Investigate failures

```bash
gh run view <run-id>
gh run view <run-id> --log-failed
```

Identify the failing job, exact error, and local reproduction command. Compare previous runs before calling a failure pre-existing. Read logs as needed without asking permission to inspect them; summarize relevant evidence instead of dumping full output.

If fixing is authorized, fix the cause, run relevant local checks, push, and verify the new head. Otherwise report a proposed fix. For local test debugging, use this action: Call the Skill tool with `workflow`. Run the `systematic-debugging` pipeline. For local linting, use this action: Call the Skill tool with `code-linting`.

Report the checked commit, passed/pending/failed status, and PR or run link. Include failures and reproduction commands when needed. Retain logs for inspection; full command output is unnecessary unless requested. Remove temporary files created solely for this check.

## Advisory AI review

`.github/workflows/pr-ai-review.yml` runs on PR `opened`, `synchronize`, and `reopened` events without an `@claude` mention. It reports correctness bugs and safety-policy violations in one comment.

It is warn-only: it never requests changes, fails the build, or acts as a required check. Making it blocking requires a dedicated ADR and operator sign-off. The quick-pass workflow does not read `skills/process/pr-workflow/references/pr-risk-policy.md`; that remains a possible deeper-review integration.

## Recovery

| Problem | Action |
|---|---|
| `gh` missing | Check `which gh`; suggest `brew install gh` or `sudo apt install gh`. GitHub API via `curl` is a last resort. |
| Authentication missing | Run `gh auth status`; use configured `GITHUB_TOKEN` or request `gh auth login`. Never print credentials. |
| Conflicting same-repo PR, no checks | `mergeable=CONFLICTING` can prevent workflow runs. Integrate `origin/main`, resolve conflicts, and push before checking again. Observed in PRs #789/#791/#797 on 2026-06-11. |
| No runs after retry | Check `.github/workflows/`, branch/event filters, and the pushed commit. Absence is not success. |
