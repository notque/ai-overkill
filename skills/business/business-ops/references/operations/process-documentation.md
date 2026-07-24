---
title: Process Documentation — Mapping, RACI, Bottleneck Analysis, Optimization
domain: operations
level: 3
skill: operations
---

# Process Documentation Reference

> **Scope**: Business process documentation from capture through optimization. Covers process mapping techniques, RACI matrix construction and enforcement, bottleneck analysis methodology, and process optimization frameworks. Use when documenting existing processes, building SOPs, identifying inefficiencies, or planning capacity.
> **Generated**: 2026-05-05 — Processes drift. Review SOPs quarterly or when incidents reveal the documented process diverges from reality.

---

## Overview

Process documentation fails for one reason: it describes how the process should work instead of how it actually works. The idealized version lives in a wiki nobody reads. The real process — with its workarounds, exceptions, and tribal knowledge — lives in people's heads. When those people leave, the process leaves with them.

Document reality first. Optimize second. A perfect SOP for a process nobody follows is worse than a messy SOP that matches what people actually do.

---

## Process Mapping

### Capture Methodology

Start by interviewing the people who do the work. Not their managers. Not the original process designer. The people who run it today.

**Questions to ask:**

| Question | What It Reveals |
|----------|----------------|
| "Walk me through the last time you did this." | The actual process, not the idealized version |
| "What do you do differently when [exception]?" | Edge cases that break the documented flow |
| "Where do you usually get stuck or wait?" | Bottlenecks and handoff failures |
| "What do you wish someone had told you when you started?" | Tribal knowledge that should be documented |
| "What step do you sometimes skip? What happens?" | Process steps that may be unnecessary or poorly designed |
| "Who do you go to when something goes wrong?" | Undocumented escalation paths |
| "What tools do you use that aren't in the official process?" | Shadow IT and workarounds |

### Process Map Components

Every process map must include:

| Component | Description | Example |
|-----------|-------------|---------|
| **Trigger** | What initiates the process | Customer submits ticket. End of month. Alert fires. |
| **Steps** | Sequential actions with decision points | Triage, assign, investigate, resolve, verify, close |
| **Decision points** | Binary branches in the flow | Severity > P2? Yes -> escalate. No -> standard queue. |
| **Handoffs** | Where work moves between people/teams | Triage team -> assigned engineer |
| **Inputs** | What each step needs to start | Ticket details, access credentials, runbook |
| **Outputs** | What each step produces | Diagnosis, fix, verification result, resolution note |
| **Exceptions** | What happens outside the normal flow | Customer escalates. Duplicate ticket. Known issue. |
| **Timing** | How long each step typically takes | Triage: 5min. Investigation: 15min-4hr. Resolution: varies. |
| **Roles** | Who performs each step | L1 support, on-call engineer, team lead |

### ASCII Process Flow Template

For text-based documentation:

```
[Trigger] -> [Step 1] -> <Decision?> --Yes--> [Step 2a] -> [Step 3]
                              |
                              No
                              |
                              v
                         [Step 2b] -> [Step 3]

[Step 3] -> <Verification?> --Pass--> [Step 4: Close]
                  |
                  Fail
                  |
                  v
             [Step 3: Rework] -> <Verification?> ...
```

### Multi-Swim-Lane Template

For processes crossing teams:

```
| Team A          | Team B          | Team C          |
|-----------------|-----------------|-----------------|
| [Request]       |                 |                 |
|       |         |                 |                 |
|       v         |                 |                 |
| [Triage] ------>| [Assign]        |                 |
|                 |       |         |                 |
|                 |       v         |                 |
|                 | [Investigate]   |                 |
|                 |       |         |                 |
|                 | <Escalate?> --->| [Review]        |
|                 |       |         |       |         |
|                 |      No         |       v         |
|                 |       v         | [Approve/Deny]  |
|                 | [Resolve]  <----|       |         |
|                 |       |         |                 |
| [Notify] <------| [Close]         |                 |
```

