# Resume Work Reference

## Overview

This reference reconstructs session state from handoff artifacts so work can continue without wasting time re-reading files and re-discovering decisions. It is the consumer half of the pause/resume pair — the pause intent creates the artifacts, this reference consumes them.

The priority cascade exists because handoff quality varies:
1. **HANDOFF.json** — Best case. Machine-readable, structured, created by explicit pause. Contains reasoning context.
2. **.continue-here.md** — Good case. Human-readable prose. May exist without JSON if user wrote it manually.
3. **task_plan.md** — Fallback. Records task structure but not session reasoning. Better than nothing.
4. **git log + git status** — Last resort. Can infer recent activity but cannot reconstruct reasoning or rejected approaches.

Each level down the cascade loses more context, so this reference always starts from the top.

---

## Instructions

### Phase 1: DISCOVER

**Goal**: Find the best available state source using the priority cascade. Always check sources in order to ensure no high-quality context is lost (higher sources contain richer information than lower ones).

**Step 1: Identify project root**

```bash
git rev-parse --show-toplevel
```

**Step 2: Check for HANDOFF.json (Priority 1)**

Look for `{project_root}/HANDOFF.json`. If found:
- Read and parse the JSON
- Check `created_at` timestamp — if older than 24 hours, set `stale_warning = true` and plan to alert user before proceeding
- This is the richest source: proceed to Phase 2 with full structured data
- Also read `.continue-here.md` if it exists (for supplementary prose context)

**Step 3: Check for .continue-here.md (Priority 2)**

If no HANDOFF.json but `.continue-here.md` exists:
- Read the prose content
- Extract what you can: task description, completed items, next action, decisions
- Note that reasoning context may be limited compared to JSON handoff

**Step 4: Check for task_plan.md (Priority 3)**

If neither handoff file exists but `task_plan.md` exists:
- Read the plan
- Extract: completed phases `[x]`, remaining phases `[ ]`, decisions, errors, current status
- Note: this source captures task structure but not session reasoning

**Step 5: Fall back to git reconstruction (Priority 4)**

If no handoff files and no task_plan.md:

```bash
# Recent activity
git log --oneline -20

# Current branch context
git branch --show-current

# Uncommitted work
git status --short

# What's changed
git diff --stat
```

Synthesize a best-effort summary from git state. This is the least precise reconstruction — it shows WHAT happened but not WHY. Never skip to this source if higher-priority sources exist, as that would lose context.

**Step 6: Set reconstruction quality indicator**

| Source | Quality | Missing |
|--------|---------|---------|
| HANDOFF.json | Full | Nothing — richest source |
| .continue-here.md | Good | Structured data, may lack reasoning detail |
| task_plan.md | Partial | Session reasoning, rejected approaches, mental model |
| git log | Minimal | All reasoning context, decisions rationale, next action specifics |

**GATE**: At least one state source found and read. If ALL sources are empty (no handoff, no plan, no git history), inform user: "No session state found. Use /do to start a new task."

### Phase 2: RECONSTRUCT

**Goal**: Build a coherent state picture from available sources. Always present a status dashboard before taking action — the user needs to confirm the reconstructed state matches reality, since self-assessment of "what I was doing" is inherently fallible.

**Step 1: Verify uncommitted files**

If the handoff reports `uncommitted_files`, check whether they still exist (work may have been lost during worktree cleanup or manual revert):

```bash
# For each file in uncommitted_files list
git status --short -- <file>
```

Flag any files that were listed as uncommitted but are now missing — these represent potential work loss.

**Step 2: Check for false completions**

If the handoff reports `false_completions`, verify those placeholder markers still exist in the codebase. They may have been fixed by manual intervention between sessions.

**Step 3: Synthesize status dashboard**

Build the dashboard from available data. This dashboard is your knowledge checkpoint — it prevents false assumptions from carrying into the resumed session:

```
===================================================================
 SESSION RESUMED
===================================================================

 Source: HANDOFF.json (created: <timestamp>) [STALE WARNING if applicable]
 Branch: <branch> (base: <base_branch>)

 Task: <task_summary>

 Completed:
   - <completed item 1>
   - <completed item 2>

 Remaining:
   - <remaining item 1>
   - <remaining item 2>

 Blockers: <blockers or "None">

 Key Decisions:
   - <decision>: <reasoning>

 Uncommitted Work: <N file(s)> [WARNING: N file(s) missing if applicable]

 False Completions: <N placeholder(s)> [or "None detected"]

 Next Action:
   <next_action description>

===================================================================
```

**GATE**: Status dashboard constructed. Ready to present to user.

### Phase 3: PRESENT

**Goal**: Show the user what was reconstructed and confirm before proceeding. Never skip the dashboard — it is the validation checkpoint that catches assumptions made by the new session before they cause problems.

**Step 1: Display status dashboard**

Show the dashboard from Phase 2.

**Step 2: Handle stale handoff warning**

