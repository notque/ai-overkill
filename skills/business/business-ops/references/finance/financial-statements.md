# Financial Statements Reference

Working reference for income statement, balance sheet, and cash flow statement generation with GAAP presentation rules and period-end adjustments.

---

## Income Statement (ASC 220 / IAS 1)

### Multi-Column Format

```
INCOME STATEMENT
Period: [Description]
(in thousands)

                              Current    Prior      Var ($)    Var (%)    Budget    Bud Var
                              --------   --------   --------   -------   --------  --------
REVENUE
  Product revenue             $XX,XXX    $XX,XXX    $X,XXX     X.X%      $XX,XXX   $X,XXX
  Service revenue             $XX,XXX    $XX,XXX    $X,XXX     X.X%      $XX,XXX   $X,XXX
  Other revenue               $XX,XXX    $XX,XXX    $X,XXX     X.X%      $XX,XXX   $X,XXX
                              --------   --------   --------             --------  --------
TOTAL REVENUE                 $XX,XXX    $XX,XXX    $X,XXX     X.X%      $XX,XXX   $X,XXX

COST OF REVENUE               $XX,XXX    $XX,XXX    $X,XXX     X.X%      $XX,XXX   $X,XXX
                              --------   --------   --------             --------  --------
GROSS PROFIT                  $XX,XXX    $XX,XXX    $X,XXX     X.X%      $XX,XXX   $X,XXX
  Gross Margin                XX.X%      XX.X%

OPERATING EXPENSES
  Research & development      $XX,XXX    $XX,XXX    $X,XXX     X.X%      $XX,XXX   $X,XXX
  Sales & marketing           $XX,XXX    $XX,XXX    $X,XXX     X.X%      $XX,XXX   $X,XXX
  General & administrative    $XX,XXX    $XX,XXX    $X,XXX     X.X%      $XX,XXX   $X,XXX
                              --------   --------   --------             --------  --------
TOTAL OPERATING EXPENSES      $XX,XXX    $XX,XXX    $X,XXX     X.X%      $XX,XXX   $X,XXX

OPERATING INCOME (LOSS)       $XX,XXX    $XX,XXX    $X,XXX     X.X%      $XX,XXX   $X,XXX
  Operating Margin            XX.X%      XX.X%

OTHER INCOME (EXPENSE)
  Interest income             $XX,XXX    $XX,XXX    $X,XXX     X.X%
  Interest expense           ($XX,XXX)  ($XX,XXX)   $X,XXX     X.X%
  Other, net                  $XX,XXX    $XX,XXX    $X,XXX     X.X%
                              --------   --------   --------
INCOME BEFORE TAXES           $XX,XXX    $XX,XXX    $X,XXX     X.X%
  Income tax expense          $XX,XXX    $XX,XXX    $X,XXX     X.X%
                              --------   --------   --------
NET INCOME (LOSS)             $XX,XXX    $XX,XXX    $X,XXX     X.X%      $XX,XXX   $X,XXX
  Net Margin                  XX.X%      XX.X%
```

### GAAP Presentation Rules — Income Statement

| Rule | Requirement |
|------|-------------|
| Expense classification | By function (COGS, R&D, S&M, G&A) or by nature. Function is standard for US companies. Must be consistent |
| Nature disclosure | If classified by function, disclose depreciation, amortization, and employee benefit costs by nature in notes |
| Operating vs non-operating | Present separately |
| Income tax | Separate line |
| Extraordinary items | Prohibited (both US GAAP and IFRS) |
| Discontinued operations | Separate, net of tax |
| Revenue disaggregation (ASC 606) | Disaggregate by nature, amount, timing, and uncertainty factors |
| Stock-based compensation | Classify within functional expense categories; disclose total SBC in notes |
| Restructuring charges | Present separately if material, or within OpEx with note disclosure |
| Non-GAAP measures | If presented, clearly label and reconcile to GAAP |

### Key Metrics

```
Revenue growth (%)             X.X%
Gross margin (%)               XX.X%
Operating margin (%)           XX.X%
Net margin (%)                 XX.X%
OpEx as % of revenue           XX.X%
Effective tax rate (%)         XX.X%
```

---

## Balance Sheet (ASC 210 / IAS 1)

