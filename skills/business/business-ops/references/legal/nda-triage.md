# NDA Triage

Rapid NDA pre-screening methodology. GREEN/YELLOW/RED classification with a 10-criterion screening checklist and common deviations catalog.

---

## Screening Checklist

### Criterion 1: Agreement Structure

| Check | Pass | Flag | Fail |
|-------|------|------|------|
| Type identified (Mutual / Unilateral disclosing / Unilateral receiving) | Type clear and appropriate for context | Type not ideal but workable | Type wrong for the relationship |
| Appropriate for business context | Mutual for exploratory, unilateral for one-way disclosure | Slight mismatch but manageable | Fundamentally inappropriate |
| Standalone agreement | Yes, standalone NDA | Confidentiality section in larger agreement (note broader context) | Not actually an NDA (contains commercial terms, exclusivity) |

**If the document is not actually an NDA** (labeled as NDA but contains substantive commercial terms): flag immediately as RED, recommend full contract review.

---

### Criterion 2: Definition of Confidential Information

| Check | Pass | Flag | Fail |
|-------|------|------|------|
| Reasonable scope | Limited to non-public info disclosed for stated purpose | Broader than preferred but not unreasonable | "All information of any kind whether or not marked" |
| Marking requirements | None, or marking within 30 days of oral disclosure | Immediate marking required for oral disclosures | Impractical marking requirements |
| Exclusions present | All standard exclusions defined | Missing one non-critical exclusion | Missing critical exclusions or none defined |
| No problematic inclusions | Clean | Minor concern | Defines publicly available or independently developed info as confidential |

---

### Criterion 3: Obligations of Receiving Party

| Check | Pass | Flag | Fail |
|-------|------|------|------|
| Standard of care | Reasonable care or same as own confidential info | Slightly higher but workable | Strict liability or impractical standard |
| Use restriction | Limited to stated purpose | Purpose broader than expected | No use restriction or "any purpose" |
| Disclosure restriction | Need-to-know basis, bound by similar obligations | Slightly broader but controlled | No meaningful restriction |
| No onerous obligations | Standard obligations | Minor unusual requirements | Impractical requirements (encrypt all communications, physical logs) |

---

### Criterion 4: Standard Carveouts

All five must be present. Missing any critical carveout affects classification.

| Carveout | Required | Impact if Missing |
|----------|----------|-------------------|
| **Public knowledge** | Information publicly available through no fault of receiving party | YELLOW -- add in redline |
| **Prior possession** | Information already known before disclosure | YELLOW -- add in redline |
| **Independent development** | Information independently developed without reference to confidential info | RED if missing -- creates risk that internal work is claimed as derived |
| **Third-party receipt** | Information rightfully received from unrestricted third party | YELLOW -- add in redline |
| **Legal compulsion** | Right to disclose when required by law/regulation/legal process (with notice where permitted) | RED if missing -- could prevent compliance with legal obligations |

---

### Criterion 5: Permitted Disclosures

| Recipient Category | Standard | Flag If |
|--------------------|----------|---------|
| Employees | Need-to-know employees | Not explicitly permitted |
| Contractors/Advisors | Under similar confidentiality obligations | Not permitted or restricted |
| Affiliates | If needed for business purpose | Prohibited when needed |
| Legal/Regulatory | As required by law | Not addressed (legal compulsion carveout may cover) |

---

### Criterion 6: Term and Duration

| Element | GREEN | YELLOW | RED |
|---------|-------|--------|-----|
| Agreement term | 1-3 years | 3-5 years | 5+ years without justification |
| Confidentiality survival | 2-5 years from termination | 5-7 years | Perpetual (unless trade secret carveout) |
| Trade secret protection | As long as info remains a trade secret | Slightly broader | Perpetual for all information regardless of trade secret status |

---

### Criterion 7: Return and Destruction

| Check | Pass | Flag | Fail |
|-------|------|------|------|
| Obligation triggered | On termination or upon request | Only on termination (no upon-request) | No return/destruction obligation |
| Scope | Return or destroy all copies | Reasonable scope | Overbroad or unclear |
| Retention exception | Allows retention for legal/compliance/backup | No explicit exception (likely implied) | Requires destruction of all copies including legal/compliance backups |
| Certification | Certification of destruction acceptable | Sworn affidavit required | Notarized affidavit or third-party attestation |

---

### Criterion 8: Remedies

