# Recruiting Reference

Pipeline management, interview design, evaluation methodology, and onboarding frameworks.

---

## Pipeline Architecture

### Standard Stages

| Stage | Owner | Duration Target | Key Actions | Exit Criteria |
|-------|-------|-----------------|-------------|---------------|
| **Sourced** | Recruiter | 0-3 days | Identify, personalize outreach, initial contact | Response received (positive or negative) |
| **Screen** | Recruiter | 3-5 days | Phone/video screen, basic fit assessment | Meets minimum qualifications + culture signal |
| **Interview** | Hiring panel | 5-10 days | Structured competency interviews (2-4 rounds) | All competencies scored, panel aligned |
| **Debrief** | Hiring manager | 1-2 days | Calibrate feedback, make hire/no-hire decision | Clear decision with documented reasoning |
| **Offer** | Recruiter + HM | 2-5 days | Package assembly, approval chain, extension | Offer extended with deadline |
| **Accepted** | Recruiter | 1-7 days | Negotiation (if needed), verbal/written acceptance | Signed offer letter |
| **Onboarding** | Manager + HR | Pre-start → 90 days | Equipment, accounts, buddy, 30/60/90 plan | Employee productive and integrated |

### Stage Transition Rules

- Never skip Screen → Interview. Every candidate gets the same structured evaluation path.
- Debrief happens within 48 hours of final interview. Delayed debriefs degrade recall and produce vague feedback.
- Offer approval chain completes before verbal offer. Verbal offers without approval create legal exposure.

---

## Pipeline Metrics

### Velocity Metrics

| Metric | Definition | Healthy Range | Warning Threshold |
|--------|------------|---------------|-------------------|
| Time to fill | Days from req open to offer accepted | 30-45 days (IC), 45-60 (manager) | >60 days IC, >90 days manager |
| Days in stage | Average time per pipeline stage | 3-7 per stage | Any stage >14 days |
| Pipeline velocity | Candidates moved per week across all stages | Depends on volume | Declining trend over 3+ weeks |
| Offer-to-accept | Days from offer extended to signed | 3-7 days | >14 days |

### Conversion Metrics

| Transition | Target Conversion | Signal When Low |
|------------|-------------------|-----------------|
| Sourced → Screen | 30-50% | Poor targeting or weak outreach |
| Screen → Interview | 40-60% | Screen criteria too loose or too tight |
| Interview → Offer | 20-40% | Bar miscalibration, weak pipeline top |
| Offer → Accepted | 70-90% | Comp not competitive, slow process, poor candidate experience |
| Overall funnel | 5-15% sourced to accepted | Healthy range for most roles |

### Source Effectiveness

Track per channel: volume sourced, conversion to hire, cost per hire, time to fill, quality of hire (90-day retention + performance).

| Source Type | Typical Strengths | Watch For |
|-------------|-------------------|-----------|
| Referrals | Highest conversion, fastest, best retention | Homogeneity risk — referral networks mirror existing team demographics |
| Inbound (job boards) | Volume | Low conversion, high noise |
| Outbound (sourcing) | Passive talent access | Low response rates, high recruiter time cost |
| Agencies | Speed for hard-to-fill roles | High cost (15-25% of first-year comp), misaligned incentives |
| University/intern pipeline | Long-term talent development | Long ramp time, seasonal |

---

## Interview Design

### Competency Framework

For each role, define 4-6 competencies. Each competency gets dedicated interview time.

| Component | Description | Example |
|-----------|-------------|---------|
| **Competency** | Observable skill or behavior the role requires | "System design" or "cross-team collaboration" |
| **Behavioral questions** | Past behavior predicts future behavior. "Tell me about a time..." | "Tell me about a time you had to design a system under tight constraints." |
| **Situational questions** | Hypothetical scenarios revealing approach. "How would you..." | "How would you handle a production outage you'd never seen before?" |
| **Follow-up probes** | Dig deeper on specifics. Force detail beyond rehearsed answers. | "What specifically did you do vs. what the team did?" |
| **Scoring rubric** | 1-4 scale with behavioral anchors per level | See rubric table below |

### Scoring Rubric Template

| Score | Label | Behavioral Anchor |
|-------|-------|-------------------|
| 1 | Does not meet | Cannot demonstrate the competency. No relevant examples. Concerning signals. |
| 2 | Partially meets | Some evidence but inconsistent. Needs significant development. Limited scope examples. |
| 3 | Meets expectations | Clear evidence of competency at expected level. Multiple relevant examples. Appropriate scope. |
| 4 | Exceeds | Strong evidence beyond expected level. Complex examples. Demonstrates teaching/leading in this area. |

**Scoring rules:**
- Score each competency independently. Do not let one strong/weak area contaminate others.
- Score against the rubric, not against other candidates (comparative scoring amplifies similarity bias).
- Score immediately after the interview. Do not wait for the debrief (anchor bias increases with delay).
- Record specific evidence for each score, not just the number.

### Interview Panel Design

| Principle | Implementation |
|-----------|---------------|
| Cover all competencies | Map each interviewer to 1-2 competencies. No competency unassessed. |
| Diverse perspectives | Panel varies by seniority, function, background. Minimum 3 interviewers. |
| No duplicate coverage | Two interviewers on the same competency wastes candidate time and creates anchoring. |
| Trained interviewers | Everyone on the panel has completed structured interviewing training. |
| Consistent questions | Same question set per competency across all candidates for the same role. |

### Question Design Failure Modes