### Standard Format

```
BALANCE SHEET
As of [Date]
(in thousands)

ASSETS
Current Assets
  Cash and cash equivalents                    $XX,XXX
  Short-term investments                       $XX,XXX
  Accounts receivable, net                     $XX,XXX
  Inventory                                    $XX,XXX
  Prepaid expenses and other current assets    $XX,XXX
Total Current Assets                           $XX,XXX

Non-Current Assets
  Property and equipment, net                  $XX,XXX
  Operating lease right-of-use assets          $XX,XXX
  Goodwill                                     $XX,XXX
  Intangible assets, net                       $XX,XXX
  Long-term investments                        $XX,XXX
  Other non-current assets                     $XX,XXX
Total Non-Current Assets                       $XX,XXX

TOTAL ASSETS                                   $XX,XXX

LIABILITIES AND STOCKHOLDERS' EQUITY
Current Liabilities
  Accounts payable                             $XX,XXX
  Accrued liabilities                          $XX,XXX
  Deferred revenue, current                    $XX,XXX
  Current portion of long-term debt            $XX,XXX
  Operating lease liabilities, current         $XX,XXX
  Other current liabilities                    $XX,XXX
Total Current Liabilities                      $XX,XXX

Non-Current Liabilities
  Long-term debt                               $XX,XXX
  Deferred revenue, non-current                $XX,XXX
  Operating lease liabilities, non-current     $XX,XXX
  Other non-current liabilities                $XX,XXX
Total Non-Current Liabilities                  $XX,XXX

Total Liabilities                              $XX,XXX

Stockholders' Equity
  Common stock                                 $XX,XXX
  Additional paid-in capital                   $XX,XXX
  Retained earnings (accumulated deficit)      $XX,XXX
  Accumulated other comprehensive income (loss)$XX,XXX
  Treasury stock                              ($XX,XXX)
Total Stockholders' Equity                     $XX,XXX

TOTAL LIABILITIES AND STOCKHOLDERS' EQUITY     $XX,XXX
```

### GAAP Presentation Rules — Balance Sheet

| Rule | Requirement |
|------|-------------|
| Current vs non-current | Distinguish explicitly |
| Current definition | Realized, consumed, or settled within 12 months (or operating cycle if longer) |
| Asset ordering | Most liquid first (US standard) |
| Accounts receivable | Net of allowance for credit losses (ASC 326) |
| PP&E | Net of accumulated depreciation |
| Goodwill | Not amortized — annual impairment test (ASC 350) |
| Leases (ASC 842) | Recognize ROU assets and lease liabilities for both operating and finance leases |
| Debt reclassification | Long-term debt maturing within 12 months reclassified to current |
| Fundamental equation | Assets = Liabilities + Stockholders' Equity (must balance) |

---

## Cash Flow Statement (ASC 230 / IAS 7)

### Indirect Method Format

```
CASH FLOWS FROM OPERATING ACTIVITIES
Net income (loss)                                          $XX,XXX
Adjustments to reconcile to net cash from operations:
  Depreciation and amortization                            $XX,XXX
  Stock-based compensation                                 $XX,XXX
  Amortization of debt issuance costs                      $XX,XXX
  Deferred income taxes                                    $XX,XXX
  Loss (gain) on disposal of assets                        $XX,XXX
  Impairment charges                                       $XX,XXX
  Other non-cash items                                     $XX,XXX
Changes in operating assets and liabilities:
  Accounts receivable                                     ($XX,XXX)
  Inventory                                               ($XX,XXX)
  Prepaid expenses and other assets                       ($XX,XXX)
  Accounts payable                                         $XX,XXX
  Accrued liabilities                                      $XX,XXX
  Deferred revenue                                         $XX,XXX
  Other liabilities                                        $XX,XXX
Net Cash Provided by (Used in) Operating Activities        $XX,XXX

CASH FLOWS FROM INVESTING ACTIVITIES
  Purchases of property and equipment                     ($XX,XXX)
  Purchases of investments                                ($XX,XXX)
  Proceeds from sale/maturity of investments               $XX,XXX
  Acquisitions, net of cash acquired                      ($XX,XXX)
  Other investing activities                               $XX,XXX
Net Cash Provided by (Used in) Investing Activities       ($XX,XXX)

CASH FLOWS FROM FINANCING ACTIVITIES
  Proceeds from issuance of debt                           $XX,XXX
  Repayment of debt                                       ($XX,XXX)
  Proceeds from issuance of common stock                   $XX,XXX
  Repurchases of common stock                             ($XX,XXX)
  Dividends paid                                          ($XX,XXX)
  Payment of debt issuance costs                          ($XX,XXX)
  Other financing activities                               $XX,XXX
Net Cash Provided by (Used in) Financing Activities       ($XX,XXX)

Effect of exchange rate changes on cash                    $XX,XXX

Net Increase (Decrease) in Cash                            $XX,XXX
Cash and cash equivalents, beginning of period             $XX,XXX
Cash and cash equivalents, end of period                   $XX,XXX
```

