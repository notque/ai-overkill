# Legal Risk Assessment Framework

Structured methodology for identifying, scoring, classifying, and documenting legal risks. Severity x Likelihood matrix with escalation criteria and business impact scoring.

---

## Risk Scoring Model

### Severity Scale

| Level | Label | Description | Financial Exposure | Operational Impact |
|-------|-------|-------------|-------------------|-------------------|
| 1 | **Negligible** | Minor inconvenience, no material impact | < 0.1% of contract/deal value | None. Normal operations. |
| 2 | **Low** | Limited impact, minor disruption | < 1% of relevant value | Minor disruption, easily absorbed |
| 3 | **Moderate** | Meaningful impact, noticeable disruption | 1-5% of relevant value | Noticeable disruption, potential limited public attention |
| 4 | **High** | Significant impact, regulatory scrutiny likely | 5-25% of relevant value | Significant disruption, likely public attention, potential regulatory action |
| 5 | **Critical** | Severe impact, fundamental business threat | > 25% of relevant value | Business disruption, reputational damage, regulatory action likely, potential personal liability |

### Likelihood Scale

| Level | Label | Description | Precedent | Triggering Events |
|-------|-------|-------------|-----------|-------------------|
| 1 | **Remote** | Highly unlikely | No known precedent in similar situations | Would require exceptional circumstances |
| 2 | **Unlikely** | Could occur but not expected | Limited precedent | Would require specific triggering events |
| 3 | **Possible** | May occur | Some precedent exists | Triggering events are foreseeable |
| 4 | **Likely** | Probably will occur | Clear precedent | Triggering events are common |
| 5 | **Almost Certain** | Expected to occur | Strong precedent or pattern | Triggering events are present or imminent |

### Risk Matrix

```
                    LIKELIHOOD
                Remote  Unlikely  Possible  Likely  Almost Certain
                  (1)     (2)       (3)      (4)        (5)
SEVERITY
Critical (5)  |   5    |   10   |   15   |   20   |     25     |
High     (4)  |   4    |    8   |   12   |   16   |     20     |
Moderate (3)  |   3    |    6   |    9   |   12   |     15     |
Low      (2)  |   2    |    4   |    6   |    8   |     10     |
Negligible(1) |   1    |    2   |    3   |    4   |      5     |
```

**Risk Score = Severity x Likelihood**

---

## Risk Classification and Response

### GREEN -- Low Risk (Score 1-4)

**Characteristics:**
- Minor issues unlikely to materialize
- Standard business risks within normal parameters
- Well-understood risks with established mitigations

**Response protocol:**
- Accept and proceed with standard controls
- Document in risk register
- Monitor quarterly or annually
- No escalation required

**Examples:**
- Vendor contract with minor deviation in non-critical area
- Routine NDA with known counterparty in standard jurisdiction
- Administrative compliance task with clear deadline and owner

---

### YELLOW -- Medium Risk (Score 5-9)

**Characteristics:**
- Moderate issues that could materialize under foreseeable circumstances
- Warrant attention but not immediate action
- Established management precedent exists

**Response protocol:**
- Implement specific controls or negotiate to reduce exposure
- Assign a single owner responsible for monitoring and mitigation
- Review monthly or as trigger events occur
- Document risk, mitigations, and rationale thoroughly
- Brief relevant business stakeholders
- Define trigger events that would elevate the risk level

**Examples:**
- Contract with LOL cap below standard but within negotiable range
- Vendor processing personal data in jurisdiction without clear adequacy determination
- Regulatory development that may affect business activity in medium term
- IP provision broader than preferred but common in market

---

### ORANGE -- High Risk (Score 10-15)

**Characteristics:**
- Significant issues with meaningful probability of materializing
- Could result in substantial financial, operational, or reputational impact
- Requires senior attention and dedicated mitigation

