# LLM Sales Failure Modes

Where LLMs fail in sales work. This reference catalogs specific failure patterns, their causes, and the guardrails that prevent them. Load this reference for every sales mode.

> **Shared base**: Universal LLM failure modes (hallucination, overconfidence, generic output, arithmetic errors, stale knowledge) are documented in `skills/shared-patterns/llm-domain-failure-modes-base.md`. This file covers sales-specific failures only.

---

## Why Sales Is Especially Dangerous for LLMs

Sales output goes directly to prospects and customers. A fabricated detail in internal documentation is a bug. A fabricated detail in a customer-facing email is a credibility-destroying event that can kill a deal and damage a company's reputation.

Sales work requires:
- **Factual accuracy** about companies, people, and products (LLMs hallucinate these)
- **Specific personalization** that cannot be generic (LLMs default to generic)
- **Numeric precision** in forecasts and financials (LLMs guess and round)
- **Honest uncertainty** about unknowns (LLMs fill gaps with plausible fiction)
- **Tone calibration** per relationship stage (LLMs default to cheerful formality)

Every failure mode below has been observed in production sales AI output.

---

## Failure Mode Catalog

### 1. Company Detail Fabrication

**What happens**: LLM generates plausible-sounding but fictional company details: revenue figures, employee counts, founding dates, office locations, product features, customer lists.

**Why it happens**: The LLM has training data about many companies. It pattern-matches to produce a "typical" company profile that sounds right but may contain details from other companies, outdated information, or pure fabrication.

**Example**:
```
BAD: "Acme Corp, founded in 2015, has 450 employees and $40M ARR."
(None of these numbers were in search results -- LLM fabricated plausible values)

GOOD: "Acme Corp: [founded year not found]. Employee count: approximately 200-500
based on LinkedIn estimate. Revenue: not publicly disclosed."
```

**Guardrail**: Every company fact must have a source (search result, user input, or public filing). State "not found" or "not publicly available" for missing data. Never fill gaps with plausible estimates unless explicitly labeled as estimates.

---

### 2. Invented Relationship History

**What happens**: LLM fabricates prior interactions, meeting history, or relationship context that never occurred.

**Why it happens**: The call prep or pipeline context suggests an existing relationship. The LLM generates "what would have happened" based on typical sales interactions, presenting fiction as history.

**Example**:
```
BAD: "In your last call with Sarah, she mentioned concerns about implementation
timeline and asked about SOC 2 compliance."
(User never provided this information -- LLM invented a plausible prior call)

GOOD: "No prior interaction history provided. First contact assumptions apply."
```

**Guardrail**: Only reference history the user explicitly provided (pasted notes, described interactions, uploaded transcripts). Never assume or generate prior interactions. If the user says "prep me for a follow-up call," ask what happened in the previous interaction.

---

### 3. Generic Outreach Disguised as Personalization

**What happens**: LLM produces email that has the structure of personalized outreach but uses interchangeable content. The "personalization" could apply to any prospect.

**Why it happens**: The LLM learned the pattern of personalized email (specific opening + pain point + proof + CTA) but fills slots with generic content rather than actual research findings.

**Detection test**: Replace the company name and person name with any other prospect. If the email still reads naturally, it's generic.

**Example**:
```
BAD: "Hi Sarah, I noticed you're doing great work at Acme Corp. Companies in
your industry often struggle with scaling their operations efficiently.
We've helped similar companies achieve better results."

GOOD: "Hi Sarah, saw Acme's Q3 announcement about expanding into APAC.
Teams opening new regions usually hit data residency complexity first --
that's where [specific capability] helped [Named Customer] cut their
compliance timeline from 6 months to 6 weeks."
```

**Guardrail**: The opening sentence must reference a fact discovered in research that is only true of this specific person or company. The proof point must name a real customer with a real result. Apply the substitution test before output.

---

### 4. Financial Data Hallucination

**What happens**: LLM generates specific financial figures (revenue, ARR, growth rate, valuation, market cap) that were not found in search results.

**Why it happens**: Financial data appears frequently in training data. The LLM generates numbers that "feel right" for a company of that size/stage. These numbers are frequently wrong by 2-10x.

