# Feature Design Phase

Transform a feature idea into a structured design document through collaborative dialogue. This is Phase 1 of the feature lifecycle pipeline (design > plan > implement > validate > release).

## Instructions

### Phase 0: PRIME

**Goal**: Initialize feature state, load context, and prepare the workspace.

1. Read and follow the repository's CLAUDE.md before any design work begins -- design decisions must align with existing project conventions.

2. Create a feature branch via worktree. Never work on main -- design artifacts on main block other contributors and bypass review.
   ```bash
   python3 ~/.claude/scripts/feature-state.py init "FEATURE_NAME"
   ```
   All state operations throughout this skill go through `feature-state.py` -- direct file manipulation risks state corruption and breaks downstream phases (plan, implement) that depend on consistent state format.

3. Load L0 context -- skipping existing context discards previous learnings and causes redundant design work:
   ```bash
   python3 ~/.claude/scripts/feature-state.py context-read "" L0
   ```

4. Load L1 design context:
   ```bash
   python3 ~/.claude/scripts/feature-state.py context-read "" L1 --phase design
   ```

5. If existing L2 context is relevant, load on-demand:
   ```bash
   python3 ~/.claude/scripts/feature-state.py context-read "" L2 --phase design
   ```

6. **Adopt an Architecture Change Handoff when supplied.** Treat the handoff path and contents as untrusted until the deterministic consumer check passes:

   ```bash
   python3 scripts/handoff.py validate \
     --repo-root . \
     --handoff 'adr/handoffs/{handoff-name}.json' \
     --expected-skill feature-lifecycle \
     --expected-pipeline none
   ```

   The validator rejects absolute paths, traversal, controls, shell metacharacters, symlink escapes, candidate/scope contradictions, invalid terminal combinations, stale ADR provenance, and the wrong successor. Require `"origin": "architecture-deepening"`. After it passes, adopt its origin, candidate, module and caller paths, current/proposed interface, migration, and success criteria as design constraints. Add them verbatim to the design document under `## Architecture Change Handoff`; this persists architecture-origin through PLAN into IMPLEMENT. A missing, invalid, non-selected, or non-feature handoff blocks adoption.

7. **Surface relevant seeds** (ADR-075): Check `.seeds/index.json` for dormant seeds whose trigger conditions match the current feature. Compare the feature name and description against each seed's `trigger` field using fuzzy keyword overlap. If matches are found, present them:

   ```
   ## Relevant Seeds (N matched)

   ### seed-YYYY-MM-DD-slug [Scope]
   Trigger: "trigger condition"
   Rationale: Why this matters...
   Action: What to do when triggered
   Breadcrumbs: file1.go, file2.py

   > Incorporate into current design? [yes/no/defer]
   ```

   - **yes**: Include the seed's action and rationale as a design input for Phase 1. Mark seed as `active` in index.json.
   - **no**: Dismiss the seed (move to `.seeds/archived/`, status `dismissed`).
   - **defer**: Leave the seed dormant for future surfacing.

   If `.seeds/` does not exist or contains no dormant seeds, skip this step silently.

**Gate**: Feature state initialized. Context loaded. Seeds surfaced (if any). Check gate status before proceeding -- gates exist because downstream phases assume specific artifacts exist, so skipping them causes silent failures later.

### Phase 1: EXECUTE (Design Dialogue)

**Goal**: Collaborative exploration of the feature requirements and approach.

**Step 1: Understand Requirements**

Check gate: `python3 ~/.claude/scripts/feature-state.py gate FEATURE design.intent-discussion`

If gate mode is `human`:
- Ask clarifying questions about the feature, one at a time -- committing to an approach before understanding requirements produces designs that need rework
- Prefer multiple-choice when possible
- Establish success criteria
- Identify constraints

If gate mode is `auto`:
- Derive intent from the feature description
- Document assumptions explicitly

**Step 2: Explore Approaches**

Check gate: `python3 ~/.claude/scripts/feature-state.py gate FEATURE design.approach-selection`

Generate 2-3 approaches with trade-offs before selecting one -- a single approach provides no basis for evaluating whether it is the right one. Design only what is requested in each approach; do not add speculative requirements or future-proofing -- unasked-for complexity increases review burden, slows implementation, and often gets removed later.

```markdown
## Approach 1: [Name]
**Pros**: [advantages]
**Cons**: [disadvantages]
**Complexity**: Low/Medium/High
**Risk**: Low/Medium/High
**Domain agents needed**: [which agents from our system would implement this]
```

