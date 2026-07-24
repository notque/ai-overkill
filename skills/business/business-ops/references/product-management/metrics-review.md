# Metrics Review Reference

Deep reference for product metrics analysis, goal-setting, and dashboard design. Loaded by METRICS mode.

---

## Product Metrics Hierarchy

### North Star Metric

The single metric capturing core value delivered. Must be:

| Property | Test |
|----------|------|
| Value-aligned | Moves when users get more value |
| Leading | Predicts long-term business success |
| Actionable | Product team can influence it |
| Understandable | Everyone in the company gets it |

**Examples by product type**:

| Product Type | North Star | Why |
|-------------|------------|-----|
| Collaboration tool | Weekly active teams with 3+ contributing members | Measures collaborative value, not just logins |
| Marketplace | Weekly transactions completed | Measures successful exchange, not just visits |
| SaaS platform | Weekly active users completing core workflow | Measures real usage, not just opening the app |
| Content platform | Weekly engaged reading/viewing time | Measures attention, not clicks |
| Developer tool | Weekly deployments using the tool | Measures integration into real workflow |

### L1 Metrics — Health Indicators

5-7 metrics that together paint complete product health across the user lifecycle.

#### Acquisition

| Metric | What It Answers |
|--------|----------------|
| New signups / trial starts | Are new users finding us? |
| Signup conversion rate | Are visitors converting? |
| Channel mix | Where are new users coming from? |
| Cost per acquisition | What are we paying per new user (paid channels)? |

#### Activation

| Metric | What It Answers |
|--------|----------------|
| Activation rate | % of new users completing the key action predicting retention |
| Time to activate | How long from signup to activation? |
| Setup completion rate | % completing onboarding steps |
| First value moment | When users first experience core value |

**Defining activation**: Look at retained vs churned users. What actions did retained users take that churned did not? The activation event should be strongly predictive of long-term retention and achievable within the first session or few days.

#### Engagement

| Metric | What It Answers |
|--------|----------------|
| DAU / WAU / MAU | How many active users at each timeframe? |
| DAU/MAU ratio (stickiness) | What fraction of monthly users return daily? (>0.5 = daily habit, <0.2 = infrequent) |
| Core action frequency | How often users do the thing that matters most |
| Session depth | How much users do per session |
| Feature adoption | % using key features |

**Defining "active"**: A login? A page view? A core action? Different definitions tell different stories. Choose deliberately and document.

#### Retention

| Metric | What It Answers |
|--------|----------------|
| D1 / D7 / D30 / D90 retention | % returning after 1 day / 1 week / 1 month / 3 months |
| Cohort retention curves | How retention evolves per signup cohort |
| Churn rate | % of users or revenue lost per period |
| Resurrection rate | % of churned users who return |

**Reading retention curves**:

| Shape | Diagnosis |
|-------|-----------|
| Steep initial drop, then flat | Activation problem. Users who survive the first few days stick. |
| Steady decline without flattening | Engagement problem. No habit formed. |
| Flat early, then gradual decline | Initial value delivered but not sustained. |
| Improving across cohorts | Product improvements working. |

#### Monetization

| Metric | What It Answers |
|--------|----------------|
| Free to paid conversion | Are users upgrading? |
| MRR / ARR | What is recurring revenue? |
| ARPU / ARPA | Revenue per user/account? |
| Expansion revenue | Growth from existing customers? |
| Net revenue retention | Revenue retained including expansion + contraction? |

#### Satisfaction

| Metric | What It Answers |
|--------|----------------|
| NPS | Would users recommend? |
| CSAT | Are users satisfied with specific interactions? |
| Support ticket volume | Are issues increasing or decreasing? |
| App store ratings | What do public reviews say? |

### L2 Metrics — Diagnostic

Used to investigate L1 changes. Load on demand, not reviewed routinely.

- Funnel conversion at each step
- Feature-level usage and adoption
- Segment breakdowns (plan, company size, geography, role)
- Performance metrics (load time, error rate, API latency)
- Content-specific engagement (which features/pages drive engagement)

---

## KPI Frameworks

### OKRs (Objectives and Key Results)

**Objectives**: Qualitative, aspirational, time-bound, directional, memorable.

**Key Results**: Quantitative, specific, time-bound, outcome-based, 2-4 per Objective.

**Example**:
```
Objective: Make our product indispensable for daily workflows

KR1: Increase DAU/MAU from 0.35 to 0.50
KR2: Increase D30 retention for new users from 40% to 55%
KR3: 3 core workflows with >80% task completion rate
```

**Scoring**: 0.0-0.3 = missed, 0.4-0.6 = progress, 0.7-1.0 = achieved.

**Failure modes**:

