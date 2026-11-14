# Preprocessing pipeline v1 review

Date: 14 November 2026, Europe/Kiev  
Reviewer: Critique  
Plan: `team-context/data/pipeline/PREPROCESSING_PLAN.md`  
Code: `team-context/data/pipeline/` (not modified)  
Outputs: `data/tidy/<region>/`, `qc_report.md`, `data/smoke_test_results.json`  
Methods: imported `$UKRAINE_SAMPLES/_staging/trend_methods.py`  
Scratch only under `team-context/team/reviews/`. No full pipeline rerun; checks used tidy outputs, extract CSVs, and the official NetCDF/shapefiles already on disk.

## Verdict: approved with fixes

The pipeline does what the plan asked for a v1: tidy monthly/annual tables, overlap weights where grids exist, unit conversions that match the extract’s own mm columns (max abs 0), Crimea masks that actually differ, independence groups, 2026 partial-year flags, and a smoke test that reproduces the three approved bbox numbers within ±0.005 — with the production GRACE overlap series correctly set aside as informational. `trend_methods.py` is imported, not copied.

Two analysis-ready outputs should not be used as they stand: the AIRS “full” annual trend includes 2025 despite the series’ own “do not use 2025” flag, and GHCN/GSOM windows labelled 1981–2025 have multi-year holes but are still called robust. Everything below is evidence for those and for the asked checks. No blocking unit or smoke-test error.

## Ranked items

### 1. AIRS 2025 is in the annual “full” trend despite “do not use 2025” (should-fix)

`annual_table` only requires 12/12 months; it does not honour `airs_2025_bias_unverified`. AIRS SurfAirTemp ANN years are 2003–2025 (n=23), including 2025 = 10.749 °C. `trends.csv` window `full` is therefore 2003–2025, OLS +0.721 °C/decade, called “robust at 0.05 (HAC and Hamed–Rao)”. The same 2003–2024 series (n=22) is OLS +0.815 °C/decade (HAC p=1.5×10⁻⁵, HR p=6.2×10⁻⁵). The flag legend and AIRS monthly flags still say the 2025 bias collapse is unverified and 2025 must not be used. Drop 2025 from AIRS annual trends until that check is done.

### 2. Station windows named 1981–2025 have holes, but are still called robust (should-fix)

GSOM TAVG_anom ANN is missing 2020, 2021, 2022, 2023 and 2024 (n=40 in a window labelled 1981–2025; slope +0.52 °C/decade, “robust”). Those years have only 9, 9, 7, 7 and 7 months with any contributing station (`n_valid` min = 1 in 2020–2023). GHCN TAVG_anom ANN is missing 2007–2009 (n=42; Jul–Sep 2007, Jun/Aug 2008, May/Jun 2009 are NaN). The planned ≥10-month deseasonalised alternative was not built (documented); it would have recovered GHCN 2008–2009 (10 months) but not GSOM 2020–2024 (7–9 months) or GHCN 2007 (9 months). Do not present these as complete 1981–2025 detections; label the missing years or restrict the station window to 1981–2019 (already computed).

### 3. Station 1991–2020 baseline with ≥15 years and no fallback drops early-ending stations (documented, note the collapse)

The rule is per station and calendar month: a month enters the regional anomaly only if that station has ≥15 years in 1991–2020 for that month; no record-mean fallback (v1 cut). Stations that end before 2006 cannot meet ≥15 years: 1991–2004 is 14 years. On the bbox GSOM TAVG table, 49 of 183 stations with any TAVG end before 2006 (46 of them in 2004) and are excluded. Only 36 GSOM TAVG stations have at least one month with a 15-year baseline; only 9 have all 12 months. GHCN TAVG: 27 stations with data, 25 with a full 12-month baseline, 0 ending before 2006 (two dropped stations both end 2009). This is OK as a labelled v1 cut, but it thins the historical network and cannot be “fixed” later without a fallback. The 2020–2024 GSOM collapse is real in the tidy series (some months down to 1 station; 2025 again has 12 months, n_valid min=4).

### 4. Smoke test: POWER/HadCRUT come from tidy outputs; blocking GRACE does not. The −11.242 vs −11.222 difference is expected and fine.

POWER T2M and HadCRUT slopes are recomputed with imported `trend_stats` on `data/tidy/ukraine_bbox/annual_seasonal.parquet` (ANN, 1981–2025, n=45): +0.552593 and +0.579280 °C/decade, within ±0.005 of +0.553 and +0.579. They do not read the old analysis CSVs for the slope. The blocking GRACE check re-invokes `load_grace(..., weights="centre")` and takes `time_center` from `$UKRAINE_SAMPLES/grace/ukraine_tws_monthly.csv`; it is not a test of the production tidy series. Production `grace.parquet` (fractional-overlap weights, 15 mascons, 560 land cells, n=235) is informational: −11.24197 vs the approved −11.22209 cm/decade (diff −0.020, 0.18%), which fails ±0.005 and is correctly marked `blocking=False` / pass False. The difference is the expected effect of adding partial edge cells (44.0–44.5°N row, 40.0–40.5°E column, 22.0–22.5°E at weight 0.8) and is far smaller than the previously reported inter-mascon spread. It is fine to adopt −11.24 as the overlap-weighted bbox number. `trend_methods` is imported from `_staging` in both `ukpipe/trends.py` and `smoke_test.py`; there is no copy under `pipeline/`. Pettitt is a separate exploratory function and is labelled anti-conservative.

