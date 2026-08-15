# Statistical Rigor Gates

Detailed documentation for the four statistical rigor gates applied during Phase 4 (ANALYZE). These are hard gates -- analysis that fails a gate must either remediate or explicitly document the violation as a limitation in the conclusion.

---

## Gate 1: Sample Adequacy

**Purpose**: Verify the data is sufficient to draw meaningful conclusions before computing any summary statistic.

**Why this gate exists**: Small or incomplete samples produce wide confidence intervals that cannot support decisions. Computing metrics on inadequate samples gives false confidence -- the number looks precise but is not.

### Checks

| Check | Minimum | Action if Failed |
|-------|---------|------------------|
| Row count vs. population | Report sample fraction | State "N of M" and warn if <5% coverage |
| Time window completeness | No gaps >10% of window | Identify gaps, adjust window or note limitation |
| Segment minimums | 30+ observations per segment | Merge small segments or exclude with disclosure |
| Missing value rate | <20% per critical column | Impute with disclosure or exclude column |

### Row Count Assessment

```python
import math

def assess_sample(sample_size, population_size=None, confidence=0.95, margin=0.05):
    """Assess whether sample size is adequate."""
    z = 1.96  # 95% confidence
    # Minimum sample for proportion estimation at given margin
    min_sample = math.ceil((z**2 * 0.25) / (margin**2))

    result = {
        'sample_size': sample_size,
        'min_for_5pct_margin': min_sample,
        'adequate': sample_size >= min_sample,
    }

    if population_size:
        result['coverage'] = sample_size / population_size
        result['coverage_warning'] = result['coverage'] < 0.05
        # Finite population correction
        adjusted_min = math.ceil(
            min_sample / (1 + (min_sample - 1) / population_size)
        )
        result['adjusted_min'] = adjusted_min
        result['adequate'] = sample_size >= adjusted_min

    return result
```

### Time Window Completeness

Check for gaps in temporal data:

```python
from datetime import datetime, timedelta

def check_time_gaps(dates, expected_granularity='daily'):
    """Identify gaps in time series data."""
    sorted_dates = sorted(set(dates))
    gaps = []
    delta = timedelta(days=1) if expected_granularity == 'daily' else timedelta(weeks=1)

    for i in range(1, len(sorted_dates)):
        actual_gap = sorted_dates[i] - sorted_dates[i-1]
        if actual_gap > delta * 1.5:  # Allow small tolerance
            gaps.append({
                'start': sorted_dates[i-1],
                'end': sorted_dates[i],
                'duration': actual_gap,
            })

    total_window = sorted_dates[-1] - sorted_dates[0]
    gap_duration = sum((g['duration'] for g in gaps), timedelta())
    gap_pct = gap_duration / total_window if total_window.days > 0 else 0

    return {
        'gaps': gaps,
        'gap_count': len(gaps),
        'gap_percentage': gap_pct,
        'passes': gap_pct <= 0.10,  # Pass if gaps <= 10% of window
    }
```

### Segment Minimums

The 30-observation minimum per segment comes from the Central Limit Theorem -- below ~30, the sampling distribution of the mean is not reliably normal, which invalidates standard confidence interval calculations.

For segments below 30:
1. **Merge**: Combine related small segments (e.g., "Northeast" + "Southeast" -> "East")
2. **Exclude**: Remove the segment with explicit disclosure ("Excluded segments with <30 observations: [list]")
3. **Accept**: Keep with disclosure that confidence intervals may be unreliable for small segments

### Missing Value Assessment

```python
def assess_missing(data, columns, critical_columns=None):
    """Assess missing value rates per column."""
    if critical_columns is None:
        critical_columns = columns

    report = {}
    for col in columns:
        total = len(data)
        missing = sum(1 for row in data if not row.get(col) or row[col] in ('', 'NA', 'null', 'None'))
        pct = missing / total if total > 0 else 0
        is_critical = col in critical_columns

        report[col] = {
            'missing': missing,
            'total': total,
            'pct': pct,
            'critical': is_critical,
            'passes': pct <= 0.20 or not is_critical,
        }

    return report
```

**Handling missing values**:
- **<5%**: Safe to drop rows or ignore. Minimal impact on analysis.
- **5-20%**: Analyze with and without missing rows. If results differ materially, investigate the missingness pattern (is it random or systematic?).
- **>20% in critical column**: The column is unreliable. Either find an alternative data source, impute with explicit disclosure of method, or exclude with documentation.

---

## Gate 2: Comparison Fairness

