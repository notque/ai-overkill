# game-dev-team-gap

## Purpose

Identify missing capability, capacity, and ownership before commitments. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: staffing, roadmap, vendors, skill inventory. Then inspect these capability-specific signals: required role, existing skill, throughput, bottleneck, hire-versus-cut, handoff risk. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. Compare required capability, available skill, capacity, ownership, throughput, and handoff risk across design, engineering, art, audio, QA, production, and operations.
2. Identify the next bottleneck rather than a wish-list of roles.
3. Choose hire, contractor, partner, tooling, training, scope cut, or sequencing based on the critical path.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| required role | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| existing skill | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| throughput | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| bottleneck | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| hire-versus-cut | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| handoff risk | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- capability matrix
- bottleneck diagnosis
- staffing options
- cost/time trade-offs
- interim plan

## Failure modes

- Do not assume headcount fixes unclear ownership.
- Do not treat partial experience as full production capacity.
- Headcount alone does not remove a coordination bottleneck.

## Example application

When a team needs to identify missing capability, capacity, and ownership before commitments, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `required role` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `handoff risk` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `team-gap plan` with an owner, a quality guard, and a stop rule.

## Validation

Recheck the gap after the next milestone because the bottleneck moves.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
