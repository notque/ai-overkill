# Contract Review: Clause-by-Clause Methodology

Full analysis methodology for contract review. Covers every material clause category with key review points, common issues, and LLM-specific failure modes.

---

## Pre-Analysis Protocol

Before analyzing any clause in isolation:

1. **Read the entire contract.** Clauses interact. An uncapped indemnity may be partially mitigated by a broad limitation of liability. A narrow confidentiality definition may be expanded by a separate DPA.
2. **Identify the contract type.** SaaS, professional services, license, partnership, procurement. The type determines which clauses are most material.
3. **Determine the user's side.** Vendor, customer, licensor, licensee, partner. This fundamentally changes the analysis -- limitation of liability protections favor different parties depending on position.
4. **Note the governing law.** Jurisdiction affects enforceability of specific clauses (e.g., non-compete enforceability, consequential damages exclusions, indemnification scope).

---

## Clause Categories

### 1. Limitation of Liability (LOL)

**Key elements to review:**

| Element | What to Check |
|---------|--------------|
| Cap amount | Fixed dollar, multiple of fees, or uncapped |
| Cap symmetry | Mutual or different per party |
| Cap carveouts | What liabilities are excluded from the cap |
| Consequential damages | Excluded? Mutual exclusion? |
| Consequential carveouts | What escapes the consequential damages exclusion |
| Cap period | Per-claim, per-year, or aggregate |

**Common issues:**
- Cap at a fraction of fees paid (e.g., "fees paid in prior 3 months" on a low-value contract) -- effective cap may be negligibly small
- Asymmetric carveouts favoring the drafter -- one party's breaches are capped while the other's are not
- Broad carveouts that eliminate the cap ("any breach of Section X" where X covers most obligations)
- No consequential damages exclusion for one party
- Cap referencing "fees paid" rather than "fees payable" -- disadvantages the receiving party early in a multi-year deal

**LLM failure modes:**
- Analyzing LOL without cross-referencing indemnification clause -- an indemnity carved out from the cap effectively creates uncapped liability
- Missing that "super cap" carveouts (IP infringement, confidentiality breach, data breach) are common and often at a higher multiple (2-3x fees)
- Failing to note that consequential damages exclusions may be unenforceable in certain jurisdictions or for certain claim types (e.g., willful misconduct)
- Assuming US-style LOL structure when reviewing contracts governed by civil law jurisdictions

**GREEN**: Cap at 12+ months of fees (or higher), mutual, standard carveouts, mutual consequential damages exclusion.
**YELLOW**: Cap at 6-12 months of fees, minor asymmetry, 1-2 additional carveouts.
**RED**: No LOL clause, uncapped liability, cap below 6 months, broad asymmetric carveouts.

---

### 2. Indemnification

**Key elements to review:**

| Element | What to Check |
|---------|--------------|
| Mutual vs. unilateral | Both parties indemnify, or only one |
| Triggers | IP infringement, data breach, bodily injury, breach of reps |
| Cap | Subject to LOL cap, separate cap, or uncapped |
| Procedure | Notice requirements, right to control defense, right to settle |
| Mitigation | Indemnitee obligation to mitigate |
| LOL relationship | How indemnification interacts with the liability cap |

**Common issues:**
- Unilateral indemnification for IP infringement when both parties contribute IP
- "Any breach" indemnification -- converts the entire agreement into uncapped liability
- No right to control defense of claims
- Indefinite survival of indemnification obligations
- No mitigation obligation on the indemnitee
- Indemnification for third-party claims only vs. direct claims -- scope matters

**LLM failure modes:**
- Failing to check whether indemnification obligations are carved out from the LOL cap -- this is the most common miss
- Not recognizing that "indemnify and hold harmless" may have different legal meanings in some jurisdictions
- Missing the interplay between indemnification scope and insurance requirements
- Overstating indemnification risks without noting that practical enforcement requires third-party claims in most formulations

**GREEN**: Mutual for core risks (IP, data breach), capped, standard procedures.
**YELLOW**: Unilateral IP indemnification (common market position), cap at LOL cap level.
**RED**: Uncapped, "any breach" scope, no defense control, indefinite survival.

---

### 3. Intellectual Property

**Key elements to review:**

