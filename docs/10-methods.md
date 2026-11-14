# 10 — Statistical Methods (judge-facing)

Implementation: `.claude/skills/trend-stats/scripts/trend_stats.py` (single source of truth, tested).
Every number in the app and slides comes from this code.

## Pipeline for one regional series
1. **Regional mean** — grid cells averaged with cos(latitude) weights (cells shrink toward the poles); NaN-aware.
2. **Temporal resolution** — monthly (daily data aggregated to monthly means/totals first; Sen/MK are O(n²)).
3. **Seasonal cycle removed** — subtract each calendar month's mean (anomalies). Without this the seasonal
   cycle dominates and can create spurious trends when a record starts/ends in different seasons.
4. **Trend magnitude** — Theil–Sen slope (median of all pairwise slopes; robust to outliers),
   reported per decade with a 95% distribution-free confidence interval (Sen 1968; Gilbert 1987).
   The CI uses the autocorrelation-corrected variance of S, so it widens for persistent series.
5. **Significance (primary)** — Mann–Kendall test with the Yue & Wang (2004) effective-sample-size
   correction: Var*(S) = η·Var(S), η = 1 + 2 Σ_{k=1}^{n−1} (1 − k/n) r₁ᵏ, where r₁ is the lag-1
   autocorrelation (≥ 0) of the Sen-detrended series (AR(1) noise model). Ties handled in Var(S).
6. **Significance (secondary, cross-check)** — OLS slope with t-test using the lag-1 effective sample
   size n_eff = n(1 − r₁)/(1 + r₁) of the residuals (Santer et al., 2000).
7. **Detectability** — years of record needed to detect the current trend with 90% probability at the
   5% level (Weatherhead et al., 1998): n* = [(3.3 σ_N √(12/f) / |ω₀|) · √((1+φ)/(1−φ))]^{2/3},
   σ_N = std of deseasonalised residuals, φ = their lag-1 autocorrelation, ω₀ = trend per year,
   f = observations per year (12 → original formula).
8. **Verdict** (plain language):
   | Condition | Verdict |
   |---|---|
   | record < 10 years | insufficient record |
   | p < 0.01 and CI excludes 0 | strong evidence |
   | p < 0.05 | evidence |
   | p < 0.10 | weak, suggestive evidence |
   | otherwise | no significant trend yet + "≈ N more years needed" |

## Trend maps (per grid cell)
Same steps per cell; significance stippling uses Benjamini–Hochberg false-discovery-rate control
(q = 0.05) across all cells, because thousands of independent tests at α = 0.05 would flag ~5% of cells
by chance (Wilks, 2016).

## Why not the classic Mann–Kendall or Hamed–Rao? Our Monte-Carlo check
Satellite and reanalysis anomalies are autocorrelated (month-to-month persistence). We simulated
series with **no trend** (false-positive rate should be 5%) and with a trend (power), using AR(1) noise.
`validate_type1.py --runs 300` output:

runs=300, alpha=0.05, AR(1) unit-variance innovations, power trend=0.06/yr
| n (months) | phi | test | false-positive rate | power |
|---|---|---|---|---|
| 120 | 0.0 | MK original | 0.040 | 0.410 |
| 120 | 0.0 | MK Hamed-Rao | 0.087 | 0.480 |
| 120 | 0.0 | MK Yue-Wang (default) | 0.030 | 0.410 |
| 120 | 0.0 | OLS n_eff | 0.040 | 0.417 |
| 120 | 0.3 | MK original | 0.147 | 0.423 |
| 120 | 0.3 | MK Hamed-Rao | 0.130 | 0.377 |
| 120 | 0.3 | MK Yue-Wang (default) | 0.063 | 0.237 |
| 120 | 0.3 | OLS n_eff | 0.060 | 0.257 |
| 120 | 0.6 | MK original | 0.320 | 0.470 |
| 120 | 0.6 | MK Hamed-Rao | 0.207 | 0.303 |
| 120 | 0.6 | MK Yue-Wang (default) | 0.047 | 0.137 |
| 120 | 0.6 | OLS n_eff | 0.047 | 0.133 |
| 240 | 0.0 | MK original | 0.040 | 1.000 |
| 240 | 0.0 | MK Hamed-Rao | 0.063 | 1.000 |
| 240 | 0.0 | MK Yue-Wang (default) | 0.040 | 1.000 |
| 240 | 0.0 | OLS n_eff | 0.030 | 1.000 |
| 240 | 0.3 | MK original | 0.140 | 0.983 |
| 240 | 0.3 | MK Hamed-Rao | 0.100 | 0.977 |
| 240 | 0.3 | MK Yue-Wang (default) | 0.050 | 0.960 |
| 240 | 0.3 | OLS n_eff | 0.053 | 0.963 |
| 240 | 0.6 | MK original | 0.320 | 0.897 |
| 240 | 0.6 | MK Hamed-Rao | 0.170 | 0.767 |
| 240 | 0.6 | MK Yue-Wang (default) | 0.057 | 0.590 |
| 240 | 0.6 | OLS n_eff | 0.060 | 0.567 |
| 480 | 0.0 | MK original | 0.057 | 1.000 |
| 480 | 0.0 | MK Hamed-Rao | 0.107 | 1.000 |
| 480 | 0.0 | MK Yue-Wang (default) | 0.053 | 1.000 |
| 480 | 0.0 | OLS n_eff | 0.053 | 1.000 |
| 480 | 0.3 | MK original | 0.147 | 1.000 |
| 480 | 0.3 | MK Hamed-Rao | 0.110 | 1.000 |
| 480 | 0.3 | MK Yue-Wang (default) | 0.053 | 1.000 |
| 480 | 0.3 | OLS n_eff | 0.063 | 1.000 |
| 480 | 0.6 | MK original | 0.330 | 1.000 |
| 480 | 0.6 | MK Hamed-Rao | 0.170 | 1.000 |
| 480 | 0.6 | MK Yue-Wang (default) | 0.040 | 1.000 |
| 480 | 0.6 | OLS n_eff | 0.043 | 1.000 |

Findings: the classic MK flags 14–33% of trendless autocorrelated series as "significant"; the
Hamed–Rao correction (as commonly implemented) still flags 10–21%; the Yue–Wang AR(1) correction and
OLS with effective n stay near the nominal 5% while keeping comparable power. Hence Yue–Wang is our
default and OLS-n_eff our cross-check.

## Known limitations (stated honestly in the app)
- Linear/monotonic trends only; abrupt shifts (e.g. reservoir drained, sensor change) are not trends.
- AR(1) noise model; long-memory variability (e.g. ENSO, PDO) can still inflate significance on short records.
- Reanalysis (MERRA-2, GLDAS) inherits changes in the observing system; satellite records can have
  instrument drift (e.g. OMI row anomaly since 2007; MODIS Terra drift). Cross-check with a second source when possible.
- Regional means hide opposite-sign sub-regional trends — use the trend map.
- Statistical significance ≠ physical importance; magnitude per decade and its CI matter as much as p.

## References
See `09-references.md` (Mann 1945; Kendall 1975; Sen 1968; Gilbert 1987; Yue & Wang 2004;
Hamed & Rao 1998; Santer et al. 2000; Weatherhead et al. 1998; Benjamini & Hochberg 1995; Wilks 2016).
