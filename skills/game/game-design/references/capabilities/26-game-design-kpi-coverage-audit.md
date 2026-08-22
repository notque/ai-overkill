# game-design-kpi-coverage-audit

## Purpose

Test whether measurement answers player questions rather than only business questions. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: analytics schema, dashboards, experiments, research plan. Then inspect these capability-specific signals: event definition, cohort, denominator, lag, confounder, quality guard, decision owner. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. Start with a player question, then define event, property, cohort, denominator, time window, confounder, and decision owner.
2. Cover activation, comprehension, choice, mastery, value, progression, social health, and trust rather than only funnel activity.
3. Pair every growth metric with a player-quality guard.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| event definition | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| cohort | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| denominator | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| lag | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| confounder | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| quality guard | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| decision owner | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- KPI question map
- event schema gaps
- dashboard table
- quality guards
- experiment decision rules

## Failure modes

- Do not instrument a metric with no decision attached.
- Do not treat correlation as feature causality.
- Retention or revenue movement alone is not player benefit.

## Example application

When a team needs to test whether measurement answers player questions rather than only business questions, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `event definition` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `decision owner` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `KPI coverage and instrumentation gaps` with an owner, a quality guard, and a stop rule.

## Validation

Validate event semantics against replay or a known test session before reading trends.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
