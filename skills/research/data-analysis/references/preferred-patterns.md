# Data Analysis Patterns to Detect and Fix

Extended catalog of patterns beyond the top 5 in the main SKILL.md. Each entry includes the signal, why it matters, and what to do instead.

---

## Methodology Patterns to Fix

### Data-First Analysis (also in SKILL.md)

**What it looks like**: Jumping straight to `pd.read_csv()` and running `.describe()` before establishing the decision context.

**Why wrong**: Produces technically correct summaries that answer the wrong question. The analyst presents "interesting findings" but the decision-maker cannot act because the findings do not map to their options.

**Do instead**: Complete Phase 1 (FRAME) first. Even 5 minutes of framing prevents hours of wasted analysis.

---

### Confirmation Bias in Extraction

**What it looks like**: Loading data and immediately computing the metric the analyst expects to find, without profiling the data first.

```python
# Bad: Jump straight to the metric
df = pd.read_csv('data.csv')
print(f"Conversion improved: {df[df.group=='B'].converted.mean() - df[df.group=='A'].converted.mean():.1%}")
```

**Why wrong**: Skipping data profiling misses quality issues that invalidate the metric. Missing values, date gaps, or population mismatches silently distort the result.

**Do instead**: Separate extraction (Phase 3) from analysis (Phase 4). Profile data quality before computing any metric.

```python
# Good: Profile first
df = pd.read_csv('data.csv')
print(f"Rows: {len(df)}")
print(f"Missing values:\n{df.isnull().sum()}")
print(f"Date range: {df.date.min()} to {df.date.max()}")
print(f"Group sizes: {df.group.value_counts().to_dict()}")
# THEN compute metrics
```

---

### Moving the Goalposts

**What it looks like**: Defining success as "5% lift" in Phase 2, then declaring success at 3% lift because "3% is still meaningful."

**Why wrong**: Post-hoc threshold adjustment is a form of p-hacking. The threshold was set before data was seen for a reason -- changing it after invalidates the pre-registration. If 3% is truly meaningful, that should have been the threshold from the start.

**Do instead**: If the result falls below the pre-defined threshold, report it as not meeting the threshold. If the stakeholder believes the threshold was wrong, document the revised threshold and note that it was changed after seeing results.

---

### Survivorship Bias

**What it looks like**: Analyzing only "active users" or "successful transactions" without accounting for those who churned or failed.

```
"Our average customer lifetime value is $500"
(Computed only from customers still active -- ignoring the 40% who churned in month 1)
```

**Why wrong**: Excluding failures inflates metrics. The real average CLV includes the customers who paid $0 after churning. Survivorship bias makes everything look better than it is.

**Do instead**: Define the population before filtering. Start with ALL users/events, then apply filters with explicit disclosure:
```
"Average CLV: $500 for retained customers (60% of cohort).
 Including churned customers: $300."
```

---

### Simpson's Paradox Ignorance

**What it looks like**: Reporting an aggregate trend without checking if the trend reverses within segments.

```
"Overall conversion improved from 3% to 4%"
(But: desktop went from 5% to 4%, mobile went from 1% to 1.5%.
 The "improvement" is entirely from more traffic shifting to higher-converting desktop.)
```

**Why wrong**: The aggregate trend can be the opposite of every segment's trend when segment sizes shift. Acting on the aggregate would mean doing more of what is not working.

**Do instead**: Always check at least one level of segmentation. If segment trends contradict the aggregate, report the segment-level finding as the primary result.

---

## Statistical Patterns to Fix

### Point Estimates Without Uncertainty (also in SKILL.md)

**What it looks like**: "The conversion rate is 4.2%."

**Why wrong**: No sample size, no confidence interval, no context for reliability. 4.2% from 50 users is noise. 4.2% from 50,000 users is signal.

**Do instead**: "Conversion rate: 4.2% (95% CI: 3.8-4.6%, N=12,400)."

---

### Relative Change Without Base Rate (also in SKILL.md)

**What it looks like**: "Revenue increased 200%!" or "Error rate dropped 50%!"

**Why wrong**: 200% of $10 is $30. 50% drop from 0.1% is 0.05%. Relative numbers without base rates mislead by making small changes sound large (or large changes sound small).

**Do instead**: Always include the base rate: "Revenue increased from $10K to $30K (+200%)" or "Error rate dropped from 0.10% to 0.05% (-50%)."

---

### P-Value Worship

**What it looks like**: "p < 0.05 therefore the effect is real and we should ship it."

**Why wrong**: Statistical significance tells you the probability of seeing this data if there were no effect. It does NOT tell you:
- How large the effect is (could be trivially small)
- Whether the effect matters for your business
- Whether your sample was representative
- Whether there are confounders

