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
8. **Verdict** (plain language). Each test gives a level, and the reported level is the weaker of the
   two (ADR-003 "conservative verdict"):
   | Level | Mann–Kendall (Yue–Wang) | OLS with n_eff |
   |---|---|---|
   | strong evidence | 99% Sen CI excludes 0 | p < 0.01 |
   | evidence | 95% Sen CI excludes 0 | p < 0.05 |
   | a hint | 90% Sen CI excludes 0 | p < 0.10 |
   | no clear trend yet (+ "≈ N more years needed") | otherwise | otherwise |

   A record shorter than 10 years gives "not enough data". In the web app the headline is further
   capped by three stability checks (see "Robustness" below).

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

### Countries (web app)
The app also offers 152 countries. A country's monthly value is the mean of the 2° map squares it
overlaps, weighted by (area of overlap) x cos(latitude); a month needs data in squares holding at least
half of the country's weight. Outlines come from the committed basemap (Natural Earth 1:10m, Ukrainian
point of view); parts farther than about 1,000 km from the mainland are left out (chain rule), and
countries under 20,000 km² are not offered. Coastal squares include some sea for atmospheric variables.
Rule and reasons: ADR-008.

Cross-check of the country method against the native-resolution series, Ukraine, same whole-year period
(`python scripts/crosscheck_country_grid.py`, run on 2026-11-15):

| Variable | Sen per decade, 2° squares | Sen per decade, native ~50 km | Correlation of the monthly anomalies |
|---|---|---|---|
| Air temperature (°C) | +0.537 [0.380, 0.694] | +0.545 [0.385, 0.703] | 0.9999 |
| Precipitation (mm/day) | +0.019 [-0.020, 0.058] | +0.018 [-0.021, 0.057] | 0.9992 |
| Soil wetness (pp) | +0.06 [-0.87, 0.98] | +0.03 [-0.90, 0.94] | 0.9992 |
| Sunlight (MJ/m²/day, 2001–2025) | +0.169 [0.031, 0.309] | +0.179 [0.040, 0.320] | 0.9994 |

Same verdict in all four cases. Ukraine itself is shown with the native series.

### Variables and their periods (web app)
Fourteen variables are on the map. MERRA-2 variables use 1981–2025; CERES SYN1deg variables (sunlight,
haze) 2001–2025; GPM IMERG rainfall 1998–2025 (TRMM-era and GPM-era satellites, change in 2014); AIRS
air temperature and water vapour 2003–2025. Pages for records shorter than 30 years say so.
- **AIRS (Aqua satellite) is a second, satellite view of MERRA-2's temperature and water vapour.** Not fully
  independent: MERRA-2 assimilates AIRS radiances. AIRS3STM v7.0 "AIRS-only" (infrared
  retrieval for the whole record, so no step when the AMSU microwave instrument degraded). Each month is
  the mean of the ~1:30 am and ~1:30 pm passes where both exist (0.2% of 1° temperature cell-months had
  one pass and were left out), coarsened to 2° like every grid. AIRS has no per-region files: every
  region's series is the area-weighted mean of the 2° squares its outline overlaps (the country method,
  ADR-008), so coastal regions include some sea. The record starts in September 2002; analyses use the
  complete years 2003–2025.
- **AIRS and MERRA-2 disagree on water vapour.** Over 2003–2025 the global trend is about +0.24 °C per
  decade (AIRS) vs +0.20 (MERRA-2) for temperature, but about +0.1 vs +0.5 kg/m² per decade for water
  vapour (quick global check, not yet validated). AIRS retrieves under clear and partly cloudy skies, so
  persistently cloudy, moist air is sampled less. Every AIRS water-vapour page carries this caveat.
