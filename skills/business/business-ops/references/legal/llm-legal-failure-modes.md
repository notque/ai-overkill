# LLM Legal Failure Modes

Where LLMs fail in legal analysis. Specific failure patterns, detection methods, and mitigation guards. Load this reference for every legal workflow mode.

> **Shared base**: Universal LLM failure modes (hallucination, overconfidence, generic output, arithmetic errors, stale knowledge) are documented in `skills/shared-patterns/llm-domain-failure-modes-base.md`. This file covers legal-specific failures only.

---

## Why Legal Is a High-Risk Domain for LLMs

Legal analysis has properties that amplify LLM weaknesses:

1. **Precision matters.** A single word ("shall" vs. "may", "and" vs. "or") changes legal meaning. LLMs optimize for plausible text, not precise legal language.
2. **Authority matters.** Legal analysis requires citing actual statutes, regulations, and case law. LLMs fabricate citations that look real but are not.
3. **Jurisdiction matters.** The same legal question has different answers in different jurisdictions. LLMs blend jurisdictions without flagging it.
4. **Currency matters.** Laws change. Training data has a cutoff. LLMs do not know what they do not know about recent changes.
5. **Consequences are asymmetric.** A plausible-sounding wrong answer can cause material harm. In most domains, a plausible wrong answer is merely unhelpful.

---

## Failure Mode Catalog

### 1. Fabricated Case Law and Citations

**What happens:** LLM generates realistic-looking case citations, statute numbers, or regulatory references that do not exist. Case names follow real naming conventions. Statute formats look correct. But the citations are invented.

**Detection signals:**
- Case name follows "[Name] v. [Name]" pattern but does not appear in legal databases
- Statute citation has correct format but wrong section number
- Regulation cited does not exist or was repealed
- LLM provides citation with unusual confidence (no hedging language)

**Mitigation:**
- Mark every case citation, statute number, and regulatory reference as "requires verification" and instruct the user to confirm with primary sources
- Use hedging: "regulations such as..." or "provisions similar to..." rather than citing specific sections
- For well-known, foundational statutes (GDPR, CCPA, HIPAA), cite the act name and general provision (e.g., "GDPR Article 28") but avoid citing specific subsections unless highly confident
- When the user needs specific citations, recommend legal research tools (Westlaw, Lexis, regulatory authority websites)
- Always include: "Verify all citations with authoritative sources before relying on them"

**Severity: CRITICAL.** Fabricated citations in legal filings have led to sanctions against attorneys. This is not a theoretical risk.

---

### 2. Jurisdiction Confusion

**What happens:** LLM blends legal principles from different jurisdictions without flagging the mix. Applies US law to UK contracts, EU regulations to Australian situations, California requirements to Texas entities. Often presents blended analysis as if it were universally applicable.

**Detection signals:**
- Analysis uses terms from one jurisdiction while discussing another (e.g., "reasonable person" standard in a civil law jurisdiction)
- Regulatory requirements cited are from a different jurisdiction than the one governing the contract
- Analysis assumes common law principles in a civil law jurisdiction (or vice versa)
- No jurisdiction specified but analysis implicitly assumes one

**Mitigation:**
- Always ask which jurisdiction governs before analyzing
- State explicitly which jurisdiction the analysis covers at the top of every output
- When multiple jurisdictions apply, analyze separately and note conflicts
- Flag when analysis may not apply to other jurisdictions: "This analysis applies to [jurisdiction]. Requirements may differ in other jurisdictions."
- Never default to US law -- ask first
- For cross-border matters, note that each element may be governed by different law

**Severity: HIGH.** Wrong jurisdiction analysis is worse than no analysis -- it creates false confidence.

---

### 3. Overconfident Analysis

**What happens:** LLM presents uncertain legal conclusions with the same confidence as well-established ones. Does not distinguish between settled law, evolving standards, and genuinely unsettled questions. Uses definitive language ("this violates..." "this is enforceable...") when the correct answer is "it depends" or "this is unsettled."

**Detection signals:**
- Absolute language without hedging: "This clause is unenforceable" (should be "this clause may be unenforceable in [jurisdiction] because...")
- No acknowledgment of counterarguments or alternative interpretations
- Presenting majority position as unanimous
- No mention of factual dependencies that could change the analysis
- Stating legal conclusions without identifying the governing standard or test

**Mitigation:**
- Use calibrated language consistently:

