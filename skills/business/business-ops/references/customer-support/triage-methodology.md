# Triage Methodology

Deep reference for ticket triage: category taxonomy, priority scoring, SLA mapping, routing rules, duplicate detection, escalation triggers, and auto-response templates.

---

## Category Taxonomy

Every ticket gets a **primary category** and optionally a **secondary category**. Root cause drives the category, not the symptom described.

| Category | Description | Signal Words |
|----------|-------------|-------------|
| **Bug** | Product behaving incorrectly or unexpectedly | Error, broken, crash, not working, unexpected, wrong, failing |
| **How-to** | Customer needs guidance on using the product | How do I, can I, where is, setting up, configure, help with |
| **Feature request** | Customer wants capability that doesn't exist | Would be great if, wish I could, any plans to, requesting |
| **Billing** | Payment, subscription, invoice, pricing | Charge, invoice, payment, subscription, refund, upgrade, downgrade |
| **Account** | Access, permissions, settings, user management | Login, password, access, permission, SSO, locked out, can't sign in |
| **Integration** | Third-party tools, APIs, webhooks | API, webhook, integration, connect, OAuth, sync, third-party |
| **Security** | Security concerns, data access, compliance | Data breach, unauthorized, compliance, GDPR, SOC 2, vulnerability |
| **Data** | Data quality, migration, import/export | Missing data, export, import, migration, incorrect data, duplicates |
| **Performance** | Speed, reliability, availability | Slow, timeout, latency, down, unavailable, degraded |

### Category Disambiguation Rules

| Symptom | Category | Reasoning |
|---------|----------|-----------|
| Bug AND feature request in same ticket | Bug (primary) | Bugs take priority -- investigate before dismissing |
| Can't log in due to a bug | Bug, not Account | Root cause drives category |
| "It used to work and now it doesn't" | Bug | Regression signal |
| "I want it to work differently" | Feature request | Enhancement signal |
| "How do I make it work?" | How-to | Guidance signal |
| Unclear whether bug or user error | Bug | Err toward investigation over dismissal |

---

## Priority Framework

### P1 -- Critical

**Criteria**: Production system down, data loss/corruption, security breach, all or most users affected.

Indicators:
- Customer cannot use the product at all
- Data being lost, corrupted, or exposed
- Security incident in progress
- Issue worsening or expanding in scope

**SLA**:
- Respond: 1 hour
- Work pattern: continuous until resolved or mitigated
- Update cadence: every 1-2 hours

### P2 -- High

**Criteria**: Major feature broken, significant workflow blocked, many users affected, no workaround.

Indicators:
- Core workflow broken but product partially usable
- Multiple users affected or key account impacted
- Blocking time-sensitive work
- No reasonable workaround

**SLA**:
- Respond: 4 hours
- Work pattern: active investigation same day
- Update cadence: every 4 hours

### P3 -- Medium

**Criteria**: Feature partially broken, workaround available, single user or small team affected.

Indicators:
- Feature not working correctly but workaround exists
- Inconvenient but not blocking critical work
- Single user or small team affected
- Customer not escalating urgently

**SLA**:
- Respond: 1 business day
- Resolution or update: 3 business days

### P4 -- Low

**Criteria**: Minor inconvenience, cosmetic issue, general question, feature request.

Indicators:
- Cosmetic or UI issues not affecting functionality
- Feature requests and enhancement ideas
- General questions or how-to inquiries
- Issues with simple, documented solutions

**SLA**:
- Respond: 2 business days
- Resolution: normal pace

### Priority Bump Triggers

Automatically escalate priority when:

| Trigger | Action |
|---------|--------|
| Customer waiting longer than SLA | Bump one level |
| Multiple customers report same issue | Bump to at least P2 |
| Customer explicitly escalates or mentions executives | Bump one level |
| Workaround stops working | Bump one level |
| Issue expands in scope (more users, data, symptoms) | Reassess from scratch |
| Revenue at risk (churn signal, contract renewal) | Bump to at least P2 |

---

## Routing Rules

| Route to | When | Expected Action |
|----------|------|-----------------|
| **Tier 1** (frontline) | How-to questions, known issues with documented solutions, billing inquiries, password resets | Resolve using KB, templates, standard procedures |
| **Tier 2** (senior) | Bugs requiring investigation, complex configuration, integration troubleshooting, account issues needing elevated access | Deep investigation, advanced troubleshooting, cross-team coordination |
| **Engineering** | Confirmed bugs needing code fixes, infrastructure issues, performance degradation | Root cause analysis, code fix, deploy |
| **Product** | Feature requests with significant demand, design decisions, workflow gaps | Prioritization decision, roadmap consideration |
| **Security** | Data access concerns, vulnerability reports, compliance questions | Immediate assessment, containment if needed |
| **Billing/Finance** | Refund requests, contract disputes, complex billing adjustments | Account adjustment, approval workflow |

### Routing Complexity Signals

