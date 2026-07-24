---
title: Vendor Management — Scorecard, Due Diligence, Contract Triggers, Performance Monitoring
domain: operations
level: 3
skill: operations
---

# Vendor Management Reference

> **Scope**: Operational vendor management lifecycle — evaluation scorecards, due diligence checklists, contract review triggers, and ongoing performance monitoring. Covers new vendor evaluation, renewal decisions, and vendor comparison. For strategic build-vs-buy decisions, see `skills/business/business-ops/references/vendor-evaluation.md`.
> **Generated**: 2026-05-05 — Vendor landscapes shift. Reassess scorecards annually and contracts at each renewal.

---

## Overview

Vendor management fails in three places. At selection: comparing feature lists instead of evaluating fitness for your specific context. At contracting: not reading the termination clause, the auto-renewal window, or the price escalation formula. At operation: not measuring performance until renewal, when it is too late to negotiate from strength.

This reference structures the vendor lifecycle so each phase produces artifacts that feed the next.

---

## Vendor Evaluation Scorecard

### Scoring Framework

Score each dimension 1-10 independently before discussing with stakeholders. Consensus-first scoring anchors to the loudest voice.

| Dimension | Weight | Score (1-10) | Scoring Guide |
|-----------|--------|-------------|---------------|
| Functional fit | 5x | ___ | Solves the actual problem without significant workarounds. 10 = drop-in fit. 1 = requires custom development. |
| Total cost of ownership | 4x | ___ | All-in cost over 3 years including hidden costs. 10 = predictable, within budget. 1 = unpredictable, escalating. |
| Integration complexity | 4x | ___ | Effort to connect to existing stack. 10 = <1 day. 1 = months of custom work. |
| Support quality | 3x | ___ | Response time, escalation path, resolution quality. 10 = dedicated support, <1h response. 1 = community forums only. |
| Security / compliance | 3x | ___ | Certifications match requirements. 10 = exceeds all requirements. 1 = no certifications, no audit reports. |
| Data portability | 3x | ___ | Can you export data in a usable format? 10 = full export, standard formats, API access. 1 = no export, proprietary format. |
| Company stability | 2x | ___ | Financial health, customer retention, market position. 10 = profitable, growing, established. 1 = pre-revenue, single investor. |
| Contract flexibility | 2x | ___ | Termination, pricing, scaling terms. 10 = month-to-month, no lock-in. 1 = multi-year, auto-renew, exit penalties. |
| **Weighted Total** | **26x** | **___/260** | |

**Interpretation:**
- 80%+ (208+): Strong fit. Proceed with contract negotiation.
- 60-79% (156-207): Acceptable with known gaps. Document gaps as contract conditions.
- 40-59% (104-155): Marginal. Only proceed if no better alternative exists.
- <40% (<104): Do not proceed. Gaps are structural, not negotiable.

### Comparison Matrix

When evaluating 2+ vendors side-by-side:

| Criterion | Vendor A | Vendor B | Vendor C | Winner |
|-----------|----------|----------|----------|--------|
| Functional fit | | | | |
| TCO (Year 3) | $___/yr | $___/yr | $___/yr | |
| Integration effort | ___days | ___days | ___days | |
| Support SLA | ___hr response | ___hr response | ___hr response | |
| Data export | [format] | [format] | [format] | |
| Contract term | ___months | ___months | ___months | |
| **Scorecard total** | ___/260 | ___/260 | ___/260 | |

---

## Total Cost of Ownership

### TCO Components

License price is not TCO. Calculate all-in cost.

| Component | Year 1 | Year 2 | Year 3 | Notes |
|-----------|--------|--------|--------|-------|
| License / subscription | $ | $ | $ | Per-seat, flat, usage-based? Price escalation clause? |
| Implementation | $ | — | — | Integration, data migration, configuration |
| Training | $ | $ | $ | Initial training + ongoing for new hires |
| Support / maintenance | $ | $ | $ | Included or add-on? Tier pricing? |
| Internal staff time | $ | $ | $ | Admin, maintenance, troubleshooting hours x loaded cost |
| Customization | $ | $ | $ | Custom development, API work, workflow adaptation |
| Infrastructure | $ | $ | $ | Additional hosting, storage, bandwidth |
| Compliance | $ | $ | $ | Audit costs, additional controls required |
| Exit costs | — | — | $ | Data migration, contract termination, replacement overlap |
| **Total** | **$** | **$** | **$** | |
| **Cumulative** | **$** | **$** | **$** | |

### Hidden Cost Checklist

Costs frequently missed in vendor evaluations:

