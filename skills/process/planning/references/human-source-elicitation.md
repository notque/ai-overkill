# Human-source elicitation

Use this when required knowledge or authority exists in another person's head. Produce a sendable artifact behind `/do`; do not add a new user command.

## Phase 1: Find the real gaps

1. **Inspect known evidence first.** Read the repository, supplied documents, decisions, tickets, and prior messages. Never ask a person for facts already available.
2. Name the recipient and why they are the right source.
3. List the facts, choices, constraints, or approvals needed to continue.
4. Remove questions whose answers would not change the plan.

## Phase 2: Draft the artifact

Write the shortest useful message with:

- Context and the decision or work this unlocks.
- Prioritized questions, one idea per question.
- A recommendation or answer scaffold when it reduces effort without leading the recipient.
- Permission to answer partially, mark an answer `unknown`, or name a better source.
- Requested deadline and expected effort when timing matters.

Add an internal **Coverage map** that maps each question to the plan gap it resolves. Do not include the map in the outbound message unless it helps the recipient.

## Phase 3: Gate and resume

Do not send, post, or contact anyone without user authorization. Return the draft for approval. When answers arrive, preserve the source, distinguish facts from preferences, update the plan, and surface conflicts instead of silently choosing.

If the recipient cannot answer, route each open gap again by source: repository, research, current-user decision, another human, or empirical test.
