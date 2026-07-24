# Spec Writing Reference

Deep reference for writing feature specifications and PRDs. Loaded by SPEC mode.

---

## PRD Section Guide

### Problem Statement

The foundation. Everything else flows from this.

**Structure**:
- What is the user problem? (2-3 sentences)
- Who experiences it and how often?
- What is the cost of not solving it? (user pain, business impact, competitive risk)
- What evidence grounds this? (research, support data, metrics, customer feedback)

**Failure modes**:

| Bad | Why | Better |
|-----|-----|--------|
| "Users need better onboarding" | No problem defined, no evidence | "42% of new users abandon setup before connecting their first integration (Mixpanel, Q1). Support tickets about 'getting started' are our #2 category." |
| "Enterprise customers want SSO" | States a solution, not a problem | "Enterprise IT teams cannot enforce their security policies without centralized auth. Three $100K+ prospects cited this as a blocker in Q4 pipeline reviews." |
| "We should improve performance" | No specificity, no who, no impact | "Page load time for the dashboard averages 4.2s on mobile (target: <2s). Users with >50 items see 8s+ loads. Mobile DAU is 30% below desktop DAU per capita." |

### Goals

**Rules**:
- 3-5 specific, measurable outcomes
- Each answers: "How will we know this succeeded?"
- Outcomes, not outputs: "reduce time to first value by 50%" not "build onboarding wizard"
- Distinguish user goals (what users get) from business goals (what the company gets)

**Examples**:

| Weak | Strong |
|------|--------|
| "Improve user experience" | "Reduce median time-to-first-success from 12 minutes to 5 minutes within 30 days of launch" |
| "Increase engagement" | "Increase D7 retention for new users from 35% to 50%" |
| "Drive revenue" | "Convert 15% of free users to paid within 60 days of activation" |

### Non-Goals

As important as goals. Prevent scope creep during implementation.

**Rules**:
- 3-5 explicit exclusions
- Adjacent capabilities out of scope for this version
- Brief rationale for each: not enough impact, too complex, separate initiative, premature

**Example**:
```
Non-Goals:
- Mobile app support (separate initiative, Q3 roadmap)
- Admin bulk operations (low request volume, <5 tickets/month)
- Real-time collaboration (requires infrastructure investment beyond this scope)
- Custom branding per workspace (enterprise-only need, will address in enterprise tier work)
```

---

## User Story Patterns

### Format

"As a [specific user type], I want [capability] so that [benefit]."

### INVEST Criteria

| Criterion | Test |
|-----------|------|
| **I**ndependent | Can be developed and delivered alone |
| **N**egotiable | Details can be discussed, not a contract |
| **V**aluable | Delivers value to the user (not just the team) |
| **E**stimable | Team can roughly estimate effort |
| **S**mall | Completable in one sprint |
| **T**estable | Clear verification path |

### Common Failure Modes

| Pattern | Problem | Fix |
|---------|---------|-----|
| Too vague | "As a user, I want the product to be faster" | What specifically? Which workflow? What target? |
| Solution-prescriptive | "As a user, I want a dropdown menu" | Describe the need: "I want to select from my saved filters" |
| No benefit | "As a user, I want to click a button" | Why? What does clicking accomplish? |
| Too large | "As a user, I want to manage my team" | Break into: invite members, set roles, remove members, view activity |
| Internal focus | "As engineering, we want to refactor the database" | This is a task, not a user story. What user outcome does the refactor enable? |
| Missing edge cases | Only happy path described | Add: error states, empty states, boundary conditions, permission failures |

### Edge Case Prompts

For every user story, explicitly address:

- **Empty state**: What does the user see before any data exists?
- **Error state**: What happens when the action fails? Network error? Validation error? Permission denied?
- **Boundary conditions**: What happens at limits? Max items? Max characters? Zero items? Concurrent access?
- **Permission variations**: What does a viewer see vs an editor vs an admin?
- **Undo/recovery**: Can the user reverse this action? What happens if they do?
- **Offline/degraded**: What happens with poor connectivity? Partial data?

---

## Acceptance Criteria Methodology

### Given/When/Then Format

```
Given [precondition or context]
When [action the user takes]
Then [expected outcome]
```

**Rules**:
- Cover happy path, error cases, and edge cases
- Be specific about expected behavior, not implementation
- Include negative test cases (what should NOT happen)
- Each criterion is independently testable
- Ban ambiguous words without definition

### Ambiguity Elimination

| Ambiguous | Specific |
|-----------|----------|
| "fast" | "< 200ms p95 response time" |
| "user-friendly" | "completes task in < 3 clicks, 0 help-text references needed" |
| "intuitive" | "80% of test users complete without guidance on first attempt" |
| "responsive" | "renders correctly at 320px-2560px viewport width" |
| "scalable" | "handles 10K concurrent users with < 500ms p99 latency" |
| "secure" | "encrypted at rest (AES-256), in transit (TLS 1.3), audit logged" |

