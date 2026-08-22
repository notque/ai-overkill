# game-design-attribution-audit

## Purpose

Audit what players believe caused success and failure. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: combat logs, UI copy, replay, loss screens, support comments. Then inspect these capability-specific signals: cue timing, visible cause, controllable action, feedback wording, rival or system blame. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. Classify the player’s likely explanation on locus (self/system), stability (one-off/recurring), and controllability (changeable/fixed).
2. Reconstruct the event from the player view: intended action, expected result, hidden rule, actual result, and causal feedback.
3. Prefer a learnable reading: responsibility without helplessness, explanation without blame.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| cue timing | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| visible cause | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| controllable action | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| feedback wording | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| rival or system blame | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- attribution profile table
- player sentence
- fairness diagnosis
- risk level
- cause-specific changes

## Failure modes

- Do not call a statistically correct outcome understandable.
- Do not force internal blame when information or control was absent.
- Do not label a player irrational for a system that hides causality.

## Example application

When a team needs to audit what players believe caused success and failure, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `cue timing` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `rival or system blame` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `attribution trace and repair options` with an owner, a quality guard, and a stop rule.

## Validation

Replay the event with naive players; ask them what caused the result and what they would change.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
