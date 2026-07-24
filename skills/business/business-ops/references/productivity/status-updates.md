# Status Updates Reference

Deep reference for status communication across audiences, standup optimization, retrospective facilitation, and change communication. Loaded by STATUS mode.

---

## Status Update Templates by Audience

### Manager (1:1 Update)

**Frame**: What you need from them + what they need to know about your work.

```
## This Week

**Shipped**
- [Outcome 1] — [impact or next step]
- [Outcome 2] — [impact or next step]

**In Progress**
- [Work item] — [% complete, expected done date]

**Blocked / Need Your Help**
- [Blocker] — I need [specific ask] by [date] to unblock [deliverable]

**Heads Up**
- [Risk or upcoming change] — no action needed yet, but [context]
```

**Key principle**: Lead with what you need from your manager. That is the actionable part. They can skim the rest.

### Team (Standup / Daily Update)

**Frame**: What the team can act on right now.

```
**Blockers** (if any — lead with these)
- [Blocker] — need [specific help] from [person]

**Done yesterday**
- [Outcome] (not "worked on X" — what finished?)

**Today's focus**
- [Single most important deliverable]
```

**Duration**: 60 seconds spoken, 3-5 lines written. Anything longer belongs in a separate conversation.

**Standup optimization rules**:
- Lead with blockers because that is the only part the team can act on in real time
- Say what finished (outcomes), not what you touched (activities)
- State one focus, not a task list — the team needs to know your priority, not your full schedule
- If you have nothing blocked and nothing interesting to report, say "No blockers, continuing on [project]" — do not invent content

### Stakeholder Update

**Frame**: Business impact + timeline + risks + decisions needed.

```
## [Project Name] — Status Update [Date]

### Summary
[2-3 sentences: what happened, what it means, what comes next]

### Progress
| Milestone | Status | Notes |
|-----------|--------|-------|
| [Milestone 1] | Done | [Key outcome or metric] |
| [Milestone 2] | On Track | [Expected completion date] |
| [Milestone 3] | At Risk | [Why and what we're doing about it] |

### Risks
| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| [Risk 1] | [What happens if it materializes] | High/Med/Low | [What we're doing] |

### Decisions Needed
- [Decision] — from [person/group] — by [date] — to unblock [what]

### Next Period
- [Key deliverable 1] — [expected date]
- [Key deliverable 2] — [expected date]
```

### Executive Update

**Frame**: Red/Yellow/Green + decisions needed. Executives scan, they do not read.

```
## [Project Name] — [GREEN/YELLOW/RED]

**One-line summary**: [What happened and why it matters to the business]

**Key metric**: [Number] vs [target] ([trend direction])

**Decision needed**: [Specific decision] by [date]
— Option A: [one sentence + tradeoff]
— Option B: [one sentence + tradeoff]
— Recommendation: [which and why]

**Next milestone**: [What] by [when]
```

**Rules for executive updates**:
- Under 200 words. If it is longer, it will not be read.
- Lead with conclusion, not journey. "We shipped X and it moved Y" — not "we had 14 standups and 3 sprint reviews."
- Status color reflects reality, not optimism. Yellow means "at risk with a mitigation plan." Red means "we need help." Calling a red project yellow to avoid a difficult conversation makes the eventual conversation worse.
- Every risk has a mitigation. Surfacing a risk without a plan is an alarm, not an update.

---

## The Progress/Plans/Problems Format

The universal format that works for any audience with adjustment to detail level.

### Progress (What Shipped)

**Frame as outcomes, not activities.**

| Activity Framing (avoid) | Outcome Framing (use) |
|--------------------------|----------------------|
| "Worked on the search feature" | "Shipped search indexing — queries are 40% faster" |
| "Had meetings about the launch plan" | "Aligned on March 15 launch date with marketing and engineering" |
| "Reviewed the Q2 roadmap" | "Finalized Q2 roadmap: 3 themes, 12 initiatives, capacity-matched" |
| "Investigated the performance issue" | "Identified the root cause: N+1 queries on the dashboard. Fix shipping tomorrow." |

**Why this matters**: Activity framing signals effort. Outcome framing signals impact. Stakeholders care about impact. Team members care about impact. Your future self reviewing these updates cares about impact.

### Plans (What Is Coming)

- State commitments with confidence levels:
  - **Committed**: "Will ship by Friday" (90%+ confidence)
  - **Planned**: "Targeting next week" (70% confidence)  
  - **Stretch**: "If capacity allows" (< 50% confidence)
- Include dependencies: "Shipping the integration depends on API access from Platform team, expected Wednesday."
- Flag timeline changes with reasons: "Originally targeting March 1, now March 8 due to [specific reason]."