**Example**:
```
BAD: "With estimated ARR of $25M and 40% year-over-year growth..."
(These numbers were not in any search result -- LLM extrapolated)

GOOD: "Revenue not publicly disclosed. Last known funding: Series B,
$30M in 2023 (source: TechCrunch). Revenue likely in $10-50M range
based on stage, but this is speculative."
```

**Guardrail**: Financial figures only from verified sources: SEC filings, press releases with specific numbers, Crunchbase (funding data), earnings reports. All estimates must be explicitly labeled as estimates with reasoning. Never present an estimate as a fact.

---

### 5. Forecast Optimism Bias

**What happens**: LLM inflates forecast probabilities, includes unlikely deals to make the forecast look healthier, and avoids recommending deal removal.

**Why it happens**: LLMs are trained on helpful, positive-toned text. "This deal is likely to close" pattern-matches better with the training distribution than "This deal should be removed from your pipeline."

**Example**:
```
BAD: "Based on the strong engagement signals, this deal has a good chance
of closing this quarter."
(Deal has no activity in 30 days, close date pushed twice, single-threaded)

GOOD: "This deal has three critical risk factors: 30 days inactive,
close date pushed twice, single contact. Recommend qualifying out
or pushing to next quarter."
```

**Guardrail**: Use standard stage probabilities with risk adjustments (see pipeline-analysis.md). Risk adjustments only reduce probability, never increase it. Always flag deals for removal when evidence warrants. Include "Deals to Consider Removing" section in every pipeline review.

---

### 6. Template-Shaped Email Output

**What happens**: LLM uses markdown formatting in customer-facing emails: **bold text**, # headers, * bullet points. These render as literal characters in email clients.

**Why it happens**: Markdown is the LLM's native formatting language. It defaults to markdown for all structured output, including emails.

**Example**:
```
BAD:
**What we discussed:**
- **Budget**: $50K allocated
- **Timeline**: Q2 implementation
- **Next steps**: Schedule technical review

GOOD:
Here's what we discussed:
- Budget: $50K allocated
- Timeline: Q2 implementation
- Next steps: Schedule technical review
```

**Guardrail**: All customer-facing email output must use plain text only. No asterisks, no hash symbols, no square brackets, no formatted bullet points. Use plain dashes for lists. Test: copy the output into a plain text editor. Does it look like a normal email? If you see * or # characters, reformat.

---

### 7. Fabricated Competitive Claims

**What happens**: LLM invents competitor pricing, features, limitations, or customer claims that are not backed by search results.

**Why it happens**: The LLM has some training data about competitors but not enough to be accurate. It fills gaps with plausible-sounding claims that may be outdated, incorrect, or fabricated.

**Example**:
```
BAD: "Competitor X charges $50/seat/month and doesn't support SSO on
their standard plan."
(Neither claim was verified in search results)

GOOD: "Competitor X: Pricing not publicly listed (enterprise quote required).
SSO support: Available on Enterprise tier per their pricing page
(source: competitor.com/pricing, accessed 2026-05-01)."
```

**Guardrail**: Every competitive claim must link to a source. If the source is a search result, note the URL and access date. If the source is user-provided field intel, label it as such. If a claim cannot be sourced, either drop it or mark it as "unverified -- confirm before using in customer conversations."

---

### 8. Over-Promising in Follow-Up Emails

**What happens**: LLM includes commitments in follow-up emails that the user did not authorize: deliverables, timelines, introductions, discounts.

**Why it happens**: The LLM generates what a "good follow-up" looks like based on training data. Good follow-ups include specific commitments. The LLM generates plausible commitments that the seller may not have made.

**Example**:
```
BAD: "As discussed, I'll send over a custom pricing proposal by Friday
and schedule a call with our CTO for a technical deep-dive."
(User only committed to sending a case study)

GOOD: "As discussed, I'll send over the [Industry] case study this week.

Let me know if a technical deep-dive with our engineering team would
be useful as a next step."
```

**Guardrail**: Follow-up emails only include commitments the user explicitly stated were made. If the user described the call but didn't specify commitments, ask: "What did you commit to sending or doing?" Do not infer commitments from the conversation summary.

---

### 9. Ignoring Disqualification Signals

**What happens**: LLM always finds reasons to pursue a deal, never recommends walking away or disqualifying.

**Why it happens**: The LLM's training data rewards helpfulness and optimism. "We should pursue this" matches the helpful pattern better than "Walk away from this deal." Sales training materials emphasize persistence.

