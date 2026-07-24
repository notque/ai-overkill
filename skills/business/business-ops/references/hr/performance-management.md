# Performance Management Reference

Review structures, calibration methodology, feedback patterns, and development planning.

---

## Review Types and Templates

### Self-Assessment

Purpose: Employee documents their own accomplishments, growth, and goals. Forces reflection. Provides manager with evidence they may not have observed directly.

#### Structure

| Section | Content | Quality Gate |
|---------|---------|-------------|
| Key accomplishments | Top 3-5 achievements with situation, contribution, impact | Each has measurable impact, not just activity |
| Goals review | Status per goal from last period with evidence | Evidence is specific (metrics, artifacts, dates), not claims |
| Growth areas | New skills, expanded scope, leadership moments | Concrete examples, not self-assessment platitudes |
| Challenges | What was difficult, what you'd do differently | Honest reflection, not disguised brags |
| Next-period goals | 3-5 specific, measurable goals | SMART criteria: Specific, Measurable, Achievable, Relevant, Time-bound |
| Manager feedback | How can your manager better support you | Actionable requests, not generic "more feedback" |

#### Accomplishment Writing Formula

**Weak**: "Worked on the migration project."
**Strong**: "Led the database migration from PostgreSQL to CockroachDB, reducing query latency p99 from 450ms to 120ms and eliminating 3 weekly on-call pages."

Pattern: **[Action verb] + [what you did specifically] + [quantified impact]**

| Component | Questions to Answer |
|-----------|-------------------|
| Action verb | Led, designed, built, shipped, reduced, eliminated, launched, established |
| What specifically | Not the project name — your contribution to it |
| Impact | Revenue, cost, time saved, reliability, team efficiency, customer satisfaction |
| Scope | Team, org, company — how broad was the effect? |

---

### Manager Review

Purpose: Document performance assessment, provide development guidance, justify compensation recommendations.

#### Structure

| Section | Content | Constraint |
|---------|---------|-----------|
| Overall rating | Exceeds / Meets / Below Expectations | One rating. No "Meets+" hedging. |
| Performance summary | 2-3 sentence overall assessment | Covers scope, impact, and growth trajectory |
| Key strengths | 2-3 strengths with behavioral examples | Behaviors, not traits. "Documented runbooks" not "is organized." |
| Development areas | 2-3 areas with actionable guidance | Specific next steps, not vague directives |
| Goal achievement | Rating per goal with observations | Evidence-based, references specific work product |
| Development plan | Skill → current → target → actions | Actions are concrete: courses, stretch assignments, mentorship |
| Comp recommendation | Promotion / equity / adjustment / none | Justified by performance evidence, not tenure or likability |

#### Rating Scale

| Rating | Definition | Signal |
|--------|-----------|--------|
| **Exceeds Expectations** | Consistently performs above level expectations. Demonstrates next-level behaviors. High impact, broad scope. | Ready for promotion discussion or significant comp action |
| **Meets Expectations** | Solid performance at expected level. Delivers reliably. Growing in role. | On track. Standard comp progression. |
| **Below Expectations** | Not meeting expectations for current level. Specific improvement needed. | Requires development plan. May lead to PIP if sustained. |

**Rating failure modes:**
- Rating inflation: everyone gets "Exceeds." Loses meaning. Undermines calibration.
- Recency bias: rating based on last 4 weeks, not full period. Keep running notes.
- Halo/horns effect: one strong/weak area colors the entire review. Score dimensions independently.
- Central tendency: everyone gets "Meets." Avoids difficult conversations at the cost of rewarding mediocrity.

---

### Feedback Writing Patterns

#### The SBI Framework

**Situation → Behavior → Impact.** The gold standard for feedback specificity.

| Component | What It Is | Example |
|-----------|-----------|---------|
| **Situation** | When and where it happened | "During the Q3 architecture review..." |
| **Behavior** | What the person did (observable) | "...you presented three options with trade-off analysis and cost projections..." |
| **Impact** | Effect on team, project, outcomes | "...which enabled the VP to make a decision in the meeting instead of scheduling a follow-up." |

#### Positive Feedback Patterns

| Pattern | Example | Why It Works |
|---------|---------|-------------|
| SBI with reinforcement | "During [situation], you [behavior], which [impact]. Keep doing this." | Links behavior to outcome. Person knows what to repeat. |
| Growth recognition | "Six months ago, your design docs lacked trade-off analysis. This quarter, every doc included it. That improvement is visible." | Acknowledges trajectory, not just current state. |
| Scope expansion | "You've been handling incidents for your team. You also wrote the runbook that reduced MTTR for the whole org. That's next-level impact." | Recognizes broader contribution. |

#### Constructive Feedback Patterns

| Pattern | Example | Why It Works |
|---------|---------|-------------|
| SBI with forward-looking | "During [situation], [behavior] led to [impact]. Next time, try [alternative]." | Specific, not personal. Provides a concrete alternative. |
| Gap identification | "You're strong at execution. The gap I see is in proactive communication — stakeholders are sometimes surprised by delays." | Names the specific gap between current and expected. |
| Frequency + evidence | "In the last quarter, 3 of 5 project updates were late by more than a day. Let's discuss what's causing this." | Data-driven. Not "you're always late." |

#### Feedback Failure Modes

