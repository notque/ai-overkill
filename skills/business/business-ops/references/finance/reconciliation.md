# Reconciliation Reference

Working reference for account reconciliation: GL-to-subledger, bank reconciliations, intercompany, aging analysis, and reconciling item classification.

---

## Reconciliation Types

### GL-to-Subledger Reconciliation

Compare the general ledger control account balance to the detailed subledger balance.

**Common accounts:**

| Control Account | Subledger Source |
|----------------|-----------------|
| Accounts receivable | AR aging report |
| Accounts payable | AP aging report |
| Fixed assets | Fixed asset register |
| Inventory | Inventory valuation report |
| Prepaid expenses | Prepaid amortization schedule |
| Accrued liabilities | Accrual detail schedules |

**Process:**
1. Pull GL balance for the control account at period end
2. Pull subledger trial balance at the same date
3. Compare totals — should match if posting is real-time
4. Investigate differences

**Common causes of GL-to-sub differences:**

| Cause | Direction | Resolution |
|-------|-----------|------------|
| Manual JE to control account, not reflected in subledger | GL differs from sub | Post corresponding subledger entry or reclassify |
| Subledger transactions not interfaced to GL | Sub differs from GL | Run interface or post manual JE |
| Batch posting timing | Either | Wait for batch completion; document as timing |
| Reclassification in GL without subledger adjustment | GL differs from sub | Post subledger reclassification |
| System interface error / failed posting | Either | Diagnose and reprocess; escalate to IT |

### Bank Reconciliation

Compare GL cash balance to bank statement balance.

**Process:**
1. Obtain bank statement balance at period end
2. Pull GL cash account balance at same date
3. Identify outstanding checks (issued, not cleared)
4. Identify deposits in transit (recorded in GL, not credited by bank)
5. Identify bank charges/interest/adjustments not yet in GL
6. Reconcile both sides to adjusted balance

**Standard format:**

```
Balance per bank statement:         $XX,XXX
  Add: Deposits in transit           $X,XXX
  Less: Outstanding checks          ($X,XXX)
  Add/Less: Bank errors              $X,XXX
Adjusted bank balance:              $XX,XXX

Balance per general ledger:         $XX,XXX
  Add: Interest/credits not recorded $X,XXX
  Less: Bank fees not recorded      ($X,XXX)
  Add/Less: GL errors                $X,XXX
Adjusted GL balance:                $XX,XXX

Difference:                          $0.00
```

**Constraint**: Adjusted bank balance must equal adjusted GL balance. A nonzero difference means the reconciliation is incomplete.

### Intercompany Reconciliation

Reconcile balances between related entities to ensure elimination to zero on consolidation.

**Process:**
1. Pull IC receivable/payable balances for each entity pair
2. Compare Entity A's receivable from B to Entity B's payable to A
3. Identify and resolve differences
4. Confirm all IC transactions recorded on both sides
5. Verify elimination entries are correct

**Common causes of IC differences:**

| Cause | Resolution |
|-------|------------|
| Timing: one entity recorded, other has not | Confirm and post on the late side |
| Different FX rates used by each entity | Agree on rate source and date; adjust |
| Misclassification (IC vs third-party) | Reclassify to correct account |
| Disputed amounts / unapplied payments | Resolve dispute; apply payment |
| Different cut-off practices across entities | Standardize cut-off procedures |

---

## Reconciling Item Classification

### Category 1: Timing Differences

Items that will self-clear without action within the normal processing cycle (1-5 business days).

| Item | Description | Action |
|------|------------|--------|
| Outstanding checks | Issued and in GL, pending bank clearance | Monitor |
| Deposits in transit | In GL, pending bank credit | Monitor |
| In-transit transactions | Posted in one system, pending interface | Monitor |
| Pending approvals | Awaiting approval to post | Monitor |

No adjusting entry needed.

### Category 2: Adjustments Required

Items requiring a journal entry to correct.

| Item | Description | Action |
|------|------------|--------|
| Unrecorded bank charges | Fees, wire charges, returned item fees | Book JE |
| Unrecorded interest | Interest income or expense | Book JE |
| Recording errors | Wrong amount, wrong account, duplicate | Correcting JE |
| Missing entries | Transaction in one system, no counterpart | Book missing entry |
| Classification errors | Correct amount, wrong account | Reclassify |

### Category 3: Requires Investigation

Items that cannot be immediately explained.

| Item | Description | Action |
|------|------------|--------|
| Unidentified differences | No obvious cause | Root cause analysis |
| Disputed items | Contested between parties | Escalate to resolution |
| Aged outstanding items | Beyond expected clearance window | Supervisor review |
| Recurring unexplained differences | Same type each period | Process investigation |

