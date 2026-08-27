# Ambiguity triage

Decide whether questions will save more work than they delay. Complexity raises the chance that a question helps; it never makes questioning mandatory by itself.

## Classify unresolved decisions

Inspect the request, repository, supplied material, and prior decisions first. For each unresolved decision, record:

- **Impact**: Would a wrong assumption change architecture, scope, data, security, cost, or user-visible behavior?
- **Uncertainty**: Is the answer absent from available evidence?
- **Reversibility**: Is a wrong choice cheap to change?
- **Source**: Repository, public evidence, current user, another person, or empirical test.

## Choose the least-friction path

### Source precedence

Route each gap by knowledge owner before counting decisions. Repository or public facts go to inspection or research. Facts, constraints, preferences, or approval held by another person always go to `human-source-elicitation.md`. Never ask the current user to answer for another person. Only current-user decisions count toward the interview threshold.

| Condition | Action |
|---|---|
| Low impact, reversible, or supported by convention | State the assumption and execute. |
| Knowledge or authority belongs to another person | Load `human-source-elicitation.md`; create an artifact instead of blocking the live session or interviewing the current user. |
| One high-impact decision, current user is the source | Ask one question with a recommendation, then execute. |
| Two or more linked high-impact decisions, or independent high-impact decisions worth resolving together | Load `depth-first-interview.md`; batch the independent decision frontier and traverse true dependencies in later rounds. |
| Evidence, not preference, can settle the decision | Load `empirical-prototype.md`. |

Questions earn their cost only when the expected rework avoided exceeds the interruption. If the user says to proceed, use stated defaults and carry remaining decisions forward.

An interview nested inside an active delivery objective suspends execution; it does not replace it. After compiling decisions, automatically resume the build, fix, install, validation, or other requested work. Stop at the decision artifact only for an explicit interview-only request.

For router-initiated ambiguity, use a harness-native structured question UI when it can present the current independent frontier without losing free-form correction. Otherwise use one numbered Markdown batch. Bound this implicit interview at five questions and three decision rounds, plus at most one concise confirmation response; use one-at-a-time turns only for genuine dependency edges. These bounds do not apply when the user explicitly requests "grill me" or an exhaustive interview.