| Instead of | Use |
|-----------|-----|
| "This is illegal" | "This likely violates [specific provision] in [jurisdiction], though enforcement depends on [factors]" |
| "This is enforceable" | "Courts in [jurisdiction] have generally enforced similar provisions, subject to [conditions]" |
| "This is standard" | "This is common in [market/industry], though terms vary" |
| "You must do X" | "Under [regulation] in [jurisdiction], organizations meeting [criteria] are required to [obligation]" |

- Always note when an area of law is:
  - Settled (high confidence)
  - Evolving (moderate confidence, note recent developments)
  - Unsettled (low confidence, recommend counsel)
- Present both sides when reasonable arguments exist on each

**Severity: HIGH.** Overconfidence in legal analysis leads to uninformed decision-making.

---

### 4. Invented Regulatory Requirements

**What happens:** LLM fabricates specific regulatory requirements that sound plausible but do not exist. May invent filing deadlines, notification requirements, approval thresholds, or compliance obligations. Often combines real requirements from different frameworks into a fictional composite.

**Detection signals:**
- Specific numeric thresholds or deadlines that cannot be verified
- Requirements attributed to a regulation that does not actually contain them
- Composite requirements mixing elements from different frameworks
- Requirements that are "too specific to be wrong" but are not from the cited source

**Mitigation:**
- For well-known requirements (GDPR 72-hour breach notification, CCPA 45-day response), cite confidently
- For specific thresholds, deadlines, or filing requirements: state the general obligation and recommend verifying specific requirements with the regulatory authority or counsel
- Distinguish between: "this regulation requires [well-known general obligation]" and "verify the specific thresholds and deadlines with current regulatory guidance"
- Never invent specific dollar amounts for fines or penalties unless they are well-established maximums (e.g., GDPR 4% of global turnover)
- When in doubt, describe the type of obligation without fabricating specifics

**Severity: HIGH.** Acting on invented requirements wastes resources. Missing real requirements creates liability.

---

### 5. Missing Clause Interactions

**What happens:** LLM analyzes each contract clause in isolation, missing critical interactions between clauses. An indemnification clause that is "uncapped" may be effectively limited by a well-crafted LOL with narrow carveouts. A confidentiality clause may be expanded by a separate DPA. LLM flags issues that are already mitigated elsewhere, or misses issues created by clause combinations.

**Detection signals:**
- Flagging a risk in one clause without checking if another clause mitigates it
- Not cross-referencing indemnification with LOL
- Analyzing confidentiality without reference to the DPA (if any)
- Missing that survival clauses extend obligations beyond the term
- Not noting that definitions in one section affect terms used throughout

**Mitigation:**
- Read the entire contract before analyzing individual clauses (explicit instruction in contract review workflow)
- After individual clause analysis, perform a holistic cross-reference check:
  - Does LOL adequately cap indemnification? Are indemnification carveouts consistent with LOL carveouts?
  - Do confidentiality provisions and DPA provisions align? Conflict?
  - Do termination provisions account for survival clauses?
  - Are defined terms used consistently throughout?
- Flag clause interactions explicitly in the analysis
- Note when one clause mitigates a risk flagged in another

**Severity: MEDIUM-HIGH.** Missing interactions leads to either false alarms (flagging mitigated risks) or missed risks (not seeing how clauses combine to create exposure).

---

### 6. Stale Legal Knowledge

**What happens:** LLM's training data has a cutoff date. Laws enacted, amended, or repealed after that date are unknown to the model. LLM may confidently apply repealed provisions, miss new requirements, or be unaware of significant court decisions.

**Detection signals:**
- References to laws that may have been amended (check for recent privacy laws, which change frequently)
- Analysis based on frameworks that have been superseded (e.g., old EU SCCs)
- No mention of well-known recent developments in the area
- Confidently stating current status of rapidly evolving areas (AI regulation, cryptocurrency, social media)

**Areas of highest staleness risk:**
- Privacy and data protection (new state laws in US, EU developments, international frameworks)
- AI regulation (rapidly evolving globally)
- Cryptocurrency and digital assets
- Cross-border data transfers (adequacy decisions change)
- Employment law (remote work, gig economy, non-compete restrictions)
- ESG and sustainability reporting

**Mitigation:**
- Include a standard caveat for any regulatory analysis: "This analysis is based on information available as of [training cutoff]. Verify current regulatory requirements with authoritative sources."
- For rapidly evolving areas, explicitly flag that the law may have changed and recommend checking with counsel or regulatory authority websites
- Never state "this is current law" -- state "as of [knowledge cutoff], the applicable framework is..."
- Recommend specific authoritative sources for current information (regulatory authority websites, not secondary sources)

**Severity: MEDIUM-HIGH.** Applying repealed law or missing new requirements can cause concrete harm.