| Failure Mode | Problem |
|-------------|---------|
| Too many OKRs (>3 objectives) | Focus diluted, nothing gets done well |
| Output KRs ("ship X features") | Measures activity not impact |
| Sandbagged targets | 100% confidence = not ambitious. Target 70% completion. |
| No mid-period review | Discover off-track too late to correct |
| Dishonest grading | Defeats the purpose of the system |

### Target-Setting Process

| Step | Action | Failure Mode |
|------|--------|-------------|
| 1. Baseline | Establish current reliable value | Setting targets without knowing where you start |
| 2. Benchmark | Check comparable products / industry | Ignoring context (B2B vs B2C retention norms differ 3x) |
| 3. Trajectory | What is current trend? | Setting 6% target when metric already improving 5%/month |
| 4. Effort | How much investment behind this? | Ambitious target with no allocated resources |
| 5. Confidence | Commit (high confidence) vs stretch (ambitious) | Single target with no range |

---

## Funnel Analysis

### Building a Funnel

1. Define the sequence of steps users take to reach the outcome
2. Measure conversion at each step
3. Identify the biggest drop-off points — these are highest-leverage opportunities

### Funnel Metrics

| Metric | Formula | Use |
|--------|---------|-----|
| Step conversion | (Users completing step N) / (Users completing step N-1) | Identify where users drop off |
| Overall conversion | (Users completing final step) / (Users entering funnel) | Overall efficiency |
| Time between steps | Median time from step N to step N+1 | Identify friction points |
| Drop-off rate | 1 - step conversion | Quantify the problem |

### Funnel Analysis Rules

- **Segment everything**: Different user types have wildly different funnels. Enterprise vs SMB, mobile vs desktop, new vs returning.
- **Time-bound**: Define the window. "Signs up and activates within 7 days" is different from "ever activates."
- **Beware averages**: Mean time-to-activate can be misleading if the distribution is bimodal. Use median or percentiles.
- **Attribution**: If you changed multiple things, you cannot attribute funnel changes to one change. Run A/B tests for causal claims.

### Common Funnel Failure Modes

| Failure Mode | Problem | Fix |
|-------------|---------|-----|
| Too many steps | Overwhelms analysis | Focus on 5-7 key decision points |
| Undefined "active" | Different queries give different answers | Document the definition precisely |
| No segmentation | Hides segment-specific problems | Always break down by key dimensions |
| Correlation = causation | "Users who do X retain better" does not mean X causes retention | Design experiments to test causal hypotheses |

---

## Cohort Analysis

### What Cohort Analysis Reveals

Cohort analysis groups users by when they joined (or performed an action) and tracks behavior over time.

**Key insight**: Aggregate metrics mask cohort effects. Overall retention could be declining even as each new cohort retains better — if growth is slowing, older (worse-retaining) cohorts dominate the average.

### Cohort Table Format

```
         Week 0  Week 1  Week 2  Week 3  Week 4
Jan W1   100%    45%     32%     28%     25%
Jan W2   100%    48%     35%     30%     --
Jan W3   100%    52%     38%     --      --
Jan W4   100%    55%     --      --      --
```

**Reading the table**:
- **Rows** (left to right): How a single cohort retains over time. Looking for the curve to flatten.
- **Columns** (top to bottom): How the same retention point improves across cohorts. Are newer cohorts better?
- **Diagonal**: All cohorts at the same calendar time. Reveals seasonal or product-wide effects.

### Cohort Analysis Best Practices

| Practice | Why |
|----------|-----|
| Use behavioral cohorts, not just time | "Users who activated in week 1" reveals more than "users who signed up in January" |
| Compare cohorts before/after changes | Did the onboarding redesign improve D7 retention? Compare pre and post cohorts. |
| Wait for maturity | A 2-week-old cohort cannot tell you about D30 retention. Be patient. |
| Control for externalities | Holidays, marketing campaigns, outages all affect cohorts differently |

---

## Statistical Pitfalls

### The Big Five

| Pitfall | What Happens | Defense |
|---------|-------------|---------|
| **Small sample noise** | Drawing conclusions from tiny datasets | Report sample sizes. Flag n<100 findings as directional only. |
| **Survivorship bias** | Analyzing only users who stayed, ignoring those who left | Include churned/inactive users in analysis. Study drop-offs. |
| **Simpson's Paradox** | Aggregate trend reverses when segmented | Always segment. A flat overall metric can hide one segment growing and another shrinking. |
| **Cherry-picking timeframes** | Choosing the period that tells the story you want | Use consistent comparison periods. Show multiple timeframes. |
| **Vanity metrics** | Metrics that always go up but indicate nothing | Total signups ever, total page views. Use rate metrics instead. |

### Statistical Significance

- For A/B tests: require 95% confidence (p < 0.05) before declaring a winner
- For small samples: be cautious. A 0.1 point NPS change on n=50 is noise.
- For metric movements: distinguish signal from noise. Weekly fluctuations of 5-10% are often normal variance.
- Report confidence intervals, not just point estimates when possible.

