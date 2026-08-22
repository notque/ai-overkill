# game-design-player-perspective-reframe

## Purpose

Restate a design issue from the player’s moment and knowledge. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: playtest recordings, UI, support, game state. Then inspect these capability-specific signals: player goal, known information, perceived cost, emotional state, alternatives, trust. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. Rewrite the issue from the player’s immediate goal, knowledge, emotional state, perceived cost, available alternatives, and trust.
2. Remove designer-only information and causal assumptions from the first pass.
3. Use the reframe to generate testable problem statements rather than empathy prose.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| player goal | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| known information | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| perceived cost | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| emotional state | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| alternatives | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| trust | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- before/after framing
- player knowledge map
- assumptions removed
- decision question
- test task

## Failure modes

- Do not put words in players’ mouths without evidence.
- Do not confuse sympathy with a usable problem definition.
- Do not presume the player shares designer knowledge.

## Example application

When a team needs to restate a design issue from the player’s moment and knowledge, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `player goal` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `trust` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `player-perspective problem statement` with an owner, a quality guard, and a stop rule.

## Validation

Give the reframed task to a player who lacks team context; compare expectations with the design intent.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