---

### 7. Template Overfitting

**What happens:** LLM applies a standard template or framework to a situation that does not fit. Uses boilerplate language when the situation requires specific, tailored analysis. Generates a response that looks professional but does not address the actual question.

**Detection signals:**
- Response follows a clear template but does not address the specific facts
- Boilerplate language that could apply to any situation
- Missing engagement with the unusual or difficult aspects of the question
- Response is generic where specific analysis was requested

**Mitigation:**
- After generating any templated response, check: does this address the specific facts and question?
- For unusual situations, note explicitly that standard templates may not apply
- When escalation triggers fire, do not force-fit a template -- escalate
- Include the specific facts in the analysis, not just the framework

**Severity: MEDIUM.** Template overfitting produces responses that look helpful but are not.

---

### 8. False Equivalence in Risk Assessment

**What happens:** LLM treats all risks as roughly equivalent, compressing scores toward the middle (3-4 range) and failing to differentiate between genuinely critical risks and minor concerns. May also assign extreme scores without justification.

**Detection signals:**
- All risks scored in the same narrow range
- No risk scored 1 or 5 on either dimension
- Critical risks (active litigation, data breach) scored the same as minor contract deviations
- No differentiation in urgency or escalation recommendations

**Mitigation:**
- Use the full 1-5 scale. A routine NDA with a known counterparty is a 1/1 risk. Active litigation with significant exposure is a 5/4.
- Require specific justification for each severity and likelihood score
- Cross-check: would a reasonable in-house counsel agree with this score?
- Compare relative scores: is this risk really the same severity as [other scored risk]?

**Severity: MEDIUM.** Score compression reduces the value of risk assessment by failing to prioritize.

---

### 9. Confidentiality and Privilege Blindness

**What happens:** LLM does not inherently understand attorney-client privilege, work product protection, or confidentiality obligations. May suggest actions that would waive privilege, recommend sharing privileged information, or fail to flag privilege considerations.

**Detection signals:**
- Recommending sharing legal analysis with opposing party or in non-privileged settings
- Not flagging that a document should be marked as privileged
- Suggesting inclusion of privileged content in non-privileged communications
- Not noting privilege considerations when recommending who to consult or share with

**Mitigation:**
- When generating legal analysis: note whether the output should be treated as privileged
- When recommending sharing or distribution: flag privilege considerations
- For incident briefs and litigation-adjacent matters: include privilege marking guidance
- Never recommend waiving privilege without explicitly flagging the implications

**Severity: MEDIUM.** Inadvertent privilege waiver can be costly and is often irreversible.

---

### 10. Precedent Bias

**What happens:** LLM defaults to common-law, US-centric legal reasoning even when analyzing situations governed by other legal systems. Assumes adversarial system, precedent-based reasoning, and common-law contract interpretation when civil law, statutory interpretation, or other frameworks may apply.

**Detection signals:**
- Analysis structured around "case law" in civil law jurisdictions
- Assuming freedom of contract principles in jurisdictions with mandatory terms
- Applying UCC concepts to non-US commercial transactions
- Using "reasonable person" standard where different standards apply

**Mitigation:**
- Identify the legal system (common law, civil law, mixed) before analyzing
- For civil law jurisdictions: focus on code provisions, not case precedent
- For non-US contracts: do not assume UCC, Restatement, or other US frameworks apply
- Ask about governing law before defaulting to any legal tradition

**Severity: MEDIUM.** Applying wrong legal tradition produces analysis that is internally consistent but fundamentally inapplicable.

---

## Guard Protocol Summary

Apply these guards to every legal analysis output:

| # | Guard | Implementation |
|---|-------|---------------|
| 1 | Jurisdiction stated | Every analysis names its governing jurisdiction at the top |
| 2 | Citations hedged | No citation presented as authoritative without "verify with authoritative sources" |
| 3 | Calibrated language | No absolutes. "Likely," "typically," "in most jurisdictions" unless truly certain |
| 4 | Staleness caveat | Note training cutoff for any regulatory analysis |
| 5 | Cross-reference check | After clause analysis, check for interactions between clauses |
| 6 | Escalation check | Before generating responses, check escalation triggers |
| 7 | Privilege awareness | Flag when output should be privileged or when privilege considerations arise |
| 8 | Full-scale scoring | Risk scores use full 1-5 range with specific justification |
| 9 | Specific engagement | Output addresses the specific facts, not just the general framework |
| 10 | Disclaimer present | "Analysis support, not legal advice. Review by qualified counsel required." |
