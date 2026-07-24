# Compensation Reference

Market benchmarking, internal equity analysis, offer structuring, and equity modeling.

---

## Total Compensation Components

| Component | Description | Variability | Key Considerations |
|-----------|-------------|-------------|-------------------|
| **Base salary** | Fixed annual cash compensation | Low — changes annually | Primary anchor. Affects bonus %, equity expectations, benefits calculations |
| **Equity** | RSUs, stock options, restricted stock | High — value fluctuates | Vesting schedule, grant cadence, dilution, tax treatment vary widely |
| **Target bonus** | Annual performance-based cash | Medium — 0-200% payout | Percentage of base. Individual + company performance multipliers |
| **Signing bonus** | One-time cash at hire | One-time | Often clawback if departure <12 months. Bridges gap when base is constrained. |
| **Benefits** | Health, dental, vision, 401k match, HSA/FSA | Low — plan-level | Hard to quantify per-person. $15-25K value for US tech companies. |
| **Perks** | WFH stipend, meals, commuter, wellness | Low | Marginal comp. Rarely a deciding factor. |

### Total Comp Calculation

```
Total First-Year Comp = Base + (Equity Year 1 Value) + (Target Bonus * Expected Payout) + Signing Bonus
Total Annual Comp (steady state) = Base + (Annual Equity Value) + (Target Bonus * Expected Payout)
```

**Year 1 is anomalous.** Signing bonus inflates it. Equity cliff (25% vesting at month 12) means zero equity for the first year at many companies. Always present both Year 1 and steady-state.

---

## Market Benchmarking

### Data Sources

| Source | Strengths | Limitations | Freshness |
|--------|-----------|-------------|-----------|
| Levels.fyi | Individual-reported, strong tech coverage, includes equity | Self-selection bias, US-heavy | Rolling, ~6 months lag |
| Glassdoor | Broad coverage across industries | Less granular on equity/bonus | Rolling |
| Radford (Aon) | Survey-based, rigorous methodology, enterprise coverage | Expensive, annual release, 12-18 month lag | Annual |
| Pave/Carta | Real-time, equity-focused, startup coverage | Biased toward funded startups | Real-time |
| Mercer/WTW | Global coverage, job architecture framework | Expensive, enterprise-focused | Annual |
| H1B salary data | Public, granular, actual paid salaries | Only H1B employees, legal minimums may apply | Rolling, ~6 month lag |

### Benchmarking Methodology

**Step 1: Job matching.** Match internal roles to benchmark roles based on responsibilities and scope, not title (because title inflation makes title-based matching unreliable).

**Step 2: Level calibration.** Map internal levels to benchmark levels. Common mapping:

| Internal Level | Typical Years | Scope | Benchmark Equivalent |
|---------------|---------------|-------|---------------------|
| Junior/L1-L2 | 0-2 | Task-level execution with guidance | Entry/Junior |
| Mid/L3 | 2-5 | Independent execution on defined work | Intermediate |
| Senior/L4 | 5-8 | Owns projects end-to-end, mentors | Senior |
| Staff/L5 | 8-12 | Cross-team technical leadership | Staff/Principal |
| Principal/L6 | 12+ | Org-wide technical direction | Distinguished |

**Step 3: Location adjustment.** Apply geographic differential. Typical adjustments relative to SF Bay Area:

| Location Tier | Adjustment | Examples |
|--------------|------------|---------|
| Tier 1 (HCOL) | 100% (baseline) | SF, NYC, Seattle |
| Tier 2 (MCOL) | 85-95% | Austin, Denver, Boston, LA |
| Tier 3 (LCOL) | 70-85% | Midwest, Southeast, smaller metros |
| International — Tier 1 | 80-100% | London, Zurich, Tel Aviv |
| International — Tier 2 | 50-80% | Berlin, Amsterdam, Toronto, Sydney |
| International — Tier 3 | 30-60% | Eastern Europe, Southeast Asia, Latin America |

**Step 4: Company stage adjustment.** Equity/cash mix shifts dramatically by stage:

