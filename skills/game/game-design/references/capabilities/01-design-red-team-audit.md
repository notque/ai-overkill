# design-red-team-audit

## Purpose

Red-team a design before commitment. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: design brief, build behavior, economy tables, player paths, test failures. Then inspect these capability-specific signals: promise mismatch, dominant strategies, opaque rules, exploit surfaces, production fragility, accessibility exclusions, trust costs. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. Run a pre-mortem: assume the proposal failed and state the specific mechanism that killed it.
2. Test goal, player value, comprehension, system fit, content scale, production, prototype validity, MVP distortion, metric gaming, rollout, and strategy.
3. Separate concept failure, execution failure, and launch failure; each needs a different mitigation.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| promise mismatch | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| dominant strategies | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| opaque rules | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| exploit surfaces | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| production fragility | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| accessibility exclusions | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| trust costs | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- verdict class
- top 3–7 failure mechanisms with early signals and mitigation
- weak assumptions
- success conditions
- fastest de-risking moves

## Failure modes

- A risk is invalid if it cannot name a player or delivery mechanism.
- Do not turn a red team into a balanced pros/cons list.
- No challenge passes without a disproof attempt.

## Example application

When a team needs to red-team a design before commitment, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `promise mismatch` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `trust costs` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `severity-ranked challenge register` with an owner, a quality guard, and a stop rule.

## Validation

Run the smallest test against the highest-severity unproven assumption.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