- **AIRS temperature over hot deserts.** Yearly anomalies of AIRS and MERRA-2 (2003–2025) correlate at
  0.93–0.94 for Ukraine and Europe but only 0.3–0.8 for Mali, Egypt and the Sahara region, where AIRS
  trends run cooler; every AIRS temperature page carries a desert caveat. Both records show the Sahel
  cooling over 2003–2025 (AIRS −0.36, MERRA-2 −0.25 to −0.36 °C per decade depending on the averaging;
  `stats-validator`, 2026-11-15), so it is not an AIRS artefact, while MERRA-2's 1981–2025 record shows
  slight warming there. When the satellite window and the long record point in opposite directions, the
  card says so (a descriptive caveat; no cause is claimed).
- **Aerosol optical depth of exactly 0 is "no retrieval"**, not clean air: the smallest positive value
  in the grid is 0.0025, and zeros occur under a low sun and over snow or ice (about 14% of
  cell-months, in winter down to 50°N). They are treated as missing. For a high-latitude country a
  winter month can therefore rest on part of the country (at least half of its weight, by rule).
- **CERES cloud amount is not offered.** Its 60°S–60°N mean anomaly is about +1.7 points in 2001–2005,
  near 0 in 2006–2021 and about -1.5 in 2022–2025: two steps in a near-global mean, the signature of
  changes in the observing system. A trend through them would be an artefact. (Checked on the cached
  grid on 2026-11-15; the provider's data-quality summary should be cited before the variable returns.)
- **Snow cover, snow depth and sea ice are map-only.** Their monthly anomalies are identically zero in
  the snow-free months, which pulls the median (Sen) slope to zero and prints a falsely tight range
  (found by `stats-validator` for Ukraine). The map uses yearly means and is not affected. Regional
  answers need a snow-season method first.
- A region/variable pair is left out, never filled, when a month is missing or when fewer than three
  calendar months hold a non-zero value in at least half of the years.
- When several calendar months hardly vary from year to year (`acquire.assess` "flat months"), the
  page's data caveat says that the median slope can be pulled toward zero.
- Extreme-month thresholds use 1981–2010, or the first 20 years of the shorter records.

### Smooth map rendering (web app)
The map is drawn as a smooth field: per-square slopes are interpolated bilinearly between square
centres, the colour runs continuously through the palette, and colour strength follows the share of the
four nearest squares that pass the map-wide test. Land-only fields are clipped to the coastline (after
extending the field by up to two squares so it reaches the coast), sea ice to the sea. This is display
only: tooltips, significance dots, rankings and all statistics use the real 2° squares.

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

Per-cell test: Mann–Kendall with the Yue–Wang AR(1) correction on the yearly means (not the plain
Mann–Kendall), with the tie term in Var(S) exactly as in `trend_stats.mann_kendall`, then BH over
every tested square (16,200 squares for T2M and PRECTOTCORR, fewer for land-only fields). A square is
not tested, and stays blank, when a year is missing, when its yearly means never vary, or when fewer
than 10 of them are non-zero (sea-ice edge, occasional snow).

### Map views: seasons and "compared with the world" (web app, ADR-011)
Each variable has the whole year and four three-month seasons (Dec–Feb, Mar–May, Jun–Aug, Sep–Nov) as
precomputed layers, and eight of the fourteen variables have each of these again as the change compared
with the world. Precipitation (MERRA-2), snow cover, snow depth and sea ice have no such layer: their
world average is not a sound reference; the two AIRS variables have none until their world averages
are reviewed (ADR-011, decision 2; `python scripts/area_stats.py --var precip
--world` shows the MERRA-2 world mean falling only over the oceans).
- **Season:** one value per year, the mean of the three months; December counts towards the following
  year, so the first winter of a record is left out (same convention as the seasonal checks of a
  region). The per-square test and the BH step are unchanged.
- **Compared with the world:** for each year the world average of that year is subtracted from every
  square, and the difference series is tested. The world average is the cos(latitude)-weighted mean of
  every square with a complete record (all squares for global fields, land squares for land-only
  fields). Differences are in the variable's units, not in percent. A negative value means "changing more slowly than the world (or
  the other way)", not "decreasing"; the layer's legend title and caption say so and print the world's
  own trend. Sen's slope of a difference is not exactly the difference of two Sen slopes, so the three
  printed numbers need not add up to the last digit.

