# game-design-prototyping-companion

## Purpose

Plan prototype states, branches, and decision gates. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: prototype code, mockups, experiment plan. Then inspect these capability-specific signals: starting assumption, branch conditions, test variants, observation, decision, disposal plan. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. Map initial assumption, test variants, branch conditions, state labels, observation points, and decision exits.
2. Keep experimental code/data separable from adoption candidates.
3. Plan the next branch before starting so surprising results have a route.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| starting assumption | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| branch conditions | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| test variants | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| observation | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| decision | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| disposal plan | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- prototype branch map
- state labels
- variant plan
- observation log
- adoption/disposal decision

## Failure modes

- Do not retain exploratory complexity by default.
- Do not test multiple unknowns without labeling which result answers which question.
- Do not retain exploratory code without an explicit adoption decision.

## Example application

When a team needs to plan prototype states, branches, and decision gates, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `starting assumption` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `disposal plan` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `prototype branch map` with an owner, a quality guard, and a stop rule.

## Validation

Review the branch map after every test; prune paths whose question has been answered.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