### 5. Unit conversions in `variables.yaml` are applied correctly

Independent checks against extract columns, all max abs = 0 unless noted: IMERG `precipitation` (mm/hr) × 24 × days_in_month matches `precip_mm` and the tidy series (mean 57.65 mm/month). MERRA-2 PRECTOTCORR and GLDAS 2.0/2.1 Qs_acc / Qsb_acc / Evap_tavg match the extract `*_mm` columns (Qs is ×8 × days). CRU-CY `pet` is officially mm/day; tidy = pet × days (mean 65.59 mm/month). GPCC and CHIRPS are already mm/month (conversion none); 1981–2025 ANN means are GPCC 586.39, CHIRPS 686.69, POWER PRECTOTCORR 588.02, MERRA-2 589.29 mm/year. MODIS scale factors are already applied in the extract (LST in K, then K_to_C → °C; NDVI 0.078–0.728, EVI 0.054–0.497); every MODIS row is flagged `no_qc;terra_only;lst_clear_sky_winter_bias`. GHCN tenths are converted in the loader; `_station_regional` then sets `conversion: none` (no double scale). QFLAG filter removed 4,022 values; PRCP uses ≥27 days or a full month, T ≥20 days.

### 6. Cell-centre cutting of POWER / CHIRPS / CCI extracts is documented; bias on POWER T2M is not material

POWER 0.5° centres run 44.5–52.0°N, 22.5–40.0°E, so cell edges are 44.25–52.25°N, 22.25–40.25°E. The bbox strips 52.25–52.4°N and 22.10–22.25°E are missing. `coverage_frac` is 1.0 on all 464 cells because the missing strips are not in the weight grid (`n_effective_cells` = 452.47). Versus the upstream centre-in-box annual T2M: max |d| = 0.024 °C, mean d = +0.008 °C, OLS +0.552593 vs +0.552706 °C/decade — not material. CHIRPS 0.05° extract edges coincide with the bbox (centres 44.425–52.375°N, 22.125–40.175°E); tidy vs the extra cut-out CSV, max abs = 1.9×10⁻⁵ mm over 550 months (1981–2025 ANN mean 686.69 mm in both). CCI 0.25° centres 44.375–52.375°N, 22.125–40.125°E (edges 44.25–52.5°N, 22.0–40.25°E) actually include the southern cell whose centre is just outside 44.4°N; coverage_frac min/median = 0.181 / 0.771 (winter missing, as flagged). Pre-aggregated GES DISC / MODIS / OMI / GPCC / SWOT extracts are bbox-only and are skipped for the masks (flagged when passed through).

### 7. Verified as requested (nits one line each)

Crimea polygons differ: Natural Earth 5.1.1 Ukraine-POV UKR is 597,211 km² (bounds [22.133, 44.381, 40.16, 52.369]); default de-facto UKR is 570,178 km² (lat min 45.214); difference 27,033 km², bounds [32.482, 44.381, 36.638, 46.218]. Simferopol, Sevastopol and Kerch are in the POV polygon and in default RUS, not default UKR; Kyiv / Donetsk / Luhansk are UKR in both. Mask vs no-Crimea series are not identical (POWER T2M max |d| = 0.552 °C, mean |d| = 0.166 °C; CHIRPS precip max |d| = 4.30 mm/month; n_eff 235.33 vs 225.38). DJF year is the Jan/Feb year (Dec 2020 + Jan/Feb 2021 = DJF 2021, exact). 2026 monthly rows are flagged `partial_year` (GSOM’s NaN March 2026 is the only unflagged 2026 row); there are no 2026 ANN rows; trends are cut at `LAST_FULL_YEAR=2025`. `coverage_frac` and `n_effective_cells` are written (HadCRUT n_eff median 5.79 of 15 overlapping 5° cells). Independence groups are present on every tidy row (0 empty of 40,788); CHIRPS is tagged “uses GTS/GHCN/GPCC normals + ERA5 fill”; trend notes say “same independence_group = not independent confirmation.” Annual = 12/12 only, as the Worker stated. `lst_clear_sky_winter_bias` is also attached to NDVI/EVI (nit). The qc_report smoke table rounds slopes to 0.553 / −11.2 with `.3g`, but the diff and pass columns are honest and the JSON keeps full precision.

## What I could not verify

- I did not rerun `run_pipeline.py`. Conversion checks used tidy outputs plus the extract CSVs; GRACE production vs centre comparison used the existing smoke JSON and tidy `grace.parquet`.
- I did not re-derive the GRACE −11.222 centre-weighted slope from the global NetCDF (the smoke path already matches the approved number to 1×10⁻⁷).
- Why GHCN TAVG is entirely missing in a few 2007–2009 months (QFLAG vs day-count vs source gap) was not traced into the daily station files.
- XTrackQualityFlags for OMI and the AIRS 2025 monthly bias itself were not re-investigated (flagged, as required).