### Problems (What Is Blocked or At Risk)

Every problem gets three parts:

1. **What**: Clear statement of the blocker or risk
2. **Impact**: What happens if it is not resolved (deadline miss, quality degradation, downstream delay)
3. **Ask**: Specific request with a named owner and deadline

**Good problem statement**: "The staging environment has been down since Monday, blocking integration testing. If not resolved by Wednesday, the March 15 launch date is at risk. Need DevOps to prioritize the fix — I've escalated to [name]."

**Weak problem statement**: "Staging is down, which is causing issues."

---

## Retrospective Facilitation

### Format: Start/Stop/Continue

The simplest effective retro format.

| Category | Prompt | Example |
|----------|--------|---------|
| **Start** | What should we begin doing? | "Start writing decision memos before scheduling decision meetings" |
| **Stop** | What should we stop doing? | "Stop extending sprint scope after planning. Additions go to next sprint." |
| **Continue** | What is working well? | "Continue the Thursday code review pairing — it's catching bugs faster" |

### Facilitation Protocol

1. **Set the stage** (5 min): State the retro's scope (last sprint, last month, specific project). Remind the team that the goal is improvement, not blame.
2. **Gather data** (10 min): Each person writes their Start/Stop/Continue items silently. One item per note. No discussion during writing.
3. **Cluster** (10 min): Group similar items. Name each cluster. Identify the top 3 clusters by dot voting.
4. **Discuss** (20 min): For each top cluster, discuss:
   - What is happening? (observations)
   - Why is it happening? (root cause, not symptoms)
   - What can we change? (specific action, not aspiration)
5. **Decide** (5 min): Pick 1-2 action items. Each has an owner and a deadline. More than 2 actions from a single retro dilutes focus.

### Retro Failure Modes with Corrections

| Failure Mode | What Goes Wrong | Do Instead |
|-------------|----------------|------------|
| Blame-oriented discussion | People defend instead of improving | Frame as system problems: "What about our process allowed this?" not "Who caused this?" |
| Action items without owners | Nothing happens between retros | Every action item has a named owner and a specific deadline |
| Too many action items | Nothing gets priority attention | Maximum 2 action items per retro. Less is more. |
| Skipping the retro because "we're busy" | The team loses its only improvement feedback loop | Keep the retro. Shorten it to 15 minutes if needed. A short retro beats no retro. |
| Same issues every retro | Actions from previous retros are not tracked | Start each retro by reviewing last retro's action items. Did they happen? Did they help? |
| Only discussing recent events | Recency bias ignores systemic patterns | Explicitly ask about patterns: "Is this the first time, or does this keep happening?" |

---

## Change Communication

When plans, timelines, or scope change, communicate proactively.

### Change Communication Template

```
## Change: [What Changed]

**What**: [Specific change in one sentence]
**Why**: [Root cause — honest, not spin]
**Impact**: [What this means for stakeholders — timeline, scope, deliverables]
**Mitigation**: [What we're doing to minimize impact]
**New plan**: [Updated timeline or scope with confidence level]
**Ask**: [What you need from the audience, if anything]
```

### Communication Timing

| Change Type | When to Communicate | To Whom |
|-------------|-------------------|---------|
| Timeline slip (< 1 week) | Within 24 hours | Direct team, manager |
| Timeline slip (> 1 week) | Same day you know | Manager, stakeholders, dependent teams |
| Scope reduction | Before it is finalized | Stakeholders who requested the cut items |
| Scope increase | Before accepting | Manager (for capacity impact), team (for workload) |
| Risk materialized | Immediately | Anyone affected + anyone who can help |
| Strategy change | As soon as decided | Full team + stakeholders |

**Key principle**: Communicate bad news early. The earlier you surface a problem, the more options exist to address it. Late surprises destroy trust faster than early warnings.

---

## Update Cadence Guide

| Cadence | When to Use | Format |
|---------|------------|--------|
| **Daily** (standup) | Active sprint, high-velocity project, crisis response | Blockers/Done/Focus — 60 seconds |
| **Weekly** | Standard project cadence, manager 1:1s | Progress/Plans/Problems — 1 page |
| **Biweekly** | Steady-state projects, low-change-rate work | Summary with key metrics and risks |
| **Monthly** | Executive reporting, long-running programs | Scorecard + narrative + decisions needed |
| **Ad hoc** | Significant changes, milestones, escalations | Change communication template |

**Rule of thumb**: Update at the cadence of decision-making. If decisions happen weekly, update weekly. If the team makes daily decisions, update daily. Updating more frequently than decisions are made creates noise. Updating less frequently creates information gaps.
