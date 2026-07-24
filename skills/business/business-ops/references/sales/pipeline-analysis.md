# Pipeline Analysis Reference

Pipeline health scoring, deal prioritization, forecast methodology, and risk detection. Used by both PIPELINE and FORECAST modes.

---

## Pipeline Health Scoring Model

Score pipeline on four dimensions. Each dimension is 0-25 points. Total health score is 0-100.

### Dimension 1: Stage Progression (0-25)

Measures whether deals are moving through stages at a healthy velocity.

| Scoring Rule | Points |
|-------------|--------|
| No deals stuck in same stage 30+ days | 25 |
| 1-2 deals stuck 30+ days | 20 |
| 3-5 deals stuck 30+ days | 15 |
| 6-10 deals stuck 30+ days | 10 |
| 10+ deals stuck OR more than 50% of pipeline stuck | 5 |

**Expected stage velocity** (industry baseline, B2B SaaS):

| Stage Transition | Healthy Duration | Warning | Critical |
|-----------------|-----------------|---------|----------|
| Prospecting -> Discovery | 7-14 days | 21 days | 30+ days |
| Discovery -> Evaluation | 14-21 days | 30 days | 45+ days |
| Evaluation -> Proposal | 7-14 days | 21 days | 30+ days |
| Proposal -> Negotiation | 7-14 days | 21 days | 30+ days |
| Negotiation -> Closed | 7-21 days | 30 days | 45+ days |

These are defaults. Enterprise deals move slower. SMB faster. Ask the user about their typical cycle length and adjust.

### Dimension 2: Activity Recency (0-25)

Measures engagement momentum across the pipeline.

| Scoring Rule | Points |
|-------------|--------|
| All deals have activity within 7 days | 25 |
| 1-2 deals with no activity 14+ days | 20 |
| 3-5 deals silent 14+ days | 15 |
| 6-10 deals silent 14+ days | 10 |
| 10+ deals silent OR more than 40% silent | 5 |

**Activity types that count** (in descending signal strength):

| Activity | Signal Strength | Notes |
|----------|----------------|-------|
| Customer-initiated email/call | Very strong | They are engaged |
| Scheduled meeting occurred | Strong | Active dialogue |
| Seller-initiated email with reply | Moderate | Two-way communication |
| Seller-initiated email, no reply | Weak | One-way, may be ghosting |
| Internal note only | None | Does not count as customer activity |

### Dimension 3: Close Date Accuracy (0-25)

Measures whether close dates reflect reality or wishful thinking.

| Scoring Rule | Points |
|-------------|--------|
| No deals with close date in the past | 25 |
| 1-2 deals past close date | 20 |
| 3-5 deals past close date | 15 |
| 6-10 deals past close date | 10 |
| 10+ past OR more than 30% past | 5 |

**Close date integrity signals**:

| Signal | Interpretation |
|--------|---------------|
| Close date pushed 3+ times | Deal may be zombie. Qualify hard. |
| Close date matches end-of-quarter | Often placeholder, not real commitment |
| Close date within 2 weeks but no meeting scheduled | Unlikely to close on time |
| Close date aligns with stated event (contract renewal, budget cycle) | Legitimate anchor |

### Dimension 4: Contact Coverage (0-25)

Measures multi-threading -- the number of contacts engaged per deal.

| Scoring Rule | Points |
|-------------|--------|
| All deals have 2+ active contacts | 25 |
| 1-3 deals single-threaded | 20 |
| 4-6 deals single-threaded | 15 |
| 7+ deals single-threaded | 10 |
| More than 50% single-threaded | 5 |

**Why single-threading kills deals**:

- Champion leaves company: deal dies immediately
- Champion goes on leave: deal stalls with no alternate path
- Champion loses internal influence: no backup advocate
- Champion's priorities shift: nobody else carries your case

**Multi-threading targets by deal size**:

| Deal Size | Minimum Contacts | Ideal |
|-----------|-----------------|-------|
| Under $25K | 1 (acceptable) | 2 |
| $25K-100K | 2 | 3-4 |
| $100K-500K | 3 | 5+ |
| $500K+ | 4 | 7+ across departments |