---

## RACI Matrix

### RACI Definitions

| Role | Definition | Rule |
|------|-----------|------|
| **R** — Responsible | Does the work | At least one per step. Can be multiple people. |
| **A** — Accountable | Owns the outcome. Makes the final call. | Exactly ONE per step. This is non-negotiable. |
| **C** — Consulted | Provides input before the work is done | Two-way communication. Keep this list short. |
| **I** — Informed | Notified after the work is done | One-way communication. Can be broad. |

### RACI Construction Rules

1. **One A per step.** If two people are accountable, nobody is. This is the most violated rule and the most important.
2. **R without A = work without ownership.** Every R needs an A above it who cares if it gets done.
3. **A without R = accountability without capability.** The accountable person must have authority over the responsible person.
4. **Too many Cs = slow process.** Every C is a person who must be consulted before proceeding. Each one adds latency.
5. **Too many Rs = diffused responsibility.** If everyone is responsible, nobody feels ownership.

### RACI Template

```
## RACI Matrix: [Process Name]

| Step | Team Lead | Engineer | QA | PM | Support | Ops |
|------|-----------|----------|----|----|---------|-----|
| 1. Receive request | I | | | R | A | |
| 2. Triage and prioritize | C | | | A | R | |
| 3. Assign work | | R | | A | I | |
| 4. Execute | | R | C | A | | I |
| 5. Review/QA | | C | R | A | | |
| 6. Deploy | | R | | I | | A |
| 7. Verify in production | | C | R | I | | A |
| 8. Close and notify | I | | | | R | A |
```

### RACI Validation Checklist

- [ ] Every step has exactly one A
- [ ] Every step has at least one R
- [ ] No person is both R and A on the same step (unless team of one)
- [ ] C count per step is ≤3 (more than 3 = bottleneck)
- [ ] No person is A on >50% of steps (overloaded decision-maker)
- [ ] Every R has a named person or role, not "TBD"
- [ ] The A for each step can actually make decisions (has authority)
- [ ] I recipients have a defined notification method

---

## SOP Template

### Standard Operating Procedure Structure

```
## Process: [Name]
**Owner**: [Person/Team — the single accountable party for this process]
**Last Updated**: [YYYY-MM-DD]
**Review Cadence**: [Quarterly / Semi-annually / Annually]
**Version**: [X.Y]

### Purpose
[One paragraph: why this process exists, what problem it solves, what outcome it produces]

### Scope
- **Included**: [What this process covers]
- **Excluded**: [What this process does NOT cover — prevent scope creep]
- **Related processes**: [Links to upstream/downstream processes]

### Trigger
[What initiates this process: event, schedule, request, threshold]

### Prerequisites
- [Access/permissions required]
- [Tools/systems required]
- [Data/inputs required]
- [Training/certification required]

### RACI Matrix
[See RACI section above]

### Procedure

#### Step 1: [Name]
- **Who**: [Role]
- **When**: [Trigger or timing relative to previous step]
- **Input**: [What this step needs]
- **Action**: [Exact instructions — specific enough for someone unfamiliar]
- **Output**: [What this step produces]
- **Duration**: [Typical time: "5-10 minutes"]
- **Exception**: [What to do if it does not go as expected]

#### Step 2: [Name]
[Same structure]

### Exceptions and Edge Cases
| Scenario | Frequency | Handling |
|----------|-----------|---------|
| [Exception] | [Common/Rare] | [What to do] |

### Metrics
| Metric | Target | Measurement Method | Review Cadence |
|--------|--------|--------------------|----------------|
| Cycle time | [Target] | [How to measure] | [Weekly/Monthly] |
| Error rate | [Target] | [How to measure] | [Weekly/Monthly] |
| Throughput | [Target] | [How to measure] | [Weekly/Monthly] |

### History
| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | [Date] | [Name] | Initial version |
```