| Check | Pass | Flag | Fail |
|-------|------|------|------|
| Injunctive relief | Acknowledgment of irreparable harm, equitable relief appropriate | Slightly broader but standard | Automatic injunction without showing harm |
| Damages | No pre-determined damages | Minor provisions | Liquidated damages in NDA |
| Symmetry | Mutual remedies (in mutual NDA) | Minor asymmetry | Substantially one-sided |

---

### Criterion 9: Problematic Provisions

Any of these present should trigger at minimum YELLOW, and most trigger RED.

| Provision | Classification if Present | Standard Position |
|-----------|--------------------------|-------------------|
| **Non-solicitation of employees** | RED | Does not belong in NDA. Delete entirely. If counterparty insists: limit to targeted solicitation (not general recruitment), 12-month term. |
| **Non-compete** | RED | Does not belong in NDA. Delete entirely. |
| **Exclusivity** | RED | Should not restrict either party from similar discussions with others |
| **Standstill** | RED (unless M&A context) | Inappropriate outside M&A. In M&A: should be time-limited with clear terms. |
| **Broad residuals clause** | RED | Effectively creates license to use confidential info. Resist entirely. |
| **Narrow residuals clause** | YELLOW | If limited to: unaided memory of authorized individuals, excludes trade secrets and patentable info, does not grant IP license. |
| **IP assignment or license** | RED | NDA should not grant any IP rights |
| **Audit rights** | YELLOW-RED | Unusual in standard NDAs. If present, must have reasonable scope and notice. |

---

### Criterion 10: Governing Law and Jurisdiction

| Check | GREEN | YELLOW | RED |
|-------|-------|--------|-----|
| Jurisdiction | Well-established commercial jurisdiction | Acceptable but non-preferred | Unfavorable or unusual jurisdiction |
| Consistency | Governing law and jurisdiction in same/related jurisdictions | Minor mismatch | Different countries for law vs. venue |
| Dispute mechanism | Litigation (standard for NDA disputes) | Mediation-first with litigation fallback | Mandatory arbitration with drafter-favorable rules |

---

## Classification Rules

### GREEN -- Standard Approval

**ALL of the following must be true:**
- Mutual NDA (or unilateral in appropriate direction)
- All five standard carveouts present
- Term within standard range (1-3 year agreement, 2-5 year survival)
- No non-solicitation, non-compete, or exclusivity provisions
- No residuals clause, or residuals narrowly scoped
- Reasonable governing law jurisdiction
- Standard remedies (no liquidated damages)
- Permitted disclosures include employees, contractors, advisors
- Return/destruction includes retention exception
- Definition of confidential information reasonably scoped

**Routing**: Approve via standard delegation of authority. Same-day.

---

### YELLOW -- Counsel Review

**One or more present, but NDA is not fundamentally problematic:**
- Definition broader than preferred but not unreasonable
- Term longer than standard but within market range (5-year agreement, 7-year survival)
- Missing one standard carveout that could be added with minor redline
- Narrow residuals clause (unaided memory, excludes trade secrets)
- Governing law in acceptable but non-preferred jurisdiction
- Minor asymmetry in mutual NDA
- Marking requirements present but workable
- Return/destruction lacks explicit retention exception
- Unusual but non-harmful provisions (obligation to notify of potential breach)

**Routing**: Flag specific issues for counsel review. Single review pass expected. 1-2 business days.

---

### RED -- Full Legal Review

**One or more present:**
- Unilateral when mutual is required (or wrong direction)
- Missing critical carveouts (independent development or legal compulsion)
- Non-solicitation or non-compete provisions
- Exclusivity or standstill provisions without appropriate context
- Unreasonable term (10+ years, or perpetual without trade secret justification)
- Overbroad definition capturing public or independently developed information
- Broad residuals clause creating effective license
- IP assignment or license grant
- Liquidated damages or penalty provisions
- Audit rights without reasonable scope or notice
- Highly unfavorable jurisdiction with mandatory arbitration
- Document is not actually an NDA (contains substantive commercial terms)

**Routing**: Full legal review. Do not sign. Requires negotiation, counterproposal with standard form, or rejection. 3-5 business days.

---

## Common Deviations Catalog

### Deviation: Overbroad Confidential Information Definition

**Frequency**: Very common
**Risk**: Captures information that should not be confidential, creates compliance burden
**Standard redline**: Narrow to information marked or identified as confidential, or that a reasonable person would understand to be confidential given nature and circumstances.
**Fallback**: Accept broader definition but add robust exclusions.

---

### Deviation: Missing Independent Development Carveout

