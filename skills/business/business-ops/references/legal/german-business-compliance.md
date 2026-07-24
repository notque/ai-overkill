# German & EU Business Compliance Frameworks

Regulation-specific requirements for German business operations, digital services, electronic identity, and AI systems.

---

## Framework Quick Reference

| Framework | Jurisdiction | Applies When | Key Differentiator |
|-----------|-------------|-------------|-------------------|
| GoBD | Germany | Tax-relevant digital records | Immutability, audit trails, Verfahrensdokumentation |
| HGB §§238-261 | Germany | All German merchants | Legal foundation for bookkeeping; GoBD operationalizes |
| TDDDG | Germany | All digital service providers | Cookie consent, ePrivacy (was TTDSG, renamed May 2024) |
| eIDAS 2.0 | EU | Any org accepting ID verification | Digital wallets by end 2026, open source requirement |
| EU AI Act | EU | Any org deploying AI systems | Risk-based tiers, mandatory logging, EUR 35M fines |

---

## GoBD (Grundsätze zur ordnungsmäßigen Führung und Aufbewahrung von Büchern)

Federal Ministry of Finance regulation for digital bookkeeping and data retention.

### 2025 Changes

- **E-invoicing mandate (Jan 1, 2025 receiving; Jan 1, 2027 issuing >EUR 800K)**: XML component of ZUGFeRD is legally relevant for archiving
- **Retention reduced**: 10 → 8 years for invoices/receipts (Bürokratieentlastungsgesetz IV, Jan 1, 2025)
- **PDF storage**: If PDF is generatable from XML, separate PDF storage no longer required

### Core Principles

Integrity, Authenticity, Accessibility, Immutability, Traceability.

### Verfahrensdokumentation (Mandatory Since 2015)

Required for every IT-supported tax-relevant process. Four components:

1. General description
2. User documentation
3. Technical system documentation
4. Operations documentation

### Code-Level Checks

| ID | Check | GoBD Ref |
|----|-------|----------|
| GB-01 | Audit trail on all tax-relevant data (user ID, timestamp, old/new value) | Immutability |
| GB-02 | WORM-like write protection for archived records | Retention |
| GB-03 | Verfahrensdokumentation covers all IT-supported tax processes | §151 |
| GB-04 | E-invoices archived in original machine-readable XML format | 2025 Amendment |
| GB-05 | Change management documented for system updates affecting tax data | Verfahrensdoku |
| GB-06 | Data retention configured for 8-year minimum (post-Dec 2024 records) | BEG IV |
| GB-07 | Role-based access control on tax-relevant data with integrity checks | Access/Integrity |

---

## HGB §§238-261 (Handelsgesetzbuch Third Book)

Commercial bookkeeping and accounting requirements for German merchants.

### Key Sections

| Section | Requirement |
|---------|------------|
| §238 | Merchants must keep books recording all business transactions |
| §239 | Clear records, no blank spaces, no erasures |
| §243-245 | Annual financial statements: balance sheet + P&L |
| §257 | Retention: 10y financial statements, 8y invoices (BEG IV) |

**HGB = the WHAT; GoBD = the HOW for electronic systems.**

### Code-Level Checks

| ID | Check | HGB Ref |
|----|-------|---------|
| HG-01 | Double-entry bookkeeping enforced in accounting system | §238 |
| HG-02 | Retention periods configured (10y statements, 8y invoices) | §257 + BEG IV |
| HG-03 | Records immutable after finalization | §239 |
| HG-04 | Financial statements generated with complete balance sheet + P&L | §243-245 |
| HG-05 | Digital records maintain audit-ready accessibility | §257 |

---

## TDDDG (Telekommunikation-Digitale-Dienste-Datenschutz-Gesetz)

Germany's ePrivacy implementation. Renamed TTDSG → TDDDG May 13, 2024 (aligned with EU Digital Services Act).

### Section 25: Cookie/Tracking Consent

- Consent required before storing/accessing info on user terminal
- Exceptions: transmission of communications, strictly necessary for requested service
- "Accept" and "Decline" with equal prominence
- Pre-filled not permitted
- Purpose, duration, third-party access disclosed
- GDPR-compliant consent standard

**Penalties**: Max EUR 300,000 per violation.

### Code-Level Checks

| ID | Check | TDDDG Ref |
|----|-------|-----------|
| TD-01 | Cookie consent banner with equal-prominence Accept/Decline buttons | §25(1) |
| TD-02 | No non-essential cookies set before explicit consent | §25(1) |
| TD-03 | Consent not pre-filled or pre-selected | §25(1) |
| TD-04 | Purpose, duration, third-party access disclosed before consent | §25(1) |
| TD-05 | Strictly-necessary exception properly scoped (no analytics in exception) | §25(2) |
| TD-06 | Consent management follows TDDDG ordinance standards | Consent Ordinance |

---

## eIDAS 2.0 (Regulation 2024/1183)

European Digital Identity Framework. Wallets by end 2026. Regulated industries must accept wallets by December 2027.

### New Trust Services

- QEAA (Qualified Electronic Attestation of Attributes)
- Electronic Archiving
- Electronic Ledgers
- EUDI Wallet

