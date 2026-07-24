---
title: Change Management — Request Workflows, Impact Assessment, Communication, Rollback
domain: operations
level: 3
skill: operations
---

# Change Management Reference

> **Scope**: Operational change management for system, process, and organizational changes. Covers change request workflows, impact assessment matrices, stakeholder communication planning, and rollback criteria definition. Use when proposing changes that need approval, documenting impact, planning communication, or defining rollback procedures.
> **Generated**: 2026-05-05 — Change management frameworks should be reviewed annually or when organizational change volume significantly shifts.

---

## Overview

Change management fails at three points. First: impact is underestimated because the assessment only considers the primary system, not downstream dependencies. Second: communication is an afterthought — people learn about the change when it breaks their workflow. Third: rollback is an optimistic sentence instead of a tested procedure.

Every change request is a contract: "Here is what will happen, who it affects, how we will tell them, and what we do if it goes wrong." If any section is vague, the contract is incomplete.

---

## Change Request Workflow

### Change Classification

Classify the change before selecting the workflow. Over-classifying wastes time. Under-classifying misses risks.

| Class | Criteria | Approval Path | Lead Time |
|-------|----------|---------------|-----------|
| **Standard** | Pre-approved, low-risk, routine | Auto-approved per policy | Same day |
| **Normal** | Moderate risk, planned, reversible | Manager + change owner | 5+ business days |
| **Major** | High risk, broad impact, or irreversible | Change Advisory Board (CAB) | 10+ business days |
| **Emergency** | Unplanned, required to restore service | Post-hoc approval within 48h | Immediate |

### Classification Decision Tree

```
Is this change pre-approved and routine?
  Yes -> STANDARD (auto-approve)
  No  -> Does it affect production systems?
           No  -> NORMAL (manager approval)
           Yes -> Is it reversible within 1 hour?
                    Yes -> How many users affected?
                             <50  -> NORMAL
                             50+  -> MAJOR
                    No  -> MAJOR

Is this an emergency to restore service?
  Yes -> EMERGENCY (implement now, approve within 48h)
```

### Change Request Template

```
## Change Request: [CR-XXXX] [Title]

### Metadata
| Field | Value |
|-------|-------|
| Requester | [Name] |
| Date submitted | [YYYY-MM-DD] |
| Classification | Standard / Normal / Major / Emergency |
| Priority | Critical / High / Medium / Low |
| Status | Draft / Submitted / Approved / In Progress / Completed / Rolled Back |
| Implementation window | [Date + time range] |

### Description
**What is changing**: [Specific technical or process change]
**Why**: [Business justification — the problem being solved or opportunity being captured]
**What happens if we don't**: [Risk of inaction — establishes urgency]

### Impact Assessment
[See Impact Assessment section below]

### Risk Assessment
[See Risk Assessment reference — load references/operations/risk-assessment.md]

### Implementation Plan
[See Implementation Plan section below]

### Communication Plan
[See Stakeholder Communication section below]

### Rollback Plan
[See Rollback Criteria section below]

### Approvals
| Approver | Role | Decision | Date |
|----------|------|----------|------|
| [Name] | [Role] | Pending / Approved / Rejected | |
```

---

## Impact Assessment

### Impact Dimensions

Assess each dimension independently. Rate High / Medium / Low / None.

| Dimension | High | Medium | Low | None |
|-----------|------|--------|-----|------|
| **Users** | >100 users change daily workflow | 20-100 users, minor workflow change | <20 users, minimal change | No user-facing change |
| **Systems** | Multiple production systems modified | Single production system modified | Non-production system only | No system changes |
| **Processes** | Core business process changes | Supporting process changes | Documentation-only changes | No process changes |
| **Data** | Schema change, data migration, format change | New data fields, optional changes | Read-only access changes | No data impact |
| **Security** | Access control, authentication, encryption changes | Permission scope changes | Audit logging changes | No security impact |
| **Cost** | >$50K budget impact | $5K-$50K budget impact | <$5K budget impact | No budget impact |
| **Compliance** | Regulatory or audit-relevant changes | Policy updates | Documentation updates | No compliance impact |

### Impact Assessment Template

```
## Impact Assessment: [CR-XXXX]

| Area | Rating | Details | Affected Parties |
|------|--------|---------|-----------------|
| Users | [H/M/L/N] | [Specific impact description] | [Who specifically] |
| Systems | [H/M/L/N] | [Which systems, how] | [System owners] |
| Processes | [H/M/L/N] | [Which processes change] | [Process owners] |
| Data | [H/M/L/N] | [What data changes] | [Data owners] |
| Security | [H/M/L/N] | [What controls affected] | [Security team] |
| Cost | [H/M/L/N] | [Budget impact] | [Budget owner] |
| Compliance | [H/M/L/N] | [Regulatory implications] | [Compliance team] |

### Dependencies
| This change depends on | Status |
|----------------------|--------|
| [Prerequisite change/system/team] | [Ready / Not ready / Blocked] |

### Downstream Effects
| What depends on this change | Impact if delayed |
|----------------------------|-------------------|
| [Downstream system/process/team] | [Consequence] |
```

