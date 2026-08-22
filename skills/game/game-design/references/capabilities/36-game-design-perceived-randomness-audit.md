# game-design-perceived-randomness-audit

## Purpose

Make variance legible, influenceable, and recoverable. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: RNG code, UI, combat logs, economy, player reports. Then inspect these capability-specific signals: distribution, range, signal, seed or history, counterplay, stakes, recovery. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. Document distribution, range, streak behavior, visibility, pre-commit information, counterplay, stakes, and recovery.
2. Audit the difference between statistical balance and player-perceived agency.
3. Use signals, bounds, history, previews, or mitigation when variance governs consequential choices.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| distribution | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| range | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| signal | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| seed or history | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| counterplay | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| stakes | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| recovery | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- randomness contract
- perception risks
- UI/rule interventions
- simulation and playtest plan

## Failure modes

- Do not answer a perception complaint with average-rate statistics only.
- Do not conceal high-stakes variance that players cannot counter.
- Statistical fairness alone cannot prove perceived fairness.

## Example application

When a team needs to make variance legible, influenceable, and recoverable, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `distribution` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `recovery` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `randomness perception audit` with an owner, a quality guard, and a stop rule.

## Validation

Combine simulation with player prediction tasks and post-outcome explanations.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
