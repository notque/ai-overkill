# Depth-First Interview Reference

## Purpose

Resolve consequential ambiguity with the fewest interruption rounds. Build a dependency tree, ask the whole independent frontier together, and walk one-at-a-time only where one answer changes the next valid question. Each question includes a recommended answer. Contrast with `pre-plan.md` (breadth-first scope clarification) and `socratic-debugging/SKILL.md` (bug-finding via questions).

## When to use vs when not

Use when:
- User signals uncertainty: "not sure", "i'm not sure", "where do i start", "want clarity on X", "interview me", "grill me", "depth-first review".
- `/do` Phase 3 found two or more linked, high-impact decisions whose answers are absent from available evidence.
- `/quick --interview` was passed.
- Two or more consequential decisions remain. Independent decisions may share a round; dependent decisions traverse in later rounds.

Use `pre-plan.md` instead when:
- Scope is unclear and you need to surface all gray areas at once for batch decisions.
- Brownfield codebase where assumptions need to be made explicit before planning.

Use `socratic-debugging` instead when:
- The task is finding a specific bug.

Proceed without an interview when question value is low: the choice is reversible, convention supplies a safe default, or asking would not change the work. State the assumption and execute. Complexity alone does not justify questions.

## Phase 0: PRIME (no question round)

1. Load CLAUDE.md (root and any subdirectory matching the topic).
2. Establish a one-sentence scope boundary (what is in vs out).
3. **Classify the trigger source**:
   - **Explicit**: user typed "interview me", "grill me", "depth-first review", or invoked `/quick --interview`.
   - **Implicit**: `ambiguity-triage.md` found linked high-impact decisions whose expected rework exceeds the interruption cost.
4. For an implicit trigger, state why the questions earn their cost and start with the highest-value independent frontier. Do not ask a meta-question about whether to ask questions; the user can stop the session at any time.
5. **Capture the continuation contract before asking**:
   - **Nested execution**: the interview suspends an active `/do` build, fix, install, validate, or other delivery objective. Compile decisions, then automatically resume that objective.
   - **Interview-only**: the user explicitly asks only for an interview, decision artifact, or plan and excludes implementation. Compile and stop at the artifact.
   - If an active delivery objective exists and the user does not explicitly cancel it, treat the interview as nested execution. Never turn an implementation request into a planning-only response merely because questions were asked.

   For implicit triggers, if the user responds with `"just build it"`, `"just go"`, `"skip questions"`, `"don't grill me"`, or any clear pass: use the recommendations as defaults, proceed to direct execution, and record `Mode Used: Interview (defaulted — user chose execution)` in Phase 3 output.

**GATE**: Trigger classified and question value established. If value is low, skip to execution.

## Phase 1: BUILD THE DECISION FRONTIER (no question round)

1. List candidate decisions discovered from the request plus a quick code exploration.
2. Dispatch factual questions to repository inspection, research, or another source owner. Do not spend the human question budget on discoverable facts. Where parallel work is available, start fact gathering alongside an independent user-decision frontier; block the round only when the fact would change a question's valid options or wording.
3. Draw dependency edges: `A -> B` only when A's answer changes B's valid options or wording.
4. Rank by load-bearing weight, then select the unresolved **independent frontier**: all questions with no unanswered prerequisite.
5. Keep the tree internal. Show only the questions the user can answer now; do not add a ceremonial branch-list turn.

**GATE**: Dependency tree built and first independent frontier selected.

## Phase 2: TRAVERSE (frontier rounds)

The trigger source controls the stopping policy:

- **Explicit grill**: construct and exhaust the material decision tree. The kinds and number of questions emerge from the decisions and dependencies needed for shared understanding. Continue until all material branches resolve, shared understanding is confirmed, or the user stops. There is no arbitrary total-question, round, or recursion cap. Question value still applies: exhaustive means complete coverage, not ceremonial volume.
- **Implicit ambiguity interview**: bounded. Ask at most 5 total questions across at most 3 decision-question rounds, plus at most one concise confirmation response. At recursion depth 3, carry deeper branches forward and continue execution with safe defaults where possible.

For each branch in priority order:

**Step 1**: Select the highest-leverage unresolved frontier. For an implicit interview, fit it to the remaining question budget. Ask independent questions together. Ask one question alone only when its answer is a prerequisite for the next branch.

**Step 2: Read code FIRST.** Use Read/Grep/Glob to answer the question if the codebase contains the answer. Only ask the human for things the codebase cannot tell you: preferences, priorities, intent, scope, taste. Asking the human for facts the code already states wastes a question budget slot and erodes trust.

**Step 3: Use the harness-native question surface when it helps.** If a structured question UI is available, use it for independent questions whose answers fit two or three mutually exclusive choices. Put the recommended choice first and include the grounded reason in its description. The UI's free-form alternative preserves correction. If the UI accepts only three questions per call, chunk a larger frontier solely at that capacity boundary. All chunks remain one logical frontier round: do not recompute the tree between chunks unless an earlier answer invalidates a pending question.

Otherwise, ask one numbered Markdown round and wait once:

