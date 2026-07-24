---
title: Risk Assessment — Probability x Impact Matrix, Categories, Mitigation Planning, Residual Risk
domain: operations
level: 3
skill: operations
---

# Risk Assessment Reference

> **Scope**: Operational risk assessment for projects, processes, vendors, and changes. Covers the probability x impact scoring matrix, risk category taxonomy, mitigation planning with ownership, residual risk tracking, and compliance-adjacent risk management. Use when identifying, scoring, or mitigating operational risks. For strategic/CEO-level risk, see `skills/business/business-ops/references/risk-assessment.md`.
> **Generated**: 2026-05-05 — Risk assessments are time-sensitive. Reassess when conditions change, not on a fixed schedule alone.

---

## Overview

Risk assessment fails in two predictable ways. First: risks get identified but never scored, so everything is "High" and nothing is prioritized. Second: risks get scored but mitigations are vague ("monitor the situation"), so the risk register becomes documentation theater.

This reference enforces structured scoring with evidence requirements and mitigation specificity. A risk rated "Low" without rationale is as suspicious as a risk rated "High" — both need justification.

---

## Probability x Impact Matrix

### The Matrix

|  | **Negligible Impact** | **Minor Impact** | **Moderate Impact** | **Major Impact** | **Severe Impact** |
|---|---|---|---|---|---|
| **Almost Certain (>90%)** | Medium | High | High | Critical | Critical |
| **Likely (60-90%)** | Low | Medium | High | High | Critical |
| **Possible (30-60%)** | Low | Medium | Medium | High | High |
| **Unlikely (10-30%)** | Low | Low | Medium | Medium | High |
| **Rare (<10%)** | Low | Low | Low | Medium | Medium |

### Probability Scoring Guide

Do not guess. Score based on evidence.

| Rating | Probability | Evidence Required |
|--------|------------|-------------------|
| Almost Certain | >90% | Has happened multiple times. Current conditions make recurrence near-guaranteed. |
| Likely | 60-90% | Has happened before in similar circumstances. Contributing factors are present. |
| Possible | 30-60% | Could happen. Some contributing factors exist. No direct precedent but plausible scenario. |
| Unlikely | 10-30% | Theoretically possible but few contributing factors present. Has not happened here. |
| Rare | <10% | Requires multiple simultaneous failures or unprecedented conditions. |

**Scoring discipline**: "It hasn't happened yet" does NOT justify "Rare." Ask: "What would need to be true for this to happen?" If the answer involves conditions that currently exist, move the probability up.

### Impact Scoring Guide

Quantify impact in at least one measurable dimension.

| Rating | Financial | Operational | Reputational | Compliance |
|--------|-----------|------------|--------------|------------|
| Severe | >$1M loss or >20% revenue impact | Complete service outage >24h. Data loss. | National media coverage. Customer exodus. | License revocation. Criminal liability. |
| Major | $100K-$1M loss or 5-20% revenue | Service degraded >4h. Significant data exposure. | Industry press coverage. Key customer loss. | Regulatory fine. Formal investigation. |
| Moderate | $10K-$100K loss or 1-5% revenue | Service degraded 1-4h. Limited data exposure. | Customer complaints. Social media attention. | Audit finding. Remediation required. |
| Minor | $1K-$10K loss or <1% revenue | Brief disruption <1h. No data loss. | Internal complaints. No external visibility. | Minor non-conformance. Self-remediated. |
| Negligible | <$1K loss | Inconvenience only. No service impact. | No visibility. | Documentation gap only. |

Adjust thresholds to your organization's scale. A $10K loss is "Negligible" for a Fortune 500 and "Major" for a 10-person startup.

---

## Risk Categories

### Category Taxonomy

| Category | Subcategories | Example Risks |
|----------|--------------|---------------|
| **Operational** | Process, People, Systems, Suppliers | Key-person dependency. Single point of failure in infrastructure. Manual process error rate. |
| **Financial** | Budget, Revenue, Cost, Liquidity | Vendor price escalation beyond budget. Project cost overrun. Revenue shortfall from delay. |
| **Compliance** | Regulatory, Contractual, Internal Policy | GDPR data handling violation. Missed SLA triggering penalty. Audit finding with remediation deadline. |
| **Strategic** | Market, Competition, Technology, Timing | Technology shift making current stack obsolete. Competitor launch. Market contraction. |
| **Reputational** | Customer, Partner, Public, Employee | Data breach notification. Service outage during peak. Public security incident. |
| **Security** | Data, Access, Infrastructure, Third-Party | Unauthorized access via compromised vendor. Unpatched vulnerability exploited. Credential leak. |