### Correlation vs Causation

"Users who use Feature X retain better" does NOT mean Feature X causes retention.

Possible explanations:
1. Feature X causes retention (what you hope)
2. Retained users discover Feature X over time (reverse causation)
3. Power users both use Feature X and retain better (confounding variable)
4. Feature X and retention both correlate with company size (spurious correlation)

**How to establish causation**: Run an A/B experiment. Randomly expose users to Feature X and measure retention difference.

---

## Review Cadences

### Weekly (15-30 min)

| What | Depth |
|------|-------|
| North Star | Current value, WoW change |
| Key L1 metrics | Notable movements only |
| Active experiments | Results, statistical significance |
| Anomalies | Unexpected spikes or drops |
| Alerts | Anything triggered |

**Action threshold**: Investigate if something looks off. Otherwise note and move on.

### Monthly (30-60 min)

| What | Depth |
|------|-------|
| Full L1 scorecard | MoM trends |
| OKR progress | On track / at risk / off track |
| Cohort analysis | Newer cohorts improving? |
| Feature adoption | Recent launches performing? |
| Segment analysis | Divergence between segments? |

**Action**: Identify 1-3 areas to investigate or invest in. Update priorities if metrics reveal new information.

### Quarterly (60-90 min)

| What | Depth |
|------|-------|
| OKR scoring | Grade the quarter honestly |
| L1 trends over quarter | Direction and rate of change |
| Year-over-year comparison | Seasonal adjustment, long-term trajectory |
| Competitive context | Market shifts, competitor movements |
| What worked / what did not | Attribution of results to actions |

**Action**: Set next-quarter OKRs. Adjust product strategy based on data.

---

## Dashboard Design

### Principles

| Principle | Implementation |
|-----------|---------------|
| Question-first | What decisions does this dashboard support? Design backwards from the decision. |
| Information hierarchy | North Star most prominent. L1 next. L2 on drill-down. |
| Context over numbers | Every number shows: current value, comparison, trend direction. |
| Fewer metrics | 5-10 that matter. Everything else in detailed reports. |
| Consistent timeframes | Same period for all metrics. No mixing daily and monthly. |
| Visual status | Green (on track), Yellow (attention), Red (off track). |
| Actionability | Every metric is something the team can influence. |

### Layout

```
┌────────────────────────────────────────┐
│  NORTH STAR: [Metric] + trend + target │
├──────────┬──────────┬──────────────────┤
│ Acquisition │ Activation │ Engagement   │
│ [metrics]   │ [metrics]  │ [metrics]    │
├──────────┬──────────┬──────────────────┤
│ Retention │ Revenue  │ Satisfaction     │
│ [metrics] │ [metrics]│ [metrics]        │
├────────────────────────────────────────┤
│ Active Experiments / Recent Launches   │
├────────────────────────────────────────┤
│ L2 drill-down (on demand)             │
└────────────────────────────────────────┘
```

### Dashboard Failure Modes

| Failure Mode | Why It Fails |
|-------------|-------------|
| Vanity metrics | Total signups ever, total page views — always go up, indicate nothing |
| Too many metrics | If it requires scrolling, cut metrics |
| No comparison | Raw numbers without previous period or target |
| Stale dashboards | Not updated or reviewed in months |
| Output metrics | Tickets closed, PRs merged instead of user/business outcomes |
| One dashboard for all | Execs, PMs, and engineers need different views |

### Alerting

| Alert Type | Trigger | Example |
|-----------|---------|---------|
| Threshold | Metric crosses critical boundary | Error rate > 1%, conversion < 5% |
| Trend | Sustained decline over multiple periods | 3 consecutive weeks of retention decline |
| Anomaly | Significant deviation from expected range | Traffic 50% below predicted |

**Alert hygiene**:
- Every alert is actionable. If you cannot do anything, do not alert.
- Review and tune regularly. False positives train people to ignore all alerts.
- Every alert has an owner. Who responds when it fires?
- Not everything is P0. Set severity levels.

---

## Metric Scorecard Template

```
## Product Metrics Review: [Period]

### Summary
[2-3 sentences: overall health, most notable change, key callout]

### Scorecard
| Metric | Current | Previous | Change | Target | Status |
|--------|---------|----------|--------|--------|--------|
| [North Star] | | | | | |
| Acquisition: Signups | | | | | |
| Activation: Rate | | | | | |
| Engagement: DAU/MAU | | | | | |
| Retention: D30 | | | | | |
| Revenue: MRR | | | | | |
| Satisfaction: NPS | | | | | |

### Trend Analysis
[For each metric worth discussing: what happened, why, one-time or sustained]

### Bright Spots
- [What is going well]

### Areas of Concern
- [What needs attention]

### Recommended Actions
1. [Specific investigation / experiment / investment / alert]

### Caveats
- [Data quality issues, comparability notes, missing metrics]
```
