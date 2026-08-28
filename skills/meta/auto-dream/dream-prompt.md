You are running the Auto-Dream memory consolidation cycle.
This is a headless background job — no interactive session, no CLAUDE.md, no hooks.
All instructions are contained in this prompt.

## Execution order — READ THIS FIRST

Execute phases in the sequence below (this differs from numbered order):

**SCAN (1) → ANALYZE (2) → REPORT (6, first write: planned changes) → CONSOLIDATE (3) → SYNTHESIZE (4) → SELECT (5) → REPORT (6, second write: actual results)**

The REPORT must be written BEFORE CONSOLIDATE begins any filesystem operations. This is a hard safety rule — the report is the audit trail. If the cycle is interrupted after writing the report but before consolidation completes, the report shows exactly what was planned.

## Context

The wrapper script provides these paths as environment variables. Use them exactly as shown:

Project memory directory: ${DREAM_MEMORY_DIR}
State output directory: ${DREAM_STATE_DIR}
Git repository: ${DREAM_REPO_DIR}
Project hash (for injection file naming): ${DREAM_PROJECT_HASH}

All paths are absolute. These are substituted by the wrapper script at runtime via `envsubst`.

## Dry-run mode

Current dry-run setting: ${DREAM_DRY_RUN_MODE}

If `${DREAM_DRY_RUN_MODE}` is `yes`:
- Phases 1 (SCAN) and 2 (ANALYZE) run normally and write their output files.
- Phase 3 (CONSOLIDATE) and Phase 4 (SYNTHESIZE) describe proposed changes in the report but make NO filesystem writes.
- Phase 5 (SELECT) runs normally (read-only).
- Phase 6 (REPORT) writes the report file normally.

If `${DREAM_DRY_RUN_MODE}` is `no`, run all phases fully.

## Safety constraints — these are hard rules, never deviate

1. **Never delete files.** Archiving means moving to the `archive/` subdirectory, not deleting. If `archive/` does not exist, create it first.
2. **Write the REPORT (Phase 6) before Phase 3 executes any filesystem operations.** The report is the audit trail. If the cycle is interrupted after writing the report, the report shows exactly what was planned.
3. **Maximum 5 memory changes per cycle.** If analysis identifies more than 5 actionable items, prioritize: (1) clear duplicates first, (2) stale project memories, (3) synthesis. Excess items go in the report as "deferred to next cycle."
4. **Flag conflicts, never auto-resolve.** Conflicting memories require human judgment. Leave both files untouched, flag in the report.
5. **Preserve YAML frontmatter when merging.** The merged file carries frontmatter from the more-recently-modified source, plus a `merged_from` list of source filenames.
6. **Update MEMORY.md atomically.** Write to MEMORY.md.tmp, then rename to MEMORY.md.

## Phase 1: SCAN

Read the following and compile a scan document:

1. Read `${DREAM_MEMORY_DIR}/MEMORY.md` to get the list of all memory files.
2. For each memory file listed in MEMORY.md:
   - Read the file (or first 30 lines if it is long)
   - Note: filename, type (from YAML frontmatter `type:` field), last-modified date, and a one-line summary
3. Read the recent git log:
   ```bash
   git -C ${DREAM_REPO_DIR} log --oneline -20
   ```

Write the scan document to:
`${DREAM_STATE_DIR}/dream-scan-{YYYY-MM-DD}.md`

where `{YYYY-MM-DD}` is today's date. Create the state directory if it does not exist:
```bash
mkdir -p ${DREAM_STATE_DIR}/
```

Scan document format:
```markdown
# Dream Scan: {YYYY-MM-DD}

## Memory Files
- Total: N files
- By type: user(N), project(N), feedback(N), reference(N), insight(N)

### File Inventory
| File | Type | Last Modified | Summary |
|------|------|---------------|---------|
| filename.md | feedback | 2026-01-15 | one-line summary |
...

## Recent Git Activity (last 20 commits)
- [commit list]

## Observations
- Any notable patterns noticed during scan
```

## Phase 2: ANALYZE

Read the scan document from Phase 1. Identify:

**Stale memories**: Project memories whose subject is no longer active.
Staleness signals (ALL three should be present for a stale call):
- The memory's topic appears in NO recent git commits (last 20)
- The memory's topic appears in NO recent session summaries (last 7 days)
- The memory file is older than 30 days