If `stale_warning` is true, warn the user before proceeding (stale handoffs may describe work superseded by manual changes between sessions):
```
WARNING: Handoff is from <timestamp> (>24 hours ago).
State may not reflect manual changes made since then.
Proceed with this handoff or discard it? [proceed/discard]
```

If user discards, fall to next priority level in cascade.

**Step 3: Determine action mode**

- **Quick resume** (user said "continue", "resume", or similar with no qualifiers): Skip options menu and proceed directly to Phase 4 to execute `next_action`. This optimizes for the common case where the user trusts the handoff and wants to get back to work fast.
- **Review mode** (user said "what was I doing", "where did I leave off", or asked a question): Display dashboard only, wait for user to choose what to do next

**GATE**: User has seen the dashboard. In quick resume mode, proceed to Phase 4. In review mode, wait for user direction.

### Phase 4: EXECUTE

**Goal**: Route to the next action and clean up handoff files (they are ephemeral session artifacts, not persistent state, so keeping them risks future resume calls loading outdated context).

**Step 1: Execute next action**

Take the `next_action` from the handoff and execute it:
- If it matches a skill trigger (e.g., "run tests" -> `vitest-runner`), route through `/do`; the dispatch prompt must say `Call the Skill tool with \`skill-name\`.`
- If it describes a code change, proceed with the implementation directly
- If it requires user input (e.g., "need clarification on threshold"), present the question

Carry forward all context from the handoff: decisions made, approaches rejected, gotchas to avoid. Honor previous session's findings unless circumstances have changed — reexploring rejected approaches burns context on work already done.

**Cache check before re-dispatching agents.** When `next_action` resumes a parallel agent wave (fan-out dispatch) that was interrupted, check the handoff's `agent_outputs` cache before dispatching each agent — reusing a finished agent's output instead of re-running it saves tokens. For each agent about to be dispatched:

1. Compute its input hash with `scripts/feature-state.py`'s `agent_input_hash(prompt, inputs)` over the exact dispatch input (prompt text plus any inputs that determine the agent's output). Determinism is the contract: an unchanged input yields the same hash as the previous session.
2. Look it up with `lookup_agent_output(handoff, input_hash)`. On a **hit**, reuse the cached `output` and skip dispatch. On a **miss** (or any input that changed since pause), dispatch the agent normally, then record the result with `store_agent_output(handoff, input_hash, output, label, timestamp)` so a later interruption can reuse it too.

A handoff with no `agent_outputs` field loads as an empty cache (`load_agent_outputs` returns `{}`) — every agent is a clean miss, so legacy handoffs and non-wave resumes behave exactly as before. Use the script helpers for hashing and lookup rather than reimplementing the hash in prose, because only identical normalized hashing across sessions makes a cache hit reliable.

**Step 2: Clean up handoff files**

After the next action has been initiated (not necessarily completed — just successfully started), delete the one-shot handoff artifacts to prevent stale state:

```bash
# Remove one-shot handoff artifacts
rm -f HANDOFF.json .continue-here.md
```

If `--keep` flag was provided, skip deletion (use only for debugging).

**Step 3: Update task_plan.md if present**

If `task_plan.md` exists, update its status line to reflect that the session has resumed. The plan is the persistent record; handoff is the ephemeral session context:
```
**Status**: Resumed from handoff — executing: <next_action summary>
```

**GATE**: Next action initiated. Handoff files cleaned up. Session is now in active work mode. Note: This reference never modifies code, resets git state, or discards uncommitted changes — it only reads and deletes handoff files.

---

## Error Handling

### Error: No State Sources Found
**Cause**: No HANDOFF.json, no .continue-here.md, no task_plan.md, and git log is empty or on a fresh branch
**Solution**: Inform user: "No session state found to resume from. Use /do to start a new task, or describe what you were working on and I'll reconstruct manually."

### Error: HANDOFF.json Parse Failure
**Cause**: HANDOFF.json exists but contains invalid JSON (corrupted, partially written, manually edited badly)
**Solution**: Warn user about the parse error. Fall through to .continue-here.md if it exists, otherwise fall to task_plan.md. Do not silently ignore the error — the user should know their handoff was corrupted.

### Error: Uncommitted Files Missing
**Cause**: Handoff reports uncommitted files that no longer exist (worktree cleanup, manual deletion, git checkout)
**Solution**: Alert the user with specific file names. These changes are likely lost. The user may need to recreate them — the handoff's `context_notes` and `decisions` can help guide reconstruction.

### Error: Stale Handoff Rejected
**Cause**: User chose to discard a stale (>24h) handoff
**Solution**: Delete the stale handoff files and fall through to the next priority level in the cascade (task_plan.md or git log). Proceed with the lower-quality reconstruction.

---

## References

### Related Intents
- `pause` (planning umbrella) — Creates the handoff artifacts this reference consumes
- `do` — Routes next_action to appropriate agent/skill for execution
- `workflow-orchestrator` — For complex multi-phase tasks that benefit from handoff between phases