### Risk Identification by Category

Structured prompts to systematically find risks. Work through each applicable category.

**Operational Risks:**
- What happens if person X is unavailable for 4 weeks?
- Which systems have no redundancy?
- Which manual processes have the highest error rate?
- What vendor dependencies have no fallback?
- What happens during peak load?

**Financial Risks:**
- What costs are variable and could spike?
- What revenue assumptions could be wrong?
- What happens if a key customer churns?
- Where are we locked into pricing that could change?
- What is the cost of a 3-month delay?

**Compliance Risks:**
- What regulations apply and when was last audit?
- Which controls are documented but not tested?
- What data crosses jurisdictional boundaries?
- What contractual SLAs are we close to breaching?
- When do certifications expire?

**Security Risks:**
- What third parties have access to our data?
- When was the last penetration test?
- What happens if credentials leak?
- Which systems lack audit logging?
- What is the mean time to detect an intrusion?

---

## Risk Register Template

### Individual Risk Entry

```
### Risk: [ID] — [Short Title]

**Category**: [Operational | Financial | Compliance | Strategic | Reputational | Security]
**Description**: [What could happen — specific, not generic]
**Trigger**: [What event or condition would cause this risk to materialize]
**Probability**: [Almost Certain | Likely | Possible | Unlikely | Rare] — [Evidence/rationale]
**Impact**: [Severe | Major | Moderate | Minor | Negligible] — [Quantified: $X, Y hours downtime, Z users affected]
**Risk Level**: [Critical | High | Medium | Low] — derived from matrix
**Owner**: [Named person, not "the team"]
**Status**: [Open | Mitigating | Mitigated | Accepted | Closed]

**Mitigation Plan**:
1. [Specific action] — [Owner] — [Due date]
2. [Specific action] — [Owner] — [Due date]

**Residual Risk After Mitigation**: [Level] — [Why this level is acceptable]
**Review Date**: [When to reassess this risk]
```

### Summary Risk Register Table

```
| ID | Risk | Category | Prob | Impact | Level | Owner | Status | Mitigation | Residual |
|----|------|----------|------|--------|-------|-------|--------|------------|----------|
| R-001 | [Title] | Operational | Likely | Major | High | [Name] | Open | [Summary] | Medium |
| R-002 | [Title] | Financial | Possible | Moderate | Medium | [Name] | Mitigating | [Summary] | Low |
| R-003 | [Title] | Security | Unlikely | Severe | High | [Name] | Open | [Summary] | Medium |
```

---

## Mitigation Planning

### Mitigation Strategy Types

| Strategy | When to Use | Example |
|----------|------------|---------|
| **Avoid** | Eliminate the risk by not doing the activity | Cancel the vendor integration that introduces compliance exposure |
| **Reduce** | Lower probability or impact | Add redundancy to eliminate single point of failure |
| **Transfer** | Shift risk to another party | Insurance, SLA penalties, contractual indemnification |
| **Accept** | Consciously decide to carry the risk | Low-impact risk where mitigation cost exceeds potential loss |
| **Share** | Distribute risk across parties | Joint venture, consortium, shared infrastructure |

### Mitigation Quality Test

A mitigation is specific and actionable or it is not a mitigation.

| Bad Mitigation | Good Mitigation | Why |
|---------------|----------------|-----|
| "Monitor the situation" | "Set up PagerDuty alert for error rate >5%. Assign to on-call. Review weekly in ops standup." | Observable. Measurable. Owned. |
| "Improve documentation" | "Write runbook for database failover by 2026-06-01. Assign to J. Smith. Validate via tabletop exercise." | Specific deliverable. Due date. Validation method. |
| "Train the team" | "Schedule 2-hour hands-on session for all on-call engineers by Q3. Test with simulation. Track completion." | Specific format. Audience. Deadline. Verification. |
| "Reduce dependency" | "Implement read replica by 2026-07-15 to eliminate single DB dependency. Test failover monthly." | Concrete action. Timeline. Ongoing validation. |
| "Be more careful" | NOT a mitigation | Behavior-based mitigations do not survive 3am incidents |

### Mitigation Tracking

For each mitigation:

