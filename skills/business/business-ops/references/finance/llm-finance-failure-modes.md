# LLM Finance Failure Modes

Where LLMs fail in finance work. Load this reference for every finance task as a guard rail. Each failure mode includes the pattern, why it happens, and the mitigation.

> **Shared base**: Universal LLM failure modes (hallucination, overconfidence, generic output, arithmetic errors, stale knowledge) are documented in `skills/shared-patterns/llm-domain-failure-modes-base.md`. This file covers finance-specific failures only.

---

## Category 1: Arithmetic Errors

LLMs do not compute. They predict tokens that look like computation. Every number in LLM-generated financial output must be verified.

### Wrong Sums

**Pattern**: Three line items ($127K, $89K, $214K) totaled as $420K. Actual: $430K.

**Why**: The model generates a plausible-looking total rather than computing one. The error is usually small enough to look correct on casual inspection.

**Mitigation**: Re-derive every total from its components. Do not trust any sum, subtotal, or grand total without explicit verification. When possible, use a script or calculator for arithmetic.

### Percentage Errors

**Pattern**: $28K variance on $500K base reported as "4.6%". Actual: 5.6%.

**Why**: The model may divide by the wrong base, transpose digits, or round incorrectly.

**Mitigation**: Recompute every percentage: variance / base x 100. Verify the base is correct (budget, prior period, actual — whichever was specified). State the formula used.

### Sign Errors

**Pattern**: Favorable revenue variance presented as unfavorable, or vice versa.

**Why**: The model confuses the direction convention. For revenue, actual > budget = favorable. For expenses, actual > budget = unfavorable. The model sometimes applies the wrong convention.

**Mitigation**: Apply the sign convention table explicitly:

| Line Type | Actual > Comparison | Actual < Comparison |
|-----------|-------------------|-------------------|
| Revenue / Income | Favorable (+) | Unfavorable (-) |
| Expense / COGS | Unfavorable (-) | Favorable (+) |

### Rounding Cascade

**Pattern**: Individual items rounded, then summed. Rounded sum differs from sum-then-round.

**Why**: Premature rounding introduces cumulative error. Three items at $33.33K each: rounded individually = $33K + $33K + $33K = $99K. Actual sum = $100K.

**Mitigation**: Carry full precision through calculations. Round only at the final presentation step.

### Debit/Credit Imbalance

**Pattern**: Entry presented as "balanced" with $150K debit and $145K credit.

**Why**: The model generates the entry line by line and does not verify the sum constraint at the end.

**Mitigation**: After generating any journal entry, verify: sum(all debits) == sum(all credits). This is an absolute constraint — no tolerance, no rounding exception.

---

## Category 2: Fabricated Standards and Citations

LLMs generate confident-sounding references to accounting standards that do not exist.

### Invented ASC/IFRS Paragraph Numbers

**Pattern**: "Per ASC 842-30-55-12, the lessee must..." when no such paragraph exists, or the paragraph says something different.

**Why**: The model has seen many ASC citations in training data and generates plausible-looking ones. The topic-level code (e.g., ASC 842 for leases) is usually correct. The sub-paragraph is often wrong.

**Mitigation**: 
- Cite at the topic level only: "Per ASC 842 (Leases)..." 
- Never cite specific paragraph numbers unless verified against the actual codification
- When uncertain: "Consult the relevant ASC guidance for [topic]"
- Flag all standard citations for professional verification

### Misapplied Rules

**Pattern**: Applying lease accounting (ASC 842) rules to a service contract, or revenue recognition (ASC 606) rules to an investment.

**Why**: The model pattern-matches on surface features (contract with payments over time) without verifying scope applicability.

**Mitigation**: State the standard being applied and its scope. Let the professional verify that the standard applies to the specific transaction.

### Conflated GAAP and IFRS

**Pattern**: Mixing US GAAP and IFRS rules in the same analysis without distinguishing them.

**Why**: Training data includes both frameworks. The model does not maintain framework boundaries.

**Mitigation**: 
- Default to US GAAP unless the user specifies IFRS
- State which framework is being applied
- Never blend rules from different frameworks without explicit callout

### Superseded Guidance

**Pattern**: Referencing pre-ASC 606 revenue recognition rules (e.g., SAB 101/104) or pre-ASC 842 lease rules (FAS 13).

**Why**: Training data includes historical guidance that has been superseded.

**Mitigation**: Flag when guidance may have been superseded. Key supersession dates:

| Old Standard | Replaced By | Effective |
|-------------|------------|-----------|
| SAB 101/104, SOP 97-2 | ASC 606 (Revenue) | 2018 |
| FAS 13 | ASC 842 (Leases) | 2019 |
| FAS 5 (loss contingencies) | ASC 326 (CECL for credit losses) | 2020 |
| FAS 141R | ASC 805 (Business Combinations) | 2009 |

---

## Category 3: Hallucinated Account Codes and Chart of Accounts

### Fabricated Account Numbers

**Pattern**: LLM generates "4100 — Product Revenue" or "6200 — Salaries" when no chart of accounts was provided.

**Why**: These are common account codes in training data. The model generates plausible defaults rather than acknowledging it lacks the information.

**Mitigation**: 
- Never generate account codes unless provided by the user
- Use descriptive placeholders: `[Revenue Account]`, `[Salary Expense Account]`
- If the user provides a partial chart, use only the codes given and flag gaps

### Assumed Chart Structure

**Pattern**: LLM assumes a specific numbering convention (1xxx = Assets, 2xxx = Liabilities, etc.) that may not match the user's system.

