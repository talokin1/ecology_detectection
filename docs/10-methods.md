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

## Regions: boxes and IPCC AR6 outlines
A region is either a latitude/longitude box or a polygon outline. The 46 IPCC AR6 WGI land reference
regions (Iturbide et al., 2020; ids `ar6_<acronym>`) are outlines. A grid cell belongs to an outline if its
centre is inside (edges are straight lines in longitude/latitude; a centre on a left or bottom edge is
inside, on a right or top edge outside, so neighbouring regions never share a cell). AR6 means use land
cells only. The ice-sheet regions (Greenland/Iceland, East and West Antarctica) are not built because the
land mask excludes ice sheets. Rule and list: `docs/decisions/ADR-005-*.md`, amendment 1.

The web app's four European regions are outlines too, but real borders (Natural Earth 1:10m, Ukrainian
point of view; `data/catalog/regions_countries.yaml`, built by `scripts/make_country_regions.py`): Ukraine
with Crimea (231 MERRA-2 cell centres inside), southern Ukraine as six admin-1 units (52), northern Europe
as seven countries (748; Åland is a separate Natural Earth unit and is not included) and southern Europe as
twelve countries, Kosovo included as part of Serbia in the Ukrainian-POV file (493). Same cell-centre rule, land cells
only. The Sahel stays a box. The map outline drawn for each region is the same polygon the numbers are
averaged over. ADR-005 amendment 2.

## Data-quality checks before any trend (acquisition layer)
Before a regional series is analysed, `backend/trend_detective/acquire.py::assess` checks whether it
can be investigated for a trend at all, and tells the user why not in plain language:

| Check | Rule | Why |
|---|---|---|
| Long enough | >= 10 years and >= 120 months | Shorter records rarely separate a trend from natural variability |
| Seasonal cycle estimable | every calendar month present in >= 5 years | Deseasonalising needs a mean for each calendar month (MODIS NDVI loses snowy winters) |
| Few flat months | < 25% of observations either exactly zero or in calendar months whose year-to-year SD is < 5% of the most variable month's | Near-tied anomalies pull Sen's slope toward zero (Ukraine snow, Sahel dry season; see `docs/planning/2026-11-14-stats-cross-check.md`) |
| No long gaps | no gap > 12 months | Gaps often mark an instrument change. The GRACE → GRACE-FO gap (2017-07 to 2018-05) is **11 months**, so this rule does not flag it; instead every GRACE series states the mission gap in its provenance caveats (tested in `backend/tests/test_grace.py`), and the Pettitt break test (plan v2, S4) is the statistical safeguard (Q6). The threshold is not lowered to catch one known case. |
| Not constant | some variation in at least one calendar month | e.g. snow depth in the Sahel: nothing to measure |

Regional means can be **land only**: region presets with `land_only: true` (the case regions) average only cells where MERRA-2 has land (cells with root-zone soil wetness; ocean, lakes and ice sheets excluded); IMERG and SYN1deg cells use the nearest MERRA-2 cell's flag. This is fixed per region before any trend is computed and recorded in each series' provenance.

**Daily inputs and monthly aggregation (plan v2, S2).** Daily MERRA-2 values come from the POWER daily store (`merra2_daily`). Monthly values from daily: mean of valid days for states (temperature), and for per-day fluxes (precipitation) the mean of valid days times the days in the month; a month counts only if >= 80% of its days are present. Check: daily-to-monthly precipitation equals POWER's own monthly `PRECTOTCORR_SUM` to 0.000 mm in all 549 months (southern Ukraine, Ukraine; measured max |diff| = 8.76×10⁻⁵ mm for Ukraine and 1.21×10⁻⁴ mm for southern Ukraine). **Pitfall:** in the POWER *monthly* store, `T2M_MAX`/`T2M_MIN` are the month's single hottest/coldest hour, not mean daily values (southern Ukraine: 21.3 °C vs 15.1 °C on average). Formulas needing mean daily Tmax/Tmin (Hargreaves PET for SPEI, M3) use `acquire.get_monthly_from_daily(..., how="mean")`.