**Purpose**: Verify that group comparisons are apples-to-apples before drawing conclusions.

**Why this gate exists**: Unfair comparisons produce misleading results. Comparing Q1 to Q3 confounds seasonality with the variable of interest. Comparing active users to all users conflates engagement with the treatment effect. These errors are easy to make and hard to detect after the fact.

### Checks

| Check | Requirement | Common Violation |
|-------|-------------|------------------|
| Same time window | Groups cover identical periods | Comparing Q1 of year A to Q3 of year B |
| Same population definition | Groups drawn from same base | Comparing active users to all users |
| Confounding variables | Identify and document known confounders | Attributing outcome to single variable without controls |
| Survivorship bias | Check if selection criteria exclude failures | Analyzing "successful" cohorts without the failures |

### Time Window Alignment

```python
def check_time_alignment(group_a_dates, group_b_dates):
    """Verify groups cover the same time period."""
    a_start, a_end = min(group_a_dates), max(group_a_dates)
    b_start, b_end = min(group_b_dates), max(group_b_dates)

    overlap_start = max(a_start, b_start)
    overlap_end = min(a_end, b_end)

    a_range = (a_end - a_start).days
    b_range = (b_end - b_start).days
    overlap = max(0, (overlap_end - overlap_start).days)

    alignment = overlap / max(a_range, b_range) if max(a_range, b_range) > 0 else 0

    return {
        'group_a_range': f"{a_start} to {a_end}",
        'group_b_range': f"{b_start} to {b_end}",
        'overlap_pct': alignment,
        'passes': alignment >= 0.90,  # 90% overlap minimum
        'warning': f"Groups cover different periods" if alignment < 0.90 else None,
    }
```

### Population Definition Check

Verify groups are drawn from the same base population:
- Both groups should have the same inclusion/exclusion criteria except for the variable being tested
- Check for self-selection bias: did users choose which group they are in?
- Check for survivorship bias: does one group exclude users who churned/failed/left?

### Confounding Variable Documentation

For each comparison, list known confounders:

```markdown
### Confounders
| Variable | Affects | Controlled? | Method |
|----------|---------|-------------|--------|
| Seasonality | Conversion rate | Yes | Same time window |
| Device type | Page load time | Partially | Reported by segment |
| User tenure | Retention | No | Documented as limitation |
```

If a confounder is not controlled, it must appear in the Limitations section of the final report.

---

## Gate 3: Multiple Testing Correction

**Purpose**: Prevent false discoveries when testing multiple hypotheses simultaneously.

**Why this gate exists**: At a 5% significance level, 1 in 20 tests will be "significant" by chance. If you test 20 segments, you expect one false positive. Without correction, the analyst reports this false positive as a real finding. Multiple testing correction prevents this.

### Decision Table

| Scenario | Number of Tests | Correction | Example |
|----------|----------------|------------|---------|
| Single hypothesis | 1 | None needed | "Did conversion improve?" |
| Few comparisons | 2-5 | Report all p-values, note unadjusted | A/B test with primary + 2 secondary metrics |
| Many comparisons | 6+ | Bonferroni: alpha / N | Analyzing 20 user segments for significance |
| Exploratory sweep | Any | Label as exploratory | "Which of 50 features correlates with churn?" |

### Bonferroni Correction

The simplest and most conservative correction:

```python
def bonferroni_correction(p_values, alpha=0.05):
    """Apply Bonferroni correction to multiple p-values."""
    n_tests = len(p_values)
    adjusted_alpha = alpha / n_tests

    results = []
    for name, p in p_values:
        results.append({
            'test': name,
            'p_value': p,
            'adjusted_alpha': adjusted_alpha,
            'significant_after_correction': p < adjusted_alpha,
            'significant_unadjusted': p < alpha,
        })

    return {
        'n_tests': n_tests,
        'original_alpha': alpha,
        'adjusted_alpha': adjusted_alpha,
        'results': results,
    }
```

### When to Apply

- **Pre-specified primary metric**: No correction needed for the single primary outcome
- **Secondary metrics**: Report as secondary; note they are not corrected unless 6+
- **Subgroup analyses**: Almost always require correction (or labeling as exploratory)
- **Data dredging / feature sweeps**: MUST be labeled exploratory with no causal claims

### Reporting Pattern

When multiple tests are performed, report transparently:

```markdown
## Multiple Testing Note
- Tests performed: [N]
- Correction method: [Bonferroni / None (reported as unadjusted) / Exploratory label]
- Adjusted significance threshold: [alpha / N]
- Tests significant after correction: [list]
- Tests significant before correction only: [list -- interpret with caution]
```

