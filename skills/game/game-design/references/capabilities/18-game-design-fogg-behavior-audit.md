# game-design-fogg-behavior-audit

## Purpose

Test whether ability, opportunity, and prompt meet at a voluntary action. This packet is a repository-aware operating procedure, not a label to apply to a design.

## Evidence intake

Inspect repository evidence before requesting context: UX flow, permissions, notifications, tutorial, telemetry. Then inspect these capability-specific signals: capability barrier, access barrier, prompt clarity, timing, consent, consequence. Ask only for external evidence, confidential player research, decision authority, or constraints unavailable in the repository.

Mark every claim as `observed`, `documented`, `measured`, or `inferred`. Give each inference a confidence level and a disproof route.

## Method

1. For a desired voluntary action, verify ability, opportunity, and a prompt arrive together.
2. Classify barriers as skill, time, access, confidence, cost, social, or interface.
3. Improve capability or opportunity before increasing prompt frequency.

## Capability matrix

| Lens | Repository question | Player or delivery consequence |
|---|---|---|
| capability barrier | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| access barrier | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| prompt clarity | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| timing | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| consent | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |
| consequence | What evidence shows how this changes the reviewed moment? | Record the effect, confidence, and repair test. |

## Diagnostic questions

- What exact player moment or delivery decision is under review?
- Which capability lens above has the strongest evidence and which is only an inference?
- Which competing explanation would produce the same visible symptom?
- What is the smallest change or test that would separate them?

## Output schema

Return all of the following, not a generic summary:

- behavior path
- barrier table
- prompt audit
- voluntary alternative
- experiment

## Failure modes

- Do not use the model to justify coercive notifications or hidden defaults.
- Do not interpret non-completion as lack of motivation without barrier evidence.
- Do not use prompts to manufacture harmful or unwanted repetition.

## Example application

When a team needs to test whether ability, opportunity, and prompt meet at a voluntary action, begin with the available build path and the capability matrix above. Apply the named method to the affected moment, not an abstract feature description. If direct player evidence is absent, publish an evidence gap rather than a false conclusion; label the result as inferred and use the validation below to move it toward measured evidence.

## Decision procedure

1. Use `capability barrier` as the first discriminating lens, because it is closest to the stated capability.
2. Compare it against `consequence` before selecting a fix; this prevents a single-dimension conclusion.
3. Convert the result into `behavior-path audit` with an owner, a quality guard, and a stop rule.

## Validation

Measure informed completion and regret/opt-out, not completion alone.

## Full-diagnostic disposition

In a complete repository diagnostic, run this packet and record `assessed`, `evidence gap`, or `not applicable` with a game-specific reason. A missing artifact is a finding; it never permits silent omission.
