# Data Analysis — Compute Examples

Python code patterns for Phase 3 (EXTRACT) and Phase 4 (ANALYZE). Use these when writing analysis scripts.

---

## Tool Detection (Phase 3 Step 1)

```python
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
```

If pandas is unavailable, fall back to `csv.DictReader` + `statistics` module. Analysis quality must be identical -- only presentation differs.

---

## Metric Computation (Phase 4 Step 1)

### stdlib approach (no external dependencies)

```python
import csv, statistics, collections, math

with open(data_file) as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# Example: conversion rate with Wilson score confidence interval
successes = sum(1 for r in rows if r['converted'] == '1')
total = len(rows)
rate = successes / total
z = 1.96  # 95% CI
denominator = 1 + z**2 / total
centre = (rate + z**2 / (2 * total)) / denominator
spread = z * math.sqrt((rate * (1 - rate) + z**2 / (4 * total)) / total) / denominator
ci_lower = centre - spread
ci_upper = centre + spread
```

### pandas approach (when available)

```python
import pandas as pd

df = pd.read_csv(data_file)
rate = df['converted'].mean()
# Bootstrap CI or Wilson as above
```

---

## Multiple Testing Correction (Phase 4 Step 3)

| Scenario | Correction |
|----------|------------|
| 2-5 comparisons | Report all p-values, flag that they are unadjusted |
| 6+ comparisons | Apply Bonferroni: adjusted threshold = 0.05 / N |
| Exploratory sweep | Label as exploratory, make no causal claims |

See `references/rigor-gates.md` Gate 3 for the full Bonferroni implementation.