**Units and display (Q1, Q3).** Cached series keep the source unit; the catalog's `display_units`/`convert`
is the only conversion and is applied once by the JSON builder (e.g. solar W/m² → MJ/m²/day with
`x * 0.0864`). "Tmax" always means the mean daily maximum; the monthly-store value is shown only as
"hottest hour of the month". DTR = mean(Tmax) − mean(Tmin) from the daily inputs.

**GRACE regional mean vs the stats-archive cross-check (Q5).** The app uses `backend/trend_detective/grace.py`,
which averages 0.5° cells whose *centres* fall in the box and keeps only JPL `land_mask` cells; the
stats-archive pipeline weights cells by their *overlap* with the box edge. For Ukraine the two trends
differ by about 4% (−10.79 vs −11.24 cm/decade). The mascon product's real resolution is about 3°
(~300 km), so this difference is within the product's own uncertainty; it is reported here, not tuned away.

Outcome: `ok`, `caution` (analysis runs, the note is shown next to the result), `too_short` or
`no_variation` (no trend is reported). Thresholds set on 2026-11-14 from real series; pending
science-lead review.

## Trend maps (per grid cell)
Same steps per cell; significance stippling uses Benjamini–Hochberg false-discovery-rate control
(q = 0.05) across all cells, because thousands of independent tests at α = 0.05 would flag ~5% of cells
by chance (Wilks, 2016).

In the web app (`scripts/make_app_data.py`) the map uses the 2° monthly grids in `data/cache/grids/`:
one mean per complete calendar year in each square (a year with any missing month leaves the square
blank), Sen's slope and Yue–Wang Mann–Kendall on those yearly means, BH across all squares with data.
Root-zone soil wetness has no value over ocean or the Greenland and Antarctic ice sheets in the
source grid, so those squares stay blank; a square whose yearly means never vary would also be left
blank rather than tested (none does in the 2026-11-14 cache).

Per-cell test: Mann–Kendall with the Yue–Wang AR(1) correction on the 45 yearly means (not the plain
Mann–Kendall), then BH over every square that has data (16,200 squares for T2M and PRECTOTCORR,
fewer for GWETROOT).

## Robustness ("borderline") check in the web app
Pre-declared and identical for every region and variable: the verdict rule is repeated (a) without the
first two years, (b) without the last two years, (c) on yearly means of the anomalies. The headline
verdict is never changed; if any of (a)–(c) gives a different level, the "How sure?" line says
"Borderline" and names the check. Added after the independent `stats-validator` review (2026-11-15)
found that some moderate verdicts depend on the end years and that the AR(1) correction may understate
persistence for the Sahel.

Displayed ranges are rounded outwards (lower bound down, upper bound up) so a printed range is never
narrower than the computed one; JSON files keep the unrounded values.

## Analysis period in the web app
Fixed before any real result was computed: every series starts in January 1981 and ends with the last
calendar year that is complete in **every** input the app uses (grids, regional series). With the
cache frozen on 2026-11-14 that is **1981–2025** (540 months). Whole years keep the yearly bars, the
seasonal tests and the map on the same footing; we never choose the start or end to strengthen a trend.

## Deeper checks (`trend_detective.climate_stats`)
Each investigation page also shows results of the team's offline JSON pipeline (ADR-007), run on the
same cached data: one input document per region with monthly T2M and GWETROOT and, where the cache has
them (the four European regions), daily T2M_MAX, T2M_MIN and PRECTOTCORR; otherwise monthly
PRECTOTCORR. Only **one** precipitation source enters each document, so drought indices are not tested
twice. Methods requested (fixed in advance): trend, monthly profile, seasons, emergence, probability
change, acceleration, variability, block bootstrap (999 replicates, seed 1729), change point, daily
indices, SPI/SPEI (baseline 1981–2010, end month August). The pipeline applies one Benjamini–Hochberg
family to all tests in the region document (q = 0.05). The page lists a fixed set of rows per variable
(chosen by topic, not by result) and labels a row "Clear change" only when the pipeline's conservative
flag holds (both Mann–Kendall and OLS pass after BH). Every row is shown, clear or not. The full output
is published as `frontend/public/data/stats/<region>.json`.

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