---

## Gate 4: Practical Significance

**Purpose**: Ensure statistically significant results are also meaningful in practice.

**Why this gate exists**: With enough data, tiny effects become statistically significant. A 0.01% conversion lift with p=0.001 is statistically significant but practically meaningless if your minimum actionable threshold is 1%. Practical significance bridges the gap between "real effect" and "worth acting on."

### Requirements

| Metric | Requirement | Why |
|--------|-------------|-----|
| Effect size | Report alongside p-value | "5% lift (p=0.03)" not just "p=0.03" |
| Confidence interval | Report range, not point estimate | "3-7% lift" not "5% lift" |
| Business threshold | Compare to minimum actionable threshold | "5% lift exceeds our 2% threshold for shipping" |
| Base rate context | Show absolute numbers, not just relative | "2.1% to 2.3%" not just "+10% lift" |

### Effect Size Calculation

```python
import math

def cohens_d(mean_a, mean_b, std_a, std_b, n_a, n_b):
    """Calculate Cohen's d for two independent groups."""
    pooled_std = math.sqrt(
        ((n_a - 1) * std_a**2 + (n_b - 1) * std_b**2)
        / (n_a + n_b - 2)
    )
    d = (mean_a - mean_b) / pooled_std if pooled_std > 0 else 0

    # Interpretation
    if abs(d) < 0.2:
        interpretation = "negligible"
    elif abs(d) < 0.5:
        interpretation = "small"
    elif abs(d) < 0.8:
        interpretation = "medium"
    else:
        interpretation = "large"

    return {
        'cohens_d': d,
        'interpretation': interpretation,
    }

def relative_and_absolute_change(baseline, treatment):
    """Report both relative and absolute change."""
    absolute = treatment - baseline
    relative = (treatment - baseline) / baseline if baseline != 0 else float('inf')
    return {
        'baseline': baseline,
        'treatment': treatment,
        'absolute_change': absolute,
        'relative_change_pct': relative * 100,
        'summary': f"{baseline:.2%} to {treatment:.2%} (absolute: {absolute:+.2%}, relative: {relative:+.1%})"
    }
```

### Base Rate Context

Always provide base rate context to prevent misleading relative claims:

| Misleading | Informative |
|------------|-------------|
| "+50% lift!" | "Conversion rose from 0.2% to 0.3%" |
| "-30% reduction in errors" | "Error rate dropped from 3.0% to 2.1%" |
| "2x improvement" | "p99 latency improved from 800ms to 400ms" |

The absolute numbers tell the decision-maker whether the change matters. A 50% lift sounds huge; going from 0.2% to 0.3% may not justify any action.

### Decision Mapping

At the end of Phase 4, map each finding to the decision:

```markdown
## Practical Significance Assessment

| Finding | Effect Size | CI | Threshold | Actionable? |
|---------|------------|-----|-----------|-------------|
| Conversion lift | +0.3% | [-0.1%, 0.7%] | 1.0% | No -- below threshold and CI includes zero |
| Churn reduction | -2.1% | [-3.5%, -0.7%] | 1.0% | Yes -- exceeds threshold, CI excludes zero |
| Revenue impact | +$12K/mo | [$3K, $21K] | $10K/mo | Marginal -- point estimate exceeds but CI lower bound does not |
```

---

## Applying Gates: Decision Tree

```
START: Metric computed
  |
  v
Gate 1: Is sample adequate?
  |-- NO --> Document limitation. Can remediate?
  |            |-- YES --> Merge segments / narrow window / impute
  |            |-- NO  --> Proceed with "insufficient data" caveat
  |
  |-- YES --> Continue
  |
  v
Gate 2: Is comparison fair? (if comparing groups)
  |-- NO --> Document unfairness. Can fix?
  |            |-- YES --> Align windows / match populations
  |            |-- NO  --> Proceed with "unfair comparison" caveat
  |
  |-- YES / N/A --> Continue
  |
  v
Gate 3: Multiple testing? (if >1 hypothesis)
  |-- YES, 2-5 --> Report all, note unadjusted
  |-- YES, 6+  --> Apply Bonferroni, report adjusted
  |-- Exploratory --> Label as exploratory, no causal claims
  |-- NO --> Continue
  |
  v
Gate 4: Is effect practically significant?
  |-- Below threshold --> "Statistically significant but not actionable"
  |-- Above threshold --> "Significant and actionable"
  |-- CI includes zero --> "Inconclusive"
  |
  v
DONE: Gate results documented in analysis-results.md
```
