# Task Management Reference

Deep reference for task decomposition, prioritization, state management, and batch processing. Loaded by TASK mode.

---

## Task Decomposition

### Vertical Slicing

Every task should represent a complete slice of value — something that delivers a result on its own, even if small.

| Slice Type | Test | Example |
|------------|------|---------|
| **Vertical (good)** | "If this is the only thing done today, does it deliver a result?" | "Write the intro section of the proposal and send for early feedback" |
| **Horizontal (split further)** | "Does this require other tasks to be useful?" | "Research competitors" — useful only when synthesized into something |

**Splitting technique**: Take any large task and ask "What is the smallest version that delivers a visible result?" Then do that version first.

| Before | After |
|--------|-------|
| "Redesign the dashboard" | "Replace the dashboard header with the new layout and ship it" |
| "Write the Q2 report" | "Draft the executive summary with key metrics and circulate for input" |
| "Migrate the database" | "Migrate the users table, validate row counts, update the read path" |

### Timeboxing Rules

| Bucket | Use For | If Over Budget |
|--------|---------|---------------|
| **1 hour** | Single-action tasks: reply, review, quick fix | Already right-sized |
| **2 hours** | Focused work: drafting, analysis, implementation | Check if it can split into two 1h tasks |
| **4 hours** | Deep work: design sessions, complex writing, architecture | Maximum single-task size. Split if larger. |
| **> 4 hours** | Decompose further | This is a project, not a task. Break into 1-4h subtasks with individual completion conditions. |

**Why these buckets**: Finer granularity (15-min, 30-min) creates false precision — estimation error on knowledge work is 50-200%. Coarser (half-day, full-day) loses planning value. The 1/2/4 system is precise enough to plan a day, loose enough to absorb variance.

---

## Priority Frameworks Applied

### Eisenhower Matrix (Personal Daily Use)

| | Urgent | Not Urgent |
|---|---|---|
| **Important** | **Do now.** Client deadline, production incident, blocking someone. | **Schedule.** Strategic work, skill building, relationship investment. This quadrant is where career growth lives. |
| **Not Important** | **Delegate or timebox.** Most email, many meetings, routine requests. Set a 30-min window, then stop. | **Drop.** Busywork, low-value notifications, meetings without agendas. Saying no here funds the Important/Not-Urgent quadrant. |

**The key insight**: Most people spend their day in Urgent (both rows). The difference between productive and busy is how much time goes to Important/Not-Urgent. Target: 30% of your day in that quadrant.

### ICE Scoring (Backlog Prioritization)

Score each item 1-10 on three dimensions:

| Dimension | 1-3 (Low) | 4-6 (Medium) | 7-10 (High) |
|-----------|-----------|--------------|-------------|
| **Impact** | Marginal improvement, few people affected | Noticeable improvement, moderate reach | Significant outcome, many people affected |
| **Confidence** | Gut feel, no supporting data | Some evidence, analogous experience | Data-backed, validated approach |
| **Ease** | Multi-week, many dependencies, new territory | Days to a week, known approach | Hours to a day, straightforward path |

**ICE Score** = Impact x Confidence x Ease. Sort descending. Do the high-score items first.

**Failure mode defense**: If you find yourself adjusting scores to justify a preferred item, stop. The score is showing you something. Investigate the mismatch between your intuition and the numbers — that gap contains information.

### Weighted Scoring (Team Decisions)

When the team needs transparent, defensible prioritization:

1. Choose 3-5 criteria relevant to your goals (e.g., revenue impact, user satisfaction, strategic alignment, effort, risk)
2. Assign weights that sum to 100% (force tradeoff: if everything is weighted equally, the weights carry no information)
3. Score each item 1-5 on each criterion
4. Weighted score = sum of (score x weight) across criteria

Present the table. Let the team discuss where scores diverge — that disagreement is the valuable part.

---

## Task State Machine

Every task lives in exactly one state:

