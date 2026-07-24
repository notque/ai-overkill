# Compliance Frameworks

Regulation-specific requirements, checklist gates, and jurisdiction mapping for compliance checks. Covers major privacy, financial, and health data frameworks.

---

## Framework Quick Reference

| Framework | Jurisdiction | Applies When | Key Differentiator |
|-----------|-------------|-------------|-------------------|
| GDPR | EU/EEA + any org processing EU residents' data | Processing personal data of EU individuals | Broadest scope, highest fines (4% global revenue) |
| CCPA/CPRA | California | Business meets revenue/data thresholds + CA residents | Opt-out model, "sale" broadly defined |
| HIPAA | US | Covered entities + business associates handling PHI | Criminal penalties, BAA required |
| SOX | US | Public companies + accounting firms | Internal controls over financial reporting |
| PCI DSS | Global | Any entity storing/processing/transmitting cardholder data | Self-assessment or QSA audit |
| SOC 2 | Global | Service organizations (trust services criteria) | Type I (point-in-time) vs. Type II (period) |

---

## GDPR (General Data Protection Regulation)

### Scope Determination

Applies if ANY of these are true:
- Organization is established in the EU/EEA
- Organization offers goods/services to individuals in the EU (even if org is outside EU)
- Organization monitors behavior of individuals in the EU

### Obligation Checklist

#### Lawful Basis (Article 6)

- [ ] Lawful basis identified and documented for EACH processing activity
- [ ] Basis is one of: consent, contract, legal obligation, vital interest, public task, legitimate interest
- [ ] If consent: freely given, specific, informed, unambiguous, withdrawable
- [ ] If legitimate interest: legitimate interest assessment (LIA) conducted and documented
- [ ] If special category data (Article 9): additional condition identified (explicit consent, employment, vital interest, etc.)

#### Data Subject Rights

| Right | Response Deadline | Extension | Key Requirements |
|-------|------------------|-----------|-----------------|
| Access (Art. 15) | 30 days | +60 days with notice | Copy of data + supplementary information |
| Rectification (Art. 16) | 30 days | +60 days with notice | Correct inaccurate data without undue delay |
| Erasure (Art. 17) | 30 days | +60 days with notice | Delete unless exemption applies (legal obligation, public interest, legal claims) |
| Restriction (Art. 18) | 30 days | +60 days with notice | Mark data, cease processing except storage |
| Portability (Art. 20) | 30 days | +60 days with notice | Structured, commonly used, machine-readable format |
| Objection (Art. 21) | Without undue delay | N/A | Must stop unless compelling legitimate grounds |

#### Breach Notification

- [ ] Process in place to detect breaches
- [ ] Supervisory authority notification within 72 hours of awareness
- [ ] Data subject notification "without undue delay" if high risk
- [ ] Breach register maintained (all breaches, not just notifiable ones)
- [ ] Template notifications prepared for common breach types

#### International Transfers

| Transfer Mechanism | When to Use | Current Status |
|-------------------|-------------|----------------|
| Adequacy decision | Transferring to a country with EU adequacy | Check current list -- subject to change |
| Standard Contractual Clauses (SCCs) | Most common mechanism for non-adequate countries | Must use June 2021 version. Correct module required (C2P, C2C, P2P, P2C). |
| Binding Corporate Rules (BCRs) | Intra-group transfers | Requires supervisory authority approval. 12-18 month process. |
| Derogations (Art. 49) | Limited, specific situations | Explicit consent, contract necessity, important public interest. Not for systematic transfers. |

Transfer Impact Assessment required for SCCs to non-adequate countries:
- [ ] Laws of the destination country assessed
- [ ] Supplementary measures identified (encryption, pseudonymization, split processing)
- [ ] Assessment documented and reviewed periodically

#### Records of Processing (Article 30)

- [ ] Records maintained for all processing activities
- [ ] Each record includes: purposes, data categories, recipients, transfers, retention, security measures
- [ ] Records available to supervisory authority on request

#### Data Protection Impact Assessment (DPIA)

Required when processing is "likely to result in a high risk":
- [ ] Systematic and extensive profiling with significant effects
- [ ] Large-scale processing of special categories or criminal data
- [ ] Large-scale systematic monitoring of public areas
- [ ] New technologies with potential high-risk impact
- [ ] Automated decision-making with legal or significant effects

DPIA must include: systematic description, necessity/proportionality, risk assessment, mitigation measures.

---

## CCPA / CPRA (California)

### Scope Determination

Applies if business meets ANY threshold:
- Annual gross revenue > $25 million
- Buys, sells, or shares personal information of 100,000+ California residents/households/devices
- Derives 50%+ of annual revenue from selling or sharing California residents' personal information

### Obligation Checklist

#### Consumer Rights

