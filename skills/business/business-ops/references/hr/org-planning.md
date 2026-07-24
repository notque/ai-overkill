# Org Planning Reference

Headcount modeling, org design principles, capacity planning, and people analytics.

---

## Org Design Principles

### Design Variables

| Variable | Options | Trade-offs |
|----------|---------|------------|
| **Structure type** | Functional, Product, Matrix, Pod | See structure comparison below |
| **Span of control** | Narrow (3-5) vs. Wide (8-12) | Narrow = more managers, more layers. Wide = less overhead, more autonomy required. |
| **Centralization** | Centralized vs. Distributed | Centralized = consistency, efficiency. Distributed = speed, local adaptation. |
| **Reporting depth** | Flat (2-3 layers) vs. Deep (5+ layers) | Flat = faster decisions, harder to manage scale. Deep = more career levels, slower. |

### Structure Comparison

| Structure | Best For | Strengths | Weaknesses |
|-----------|----------|-----------|------------|
| **Functional** | Stable domains, shared expertise | Deep specialization, clear career paths, resource efficiency | Cross-functional coordination is slow, siloed priorities |
| **Product** | Customer-facing delivery, speed | End-to-end ownership, fast decisions, customer-aligned | Duplicate expertise, inconsistent standards, people isolation |
| **Matrix** | Complex orgs needing both depth and delivery | Balances specialization with delivery | Dual reporting confusion, political, requires mature management |
| **Pod/Squad** | Cross-functional delivery at small scale | Autonomy, speed, clear mission | Hard to scale, skill development challenges, resource allocation |

### Healthy Org Benchmarks

| Metric | Healthy Range | Warning | Critical |
|--------|---------------|---------|----------|
| Span of control | 5-8 direct reports | <4 or >10 | <3 (vanity titles) or >12 (neglect) |
| Management layers | 1 per 50-100 people | >1 per 30 | >1 per 20 |
| IC-to-manager ratio | 6:1 to 10:1 | <5:1 | <3:1 (top-heavy, excess overhead) |
| Team size | 5-9 people | <4 or >10 | <3 (fragile) or >12 (unmanageable) |
| Single points of failure | 0 critical | 1-2 | >3 (bus factor risk) |
| Skip-level ratio | Every IC has skip-level access | Some don't | No skip-levels happening |

### Org Design Failure Modes

| Failure Mode | Symptom | Root Cause | Fix |
|-------------|---------|-----------|-----|
| **Empire building** | Managers optimizing headcount over outcome | Headcount = status in org culture | Measure outcomes per person, not team size |
| **Reporting line as reward** | Star performer gets direct reports as "promotion" | No IC growth track | Build a staff/principal IC ladder with real scope |
| **Shadow org** | Informal decision-making bypasses the official chart | Org structure doesn't match actual information flow | Redesign around how work actually flows |
| **Reorg churn** | Annual restructures that never settle | Treating structure as the solution to execution problems | Fix execution, then assess if structure change is still needed |
| **Single point of failure** | One person holds all context for a critical system | Under-investment in documentation and knowledge sharing | Immediate pairing, documentation sprint, cross-training |
| **Absentee manager** | Manager has too many reports, too many meetings, no 1:1 time | Span too wide, manager also an IC | Reduce span or remove IC responsibilities |

---

## Headcount Modeling

### Planning Framework

| Dimension | Questions | Output |
|-----------|-----------|--------|
| **Demand** | What work needs to happen? What's the project/product roadmap? | Required capacity by function |
| **Supply** | Who do we have? What can they deliver? What's the attrition forecast? | Current capacity with risk adjustment |
| **Gap** | Where does demand exceed supply? Which gaps are most critical? | Prioritized hiring list |
| **Sequence** | Which hires unlock the most capacity or reduce the most risk? | Quarterly hiring roadmap |
| **Budget** | What does this cost? What are the trade-offs? | Cost model with scenarios |

### Headcount Request Template

