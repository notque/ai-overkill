# Journal Entries Reference

Working reference for preparing journal entries with proper debits, credits, supporting documentation, and review workflows.

---

## Debit/Credit Rules

| Account Type | Normal Balance | Debit Does | Credit Does |
|-------------|---------------|------------|-------------|
| Asset | Debit | Increase | Decrease |
| Contra Asset (e.g., Accum. Depreciation) | Credit | Decrease | Increase |
| Liability | Credit | Decrease | Increase |
| Equity | Credit | Decrease | Increase |
| Revenue | Credit | Decrease | Increase |
| Contra Revenue (e.g., Sales Returns) | Debit | Increase | Decrease |
| Expense | Debit | Increase | Decrease |

**Fundamental constraint**: Every journal entry must balance. Sum of debits = sum of credits. No exceptions.

---

## Standard Accrual Categories

### 1. Accounts Payable Accruals

Goods/services received but not yet invoiced at period end.

**Entry:**
- Debit: Expense account (or asset if capitalizable)
- Credit: Accrued liabilities

**Sources for amount:**
- Open POs with confirmed receipts
- Contracts with services rendered, not yet billed
- Recurring vendor arrangements (utilities, professional services, subscriptions)
- Employee expense reports submitted but unprocessed

**Controls:**
- Auto-reverse in the following period
- Consistent estimation methodology period over period
- Document basis: PO amount, contract terms, or historical run-rate
- Track actual vs accrual to calibrate future estimates

### 2. Fixed Asset Depreciation

Periodic depreciation/amortization for tangible and intangible assets.

**Entry:**
- Debit: Depreciation/amortization expense (by department/cost center)
- Credit: Accumulated depreciation/amortization

**Methods:**

| Method | Formula | Use Case |
|--------|---------|----------|
| Straight-line | (Cost - Salvage) / Useful life | Default for financial reporting |
| Declining balance | Rate x Net book value | Accelerated; tax reporting |
| Units of production | (Cost - Salvage) x (Actual units / Total expected units) | Usage-based assets |

**Controls:**
- Source from fixed asset register or depreciation schedule
- Verify new additions have correct useful life and method
- Check for disposals or impairments requiring write-off
- Track book vs tax depreciation separately

### 3. Prepaid Expense Amortization

Amortize prepaid expenses over their benefit period.

**Entry:**
- Debit: Expense account (insurance, software, rent, etc.)
- Credit: Prepaid expense

**Common categories:**

| Category | Typical Term | Amortization Basis |
|----------|-------------|-------------------|
| Insurance premiums | 12 months | Straight-line monthly |
| Software licenses | 12-36 months | Per contract term |
| Prepaid rent | Per lease term | Monthly |
| Maintenance contracts | Per contract | Straight-line |
| Conference deposits | Event date | Expense at event or upon forfeiture |

**Controls:**
- Maintain amortization schedule with start/end dates and monthly amounts
- Review for immaterial items that should be expensed immediately
- Check for cancelled contracts requiring accelerated amortization
- Add new prepaids to schedule promptly

### 4. Payroll Accruals

Accrue compensation and related costs earned but not yet paid.

**Entries:**

| Component | Debit | Credit |
|-----------|-------|--------|
| Salary accrual (partial pay period) | Salary expense by dept | Accrued payroll |
| Bonus accrual | Bonus expense by dept | Accrued bonus |
| Benefits | Benefits expense | Accrued benefits |
| Employer payroll taxes | Payroll tax expense | Accrued payroll taxes |

**Calculation basis:**
- Salary: Working days in period / total days in pay period x gross pay
- Bonus: Plan terms (target x performance factor x proration)
- Benefits: Employer share of health, retirement match, PTO liability
- Taxes: FICA (6.2% SS up to wage base + 1.45% Medicare), FUTA, SUTA

### 5. Revenue Recognition (ASC 606)

Five-step framework:

| Step | Action |
|------|--------|
| 1. Identify the contract | Agreement with commercial substance, identifiable rights/obligations, payment terms, approval |
| 2. Identify performance obligations | Distinct goods/services promised. Distinct = customer can benefit independently AND separately identifiable |
| 3. Determine transaction price | Fixed + variable consideration (constraint: include only amounts not subject to significant reversal) |
| 4. Allocate to obligations | Standalone selling price for each obligation. Methods: adjusted market, expected cost + margin, residual |
| 5. Recognize upon satisfaction | Point in time (control transfers) or over time (customer simultaneously receives/consumes benefit) |