### Dependency Mapping

Changes rarely exist in isolation. Map what this change depends on and what depends on this change.

```
[Upstream Change A] ----\
                         \
[Upstream Change B] -------> [THIS CHANGE] -------> [Downstream System X]
                         /                    \
[Prerequisite C] -------/                      \---> [Downstream Process Y]
```

Questions to ask:
- What must be complete BEFORE this change?
- What breaks if this change is delayed?
- What other changes are happening in the same window?
- Which teams need to coordinate?

---

## Stakeholder Communication

### Communication Planning Matrix

For each stakeholder group, define what, when, how, and who.

| Audience | What They Need to Know | Channel | Timing | Owner | Message Type |
|----------|----------------------|---------|--------|-------|-------------|
| **Directly affected users** | What changes, what to do differently, where to get help | Email + team meeting | 2 weeks before | Change owner | Detailed instructions |
| **Indirectly affected teams** | What is changing, potential impact on their work | Email + Slack | 1 week before | Change owner | Summary + FAQ |
| **Leadership/sponsors** | Status, risks, go/no-go decision | Status report | Per approval cycle | Change owner | Executive summary |
| **Support/helpdesk** | What to expect, how to troubleshoot, escalation path | Training session + runbook | 1 week before | Support lead | Operational guide |
| **External customers** | What changes for them, timeline, support contact | Email / in-app notification | Per SLA/contract | Comms team | Customer-facing notice |

### Communication Principles

1. **Explain WHY before WHAT.** People accept change better when they understand the reason. "We are migrating databases" meets resistance. "The current database cannot handle peak load, which caused the outage last month. We are migrating to a system that handles 10x the traffic" gets buy-in.

2. **Communicate early.** Surprises create resistance. Previews create buy-in. Even incomplete information ("We are planning a change to X. Details coming next week.") is better than silence followed by disruption.

3. **Acknowledge what is being lost.** Every change removes something familiar. Saying "this is an improvement" while ignoring that people's workflows are disrupted is tone-deaf. "We know the current system is familiar, and this change will require adjusting your daily routine for a few weeks" builds trust.

4. **Be specific about impact.** "Everyone will be affected" is not a communication. "The 200 users in the billing team will need to learn the new approval workflow. Training sessions are scheduled for June 3-5." is a communication.

5. **Provide a path for questions.** Announce and disappear = anxiety. Announce with a FAQ, a Slack channel, a drop-in session, and a named contact = manageable change.

### Communication Timeline Template

```
## Communication Timeline: [CR-XXXX]

| When | What | Audience | Channel | Owner | Status |
|------|------|----------|---------|-------|--------|
| T-30 days | Preview announcement | All stakeholders | Email | [Name] | |
| T-14 days | Detailed notification | Affected users | Email + meeting | [Name] | |
| T-7 days | Training session | Affected users | Workshop | [Name] | |
| T-3 days | Final reminder | Affected users | Slack + email | [Name] | |
| T-0 (go-live) | Go-live announcement | All | Slack | [Name] | |
| T+1 day | Status update | All stakeholders | Email | [Name] | |
| T+7 days | Feedback survey | Affected users | Survey | [Name] | |
| T+30 days | Adoption report | Leadership | Status report | [Name] | |
```

### Resistance Management

| Resistance Pattern | Cause | Response |
|-------------------|-------|----------|
| "This was fine before" | Comfort with status quo | Quantify the problem the change solves. Show data. |
| "Nobody asked us" | Lack of involvement | Include resistors in design review. Give them influence. |
| "This is more work" | Change increases short-term effort | Acknowledge the transition cost. Show long-term benefit. Provide support. |
| "It won't work here" | Past failed changes eroded trust | Address specific concerns. Start with pilot group. Show early results. |
| Passive non-adoption | Silent disagreement | Track adoption metrics. Follow up individually with non-adopters. |
| Active undermining | Deep disagreement or threatened role | Address privately. Understand root concern. Escalate if persistent. |

---

## Implementation Planning

### Implementation Plan Template