### Developer Requirements

- Wallet components must be open source
- Zero-tracking/profiling by design
- Privacy dashboard
- Selective disclosure
- Local data storage

### Code-Level Checks

| ID | Check | eIDAS Ref |
|----|-------|-----------|
| EI-01 | Electronic signatures implement correct eIDAS level (simple/advanced/qualified) | Art. 25-26 |
| EI-02 | QEAA verification against qualified trust service provider | Art. 45 |
| EI-03 | EUDI Wallet integration accepts wallet-presented credentials | Art. 5a |
| EI-04 | Privacy-by-design: no tracking/profiling of wallet usage | Art. 5a |
| EI-05 | Selective disclosure: request only necessary attributes | Art. 5a |
| EI-06 | Open source wallet components publicly available | Art. 5a |

---

## EU AI Act (Regulation 2024/1689)

Risk-based: Unacceptable (banned Feb 2025) → High-Risk (Aug 2026) → Limited (transparency) → Minimal.

### Timeline

| Date | Milestone |
|------|-----------|
| Feb 2, 2025 | Prohibited practices + AI literacy obligations |
| Aug 2, 2025 | GPAI obligations |
| Aug 2, 2026 | High-risk full compliance |
| Aug 2, 2027 | Annex I regulated products |

### Developer-Facing Requirements (Articles 9-15)

| Article | Requirement |
|---------|------------|
| Art. 9 | Lifecycle risk identification, residual risk documentation, continuous monitoring |
| Art. 11 | Technical documentation (9 Annex IV categories incl. architecture, ADRs, model cards, training data, testing). Retained 10 years. |
| Art. 12 | Automatic logging as architectural requirement (not bolt-on). Schema: user, timestamp, spec version, model ID, input, output, reviewer, tests. Retention: 6 months minimum. |
| Art. 13 | Transparency -- disclose GPAI model, spec, human review, modifications |
| Art. 14 | Human oversight -- override/halt mechanisms, automation bias awareness |
| Art. 15 | Accuracy & robustness testing with documented metrics |

### High-Risk Triggers for Dev Teams

- AI as safety component in regulated products (medical, automotive)
- AI evaluating/screening/monitoring PEOPLE (accidental trigger: dev performance dashboards, AI-based PR routing)
- AI in critical infrastructure

### GPAI Open Source Exception

Exempt from documentation unless systemic risk.

### Penalties

| Tier | Fine | Applies To |
|------|------|-----------|
| Prohibited practices | EUR 35M / 7% global revenue | Art. 5 violations |
| High-risk non-compliance | EUR 15M / 3% global revenue | Arts. 9-15 violations |
| Incorrect information | EUR 7.5M / 1% global revenue | Misleading declarations |

### Code-Level Checks

| ID | Check | AI Act Ref |
|----|-------|-----------|
| AI-01 | AI system risk classification documented | Art. 6 |
| AI-02 | Technical documentation with 9 Annex IV categories | Art. 11 |
| AI-03 | Automatic logging architecture with provenance schema | Art. 12 |
| AI-04 | Human oversight mechanism (override/halt capability) | Art. 14 |
| AI-05 | Accuracy and robustness testing with documented metrics | Art. 15 |
| AI-06 | Risk management system with lifecycle coverage | Art. 9 |
| AI-07 | Transparency disclosure for GPAI model usage | Art. 13 |
| AI-08 | Version control for all AI artifacts (code, weights, configs, datasets, docs) | Art. 11 |
| AI-09 | Prohibited AI practices not implemented (social scoring, real-time biometric mass surveillance, etc.) | Art. 5 |
| AI-10 | AI literacy training documented for staff | Art. 4 |
| AI-11 | CI/CD provenance tracking (model ID, spec version, human review) per artifact | Art. 12 |

---

## Cross-Framework Compliance Matrix (German Business)

| Pair | Relationship |
|------|-------------|
| GoBD ↔ HGB | GoBD operationalizes HGB §§238-261 for electronic systems |
| TDDDG ↔ GDPR | TDDDG is German ePrivacy; GDPR consent standards apply |
| AI Act ↔ GDPR | AI Act references GDPR for personal data in AI training |
| eIDAS ↔ DORA | Financial entities must accept EUDI Wallets by 2027 |

**Rule**: When frameworks overlap, apply the strictest requirement unless doing so would violate another framework. Document conflicts and escalate to counsel.

---

## Cross-References

These reviewer-system references cover adjacent German/EU compliance domains:

- `agents/reviewer-system/references/german-it-security.md` — BSI Grundschutz, KRITIS, NIS2UmsuCG
- `agents/reviewer-system/references/financial-resilience-de-eu.md` — DORA, KWG/MaRisk (eIDAS<>DORA interaction noted in matrix above)
- `agents/reviewer-system/references/industry-specific-compliance.md` — TISAX automotive compliance
- `agents/reviewer-system/references/sovereign-cloud-data-residency.md` — BSI C5, BDSG/DSGVO, data residency
- `agents/reviewer-system/references/compliance-checklists.md` — GDPR, SOC 2, PCI-DSS, HIPAA

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