**Example**:
```
BAD: "While there are some challenges, this deal still has potential
and I recommend continued engagement."
(Prospect explicitly said they have no budget, no timeline, and are
under contract with a competitor for 2 more years)

GOOD: "Disqualification recommended. Three disqualifying factors:
1. No budget allocated
2. No timeline for evaluation
3. Locked into competitor contract through 2028
Recommend: Add to nurture list. Re-engage 6 months before contract
renewal (early 2028)."
```

**Guardrail**: Define disqualification criteria and apply them without hesitation. When 2+ disqualifying factors are present, recommend disqualification first, with a path to re-engage later. Disqualifying a bad deal is more valuable than wasting time on it.

**Disqualification criteria**:

| Factor | Threshold |
|--------|----------|
| Budget | No budget AND no path to budget |
| Authority | Cannot access decision maker after 2 attempts |
| Need | No identified pain point after discovery |
| Timeline | No evaluation window in next 6 months |
| Fit | Product does not solve their stated problem |
| Competition | Locked into competitor contract with no exit |
| Engagement | No response after full follow-up sequence |

---

### 10. Tone Miscalibration

**What happens**: LLM uses the same tone regardless of deal stage, relationship depth, or prospect seniority.

**Why it happens**: The LLM defaults to a "professional but friendly" tone that works for initial outreach but feels wrong at other stages.

| Stage | Correct Tone | LLM Default | Problem |
|-------|-------------|-------------|---------|
| Cold outreach | Direct, value-focused | Over-formal | Feels stiff, unnatural |
| Discovery | Curious, consultative | Solution-pushing | Premature pitching |
| Negotiation | Confident, flexible | Eager to please | Undermines pricing power |
| Follow-up | Brief, specific | Cheerful, wordy | Wastes prospect's time |
| Re-engagement | Low-pressure, new value | Guilt-inducing | "Just checking in" pattern |
| Executive comms | Concise, strategic | Feature-detailed | Misses the altitude |

**Guardrail**: Calibrate tone to deal stage and audience seniority. Executives get shorter, more strategic communication. Technical evaluators get deeper, more precise language. Early-stage prospects get value-first, question-driven outreach. Late-stage prospects get direct, action-oriented communication.

---

## Meta-Guardrails

These rules apply across all sales modes.

### The Verification Rule

Before outputting any factual claim about a company, person, product, or financial metric, answer: "Where did I learn this?" If the answer is "from my training data" or "it seems likely," do not present it as fact. Either:
1. Search for verification
2. Label it as an assumption
3. Omit it

### The Substitution Test

For personalized content (outreach, call prep): Replace the prospect's name and company with any other. If the content still reads naturally, the personalization is fake. Rewrite.

### The Commitment Audit

For follow-up emails: List every commitment in the email. Cross-reference against what the user explicitly stated. Remove any commitment not confirmed by the user.

### The Negativity Test

For pipeline reviews and forecasts: Count the number of positive vs. negative assessments. If every deal gets a positive assessment, the analysis is biased. Force at least one "consider removing" recommendation per review.

### The Source Test

For competitive intelligence: Every claim about a competitor must have a source notation. "Source: competitor.com/pricing" or "Source: G2 review, Oct 2025" or "Source: user-provided field intel." Claims without sources get marked "unverified" or removed.

---

## Failure Mode Quick Reference

| # | Failure Mode | One-Line Prevention |
|---|-------------|-------------------|
| 1 | Company detail fabrication | Every fact needs a source. "Not found" is better than wrong. |
| 2 | Invented relationship history | Only reference what the user explicitly provided. |
| 3 | Generic outreach | Substitution test: if another prospect fits, rewrite. |
| 4 | Financial hallucination | Only from SEC filings, press releases, or Crunchbase. Label estimates. |
| 5 | Forecast optimism | Standard probabilities. Risk adjustments only decrease. |
| 6 | Markdown in emails | Plain text only. No asterisks, no headers. |
| 7 | Fake competitive claims | Every claim needs a source URL or "unverified" label. |
| 8 | Over-promising in follow-ups | Only include commitments the user confirmed. |
| 9 | Ignoring disqualification | 2+ disqualifying factors = recommend walking away. |
| 10 | Tone miscalibration | Match tone to deal stage and audience seniority. |
