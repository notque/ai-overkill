# Quick Skill Examples and Error Handling

## Usage Examples

**Example 1: Base Mode**

User says: `/quick add --verbose flag to the CLI`
1. Generate ID: 260322-001
2. Plan: add flag definition, wire to handler, update help text (3 edits)
3. Create branch: `quick/260322-001-add-verbose-flag`
4. Execute edits, commit, log to STATE.md

**Example 2: With Research**

User says: `/quick --research fix the timeout bug in auth middleware`
1. RESEARCH: Read auth middleware, identify timeout source, trace call path
2. PLAN: change timeout value in config, update middleware to use it (2 edits)
3. EXECUTE, COMMIT, LOG

**Example 3: Escalated from --trivial**

`/quick --trivial` hit 3-edit limit while fixing a bug across 5 files.
1. Quick picks up with context: "Continuing from --trivial -- 3 files already edited"
2. PLAN: remaining 2 files to edit
3. EXECUTE remaining edits, COMMIT all changes, LOG as tier `trivial->quick`

**Example 4: Full Rigor**

User says: `/quick --full update payment amount rounding logic`
1. PLAN: identify rounding function, change to banker's rounding
2. EXECUTE the edit
3. VERIFY: run payment tests, lint, review diff
4. COMMIT, LOG

## Task ID Format

Base36 sequence: `001, 002, ... 009, 00a, 00b, ... 00z, 010, ...`

Full ID: `YYMMDD-xxx` (e.g., `260322-001`, `260322-00a`)

## Error Handling

### Error: Task ID Collision
**Cause**: Two quick tasks started in the same second with the same sequence
**Solution**: Increment the sequence number. If STATE.md is corrupted, scan git log for `Quick task YYMMDD-` patterns to find the true next ID.

### Error: Scope Exceeds Quick Tier
**Cause**: Task grows beyond the contained, single-threaded tier.
**Solution**: Use `/do` for multiple components, architectural changes, or parallel work. More than 15 edits alone is advisory: suggest an upgrade and continue within existing authorization if the task remains contained.

### Error: Test Failure in --full Mode
**Cause**: Quality gate found issues with the changes
**Solution**: Fix the failing tests. If the fix requires significant additional work, note it in STATE.md and suggest a follow-up `/quick` task rather than expanding scope.

### Error: Branch Conflict
**Cause**: Branch `quick/<task-id>-...` already exists
**Solution**: Increment the task ID sequence number and try again.