---

## Aging Analysis

### Age Buckets and Escalation

| Age | Status | Action |
|-----|--------|--------|
| 0-30 days | Current | Monitor — within normal processing cycle |
| 31-60 days | Aging | Investigate — why has item not cleared? |
| 61-90 days | Overdue | Escalate to supervisor, document investigation |
| 90+ days | Stale | Escalate to management — potential write-off or adjustment |

### Aging Report Format

```
| Item # | Description | Amount | Date Originated | Age (Days) | Category | Status | Owner |
|--------|-------------|--------|-----------------|------------|----------|--------|-------|
```

### Trending Analysis

Track reconciling item totals over time:
- Compare total outstanding items to prior period
- Flag if total reconciling items exceed materiality threshold
- Flag if item count is growing period over period
- Identify recurring items (may indicate underlying process failure)

---

## Escalation Thresholds

| Trigger | Example Threshold | Escalation |
|---------|-------------------|------------|
| Individual item amount | > $10K | Supervisor review |
| Individual item amount | > $50K | Controller review |
| Total reconciling items | > $100K | Controller review |
| Item age | > 60 days | Supervisor follow-up |
| Item age | > 90 days | Controller / management |
| Unreconciled difference | Any amount | Cannot close — must resolve or document |
| Growing trend | 3+ consecutive periods | Process improvement investigation |

*Set thresholds based on organization's materiality level and risk appetite.*

---

## Reconciliation Best Practices

| Practice | Standard |
|----------|----------|
| Timeliness | Complete within close calendar (typically T+3 to T+5) |
| Completeness | All balance sheet accounts on defined frequency (monthly for material, quarterly for immaterial) |
| Documentation | Preparer, reviewer, date, clear explanation of all reconciling items |
| Segregation | Reconciler is not the transaction processor for that account |
| Follow-through | Track open items to resolution — never carry forward indefinitely |
| Root cause | For recurring items, fix the underlying process |
| Standardization | Consistent templates and procedures across all accounts |
| Retention | Per organization's document retention policy |

---

## Reconciliation Template

```
ACCOUNT RECONCILIATION
Account: [Code] — [Name]
Period: [Month/Year]
Prepared by: [Name]     Date: [Date]
Reviewed by: [Name]     Date: [Date]

GL Balance:                          $XX,XXX
Subledger/Source Balance:            $XX,XXX
Difference:                          $X,XXX

Reconciling Items:
| # | Description | Amount | Category | Age | Status |
|---|-------------|--------|----------|-----|--------|
| 1 | [Detail]    | $X,XXX | Timing   | XX  | Open   |
| 2 | [Detail]    | $X,XXX | Adj Req  | XX  | JE #XX |

Total Reconciling Items:             $X,XXX
Adjusted Difference:                 $0.00

Prior Period Comparison:
- Total reconciling items last period: $X,XXX
- Change: $X,XXX ([direction])
- Items carried forward from prior period: [count]
```

---

## Month-End Close Integration

Reconciliation fits into the close calendar as follows:

| Close Day | Reconciliation Activity |
|-----------|------------------------|
| T+1 | Bank reconciliation (with final bank statement) |
| T+2 | AR and AP subledger reconciliations |
| T+3 | All balance sheet reconciliations, intercompany recs |
| T+3 | Post adjusting JEs identified during reconciliation |
| T+4 | Management review of reconciliation results |

### Close Task Dependencies

```
Level 1 (T+1): Cash entries, bank statement retrieval
    ↓
Level 2 (T+2): Bank rec, AR/AP subledger recs
    ↓
Level 3 (T+3): All balance sheet recs, IC rec, adjusting entries
    ↓
Level 4 (T+4): Preliminary trial balance, draft financials
    ↓
Level 5 (T+5): Management review, hard close, period lock
```

### Close Metrics

| Metric | Target |
|--------|--------|
| Close duration (period end to hard close) | Reduce over time |
| Adjusting entries after soft close | Minimize |
| Late tasks | Zero |
| Reconciliation exceptions | Reduce over time |
| Post-close corrections | Zero |

---

## Continuous Reconciliation

For organizations targeting a 3-day close, shift reconciliation work into the month:

| Traditional | Continuous |
|------------|-----------|
| Reconcile all items at month-end | Reconcile daily/weekly; month-end is final verification |
| Start from scratch each period | Carry forward the prior rec, update incrementally |
| Investigate items at close | Investigate items as they arise |
| All adjusting JEs at close | Post adjustments throughout the month |

Benefits: shorter close, earlier detection of errors, reduced month-end stress.
