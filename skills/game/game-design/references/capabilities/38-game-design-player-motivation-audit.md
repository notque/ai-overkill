# game-design-player-motivation-audit

## Purpose

Audit why a player begins, continues, chooses, and returns. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: research, sessions, gameplay, progression, player language. Then inspect these capability-specific signals: entry context, immediate need, repeat value, identity, social context, exit reason. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. Map entry trigger, immediate need, repeated value, identity, social context, friction tolerance, and exit reason.
2. Distinguish extrinsic reward from the experience the player seeks.
3. Compare stated preferences with observed choices and alternatives.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| entry context | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| immediate need | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| repeat value | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| identity | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| social context | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| exit reason | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- motivation journey
- need-to-feature map
- mismatch risks
- test plan

## Failure modes

- Do not declare a player motivated because they completed a funnel.
- Do not reduce motivation to a reward type.
- Do not confuse a mechanic with the need it might satisfy.

## Example application

When a team needs to audit why a player begins, continues, chooses, and returns, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `entry context` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `exit reason` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `motivation audit` with an owner, a quality guard, and a stop rule.

## Validation

Observe what players voluntarily repeat or decline after rewards are removed.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
