# game-design-core-loop-extractor

## Purpose

Expose the repeated player decision and its feedback cycle. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: playable code, state transitions, UI, data tables, player journey. Then inspect these capability-specific signals: trigger, action, information, cost, reward, consequence, renewed goal. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. Map trigger, player intention, information, decision, action, immediate feedback, cost/reward, state change, and renewed intention.
2. Separate the moment-to-moment loop from progression, collection, narrative, and monetization layers.
3. Mark where the loop has no meaningful choice, no readable consequence, or no reason to repeat.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| trigger | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| action | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| information | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| cost | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| reward | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| consequence | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| renewed goal | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- loop diagram
- choice inventory
- feedback ledger
- missing-link diagnosis
- smallest loop test

## Failure modes

- Do not call a reward schedule a core loop.
- Do not hide a weak repeated action under meta progression.
- Meta systems cannot hide an absent repeated decision.

## Example application

When a team needs to expose the repeated player decision and its feedback cycle, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `trigger` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `renewed goal` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `loop map with missing links` with an owner, a quality guard, and a stop rule.

## Validation

Watch players repeat the loop without prompting and ask what decision they believe they are making.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
