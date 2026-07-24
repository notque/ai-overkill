# LLM Failure Modes in Productivity Work

Where LLMs systematically fail at productivity tasks. Loaded across all modes as a guardrail reference.

> **Shared base**: Universal LLM failure modes (hallucination, overconfidence, generic output, arithmetic errors, stale knowledge) are documented in `skills/shared-patterns/llm-domain-failure-modes-base.md`. This file covers productivity-specific failures only.

---

## Why This File Exists

LLMs are optimistic planners and fluent generators. Both traits are dangerous in productivity work. An aspirational daily plan looks motivating until it collides with a real calendar. A task list without time estimates feels productive until nothing gets prioritized. Generic advice sounds wise until it fails to adapt to a specific person's constraints.

This reference catalogs the specific failure modes, their signatures, and the defenses against each.

---

## Failure Mode 1: Aspirational Planning

### What Happens

The LLM generates a daily or weekly plan that ignores real constraints: existing calendar commitments, energy fluctuations, commute time, meal breaks, transition costs between tasks. The plan assumes 8 hours of peak-energy productive time. The user follows it for 2 hours, falls behind, and abandons the plan entirely.

### Signatures

| Signal | Example |
|--------|---------|
| No calendar awareness | Plan schedules 4 hours of deep work when 3 hours of meetings are already booked |
| No buffer time | Back-to-back blocks with zero transition time |
| Peak energy all day | Creative work scheduled for 4pm as if it is the same as 9am |
| 100% utilization | Every minute planned, leaving zero room for unplanned work |
| Aspirational task count | 12 items on a daily plan when 3-5 is realistic |

### Defenses

| Defense | Implementation |
|---------|---------------|
| Calendar-first planning | Start with the calendar. Build the plan around committed time, not on top of it. |
| Buffer mandate | Minimum 15-minute buffer between blocks. Minimum 20% of day unplanned. |
| Energy-aware scheduling | Ask about energy patterns. Schedule hard work during peak energy, routine work during recovery. |
| Task count ceiling | Daily plans have a maximum of 3 Top priority items. Plans with more than 3 priorities have zero priorities. |
| Utilization cap | Plan for 5-6 productive hours, not 8. The remaining time absorbs meetings, transitions, and surprises. |

---

## Failure Mode 2: Unestimated Task Lists

### What Happens

The LLM produces a beautifully organized task list with categories, priorities, and descriptions — but no time estimates. Without estimates, the user cannot plan a day around the list. They pick tasks by gut feel, run out of time, and carry tasks forward indefinitely. The list grows. Morale shrinks.

### Signatures

| Signal | Example |
|--------|---------|
| No time estimates | Tasks listed with titles and descriptions only |
| No priority markers | All tasks appear equally important |
| No completion conditions | "Research competitors" — when is this done? |
| Infinite list | 40+ items with no triage or grouping |
| No distinction between quick and deep | A 5-minute email reply next to a 4-hour architecture doc |

### Defenses

| Defense | Implementation |
|---------|---------------|
| Mandatory estimates | Every task gets a time bucket: 1h, 2h, or 4h. Tasks under 1h batch together. Tasks over 4h decompose. |
| Completion conditions | Every task has a "done when" clause. "Research competitors" becomes "Write a 1-page comparison of the top 3 competitors' pricing models." |
| Priority assignment | Use Eisenhower (personal) or ICE (backlog). Unprioritized lists are incomplete. |
| List ceiling | Active task list stays under 15 items. Anything beyond goes to a backlog or "someday" list. If you cannot maintain 15 active items, you cannot maintain 40. |
| Size visibility | When presenting a task list, include total estimated hours. "This list totals 28 hours — that is roughly 5 days of focused work." |

---

## Failure Mode 3: Generic Productivity Advice

### What Happens

The LLM dispenses widely-known productivity tips without adapting them to the user's specific situation. "Try the Pomodoro technique." "Use the Eisenhower matrix." "Eat the frog — do the hardest thing first." This advice is correct in general and useless in particular.

### Signatures

| Signal | Example |
|--------|---------|
| Named techniques without adaptation | "Have you tried the Pomodoro technique?" without knowing the user's work involves 3-hour deep coding sessions that Pomodoro would fragment |
| One-size-fits-all | Same advice for a manager with 6 hours of meetings and an IC with 6 hours of deep work |
| Technique-dropping | Mentioning 5 techniques without applying any to the user's specific situation |
| Context-free tips | "Block time for deep work" without knowing the user's calendar or team culture |
| Book recommendations instead of solutions | "Check out Getting Things Done!" when the user asked for help planning their Tuesday |

### Defenses

| Defense | Implementation |
|---------|---------------|
| Context-first | Gather the user's actual constraints (calendar, role, energy patterns, team size, meeting load) before recommending anything. |
| Apply, do not recommend | Instead of "use the Eisenhower matrix," take their actual tasks and sort them into the matrix. Show the result, not the technique name. |
| Adapt to role | A manager's productivity system (meeting optimization, delegation, decision velocity) is fundamentally different from an IC's (focus protection, batch processing, deep work blocks). |
| One recommendation at a time | Pick the single highest-leverage change for this person and implement it. Five tips is an article. One implemented change is progress. |
| Test against specifics | Before giving advice, check: "Does this recommendation account for [specific constraint the user mentioned]?" If not, revise it. |

---

## Failure Mode 4: Meeting Agendas Without Decision Outcomes

### What Happens