**Frequency**: Common
**Risk**: Could create claims that internally-developed products were derived from counterparty's confidential information
**Standard redline**: Add: "Information independently developed by or for the Receiving Party without use of or reference to the Disclosing Party's Confidential Information."
**Fallback**: None. This carveout is essential. Escalate if counterparty refuses.

---

### Deviation: Non-Solicitation of Employees

**Frequency**: Moderate (often embedded by counterparty legal as boilerplate)
**Risk**: Restricts hiring, may be unenforceable in some jurisdictions, creates unnecessary liability
**Standard redline**: Delete entirely.
**Fallback**: If counterparty insists: limit to targeted solicitation (not general recruitment or response to job postings), cap at 12 months, limit to employees directly involved in the engagement.

---

### Deviation: Broad Residuals Clause

**Frequency**: Moderate (more common in technology NDAs)
**Risk**: Effectively grants a license to use confidential information for any purpose, undermining the NDA's core protection
**Standard redline**: Delete entirely.
**Fallback**: If required: (a) limited to general ideas, concepts, know-how retained in unaided memory of authorized individuals, (b) explicitly excludes trade secrets and patentable information, (c) does not create any IP license, (d) does not override any other obligation in the agreement.

---

### Deviation: Perpetual Confidentiality Obligation

**Frequency**: Common
**Risk**: Creates indefinite compliance burden, may be unenforceable
**Standard redline**: Replace with defined term (2-5 years from disclosure or termination). Offer trade secret carveout: "provided that Confidential Information constituting trade secrets shall be protected for so long as such information retains trade secret status."
**Fallback**: Accept 7-year term with trade secret carveout.

---

### Deviation: Mandatory Arbitration

**Frequency**: Moderate
**Risk**: Limits remedies (no injunctive relief without court involvement), may be more expensive for NDA disputes (which are typically straightforward)
**Standard redline**: Replace with litigation in agreed jurisdiction. Preserve right to seek injunctive relief in any court of competent jurisdiction.
**Fallback**: Accept arbitration with: (a) right to seek injunctive relief in court, (b) neutral arbitration rules (e.g., AAA, ICC, JAMS), (c) arbitration seat in reasonable location, (d) single arbitrator for disputes under threshold.

---

### Deviation: No Legal Compulsion Carveout

**Frequency**: Uncommon but serious when missing
**Risk**: Could prevent compliance with legal obligations (subpoena, regulatory inquiry, court order)
**Standard redline**: Add: "The Receiving Party may disclose Confidential Information to the extent required by applicable law, regulation, or legal process, provided that the Receiving Party gives prompt written notice to the Disclosing Party (to the extent legally permitted) to allow the Disclosing Party to seek a protective order or other appropriate remedy."
**Fallback**: None. This carveout is essential. Escalate if counterparty refuses.

---

## Triage Report Template

```
## NDA Triage Report

**Classification**: [GREEN / YELLOW / RED]
**Parties**: [party names]
**Type**: [Mutual / Unilateral (disclosing) / Unilateral (receiving)]
**Term**: [agreement duration] | **Survival**: [confidentiality duration]
**Governing Law**: [jurisdiction]
**Review Basis**: [Playbook / Default Standards]

## Screening Results

| # | Criterion | Status | Notes |
|---|-----------|--------|-------|
| 1 | Agreement Structure | [PASS/FLAG/FAIL] | [details] |
| 2 | Definition Scope | [PASS/FLAG/FAIL] | [details] |
| 3 | Receiving Party Obligations | [PASS/FLAG/FAIL] | [details] |
| 4 | Standard Carveouts | [PASS/FLAG/FAIL] | [which present/missing] |
| 5 | Permitted Disclosures | [PASS/FLAG/FAIL] | [details] |
| 6 | Term and Duration | [PASS/FLAG/FAIL] | [details] |
| 7 | Return and Destruction | [PASS/FLAG/FAIL] | [details] |
| 8 | Remedies | [PASS/FLAG/FAIL] | [details] |
| 9 | Problematic Provisions | [PASS/FLAG/FAIL] | [list any found] |
| 10 | Governing Law | [PASS/FLAG/FAIL] | [details] |

## Issues Found

### [Issue -- YELLOW/RED]
**What**: [description]
**Risk**: [what could go wrong]
**Suggested Fix**: [specific redline language]
**Fallback**: [alternative position]

## Recommendation
[Approve / Send for review with notes / Reject and counter]

## Routing
| Classification | Action | Timeline |
|---|---|---|
| GREEN | Approve per delegation of authority | Same day |
| YELLOW | Counsel review with flagged issues | 1-2 business days |
| RED | Full review, negotiation, or counterproposal | 3-5 business days |
```