| Field | Content | Example |
|-------|---------|---------|
| Role | Title, level, function | Senior Backend Engineer, L4 |
| Justification | Why this role, why now | "Auth service rewrite blocked on capacity. No existing team member has IdP integration experience." |
| Impact if unfilled | What happens without this hire | "Auth rewrite slips to Q3. SOC2 compliance timeline at risk." |
| Alternative considered | Can existing team absorb? Contractor? Defer? | "Contractor evaluated — context ramp time makes FTE more efficient for 6+ month project." |
| Cost | Fully loaded annual cost | $280K (base $180K + equity $60K + benefits $40K) |
| Timeline | When needed, how long to fill | Start by April 1. Expect 45-day fill time. Req must open by Feb 15. |
| Hiring manager | Who owns the search | [Name] |

### Cost Modeling

| Cost Component | Typical Multiplier | Notes |
|---------------|-------------------|-------|
| Base salary | 1.0x | Cash compensation |
| Benefits | 0.2-0.3x base | Health, dental, vision, retirement, insurance |
| Equity | 0.1-0.5x base | Varies dramatically by stage |
| Payroll taxes | 0.08-0.12x base | FICA, state taxes, unemployment |
| Equipment/onboarding | $3-8K one-time | Laptop, monitor, software licenses |
| Recruiting | 0.15-0.25x first-year base (agency) or $5-15K (in-house) | Per hire |
| **Fully loaded multiplier** | **1.3-1.6x base** | Rule of thumb for total cost |

### Scenario Planning

Model three scenarios for every headcount plan:

| Scenario | Assumption | Impact |
|----------|-----------|--------|
| **Optimistic** | All hires filled on time, no attrition, budget approved in full | Full roadmap delivery |
| **Baseline** | 80% of hires filled, standard attrition (10-15%), budget 85% approved | Adjusted roadmap with prioritization |
| **Conservative** | 60% of hires filled, elevated attrition (20%), budget constrained | Critical path only, defer non-essential |

Always present baseline as the plan and conservative as the contingency.

---

## Capacity Planning

### Capacity Calculation

```
Available capacity = (Headcount) * (Working days) * (Productivity factor)
Productivity factor = 1.0 - (meetings + overhead + PTO + onboarding ramp)
```

Typical productivity factors:

| Role Type | Productivity Factor | Why |
|-----------|-------------------|-----|
| IC (execution-heavy) | 0.65-0.75 | Meetings, overhead, context switching |
| IC (new hire, first 90 days) | 0.25-0.50 | Onboarding ramp |
| Manager | 0.20-0.40 for individual contribution | Most time goes to people management, meetings, planning |
| Tech lead (hybrid) | 0.40-0.55 | Split between execution and coordination |

### Gap Analysis

| Gap Type | Signal | Resolution Options |
|----------|--------|-------------------|
| **Skill gap** | Team lacks expertise for planned work | Hire, train existing, contractor, defer project |
| **Capacity gap** | Team has skills but not enough people | Hire, prioritize ruthlessly, extend timelines |
| **Coverage gap** | Single point of failure for critical function | Cross-train, document, pair, hire backup |
| **Leadership gap** | Team needs a manager or tech lead and doesn't have one | Promote internal (preferred), hire external |

---

## People Analytics

### Headcount Reporting

| Dimension | Cuts | Frequency |
|-----------|------|-----------|
| By team/department | All org units | Monthly |
| By location | Office, remote, geo | Monthly |
| By level | IC levels, management levels | Quarterly |
| By tenure | Bands: <1yr, 1-2yr, 2-5yr, 5+ yr | Quarterly |
| By function | Engineering, product, design, ops, etc. | Monthly |

### Attrition Analysis

| Metric | Formula | Healthy Range |
|--------|---------|---------------|
| Overall attrition | (Departures in period / Average headcount) * 12/months | 10-15% annual |
| Voluntary attrition | Voluntary departures only | 8-12% annual |
| Regrettable attrition | Voluntary departures of high performers | <5% annual |
| Involuntary attrition | Terminations, layoffs | <5% (steady state) |
| New hire attrition (first year) | New hires who leave within 12 months | <15% |

### Attrition Root Cause Categories

| Category | Indicators | Intervention |
|----------|-----------|-------------|
| **Compensation** | Below-market comp, no recent adjustment, competitor offers | Market adjustment, retention package |
| **Manager** | Exit interviews cite manager, low manager scores | Manager coaching, reassignment, skip-level program |
| **Growth** | Exit interviews cite lack of growth, stale role | Career pathing, stretch assignments, lateral moves |
| **Culture** | Exit interviews cite culture, belonging issues | Team health assessment, inclusion initiatives |
| **Burnout** | High hours, no PTO usage, on-call burden | Workload audit, mandatory PTO, on-call rotation fix |
| **Personal** | Relocation, career change, family | Limited intervention — wish them well |