```
## Implementation Plan: [CR-XXXX]

### Pre-Implementation
| Step | Owner | When | Dependencies | Verification |
|------|-------|------|--------------|-------------|
| [Backup/snapshot] | [Name] | T-1h | None | Backup confirmed |
| [Stakeholder notification] | [Name] | T-1h | None | Sent |
| [Monitoring dashboards open] | [Name] | T-15min | None | URLs loaded |

### Implementation Steps
| # | Step | Owner | Expected Duration | Expected Result | Failure Action |
|---|------|-------|-------------------|-----------------|----------------|
| 1 | [Action] | [Name] | [Xmin] | [Observable result] | [What to do] |
| 2 | [Action] | [Name] | [Xmin] | [Observable result] | [What to do] |
| 3 | [Action] | [Name] | [Xmin] | [Observable result] | [What to do] |

### Post-Implementation
| Step | Owner | When | Verification |
|------|-------|------|-------------|
| [Verify service health] | [Name] | T+15min | [Health check passes] |
| [Monitor for 30 minutes] | [Name] | T+30min | [No new alerts] |
| [Notify stakeholders: complete] | [Name] | T+30min | [Message sent] |
| [Close maintenance window] | [Name] | T+1h | [Window closed] |
```

### Go/No-Go Checklist

Run before implementation begins. All items must pass.

```
## Go/No-Go Checklist: [CR-XXXX]

### Go Criteria (all must be YES)
- [ ] All approvals obtained
- [ ] Implementation team available and briefed
- [ ] Rollback procedure reviewed and understood
- [ ] Backups/snapshots taken and verified
- [ ] Monitoring and alerting configured
- [ ] Communication sent to affected parties
- [ ] Maintenance window confirmed (if applicable)
- [ ] No conflicting changes in the same window
- [ ] Support/on-call team briefed on the change

### No-Go Criteria (any one triggers postpone)
- [ ] Outstanding unresolved risks rated High or Critical
- [ ] Key implementation team member unavailable
- [ ] Dependent upstream change not yet complete
- [ ] Production incident in progress
- [ ] Insufficient time remaining in maintenance window
```

---

## Rollback Criteria and Procedures

### When to Roll Back

Define trigger criteria BEFORE implementation. During an incident is too late to debate.

| Trigger Type | Example | Action |
|-------------|---------|--------|
| **Hard trigger** (automatic rollback) | Error rate >5% for 5 minutes | Roll back immediately. No discussion. |
| **Soft trigger** (evaluate, then decide) | Performance degraded 20% but stable | Assess. Roll back if not improving within 30 minutes. |
| **Time-based** | Change not verified within maintenance window | Roll back. Reschedule. |
| **User-reported** | >10 user reports of the same issue | Assess severity. Roll back if user-facing impact confirmed. |

### Rollback Plan Template

```
## Rollback Plan: [CR-XXXX]

### Decision Authority
- **Who can authorize rollback**: [Name/Role]
- **Automatic rollback triggers**: [List hard triggers]
- **Escalation if unsure**: [Contact]

### Rollback Steps
| # | Step | Command/Action | Expected Result | Duration |
|---|------|---------------|-----------------|----------|
| 1 | [Undo step N] | [Exact action] | [Expected state] | [Xmin] |
| 2 | [Undo step N-1] | [Exact action] | [Expected state] | [Xmin] |
| 3 | [Verify restoration] | [Check command] | [Normal state confirmed] | [Xmin] |

### Total Rollback Time: [X minutes]

### Post-Rollback
- [ ] Verify system returned to pre-change state
- [ ] Notify stakeholders: "Change [CR-XXXX] rolled back. [Reason]. No data loss."
- [ ] Create incident record if applicable
- [ ] Schedule post-mortem within 48 hours
- [ ] Update change request status to "Rolled Back"

### Non-Reversible Components
| Component | Why Non-Reversible | Compensating Action |
|-----------|-------------------|---------------------|
| [Component] | [Reason] | [What to do instead] |
```

### Rollback Testing

Rollback procedures must be tested before the change. An untested rollback is a hope, not a plan.

| Test Method | When to Use |
|------------|------------|
| Full rehearsal in staging | Major changes with complex rollback |
| Tabletop walkthrough | Normal changes with straightforward rollback |
| Automated rollback test | Standard changes with scripted rollback |
| Documented from prior experience | Emergency changes (tested post-hoc if time permits) |

---

## Change Management Failure Modes

| Failure Mode | Symptom | Fix |
|-------------|---------|-----|
| Classification avoidance | Everything is "Standard" to skip approval | Audit classification decisions. Auto-escalate when impact assessment contradicts classification. |
| Communication as afterthought | Users discover changes by encountering them | Communication plan is a required section. No approval without it. |
| Vague rollback | "Undo the changes" | Rollback must have exact steps, expected results, and tested procedure. |
| Ignoring downstream | Only assessed impact on primary system | Dependency mapping is required. Ask: "What depends on this?" |
| Emergency abuse | "Emergency" classification to bypass approval | Track emergency frequency. If >20% of changes are emergency, the process or the system has problems. |
| No post-implementation review | Change completed, nobody checks if it worked | Require verification within 24 hours. Track success rate. |
| Change collision | Multiple changes in same window, failure attribution impossible | Maintain change calendar. No overlapping changes on same system. |
| Resistance dismissed | "People will get used to it" | Resistance is signal. Track adoption. Follow up with non-adopters. Adjust. |