**Common entries:**

| Scenario | Debit | Credit |
|----------|-------|--------|
| Recognize deferred revenue | Deferred revenue | Revenue |
| Recognize with new receivable | Accounts receivable | Revenue |
| Receive payment in advance | Cash / AR | Deferred revenue |

---

## Entry Format Template

```
Journal Entry: [Type] — [Period]
Prepared by: [Name]
Date: [Period end date]
Reversal: [Yes/No — if yes, reversal date]

| Line | Account Code | Account Name | Debit | Credit | Dept | Memo |
|------|-------------|--------------|-------|--------|------|------|
| 1    | [Code]      | [Name]       | X,XXX |        | [D]  | [Detail] |
| 2    | [Code]      | [Name]       |       | X,XXX  | [D]  | [Detail] |
|      |             | **Total**    | X,XXX | X,XXX  |      |      |

Supporting Detail:
- Calculation basis and assumptions
- Reference to source documentation
- Comparison to prior period entry (if available)
```

---

## Supporting Documentation Requirements

Every entry must include:

| Requirement | Purpose |
|------------|---------|
| Entry description/memo | Audit trail — what and why |
| Calculation support | How amounts were derived |
| Source documents | PO numbers, invoice numbers, contract refs, payroll register |
| Period | Accounting period the entry applies to |
| Preparer ID | Who prepared and when |
| Approval evidence | Review per authorization matrix |
| Reversal indicator | Whether entry auto-reverses and reversal date |

---

## Approval Matrix

| Entry Type | Threshold | Approver |
|-----------|-----------|----------|
| Standard recurring | Any | Accounting manager |
| Non-recurring manual | < $50K | Accounting manager |
| Non-recurring manual | $50K-$250K | Controller |
| Non-recurring manual | > $250K | CFO / VP Finance |
| Top-side / consolidation | Any | Controller+ |
| Out-of-period adjustments | Any | Controller+ |

*Thresholds are illustrative. Set based on organization's materiality.*

---

## Review Checklist

Before approving any entry:

- [ ] Debits = credits (balanced)
- [ ] Correct accounting period
- [ ] Account codes valid and appropriate
- [ ] Amounts mathematically accurate with supporting calculations
- [ ] Description clear, specific, audit-sufficient
- [ ] Department/cost center coding correct
- [ ] Consistent with prior period treatment
- [ ] Auto-reversal set for accruals
- [ ] Supporting documentation complete and referenced
- [ ] Within preparer's authority level
- [ ] No duplicate of existing entry
- [ ] Unusual amounts explained

---

## Common Errors

| Error | Detection | Risk |
|-------|-----------|------|
| Unbalanced entry | Sum check: debits != credits | Misstatement |
| Wrong period | Entry date vs period end | Cut-off error |
| Wrong sign | Debit as credit or vice versa | Double the intended impact |
| Duplicate | Same transaction recorded twice | Overstatement |
| Wrong account | Similar account codes transposed | Misclassification |
| Missing reversal | Accrual not set to auto-reverse | Double-counting next period |
| Stale accrual | Recurring accrual not updated for changed circumstances | Inaccurate estimate |
| Round-number estimate | $100,000 exactly without calculation basis | Audit flag for fabrication |
| Wrong FX rate | Foreign currency at incorrect rate or date | Translation error |
| Missing intercompany elimination | One-sided intercompany entry | Consolidation error |
| Capitalization error | Expense capitalized or capital item expensed | Asset/expense misstatement |
| Cut-off error | Recorded in wrong period based on delivery/service date | Revenue/expense timing |

---

## Intercompany Journal Entries

When booking intercompany transactions:

1. Both entities must record their side of the transaction
2. Use designated intercompany accounts (receivable/payable pairs)
3. Amounts must match exactly (same currency, same date, same FX rate)
4. Elimination entries must zero out the intercompany balances in consolidation
5. Document the business purpose for each intercompany transaction

**Common intercompany types:**
- Management fees / shared services allocations
- Intercompany sales of goods or services
- Intercompany loans and interest
- Cost recharges and royalties
- Dividend declarations between entities
