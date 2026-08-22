# game-design-player-persona-extractor

## Purpose

Turn evidence into falsifiable play-context personas. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: interviews, playtests, support, analytics with consent. Then inspect these capability-specific signals: situation, desired outcome, familiarity, available time, social setting, limits, anti-persona. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. Inventory repository evidence before interviews: target promise, entry flows, rules, rewards, support patterns, analytics definitions, and existing research.
2. Build persona hypotheses from situation, job-to-be-done, desired feeling, familiarity, time, device, social setting, constraints, trust needs, and alternatives—not demographics alone.
3. Write a paired anti-persona that makes the exclusion or trade-off visible; assign confidence per field as observed, reported, inferred, or unknown.
4. Compare feature decisions across personas and anti-personas before claiming fit.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| situation | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| desired outcome | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| familiarity | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| available time | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| social setting | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| limits | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| anti-persona | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- evidence ledger
- persona cards
- anti-persona cards
- confidence map
- behavior predictions
- feature-fit matrix
- validation interview/playtest plan

## Failure modes

- Do not create a persona from demographic stereotypes.
- Do not present inference as research.
- Do not omit the anti-persona when a scope choice excludes a play context.
- Demographics alone are insufficient persona evidence.

## Example application

When a team needs to turn evidence into falsifiable play-context personas, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `situation` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `anti-persona` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `persona hypotheses` with an owner, a quality guard, and a stop rule.

## Validation

Recruit against the uncertain fields, give a neutral task, observe behavior, then revise confidence and the feature-fit matrix.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