---

## Deal Prioritization Framework

### Default Weighting

| Factor | Weight | Scoring Method |
|--------|--------|---------------|
| Close Date | 30% | Inverse days to close: deals closing soonest score highest |
| Deal Size | 25% | Normalized to largest deal in pipeline |
| Stage | 20% | Later stage = higher score |
| Activity | 15% | Days since last activity (inverse) |
| Risk | 10% | Composite of risk flags (fewer = higher) |

### Alternative Weightings (User-Triggered)

| User Says | Adjustment |
|-----------|-----------|
| "Focus on big deals" | Deal Size -> 40%, Close Date -> 20% |
| "I need quick wins" | Close Date -> 40%, Stage -> 25%, Deal Size -> 15% |
| "Fix my pipeline hygiene" | Risk -> 30%, Activity -> 25%, Close Date -> 20% |
| "Help me hit my number" | Close Date -> 35%, Deal Size -> 30%, Stage -> 20% |

### Time Horizon Classification

| Category | Criteria | Action Required |
|----------|---------|-----------------|
| **Close This Week** | Close date within 7 days AND stage >= Proposal | Focus time. Daily action. Remove blockers. |
| **Close This Month** | Close date within 30 days AND stage >= Evaluation | Keep warm. Weekly touchpoint. Track progress. |
| **Nurture** | Close date 30-90 days OR stage <= Discovery | Periodic check-in. Build relationship. Share value. |
| **Consider Removing** | Past close date 30+ days, no activity 30+ days, pushed 3+ times | Qualify out or mark closed-lost. Pipeline inflation hurts forecasting. |

---

## Forecast Methodology

### Stage-Weighted Forecast

Base calculation per deal: `Amount * Stage Probability * Risk Adjustment = Weighted Value`

Default stage probabilities:

| Stage | Base Probability | Notes |
|-------|-----------------|-------|
| Closed Won | 100% | Already booked |
| Verbal Commit | 90% | Verbal yes, awaiting paperwork |
| Negotiation / Contract | 80% | Terms being discussed |
| Proposal / Quote | 60% | Proposal delivered, awaiting response |
| Evaluation / Demo | 40% | Active evaluation |
| Discovery / Qualification | 20% | Exploring fit |
| Prospecting / Lead | 10% | Early stage, low confidence |

### Risk Adjustments

Apply after base probability. These compound multiplicatively.

| Risk Factor | Adjustment | Detection |
|------------|-----------|-----------|
| No activity 14+ days | -10% (multiply by 0.90) | Last activity date vs today |
| No activity 30+ days | -25% (multiply by 0.75) | Last activity date vs today |
| Close date in past | -20% (multiply by 0.80) | Close date < today |
| Close date pushed 3+ times | -30% (multiply by 0.70) | Requires user confirmation |
| Single-threaded | -10% (multiply by 0.90) | Only one contact |
| No next step defined | -15% (multiply by 0.85) | Missing from deal record |
| Champion left company | -50% (multiply by 0.50) | Requires user confirmation |
| Competitor displacement | -15% (multiply by 0.85) | Incumbent competitor present |

**Example**: $100K deal in Proposal stage, no activity 14 days, single-threaded.
Base: 60% -> Risk: 0.60 * 0.90 * 0.90 = 0.486 -> Weighted: $48,600.

### Commit vs. Upside Classification

| Category | Criteria | Forecast Treatment |
|----------|---------|-------------------|
| **Commit** | Stage >= Negotiation AND no critical risk flags AND rep would bet on it | Include in worst-case scenario |
| **Best Case** | Stage >= Evaluation AND active engagement | Include in best-case only |
| **Upside** | Everything else in pipeline | Exclude from forecast, note for pipeline generation |

Rules for commit classification:
- Never commit a deal with close date in the past
- Never commit a deal with no activity 30+ days
- Never commit a deal the user says has low confidence
- Ask the user: "Would you bet your forecast on this deal?" If hesitation, it's upside.

### Three-Scenario Model