### GAAP Presentation Rules — Cash Flow

| Rule | Requirement |
|------|-------------|
| Method | Indirect most common (start with net income, adjust). Direct permitted but rare |
| Required disclosures | Interest paid and income taxes paid (face or notes) |
| Non-cash activities | Disclosed separately (lease assets, stock-for-acquisition, etc.) |
| Cash equivalents | Original maturity ≤ 3 months, highly liquid |
| Operating changes sign convention | Increase in asset = use of cash (negative). Increase in liability = source of cash (positive) |
| Verification | Beginning cash + net change = ending cash. Cross-check to balance sheet |

### Working Capital Changes — Sign Convention

| Change | Cash Flow Effect | Sign |
|--------|-----------------|------|
| AR increases | Cash used (sold but not collected) | Negative |
| AR decreases | Cash provided (collected) | Positive |
| Inventory increases | Cash used (purchased) | Negative |
| Inventory decreases | Cash provided (sold from existing) | Positive |
| AP increases | Cash provided (purchased but not paid) | Positive |
| AP decreases | Cash used (paid down) | Negative |
| Deferred revenue increases | Cash provided (collected in advance) | Positive |
| Deferred revenue decreases | Cash used (recognized previously collected) | Negative |

---

## Period-End Adjustments

### Required Adjustments

| Adjustment | Description | Accounts Affected |
|-----------|-------------|-------------------|
| Accruals | Expenses incurred, not paid | Expense / Accrued liabilities |
| Deferrals | Prepaid expenses, deferred revenue | Expense or Revenue / Prepaid or Deferred |
| Depreciation/amortization | Periodic allocation from schedules | D&A expense / Accumulated D&A |
| Bad debt provision | Adjust allowance per aging and loss rates | Bad debt expense / Allowance for credit losses |
| Inventory adjustments | Write-downs for obsolete/impaired | COGS or loss / Inventory |
| FX revaluation | Revalue foreign currency monetary items | FX gain/loss / Asset or Liability |
| Tax provision | Current and deferred income tax | Tax expense / Tax payable, Deferred tax |
| Fair value | Mark-to-market investments, derivatives | Gain/loss or OCI / Asset or Liability |

### Reclassifications

| Reclassification | Purpose |
|-----------------|---------|
| Current/non-current | Reclassify debt maturing within 12 months to current |
| Contra account netting | Net allowances against gross balances |
| Intercompany elimination | Eliminate IC balances in consolidation |
| Discontinued operations | Reclassify to separate line, net of tax |
| Equity method | Record share of investee income/loss |
| Segment | Ensure correct operating segment classification |

---

## Materiality Thresholds for Variance Investigation

| Line Item Size | Dollar Threshold | Percentage Threshold |
|---------------|-----------------|---------------------|
| > $10M | $500K | 5% |
| $1M - $10M | $100K | 10% |
| < $1M | $50K | 15% |

Investigate when either threshold is exceeded. Flag for professional review.

---

## Comparison Periods

| Report Type | Comparison Columns |
|------------|-------------------|
| Monthly | Prior month, prior year same month, budget |
| Quarterly | Prior quarter, prior year same quarter, budget |
| Annual | Prior year, budget |
| YTD | Prior year YTD, budget YTD |

Always include both dollar and percentage variances. Express margin changes in basis points (1 bp = 0.01%).
