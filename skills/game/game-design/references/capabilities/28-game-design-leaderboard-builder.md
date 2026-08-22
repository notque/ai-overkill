# game-design-leaderboard-builder

## Purpose

Specify a leaderboard from social purpose through operations. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: game rules, data, anti-cheat, live operations, UI. Then inspect these capability-specific signals: comparison purpose, eligibility, scoring, reset, ties, display, reward cap, fallback. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. Define why comparison exists before defining the display.
2. Specify eligibility, scoring, data integrity, tie rules, periods, resets, rewards, migration, anti-cheat, moderation, and non-ranked fallback.
3. Prototype the experience for a first-time, mid-skill, top-rank, and returning player.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| comparison purpose | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| eligibility | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| scoring | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| reset | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| ties | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| display | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| reward cap | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| fallback | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- leaderboard specification
- score contract
- cohort plan
- operations playbook
- UI states

## Failure modes

- Do not ship a score without dispute and correction policy.
- Do not make rank the only route to recognition.
- Do not build ranking before defining why players compare.

## Example application

When a team needs to specify a leaderboard from social purpose through operations, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `comparison purpose` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `fallback` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `leaderboard specification` with an owner, a quality guard, and a stop rule.

## Validation

Run simulation data through ranking, reset, tie, and fraud scenarios before implementation.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
