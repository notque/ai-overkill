# game-dev-time-estimator

## Purpose

Estimate schedule ranges with dependencies and rework. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: backlog, capacity, history, build pipeline. Then inspect these capability-specific signals: scope, throughput, dependencies, integration, QA, approvals, content, contingency. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. Estimate low, expected, and high schedules from scope, milestone quality bar, team availability, dependencies, content throughput, integration, QA, approvals, and rework.
2. Use distinct modes for known team, unknown team, target date, and milestone type.
3. Expose critical path and what can genuinely run in parallel.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| scope | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| throughput | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| dependencies | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| integration | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| QA | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| approvals | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| content | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| contingency | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- schedule range
- driver list
- parallelization map
- hidden time sinks
- shortening levers
- next actions

## Failure modes

- Do not turn part-time effort into full-time calendar assumptions.
- Do not linearly scale a vertical-slice schedule to release.
- Calendar arithmetic is not an estimate.

## Example application

When a team needs to estimate schedule ranges with dependencies and rework, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `scope` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `contingency` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `schedule range and critical path` with an owner, a quality guard, and a stop rule.

## Validation

Review estimate accuracy at each milestone and update the drivers, not just the date.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