- [ ] Price escalation at renewal (typical: 5-10% annual, often buried in terms)
- [ ] Overage charges for exceeding usage tiers
- [ ] Premium support tier required for production SLA
- [ ] Additional seats for admin/service accounts
- [ ] SSO/SAML as paid add-on (common in SaaS)
- [ ] API rate limits requiring paid upgrade
- [ ] Data storage beyond included allocation
- [ ] Professional services for initial setup
- [ ] Certification/compliance add-ons
- [ ] Currency fluctuation on non-USD contracts
- [ ] Opportunity cost of internal resources spent on vendor management
- [ ] Cost of vendor downtime to your operations (SLA credits rarely cover actual losses)

---

## Due Diligence Checklist

### Financial Stability

| Check | Source | Red Flag |
|-------|--------|----------|
| Funding / revenue status | Crunchbase, press releases, SEC filings | Runway <18 months. Revenue declining. Recent layoffs >20%. |
| Customer base size and diversity | Case studies, G2/Capterra, reference calls | <50 customers. Single-industry concentration. |
| Key customer concentration | Ask directly | >30% revenue from one customer (they leave, vendor is at risk) |
| Leadership stability | LinkedIn, press | C-suite turnover in last 12 months |
| Acquisition signals | Industry news, investor activity | Actively seeking acquisition (roadmap becomes irrelevant) |

### Security Posture

| Check | Source | Red Flag |
|-------|--------|----------|
| SOC 2 Type II report | Request directly | No report. Type I only. Report >12 months old. |
| Penetration test results | Request directly (summary) | Never conducted. Findings not remediated. Won't share summary. |
| Incident history | Public disclosures, news | Breach in last 24 months with poor response. |
| Data encryption | Technical documentation | No encryption at rest. No TLS in transit. Shared keys. |
| Access controls | Technical documentation, SOC 2 | No RBAC. No MFA for admin. Shared credentials. |
| Subprocessor list | DPA / privacy documentation | Unclear data handling chain. Subprocessors in restricted jurisdictions. |

### Contract and Legal

| Check | What to Look For | Red Flag |
|-------|-----------------|----------|
| Auto-renewal clause | Notice period, renewal terms | Auto-renew with <30-day cancellation window |
| Termination rights | For cause, for convenience, notice period | No termination for convenience. Excessive notice period. |
| Price escalation | Annual increase caps, CPI adjustments | Uncapped increases. No ceiling on usage-based pricing. |
| Data ownership | Who owns data created in the platform | Vendor claims rights to aggregated/derived data |
| Data portability | Export formats, migration support, timeline | No export. Proprietary format only. Charges for export. |
| SLA and remedies | Uptime guarantee, measurement, credits | SLA credits capped at <monthly fee. Measured monthly (hides daily outages). |
| Liability caps | Limitation of liability | Liability capped at 1x annual fees (inadequate for data loss) |
| Indemnification | IP infringement, data breach | No indemnification for breaches caused by vendor |
| Insurance | Cyber liability, E&O | No cyber liability insurance |

### Reference Checks

Do not accept only vendor-provided references. They are curated.

| Reference Type | Questions to Ask |
|---------------|-----------------|
| Vendor-provided (3 minimum) | What surprised you? What took longer than expected? Would you choose them again? |
| Self-sourced (find on G2, LinkedIn) | Why did you choose them? What are the real downsides? How is support when things break? |
| Churned customers (ask vendor who left) | Why did you leave? What was the exit process like? What would have kept you? |
| Similar-scale organizations | How does it perform at our scale? What breaks as you grow? |

---

## Contract Review Triggers

Events that should trigger a contract review outside the normal renewal cycle.

| Trigger | Action |
|---------|--------|
| Vendor acquired by another company | Review continuity, roadmap, pricing commitments. Prepare exit plan. |
| Major security incident at vendor | Assess exposure. Review incident response. Consider SLA implications. |
| Price increase >5% at renewal | Benchmark against alternatives. Negotiate or initiate RFP. |
| SLA breach (3+ in rolling 12 months) | Document pattern. Negotiate improved terms or credits. Evaluate alternatives. |
| Vendor layoffs >15% of workforce | Assess impact on support, roadmap, stability. Prepare contingency. |
| Your usage model changes significantly | Review pricing fit. May need different tier or different vendor. |
| Regulatory change affecting data handling | Review vendor compliance posture. Update DPA if needed. |
| Vendor changes terms unilaterally | Review impact. Exercise termination rights if material. |
| Key contact/champion at vendor leaves | Rebuild relationship. Assess organizational support depth. |
| Your team reports declining satisfaction | Survey users. Document specific issues. Use as negotiation leverage. |

---