The LLM creates a meeting agenda that lists topics to discuss but does not specify what decisions the meeting should produce. The result is a well-organized meeting that covers three topics, generates discussion, and concludes without anyone knowing what was decided or what happens next.

### Signatures

| Signal | Example |
|--------|---------|
| Topic-only agenda | "1. Discuss Q2 roadmap. 2. Review hiring plan. 3. Budget update." — what decisions? |
| No time allocations | Topics listed without time budgets, so item 1 consumes 50 minutes of a 60-minute meeting |
| No item types | Discussion items, decision items, and information items all treated identically |
| No pre-read | Attendees arrive cold. The first 15 minutes are context-setting that should have happened async. |
| No defined outcome | "Agenda" is really a topic list. After the meeting, there is no artifact. |

### Defenses

| Defense | Implementation |
|---------|---------------|
| Item typing | Every agenda item is labeled: Decision, Discussion, Information, or Brainstorm. Different types need different facilitation. |
| Outcome definition | Each item has a "done when" statement. "Q2 roadmap — done when top 3 priorities are rank-ordered and each has an owner." |
| Time allocation | Each item gets allocated minutes that sum to the meeting duration minus 5 minutes (for wrap-up). |
| Pre-read requirement | Information-heavy items have pre-read materials distributed 24h before. Meeting time is for questions and decisions, not presentations. |
| Action item capture | Designate a note-taker. Decisions and action items captured during the meeting with owners and deadlines. |

---

## Failure Mode 5: Task-List Reviews

### What Happens

The LLM produces a "weekly review" that is just a task list with checkmarks. What was done. What was not done. Move undone items to next week. This is task management, not review. There is no reflection, no pattern identification, no adjustment to the system. The same failures repeat week after week.

### Signatures

| Signal | Example |
|--------|---------|
| Done/Not-done only | "Completed 7 of 12 tasks. Carrying 5 forward." No analysis of why. |
| No planned vs actual comparison | Tasks listed without comparing to what was originally planned |
| No pattern identification | The same type of task gets deferred every week and nobody notices |
| No systemic questions | Review does not ask "why do I consistently overcommit?" or "why does admin work always expand?" |
| Carryover without examination | Tasks moved forward every week for a month with no examination of whether they matter |

### Defenses

| Defense | Implementation |
|---------|---------------|
| Planned vs actual comparison | Show what was planned for the week alongside what actually happened. The gap is the data. |
| Pattern questions | Ask: What type of work consistently gets deferred? Where did unplanned work come from? Which commitments to others were met vs missed? |
| Carryover limit | A task that carries forward 3+ times gets one of: decompose (too big), escalate (blocked), drop (not actually important). Indefinite carryover is not allowed — it creates a guilt backlog that drains energy. |
| Adjustment mandate | Every review produces 1-2 specific, testable adjustments. "Block Tuesday morning for deep work" not "do more deep work." |
| Metrics tracking | Track completion rate, carryover count, unplanned work ratio, deep work hours. Trends over 4+ weeks reveal systemic issues that single-week reviews miss. |

---

## Failure Mode 6: Activity-Based Status Updates

### What Happens

The LLM writes status updates framed as activities ("worked on", "spent time", "had meetings about") rather than outcomes ("shipped", "decided", "unblocked"). Activity framing signals effort. Outcome framing signals impact. Stakeholders receiving activity-based updates cannot tell if the project is progressing or just consuming time.

### Signatures

| Signal | Example |
|--------|---------|
| Activity verbs | "Worked on search feature" instead of "Shipped search indexing — queries 40% faster" |
| No measurable progress | "Continued integration work" — are we 30% done or 90% done? |
| Meeting attendance as progress | "Met with design team about the new flow" — what was decided? |
| No blockers surfaced | Everything sounds on track even when it is not |
| No decisions needed | Status update does not ask the reader for anything — purely informational |

### Defenses

| Defense | Implementation |
|---------|---------------|
| Outcome verb requirement | Use "shipped", "decided", "unblocked", "measured", "validated" instead of "worked on", "discussed", "continued" |
| Measurable progress | Include percentage, count, or milestone: "3 of 5 API endpoints migrated. On track for completion Wednesday." |
| Decision surfacing | Every update includes decisions made (for the record) and decisions needed (for the reader to act on) |
| Honest risk reporting | Status colors reflect reality. If it is yellow, say yellow. Early warnings preserve trust. Late surprises destroy it. |
| Ask inclusion | Status updates that do not ask the reader for anything are FYIs, not updates. If no action is needed, say so explicitly — that is itself useful information. |

---

## Cross-Cutting Defense: The Specificity Test

Across all failure modes, the root cause is the same: the LLM generates plausible, well-structured output that lacks specificity. The defense is to check every recommendation, plan, and task against the person's actual situation.

**Before delivering any productivity artifact, verify**:

1. **Calendar test**: Does this plan account for the real calendar, not an imaginary free day?
2. **Energy test**: Does this schedule match the person's stated or likely energy patterns?
3. **Estimate test**: Does every task have a time estimate and a completion condition?
4. **Adaptation test**: Would this recommendation change if the person's role, schedule, or team size were different? If not, it is probably generic.
5. **Actionability test**: Can the person start on this within the next 24 hours? If not, it is aspirational.
6. **Carryover test**: Are deferred tasks examined for patterns, or just moved forward?
7. **Outcome test**: Are results framed as outcomes (impact) or activities (effort)?

If any test fails, revise the artifact before delivering. Productive-looking output that does not survive contact with a real calendar is worse than no output — it consumes the user's time to produce and their trust when it fails.