### Checklist Format (Alternative)

```
- [ ] Admin can enter SSO provider URL in organization settings
- [ ] Team members see "Log in with SSO" on login page
- [ ] SSO login creates account if none exists (email match)
- [ ] SSO login links to existing account on email match
- [ ] Failed SSO shows error message with retry option and support link
- [ ] Admin can disable SSO (members fall back to email/password)
- [ ] SSO removal does NOT delete existing accounts
```

---

## Requirements Prioritization

### P0 / P1 / P2 Framework

| Priority | Definition | Test |
|----------|-----------|------|
| **P0 (Must-Have)** | Feature cannot ship without these. Minimum viable. | "Would we not ship without this?" If no, P0. |
| **P1 (Nice-to-Have)** | Significantly improves experience. Core use case works without them. | Fast follow-ups after launch. |
| **P2 (Future)** | Out of scope for v1. Design should support them later. | Architectural insurance — guide decisions now. |

**Discipline rules**:
- Be ruthless about P0s. Tighter must-have list = faster ship + faster learning.
- If everything is P0, nothing is P0. Challenge every must-have.
- P1s are things you are confident you will build soon, not a wish list.
- P2s prevent accidental architecture decisions that make future work hard.

### MoSCoW Cross-Reference

| MoSCoW | Maps to | Usage |
|--------|---------|-------|
| Must have | P0 | Non-negotiable commitments |
| Should have | P1 | Important, expected, but delivery is viable without |
| Could have | Below P1 | Include only if capacity allows |
| Won't have | Explicit exclusion | Out of scope this version |

---

## Scope Management

### Recognizing Scope Creep

- Requirements added after spec approval
- "Small" additions accumulating into a larger project
- Building features no user asked for ("while we are at it...")
- Launch date moving without explicit re-scoping
- Stakeholders adding requirements without removing anything

### Prevention Tactics

| Tactic | Implementation |
|--------|---------------|
| Explicit non-goals | Every spec has them |
| Scope addition = scope removal | Any add comes with a remove or timeline extension |
| v1 / v2 separation | Clear boundary in spec |
| Problem statement check | Review spec against original problem. Does everything serve it? |
| Investigation time-box | "If we cannot figure out X in 2 days, we cut it" |
| Parking lot | Capture good ideas that are out of scope |

---

## Success Metrics Definition

### Leading Indicators (Change in Days-Weeks)

| Metric | What It Measures |
|--------|-----------------|
| Adoption rate | % of eligible users who try the feature |
| Activation rate | % who complete the core action |
| Task completion rate | % who accomplish their goal |
| Time to complete | Duration of core workflow |
| Error rate | How often users hit errors or dead ends |
| Feature usage frequency | How often users return to the feature |

### Lagging Indicators (Change in Weeks-Months)

| Metric | What It Measures |
|--------|-----------------|
| Retention impact | Does this feature improve retention? |
| Revenue impact | Does this drive upgrades, expansion, or new revenue? |
| NPS / satisfaction | Does this improve user sentiment? |
| Support ticket reduction | Does this reduce support load? |
| Competitive win rate | Does this help win more deals? |

### Target-Setting Rules

- Specific: "50% adoption within 30 days" not "high adoption"
- Based on comparables: similar features, industry benchmarks, explicit hypotheses
- Two thresholds: "success" and "stretch"
- Measurement method defined: what tool, what query, what time window
- Evaluation cadence defined: 1 week, 1 month, 1 quarter post-launch

---

## Output Structure

```markdown
# [Feature Name] — Product Requirements Document

## Problem Statement
[2-3 sentences. Who, evidence, cost of not solving.]

## Goals
1. [Measurable outcome tied to user/business metric]
2. ...

## Non-Goals
1. [Exclusion] — [rationale]
2. ...

## User Stories
### [Persona 1]
- As a [type], I want [capability] so that [benefit]
  - AC: Given... When... Then...
  - AC: Given... When... Then...
### [Persona 2]
- ...

## Requirements
### P0 — Must-Have
| Requirement | Acceptance Criteria | Dependencies |
|------------|-------------------|--------------|
| ... | ... | ... |

### P1 — Nice-to-Have
| Requirement | Acceptance Criteria | Dependencies |
|------------|-------------------|--------------|
| ... | ... | ... |

### P2 — Future Considerations
| Requirement | Notes |
|------------|-------|
| ... | ... |

## Success Metrics
### Leading Indicators
| Metric | Target | Measurement | Evaluation |
|--------|--------|-------------|------------|
| ... | ... | ... | ... |

### Lagging Indicators
| Metric | Target | Measurement | Evaluation |
|--------|--------|-------------|------------|
| ... | ... | ... | ... |

## Open Questions
| Question | Owner | Blocking? |
|----------|-------|-----------|
| ... | ... | ... |

## Timeline
| Milestone | Date | Dependencies |
|-----------|------|-------------|
| ... | ... | ... |
```