```
CAPTURED → DEFINED → SCHEDULED → IN PROGRESS → DONE
                ↓          ↓            ↓
             DEFERRED   BLOCKED      DROPPED
                ↓          ↓
             (re-enter DEFINED when ready)
```

| State | Entry Condition | Exit Condition |
|-------|----------------|----------------|
| **CAPTURED** | Task exists in any form | Has action verb + completion condition + time estimate |
| **DEFINED** | Passes the clarity test (see below) | Assigned to a specific day or time block |
| **SCHEDULED** | On a specific day's plan | Work begins |
| **IN PROGRESS** | Active work happening | Completion condition met, or state change |
| **DONE** | Completion condition verified | Archive after 1 week |
| **DEFERRED** | Consciously postponed with a review date | Review date arrives → re-enter DEFINED |
| **BLOCKED** | Cannot proceed. Blocker identified with owner. | Blocker resolved → re-enter SCHEDULED |
| **DROPPED** | Deliberately abandoned with reason | Terminal state |

**Clarity test** (DEFINED entry gate): "Could someone else pick this up and know exactly what 'done' looks like?" If not, the task is still CAPTURED.

---

## Dependency Tracking

### Dependency Types

| Type | Example | Tracking Method |
|------|---------|----------------|
| **Blocking** | "Cannot start X until Y is done" | List blocker explicitly. Assign owner to unblock. |
| **Informing** | "X would benefit from Y's output, but can proceed without it" | Note the dependency. Start X; incorporate Y when available. |
| **External** | "Waiting on vendor response / approval / access" | Set a follow-up date. Escalate if no response by date. |

### Waiting-On Protocol

For every external dependency:
1. Document what you are waiting for, from whom, since when
2. Set a follow-up date (default: 3 business days)
3. On follow-up date: ping once. If no response in 24h, escalate or find an alternative path.
4. Carry the waiting item visibly — do not let it disappear into a backlog

---

## Batch Processing Patterns

### Context-Switching Cost

Switching between unrelated tasks costs 15-25 minutes of reorientation. Three switches in a morning can consume an hour of productive time.

**Mitigation**: Group similar tasks into batches and process them in dedicated windows.

| Batch Type | Tasks | Optimal Window |
|------------|-------|---------------|
| **Communication** | Email replies, Slack threads, review requests | 30-min blocks, 2-3x/day |
| **Review** | Code reviews, document reviews, PR feedback | Single 60-min block |
| **Creation** | Writing, design, coding, analysis | 90-120 min uninterrupted blocks |
| **Admin** | Expense reports, scheduling, tool setup | 30 min end-of-day |
| **Planning** | Task triage, calendar review, priority updates | 15 min start-of-day |

### Processing Rules

- Process batches in order of energy requirement: creation first (high energy), then review (medium), then communication and admin (low).
- Set a hard stop for each batch. Communication expands to fill available time — timebox it.
- When an item in a batch requires deep thought, pull it out and schedule it as its own deep work block. Do not let one complex item derail the batch.

---

## Task Extraction from Conversations

When processing meeting notes, chat threads, or email:

| Signal | Task Type | Example |
|--------|-----------|---------|
| "I'll..." / "I can..." | Commitment you made | "I'll send the updated numbers by Friday" → Task: Send updated numbers (due Friday) |
| "Can you..." / "Please..." | Request received | "Can you review the proposal?" → Task: Review proposal (owner: you) |
| "We should..." / "We need to..." | Team action item | "We should update the docs" → Task: Update docs (owner: TBD — clarify) |
| "Let's follow up on..." | Follow-up | "Let's follow up next week" → Task: Follow up on [topic] (due: next week) |
| Deadline mentioned | Deadline task | "The board meeting is March 15" → Task: Prepare board materials (due: March 13, 2-day buffer) |

**Extraction rule**: Surface extracted tasks for confirmation. Present them, ask which to add. Automatically adding tasks from ambiguous signals ("we should...") creates noise.
