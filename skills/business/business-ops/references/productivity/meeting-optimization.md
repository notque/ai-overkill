# Meeting Optimization Reference

Deep reference for meeting audits, agenda design, async conversion, and recurring meeting optimization. Loaded by MEETING mode.

---

## The 5P Audit Framework

Every meeting should pass this framework. If it fails on Purpose, the meeting should not exist.

| P | Question | Pass Criteria | Fail Signal |
|---|----------|--------------|-------------|
| **Purpose** | What decision or outcome does this meeting produce? | Specific, articulable outcome that requires real-time interaction | "Touch base," "sync up," "stay aligned" with no concrete deliverable |
| **Participants** | Does every attendee have a role (decide, input, inform)? | Each person either makes a decision, provides input that changes the outcome, or needs the information to act | More than 2 people who are "just listening" — they should get notes instead |
| **Preparation** | What should attendees review beforehand? | Pre-read exists and is distributed 24h+ before | Attendees arrive cold. The first 15 minutes are context-setting. |
| **Process** | How will the meeting be run? | Agenda with time allocations, facilitation plan, decision method | Freeform discussion that ends when time runs out |
| **Payoff** | What leaves the room? | Decisions documented, action items assigned with owners and deadlines | "Good discussion" with no recorded outcomes |

### Applying the Audit

For each meeting under review:

1. State the Purpose in one sentence. If you need two sentences, the meeting has two purposes — split it or pick one.
2. List every Participant with their role. Anyone without a clear role is optional — make them optional.
3. Identify the Preparation gap. If none exists, create a pre-read document.
4. Design the Process. Allocate time per agenda item. Identify the decision method for each decision item.
5. Define the Payoff. What artifacts does this meeting produce? Who captures them?

---

## Meeting Types and Templates

### Decision Meeting

**Purpose**: Arrive at a specific decision with the people who have authority and context.

| Element | Specification |
|---------|--------------|
| **Duration** | 30 min (extend to 45 only if multiple decisions) |
| **Attendees** | Decision maker + 2-4 people with critical context. Informed parties get notes. |
| **Pre-read** | 1-page decision memo: context, options (3 max), recommendation, tradeoffs |
| **Agenda** | 5 min: Confirm everyone read the memo. 15 min: Debate the options. 5 min: Make the decision. 5 min: Document and assign next steps. |
| **Output** | Decision recorded. Rationale documented. Action items assigned. |

**Key principle**: The meeting is for debate and decision, not for presenting context. Context goes in the pre-read. If attendees have not read it, spend 5 minutes on a verbal summary, then proceed — do not re-present the full document.

### Discussion Meeting

**Purpose**: Explore a topic, gather perspectives, develop shared understanding.

| Element | Specification |
|---------|--------------|
| **Duration** | 45-60 min |
| **Attendees** | People with diverse perspectives on the topic. 4-8 optimal. |
| **Pre-read** | Framing document: what we know, what we are exploring, specific questions to answer |
| **Agenda** | 5 min: Frame the discussion with specific questions. 35-45 min: Structured discussion (round-robin or breakout). 5-10 min: Synthesize key takeaways, identify follow-ups. |
| **Output** | Key insights documented. Open questions listed. Next steps and owners assigned. |

### Information Meeting

**Purpose**: Communicate information that requires Q&A or immediate reaction.

| Element | Specification |
|---------|--------------|
| **Duration** | 15-25 min maximum |
| **Attendees** | Only people who need to act on the information |
| **Pre-read** | The information itself (document, dashboard, announcement) |
| **Agenda** | 5 min: Highlight what changed and why it matters. 10-15 min: Q&A. 5 min: Action items. |
| **Output** | Questions answered. Action items captured. |

**Async-first check**: If no Q&A is expected and no immediate action is needed, this should be an email/document with a deadline for questions. Convert to async.

### Brainstorm Meeting

**Purpose**: Generate ideas on a specific problem.

| Element | Specification |
|---------|--------------|
| **Duration** | 45-60 min |
| **Attendees** | 3-6 people with diverse perspectives. More than 6 fragments the conversation. |
| **Pre-read** | Problem statement with constraints, prior attempts, and what "good" looks like |
| **Agenda** | 10 min: Restate problem and constraints. 20 min: Diverge — generate ideas (no evaluation). 15 min: Converge — cluster, evaluate, select top 3. 10 min: Define next steps for top ideas. |
| **Output** | Ranked list of ideas. Top 3 with assigned owners for next steps. |

**Facilitation rule**: Separate divergent and convergent thinking. Evaluating ideas during generation kills creativity. Generate first, evaluate second.

---

## Async-First Decision Tree

Before scheduling any meeting, apply this filter:

```
Does this require real-time interaction?
├── NO: Can it be a document with comments?
│   ├── YES → Write the document. Set a comment deadline. Skip the meeting.
│   └── NO: Can it be a recorded video + async feedback?
│       ├── YES → Record a Loom/video. Set a feedback deadline.
│       └── NO → Schedule the meeting (rare path).
└── YES: Does it require back-and-forth debate?
    ├── YES → Schedule a Decision Meeting (30 min)
    └── NO: Does it require brainstorming?
        ├── YES → Schedule a Brainstorm Meeting (45-60 min)
        └── NO → Schedule an Information Meeting (15-25 min)
```

### Situations That Genuinely Need Meetings

| Situation | Why Async Fails |
|-----------|----------------|
| Sensitive feedback (performance, conflict) | Tone and nuance get lost in text. Real-time allows reading reactions. |
| Multi-party negotiation | Async threads create misalignment. Real-time converges faster. |
| Creative brainstorming | Idea building requires rapid back-and-forth energy. |
| Crisis response | Speed of coordination matters more than documentation quality. |
| Relationship building (1:1s) | Trust is built through presence, not documents. |