| Element | What to Check |
|---------|--------------|
| Pre-existing IP | Each party retains their own |
| Developed IP | Ownership of IP created during engagement |
| Work-for-hire | Scope of work-for-hire provisions |
| License grants | Scope, exclusivity, territory, sublicensing |
| Open source | Obligations and restrictions |
| Feedback clauses | Grants on suggestions or improvements |

**Common issues:**
- Broad IP assignment capturing the customer's pre-existing IP
- Work-for-hire extending beyond deliverables to tools, methodologies, or frameworks
- Unrestricted feedback clauses granting perpetual, irrevocable licenses on any suggestion
- License scope broader than the business relationship requires
- No open source disclosure or compliance obligations
- Assignment of "improvements" or "derivative works" without defining these terms

**LLM failure modes:**
- Confusing IP ownership with IP licensing -- assignment transfers ownership permanently; a license grants usage rights
- Not flagging that work-for-hire has specific legal requirements (US Copyright Act Section 101) and may not apply to all work products
- Missing that "background IP" / "pre-existing IP" definitions are critical -- if undefined, disputes arise about what each party brought to the relationship
- Failing to note that IP provisions may be unenforceable without adequate consideration

**GREEN**: Pre-existing IP retained, developed IP ownership appropriate for deal structure, reasonable license scope.
**YELLOW**: Broad feedback clause, license scope wider than needed, work-for-hire scope slightly broad.
**RED**: Pre-existing IP assignment, unrestricted work-for-hire, no IP provisions at all.

---

### 4. Data Protection

**Key elements to review:**

| Element | What to Check |
|---------|--------------|
| DPA requirement | Is a DPA needed? Is one attached? |
| Controller/processor | Correct classification of roles |
| Sub-processors | Rights and notification obligations |
| Breach notification | Timeline (72 hours for GDPR) |
| Cross-border transfers | SCCs, adequacy decisions, BCRs |
| Deletion/return | Obligations on termination |
| Security | Requirements and audit rights |
| Purpose limitation | Processing limited to stated purposes |

**DPA review checklist (GDPR Article 28):**
- Subject matter, duration, nature, purpose clearly defined
- Type of personal data and categories of data subjects specified
- Processor processes only on documented instructions
- Confidentiality commitments for personnel
- Appropriate technical and organizational security measures (Article 32)
- Sub-processor requirements: written authorization, notification of changes, same obligations flow down
- Data subject rights assistance
- Breach notification without undue delay (24-48 hours to enable 72-hour regulatory deadline)
- Deletion or return on termination
- Audit rights (SOC 2 Type II + right to audit upon cause is standard compromise)

**Common issues:**
- No DPA when personal data is processed
- Blanket sub-processor authorization without notification
- Breach notification timeline exceeding regulatory requirements
- No cross-border transfer protections for international data flows
- Inadequate deletion provisions (no timeline, no certification)
- Outdated SCCs (must use June 2021 EU SCCs)
- No data processing locations specified

**LLM failure modes:**
- Assuming GDPR applies universally -- must check which regulations apply based on data subjects' locations and organization's presence
- Confusing data controller and data processor roles -- misclassification changes the entire obligation structure
- Not recognizing that SCC modules matter (C2P, C2C, P2P, P2C) -- wrong module invalidates the transfer mechanism
- Stating specific breach notification timelines without noting jurisdiction variations
- Missing that DPA liability must align with (not conflict with) the main services agreement

**GREEN**: DPA attached, correct roles, standard sub-processor provisions, compliant transfer mechanisms, audit rights.
**YELLOW**: DPA present but missing one element, breach timeline slightly long, general sub-processor authorization with notification.
**RED**: No DPA for personal data processing, no transfer protections, blanket sub-processor authorization, no audit rights.

---

### 5. Confidentiality

**Key elements to review:**

| Element | What to Check |
|---------|--------------|
| Scope | Definition of confidential information |
| Term | Duration of obligations |
| Standard carveouts | Public knowledge, prior possession, independent development, third-party receipt, legal compulsion |
| Return/destruction | Obligations and timeline on termination |
| Permitted disclosures | Employees, contractors, advisors, affiliates |
| Residuals | Whether residuals clause exists and its scope |

**Common issues:**
- Overbroad definition capturing all information regardless of marking
- Missing independent development carveout (creates risk that internal work is claimed as derived)
- Perpetual obligations without trade secret justification
- No retention exception for legal/compliance backups
- Broad residuals clause effectively granting a license to use confidential information