## v1.1 re-review

Date: 14 November 2026, Europe/Kiev  
Target: `team-context/data/pipeline` v1.1 (qc_report generated 12:23 Europe/Kiev; smoke JSON 12:23; README/smoke_test.py updated the same minute for the GRACE production switch).  
Methods: imported `$UKRAINE_SAMPLES/_staging/trend_methods.py`. No pipeline rerun. Scratch: `team-context/team/reviews/pipeline_v11_rereview_checks.py` and `.json`.  
Smoke and docs were re-read after Worker switched the blocking GRACE check to the overlap-weighted production series.

### Verdict: approved with fixes

All six v1.0 should-fixes and the three nits are in the files and in `trends.csv`. The GSOM dropped-station count of 147 is correct. AIRS 2003–2024 from the production tidy annual series is +0.819435 °C/decade (old extract +0.815362). The new blocking GRACE smoke check reproduces −11.24197 vs −11.242 (n=235, diff +3.3×10⁻⁵). Global-file cuts match the old extracts at corr ≥ 0.9983; units are consistent; the production path does not mix the two CHIRPS archives.

One should-fix remains: `trends.csv` still does not report the production GRACE method that the smoke test now treats as the standard.

### Ranked items

### 1. GRACE production series is correct; `trends.csv` headline is not that series (should-fix)

The updated smoke test is as Worker described. Blocking check = production tidy series (`grace.parquet`, overlap weights, 15 mascons / 560 land cells) with the approved method from `grace_findings.py` (climatology from 12/12 years, drop 2002/2017/2018/2026, time = decimal year of `time_center`). Independent recompute: n=235, OLS −11.24196686 cm/decade, HAC p=1.2×10⁻³⁶, HR p=9.1×10⁻¹², vs reference −11.242 (diff +0.000033, well inside ±0.005). Legacy cell-centre check is non-blocking and still matches −11.222087. README, qc_report and `smoke_test.py` all state this switch (attributed to the team lead via Thinker, 14 Nov 2026). POWER +0.552593 and HadCRUT +0.579280 still pass.

`trends.csv` does not publish that number. On `ukraine_bbox` the headline row is the generic 12/12 annual series: −11.993 cm/decade, n=14, 2004–2025, `missing_years` 2011–2018, labelled “robust” under `window=full` (not `_gappy`). The monthly-deseasonalised row is −10.861, n=252 (keeps 2002/2017/2018/2025, uses month-start decimal years and a record-mean climatology, not `time_center` / complete-year climatology). The same split appears on the masks (annual headlines −12.785 / −13.024; monthly −11.747 / −11.987). Anyone quoting `trends.csv` will not get the −11.24 production figure the smoke test now guards. Add a labelled GRACE headline (or a dedicated window) that uses the approved method, or clearly mark the annual 12/12 row as a different convention.

### 2. v1.0 fixes — all verified in the actual files

1. **AIRS excludes 2025 from trends.** `trends.csv` full window is 2003–2024, n=22, `excluded_years=2025`, slope +0.819435 °C/decade (HAC p=7.9×10⁻⁷, HR p=1.3×10⁻⁴, robust). All 12 monthly 2025 rows carry `airs_2025_bias_unverified`. Independent recompute from tidy annual 2003–2024 matches that slope to 1×10⁻¹⁴; the old extract (`SurfAirTemp_C`) is +0.815362, matching Worker’s +0.815 / +0.819 and the verification table (+0.8194 vs +0.8154). 2025 is still present as a 12/12 year in `annual_seasonal.parquet` (nit below).
2. **Station headline is 1981–2019.** All eight GSOM/GHCN headlines use `1981-2019_station_window`. Windows with holes are `*_gappy`, carry `n` and `missing_years` (GSOM TAVG 2020–2024, n=40; GHCN TAVG 2007–2009, n=42), and are explicitly “not treated as robust”. GHCN TAVG’s headline still lacks 2007–2009 (n=36 of 39); that is noted in `robust_call` and in the deviations section — acceptable if quotes use n=36, not a complete 1981–2019 record.
3. **Station baseline is documented as a v1 limitation** in README, qc_report (“Station baseline coverage”) and the deviations list, with the computed counts (see item 5).
4. **GRACE overlap-weight production check** — see item 1. Present and independently reproduced.
5. **`coverage_frac` is honest.** POWER T2M on the bbox is a constant 0.978 (n_eff=452.47), not 1.0; CHIRPS bbox 0.948 (sea fill); GLDAS bbox ~0.895–0.898 (land-only grid); GPCC bbox 0.975. On `ukraine_mask` (primary) CHIRPS/IMERG/MERRA-2 are 1.0, POWER 0.999, GLDAS 0.987, GPCC/AIRS ~1.0.
6. **`ukraine_mask` is stated as the primary Crimea mask** in README, the Crimea section, and the flag legend (POV file, 597,211 km², Crimea included; `ukraine_mask_no_crimea` is a sensitivity variant).

v1 nits are also fixed: `lst_clear_sky_winter_bias` is only on LST_Day/LST_Night (NDVI/EVI have `no_qc;terra_only` only); the smoke table prints four decimals (+0.5530, +0.5790, −11.2420, −11.2220); GSOM TAVG March 2026 is NaN and flagged `partial_year;missing_value`.