### Situations That Should Almost Always Be Async

| Situation | Better Async Format |
|-----------|-------------------|
| Status updates | Written update in a shared channel with a template |
| FYI announcements | Email or document with a "questions by [date]" deadline |
| Document reviews | Comments on the document, consolidated by the author |
| Progress check-ins | Dashboard or weekly written summary |
| Information sharing | Recorded walkthrough video (< 10 min) |

---

## Meeting Cost Calculator

### Formula

```
Annual cost = (# participants) x (avg hourly cost) x (duration in hours) x (frequency per year)
```

### Common Examples

| Meeting | Participants | Duration | Frequency | Annual Cost (@$75/hr) |
|---------|-------------|----------|-----------|----------------------|
| Weekly team standup | 8 | 30 min | 50/year | $15,000 |
| Weekly team sync | 8 | 60 min | 50/year | $30,000 |
| Biweekly sprint planning | 6 | 90 min | 26/year | $17,550 |
| Monthly all-hands | 30 | 60 min | 12/year | $27,000 |
| Daily standup | 5 | 15 min | 250/year | $15,625 |
| Weekly 1:1 | 2 | 30 min | 50/year | $3,750 |

**How to use the number**: The cost itself does not determine whether a meeting is worthwhile. A $30,000/year meeting that produces weekly alignment saving $100,000 in rework is a bargain. A $3,750/year 1:1 that produces no decisions or growth conversations is waste. The number makes the cost visible so the value can be assessed honestly.

### Hidden Costs Not in the Formula

| Cost | Impact |
|------|--------|
| **Context-switching** | 15-25 min before and after each meeting to context-switch. A 30-min meeting actually costs ~60-75 min. |
| **Fragmentation** | A meeting at 10:30am breaks a morning into two sub-90-min blocks, neither long enough for deep work. |
| **Preparation** | Time spent preparing for the meeting (reviewing docs, creating slides). |
| **Recovery** | Emotionally draining meetings (conflict, bad news) reduce productivity for hours afterward. |

---

## Recurring Meeting Optimization

### Audit Protocol for Recurring Meetings

For each recurring meeting, ask:

| Question | If the Answer Is No |
|----------|--------------------|
| Did this meeting produce a decision or action item in the last 3 occurrences? | Reduce frequency or cancel |
| Is every regular attendee actively participating? | Make passive attendees optional; send them notes |
| Could the meeting be 50% shorter with better preparation? | Create a pre-read requirement and shorten |
| Is the frequency right? | Weekly meetings where nothing changes week-to-week should be biweekly. Daily meetings where updates take 2 minutes should be async. |

### Frequency Decision Guide

| Signal | Current Frequency | Recommendation |
|--------|------------------|---------------|
| "Nothing new since last time" is common | Weekly | Move to biweekly |
| Updates take < 5 min, no discussion | Daily | Move to async check-in |
| Decisions pile up between meetings | Biweekly | Move to weekly, or allow ad-hoc decision meetings |
| Meeting consistently runs over time | Any | Either extend (with tighter agenda) or split into two focused meetings |
| Attendance is declining | Any | Purpose has eroded — re-audit with 5P framework |

---

## Action Item Capture

### During the Meeting

Designate one person (not the facilitator) to capture:
- **Decision**: What was decided, by whom, with what rationale
- **Action item**: What needs to happen, who owns it, by when
- **Open question**: What was not resolved, who will follow up

### Action Item Format

```
[ ] [Action verb] [specific deliverable] — Owner: [name] — Due: [date]
```

**Good**: "Draft the API migration plan with timeline and resource requirements — Owner: Sarah — Due: March 8"

**Weak**: "Sarah to look into the API thing" — No deliverable, no deadline, ambiguous scope.

### Post-Meeting Protocol

Within 30 minutes of meeting end:
1. Send notes to all attendees and relevant stakeholders
2. Action items added to the appropriate task tracking system
3. Decisions recorded in the relevant decision log or document

If this does not happen, the meeting's value dissipates within 24 hours as people's memories diverge.

---

## Meeting-Free Time Protection

### Why It Matters

Knowledge workers need 3-4 hours of uninterrupted time daily for deep work. A single meeting in the middle of a morning block reduces that block's productive output by 40-60% (because of context-switching overhead on both sides).

### Protection Strategies

| Strategy | Implementation | Tradeoff |
|----------|---------------|----------|
| **No-meeting mornings** | Block 9am-12pm on the team calendar. Meetings only after noon. | Works well for individual deep work. May conflict with cross-timezone collaboration. |
| **No-meeting days** | Designate one full day (often Wednesday or Friday) with zero meetings. | Highest deep work yield. Requires team-wide commitment. |
| **Focus blocks** | Each person blocks 2-3 hour chunks as "busy" and declines meetings during them. | Most flexible. Lowest compliance without cultural support. |
| **Meeting windows** | All meetings happen in designated windows (e.g., 1-5pm). | Clear structure. Limits scheduling flexibility. |

### Defending Focus Time

When someone requests a meeting during protected focus time:
1. Offer an alternative time within your meeting windows
2. Offer an async alternative ("Can I review the document and send comments by EOD instead?")
3. If neither works, accept the meeting but acknowledge the tradeoff: "I can attend, but this means [deliverable] moves to tomorrow."

Making the cost visible builds organizational awareness. Over time, people stop booking over focus time because they see the downstream impact.
