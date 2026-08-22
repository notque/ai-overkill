# game-design-design-pillars-extractor

## Purpose

Derive trade-off rules from repeated product intent. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: GDD, pitch, backlog, build, stakeholder notes. Then inspect these capability-specific signals: player promise, non-negotiable feeling, repeated verbs, exclusions, hard constraints. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. Extract repeated player promises, verbs, emotional stakes, and exclusions from docs and the build.
2. Write three to five rules in “we choose X over Y when…” form so they settle trade-offs.
3. Test each pillar against current features and a plausible tempting feature it would reject.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| player promise | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| non-negotiable feeling | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| repeated verbs | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| exclusions | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| hard constraints | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- pillar set
- evidence per pillar
- feature alignment matrix
- contradictions
- decision rules

## Failure modes

- Do not write values that every game could claim.
- Do not make pillars a retrospective description of the feature list.
- A pillar must reject plausible work, not praise all work.

## Example application

When a team needs to derive trade-off rules from repeated product intent, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `player promise` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `hard constraints` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `three-to-five falsifiable pillars` with an owner, a quality guard, and a stop rule.

## Validation

Ask separate reviewers to use the pillars on the same trade-off; compare their decisions.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
