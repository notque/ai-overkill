# Autonomous game improvement

Use this protocol whenever the user asks to improve a game, retention, churn, engagement, return rate, player experience, or a product with game-like loops. Its job is to find and act on meaningful player improvements without waiting for a narrowly specified feature.

## Operating contract

1. Begin with the target repository's governing instructions and applicable local game, product, UI, implementation, analytics, research, and testing skills.
2. Treat the playable product and its evidence as the source of truth. A feature request, KPI target, or framework can generate hypotheses; it cannot override observed player harm.
3. Run greedily. For an isolated player moment, load every neighboring domain that could alter the diagnosis. For retention, churn, or whole-product improvement, run all 61 capability packets and record a disposition for each.
4. Move from evidence to action. Implement a small reversible improvement when it is within repository authority, technically safe, and the player benefit is clear enough to test. Otherwise create an implementation-ready task with the exact decision that needs authority.
5. Optimize for voluntary return, understanding, agency, competence, belonging, fairness, and trust. Never use hidden costs, forced notifications, punitive absence, shame, manipulative scarcity, confusing probability, or social pressure as an improvement.

## Improvement cycle

### 1. Build the evidence map

Inventory the game promise, target players, current build and entry points, rules, state, UI copy, reward schedules, progression, social systems, failures, return surfaces, telemetry definitions, tests, player research, support, reviews, analytics, backlog, and recent changes. Mark every conclusion as observed, documented, measured, or inferred.

For retention or engagement, trace at least these paths:

- arrival → first intention → first meaningful action → feedback → next choice;
- recurring session → goal selection → effort → reward or failure → closing moment → voluntary reason to return;
- lapsed player → re-entry cue → comprehension → catch-up → value or exit;
- where relevant, invitation → cooperation or competition → recognition → conflict/abuse recovery.

### 2. Run the design sweep

Load the capability matrix and all implicated cards. A systemic request must sweep the whole matrix, including motivation, needs, persona, friction, goal density, flow, failure/fairness, randomness, progression, social comparison, premium systems, emotion, instrumentation, prototyping, production scope, and red-team critique.

For each candidate issue, write a compact finding with: evidence, player moment and segment, lost need or expectation, competing causes, severity, confidence, affected system/files, smallest viable change, accessibility/trust risk, owner, and test.

Use motivation frameworks as hypotheses rather than diagnoses. In particular, distinguish:

| Signal | Product question | Safe design direction |
|---|---|---|
| Autonomy loss | Does the player meaningfully choose a goal, route, pace, or stop point? | Add understandable choices and graceful exits; remove forced steps. |
| Competence loss | Can the player predict, practice, recover, and see improvement? | Improve feedback, goal clarity, retry learning, and fair catch-up. |
| Relatedness loss | Does social play create belonging rather than exposure or comparison harm? | Support cooperative contribution, recognition, boundaries, and recovery. |
| Extrinsic overshadowing | Are rewards replacing the value of the activity itself? | Strengthen the core activity and vary meaningful challenges before adding rewards. |
| Amotivation/friction | Does effort lack context, agency, or visible progress? | Remove dead steps, explain value at the decision point, or create a smaller meaningful goal. |

### 3. Publish the complete improvement queue

Prioritize findings by player harm or value, confidence, reach, reversibility, cost, learning value, dependency risk, accessibility, and trust. Do not collapse these into a single score without preserving the trade-offs.

Classify each recommendation:

| Class | Action |
|---|---|
| Safe and reversible | Implement on a scoped branch, add or update tests, and document the player hypothesis. Examples: clearer goal/reward copy, a recoverable retry state, a misleading cue correction, an accessible setting default, a removed dead-end, or instrumentation that measures player understanding. |
| Needs a product choice | Give two to five materially different options with player, delivery, and validation consequences; identify the owner and decision deadline. |
| Irreversible, paid, social-risk, or live-operations change | Do not enact automatically. Supply an implementation-ready proposal, abuse/trust review, rollback plan, and explicit authority needed. |
| Evidence gap | Create the smallest observation, playtest, prototype, or instrumentation task that can distinguish the leading explanations. |