**LLM failure modes:**
- Not distinguishing between confidentiality provisions in standalone NDAs vs. embedded in commercial agreements (different materiality)
- Missing that "residuals" clauses are contentious and often a deal point
- Failing to cross-reference confidentiality with the separate DPA (if any) for data-specific obligations

**GREEN**: Reasonable scope, standard carveouts, 2-5 year term, return/destruction with retention exception.
**YELLOW**: Broader scope, 5-7 year term, missing one carveout, narrow residuals.
**RED**: Overbroad definition, perpetual term, missing critical carveouts, broad residuals.

---

### 6. Representations and Warranties

**Key elements to review:**

| Element | What to Check |
|---------|--------------|
| Scope | What is warranted (authority, non-infringement, functionality, compliance) |
| Disclaimers | "As-is" disclaimers, exclusion of implied warranties |
| Survival | How long warranties survive after termination |
| Remedy | Exclusive remedy for warranty breach vs. general remedies |

**Common issues:**
- No warranty of non-infringement from the provider
- "As-is" disclaimer on services that should have functionality warranties
- Warranty survival too short to discover issues
- No remedy specified for warranty breach (defaults to general remedies, which may be more favorable)

**LLM failure modes:**
- Failing to note that warranty disclaimers may be unenforceable for certain types of warranties in certain jurisdictions (e.g., implied warranties of merchantability under UCC may require conspicuous disclaimer)
- Not cross-referencing warranties with indemnification -- a warranty of non-infringement typically pairs with an IP indemnification obligation

**GREEN**: Mutual authority reps, appropriate functionality warranties, reasonable disclaimers, 12+ month survival.
**YELLOW**: Limited warranties, short survival, broad disclaimers on services.
**RED**: No warranties, warranty period shorter than a billing cycle, hidden "as-is" for core deliverables.

---

### 7. Term and Termination

**Key elements to review:**

| Element | What to Check |
|---------|--------------|
| Initial term | Length and appropriateness for deal |
| Renewal | Auto-renewal terms, notice period, renewal term length |
| Termination for convenience | Available? Notice period? Early termination fees? |
| Termination for cause | Cure period? What constitutes cause? |
| Effects | Data return, transition assistance, survival clauses |
| Wind-down | Period and obligations |

**Common issues:**
- Long initial terms with no termination for convenience
- Auto-renewal with short notice windows (30 days for annual renewal is too short)
- No cure period for termination for cause
- Inadequate transition assistance provisions
- Survival clauses that effectively extend the agreement indefinitely
- Early termination fees calculated on remaining term rather than actual damages

**LLM failure modes:**
- Not flagging the interaction between auto-renewal and notice periods -- a 30-day notice window on a 3-year renewal effectively locks in for 3 years if the window is missed
- Missing that "termination for cause" definitions vary -- "material breach" is standard but "any breach" lowers the threshold dramatically
- Failing to check what happens to paid-but-unused fees on termination

**GREEN**: Reasonable term, 90+ day renewal notice, termination for convenience, 30-day cure, adequate transition.
**YELLOW**: 60-day renewal notice, limited termination for convenience, 15-day cure.
**RED**: No termination for convenience, auto-renewal with <30-day notice, no cure period, no transition assistance.

---

### 8. Governing Law and Dispute Resolution

**Key elements to review:**

| Element | What to Check |
|---------|--------------|
| Choice of law | Governing jurisdiction |
| Dispute mechanism | Litigation, arbitration, mediation first |
| Venue | Court or arbitration seat |
| Arbitration rules | Which rules, number of arbitrators, seat |
| Jury waiver | Present? Mutual? |
| Class action waiver | Present? Enforceable? |
| Prevailing party fees | Attorney's fees provision |

**Common issues:**
- Unfavorable jurisdiction (unusual, remote, or hostile venue)
- Mandatory arbitration with rules favoring the drafter (e.g., drafter chooses arbitrator)
- Jury waiver without corresponding protections
- No escalation process before formal dispute resolution
- Governing law and venue in different jurisdictions (creates conflicts)

**LLM failure modes:**
- Assuming all jurisdictions are equivalent -- Delaware, New York, California, and England are standard commercial jurisdictions; others may present enforcement challenges
- Not recognizing that arbitration vs. litigation choice has significant cost, speed, confidentiality, and appeal implications
- Stating that a particular governing law is "unfavorable" without asking what the user's preferred jurisdiction is
- Missing that choice of law may not be enforceable for certain claims (e.g., employment claims, consumer protection)