### 3. GSOM TAVG dropped count: 147 is correct

Recomputed from `data/tidy/ukraine_bbox/stations_gsom.parquet` with the pipeline rule (≥15 years in 1991–2020, per station and calendar month, no fallback):

- 183 stations with any TAVG
- 36 with ≥1 baseline month
- 9 with a full 12-month baseline
- **147 dropped entirely** (183−36)
- 49 end before 2006 — all of them by 2004 (none end in 2005); none of those 49 has a baseline month. Worker is right that 49 ≠ 147: the other 98 dropped stations run into 2006 or later but still lack 15 years in 1991–2020 for any calendar month.

The same counts are in README and the qc_report table.

### 4. Global-file cuts vs old extracts

`verify_global_vs_bbox.csv`: 28 variables, all corr ≥ 0.9983 (minimum: GPCC precip 0.99825). Every `trend_new` was recomputed from tidy 12/12 annual values and matches the table to machine precision. Units are consistent with the planned conversions (IMERG and MERRA-2/GLDAS flux means are clearly mm/month, not mm/hr or kg m⁻² s⁻¹; GLDAS Qs/Qsb means are in the mm/month range expected from ×8×days; GPCC is mm/month). Overlap weights use spherical cell area R² Δλ (sin φn − sin φs), i.e. the exact integral of cos(lat), times the fractional overlap; confirmed in `ukpipe/regions.py`.

Material-looking slope gaps under a naïve “>5% of the old slope” rule, and whether they matter:

- **MERRA-2 PRECTOT** +0.687 vs +0.376 mm/year/decade (rel 82%). Both are indistinguishable from zero (new HAC p=0.96, HR p=0.70; neither robust). The absolute gap is 0.31 mm/year/decade, 0.046% of the ~676 mm/year mean — an edge-cell overlap effect on a near-zero slope, not a unit error or a label change.
- **AIRS TotH2OVap** +0.147 vs +0.161 (rel 9.1%). HAC p flips from 0.046 (old extract) to 0.068 (global); HR p is 0.071 on both, so the robust call stays “not significant”. Documented method difference (per-cell nanmean(A,D) then weights, vs mean of A and D bbox means).
- **CHIRPS precip** +1.832 vs +1.718 (rel 6.6%). Both not significant (HAC p≈0.86/0.87, HR p=0.69). The monthly series agree to <5×10⁻⁵ mm through 2025-09; all differences >0.33 mm start in 2025-10 (max 15.07 mm in 2026-02). Oct–Dec 2025 alone move the 2025 annual total by +3.94 mm and therefore the 1981–2025 slope. This is the two-archive tail, not a weighting bug.

No other variable is near a 5% slope gap or a robustness flip. IMERG is an exact match (cell edges coincide with the bbox).

**CHIRPS archives are not mixed in production.** All three regions load `$GLOBAL_DATA/chirps_v3/chirps-v3.0.monthly.nc` (`path=global_grid_overlap_weights`), 549 months, 1981-01..2026-09. The bbox COG extract (ends 2026-10, differs from 2025-10) is only the fallback if that global file is missing (`dispatch.py`). The verification table compares the two; tidy output is global-only. Keep it that way — do not splice the COG tail onto the global series.

**MODIS is still `no_qc`.** The slim global files contain only NDVI/EVI (MOD13C2) and LST_Day/LST_Night (MOD11C3); there are no QA layers to read. The flag is honest and matches the global-fetch review.

**GPCC `gauge` (and `gauge_int`) are in the global v2025 files but are not loaded** — only `precip` is read. Not blocking for v1; a weighted or flagged gauge-density series would help the early (1891+) record.

**GLDAS Rainf was not fetched** and is not in `variables.yaml`. Evap, Qs and Qsb are present; a GLDAS P–ET residual still cannot be built. Already a planned v1 cut.

**Land mask.** Every gridded global loader uses the same region polygon and overlap weights. Residual coverage gaps are product-inherent (GLDAS land-only coastal cells; CHIRPS sea fill on the bbox; MERRA-2/IMERG have data over sea, so bbox coverage=1). On the primary `ukraine_mask` those differences shrink to a few percent at most (GLDAS 0.987). Do not treat a bbox MERRA-2 (land+sea) mean as the same domain as bbox CHIRPS or GLDAS.

**Regions in `tidy/`:** only `ukraine_bbox`, `ukraine_mask`, and `ukraine_mask_no_crimea`. No other countries. Trend tables are sane (153 / 187 / 187 rows, no null slopes, n_min=14, AIRS full ends in 2024 on all three). Mask vs bbox shifts are small and in the expected direction (POWER T2M 1981–2025 +0.553 bbox / +0.556 mask / +0.556 no-Crimea). GRACE is more sensitive to the polygon, as expected.

### Nits (one line each)

