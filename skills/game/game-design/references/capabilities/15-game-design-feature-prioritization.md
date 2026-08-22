# game-design-feature-prioritization

## Purpose

Rank work by player value, evidence, cost, risk, and reversibility. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: backlog, analytics, playtests, technical estimates, roadmap. Then inspect these capability-specific signals: promise fit, affected moment, confidence, effort range, dependencies, opportunity cost. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. Compare player value, pillar fit, evidence confidence, reach, effort range, dependencies, reversibility, and cost of delay.
2. Generate alternatives and a cut before scoring.
3. Use a decision record rather than pretending a numerical score settles strategic disagreement.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| promise fit | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| affected moment | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| confidence | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| effort range | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| dependencies | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| opportunity cost | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- priority matrix
- assumptions
- ranked queue
- cut/defer list
- owner and review date

## Failure modes

- Do not rank work without naming the player moment.
- Do not hide unmeasured risk inside a single score.
- Priority scores do not erase disagreement or uncertainty.

## Example application

When a team needs to rank work by player value, evidence, cost, risk, and reversibility, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `promise fit` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `opportunity cost` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `priority decision record` with an owner, a quality guard, and a stop rule.

## Validation

Revisit after the selected experiment; confirm the premise before scaling the feature.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