**Response protocol:**
- Escalate to senior counsel (head of legal or designated senior)
- Develop specific, actionable mitigation plan
- Brief business leadership
- Review weekly or at defined milestones
- Consider outside counsel engagement
- Full risk memo with analysis, options, recommendations
- Define contingency plan (what if risk materializes?)

**Examples:**
- Contract with uncapped indemnification in material area
- Data processing activity potentially violating regulatory requirements
- Threatened litigation from significant counterparty
- IP infringement allegation with colorable basis
- Regulatory inquiry or audit request

---

### RED -- Critical Risk (Score 16-25)

**Characteristics:**
- Severe issues likely or certain to materialize
- Could fundamentally impact the business, officers, or stakeholders
- Requires immediate executive attention

**Response protocol:**
- Immediate escalation to General Counsel, C-suite, Board as appropriate
- Engage outside counsel immediately
- Establish dedicated response team with clear roles
- Consider insurance notification
- Activate crisis management protocols if reputational risk involved
- Implement litigation hold if legal proceedings possible
- Daily or more frequent review until resolved or reduced
- Include in board risk reporting
- Make any required regulatory notifications

**Examples:**
- Active litigation with significant exposure
- Data breach affecting regulated personal data
- Regulatory enforcement action
- Material contract breach (by or against the organization)
- Government investigation
- Credible IP infringement claim against core product/service

---

## Escalation Decision Tree

```
Is there active litigation or government investigation?
├── YES → RED. Engage outside counsel immediately.
└── NO → Continue.

Could the risk result in criminal liability?
├── YES → RED. Engage criminal defense counsel.
└── NO → Continue.

Does the risk involve regulated personal data (breach, non-compliance)?
├── YES → Is there a notification deadline?
│   ├── YES → ORANGE minimum. Check deadline. May be RED.
│   └── NO → Score normally but minimum YELLOW.
└── NO → Continue.

Is the financial exposure > 25% of relevant deal/contract value?
├── YES → Score normally but minimum ORANGE.
└── NO → Continue.

Apply standard Severity x Likelihood scoring.
```

---

## When to Engage Outside Counsel

### Mandatory

| Trigger | Why |
|---------|-----|
| Active litigation | Defense or prosecution requires litigation counsel |
| Government investigation | Regulatory, law enforcement, or agency inquiry |
| Criminal exposure | Potential criminal liability for org or personnel |
| Securities issues | Could affect disclosures or filings |
| Board-level matters | Requires board notification or approval |

### Strongly Recommended

| Trigger | Why |
|---------|-----|
| Novel legal issues | First impression or unsettled law |
| Jurisdictional complexity | Unfamiliar jurisdiction or conflicting requirements |
| Material financial exposure | Exceeds organizational risk tolerance |
| Specialized expertise needed | Antitrust, FCPA, patent prosecution, etc. |
| New regulations | Materially affect business, require compliance program |
| M&A transactions | Due diligence, deal structuring, regulatory approvals |

### Consider

| Trigger | Why |
|---------|-----|
| Complex contract disputes | Significant disagreements with material counterparties |
| Employment matters | Discrimination, harassment, wrongful termination, whistleblower |
| Data incidents | Potential breaches triggering notification obligations |
| IP disputes | Infringement allegations involving material products |
| Insurance coverage disputes | Disagreements over coverage for material claims |

---

## Business Impact Scoring

Beyond the risk matrix, assess business impact across five dimensions:

| Dimension | Questions to Answer | Score (1-5) |
|-----------|-------------------|-------------|
| **Financial** | Direct costs? Potential damages? Insurance coverage? | __ |
| **Operational** | Business disruption? Process changes needed? Timeline impact? | __ |
| **Reputational** | Public attention likely? Customer trust affected? Media risk? | __ |
| **Regulatory** | Fines possible? License/certification at risk? Ongoing scrutiny? | __ |
| **Strategic** | Affects competitive position? Partnership implications? Market access? | __ |

**Composite Business Impact = Average of dimension scores**

Use to prioritize when multiple risks compete for attention. Two risks with the same matrix score may have very different business impact profiles.