**Why**: This convention is common but not universal. Many organizations use different numbering schemes.

**Mitigation**: Ask for the user's chart of accounts or use descriptive names rather than assumed codes.

---

## Category 4: Materiality and Judgment Errors

### No Materiality Threshold Applied

**Pattern**: Investigating a $500 variance on a $50M revenue line. Generating 200-word narratives for immaterial items.

**Why**: The model treats all variances as equally important. It has no inherent sense of materiality.

**Mitigation**: Apply materiality thresholds before investigation. If no thresholds are provided, ask for them. Suggest defaults based on organization size.

### Wrong Materiality Benchmark

**Pattern**: Using net income as the materiality base for a balance sheet assertion, or total assets as the base for an income statement item.

**Why**: The model does not consistently match the benchmark to the financial statement element.

**Mitigation**: 

| Financial Statement | Typical Benchmark |
|--------------------|-------------------|
| Income statement | Revenue or pre-tax income |
| Balance sheet | Total assets or equity |
| Cash flow | Cash from operations |

### Inconsistent Materiality Application

**Pattern**: Investigating a 3% variance on one line while ignoring an 8% variance on another of similar magnitude.

**Why**: The model processes items sequentially and may lose track of the threshold applied to earlier items.

**Mitigation**: Apply thresholds to ALL line items in a single pass. Present results in a table showing which items exceed thresholds and which do not.

---

## Category 5: Period and Temporal Errors

### Wrong Period Allocation

**Pattern**: December services booked as January expense because the invoice date is in January.

**Why**: The model may confuse invoice date with service date. Under accrual accounting, the expense period is when the service was received, not when it was invoiced or paid.

**Mitigation**: Always determine the service/delivery date, not the invoice/payment date. Accrue in the period the obligation was incurred.

### Ignoring Accrual Basis

**Pattern**: Recording expense only when cash is paid. Recognizing revenue only when cash is received.

**Why**: Cash basis is simpler and the model defaults to the simpler approach.

**Mitigation**: Unless explicitly told otherwise, assume accrual basis. Revenue recognized when earned (performance obligation satisfied). Expense recognized when incurred (goods/services received).

### Partial Period Errors

**Pattern**: Full-month depreciation on an asset placed in service on the 15th.

**Why**: The model defaults to the simplest calculation rather than applying the entity's partial-period convention.

**Mitigation**: Ask for the entity's convention: half-month, mid-quarter, exact days. Apply it consistently.

### Incorrect Comparison Periods

**Pattern**: Comparing Q4 actual to Q3 actual and calling it "year-over-year."

**Why**: Terminology confusion. YoY = same period in the prior year, not prior sequential period.

**Mitigation**: Use precise labels:

| Term | Meaning |
|------|---------|
| YoY | Same period, prior year (Q4 2025 vs Q4 2024) |
| QoQ | Sequential quarter (Q4 vs Q3) |
| MoM | Sequential month (Dec vs Nov) |
| YTD | Year-to-date (Jan through current month) |

---

## Category 6: Structural Accounting Errors

### Balance Sheet Does Not Balance

**Pattern**: LLM generates a balance sheet where Assets != Liabilities + Equity.

**Why**: The model generates each section independently and does not verify the fundamental equation.

**Mitigation**: After generating any balance sheet, verify: Total Assets = Total Liabilities + Total Stockholders' Equity. This is an absolute constraint.

### Cash Flow Does Not Reconcile

**Pattern**: Beginning cash + net change != ending cash. Or ending cash != balance sheet cash.

**Why**: Same issue — sections generated independently without cross-verification.

**Mitigation**: Verify:
1. Beginning cash + net cash change = ending cash
2. Ending cash = balance sheet cash and cash equivalents

### Intercompany Does Not Eliminate

**Pattern**: Intercompany receivables and payables that do not net to zero in consolidation.

**Why**: The model may create one side of an intercompany entry without the corresponding elimination.

**Mitigation**: For every intercompany balance, verify that the offsetting balance exists in the counterparty entity and that the elimination entry zeroes both out.

---

## Category 7: Overconfidence and Missing Caveats

### Presenting Estimates as Facts

**Pattern**: "The accrual should be $47,382" without stating assumptions or ranges.

**Why**: The model presents a single point estimate with false precision rather than acknowledging uncertainty.

**Mitigation**: For any estimated amount, state:
- Calculation methodology
- Key assumptions
- Sensitivity to assumption changes
- Whether the estimate requires professional review

### Omitting "Consult Professional" Disclaimers

**Pattern**: Providing definitive tax advice, legal interpretations, or audit opinions.

**Why**: The model optimizes for helpfulness over appropriate caution.

**Mitigation**: All financial output is working material for professionals. Never present output as:
- Tax advice
- Legal interpretation
- Audit opinion
- Authoritative GAAP interpretation

Always include: "Review by qualified financial professional required before [posting/filing/reporting]."

---

## Quick Reference: Verification Checklist

Run after every finance output:

| Check | Action |
|-------|--------|
| All sums verified | Re-derive totals from components |
| All percentages verified | Recompute: value / base x 100 |
| Signs correct | Apply favorable/unfavorable convention |
| Debits = credits | Sum check on every journal entry |
| A = L + E | Verify on every balance sheet |
| Cash reconciles | Beginning + change = ending |
| No fabricated codes | Account codes from user data only |
| No fabricated standards | ASC/IFRS citations at topic level only |
| Materiality applied | Thresholds set before investigation |
| Period correct | Expense in period incurred, revenue in period earned |
| Caveats present | Professional review disclaimer included |