**Duplicate memories**: Two or more memories covering substantially the same ground.
Match on semantic similarity of content, not filename. Two memories are duplicates if
a reader could replace one with the other without losing information.

**Conflicting memories**: Two memories that give contradictory guidance.
Example: one says "always use absolute paths", another says "relative paths are fine for scripts".
Flag for human review instead of auto-resolving.

**Recurring patterns**: Behaviors that recur across 3 or more memory files or recent commits in the scan window.
Examples: same error type appears repeatedly, same file modified in most sessions,
same skill invoked every session.

Write the analysis document to:
`${DREAM_STATE_DIR}/dream-analysis-{YYYY-MM-DD}.md`

Analysis document format:
```markdown
# Dream Analysis: {YYYY-MM-DD}

## Stale Memories
| File | Age (days) | Reason | Proposed Action |
|------|-----------|--------|-----------------|
| old-project-memory.md | 45 | No git/session refs in 7 days, project complete | Archive |

## Duplicate Memories
| File A | File B | Similarity | Proposed Action |
|--------|--------|-----------|-----------------|
| feedback_a.md | feedback_b.md | Both say "use absolute paths in bash" | Merge → merged_absolute_paths.md |

## Conflicting Memories
| File A | File B | Conflict Description | Proposed Action |
|--------|--------|---------------------|-----------------|
| pref_a.md | pref_b.md | A says ruff, B says flake8 | FLAG for human review |

## Cross-Session Patterns
| Pattern | Occurrences | Evidence | Proposed Action |
|---------|---------|----------|-----------------|
| make check before every commit | 8 of 10 commits | commit SHAs | Synthesize insight memory |

## Prioritized Action List (max 5 changes)
1. [action type]: [file(s)] — [reason]
2. ...
(if more than 5: list remaining as "Deferred to next cycle")
```

## Phase 3: CONSOLIDATE

**STOP — Before executing this phase**, verify that the REPORT (Phase 6) has already been written with the planned changes from Phase 2. The report must exist as an audit trail before any filesystem operations begin. If you have not yet written the report, go to Phase 6 and write the initial report first, then return here.

Apply the prioritized action list from Phase 2. Maximum 5 changes.

**IMPORTANT**: If `${DREAM_DRY_RUN_MODE}` is `yes`, skip all filesystem operations in this phase.
Describe what WOULD be done in the report (Phase 6) but make no changes.

For each archive action:
1. Create `archive/` directory if it does not exist:
   ```bash
   mkdir -p ${DREAM_MEMORY_DIR}/archive/
   ```
2. Move the file to archive/:
   ```bash
   mv ${DREAM_MEMORY_DIR}/{filename}.md \
      ${DREAM_MEMORY_DIR}/archive/{filename}.md
   ```
3. Remove the entry from MEMORY.md (write to MEMORY.md.tmp, then rename).

For each merge action:
1. Read both source files completely.
2. Create merged content: combine the information from both files into a single coherent memory.
   Use the frontmatter from the more-recently-modified source file.
   Add `merged_from: [source_a.md, source_b.md]` to the frontmatter.
3. Write merged file to memory/:
   ```bash
   # Write to the merged filename
   ```
4. Archive both source files (as above).
5. Add the merged file entry to MEMORY.md, remove the source entries.
6. MEMORY.md update: write to MEMORY.md.tmp, then rename to MEMORY.md.

For each conflict: leave files unchanged. Record in report.

## Phase 4: SYNTHESIZE

Create new insight memories from cross-session patterns identified in Phase 2.
Maximum 2 new insight memories per cycle.

**IMPORTANT**: If `${DREAM_DRY_RUN_MODE}` is `yes`, skip all filesystem writes.
Describe what WOULD be synthesized in the report but make no writes.

Each insight memory format:
```markdown
---
type: insight
created: {YYYY-MM-DD}
synthesized_from: [session_id_1, session_id_2, ...]
---

# {Title describing the pattern}

{2-4 paragraphs describing the cross-session behavioral pattern, what it means,
and why it matters for future sessions. Write in the same voice as other memory files
in the project — first-person observations, concrete and specific.}
```