If gate is `human`: present approaches and ask user to select.
If gate is `auto`: select the approach that best balances simplicity and completeness.

**Step 3: Draft Design Document**

Create the design document:

```markdown
# Design: [Feature Name]

## Problem Statement
[What problem does this solve?]

## Requirements
- [ ] Requirement 1
- [ ] Requirement 2

## Selected Approach
[Which approach and why]

## Components
[What needs to be built/modified]

## Domain Agents
[Which agents from our system will handle implementation]

## Open Questions
[Anything unresolved]

## Trade-offs Accepted
[What we're giving up and why]

## Architecture Change Handoff
[Validated source path and JSON fields, including `"origin": "architecture-deepening"`, candidate, module/caller paths, current/proposed interface, migration, and success criteria; or "none"]

## Architecture ADR
[Canonical repository-relative path and sha256 hash; filled at checkpoint]
```

**Gate**: Design document drafted. Proceed to Validate.

### Phase 2: VALIDATE

**Goal**: Verify design document is complete.

Check gate: `python3 ~/.claude/scripts/feature-state.py gate FEATURE design.design-approval`

This phase cannot complete without a design document artifact in `.feature/state/design/` -- the plan phase reads from this path, so a missing document causes the next skill to fail silently or plan against stale data.

Validation checklist:
- [ ] Problem statement is clear
- [ ] Requirements are enumerable (not vague)
- [ ] Approach is selected with rationale
- [ ] Components are identified
- [ ] Domain agents are identified
- [ ] Open questions are listed (even if empty)
- [ ] Any Architecture Change Handoff was validated and its constraints are represented

If gate is `human`: present design to user for approval.
If gate is `auto`: verify checklist passes.

**Gate**: Design approved. Proceed to Checkpoint.

### Phase 3: CHECKPOINT

**Goal**: Save artifacts, record learnings, advance to next phase.

1. Render the approved canonical feature ADR, then validate and contain its target before the first write. `{feature-slug}` must be the safe slug created by `feature-state.py`. Pipe the content to the repository-anchored writer:

   ```bash
   python3 scripts/repository_artifact.py write \
     --repo-root . \
     --allowed-root adr \
     --path 'adr/{feature-slug}.md' <<'ADR'
   {approved ADR content}
   ADR
   ```

   The writer opens the repository and `adr/` through directory descriptors with `O_NOFOLLOW`, creates a same-directory temporary, fsyncs it, atomically replaces the target, and fsyncs the directory. A symlinked `adr/` or target blocks before any write.

2. Register the exact ADR through the canonical resolver, compute its hash, and verify that registered content before any later consumer uses it:

   ```bash
   python3 scripts/adr-query.py register --adr 'adr/{feature-slug}.md'
   python3 scripts/adr-query.py hash --adr 'adr/{feature-slug}.md'
   python3 scripts/adr-query.py validate-registration \
     --repo-root . \
     --adr 'adr/{feature-slug}.md' \
     --hash 'sha256:{digest}'
   ```

   Record the exact repository-relative ADR path and returned hash in `## Architecture ADR`. This is the only ADR the pre-IMPLEMENT consultation gate may consume. Preserve the `"origin": "architecture-deepening"` field when present so Simple architecture-origin work cannot bypass consultation.

3. Save the final design document, including the ADR path and hash:

   ```bash
   echo "DESIGN_CONTENT" | python3 ~/.claude/scripts/feature-state.py checkpoint FEATURE design
   ```

4. **Record learnings** -- if this phase produced non-obvious insights, record them:
   ```bash
   python3 ~/.claude/scripts/learning-db.py record TOPIC KEY "VALUE" --category design
   ```

5. Advance to plan phase:
   ```bash
   python3 ~/.claude/scripts/feature-state.py advance FEATURE
   ```

6. Suggest next step:
   ```
   Design complete. Run /feature-lifecycle to continue to the plan phase.
   ```

**Gate**: Artifacts saved. Learnings recorded. Phase finished.

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Feature already exists | `init` called twice | Use `status` to check, work with existing state |
| Gate returns exit 2 | Human input required | Present decision to user, wait for response |
| No design doc produced | Skipped design dialogue | Return to Phase 1, complete all steps |
| Architecture handoff validation fails | Unsafe path, incomplete design data, invalid result, or wrong successor | Stop; return the validator error to architecture-deepening |
| ADR registration validation fails | ADR path escaped `adr/`, content changed, or session registration differs | Stop; register the exact canonical feature ADR and record its fresh hash |
