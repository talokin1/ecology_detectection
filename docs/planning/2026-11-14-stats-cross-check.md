# 2026-11-14 — Cross-check of `trend_stats.py` on real regional series

Purpose: independent check before any number reaches the UI (CLAUDE.md working agreement).
`analyze_series` from `.claude/skills/trend-stats/scripts/trend_stats.py` (unchanged) was run on
seven series read with `backend/trend_detective/power_zarr.py`, and compared with a separately
written straight-line fit (trend and seasonal cycle fitted together, lag-1 effective sample size).
The independent code is not in the repo; it was used only for this comparison.
SI-assisted (Claude, Anthropic). Not yet reviewed by the science lead.

Slopes are per decade, in source units. Period: start of each record to 2026-09/10.

| Series (box) | Sen slope [95 % CI] | MK p (Yue-Wang) | OLS slope | OLS p | n_eff / r1 | Verdict level | Independent OLS slope / p |
|---|---|---|---|---|---|---|---|
| MERRA-2 `T2M`, Ukraine (22–40.5°E, 44–52.5°N) | 0.523 [0.383, 0.664] | 3e-12 | 0.530 | 8e-12 | 325 / 0.26 | strong | 0.530 / 8e-12 |
| MERRA-2 `FRSNO`, Ukraine | −4.5e-07 [−7.9e-05, 0] | 0.21 | −0.0082 | 0.13 | 187 / 0.49 | none | −0.0082 / 0.13 |
| MERRA-2 `PRECTOTCORR`, Ukraine | 0.034 [−0.003, 0.070] | 0.069 | 0.038 | 0.041 | 490 / 0.06 | weak | 0.038 / 0.041 |
| IMERG `IMERG_PRECTOT`, Ukraine | 0.054 [−0.020, 0.133] | 0.15 | 0.062 | 0.13 | 330 / 0.02 | none | 0.062 / 0.13 |
| MERRA-2 `PRECTOTCORR`, Sahel (15°W–35°E, 10–18°N) | 0.012 [−0.004, 0.048] | 0.18 | 0.087 | 0.019 | 153 / 0.56 | none | 0.087 / 0.019 |
| MERRA-2 `FRSEAICE`, Arctic cap (70–90°N) | −0.0119 [−0.0168, −0.0073] | 4e-07 | −0.0137 | 2e-07 | 69 / 0.78 | strong | −0.0137 / 2e-07 |
| SYN1deg `CLOUD_AMT`, Ukraine | −1.24 [−2.40, −0.09] | 0.035 | −1.07 | 0.078 | 226 / 0.15 | moderate | −1.07 / 0.078 |

## Findings
1. **OLS agrees.** The reference module's OLS slope and p-value match the independent fit to
   3–4 significant digits on all seven series.
2. **Sen's slope collapses on zero-heavy series.** Ukraine snow-cover fraction: Sen −4.5e-07 per
   decade against OLS −0.0082, and `years_to_detect` came out as 53,139. Sahel rainfall: Sen 0.012
   against OLS 0.087. In both, many months are zero every year (no snow in summer, no rain in the
   dry season), so their anomalies are identical and the median of pairwise slopes sits near zero.
   Since Sen's slope is the headline number (ADR-002), snow, rainfall in dry climates and sea ice
   would show "no change" where the mean is changing. For the science lead to decide; options
   include analysing only the relevant season, annual means, or showing OLS for such variables.
3. **Primary and secondary tests disagree in borderline cases** (Ukraine rainfall: 0.069 vs 0.041;
   Ukraine cloud: 0.035 vs 0.078). Expected, but the verdict card should say what happens then.
4. **Two datasets disagree on the same variable.** Ukraine rainfall is borderline in MERRA-2
   (1981 →) and not significant in IMERG (1998 →). The periods differ, so this is not a like-for-like
   comparison yet.

These numbers are a pipeline check, not validated results. None has been compared with Giovanni
or the literature.
