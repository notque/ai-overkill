# game-design-granular-player-motivation-audit

## Purpose

Separate the distinct experiences a feature may satisfy. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: interviews, observed choices, alternatives, churn or support evidence. Then inspect these capability-specific signals: mastery, autonomy, belonging, expression, discovery, care, status, relief, narrative meaning. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. Disaggregate motives such as mastery, autonomy, discovery, expression, care, belonging, status, relief, and narrative meaning.
2. Map a feature’s actions, feedback, and trade-offs to each motive; look for conflicts and false proxies.
3. Use observed choices to update the map.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| mastery | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| autonomy | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| belonging | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| expression | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| discovery | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| care | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| status | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| relief | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| narrative meaning | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- motivation coverage matrix
- underserved motives
- anti-motives
- design experiments

## Failure modes

- Do not use a taxonomy as a persona generator.
- Do not assume a reward serves the motive suggested by its label.
- A long taxonomy does not validate an untested assumption.

## Example application

When a team needs to separate the distinct experiences a feature may satisfy, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `mastery` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `narrative meaning` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `motivation coverage matrix` with an owner, a quality guard, and a stop rule.

## Validation

Compare voluntary choice and qualitative reason across motive-relevant alternatives.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