> 1. [Decision]?
>    Recommended: [answer], because [reason grounded in code or stated constraint].
> 2. [Independent decision]?
>    Recommended: [answer], because [reason].
>
> Accept the recommendations, or change any numbered answer.

In Markdown, ask the full independent frontier in one message. Do not split it into separate messages. Structured UI may chunk only because of its per-call capacity; portable Markdown must preserve the full frontier, recommendations, and single-wait behavior.

The recommendation is non-negotiable — turning "design this" into "ratify-or-correct" is the whole point. A bare question without a recommendation puts the design burden back on the user.

**Step 4: Recompute the frontier.** Apply the answers, unlock dependent branches, and form the next independent frontier. Do not ask a dependent follow-up before its prerequisite is answered. An explicit grill follows material dependencies until resolved. An implicit interview stops recursion at depth 3 and marks deeper sub-branches `[carried forward]`.

**Step 5: Stop policy.** For an explicit grill, stop only on complete material coverage plus confirmation, or when the user stops. For an implicit interview, enforce the 5-question and 3-decision-round caps and mark unresolved branches `[carried forward]`. Never add low-value questions to make the interaction feel like a "grill."

**GATE**: User signals "ok go", "build it", or "that's enough"; all material branches resolve; or an implicit-interview cap is hit.

## Phase 3: COMPILE OUTPUT

Emit the SAME schema as `pre-plan.md` (no fork — downstream consumers must work on either artifact):

```markdown
## Resolved Decisions
- [Decision 1]: [answer] — [one-line rationale]
- [Decision 2]: [answer] — [one-line rationale]

## Carried Forward
- [Branch deferred]: [why deferred, when to revisit]

## Scope Boundary
[One sentence on what is in vs out]

## Mode Used
Interview (depth-first, N questions asked)
```

## Confirmation and continuation state table

Final shared understanding is a hard gate before nested execution resumes. Distinguish answering the last frontier from authorizing execution:

| State after the final frontier | Next action |
|---|---|
| `ANSWER_ONLY + NESTED_EXECUTION` | Compile the interpretation, ask one concise confirmation, and do not execute yet. |
| `EXPLICIT_PROCEED + NESTED_EXECUTION` | The user's explicit "proceed", "build it", "looks right, continue", or equivalent both confirms the interpretation and authorizes automatic execution. |
| `CONFIRMED + NESTED_EXECUTION` | Automatically resume the suspended `/do` objective. |
| `INTERVIEW_ONLY` | Deliver the compiled artifact and stop; never infer implementation authority. |

A bare answer to the last numbered question is `ANSWER_ONLY`, even when it accepts the recommendation. It does not satisfy confirmation. Do not add another confirmation when the same response explicitly says to proceed. If the compiled interpretation materially differs from any answer, show the difference in the concise confirmation.

**Continuation gate**:
- Nested execution: only after `EXPLICIT_PROCEED` or `CONFIRMED`, pass the artifact downstream or save it beside `task_plan.md`, then resume the suspended `/do` objective in the same turn. The interview is a decision phase, not a terminal result.
- Interview-only: deliver the artifact and stop.

**GATE**: Output structurally identical to `pre-plan.md` output and the continuation contract has been honored.

## Error Handling

### Error: User defers every question
**Cause**: User replies "your call" or "you decide" to every question.
**Solution**: In an implicit interview, after 2 consecutive defers switch to direct execution using the recommendations and note `Mode Used: Interview (defaulted)`. In an explicit grill, treat each defer as delegation of that decision to the recommendation, continue through every other material branch, then require the normal shared-understanding confirmation.

### Error: Implicit branch exceeds recursion budget
**Cause**: A question reveals ambiguity larger than expected.
**Solution**: For an implicit interview only, stop that branch at depth 3, emit current state, and mark the remainder `[carried forward — needs separate interview]`. Resume nested execution with safe defaults where possible. In an explicit grill, never carry a material branch forward because it is deep or large: restructure it into a dependency subtree, expand successive frontiers, and continue until material coverage and shared understanding are complete or the user stops.

### Error: User invokes interview but request is fully specified
**Cause**: Misclassification — request had concrete file/symbol/test specified but the trigger fired anyway.
**Solution**: In Phase 0 PRIME, when scope boundary is trivially clear and no gray areas surface in a quick code scan, output `## No interview needed` with a one-line justification and skip directly to Phase 3 with `Mode Used: Interview (skipped — no ambiguity)`.

### Error: Implicit-interview cap hit with branches unresolved
**Cause**: A router-initiated interview found more ambiguity than its interruption budget allows.
**Solution**: Emit Phase 3 with all unresolved branches in Carried Forward. Resume nested execution using recommendations as safe defaults where possible. Do not apply this cap to an explicit grill; continue that dependency tree until material coverage is complete or the user stops.

## References

- ADR-209 (this design)
- ADR-072 (pre-plan breadth-first contract — sibling, not superseded)
- `pre-plan.md` (sibling reference, breadth-first counterpart)
- `docs/PHILOSOPHY.md` (umbrella pattern, progressive disclosure, anti-rationalization caps)