| Failure Mode | Problem | Better Approach |
|-------------|---------|-----------------|
| "What's your greatest weakness?" | Rehearsed answers. Zero signal. | "Tell me about a project that didn't go well and what you learned." |
| Brain teasers | Test puzzle familiarity, not job skills | Use role-relevant problem-solving scenarios |
| "Where do you see yourself in 5 years?" | Penalizes honesty. Rewards performance. | "What kind of work energizes you most?" |
| Leading questions | "You'd agree that X is important, right?" | Open-ended: "How do you think about X?" |
| Illegal questions | Age, family status, religion, disability, national origin | Never ask. Train interviewers on prohibited topics. |
| Culture fit (vague) | Proxy for "like me" — homogeneity bias | Define specific values + behaviors. Evaluate those. |

---

## Debrief Structure

### Debrief Protocol

1. **Independent scoring first.** All interviewers submit scores before the debrief meeting. No anchoring.
2. **Structured discussion.** Walk through each competency. Interviewer presents evidence, then score.
3. **Evidence-based.** "I scored 3 on system design because [specific example from interview]" — not "I liked them."
4. **Disagree on evidence, not feelings.** When scores differ, discuss the evidence. What did one interviewer see that another didn't?
5. **Decision framework.** Strong hire / Hire / No hire / Strong no hire. Require at least one "strong hire" and no "strong no hire" to proceed.

### Debrief Template

```
## Candidate Debrief: [Name] — [Role]
Date: [Date] | Panel: [Names]

### Competency Scores
| Competency | Interviewer | Score | Key Evidence |
|------------|-------------|-------|-------------|
| [Comp 1]   | [Name]      | [1-4] | [Specific example] |
| [Comp 2]   | [Name]      | [1-4] | [Specific example] |

### Strengths (evidence-based)
- [Strength with specific example]

### Concerns (evidence-based)
- [Concern with specific example]

### Decision: [Strong hire / Hire / No hire / Strong no hire]
### Reasoning: [2-3 sentences]
```

---

## Onboarding Framework

### Pre-Start Checklist (Before Day 1)

| Category | Task | Owner | Timeline |
|----------|------|-------|----------|
| Communication | Send welcome email (start date, time, logistics, dress code) | Recruiter/Manager | 1 week before |
| Accounts | Set up email, Slack, core tools for role | IT | 3 days before |
| Equipment | Order/configure laptop, monitor, peripherals | IT | 1 week before |
| Access | Grant repo/system access appropriate for role | Manager/IT | Day 1 |
| People | Assign onboarding buddy (not manager, peer-level) | Manager | 1 week before |
| Calendar | Add to team standup, recurring meetings, socials | Manager | 3 days before |
| Space | Prepare desk / ship remote setup | Office ops | 3 days before |
| Documentation | Prepare reading list, team wiki links, architecture docs | Manager | 1 week before |

### Day 1 Schedule Template

| Time | Activity | With | Goal |
|------|----------|------|------|
| 9:00 | Welcome, logistics, building/remote tour | Manager | Comfort, orientation |
| 10:00 | IT setup, tool walkthrough | IT / Buddy | Functional access |
| 11:00 | Team introductions (individual, not group) | Team members | Personal connection |
| 12:00 | Welcome lunch | Manager + 2-3 team | Informal relationship building |
| 1:30 | Company context: mission, values, how we work | Manager | Alignment |
| 3:00 | Role expectations, 30/60/90 goals, first project | Manager | Clarity on success criteria |
| 4:00 | Free exploration: read docs, poke around tools | Self | Self-directed onboarding |

### 30/60/90-Day Framework

| Period | Focus | Success Looks Like |
|--------|-------|-------------------|
| **Days 1-30** | Learn | Understands team, codebase/domain, processes. Completes 1-2 small tasks. Has asked many questions. |
| **Days 31-60** | Contribute | Delivers independently on scoped work. Participates in reviews. Identifies one improvement. |
| **Days 61-90** | Own | Owns a workstream. Contributes to planning. Can onboard the next new hire. |

### Onboarding Failure Modes

| Failure Mode | Problem | Fix |
|-------------|---------|-----|
| Information firehose Day 1 | Overwhelming, nothing retained | Spread learning over 2 weeks. Day 1 = setup + relationships. |
| No buddy assigned | New hire bothers manager for everything or stays silent | Assign a peer buddy. Not the manager. Someone approachable. |
| Unclear first task | New hire sits idle, feels useless | Have a real (small, shippable) task ready for week 1. |
| No check-ins | Problems fester for weeks | Daily check-in week 1, then weekly through day 90. |
| Sink or swim | "Smart people figure it out" — they do, slowly and resentfully | Structure is not hand-holding. It's efficiency. |

---

## Job Posting Quality Checklist

Run every job posting through these checks before publishing.

| Check | What to Look For | Action |
|-------|-----------------|--------|
| Gendered language | "Rockstar", "ninja", "aggressive", "dominant" | Replace with neutral terms. Use tools like Textio or manual review. |
| Unnecessary requirements | "10 years experience" for a mid-level role, degree requirements for skills-based roles | Separate must-have from nice-to-have. Cut inflated requirements. |
| Exclusionary phrasing | "Culture fit", "young and dynamic team", "native English speaker" | Remove. Replace with specific behavioral requirements. |
| Jargon overload | Acronyms, internal terminology | Plain language. A candidate outside your company should understand every requirement. |
| Benefits buried | Salary range and benefits not visible | Lead with or clearly include compensation range. Many jurisdictions require it. |
| Passive voice | "Responsibilities will include..." | Active voice: "You will..." |