---

## Bottleneck Analysis

### Identifying Bottlenecks

A bottleneck is the step that constrains the throughput of the entire process. Improving any other step does not increase overall throughput until the bottleneck is resolved.

**Detection methods:**

| Method | How | Signal |
|--------|-----|--------|
| Queue length | Measure work-in-progress before each step | Longest queue = bottleneck |
| Wait time | Measure time between step completion and next step start | Longest wait = handoff bottleneck |
| Utilization | Measure how busy each role/resource is | >90% utilization = capacity bottleneck |
| Rework rate | Measure how often each step's output is rejected | Highest rework = quality bottleneck |
| Dependency count | Count how many steps must complete before this step can start | Most dependencies = coordination bottleneck |

### Bottleneck Classification

| Type | Cause | Example | Fix Approach |
|------|-------|---------|-------------|
| **Capacity** | Not enough people/resources | One reviewer for all code reviews | Add capacity, parallelize, batch |
| **Handoff** | Work stalls between teams | Dev-to-QA handoff takes 2 days average | Reduce handoffs, co-locate, automate handoff |
| **Approval** | Waiting for sign-off | Every change needs VP approval | Delegate authority, batch approvals, set SLAs |
| **Information** | Missing data blocks progress | Can't start without spec that's always late | Pull information upstream, provide templates, set deadlines |
| **Skill** | Only one person can do this step | Only Alice knows the billing system | Cross-train, document, reduce specialization dependency |
| **Tool** | Tooling is slow or manual | Manual data entry between systems | Automate, integrate, replace tool |

### Bottleneck Analysis Template

```
## Bottleneck Analysis: [Process Name]
**Date**: [YYYY-MM-DD]
**Analyst**: [Name]

### Process Metrics
| Step | Avg Duration | Wait Before | Queue Depth | Rework Rate | Resource Utilization |
|------|-------------|-------------|-------------|-------------|---------------------|
| [Step 1] | [time] | [time] | [count] | [%] | [%] |
| [Step 2] | [time] | [time] | [count] | [%] | [%] |

### Identified Bottlenecks (ranked by impact)
1. **[Step/Handoff]**: [Type] bottleneck
   - Evidence: [What data shows this is the constraint]
   - Impact: [How much this slows the overall process]
   - Root cause: [Why this step is constrained]
   - Recommendation: [Specific fix]
   - Estimated improvement: [Time/throughput gain]

### Constraint Chain
[Sometimes fixing bottleneck #1 reveals bottleneck #2 was always there]
Current: Step 3 (capacity) -> Step 5 (approval) -> Step 7 (skill)
After fixing Step 3: Step 5 becomes the new constraint
```

---

## Process Optimization

### Waste Identification Framework

Based on lean methodology, adapted for knowledge work.

| Waste Type | Definition | Knowledge Work Examples | Detection |
|-----------|-----------|------------------------|-----------|
| **Waiting** | Time spent idle, in queues, or blocked | Waiting for approval. Waiting for spec. Waiting for environment. | Measure queue time between steps. |
| **Rework** | Doing work that was already done (due to defects) | Bug found in production. Spec changed after implementation. | Count iterations per work item. |
| **Handoffs** | Transferring work between people/teams | Dev to QA. Support to engineering. Design to development. | Count handoffs per process. Each one = context loss. |
| **Over-processing** | Doing more work than necessary | Detailed report nobody reads. Three levels of approval for minor changes. | Ask: "What happens if we skip this step?" |
| **Motion** | Unnecessary movement/switching | Context-switching between tasks. Navigating between tools. | Count tool switches and context changes per task. |
| **Inventory** | Work-in-progress that is not moving | 50 open tickets, 30 untouched for 2+ weeks. | Count WIP. If WIP > throughput × cycle time, you have inventory waste. |
| **Overproduction** | Making more than needed or before needed | Building features nobody requested. Creating reports in advance. | Track feature usage. Track report readership. |