---

## Risk Assessment Documentation

### Risk Assessment Memo Format

```
## Legal Risk Assessment

**Date**: [date]
**Assessor**: [name]
**Matter**: [description]
**Privileged**: [Yes/No]

### 1. Risk Description
[Clear, concise description]

### 2. Background and Context
[Relevant facts, history, business context]

### 3. Risk Analysis

**Severity**: [1-5] -- [Label]
[Rationale: potential financial exposure, operational impact, reputational considerations]

**Likelihood**: [1-5] -- [Label]
[Rationale: precedent, triggering events, current conditions]

**Risk Score**: [Score] -- [GREEN/YELLOW/ORANGE/RED]

### 4. Business Impact
| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Financial | [1-5] | [Why] |
| Operational | [1-5] | [Why] |
| Reputational | [1-5] | [Why] |
| Regulatory | [1-5] | [Why] |
| Strategic | [1-5] | [Why] |

### 5. Contributing Factors
[What increases the risk]

### 6. Mitigating Factors
[What decreases the risk or limits exposure]

### 7. Mitigation Options
| Option | Effectiveness | Cost/Effort | Recommended? |
|--------|-------------|-------------|-------------|
| [Option] | [H/M/L] | [H/M/L] | [Yes/No] |

### 8. Recommended Approach
[Specific recommendation with rationale]

### 9. Residual Risk
[Expected risk level after mitigation]

### 10. Monitoring Plan
[How and how often monitored. Trigger events for re-assessment.]

### 11. Next Steps
1. [Action -- Owner -- Deadline]
2. [Action -- Owner -- Deadline]
```

### Risk Register Entry Format

| Field | Content |
|-------|---------|
| Risk ID | Unique identifier |
| Date Identified | [date] |
| Description | Brief description |
| Category | Contract / Regulatory / Litigation / IP / Data Privacy / Employment / Corporate |
| Severity | [1-5] with label |
| Likelihood | [1-5] with label |
| Risk Score | [calculated] |
| Risk Level | GREEN / YELLOW / ORANGE / RED |
| Business Impact | [composite score] |
| Owner | Person responsible |
| Mitigations | Current controls |
| Status | Open / Mitigated / Accepted / Closed |
| Review Date | Next scheduled review |
| Notes | Additional context |

---

## Common Scoring Errors

| Error | Problem | Correction |
|-------|---------|------------|
| Anchoring on worst case | Setting severity to 5 because the worst possible outcome is catastrophic, ignoring that the worst case is extremely unlikely | Score severity based on the most likely adverse outcome, not the theoretical worst case |
| Conflating severity and likelihood | High-severity risk automatically scored as high-likelihood | Assess independently. A catastrophic risk can be remote. |
| Recency bias | Recent incident drives likelihood up beyond what data supports | Use base rates and precedent, not recent events alone |
| Ignoring mitigations | Scoring raw risk without accounting for controls already in place | Score residual risk (after existing controls), not inherent risk |
| Range compression | All risks scored 3-4 (moderate-high) to avoid extremes | Use the full scale. Scores of 1 and 5 exist for a reason. |
| Single-dimension focus | Scoring on financial exposure only, ignoring operational/reputational | Use the five-dimension business impact model |

---

## Risk Review Cadence

| Risk Level | Review Frequency | Escalation Check |
|------------|-----------------|-----------------|
| GREEN | Quarterly or annually | At each review |
| YELLOW | Monthly or at trigger events | At each review + when conditions change |
| ORANGE | Weekly or at milestones | At each review + when new information arrives |
| RED | Daily or more frequently | Continuous until resolved or reduced |

**Trigger events requiring immediate re-assessment regardless of cadence:**
- New litigation filed or threatened
- Regulatory inquiry or investigation initiated
- Data breach discovered
- Material contract breach (by either party)
- Significant business change (M&A, restructuring, new market entry)
- Change in applicable law or regulation
- Insurance coverage change
