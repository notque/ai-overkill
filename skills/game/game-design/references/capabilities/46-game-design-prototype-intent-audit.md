# game-design-prototype-intent-audit

## Purpose

Verify a prototype answers a decision-critical unknown. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: prototype, brief, test plan, backlog. Then inspect these capability-specific signals: unknown, hypothesis, scope, observation, success threshold, stop rule, next decision. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. State the decision-critical unknown, hypothesis, scope boundary, fake-able elements, observation, threshold, and stop rule.
2. Check whether the prototype can produce a false positive or false negative because an essential ingredient is missing.
3. Dispose, revise, scale, or stop explicitly after evidence.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| unknown | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| hypothesis | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| scope | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| observation | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| success threshold | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| stop rule | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| next decision | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- prototype intent card
- validity threats
- test design
- decision gate
- disposal plan

## Failure modes

- Do not call a feature slice a prototype without an uncertainty.
- Do not let production polish consume the learning budget.
- A prototype is not production work with unfinished visuals.

## Example application

When a team needs to verify a prototype answers a decision-critical unknown, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `unknown` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `next decision` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `prototype intent review` with an owner, a quality guard, and a stop rule.

## Validation

Pass only when the observed result changes the next decision.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