## A region compared with the world (`vs_world`, web app, ADR-011)
For every regional analysis the monthly series "region minus world average" is deseasonalised and put
through the full headline rule: weaker of Mann–Kendall (Yue–Wang) and OLS (n_eff), then the most
cautious of the four robustness calculations. The page reports a difference only when that series has
at least "evidence" of a trend; otherwise "not clearly different". Wording never runs ahead of the
tests: "faster"/"more slowly" also needs an established trend of the region or of the world (otherwise
"moving apart"), and ratio-scale variables say "a larger/smaller change" and add both trends as a
percent of their own means, because the order can reverse in percent. Seasonal rows test one value per
year of the difference with Mann–Kendall only, and the four seasons form one BH family (q = 0.05); this
is lighter than the headline rule and the page says so.
For air temperature the world average includes the oceans, which warm more slowly than land, so most
land regions sit above it; the page states this next to the comparison.

## Your own area (web app, ADR-011)
A visitor can mark any longitude/latitude box and get its trend. Rules, fixed in advance:
- the box value is the mean of the 2° squares it overlaps, each weighted by the share of the square
  inside the box times cos(latitude); squares without a complete record are left out, and the panel
  reports the share of the box (by weight) that had data;
- one value per year (whole year, or the season the map shows), then the yearly rule
  `make_app_data.yearly_values_trend`: Sen's slope, ranges from Mann–Kendall with the Yue–Wang
  correction, OLS with the lag-1 effective sample size, verdict = the weaker of the two levels (the
  same thresholds as in the table above); fewer than 10 years gives "not enough data";
- the comparison with the world, or with a second box, tests the year-by-year difference.
It is computed in the browser by a port of `trend_stats.py` (`frontend/src/lib/stats.ts`), which is
compared on every build with reference values written by `python scripts/area_stats.py --fixture`
(21 series, 7 boxes from the NetCDF grids). The yearly grids the browser reads
(`frontend/public/data/series/*.bin`) store, for each square, a float32 mean, a float32 step size
(1/32000 of the square's largest departure from its mean) and int16 counts; the rounding error is half
a step. Any box shown on the site can
be reproduced with `python scripts/area_stats.py --var <id> --box W S E N [--season <s>]`.
This is a quick check: one value per year and no stability checks. Its false-alarm rate depends on how
alike neighbouring years are (`python scripts/area_stats.py --false-alarms`, 1,500 trend-free AR(1)
series per cell, share called "evidence" or "strong"; 5% would be exact):

| φ (year-to-year memory) | 45 years | 25 years | 10 years |
|---|---|---|---|
| 0.0 | 3.7% | 3.2% | 2.7% |
| 0.3 | 6.8% | 7.4% | 6.9% |
| 0.6 | 8.1% | 10.0% | 14.7% |
| 0.8 | 12.2% | 15.3% | 20.1% |

So the yearly rule is conservative without memory and liberal with strong memory (soil wetness, sea
ice). The same per-square test feeds the maps, where the BH step across squares comes on top. The
"near 5%" result in the Monte-Carlo section below is for monthly series of 10 years or more, not for
this yearly rule. And a box drawn around a patch that stood out on the map is not a fair test of that
patch (the choice used the data); the panel says so under every clear-looking result.

## Robustness: the headline is the most cautious of four calculations (web app)
Pre-declared and identical for every region and variable. The verdict rule is computed four times:
on the full record, (a) without the first two years, (b) without the last two years, (c) on yearly
means of the anomalies (fewer, more independent points). **The headline verdict is the weakest of the
four.** The statistics line names every calculation that differs from the full record, and the JSON
keeps the full-record level (`verdict.full_record_level`). So a trend that rests on the end years, or
that vanishes with yearly means because monthly AR(1) understates persistence, is never called strong.
History: the checks were first reported next to an unchanged headline (2026-11-15, first
`stats-validator` review); the second review the same day found headlines such as "strong evidence,
very sure" next to checks saying "no clear trend" (northern Europe cloud cover, China haze, Brazil
satellite rainfall), so the cap became the rule.

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
