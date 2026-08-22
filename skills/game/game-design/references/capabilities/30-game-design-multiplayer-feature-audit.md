# game-design-multiplayer-feature-audit

## Purpose

Audit a shared feature as relationships, coordination, and failure recovery. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: network flows, lobby, matchmaking, rewards, reports. Then inspect these capability-specific signals: role interdependence, communication, power gap, sabotage path, absence, rejoin, newcomer value. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. Map roles, interdependence, communication, timing, power gaps, abandonment, rejoin, sabotage, and recovery.
2. Test coordination failure as carefully as successful cooperation.
3. Define value for a quiet player, novice, host, late joiner, and player who prefers limited social exposure.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| role interdependence | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| communication | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| power gap | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| sabotage path | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| absence | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| rejoin | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| newcomer value | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- social flow
- failure-state table
- safety/abuse risks
- feature fixes
- telemetry and moderation needs

## Failure modes

- Do not mistake synchronous presence for relationship value.
- Do not create hostage states or irreversible team punishment.
- Cooperation is not automatic when players share a space.

## Example application

When a team needs to audit a shared feature as relationships, coordination, and failure recovery, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `role interdependence` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `newcomer value` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `multiplayer feature review` with an owner, a quality guard, and a stop rule.

## Validation

Playtest with uneven skill and communication; assess contribution and repair.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