| Field | Required | Description |
|-------|----------|-------------|
| Action | Yes | Specific deliverable or change |
| Owner | Yes | Named person (not team or role) |
| Due date | Yes | Calendar date, not "next quarter" |
| Status | Yes | Not Started / In Progress / Complete / Overdue |
| Verification | Yes | How to confirm the mitigation is working |
| Effectiveness review | Yes | Date to assess whether the mitigation actually reduced risk |

---

## Residual Risk Tracking

### What Is Residual Risk?

Residual risk = risk that remains after mitigations are applied. Every mitigation reduces risk; none eliminates it entirely.

```
Initial Risk Level: High (Likely x Major)
Mitigation: Add read replica; implement automated failover
Residual Risk Level: Medium (Unlikely x Major)
Rationale: Failover eliminates single-point-of-failure. Impact unchanged 
  because any DB outage during failover still causes brief disruption.
Acceptance: Medium is within risk appetite. Reviewed by [Name] on [Date].
```

### Residual Risk Decision Framework

| Residual Level | Action Required |
|---------------|----------------|
| Critical | Unacceptable. Additional mitigations required. Escalate to leadership. |
| High | Requires explicit acceptance by risk owner's manager. Document rationale. |
| Medium | Acceptable with monitoring. Define review cadence (monthly or quarterly). |
| Low | Acceptable. Review annually or when conditions change. |

### Risk Appetite Statement

Define organizational risk appetite before assessing. Without it, every risk assessment is subjective.

```
## Risk Appetite

**Overall posture**: [Risk-averse | Balanced | Risk-tolerant]

**By category**:
| Category | Appetite | Rationale |
|----------|----------|-----------|
| Operational | Balanced | Accept calculated risks to move faster |
| Financial | Risk-averse | Protect cash flow; avoid commitments >$X without board approval |
| Compliance | Zero tolerance | Regulatory violations are existential |
| Security | Risk-averse | Data breaches have outsized reputational impact |
| Strategic | Risk-tolerant | Market position requires calculated bets |
```

---

## Compliance-Adjacent Risk Management

### Mapping Risks to Controls

When risks overlap with compliance requirements, map them to the applicable control framework.

| Risk | Compliance Framework | Control | Evidence Required |
|------|---------------------|---------|-------------------|
| Unauthorized data access | SOC 2 CC6.1 | Role-based access control | Access review logs, quarterly access recertification |
| Data loss | ISO 27001 A.12.3 | Backup and recovery | Backup logs, restore test results |
| Unpatched vulnerability | PCI DSS 6.2 | Patch management | Scan reports, patch deployment records |
| Insider threat | SOC 2 CC6.3 | Separation of duties | Role matrix, approval logs |

### Audit Evidence for Risk Management

Maintain evidence that risk management is active, not just documented.

| Evidence Type | What It Proves | Collection Frequency |
|--------------|----------------|---------------------|
| Risk register with dates | Risks are tracked over time | Updated per event + quarterly review |
| Mitigation status updates | Mitigations are progressing | Monthly |
| Residual risk reviews | Risk acceptance is deliberate | Quarterly |
| Incident-to-risk mapping | Incidents trigger risk reassessment | Per incident |
| Risk appetite review | Appetite is current, not stale | Annually |

---

## Risk Assessment Failure Modes

| Failure Mode | Symptom | Fix |
|-------------|---------|-----|
| Everything is High | No prioritization possible | Force-rank: at most 20% of risks can be High/Critical. The rest need differentiation. |
| Optimism bias | Probability consistently underestimated | For each "Low" probability: name the evidence. "Has not happened" requires "and here is why it cannot." |
| Impact without numbers | "High impact" with no quantification | Require at least one measurable dimension: dollars, hours, users, SLA. |
| Orphan mitigations | Mitigations with no owner or due date | No mitigation without owner + date. Ownerless mitigations do not exist. |
| Risk register as artifact | Created once, never updated | Schedule quarterly reviews. Trigger reviews on incidents. Mark register with last-reviewed date. |
| Treating issues as risks | Conflating current problems with future risks | Issues are happening now (action items). Risks might happen (mitigation plans). Separate them. |
| Copy-paste risks | Generic risks not tailored to context | Every risk must reference the specific project, system, or decision. "Data breach" is not a risk. "Unauthorized access to customer PII via compromised vendor API key" is. |
| Mitigation theater | "Monitor the situation" as a mitigation | Mitigations must be verifiable. If you cannot test whether the mitigation is working, it is not a mitigation. |
