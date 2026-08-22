# game-design-ideal-outcome-backcasting

## Purpose

Work backward from a concrete ideal player story. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: vision, current build, team capacity, release constraints. Then inspect these capability-specific signals: future player outcome, observed evidence, prerequisite capability, milestone, next test. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. Write a concrete future player story with observable behavior, feeling, and proof of value.
2. Walk backward through prerequisite experiences, systems, content, capabilities, and decisions.
3. Stop when the next low-cost proof is reachable.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| future player outcome | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| observed evidence | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| prerequisite capability | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| milestone | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| next test | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- ideal outcome narrative
- reverse milestone chain
- assumptions
- next proof

## Failure modes

- Do not write a future fantasy that cannot be observed.
- Do not mistake a release plan for a causally ordered path.
- Future narratives must expose assumptions rather than hide them.

## Example application

When a team needs to work backward from a concrete ideal player story, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `future player outcome` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `next test` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `backcast milestone chain` with an owner, a quality guard, and a stop rule.

## Validation

Test the earliest prerequisite before funding downstream milestones.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