Route to Tier 2+ when:
- Issue requires access the frontline agent doesn't have
- Troubleshooting has exceeded 3 back-and-forth exchanges without resolution
- Issue involves custom configuration or non-standard setup
- Customer is a high-value account (enterprise, high ARR)
- Issue crosses product areas or teams

---

## Duplicate Detection Process

Before routing, check for duplicates:

1. **Search by symptom**: similar error messages or descriptions in open tickets
2. **Search by customer**: does this customer have an open ticket for the same issue
3. **Search by product area**: recent tickets in the same feature area
4. **Check known issues**: compare against documented known issues list

### When Duplicate Found

| Scenario | Action |
|----------|--------|
| Exact duplicate from same customer | Merge into existing ticket, notify customer |
| Same issue, different customer | Link tickets, bump priority if pattern emerging (3+ = escalate the pattern) |
| Similar but different root cause | Create new ticket, reference related ticket in notes |
| Resolved duplicate exists | Check if resolution applies, link for context |

---

## Escalation Trigger Matrix

These conditions should trigger escalation regardless of initial triage assessment:

| Signal | Escalation Target | Urgency |
|--------|-------------------|---------|
| "We're considering switching to [competitor]" | Leadership + Account team | High |
| "This is a security/compliance issue" | Security team | Critical |
| "Our CEO / VP / CTO wants to talk to someone" | Leadership | High |
| 3+ customers report identical issue in 24h | Engineering + Leadership | High |
| Customer has been waiting > 2x SLA | Manager review | Medium |
| Data loss or corruption confirmed | Engineering | Critical |
| Customer references contract terms or legal | Legal + Leadership | High |
| Issue blocks go-live or launch | Engineering + Account team | Critical |

---

## Auto-Response Templates by Category

### Bug -- Initial Response

```
Thank you for reporting this. I can see how [specific impact]
would be disruptive for your work.

I've logged this as a [priority] issue and our team is
investigating. [If workaround: "In the meantime, you can
[workaround]."]

I'll update you within [SLA timeframe] with what we find.
```

### How-to -- Initial Response

```
Great question. [Direct answer or link to documentation]

[If multi-step: "Here's how to do this:"]
[Steps or guidance]

Let me know if that helps or if you have follow-up questions.
```

### Feature Request -- Initial Response

```
Thank you for this suggestion -- I can see why [capability]
would be valuable for your workflow.

I've documented this and shared it with our product team.
I can't commit to a specific timeline, but your feedback
directly informs our roadmap priorities.

[If alternative exists: "In the meantime, you might find
[alternative] helpful for achieving something similar."]
```

### Billing -- Initial Response

```
I understand billing issues need prompt attention. Let me
look into this.

[If straightforward: resolution details]
[If complex: "I'm reviewing your account now and will have
an answer for you within [timeframe]."]
```

### Security -- Initial Response

```
Thank you for flagging this -- we take security concerns
seriously and are reviewing this immediately.

I've escalated to our security team for investigation.
We'll follow up within [timeframe] with our findings.

[If action needed: "In the meantime, we recommend
[protective action]."]
```

### Account -- Initial Response

```
I can see you're having trouble accessing your account.
Let me help sort this out.

[If quick fix: resolution steps]
[If investigation needed: "I'm looking into this now and
will update you within [timeframe]."]

[If security-adjacent: "For your account's security, I may
need to verify some details before making changes."]
```

---

## Triage Output Template

Every triage produces this structured output:

```
## Triage: [One-line issue summary]

**Category:** [Primary] / [Secondary if applicable]
**Priority:** [P1-P4] -- [Brief justification]
**Product area:** [Area/team]

### Issue Summary
[2-3 sentence summary of what the customer is experiencing]

### Key Details
- **Customer:** [Name/account if known]
- **Impact:** [Who and what is affected]
- **Workaround:** [Available / Not available / Unknown]
- **Related tickets:** [Links to similar issues if found]
- **Known issue:** [Yes -- link / No / Checking]

### Routing Recommendation
**Route to:** [Team or queue]
**Why:** [Brief reasoning]

### Suggested Initial Response
[Draft first response to the customer]

### Internal Notes
- [Additional context for the agent picking this up]
- [Reproduction hints if it's a bug]
- [Escalation triggers to watch for]
```

---

## Triage Failure Modes

| Failure Mode | Problem | Correct Approach |
|-------------|---------|-----------------|
| Categorizing by symptom instead of root cause | Misroutes ticket, delays resolution | Investigate root cause before categorizing |
| Defaulting everything to P3 | Under-serves critical issues, over-serves low ones | Apply priority criteria honestly, err high when uncertain |
| Skipping duplicate check | Creates redundant work, fragments context | Always search before routing |
| Writing vague internal notes | Next agent wastes time re-investigating | Include what you checked, what you ruled out, what to try next |
| Routing to engineering without repro steps | Engineers send it back, customer waits longer | Reproduce or document what you tried before escalating |
| Dismissing "feature request" that's actually a bug | Customer feels unheard, real issue persists | "It used to work" = bug, not feature request |
