# game-design-player-segment-perception-audit

## Purpose

Compare how contexts interpret the same feature. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: research, adoption data, playtests, store and community feedback. Then inspect these capability-specific signals: segment context, expectation, perceived value, barrier, alternative, exclusion risk. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. Segment by play context, entry path, experience, time, social setting, device, and goal.
2. For each segment, map expected value, perceived cost, confusion, alternative, and exclusion risk.
3. Use the same feature moment so differences are comparable.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| segment context | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| expectation | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| perceived value | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| barrier | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| alternative | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| exclusion risk | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- segment perception matrix
- common and divergent readings
- trade-off decision
- research gaps

## Failure modes

- Do not turn segments into static identities.
- Do not optimize one segment without naming the cost to another.
- Segments describe contexts, not immutable identities.

## Example application

When a team needs to compare how contexts interpret the same feature, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `segment context` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `exclusion risk` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `segment perception matrix` with an owner, a quality guard, and a stop rule.

## Validation

Compare behavior and interpretation under the same scenario across selected contexts.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
