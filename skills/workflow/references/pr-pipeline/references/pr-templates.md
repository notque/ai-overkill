# PR Templates and Examples

Full details for Phase 5 (CREATE PR) of the PR Pipeline: artifact-driven body generation, templates, and all usage examples.

---

## Artifact-Driven PR Body Generation

When planning artifacts exist, generate the PR body from them rather than writing freeform. Artifacts capture *intent* (why the change was made), which is more valuable to reviewers than a mechanical diff summary.

Check for artifacts in this order and build the PR body from what's available:

| Artifact | PR Section Generated | How to Extract |
|----------|---------------------|----------------|
| `task_plan.md` | **Summary** (from Goal section) and **Changes** (from completed tasks) | Read the Goal and Phases sections; list completed items as change bullets |
| Verification reports (`*-verification.md`, test output) | **Test Plan** (from verification output) | Extract pass/fail counts and key assertions verified |
| Review summaries (Phase 2 / Phase 4b output) | **Review Findings** (from reviewer results) | Summarize security/logic/quality verdicts |
| Deviation logs (ADR-076 repair actions) | **Deviations** section | List repair actions taken and why the original plan changed |

**Fallback**: If no artifacts exist, fall back to diff-based generation -- summarize changes from the diff and commit messages. This is the existing behavior and remains the default for ad-hoc PRs without planning artifacts.

## PR Body Template (Artifact-Driven)

```markdown
## Summary
<!-- From task_plan.md Goal section, or from commit messages if no plan -->
- [Goal statement]
- [Key change 1 from completed tasks]
- [Key change 2 from completed tasks]

## Changes
<!-- From task_plan.md completed phases/tasks -->
- [Completed task description]
- [Completed task description]

## Test Plan
<!-- From verification reports, or manual checklist if no reports -->
- [ ] [Verification result 1]
- [ ] [Verification result 2]

## Review Findings
<!-- From Phase 2 / Phase 4b review output -->
Security: PASS
Business Logic: PASS
Code Quality: PASS

## Deviations
<!-- From deviation logs, omit section if none -->
- [Deviation description and rationale]
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