- AIRS 2025 remains a 12/12 year in `annual_seasonal.parquet`; anyone computing a “full” slope from that file will re-introduce the year `trends.csv` correctly drops — drop or flag it there too.
- GPCC global `gauge`/`gauge_int` are unused (item 4).
- GHCN TAVG headline 1981–2019 is still missing 2007–2009 (n=36); already footnoted, do not quote it as a complete 39-year window.
- GRACE’s annual `full` window lists `missing_years` 2011–2018 but is not labelled `_gappy`, unlike the station convention.
- GLDAS Rainf is absent, so no GLDAS P–ET (already a v1 cut).
- MODIS QC is absent from the slim global granules; `no_qc` is the right flag, not a regression.

### What I could not verify

- I did not rerun `run_pipeline.py` or `smoke_test.py` (the latter would rewrite `qc_report.md`). GRACE −11.24197 was recomputed from the existing tidy series plus `time_center` from the Researcher CSV.
- I did not re-derive the legacy −11.222 centre-weighted slope from the global NetCDF; the smoke JSON still matches the approved number to 1×10⁻⁷, and the loader path was not changed except for which check is blocking.
- Whether the team lead's GRACE decision is correctly attributed is taken from Worker’s docs, not independently checked with the team lead.

## v1.2 review

Date: 14 November 2026, Europe/Kiev  
Reviewer: Critique  
Scope: MODIS per-pixel QC, GLDAS 2.0/2.1 rain/snow split, MERRA-2 T2MMAX/T2MMIN/DTR and winds, GPCC/CHIRPS final numbers, smoke test, multiple-testing family.  
Methods: imported `$UKRAINE_SAMPLES/_staging/trend_methods.py`. Scratch only under `team-context/team/reviews/`. No full pipeline rerun; spot-checks used tidy outputs, the series cache, official NetCDF attributes, and a Ukraine-window decode of three MODIS months (Jan 2003, Jul 2003, Jan 2010). Commands run with `nice -n 19`, `OMP_NUM_THREADS=1`.

### Verdict: approved with fixes

The v1.2 additions do what Worker claimed. MODIS QC bit positions match the C6.1 CMG user guides / file legends, QC is applied per pixel before the area mean, the surviving fraction is overlap × spherical-area weighted, and the published QC-impact table recomputes exactly from the `ukraine_mask` cache. MERRA-2 T2MMAX/T2MMIN are M2SMNXSLV monthly means of daily max/min (K→°C), DTR is their difference, and the two headline trends recompute: **+0.6358 and +0.5784 °C/decade**, both robust. Winds are flagged as speed-of-the-monthly-mean. GLDAS `Rainf_f_tavg` is “Total precipitation rate” (rain+snow); units are `kg m-2 s-1 × 86400 × days` with max abs 0 against tidy. 2.0 and 2.1 are not spliced. Smoke still PASSes at the exact values (POWER **+0.552593**, HadCRUT **+0.579280**, GRACE production **−11.241967** cm/decade, n=235). New variables are in the multiple-testing family (annual family 157 on `ukraine_mask`, 131 without the new rows would have been 126 / 100).

One analysis-ready output should not be used as it stands: **do not headline GLDAS-2.1 snowfall −22.7 mm/year/decade as a Ukraine climate result.** It is unconfirmed by GLDAS-2.0 on the overlap, there is no MERRA-2 PRECSNO or station snow to check it against, and the 2000–2025 window includes the GLDAS-2.1 forcing breaks. The slope is also **per decade**, not “mm/yr”.

### Ranked items

### 1. GLDAS-2.1 snowfall is statistically “robust” on the full window, but must not be a headline (should-fix)

`trends.csv` (`ukraine_mask`, annual 12/12, 2000–2025, n=26) is **−22.696 mm/year/decade**, HAC p=0.014, HR p=0.028, `headline=True`, called “robust at 0.05 (HAC and Hamed–Rao)”. The number is correctly computed. The claim is not.

- Units: the column is `lin_slope_per_decade` with unit `mm/year`. Mean annual snowfall is 115.5 mm/year, so this is about −20% per decade, not −22.7 mm per year.
- GLDAS-2.0, same mask, 1948–2014: **−1.57 mm/year/decade, not significant**. Over the 2000–2014 overlap the two products do not agree: annual means **77.9 vs 130.6 mm/year**, monthly corr 0.96 but 2.1 is wetter by 4.4 mm/month; overlap slopes **+14.6 vs −0.9**, both n.s. on a 15-year short record.
- The 2000–2025 “detection” is fragile and sits on known 2.1 forcing breaks (Mar 2001; AGRMET after 2011; GALWEM from Jun 2025). Dropping 2000 and 2025 (2025 is the lowest year, 39.3 mm) gives 2002–2024 **−16.0, n.s.** 2001–2010 is essentially zero; 2011–2025 is −38, also n.s.
- No independent check is possible in this pipeline: MERRA-2 `flx_slim` has only PRECTOT/PRECTOTCORR (no PRECSNO); there is no station snow series. 2.0 and 2.1 are correctly kept as separate sources (no splice).
- In the same 157-test annual family the snowfall HAC p fails Bonferroni and only passes BH. `robust_call` does not use that correction (pre-existing), but it is a further reason not to pitch this as a clear detection.