| Right | Response Deadline | Extension | Notes |
|-------|------------------|-----------|-------|
| Right to Know | 45 calendar days | +45 days with notice | Acknowledge within 10 business days |
| Right to Delete | 45 calendar days | +45 days with notice | Must direct service providers to delete too |
| Right to Opt-Out of Sale/Sharing | 15 business days | None | "Do Not Sell or Share My Personal Information" link required |
| Right to Correct | 45 calendar days | +45 days with notice | CPRA addition |
| Right to Limit Sensitive PI Use | 15 business days | None | CPRA addition. "Limit the Use of My Sensitive Personal Information" link. |
| Non-Discrimination | N/A | N/A | Cannot penalize consumers exercising rights |

#### Service Provider Requirements

- [ ] Written contract with service providers restricts PI use to specified business purpose
- [ ] Service providers certify they understand and will comply with CCPA/CPRA
- [ ] Service providers must cooperate with consumer rights requests
- [ ] Downstream service providers bound by same restrictions

#### Privacy Notice Requirements

- [ ] Notice at or before collection
- [ ] Categories of PI collected
- [ ] Purposes for each category
- [ ] Whether PI is sold or shared
- [ ] Retention period for each category
- [ ] Consumer rights and how to exercise them
- [ ] Updated at least annually

### CCPA vs. GDPR Key Differences

| Dimension | GDPR | CCPA/CPRA |
|-----------|------|-----------|
| Consent model | Opt-in (consent before processing) | Opt-out (can process until consumer opts out) |
| Scope of "personal data" | Any information relating to identified/identifiable person | Broader: includes household and device data |
| Right to delete exceptions | More limited | Broader exceptions (transaction completion, security, legal obligation, internal use) |
| Private right of action | Generally no (except through supervisory authority) | Yes, for data breaches (statutory damages $100-$750 per consumer per incident) |
| Enforcement body | Supervisory authorities (e.g., ICO, CNIL) | California Privacy Protection Agency (CPPA) + AG |

---

## HIPAA (Health Insurance Portability and Accountability Act)

### Scope Determination

Applies to:
- **Covered entities**: Health plans, healthcare clearinghouses, healthcare providers who transmit health information electronically
- **Business associates**: Any entity that creates, receives, maintains, or transmits PHI on behalf of a covered entity

### Obligation Checklist

#### Administrative Safeguards

- [ ] Security officer designated
- [ ] Risk analysis conducted (initial + periodic)
- [ ] Risk management plan implemented
- [ ] Workforce training on policies and procedures
- [ ] Sanctions policy for violations
- [ ] Information system activity review procedures
- [ ] Contingency plan (backup, recovery, emergency operations)
- [ ] Business Associate Agreements (BAAs) with all BAs

#### Technical Safeguards

- [ ] Access controls (unique user IDs, emergency access, automatic logoff, encryption)
- [ ] Audit controls (hardware, software, procedural mechanisms to record access)
- [ ] Integrity controls (mechanisms to authenticate ePHI, protect from improper alteration/destruction)
- [ ] Transmission security (encryption for ePHI in transit)
- [ ] Authentication (verify identity of persons seeking access)

#### Physical Safeguards

- [ ] Facility access controls
- [ ] Workstation use policies
- [ ] Workstation security
- [ ] Device and media controls (disposal, re-use, accountability, backup)

#### Breach Notification

| Notification | Deadline | Details |
|-------------|----------|---------|
| To individuals | Without unreasonable delay, max 60 days from discovery | Written notice by first-class mail or email (if consented) |
| To HHS | 60 days (if 500+ individuals); annual (if <500) | Via HHS breach reporting portal |
| To media | Without unreasonable delay, max 60 days | If breach affects 500+ residents of a state/jurisdiction |

#### BAA Requirements

Every Business Associate Agreement must include:
- [ ] Permitted uses and disclosures of PHI
- [ ] Prohibition on further use/disclosure beyond contract
- [ ] Appropriate safeguards requirement
- [ ] Breach reporting obligation
- [ ] Subcontractor same-obligation flow-down
- [ ] Access to PHI for individual rights requests
- [ ] Return or destruction of PHI on termination
- [ ] HHS audit/investigation cooperation

---

## SOX (Sarbanes-Oxley Act)

### Scope Determination

Applies to: US public companies and their accounting firms. Section 404 (internal controls) is the primary in-house legal touchpoint.

### Key Compliance Areas

#### Section 302 -- Corporate Responsibility for Financial Reports

- [ ] CEO and CFO certify quarterly and annual reports
- [ ] Certify: reviewed the report, no material misstatements, financial statements fairly present financial condition
- [ ] Certify: responsible for internal controls, evaluated within 90 days, disclosed changes

#### Section 404 -- Internal Controls over Financial Reporting

- [ ] Management assessment of internal controls effectiveness
- [ ] External auditor attestation on management's assessment
- [ ] Material weaknesses in controls identified and disclosed
- [ ] Remediation plans for identified weaknesses