## Performance Monitoring

### Vendor Performance Scorecard (Ongoing)

Review quarterly. Score 1-5 for each dimension.

| Dimension | Q1 | Q2 | Q3 | Q4 | Trend | Notes |
|-----------|----|----|----|----|-------|-------|
| Uptime / availability | | | | | | Measure against SLA |
| Support responsiveness | | | | | | Time to first response, time to resolution |
| Support quality | | | | | | Resolution rate, escalation frequency |
| Feature delivery | | | | | | Roadmap items delivered on time |
| Communication quality | | | | | | Proactive notification, transparency |
| Billing accuracy | | | | | | Invoice errors, unexpected charges |
| **Average** | | | | | | |

### SLA Tracking

```
## SLA Performance: [Vendor Name]

| SLA Metric | Committed | Actual | Status | Credit Due |
|-----------|-----------|--------|--------|------------|
| Uptime | 99.9% | ___% | Pass/Fail | $___  |
| Response time (P1) | 1 hour | ___hr | Pass/Fail | $___  |
| Response time (P2) | 4 hours | ___hr | Pass/Fail | $___  |
| Resolution time (P1) | 4 hours | ___hr | Pass/Fail | $___  |
| Resolution time (P2) | 24 hours | ___hr | Pass/Fail | $___  |
```

### Performance Review Meeting Agenda

Quarterly review with vendor account team:

1. **SLA review**: Performance against commitments. Credits owed.
2. **Support review**: Ticket volume, resolution quality, escalation patterns.
3. **Roadmap update**: Features delivered, upcoming features, timeline changes.
4. **Usage review**: Current vs. projected. Tier optimization opportunities.
5. **Issues log**: Open items from previous review. New issues.
6. **Relationship health**: Communication quality, responsiveness, partnership.
7. **Contract items**: Upcoming renewal, pricing discussion, term changes.

---

## Vendor Risk Assessment

### Concentration Risk

| Question | Threshold | Action if Exceeded |
|----------|-----------|-------------------|
| What % of a critical process depends on this vendor? | >80% | Document alternative. Create exit plan. |
| Can you operate for 48 hours without this vendor? | No | Create business continuity plan for vendor outage. |
| How long to migrate to an alternative? | >6 months | Begin evaluating alternatives now. Do not wait for crisis. |
| What data is locked in this vendor's platform? | Any critical data | Verify export capability. Test export quarterly. |

### Exit Planning

Every vendor relationship should have an exit plan. Not because you plan to leave, but because you might need to.

```
## Vendor Exit Plan: [Vendor Name]

### Trigger Criteria
- [What would cause us to exit: acquisition, breach, cost, performance]

### Data Migration
- **Data to export**: [What data, what format, what volume]
- **Export method**: [API, bulk export, manual, vendor-assisted]
- **Export tested**: [Yes/No — when last tested]
- **Migration target**: [Where data goes next]

### Replacement Options
| Option | Readiness | Migration Effort | Cost Delta |
|--------|-----------|-----------------|------------|
| [Vendor B] | Evaluated / Not evaluated | [weeks] | [+/-$X/yr] |
| [Build in-house] | Feasible / Not feasible | [weeks] | [+/-$X/yr] |
| [Manual process] | Temporary only | [immediate] | [+$X/yr in labor] |

### Contract Obligations
- **Notice period**: [X days]
- **Termination fee**: [$X]
- **Data deletion timeline**: [X days post-termination]

### Timeline
- **Best case**: [X weeks from decision to full migration]
- **Worst case**: [X weeks, accounting for data complexity and testing]
```

---

## Vendor Management Failure Modes

| Failure Mode | Symptom | Fix |
|-------------|---------|-----|
| Feature-list comparison | Choosing the vendor with the longest feature list | Score on fitness for your specific use case, not feature count |
| Ignoring exit costs | No exit plan until you need to leave | Build exit plan during evaluation. Test data export before signing. |
| Renewal surprise | Auto-renewed at higher price, nobody noticed | Calendar the renewal window -90 days. Review performance before renewal. |
| Single-threaded relationship | One person manages the vendor; they leave | Document vendor relationship. At least two people attend QBRs. |
| SLA credit neglect | Vendor misses SLA, nobody claims credits | Automate SLA tracking. File claims within contractual window. |
| Demo-driven evaluation | Chose based on the sales demo, not real testing | Require POC with your data, your integrations, your scale |
| Ignoring churned customers | Only spoke to vendor-curated references | Actively seek out customers who left. Their reasons are the real risks. |
| TCO = license price | Did not account for implementation, training, maintenance, exit | Use the full TCO template. Every component, every year. |