For every implementation, trace the repository's local code and test conventions; use the relevant implementation skill rather than inventing a parallel architecture. Keep the change scoped to the discovered player problem. Re-run the applicable tests and preserve a clear rollback path.

The output is a detailed, exhaustive queue, not a short set of representative ideas. Give every actionable finding an ID and include: player moment and affected segment, evidence and confidence, severity, root-cause and competing hypotheses, exact files/systems likely affected, player-visible change, implementation steps, dependencies, owner skill or role, tests, benefit measure, harm guard, rollback, and disposition. Group the queue into:

- **Fix now** — safe, reversible, evidence-supported changes that can be implemented in the repository.
- **Fix next** — actions with known dependencies or a bounded prototype/instrumentation prerequisite.
- **Decision required** — materially different product, economy, social, paid, legal, or live-operations choices, each with options and a recommended decision.
- **Research required** — unresolved causes with the shortest discriminating observation, playtest, or data task.

### 4. Execute the fix queue with the wider skill system

Do not stop after reporting. Work through every `Fix now` item in priority order, then advance newly unblocked `Fix next` items. For each item, discover the target repository's local skills, agents, and governing instructions, then route to all capabilities that materially improve the outcome. Typical collaborators are the repository's game or engine implementation guidance for rules and state, UI/design guidance for player-facing flows, analytics/data guidance for instrumentation, research guidance for evidence gaps, and testing/quality guidance for verification. In this toolkit, inspect the installed skill index rather than assuming a fixed set; the target game repository's own skills take precedence where they are more specific.

For each queued item:

1. Create a scoped implementation task from the finding and load the selected companion guidance.
2. Make the change, add or update the narrowest meaningful test or reproducible check, and run the repository's relevant quality gate.
3. Re-inspect the player path affected by the change; confirm that it improves the stated moment without moving harm elsewhere.
4. Record the change, evidence, files, test result, benefit measure, harm guard, rollback, and next review date in the queue.
5. Continue to the next actionable item. Do not quietly replace unfixed items with a generic future backlog.

If an item needs authority, live access, a paid-system decision, a broad migration, or an irreversible social effect, prepare it to the same implementation depth and continue with all other safe items. It is a visible blocked item, not permission to end the improvement cycle.

### 5. Measure player benefit, not only movement

Before releasing a change, define:

- the affected player segment, moment, and expected behavioral change;
- a player-benefit signal (understanding, successful self-chosen completion, fair recovery, satisfaction, or observed value);
- a harm guard (confusion, abandonment after prompt, spend pressure, accessibility regression, social abuse, negative sentiment, or support burden);
- the comparison, sample/window, owner, decision date, and stop or rollback rule.

Interpret retention carefully: a longer session, more clicks, more spending, or fewer exits is not evidence of value by itself. Pair the business signal with a player-outcome measure and qualitative evidence.

To drive one of these signals to a stated target instead of stopping when the
queue empties, call the optimization skill. Call the Skill tool with `hill-climb`.
It adds a measured baseline, accept/revert per change, and a plateau stop
(`skills/meta/hill-climb/references/domain-playbooks.md`).

### 6. Report and continue

Return the evidence ledger, 61-card coverage ledger when applicable, prioritized improvement backlog, exact changes made, tests run, measurement plan, unresolved decisions, and a next-cycle trigger. A valid improvement report says both what changed and what evidence would make the team reverse or extend it.

## Retention safety checks

Before proposing a retention change, explicitly test for these traps:

- Adding a reward loop when the core action lacks clarity, agency, or felt progress.
- Treating notifications, streak loss, timer pressure, or currency scarcity as a replacement for a player-chosen reason to return.
- Adding leaderboards where comparison will disproportionately demoralize, expose, or exclude players.
- Increasing task volume or grind rather than improving choice, learning, or payoff.
- Reading aggregate retention as proof when new, returning, accessibility-constrained, and dissatisfied segments have different experiences.

If a trap is present, the repair belongs earlier in the player path. State that plainly and prioritize the underlying experience over a superficial engagement lever.

## Completion gate

Do not conclude with a generic backlog. The cycle is complete only when it has inspected the actual repository, routed all material design and implementation guidance, made or specified the next smallest evidence-supported improvement, verified its technical path, and established both benefit and harm measures for the next decision.