### Diversity Metrics

| Metric | What to Measure | Granularity |
|--------|----------------|-------------|
| Representation | Headcount by demographic group | By level, team, function |
| Hiring pipeline | Applicant, screen, interview, offer, accept by group | By role, source |
| Promotion rate | Promotions per group / eligible population per group | By level transition |
| Attrition rate | Departures per group / headcount per group | By voluntary/involuntary |
| Pay equity | Compa-ratio by demographic group at same level/role | By role family + level |
| Inclusion scores | Survey responses by demographic group | By team |

**Reporting constraints:**
- Minimum group size of 5 before reporting demographics (below that, individuals are identifiable)
- Present as rates, not raw counts (counts without context are misleading)
- Compare like-for-like: same role, same level, same location
- Trends over time matter more than snapshots

### Engagement Metrics

| Metric | Source | Healthy Range |
|--------|--------|---------------|
| eNPS (Employee Net Promoter Score) | Survey: "How likely to recommend as a workplace?" | 10-50 (>30 = strong) |
| Engagement index | Composite of survey questions on motivation, satisfaction, commitment | >70% favorable |
| Participation rate | Survey response rate | >75% |
| Manager effectiveness | Survey questions on manager quality | >75% favorable |
| Growth perception | "I have opportunities to grow here" | >65% favorable |

### Flight Risk Model

Composite risk score based on multiple factors:

| Factor | Weight | Data Source |
|--------|--------|------------|
| Compa-ratio < 0.85 | 25% | Comp data |
| Time since last promotion > 2 years | 20% | HRIS |
| Low engagement score | 20% | Survey |
| Manager effectiveness score (low) | 15% | Survey |
| Approaching vesting cliff | 10% | Equity data |
| Tenure at risk inflection (18mo, 3yr) | 10% | HRIS |

**Risk levels:**
- Low (0-30): Monitor in regular cycle
- Medium (31-60): Proactive manager conversation
- High (61-100): Immediate retention intervention

---

## Reorg Planning

### Decision Framework: When to Reorg

| Situation | Reorg Appropriate? | Why |
|-----------|-------------------|-----|
| Work is flowing fine but "could be better" | No | Churn cost > marginal improvement |
| Two teams do overlapping work with conflicts | Yes | Clear duplication and coordination failure |
| Team is too large for one manager | Partial — split, don't reorg | Targeted change, minimal disruption |
| New product/market requires cross-functional team | Maybe — pod first | Try a pod/squad before restructuring |
| Post-acquisition integration | Yes | Merge teams, eliminate redundancy, align cultures |
| Manager departure creates vacuum | Partial — backfill or merge | Don't reorg around one person's departure |

### Reorg Communication Plan

| Phase | Timeline | Audience | Content |
|-------|----------|----------|---------|
| **Pre-announcement** | 1-2 weeks before | Senior leaders | Changes, rationale, their role in communication |
| **Announcement** | Day 0 | All affected employees | What's changing, why, what it means for each person |
| **1:1 conversations** | Day 0-3 | Each affected individual | Personal impact, new manager, new team, questions |
| **Team kickoff** | Week 1 | New teams | Mission, priorities, working agreements |
| **30-day check-in** | Day 30 | All affected | How's it going, what needs adjustment |

### Reorg Failure Modes

| Failure Mode | Risk | Prevention |
|-------------|------|-----------|
| Announcing before 1:1s | People learn about their new manager in an all-hands | Individual conversations first, then group announcement |
| Reorg without clear "why" | Perceived as political, creates cynicism | State the problem the reorg solves. If you can't, don't reorg. |
| Changing everything at once | Disorientation, productivity cliff | Change structure OR process OR tools — not all three simultaneously |
| No success metrics | Can't tell if the reorg worked | Define measurable outcomes before executing |
| Ignoring informal networks | Reorg severs critical informal communication channels | Map informal networks, preserve key connections intentionally |
