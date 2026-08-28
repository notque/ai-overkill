# Pause Work Reference

Capture ephemeral session reasoning into durable artifacts so the next session can resume without wasting time on context reconstruction. `task_plan.md` records WHAT tasks exist; this reference captures WHY the current session chose a particular approach, what it rejected, and what it planned to do next.

Two output files serve different audiences because each addresses a distinct use case:
- `HANDOFF.json` — machine-readable, consumed by the `resume` intent for automated state reconstruction. Must always be produced to enable resume routing.
- `.continue-here.md` — human-readable, for users who want to understand session state without starting a new session. Must always be produced to support human-only resumption paths.

Skipping either file breaks half the use case: without the JSON, resume cannot detect handoff state automatically; without the markdown, users cannot quickly grok where things stand.

## Instructions

### Phase 1: GATHER

**Goal**: Collect all state needed for the handoff.

Steps (read CLAUDE.md, identify project root via `git rev-parse`, collect git state — branch, uncommitted files, diff stats, recent commits, scan modified files for false completions using placeholder markers `TODO|FIXME|PLACEHOLDER|TBD|XXX|HACK|stub|not yet implemented`, read `task_plan.md` if present, read `.adr-session.json` if present): `pause-gather-steps.md`.

Rationale for false-completion scan: placeholder markers indicate work that looks done but is not — this is the most dangerous handoff failure mode.

**GATE**: Git state collected. Modified file list available. Placeholder scan complete. Ready to synthesize.

### Phase 2: SYNTHESIZE

**Goal**: Combine gathered state with session reasoning into handoff content.

Populate five fields — `completed_tasks` (specific: "Implemented scoring module in scripts/quality-score.py", not "Did some work"), `remaining_tasks` (from unchecked task_plan phases, placeholder markers, known incomplete work), `decisions` (format `{"description": "reasoning"}` — the highest-value content because git log shows WHAT but not WHY or what was rejected), `next_action` (exact action, file paths, function names, integration points, not "continue working"), `context_notes` (mental model, rejected approaches, gotchas, assumptions). Detailed field guidance: `pause-synthesize-fields.md`.

**GATE**: All handoff fields populated with specific, actionable content. No vague entries like "continue work" or "finish implementation."

### Phase 3: EXTRACT DECISIONS

**Goal**: Take the decisions this session made, filter for the ones that warrant ADRs, and draft ADR skeletons for each candidate. This phase runs before WRITE so that ADR data is available for inclusion in both handoff files — passing extracted data downstream is cheaper than appending to files after the fact.

Steps (collect this session's decisions from the Phase 2 `decisions` field, filter with the decision-vs-tip heuristic table, get next ADR number via `adr-query.py next-number`, draft ADR skeletons to `adr/{N}-{slug}.md`, pass `drafted_adrs` list to Phase 4): `pause-extract-decisions.md`. The ADR skeleton template and filter heuristic live in that same reference.

**GATE**: Session decisions collected. Candidates filtered using the decision-vs-tip heuristic. ADR skeleton files written to disk for any candidates found. `drafted_adrs` data available for Phase 4.

### Phase 4: WRITE

**Goal**: Write both handoff files to the project root. This reference only creates files and leaves existing code and git state untouched because it must be safe to invoke repeatedly without side effects.

**Step 1: Write HANDOFF.json** to `{project_root}/HANDOFF.json` with UTC ISO 8601 timestamps. Include `drafted_adrs` from Phase 3 — omit the field entirely (not null, not `[]`) if no ADRs were drafted, so the resume intent can detect absence reliably. When pausing mid-way through a parallel agent wave, also persist already-returned agents under `agent_outputs` (keyed by `agent_input_hash`) so the resume intent can reuse them instead of re-dispatching; omit the field when no wave was in progress. Full JSON template and cache helper guidance: `pause-write-templates.md`.

**Step 2: Write .continue-here.md** to `{project_root}/.continue-here.md` because humans need prose-form state before committing to the resume intent. Include the "ADRs Drafted from Session Learnings" section only if `drafted_adrs` is non-empty. Full markdown template: `pause-write-templates.md`.

**Step 3: Suggest WIP commit if needed** — If uncommitted changes were detected in Phase 1, display a warning. Let the user decide whether to commit because changes may be experimental, broken, or staged for review. Warning text: `pause-write-templates.md`.

**Step 4: Optional commit of handoff files** — If `--commit` flag was provided, run `git add HANDOFF.json .continue-here.md && git commit -m "chore: session handoff artifacts"`.

**GATE**: Both files written to project root. User notified of uncommitted work if any.

### Phase 5: CONFIRM

**Goal**: Display summary and confirm handoff was captured. Skip this phase if `--quiet` flag was provided.

Full handoff summary banner (completed/remaining/blockers/uncommitted/false-completions/ADR counts, next-action line, resume hint): `pause-confirm-and-errors.md`.

## Error Handling

Common errors (not in a git repository, cannot determine session work, no decisions found to extract, HANDOFF.json already exists) and solutions: `pause-confirm-and-errors.md`.

## References

| Reference | When to Load | Content |
|-----------|-------------|---------|
| `pause-gather-steps.md` | Phase 1 GATHER | Git state commands, placeholder-marker scan, task_plan.md + .adr-session.json reads |
| `pause-synthesize-fields.md` | Phase 2 SYNTHESIZE | Field-by-field guidance for completed_tasks, remaining_tasks, decisions, next_action, context_notes |
| `pause-extract-decisions.md` | Phase 3 EXTRACT | Session-decision collection, decision-vs-tip filter heuristic, ADR skeleton template |
| `pause-write-templates.md` | Phase 4 WRITE | Full HANDOFF.json template, .continue-here.md template, WIP-commit warning |
| `pause-confirm-and-errors.md` | Phase 5, Error Handling | Summary banner template, error matrix with causes and solutions |

### Related Intents
- `resume` (planning umbrella) — Consumes handoff artifacts to restore session state
- `workflow-orchestrator` — For complex multi-phase tasks that benefit from handoff between phases