Treat 2.1 snowfall (and the matching 2.1 SWE decline) as a **forcing diagnostic**, not a climate headline, unless a non-GLDAS-2.1 source confirms it. File attributes confirm the variable semantics Worker used: `Rainf_f_tavg` long_name = “Total precipitation rate”, `Snowf_tavg` = “Snow precipitation rate”. Liquid rain as `clip(Rainf_f − Snowf)` per cell is the right construction; official `Rainf_tavg` was not fetched.

### 2. Growing-season / JJA VI is recommended but not an official tested series (should-fix)

QC impact and flags are right: on `ukraine_mask`, VI QC removes **31.8% of DJF area** (kept-area fraction 0.683 in DJF vs 0.999 in JJA), annual NDVI goes **+0.00474 → +0.00214** (n.s. both), annual EVI **+0.00606 → +0.00518** and flips from robust to “HAC significant; Hamed–Rao anti-conservative; not treated as robust”. LST trends move by **≤0.001 °C/decade**. Those published numbers recompute exactly. `no_qc` is gone from production; every MODIS month is `qc_pixel_masked`. The winter-sampling flag and the clear-sky LST flag are applied only where they belong.

What is missing: `trends.csv` still has only `annual_ANN_12of12` (and monthly deseasonalised) for NDVI/EVI. JJA and Apr–Sep are not official rows and are not in the test family. `annual_seasonal.parquet` does have DJF/MAM/JJA/SON, and those series do not all say the same thing, so “use JJA/growing-season VI” cannot be left as a note:

- JJA EVI 2001–2025: **+0.01142, robust** (just; HAC p=0.032, HR p=0.047). Including 2000: +0.01309, still robust.
- Apr–Sep EVI 2000–2025 (6/6 months, not a pipeline period): **+0.00730**, HAC significant but HR anti-conservative — **not treated as robust**.
- JJA NDVI 2001–2025: **−0.00060, n.s.** Apr–Sep NDVI: −0.00313, n.s.

Add official JJA (and, if you mean it, Apr–Sep) rows to `trends.csv`, put them in the family, and do not treat JJA and “growing season” as interchangeable. Until then, do not use the annual VI headlines for vegetation-change claims. A related gap: 22 Jan/Feb months with `coverage_frac < 0.5` (min 0.093) are flagged `qc_low_coverage_lt50pct` but still enter the 12/12 annual mean in 15 of the 17 years that have one. The 50% threshold is sensible as a warning; keeping those months in the annual headline is why the winter-sampling effect is still in the official NDVI/EVI rows.

### 3. MODIS bit decoding, order of operations, and remaining LST clear-sky bias — verified

Against the C6.1 guides and the bits stored in the QC files:

- MOD13C2: `pixel_reliability` 0 good / 1 marginal kept; −1 fill, 2 snow/ice, 3 cloudy, **4 estimated** dropped. `VI_Quality` bits 0–1 (MODLAND) kept only for 00/01. The file legend matches. The two tests are ANDed. Spot pixels in Jan 2003, Jul 2003 and Jan 2010 behave as coded (e.g. Jan 2003 snow rel=2, bits 01, NDVI raw −108, dropped; estimated rel=4 dropped even when MODLAND is 01; July good rel=0, bits 00, NDVI 0.66, kept). Reliability 4 is present in the Ukraine window (3,310 pixels in Jan 2003; 12,284 in Jan 2010).
- MOD11C3: `QC_Day` / `QC_Night` bits 0–1 mandatory QA, bits 6–7 average LST error (00 ≤1 K, 01 ≤2 K) — confirmed by the LAADS C6.1 filespec. Keep mand=00, or mand=01 with error ≤2 K; drop 10/11 and mand=01 with error >2 K. Spot pixels match (e.g. Jul 2003 day mand=01 err=10, 301.48 K, dropped). The NetCDF `_FillValue` on QC is 0, which is also a valid “good” QC word; auto-mask is correctly disabled, and every QC=0 pixel in the window is kept.
- QC is applied to the array before `grid_aggregate`. `__qc_kept_area_frac` uses overlap × area weights. On `ukraine_mask` the 50% flag on `coverage_frac` (valid area / region area) agrees with `kept_area_frac` (22 months both ways).
- LST QC removes <0.3% of area because the CMG is already a clear-sky monthly composite. The winter bias remains and is honestly flagged: mean `LST_Day_clear_days` is 8.0 in December vs 22.8 in August. No clear-sky-days threshold is applied (documented). Do not treat the robust LST_Day/Night +0.89 / +0.86 °C/decade headlines as all-sky air-temperature trends.

### 4. MERRA-2 T2MMAX / T2MMIN / DTR / winds — verified

Collection is M2SMNXSLV (`statM_2d_slv_Nx`), LongName “Daily, Aggregated Statistics … Monthly Mean”. T2MMAX/T2MMIN are in K and converted K→°C. DTR is derived per cell as T2MMAX−T2MMIN (equal to the monthly mean of daily DTR) and left unconverted, unit °C; regional identity holds to 2×10⁻¹³. July 1980 bbox: T2MMAX 24.14, T2MMIN 14.46, T2M 19.57 °C, as documented. Headlines on `ukraine_mask` 1980–2025 (n=46) recompute to machine precision: T2MMAX **+0.6358**, T2MMIN **+0.5784**, both robust and Bonferroni-significant in the 157-test family; DTR **+0.057**, n.s. `WS10M_from_mean_UV` is √(U²+V²) of the monthly-mean components, flagged `speed_of_monthly_mean_wind_underestimates_mean_speed`; mask mean 1.63 m/s vs POWER WS10M 4.34 m/s. It is ≥ the hypot of the regional-mean U,V in every month, as it must be. Do not compare it to a mean-speed series.

