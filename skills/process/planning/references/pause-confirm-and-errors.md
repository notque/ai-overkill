# Pause-Work Confirm Output and Error Handling

Verbatim Phase 5 (CONFIRM) summary template and error matrix.

## Phase 5 confirm summary

Display the handoff summary:

```
===================================================================
 SESSION PAUSED
===================================================================

 Handoff files created:
   - HANDOFF.json (machine-readable)
   - .continue-here.md (human-readable)

 Completed: N task(s)
 Remaining: N task(s)
 Blockers: N
 Uncommitted files: N
 False completions: N placeholder(s) found
 ADRs drafted: N

 Next action: <brief next_action summary>

 Resume with: /resume-work
===================================================================
```

## Error Handling

### Error: Not in a Git Repository
**Cause**: `git rev-parse --show-toplevel` fails — no `.git/` directory found
**Solution**: Handoff files require git context for branch and uncommitted file detection. Navigate to a git repository root and retry.

### Error: Cannot Determine Session Work
**Cause**: No commits on current branch, no task_plan.md, no uncommitted changes — nothing to hand off
**Solution**: If the session genuinely did no work, there is nothing to hand off. Inform the user: "No work detected to hand off. If you made changes that aren't committed or tracked, describe what you were working on and I'll create the handoff manually."

### Error: No decisions found to extract
**Cause**: The session made no architectural decision that clears the decision-vs-tip heuristic
**Solution**: Proceed to Phase 4 with an empty `drafted_adrs` list and omit the ADR section from both handoff files. The handoff files are the primary deliverable; ADR extraction is a best-effort enhancement. A session of pure implementation work legitimately drafts no ADRs.

### Error: HANDOFF.json Already Exists
**Cause**: A previous `/pause` created handoff files that were not yet consumed by `/resume-work`
**Solution**: Warn the user that stale handoff files exist. Offer to overwrite (default) or append. Overwriting is almost always correct — stale handoffs from abandoned sessions should not block new ones.