**GREEN**: Well-established commercial jurisdiction, consistent governing law and venue, reasonable dispute mechanism.
**YELLOW**: Acceptable but non-preferred jurisdiction, mandatory arbitration with standard rules.
**RED**: Problematic jurisdiction, mandatory arbitration with drafter-favorable rules, governing law and venue misaligned.

---

### 9. Insurance

**Key elements to review:**

| Element | What to Check |
|---------|--------------|
| Coverage types | CGL, E&O/professional liability, cyber, workers' comp |
| Minimums | Dollar amounts appropriate for deal size and risk |
| Evidence | Certificate of insurance requirements |
| Additional insured | Whether the counterparty must be named |
| Notification | Obligation to notify of policy changes or cancellation |

**Common issues:**
- No insurance requirements when the deal involves material risk
- Minimums too low for the contract value
- No cyber insurance when data is being processed
- No requirement to maintain coverage for the term of the agreement

**GREEN**: Appropriate coverage types, reasonable minimums, standard COI requirements.
**YELLOW**: Missing one coverage type, minimums below ideal but present.
**RED**: No insurance clause for a material engagement, or minimums grossly inadequate.

---

### 10. Assignment

**Key elements to review:**
- Consent requirements for assignment
- Change of control provisions
- Exceptions (affiliates, restructuring)
- Whether consent can be unreasonably withheld

**Common issues:**
- No assignment clause (defaults to applicable law, which varies)
- Unilateral assignment right for one party only
- Change of control exception that allows assignment to a competitor

---

### 11. Force Majeure

**Key elements to review:**
- Scope of qualifying events
- Notification requirements
- Duration threshold before termination rights trigger
- Whether pandemic/epidemic is included
- Whether the clause covers performance obligations only or payment obligations too

---

### 12. Payment Terms

**Key elements to review:**
- Net terms (Net 30 standard; Net 60+ disadvantages the payee)
- Late payment interest and fees
- Tax responsibilities
- Price escalation mechanisms
- Currency and exchange rate risk
- Right to suspend services for non-payment

---

## Redline Generation Standards

When generating redlines for YELLOW and RED deviations:

```
**Clause**: [Section reference and clause name]
**Current language**: "[exact quote]"
**Proposed redline**: "[specific alternative language]"
**Rationale**: [1-2 sentences, suitable for counterparty]
**Priority**: [Must-have / Should-have / Nice-to-have]
**Fallback**: [Alternative position if primary redline rejected]
```

**Rules:**
- Be specific -- provide exact language ready to insert, not vague guidance
- Be balanced -- firm on critical points, commercially reasonable on others
- Provide fallback positions for YELLOW items
- Prioritize -- not all redlines are equal
- Consider the relationship -- new vendor vs. strategic partner vs. commodity supplier

---

## Negotiation Priority Framework

**Tier 1 -- Must-Haves (Deal Breakers):**
- Uncapped or materially insufficient liability protections
- Missing data protection requirements for regulated data
- IP provisions jeopardizing core assets
- Terms conflicting with regulatory obligations

**Tier 2 -- Should-Haves (Strong Preferences):**
- LOL cap adjustments within range
- Indemnification scope and mutuality
- Termination flexibility
- Audit and compliance rights

**Tier 3 -- Nice-to-Haves (Concession Candidates):**
- Preferred governing law (if alternative is acceptable)
- Notice period preferences
- Minor definitional improvements
- Insurance certificate requirements

**Strategy**: Lead with Tier 1. Trade Tier 3 concessions to secure Tier 2 wins. Never concede Tier 1 without escalation.

---

## Holistic Assessment Checklist

After individual clause analysis, assess the contract holistically:

- [ ] Overall risk allocation balanced or appropriately skewed for the deal structure?
- [ ] Liability protections consistent across clauses (no clause undermining another)?
- [ ] Indemnification and LOL interact correctly?
- [ ] Data protection provisions adequate for the data involved?
- [ ] Termination rights provide adequate exit options?
- [ ] Survival clauses reasonable in scope and duration?
- [ ] Commercial terms (payment, pricing, SLA) align with business expectations?