### 5. Smoke test, and the GPCC / CHIRPS “586.39 / 686.69” check

Recomputed from current tidy + imported `trend_methods` / `grace_headline_trend`, all within ±0.005 of the blocking references: POWER T2M 1981–2025 **+0.552593**, HadCRUT5 **+0.579280**, GRACE production overlap **−11.241967** (n=235). The smoke JSON (`run_at` 14 Nov 2026, 13:00:56 Europe/Kiev) matches.

CHIRPS production is the global v3.0 file only, **549 months, 1981-01..2026-09**. The old bbox extract 1981–2025 ANN mean is **686.69 mm/year**; the production overlap-weighted tidy mean is **686.78** (monthly corr 0.9997; 1981–2025 max abs 2.0 mm). GPCC old centre-cut extract is **586.39**; production tidy is **585.35** (corr 0.9983, mean diff −0.087 mm/month over 1981–2025, max abs 5.3 mm). Those gaps are the already-documented overlap-vs-centre effect in `verify_global_vs_bbox.csv`, not a unit or date-alignment error. Quote the production numbers (585.35 / 686.78), not the old extract means. I could not find a written description of the mid-run GPCC/CHIRPS loader bug; the final series are consistent with a clean overlap-weighted cut.

### 6. Multiple testing: new variables are in the family

`add_multiple_testing` is still applied to all annual 12/12 rows with a finite p-value, all windows together (pre-existing). On `ukraine_mask` that family is **157** (31 of them are the new variables: T2MMAX/T2MMIN/DTR, U/V/WS, 2.0+2.1 precip_total/snowfall/rainfall_liquid, LST clear-day counts, each with the windows that exist). Monthly family is 74. T2MMAX/T2MMIN survive Bonferroni; GLDAS-2.1 snowfall and LST_Day do not, but still pass BH. `robust_call` remains a raw 0.05 rule.

### Nits (one line each)

- Wording in the Worker note (“snowfall −22.7 mm/yr”) is wrong; write **mm/year/decade**.
- `precip_total − rainfall_liquid − snowfall` is not identically zero (max abs 0.29 mm/month) because liquid is clipped per cell and Snowf has a slightly smaller valid mask (1,281 vs 1,288 cells in Jan 2000).
- `LST_Night_clear_days` +0.43 days/decade is called robust and is a headline; treat it as a sampling series, not a climate finding.
- Official GLDAS `Rainf_tavg` (liquid-only) was not fetched; the derived difference is fine if the mask/clip residual is documented.
- Apr–Sep is not a pipeline period, only DJF/MAM/JJA/SON; if “growing season” is the recommendation, add it.
- AIRS 2025 still sits as a 12/12 year in `annual_seasonal.parquet` (open v1.1 nit).

### What I could not verify

- I did not rerun `run_pipeline.py`, `compare_modis_qc.py`, or `smoke_test.py` (the last would rewrite `qc_report.md`). Trends and the QC-impact table were recomputed from tidy outputs and the series cache.
- The mid-run GPCC/CHIRPS loader bug itself is not described in the code or report; only the final series were checked.
- GALWEM’s exact contribution to the 2025 snowfall annual total (the year is 12/12 and is the record low).

## v1.3 re-review

Date: 14 November 2026, Europe/Kiev  
Reviewer: Critique  
Scope: confirm the v1.2 fixes in `trends.csv` / `qc_report.md` / `README.md`; recompute Bonferroni and BH; check headlines against the MT flags and GRACE region labels.  
Methods: imported `$UKRAINE_SAMPLES/_staging/trend_methods.py`. Scratch only under `team-context/team/reviews/`. No full pipeline rerun. Spot-checks used tidy outputs and `statsmodels.stats.multitest` (plus a manual BH step-up). Commands run with `nice -n 19`, `OMP_NUM_THREADS=1`.

### Verdict: approved, with nits

Every v1.2 fix is in the files and does what was claimed. GLDAS-2.1 snowfall and SWE are `role=forcing_diagnostic`, `headline=False`, with the reasons in `robust_call` and the report. `slope_unit` is `mm/yr per decade` on annual precip-type slopes (snowfall full, mask, −22.696). Official JJA and Apr–Sep (AMJJAS 6/6) QC'd NDVI/EVI rows are in `trends.csv` and the annual family, both reported, with the season-sensitivity note; annual VI is `annual_includes_low_coverage_winter_months` and not a headline (19 low-coverage Jan/Feb months in the 2001–2025 window, 22 over the mask record). The GPCC/CHIRPS 585.35 / 686.78 production means are in README and the report and recompute (585.3496 / 686.7771). The GLDAS residual and derived liquid rain are documented. `clear_days` is `sampling_diagnostic`, not a headline. Smoke still PASSes (POWER +0.552593, HadCRUT +0.579280, GRACE bbox −11.241967). Family sizes are **161 / 135 annual** (mask / bbox) and **74 / 66 monthly**.