Write to: `${DREAM_MEMORY_DIR}/insight_{topic}_{YYYY-MM-DD}.md`

Add each new insight to MEMORY.md (write to MEMORY.md.tmp, then rename).

## Phase 5: SELECT

Build an injection-ready payload for the next session start.

This phase selects the most relevant current memories and formats them for injection
into the session context. This replaces what retro-knowledge-injector.py used to do
(brute-force top-20 by confidence) with LLM-curated selection.

Steps:
1. Read the current MEMORY.md to get the updated memory list (after consolidation).
2. Read each memory file (first 30 lines is sufficient for selection).
3. Select the top entries most likely to be useful in the next session. Criteria:
   - Feedback memories with concrete, actionable guidance: high priority
   - Reference memories for active project areas (check git log): high priority
   - Insight memories from recent synthesis: high priority
   - Stale project memories not yet archived: low priority
   - Budget: ~2000 tokens (~8000 characters) total for the injection payload
4. Format the selected memories as a `<retro-knowledge>` block (matching the format
   that was used by retro-knowledge-injector.py so downstream consumers still work):

```
<retro-knowledge>
**Accumulated knowledge from prior sessions.** Use these patterns where applicable.
Adapt, don't copy. Note where patterns do NOT apply to the current task.

## {Topic Category}
- {key}: {first line of memory content}

## {Another Category}
- {key}: {first line of memory content}

</retro-knowledge>
```

The project hash is provided as `${DREAM_PROJECT_HASH}` by the wrapper script.

Write the injection payload atomically to avoid partial writes if interrupted:
1. Write to: `${DREAM_STATE_DIR}/dream-injection-${DREAM_PROJECT_HASH}.md.tmp`
2. Rename: `mv ${DREAM_STATE_DIR}/dream-injection-${DREAM_PROJECT_HASH}.md.tmp ${DREAM_STATE_DIR}/dream-injection-${DREAM_PROJECT_HASH}.md`

Create the state directory if it does not exist:
```bash
mkdir -p ${DREAM_STATE_DIR}/
```

## Phase 6: REPORT

Write the dream summary. This phase runs twice: once before CONSOLIDATE as a pre-execution
plan (written after ANALYZE), and again after all phases complete with actual results.
If Phases 3-5 made filesystem changes, describe them here for audit purposes. If running
dry-run, describe what WOULD have been done.

Write to: `${DREAM_STATE_DIR}/last-dream-{YYYY-MM-DD}.md`
Also write the same content to: `${DREAM_STATE_DIR}/last-dream.md`
(last-dream.md is the latest-pointer that the session-start hook reads)

Report format:
```markdown
# Dream Report: {YYYY-MM-DD}

## One-Line Summary
{Single natural language sentence summarizing the dream outcome. Examples: "Scanned 12 memories, no changes needed (dry-run)." or "Consolidated 3 memories, synthesized 1 insight."}

## Summary
- Memories scanned: N
- Commits reviewed: M (last 20)
- Changes made: K (max 5)
- Conflicts flagged: J (requires human review)
- Dry run: yes/no

## Consolidations
- Archived: [list of archived memory names with reason]
- Merged: [list of merged memory pairs with result file]

## New Insights
- [insight-memory-name]: [one-line description of pattern]

## Conflicts Requiring Review
- [memory-name] vs [memory-name]: [description of conflict]

## Injection Payload
- File: ${DREAM_STATE_DIR}/dream-injection-${DREAM_PROJECT_HASH}.md
- Entries selected: N
- Token estimate: ~N tokens

## No-Op Reason
(only present if K=0) [explanation of why no changes were made]

## Deferred to Next Cycle
(only present if items were deferred) [list of deferred items with reason]
```

After writing both report files, output a one-line summary to stdout:
`[dream] {K} memories consolidated, {synthesis_count} insights synthesized — {YYYY-MM-DD}`

## Execution sequence

Execute phases in order: SCAN → ANALYZE → REPORT (write planned changes) → CONSOLIDATE → SYNTHESIZE → SELECT → REPORT (update with actual results) → done.

The REPORT is written twice:
1. Before CONSOLIDATE: write the planned changes as a "pre-execution plan"
2. After all phases complete: update with actual results (overwrite the same file)

This ensures the report exists as an audit trail before any filesystem operations.
