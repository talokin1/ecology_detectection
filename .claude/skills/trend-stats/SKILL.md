---
name: trend-stats
description: Statistical trend analysis for the Earth System Trend Detective project. Use for ANY trend slope, significance test (Mann-Kendall, t-test, CI), deseasonalisation, autocorrelation handling, per-pixel trend maps, FDR, "years until detectable", verdict wording, or when checking a teammate's statistics.
---

# Trend statistics

The reference implementation is `scripts/trend_stats.py` (numpy + scipy only, 16 tests in
`scripts/test_trend_stats.py`). Methodology for judges: `docs/10-methods.md`. **Import and reuse
it; never re-implement a test inline.** If the backend needs it, copy it into `backend/` unchanged
(keep tests) or import from a shared package — do not fork the maths.

## Default recipe (one regional series)
```python
import sys; sys.path.insert(0, ".claude/skills/trend-stats/scripts")
from trend_stats import analyze_series
result = analyze_series(dates, values, units="K", variable_name="Air temperature")
# -> JSON-ready dict: Sen slope/decade + 95% CI, MK (Yue-Wang) p, OLS n_eff cross-check,
#    total/percent change, noise std & r1, years_to_detect, verdict {level, direction, text}
```
Inputs: monthly values (`obs_per_year=12`, default, deseasonalised automatically) or annual values
(`obs_per_year=1`, `deseasonalize_monthly=False`). Aggregate daily → monthly first.

## Rules
1. **Seasonality**: always analyse anomalies for sub-annual data. Show raw + anomalies in the chart.
2. **Primary test**: Mann-Kendall with Yue-Wang AR(1) correction (`method="yue_wang"`). Cross-check with
   `ols_trend(..., adjust_autocorr=True)`. If the two disagree on significance at 0.05, say so and use
   the more conservative verdict: the card shows the weaker verdict plus a "Two methods disagree"
   line, and the row does not count as a multiple-testing pass (plan-v2 Verdict section, merge plan v2 Q8).
3. **Do not use** classic MK or Hamed-Rao as the reported result for autocorrelated data — our Monte-Carlo
   (`scripts/validate_type1.py`) shows 14–33% and 10–21% false positives at φ = 0.3–0.6.
4. **Units**: slope per decade in the variable's display units; percent change only for ratio-scale
   variables (precipitation, NO2, NDVI, soil moisture) — never for temperature.
5. **Record length**: < 10 years → "insufficient"; warn when < 20 years or when the series has > 20% gaps.
6. **Regional mean**: `area_weighted_mean(field, lats)` (cos-latitude weights) before analysis.
7. **Maps**: per-cell `mann_kendall` + `sens_slope`, then `fdr_bh(pvals, q=0.05)` for stippling.
   Mask cells with < 80% valid months.
8. **Detectability**: `years_to_detect` uses deseasonalised residual std and lag-1 r; present as
   "≈ N more years at the current rate", rounded, with the caveat that rates may change.
9. **Never** tune parameters to reach significance, drop inconvenient years, or report a p-value
   without n, period and method.
10. Before any number reaches UI/slides, run the `stats-validator` subagent on it.

## Interpreting for the audience (copy patterns)
- p-value: "the chance of seeing a trend at least this strong if nothing were really changing".
- CI: "the slope is most likely between A and B per decade".
- Non-significant: "not proven yet ≠ no change" + years-to-detect.
- Opposite trends: "the same process (e.g. a shifting storm track) can dry one region and wet another."

## Tests
`python -m pytest -q .claude/skills/trend-stats/scripts` — must pass before merging changes to the maths.
`python .claude/skills/trend-stats/scripts/validate_type1.py --runs 300` regenerates the validation table.
