# game-dev-budget-estimator

## Purpose

Estimate cost as ranges driven by scope and delivery assumptions. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: roadmap, staffing, vendors, technical plan. Then inspect these capability-specific signals: team shape, duration, rates, content volume, platform, QA, live operations, contingency. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. Estimate by scenario: team shape, rates, duration, content volume, platform, vendors, QA, operations, contingency, and rework.
2. Present low, expected, and high cases with the assumptions that move each.
3. Run sensitivity on the top cost drivers rather than presenting one total.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| team shape | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| duration | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| rates | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| content volume | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| platform | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| QA | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| live operations | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| contingency | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- budget range
- cost-driver table
- scenarios
- contingency rationale
- cut levers

## Failure modes

- Do not present an early estimate as a quote.
- Do not omit non-development costs and operational tail.
- One-number budgets conceal uncertainty.

## Example application

When a team needs to estimate cost as ranges driven by scope and delivery assumptions, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `team shape` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `contingency` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `budget range and sensitivity table` with an owner, a quality guard, and a stop rule.

## Validation

Re-estimate after each milestone and compare actual burn to the assumptions.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
