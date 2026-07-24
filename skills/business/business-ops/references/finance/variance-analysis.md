# Variance Analysis Reference

Working reference for variance decomposition, materiality thresholds, narrative generation, and waterfall analysis.

---

## Decomposition Techniques

### 1. Price / Volume Decomposition

The foundational technique. Applies to any metric expressible as Price x Volume.

**Two-way decomposition:**
```
Total Variance = Actual - Budget (or Prior)

Volume Effect = (Actual Volume - Budget Volume) x Budget Price
Price Effect  = (Actual Price - Budget Price) x Actual Volume

Verification: Volume Effect + Price Effect = Total Variance
```

**Three-way decomposition (isolating mix):**
```
Volume Effect = (Actual Volume - Budget Volume) x Budget Price x Budget Mix
Price Effect  = (Actual Price - Budget Price) x Budget Volume x Actual Mix
Mix Effect    = Budget Price x Budget Volume x (Actual Mix - Budget Mix)

Verification: Volume + Price + Mix = Total Variance
```

**Worked example — Revenue variance:**

| | Units | Price | Revenue |
|---|------|-------|---------|
| Budget | 10,000 | $50 | $500,000 |
| Actual | 11,000 | $48 | $528,000 |
| Variance | +1,000 | -$2 | +$28,000 |

Decomposition:
- Volume effect: +1,000 x $50 = +$50,000 favorable (sold more)
- Price effect: -$2 x 11,000 = -$22,000 unfavorable (lower ASP)
- Net: +$28,000 favorable
- Verify: $50,000 + (-$22,000) = $28,000

### 2. Rate / Mix Decomposition

Used when analyzing blended rates across segments with different unit economics.

```
Rate Effect = Sum_i (Actual Volume_i x (Actual Rate_i - Budget Rate_i))
Mix Effect  = Sum_i (Budget Rate_i x (Actual Volume_i - Expected Volume_i at Budget Mix))
```

**Worked example — Gross margin:**
- Product A: 60% margin, Product B: 40% margin
- Budget mix: 50% A, 50% B → Blended margin 50%
- Actual mix: 40% A, 60% B → Blended margin 48%
- Mix effect: 2 percentage points of margin compression

### 3. Headcount / Compensation Decomposition

For payroll and people-cost variances.

```
Total Comp Variance = Actual - Budget Compensation

Components:
1. Headcount variance  = (Actual HC - Budget HC) x Budget Avg Comp
2. Rate variance       = (Actual Avg Comp - Budget Avg Comp) x Budget HC
3. Mix variance        = Level/department mix shift
4. Timing variance     = Hiring earlier/later than plan (partial-period)
5. Attrition impact    = Unplanned departure savings (net of backfill costs)
```

### 4. Spend Category Decomposition

For operating expenses where price/volume does not apply.

```
Total OpEx Variance = Actual - Budget

Categories:
1. Headcount-driven    (salaries, benefits, payroll taxes, recruiting)
2. Volume-driven       (hosting, transaction fees, commissions, shipping)
3. Discretionary       (travel, events, professional services, marketing programs)
4. Contractual/fixed   (rent, insurance, software licenses, subscriptions)
5. One-time            (severance, legal settlements, write-offs, project costs)
6. Timing/phasing      (spend shifted between periods vs plan)
```

---

## Materiality Thresholds

### Setting Thresholds

Base thresholds on:

| Factor | Approach |
|--------|----------|
| Financial statement materiality | 1-5% of key benchmark (revenue, total assets, net income) |
| Line item size | Larger items warrant lower % thresholds |
| Volatility | More volatile items may need higher thresholds to filter noise |
| Decision relevance | What level would change a management decision? |

### Threshold Framework

| Comparison | Dollar Threshold | % Threshold | Trigger |
|-----------|-----------------|-------------|---------|
| Actual vs Budget | Org-specific | 10% | Either exceeded |
| Actual vs Prior Period | Org-specific | 15% | Either exceeded |
| Actual vs Forecast | Org-specific | 5% | Either exceeded |
| Sequential (MoM) | Org-specific | 20% | Either exceeded |

*Dollar thresholds: typically 0.5%-1% of revenue for income statement items.*

### Investigation Priority

When multiple variances exceed thresholds, prioritize:

| Priority | Criterion |
|----------|-----------|
| 1 | Largest absolute dollar variance |
| 2 | Largest percentage variance |
| 3 | Unexpected direction (opposite to trend) |
| 4 | New variance (was on track, now off) |
| 5 | Cumulative/trending (growing each period) |

---

## Narrative Generation

### Structure

```
[Line Item]: [Favorable/Unfavorable] variance of $[amount] ([percentage]%)
vs [comparison basis] for [period]

Driver: [Primary driver description]
[2-3 sentences: business reason, quantified contributing factors]

Outlook: [One-time / Expected to continue / Improving / Deteriorating]
Action:  [None / Monitor / Investigate / Update forecast]
```

### Quality Checklist

Every narrative must be:

| Criterion | Test |
|-----------|------|
| Specific | Names the actual driver, not "higher than expected" |
| Quantified | Dollar and percentage impact of each driver |
| Causal | Explains WHY, not just WHAT |
| Forward-looking | States whether variance continues, normalizes, or worsens |
| Actionable | Identifies required follow-up or decision |
| Concise | 2-4 sentences. No filler |

### Failure Modes (detect and fix these)

| Failure Mode | Why It Fails | Fix |
|-------------|-------------|-----|
| "Revenue was higher due to higher revenue" | Circular — no explanation | Name the driver: volume, pricing, customer, product |
| "Expenses were elevated" | Vague — which expenses? Why? | Specify line item, amount, and cause |
| "Timing" (standalone) | Unverifiable without detail | State what was early/late and when it normalizes |
| "One-time" (standalone) | Unnamed one-time item is suspicious | Name the specific event and amount |
| "Various small items" for material variance | Insufficient decomposition | Break down until each component is below materiality |
| Only largest driver mentioned | Hides offsetting items | Show all material contributing factors |

---

## Waterfall / Bridge Analysis

### Data Structure

```
Starting value:  [Base / Budget / Prior period]
Drivers:         [Signed amounts for each contributing factor]
Ending value:    [Actual / Current period]

Verification: Starting + Sum(Drivers) = Ending
```

### Text Waterfall Format

```
WATERFALL: [Metric] — [Period] [Comparison]

[Comparison] Amount                              $XX,XXXK
  |
  |--[+] [Driver 1]                              +$X,XXXK
  |--[+] [Driver 2]                              +$X,XXXK
  |--[-] [Driver 3]                              -$X,XXXK
  |--[-] [Driver 4]                              -$X,XXXK
  |--[+] [Driver 5]                              +$XXXK
  |
[Current Period] Amount                          $XX,XXXK

Net Variance: +$X,XXXK (+X.X% favorable)
```

### Bridge Reconciliation Table

```
| Driver | Amount | % of Variance | Cumulative |
|--------|--------|---------------|------------|
| [Driver 1] | +$XXK | XX% | +$XXK |
| [Driver 2] | +$XXK | XX% | +$XXK |
| [Driver 3] | -$XXK | -XX% | +$XXK |
| **Total** | **+$XXK** | **100%** | |
```

*Individual driver percentages can exceed 100% when offsetting items exist.*

### Waterfall Best Practices

| Practice | Rationale |
|----------|-----------|
| Order by magnitude (largest positive to largest negative) or by logical business sequence | Readability |
| Limit to 5-8 drivers | Aggregate smaller items into "Other" |
| Verify reconciliation | Start + drivers = end (always) |
| Color code when visual | Green = favorable, red = unfavorable |
| Label each bar | Amount + brief description |
| Include total variance bar | Summary view |

---

## Budget vs Actual vs Forecast

### Three-Way Comparison

```
| Metric | Budget | Forecast | Actual | Bud Var ($) | Bud Var (%) | Fcast Var ($) | Fcast Var (%) |
|--------|--------|----------|--------|-------------|-------------|---------------|---------------|
```

### When to Use Each Comparison

| Comparison | Use Case |
|-----------|----------|
| Actual vs Budget | Annual performance, compensation, board reporting |
| Actual vs Forecast | Operational management, emerging issues |
| Forecast vs Budget | How expectations changed since planning |
| Actual vs Prior Period | Trend analysis, seasonality, new business lines |
| Actual vs Prior Year | YoY growth, seasonality-adjusted comparison |

### Forecast Accuracy Tracking

```
Forecast Accuracy = 1 - |Actual - Forecast| / |Actual|
MAPE = Average of |Actual - Forecast| / |Actual| across periods
```

### Variance Trending Interpretation

| Pattern | Interpretation |
|---------|---------------|
| Consistently favorable | Budget may be too conservative (sandbagging) |
| Consistently unfavorable | Budget too aggressive or execution issues |
| Growing unfavorable | Deteriorating performance or unrealistic targets |
| Shrinking variance | Forecast accuracy improving (normal intra-year pattern) |
| Volatile | Unpredictable business or poor forecasting methodology |

---

## Favorable vs Unfavorable Convention

| Line Item Type | Actual > Budget | Actual < Budget |
|---------------|----------------|----------------|
| Revenue | Favorable | Unfavorable |
| COGS / Expense | Unfavorable | Favorable |
| Gross Profit | Favorable | Unfavorable |
| Net Income | Favorable | Unfavorable |

**Sign convention**: Express favorable as positive, unfavorable as negative. Always label direction explicitly — do not rely on sign alone.

---

## Common Calculation Verification

After producing any variance analysis, verify:

| Check | Method |
|-------|--------|
| Decomposition sums to total | Volume + Price + Mix = Total Variance |
| Percentages are correct | Variance / Base x 100 (not variance / actual) |
| Bridge reconciles | Start + all drivers = End |
| Signs are consistent | Favorable = positive for income items, negative for expense items |
| Basis is stated | "vs Budget" or "vs Prior Year" — never ambiguous |
| Margin changes in basis points | 1 pp = 100 bps. State "X.X pp" or "XXX bps" |