#### Section 802 -- Criminal Penalties for Document Destruction

- [ ] Document retention policies in place
- [ ] Litigation hold procedures documented and enforced
- [ ] Prohibition on destruction of documents related to federal investigation
- [ ] 20-year maximum imprisonment for willful destruction

#### Whistleblower Protections (Section 806)

- [ ] Anti-retaliation policy in place
- [ ] Reporting channels available (anonymous option)
- [ ] Investigation procedures for reports
- [ ] No discharge, demotion, suspension, threats, harassment for reporting

---

## PCI DSS (Payment Card Industry Data Security Standard)

### Scope Determination

Applies to: any entity that stores, processes, or transmits cardholder data (CHD) or sensitive authentication data (SAD).

### 12 Requirements Summary

| Requirement | Area | Key Controls |
|-------------|------|-------------|
| 1 | Network security | Install and maintain network security controls |
| 2 | Default security | Apply secure configurations to all system components |
| 3 | Data protection | Protect stored account data (encryption, masking, hashing) |
| 4 | Transmission | Protect CHD with strong cryptography during transmission |
| 5 | Malware | Protect from malicious software |
| 6 | Software | Develop and maintain secure systems and software |
| 7 | Access control | Restrict access by business need to know |
| 8 | Authentication | Identify users and authenticate access |
| 9 | Physical | Restrict physical access to CHD |
| 10 | Logging | Log and monitor all access to system components and CHD |
| 11 | Testing | Test security of systems and networks regularly |
| 12 | Policies | Support information security with organizational policies and programs |

---

## Additional Privacy Frameworks (Quick Reference)

| Framework | Jurisdiction | Key Differentiators | Enforcement |
|-----------|-------------|--------------------|----|
| LGPD | Brazil | Similar to GDPR. DPO required. ANPD enforcement. | Fines up to 2% of revenue in Brazil (R$50M cap) |
| POPIA | South Africa | Information Regulator oversight. Required registration. | Up to R10M fine or 10 years imprisonment |
| PIPEDA | Canada (federal) | Consent-based. OPC oversight. Being modernized. | Complaints-driven, limited fines currently |
| PDPA | Singapore | Do Not Call registry. Mandatory breach notification. | Up to S$1M fine |
| PIPL | China | Strict cross-border rules. Data localization. CAC oversight. | Up to 5% of annual revenue |
| UK GDPR | United Kingdom | Post-Brexit UK version. ICO oversight. | Up to GBP 17.5M or 4% of global turnover |
| Privacy Act 1988 | Australia | 13 Australian Privacy Principles. Notifiable Data Breaches scheme. | Up to A$50M per violation |

---

## Cross-Framework Compliance Matrix

When multiple frameworks apply, use this matrix to identify the strictest requirement:

| Obligation | GDPR | CCPA/CPRA | HIPAA | Strictest |
|-----------|------|-----------|-------|-----------|
| Consent model | Opt-in | Opt-out | Authorization | GDPR (opt-in) |
| Breach notification (authority) | 72 hours | N/A | 60 days | GDPR (72 hours) |
| Breach notification (individual) | Without undue delay | N/A | 60 days | GDPR |
| Right to delete | Yes (with exceptions) | Yes (broader exceptions) | Limited | GDPR (fewer exceptions) |
| Data retention limits | Purpose limitation | Stated in notice | 6 years (HIPAA records) | Varies by data type |
| Cross-border transfers | Restricted (SCCs, etc.) | No specific restriction | BAA required | GDPR |
| DPO/Privacy officer | Required in certain cases | Not required | Security officer required | Depends on org |
| Fines (maximum) | 4% global revenue | $7,500 per violation | $1.9M per violation category | GDPR |

**Rule**: When frameworks overlap, apply the strictest requirement unless doing so would violate another framework. Document conflicts and escalate to counsel.

---

## Compliance Check Output Template

```
## Compliance Check: [Initiative]

### Quick Assessment
[Proceed / Proceed with conditions / Requires further review]

### Applicable Frameworks
| Framework | Relevance | Key Requirements |
|-----------|-----------|-----------------|
| [Framework] | [How it applies] | [What to do] |

### Requirements Checklist
| # | Requirement | Framework | Status | Action Needed |
|---|-------------|-----------|--------|---------------|
| 1 | [Req] | [Source] | [Met/Not Met/Unknown] | [Action] |

### Risk Areas
| Risk | Severity | Framework | Mitigation |
|------|----------|-----------|------------|
| [Risk] | [H/M/L] | [Source] | [How to address] |

### Approvals Needed
| Approver | Why | Framework | Status |
|----------|-----|-----------|--------|
| [Role] | [Reason] | [Source] | [Pending] |

### Recommended Actions (Priority Order)
1. [Action] -- [Deadline if applicable]
```