**Do instead**: Report p-value as ONE input alongside effect size, confidence interval, practical significance threshold, and known limitations.

---

### Multiple Comparisons Without Correction (also in SKILL.md)

**What it looks like**: Testing 20 user segments, finding one with p < 0.05, and reporting it as a significant finding.

**Why wrong**: At alpha=0.05, testing 20 segments gives a 64% chance of at least one false positive (1 - 0.95^20). The "finding" is likely noise.

**Do instead**: Apply Bonferroni correction (divide alpha by number of tests) or label the analysis as exploratory requiring confirmation.

---

### Confusing Correlation with Causation

**What it looks like**: "Users who complete onboarding have 3x higher retention. We should force all users to complete onboarding."

**Why wrong**: Users who complete onboarding may be more motivated to begin with. Forcing unmotivated users through onboarding will not make them motivated. The correlation may reflect selection, not treatment.

**Do instead**: Report as correlation. Note that causation requires an experiment (A/B test) or quasi-experimental methods. If the user needs causal claims, recommend an experiment design.

---

## Communication Patterns to Fix

### Methods-First Communication (also in SKILL.md)

**What it looks like**: Leading with statistical methodology instead of business insight.

**Why wrong**: The decision-maker does not need to know you used OLS regression. They need to know revenue is declining.

**Do instead**: Lead with the insight. Put methodology in the appendix.

---

### Data Dump

**What it looks like**: Presenting every computed metric in a giant table without highlighting what matters.

**Why wrong**: The decision-maker drowns in numbers. Key findings are buried. Analysis without prioritization is not analysis -- it is a spreadsheet.

**Do instead**: Lead with the 1-3 most important findings. Use the headline/evidence/limitations structure. Reference the full data in an appendix.

---

### Certainty Theater

**What it looks like**: Presenting conclusions with absolute confidence when the data has significant limitations.

```
"We have definitively proven that the new pricing model increases revenue."
```

**Why wrong**: "Definitively proven" implies controlled experiment with no confounders. Most business analyses have significant caveats. Overstating certainty sets up the decision-maker for surprise when reality diverges.

**Do instead**: State confidence level explicitly:
```
"Revenue increased 12% after the pricing change (95% CI: 5-19%).
 However, the comparison period included a holiday season,
 which may account for 3-5% of the increase."
```

---

### Hiding Inconclusive Results

**What it looks like**: Omitting analyses that showed no significant effect, only reporting the ones that "worked."

**Why wrong**: Publication bias at the individual analysis level. The decision-maker needs to know that 4 of 5 metrics showed no effect -- that IS a finding. It means the intervention probably does not work, despite one metric being marginally significant.

**Do instead**: Report all planned analyses. "We tested 5 metrics. Only email open rate showed significance (p=0.04). The other 4 metrics showed no significant change. Given the multiple testing context, the email open rate result should be treated with caution."

---

## Process Patterns to Fix

### Silent Definition Changes (also in SKILL.md)

**What it looks like**: Changing how a metric is computed after seeing the data without documenting the change.

**Why wrong**: Invalidates the pre-registration. Makes it impossible to audit whether the analyst cherry-picked a favorable definition.

**Do instead**: Return to Phase 2, update the definition with a changelog entry explaining why.

---

### No Artifact Trail

**What it looks like**: Performing analysis entirely in conversation without saving intermediate artifacts.

**Why wrong**: When context compresses or the session ends, all work is lost. No one can audit the methodology. Reproducibility is zero.

**Do instead**: Save artifacts at every phase: analysis-frame.md, metric-definitions.md, data-quality-report.md, analysis-results.md, analysis-report.md.

---

### Scope Creep in Analysis

**What it looks like**: "While I was analyzing conversion, I also looked at retention, engagement, revenue per user, session length, and feature adoption."

**Why wrong**: Each additional metric dilutes focus and increases multiple testing risk. The original decision was about conversion -- other metrics are interesting but not actionable without their own decision frame.

**Do instead**: Answer the question that was asked. If other findings emerge, note them as "exploratory observations for future investigation" -- do not present them as findings of this analysis.

---

### Copy-Paste Methodology

**What it looks like**: Applying the same analytical approach to every dataset regardless of the data characteristics or decision context.

**Why wrong**: A/B test evaluation requires different methods than trend analysis. Distribution profiling requires different methods than cohort comparison. Using the wrong template produces misleading output.

**Do instead**: Select the analysis template based on the decision question:
- "Which option is better?" -> A/B Test / Cohort Comparison
- "Is it getting better or worse?" -> Trend Analysis
- "What does the distribution look like?" -> Distribution Profiling
- "Where do we lose users?" -> Funnel Analysis
- "What happened?" -> Anomaly Investigation
