# game-design-one-thing-to-remove

## Purpose

Find the highest-leverage subtraction. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: feature inventory, player paths, code ownership, metrics. Then inspect these capability-specific signals: player value, pillar fit, maintenance cost, confusion, dependency, opportunity cost. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. Inventory features by player decision changed, pillar fit, confusion, maintenance, dependency, and opportunity cost.
2. Test subtraction candidates against onboarding, readability, content burden, and support burden.
3. Name what becomes clearer or more feasible after removal.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| player value | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| pillar fit | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| maintenance cost | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| confusion | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| dependency | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| opportunity cost | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- removal candidate ranking
- before/after player path
- dependency plan
- cut test

## Failure modes

- Do not remove a feature merely because it is visible or difficult.
- Do not call a removal safe without checking hidden dependencies.
- Cutting a visible feature is not automatically simplification.

## Example application

When a team needs to find the highest-leverage subtraction, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `player value` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `opportunity cost` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `removal recommendation` with an owner, a quality guard, and a stop rule.

## Validation

Prototype the absence and observe whether comprehension or core-loop use improves.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