| Failure Mode | Problem | Better |
|-------------|---------|--------|
| "Great job!" | No signal. The person learns nothing about what to repeat. | Name the specific behavior and its impact. |
| "You need to communicate better." | Vague. Communicate what, to whom, when, how? | "Send project status updates to stakeholders every Friday by EOD." |
| "You're not a team player." | Personality judgment. Defensive response guaranteed. | "In the last sprint, you merged 3 PRs without requesting review. Code review is a team expectation." |
| Feedback sandwich | "Good job, but [real feedback], and good job again." Transparent. Dilutes the message. | Lead with the feedback directly. Adults can handle it. |
| "You should be more like [other person]." | Demoralizing comparison. | Describe the target behavior without naming someone else. |
| Annual surprise | Saving feedback for the review. | Feedback within 48 hours of the event. Reviews should contain no surprises. |

---

## Calibration Methodology

### Purpose

Ensure rating consistency across managers, teams, and the organization. Prevent inflation, deflation, and bias.

### Pre-Calibration Preparation

| Step | Action | Output |
|------|--------|--------|
| 1 | Manager submits proposed ratings for all direct reports | Rating spreadsheet |
| 2 | HRBP aggregates ratings by team, level, org | Distribution summary |
| 3 | Compare distribution to targets | Variance analysis |
| 4 | Identify discussion candidates | Borderline list |

### Distribution Targets

| Rating | Target Range | Red Flag |
|--------|-------------|----------|
| Exceeds Expectations | 15-20% | >30% = inflation, <10% = suppression |
| Meets Expectations | 60-70% | <50% = bimodal split |
| Below Expectations | 10-15% | 0% sustained = avoidance of difficult conversations |

**These are guidelines, not quotas.** If a team genuinely has 30% exceeds performers, the calibration discussion should surface the evidence, not force the numbers down. Forced distribution destroys trust.

### Calibration Meeting Protocol

1. **Manager presents cases** — 2 minutes per employee. Focus on top/bottom of distribution.
2. **Cross-manager challenge** — "What specific evidence supports Exceeds?" Require behavioral examples.
3. **Bias checks** — HRBP monitors for pattern biases: tenure bias (long tenure = higher rating), recency bias, similarity bias.
4. **Level-norming** — Compare across managers: "Is Manager A's 'Meets' the same as Manager B's?"
5. **Adjustment recording** — Document every rating change and the evidence that drove it.

### Promotion Readiness Assessment

| Criterion | Evidence Required |
|-----------|-------------------|
| Sustained performance | 2+ review cycles at current level demonstrating consistent delivery |
| Next-level behaviors | Already performing at least 2-3 responsibilities of the target level |
| Scope expansion | Impact extends beyond immediate team/project |
| Independence | Operates with decreasing guidance over time |
| Peer recognition | Respected by peers as operating at a higher level |

**Promotion failure modes:**
- Tenure-based promotion: "They've been here 3 years, they deserve it." Time is not evidence.
- Promise-based promotion: "Promote them and they'll step up." Evidence first, promotion second.
- Retention promotion: "If we don't promote them, they'll leave." Solves the wrong problem — likely a comp issue.
- Single-achievement promotion: One great project ≠ sustained next-level performance.

---

## Development Planning

### Development Plan Structure

| Field | Description | Example |
|-------|-------------|---------|
| Skill | The specific competency to develop | "Technical design documentation" |
| Current level | Where they are now (behavioral description) | "Writes implementation docs but not trade-off analysis" |
| Target level | Where they should be (behavioral description) | "Writes design docs with alternatives, trade-offs, and decision rationale" |
| Actions | Concrete steps to close the gap | "1. Review 3 exemplar design docs. 2. Write design doc for Project X with mentor review. 3. Present design at architecture review." |
| Timeline | When to reassess | "Review at next 1:1 in 6 weeks" |
| Support needed | Manager/org resources required | "Pair with Staff Engineer Y on first design doc" |

### Development Action Types

| Type | Best For | Examples |
|------|----------|---------|
| **Stretch assignments** | Building new skills through real work | Lead a project, own a workstream, mentor a junior |
| **Training/courses** | Foundational knowledge gaps | Conference, online course, certification |
| **Mentorship** | Navigating organizational complexity, career growth | Pair with senior leader, cross-functional mentor |
| **Exposure** | Building visibility and breadth | Present at all-hands, join cross-functional initiative, shadow senior leader |
| **Feedback loops** | Improving specific behaviors | Weekly 1:1 check-ins on the development area with specific observations |

---

## Performance Improvement Plans (PIPs)

### When to Use

- Employee has received clear feedback on performance gaps
- Gaps have persisted despite coaching (documented in 1:1 notes)
- Performance is below expectations for current level
- This is not a first conversation — surprise PIPs are failures of management, not of the employee

### PIP Structure

| Component | Content |
|-----------|---------|
| Performance gaps | Specific, behavioral, documented. "Missed 3 of 5 sprint deadlines in Q3" not "underperforming." |
| Expected level | Clear description of what meeting expectations looks like |
| Success criteria | Measurable outcomes. "Complete all sprint commitments for 4 consecutive sprints." |
| Support provided | Training, mentorship, reduced scope, regular check-ins |
| Timeline | Typically 30-60 days. Long enough to demonstrate sustained improvement. |
| Check-in cadence | Weekly minimum. Document progress at each check-in. |
| Outcomes | Meets expectations (PIP closed), partial improvement (extend or adjust), does not meet (separation) |

### PIP Guardrails

- **Legal review required** before issuing. Always.
- **Document everything.** Every conversation, every observation, every check-in.
- **Genuine path to success.** If the PIP is designed so the employee can't pass, it's not a PIP — it's a slow termination. Those destroy trust across the team.
- **Confidential.** Between the employee, their manager, and HR. Not team knowledge.
- **No PIP for skills the employee was never expected to have.** Hire for skill X, PIP for skill Y = management failure.