ukraine_mask JJA EVI is **+0.01142**, robust at the raw 0.05 rule (HAC p=0.0325, HR p=0.0471) but `mt_bonferroni_pass` and `mt_bh_pass` are both False. Apr–Sep EVI is **+0.00706**, not treated as robust (HR anti-conservative). Both recompute exactly.

### Ranked items

### 1. Bonferroni / BH columns recompute correctly; the pass flag is an AND, not a single max-p test (verified)

`add_multiple_testing` is applied separately to annual HAC lag-1, annual Hamed–Rao, and monthly HAC lag-3. I recomputed all three from the p-values in `trends.csv` with `multipletests(..., method="bonferroni"|"fdr_bh")` and a manual BH step-up: family sizes, alphas (0.05/161, 0.05/135, 0.05/74, 0.05/66), adjusted p, q-values and reject flags match to machine precision (BH q differs by at most 2×10⁻¹⁶ from a hand BH).

`mt_bonferroni_pass` / `mt_bh_pass` are **not** “Bonferroni/BH of max(HAC, HR)” as a single test. They are:

- annual: **both** HAC lag-1 and Hamed–Rao must survive the correction (`AND` of the two reject flags);
- monthly: **HAC lag-3 only** (Hamed–Rao is not put through `add_multiple_testing` on monthly rows).

For Bonferroni, AND of the two tests is exactly Bonferroni on max(HAC, HR) — confirmed, 64 annual rows on the mask. For BH, AND is not in general the same as BH on the max; it agreed on the mask and on every headline row, and disagreed on one bbox sampling row (`LST_Night_clear_days`, not a headline). The monthly HAC-only rule is documented in the headline-table caption; the GRACE headline would also pass a Hamed–Rao Bonferroni (mask p=6.6×10⁻¹², family 74). `robust_call` itself is still the raw 0.05 rule, as documented.

The family definition (all annual windows plus the new seasonal VI rows, all roles, including diagnostics) is conservative and documented. Dependent windows of the same series inflate n; that is a choice, not an error. 157 (v1.2 annual) + 4 seasonal VI rows = 161.

### 2. Headline Bonferroni survivors, and two robust headlines that fail both corrections

On `ukraine_mask`, 26 headline rows pass Bonferroni. They are the air- and land-surface temperature series (POWER/MERRA-2 T2M, T2MMAX/T2MMIN, AIRS, HadCRUT, GISTEMP, Berkeley, CRU tmp/tmn/tmx, GHCN/GSOM TAVG/TMAX/TMIN, GLDAS Tair, MODIS LST_Night), **CRU vapour pressure**, and **GRACE −12.12 cm/decade**. Worker’s “all the temperature series plus GRACE” is right as a description of the set, with the vap addition. LST_Day and CRU DTR are robust at raw 0.05 and pass BH but fail Bonferroni.

Two mask headlines are called “robust at 0.05” and fail **both** Bonferroni and BH: JJA EVI (+0.0114), which the report already flags, and **POWER ALLSKY_SFC_SW_DWN +0.0496 kWh/m²/day/decade** (HAC p=0.023, HR p=0.042), which is not mentioned in the results prose. The headline table does show `mt_bonferroni_pass=False`, `mt_bh_pass=False`, so the columns say so; `robust_call` does not. On the bbox the same pattern appears for GLDAS-2.0 `rainfall_liquid` and GLDAS-2.1 `Evap_tavg`. A one-line note next to those rows (as was done for JJA EVI) would close it.

### 3. GRACE −12.12 (mask) vs −11.242 (bbox) are region-labelled (verified)

Recomputed with `grace_headline_trend` (same function as the blocking smoke test): `ukraine_mask` **−12.1199** cm/decade (n=235), `ukraine_bbox` **−11.2420**, `ukraine_mask_no_crimea` **−12.3637**. Every GRACE row carries the `region` column; headline tables are under per-region headings; both headline rows pass Bonferroni and BH. The generic 12/12 and record-mean monthly GRACE rows stay `role=different_convention`, `headline=False`.

### Nits (one line each)

- POWER ALLSKY (mask) and, on the bbox, GLDAS-2.0 liquid rain and 2.1 Evap are robust headlines that fail both MT corrections and are not called out in prose (item 2).
- CRU `vap` also survives Bonferroni on the mask; it is not a temperature series.
- GLDAS-2.1 `Tair_f_inst` +0.95 °C/decade (n=26) is a Bonferroni-surviving headline; it sits on the same short 2.1 forcing window that disqualified 2.1 snowfall — flag or compare with 2.0 / MERRA-2 before pitching it as independent.
- The growing-season VI table in `qc_report.md` truncates `robust_call` at 70 characters.
- `role` values `finding_peak season (JJA)` / `finding_growing season (Apr-Sep)` are a bit awkward; harmless.

### What I could not verify

- I did not rerun `run_pipeline.py` or `smoke_test.py` (the latter would rewrite `qc_report.md`). Slopes and MT flags were recomputed from the current tidy tables.
