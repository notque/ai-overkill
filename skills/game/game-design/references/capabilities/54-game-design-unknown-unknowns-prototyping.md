# game-design-unknown-unknowns-prototyping

## Purpose

Search for assumptions the current question set misses. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: assumptions, prototype history, risks, research gaps. Then inspect these capability-specific signals: uncertainty quadrant, hidden dependency, player behavior surprise, technical surprise, market surprise. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. Sort uncertainty into known-known, known-unknown, unknown-known, and unknown-unknown; look in player behavior, integration, content scale, market meaning, and operations.
2. Use probes, exploration prototypes, pre-mortems, and divergent observation to expose surprises.
3. Keep discovery work small and explicitly separate from confirmation tests.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| uncertainty quadrant | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| hidden dependency | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| player behavior surprise | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| technical surprise | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| market surprise | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- uncertainty map
- hiding places
- exploration probes
- surprise log
- next questions

## Failure modes

- Do not claim exhaustive risk discovery.
- Do not use an unknowns workshop to delay an obvious test.
- Do not pretend every uncertainty can be scheduled away.

## Example application

When a team needs to search for assumptions the current question set misses, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `uncertainty quadrant` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `market surprise` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `unknown-unknown exploration plan` with an owner, a quality guard, and a stop rule.

## Validation

Success is a changed question set, not confirmation of the original plan.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