| Stage | Base Percentile Target | Equity | Bonus | Rationale |
|-------|----------------------|--------|-------|-----------|
| Pre-seed/Seed | 25th-50th | Heavy (0.5-2%) | Rare | Cash constrained, equity is the draw |
| Series A-B | 50th-65th | Moderate (0.1-0.5%) | Sometimes | Balancing cash with equity upside |
| Series C+ / Growth | 60th-75th | Moderate (RSUs typical) | Common | Competitive cash + meaningful equity |
| Public | 50th-75th | RSUs, refresh grants | Standard | Full comp package, liquid equity |
| Enterprise/non-tech | 50th-75th | Limited or none | Standard | Cash-heavy, pension/benefits |

### Percentile Bands

Standard reporting format:

| Percentile | Meaning | When to Target |
|-----------|---------|----------------|
| 25th | Below market | Constrained budget. Risk of attrition for strong performers. |
| 50th (median) | At market | Standard target for most roles. "Competitive." |
| 75th | Above market | For critical/hard-to-fill roles or retention situations |
| 90th | Top of market | Exceptional talent, niche skills, competitive bidding situations |

---

## Internal Equity Analysis

### Band Structure

| Term | Definition |
|------|-----------|
| **Band minimum** | Floor for the level. No one should be paid below this for the role/level. |
| **Band midpoint** | Target market rate. New hires at expected experience should land here. |
| **Band maximum** | Ceiling for the level. Above this = promotion or re-leveling needed. |
| **Compa-ratio** | Employee pay / band midpoint. 1.0 = at midpoint. <0.8 = significantly below. >1.2 = above band. |
| **Range penetration** | (Pay - Min) / (Max - Min). Shows position within the band. |

### Equity Audit Checklist

| Check | Method | Flag When |
|-------|--------|-----------|
| Band outliers | Compa-ratio for each employee | <0.85 or >1.15 |
| Compression | Senior vs. junior pay gap within same team | Gap <10% between levels |
| Inversion | Junior employee paid more than senior in same role | Any occurrence |
| Tenure-pay disconnect | Tenure vs. compa-ratio scatter plot | Long tenure + low compa-ratio |
| Demographic parity | Compa-ratio by demographic group at same level/role | Statistical gap >3% at same level |
| New hire premium | New hire comp vs. existing employee comp at same level | New hires >10% above existing |

### Compression and Inversion

**Compression**: Pay gap between levels narrows to the point where promotion provides minimal pay increase. Causes: market-rate new hires at higher rates, insufficient adjustment for promotions, cost-of-living raises that don't keep pace with market movement.

**Fix**: Regular market adjustment cycles (annual minimum), promotion-triggered band placement review, new hire offer calibration against existing team.

**Inversion**: Junior employee compensated higher than senior peer in same role family. Causes: hot market hiring, location arbitrage changes, acquisition-inherited comp.

**Fix**: Immediate review of senior employee's compensation. Inversion is never acceptable as a steady state.

---

## Offer Structuring

### Package Assembly Checklist

| Component | Inputs Needed | Typical Flexibility |
|-----------|---------------|-------------------|
| Base salary | Role, level, location, band, budget | ±5-10% from target |
| Equity | Stage, grant pool, vesting schedule, valuation method | Moderate — pool-constrained |
| Signing bonus | Competing offer gap, relocation, clawback terms | High — one-time cost |
| Target bonus | Role level, company plan | Low — typically standardized |
| Start date | Candidate availability, team readiness | Moderate |
| Title | Internal leveling, candidate expectations | Low — must match internal framework |
| Location | Office requirement, remote policy, tax implications | Varies by company policy |

### Equity Grant Design

| Parameter | Common Structures |
|-----------|------------------|
| **Vesting schedule** | 4-year with 1-year cliff (standard), 4-year monthly (increasingly common), 3-year annual (uncommon) |
| **Grant type** | RSUs (public/late-stage), ISOs (startup, tax-advantaged), NSOs (startup, above ISO limit) |
| **Refresh cadence** | Annual (top companies), ad-hoc (most companies), none (concerning for retention) |
| **Valuation method** | 409A (private), market price (public), projected (speculative — flag this) |

