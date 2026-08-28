# Feature Release Phase

Merge the validated feature to main branch via PR, optionally tag a release, and clean up the feature worktree. Phase 5 of the feature lifecycle (design → plan → implement → validate → **release**).

## Instructions

### Phase 0: PRIME

1. Read and follow the repository CLAUDE.md before any other action. Repository-level conventions override defaults here.

2. Verify feature state is `release` and `validate` is completed. All state operations go through the state script -- never manipulate state files directly:
   ```bash
   python3 ~/.claude/scripts/feature-state.py gate FEATURE release.merge-strategy
   ```

3. Load all artifacts: design document, plan, implementation summary, and validation report. These provide the raw material for PR content in the next phase; skipping any artifact risks an incomplete PR description.

4. Confirm validation passed before proceeding. A feature with failing validation cannot be released -- there are no exceptions. If validation has not passed, stop and direct the user to run the validate phase first.

**Gate**: All artifacts loaded. Validation passed. State confirmed as `release`. Proceed.

### Phase 1: EXECUTE (Release)

**Step 1: Generate PR Content**

From the accumulated artifacts, generate a PR description following this structure:

```markdown
## Summary
[From design document problem statement]

## Changes
[From implementation artifact -- what was built]

## Testing
[From validation report -- what was verified]

## Design Decision
[From design document -- why this approach]
```

**Step 2: Create PR**

Use existing pr-pipeline patterns:

1. Ensure feature branch is pushed to remote.
2. Create PR via `gh pr create` targeting main. Always merge via pull request -- never push directly to main, even for small features. This is non-negotiable because direct pushes bypass review and CI.
3. Use squash merge (default) so the feature branch collapses into a single clean commit on main.
4. Use conventional commit format for the squash commit message. Do not add "Co-Authored-By" or "Generated with Claude Code" attribution lines.
5. Link to design decisions in the PR body.

**Step 3: Post-Merge Cleanup** (after PR is merged)

Do not begin cleanup until the PR merge is confirmed. Deleting the branch or worktree before merge confirmation risks losing work.

1. Clean up worktree:
   ```bash
   python3 ~/.claude/scripts/feature-state.py worktree FEATURE cleanup
   ```

2. Archive feature state:
   ```bash
   python3 ~/.claude/scripts/feature-state.py complete FEATURE
   ```

3. Update L0 (remove feature from active list).

**Optional post-merge actions** (only when explicitly enabled by the user):
- **Version Bump**: Bump version number based on change type (patch/minor/major).
- **Changelog Update**: Add entry to CHANGELOG.md.
- **Tag Release**: Create git tag after merge.

**Gate**: PR created/merged. Cleanup complete.

### Phase 2: VALIDATE

- [ ] PR was created successfully
- [ ] Feature branch exists on remote
- [ ] PR description includes design context

### Phase 3: CHECKPOINT

1. Save release artifact:
   ```bash
   echo "RELEASE_NOTES" | python3 ~/.claude/scripts/feature-state.py checkpoint FEATURE release
   ```

2. Report completion:
   ```
   Feature [NAME] released successfully.
   - Design → Plan → Implement → Validate → Release: complete
   - PR: [URL]
   - Review findings: [N] resolved, [M] carried into the PR body
   ```

## Error Handling

| Scenario | Action |
|----------|--------|
| Validation not passed | Stop. Direct user to run the validate phase. Do not proceed. |
| PR creation fails | Check branch is pushed, `gh` is authenticated, and target branch exists. Retry once. |
| Worktree cleanup fails | Log the error but do not block completion. User can clean up manually. |
| State script errors | Report the exact error. Do not fall back to manual file manipulation. |