### Optimization Strategies

| Strategy | When to Use | Example |
|----------|------------|---------|
| **Eliminate** | Step adds no value | Remove approval step for changes under $500 |
| **Automate** | Step is deterministic and repetitive | Auto-assign tickets based on component tags |
| **Parallelize** | Independent steps run sequentially | Run security review and code review simultaneously |
| **Simplify** | Step is more complex than necessary | Replace 5-page change request with structured form |
| **Combine** | Multiple steps could be one | Merge triage and assignment into single step |
| **Batch** | Small items processed one-at-a-time inefficiently | Batch minor approvals into daily review |
| **Shift left** | Defects found late, expensive to fix | Add linting to pre-commit hooks instead of code review |

### Before/After Comparison Template

```
## Process Optimization: [Name]

### Current State
- Total steps: [N]
- Total cycle time: [X hours/days]
- Handoffs: [N]
- Approval gates: [N]
- Known pain points: [List]

### Proposed Changes
| Change | Type | Step Affected | Expected Impact |
|--------|------|--------------|-----------------|
| [Change] | Eliminate/Automate/etc. | Step [N] | Save [X] time per cycle |

### Future State
- Total steps: [N] (was [N])
- Total cycle time: [X] (was [X])
- Handoffs: [N] (was [N])
- Approval gates: [N] (was [N])

### Impact Summary
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Cycle time | [X] | [X] | [X]% faster |
| Error rate | [X]% | [X]% | [X]% reduction |
| Cost per cycle | $[X] | $[X] | $[X] saved |
| Throughput | [X]/week | [X]/week | [X]% increase |

### Implementation Plan
| Phase | Action | Owner | Timeline |
|-------|--------|-------|----------|
| 1 | [Quick win] | [Name] | [Date] |
| 2 | [Medium effort] | [Name] | [Date] |
| 3 | [Longer-term] | [Name] | [Date] |
```

---

## Capacity Planning Integration

### Resource-to-Process Mapping

When processes are documented, map resource consumption for capacity planning.

| Process | Frequency | Duration | Roles Required | Peak Load |
|---------|-----------|----------|---------------|-----------|
| [Process A] | Daily | 2hr | 1 engineer, 1 PM | Month-end |
| [Process B] | Weekly | 4hr | 2 engineers | Q4 |
| [Process C] | On-demand | 1hr avg | 1 support | After releases |

### Utilization Impact Analysis

When optimizing a process, quantify the capacity freed:

```
Current: Process takes 4hr/week from senior engineer (10% utilization)
Optimized: Process takes 1hr/week (2.5% utilization)
Freed: 3hr/week = 7.5% capacity returned to project work
Annual value: 3hr × 48 weeks × $75/hr loaded cost = $10,800
```

---

## Process Documentation Failure Modes

| Failure Mode | Symptom | Fix |
|-------------|---------|-----|
| Aspirational documentation | SOP describes how it should work, not how it does | Interview practitioners. Document current state first. Optimize second. |
| RACI with multiple As | Two people "accountable" per step | Enforce one A per step. Resolve ownership disputes before documenting. |
| Exception-free processes | No edge case handling documented | Ask "What do you do when X goes wrong?" for every step. |
| Orphan SOPs | Created once, never updated, nobody reads it | Embed process docs in the workflow (linked from tickets, dashboards). Review cadence enforced. |
| Over-documented | 50-page SOP for a 5-step process | Match documentation depth to process complexity. Runbooks for ops. SOPs for business processes. |
| Documenting tools, not outcomes | "Click the blue button, then the green button" | Document what to accomplish, not how to navigate a UI (UIs change). |
| No metrics | Process documented but no way to know if it works | Every SOP needs at least one measurable metric with a target. |
| Copy-paste SOPs | Same template filled identically for different processes | Each process has unique exceptions, timing, and failure modes. Generic templates produce generic docs. |