### Negotiation Framework for Hiring Managers

| Lever | When to Use | Watch For |
|-------|-------------|-----------|
| Base increase | Candidate cites competing offer or market data | Internal equity impact — raising one creates comparison |
| Equity increase | Candidate values long-term upside | Pool constraints, dilution limits |
| Signing bonus | Bridge gap without raising base (no recurring cost) | Clawback terms, candidate sees through short-term fix |
| Title upgrade | Candidate has title sensitivity | Must match internal leveling. Never give a title the person can't perform at. |
| Start date flexibility | Candidate needs time for transition | Team's hiring urgency |
| Remote work | Candidate prefers flexibility | Must align with policy. Don't make one-off exceptions. |
| Relocation package | Candidate must relocate | One-time cost, specify exactly what's covered |

### Offer Letter Compliance

| Jurisdiction Issue | What to Check |
|-------------------|---------------|
| At-will employment | Required in most US states. Some states (Montana) differ. |
| Salary transparency | NYC, CO, CA, WA, and growing list require salary ranges in postings and offers |
| Non-compete | Unenforceable in CA, limited in many states, FTC rule pending |
| Benefits enrollment | Enrollment windows, waiting periods, state-mandated minimums |
| Equity tax treatment | ISOs vs. NSOs, 83(b) elections, RSU tax at vesting — always recommend tax advisor |
| International | Employment law varies dramatically. Local counsel required. |

**Every offer letter draft must include the disclaimer: "This draft requires legal review before sending to the candidate."**

---

## Equity Modeling

### RSU Modeling Template

| Parameter | Input | Notes |
|-----------|-------|-------|
| Grant size | [X] shares/units | |
| Current share price | $[X] | 409A for private, market for public |
| Vesting schedule | [X]-year, [cliff?], [monthly/quarterly/annual] | |
| Annual refresh | [X] shares/year (if applicable) | |
| Projected growth rate | [X]% annually (if modeling upside) | Always label as projection, never as guarantee |

### Option Modeling

| Parameter | Description |
|-----------|-------------|
| Strike price | Price at which the option can be exercised (409A value at grant) |
| Current FMV | Fair market value at time of analysis |
| Spread | FMV - Strike = current paper value per share |
| Shares granted | Total option shares |
| Vested shares | Shares exercisable today |
| Cost to exercise | Vested shares * strike price |
| Paper value | Vested shares * spread |
| Tax implications | ISO: AMT on exercise, capital gains on sale. NSO: ordinary income on exercise. |

### Equity Communication Rules

| Do | Don't |
|-----|-------|
| Present equity as a range of outcomes | Present a single "expected" value |
| Label projections explicitly | Imply growth rates are guaranteed |
| Explain dilution risk | Ignore dilution in projections |
| Recommend a tax advisor | Provide tax advice |
| Explain vesting schedule clearly | Bury cliff or forfeiture terms |
| Show paper value AND liquidity constraints | Show only paper value |

---

## Retention Risk Assessment

### Flight Risk Indicators

| Factor | Risk Signal | Weight |
|--------|------------|--------|
| Compa-ratio | <0.85 | High |
| Time since last adjustment | >18 months | Medium |
| Performance rating | Exceeds + below-market comp | High (regrettable attrition risk) |
| Tenure | 2-3 years (vesting cliff), 18 months (common transition point) | Medium |
| Manager relationship | Low manager effectiveness scores | Medium |
| Market demand | Hot market for their skill set | High |
| Equity cliff | Approaching vesting cliff with no refresh | High |

### Retention Intervention Timing

| Risk Level | Action | Timeline |
|-----------|--------|----------|
| Watch | Monitor, flag for next comp cycle | Next quarter |
| Elevated | Manager 1:1 to assess satisfaction, off-cycle adjustment consideration | Within 2 weeks |
| Critical | Retention package: equity refresh + base adjustment + career conversation | Immediately |

**Retention packages after a counter-offer have 50% failure rate within 12 months.** Proactive retention before the resignation is 3x more effective than reactive counter-offers.