| Scenario | Formula | Use |
|----------|---------|-----|
| **Best Case** | Sum of all deal amounts at stage probability (no risk adjustment) | Upper bound. Optimistic. |
| **Likely Case** | Sum of weighted values (stage probability * risk adjustments) | Planning target. Most realistic. |
| **Worst Case** | Sum of Commit deals only | Floor. What you can count on. |

### Gap Analysis

```
Gap = Quota - Closed to Date - Likely Case Forecast
Coverage Ratio = Open Pipeline / (Quota - Closed to Date)
```

| Coverage Ratio | Assessment |
|---------------|-----------|
| 4x+ | Strong. Focus on execution, not pipeline generation. |
| 3x | Healthy. Standard coverage for B2B. |
| 2x-3x | Tight. Need to accelerate deals and maintain pipeline generation. |
| 1x-2x | At risk. Pipeline generation is urgent. Every deal matters. |
| Below 1x | Critical. Cannot hit target from existing pipeline alone. |

### Gap-Closing Strategies

| Strategy | When to Use | Expected Impact |
|----------|------------|----------------|
| **Accelerate** | Deals in late stage that can close faster | Pull in revenue from future periods |
| **Upsize** | Existing deals with expansion potential | Increase deal value without new pipeline |
| **Revive** | Stalled deals with prior engagement | Lower cost than new pipeline |
| **Generate** | Coverage below 2x | New pipeline at early stages |
| **Negotiate** | Quota discussion with management | Adjust target if pipeline is structurally thin |

---

## Pipeline Shape Analysis

Healthy pipelines have a funnel shape -- more deals in early stages, fewer in late stages. Inverted funnels signal pipeline generation problems.

### Ideal Distribution (B2B SaaS)

| Stage Group | % of Total Deals | % of Total Value |
|------------|-----------------|------------------|
| Early (Prospecting, Discovery) | 40-50% | 20-30% |
| Mid (Evaluation, Proposal) | 30-35% | 35-45% |
| Late (Negotiation, Contract) | 15-25% | 30-40% |

### Shape Diagnostics

| Shape | What It Means | Recommended Action |
|-------|--------------|-------------------|
| **Top-heavy** (many early, few late) | Deals are entering but not progressing | Review qualification criteria. Are early-stage deals real? |
| **Bottom-heavy** (few early, many late) | Pipeline generation has stalled | Immediate prospecting push. Pipeline will dry up in 60-90 days. |
| **Uniform** (even distribution) | Generally healthy but inspect individual deals | Focus on accelerating mid-stage deals |
| **Bimodal** (many early + many late, hollow middle) | Conversion problem in mid-stages | Diagnose why deals stall in evaluation/proposal |
| **Single-deal dependent** | One deal is >40% of pipeline value | Extreme risk concentration. Generate pipeline urgently. |

---

## Hygiene Audit Checklist

Flag these issues automatically when reviewing pipeline data.

| Issue | Detection Rule | Impact | Fix |
|-------|---------------|--------|-----|
| Missing close date | Close date field empty | Cannot forecast | Add realistic close date |
| Missing amount | Amount field empty or $0 | Cannot forecast | Estimate or qualify |
| Missing next step | No next action recorded | Stall risk | Define next action |
| Missing contact | No primary contact | Cannot engage | Assign contact |
| Duplicate deals | Same account + similar amount + overlapping dates | Inflated pipeline | Merge or close duplicate |
| Stale stage | Same stage 45+ days | Over-represented in forecast | Advance, regress, or close |
| Zombie deal | Past close date + no activity 30+ days + pushed 2+ times | Dead weight | Close lost |
| Orphaned deal | Owner left company or changed role | No one working it | Reassign |

---

## Reporting Cadence

| Review Type | Frequency | Focus |
|------------|-----------|-------|
| Deal inspection | Daily | Top 3-5 deals. What changed? What's the next action? |
| Pipeline review | Weekly | Full pipeline health. Prioritization. Risk flags. |
| Forecast call | Bi-weekly or weekly | Commit/upside. Gap analysis. Scenario update. |
| Pipeline shape | Monthly | Stage distribution. Generation vs. close rate. |
| Deep clean | Quarterly | Full hygiene audit. Remove dead weight. Reset close dates. |
