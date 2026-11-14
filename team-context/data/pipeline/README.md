# Preprocessing pipeline v1.4 (data analysis only)

Plan: `PREPROCESSING_PLAN.md` (v2). QC report: `qc_report.md`.

Primary significance is the repo Mann-Kendall Yue-Wang test (ADR-003). HAC and Hamed-Rao lag-3 are sensitivity columns.

## Run
Set `UKRAINE_SAMPLES` and `GLOBAL_DATA` if the extracts are not discoverable next to this checkout. Install `requirements-analysis.txt`.

    cd team-context/data/pipeline
    export OMP_NUM_THREADS=2
    nice -n 10 python run_pipeline.py --region ukraine_bbox ukraine_mask ukraine_mask_no_crimea
    nice -n 10 python verify_global_vs_bbox.py   # global cuts vs old bbox extracts -> data/verify_global_vs_bbox.csv
    nice -n 10 python compare_modis_qc.py        # MODIS QC'd vs unQC'd -> data/modis_qc_impact*.csv
    python smoke_test.py      # exit 1 only on a BLOCKING failure (POWER, HadCRUT5, GRACE production -11.242)
Options: `--sources nasa_power grace ...` (subset), `--no-trends`. First run of a new region ~85 s (global cuts are
computed, GLDAS 2.0 is the slowest at ~25 s), cached re-runs ~15 s. Workers for global cuts: `UKPIPE_WORKERS` (default 2).
New regions: add to `config/regions.yaml` - every gridded source, including the global files, follows the region config.

## Regions and Crimea
- **`ukraine_mask` is the PRIMARY mask**: Natural Earth 10m Ukraine point-of-view file, internationally recognised
  borders, Crimea INCLUDED (597,211 km²).
- `ukraine_mask_no_crimea` is a SENSITIVITY variant (default NE file, Crimea excluded, 570,178 km²).
- `ukraine_bbox` 22.1-40.2E, 44.4-52.4N (used for the smoke test and the verification against the old extracts).

## Layout
- `config/regions.yaml` (bbox / Natural Earth polygon; Crimea option), `config/variables.yaml` (units, conversions, valid ranges, per-variable qc flags, independence groups)
- `ukpipe/regions.py` fractional-overlap x spherical-area weights (cached in `data/cache/weights/`), `Region.area_km2`
- `ukpipe/core.py` schema, unit conversion, area aggregation (coverage_frac = valid area / true region area), 12/12 annual + 3/3 seasons (DJF -> Jan year), deseasonalising, flags
- `ukpipe/loaders/global_grids.py` generic global-file cutter: MERRA-2 slv/flx (+ U10M/V10M wind, M2SMNXSLV T2MMAX/T2MMIN, DTR), GLDAS 2.0/2.1 (+ Rainf_f/Snowf), IMERG, AIRS (A/D), MODIS MOD13C2/MOD11C3 with per-pixel QC, GPCC, CHIRPS (reads only the region window; per-cell derived fields; series cached in `data/cache/series/`)
- `ukpipe/loaders/dispatch.py` global file first, old bbox extract as FALLBACK when a global file set is missing
- `ukpipe/loaders/gridded.py` POWER, GRACE, HadCRUT5, GISTEMP, Berkeley 1°, CHIRPS bbox nc (fallback), CCI SM
- `ukpipe/loaders/tables.py` old pre-aggregated bbox tables (fallback; OMI and SWOT stay bbox-only), country series (CRU-CY, Berkeley country), stations (GHCN-D, GSOM)
- `ukpipe/trends.py` imports vendored `vendor/trend_methods.py` (unchanged maths) as sensitivity, and `ukpipe/repo_yw.py` imports the repo `trend_stats.py` as the primary test. Pettitt is exploratory only.
- `ukpipe/qc.py`, `ukpipe/report.py` QC table, Crimea check, verification table, report

## Outputs (`data/tidy/<region>/`)
- `<source>.parquet` tidy long monthly: source, variable, region, date (month start), value, unit, n_valid, n_effective_cells, coverage_frac, flags, anomaly, baseline, independence_group
- `all_monthly_long.parquet`, `monthly_wide.parquet|csv` (columns `source:variable`)
- `annual_seasonal.parquet|csv` (ANN 12/12; DJF/MAM/JJA/SON 3/3; precip/flux totals summed -> mm/year, mm/season)
- `trends.csv`: annual windows full / 1981-2025 / 2001-2025, monthly deseasonalised; columns `headline`, `missing_years`, `excluded_years`, robust_call, multiple-testing, Pettitt
- `qc_variables.csv`, `stations_ghcn.parquet`, `stations_gsom.parquet`, `run_meta.json`
- `data/smoke_test_results.json`, `data/verify_global_vs_bbox.csv`, `data/modis_qc_impact.csv`, `data/modis_qc_impact_seasonal.csv`
- `data_dictionary.csv` (pipeline output variables: units, conversions, flags, global products; regenerated with the report)

## New variables (14 Nov 2026)
- `merra2`: U10M, V10M, `WS10M_from_mean_UV` (sqrt(U²+V²) per cell of MONTHLY-MEAN winds = speed of the mean wind;
  underestimates mean wind speed: mask mean 1.6 vs POWER 4.3 m/s; flagged), T2MMAX/T2MMIN (M2SMNXSLV monthly mean of daily
  max/min, °C), DTR = T2MMAX - T2MMIN.
- `gldas20` / `gldas21` (separate, no splice): `precip_total` (Rainf_f_tavg, already rain+snow), `snowfall` (Snowf_tavg),
  `rainfall_liquid` (Rainf_f - Snowf), all mm/month. GLDAS 2.1 precip is wet vs GPCC (726 vs 574 mm/yr, mask 2001-2020);
  treat GLDAS precip trends as forcing diagnostics. Official liquid-only `Rainf_tavg` was not fetched, so liquid rain is
  derived; `precip_total - rainfall_liquid - snowfall` leaves a residual up to 0.29 mm/month (per-cell clipping, Snowf mask).
- Production precip levels (1981-2025 ANN, ukraine_bbox): GPCC 585.35, CHIRPS 686.78 mm/yr (old centre-cut extracts
  586.39 / 686.69; overlap-vs-centre effect, not a bug).
- `modis`: NDVI/EVI/LST now per-pixel QC'd (`qc_pixel_masked`), plus `LST_Day_clear_days` / `LST_Night_clear_days`.

## Trend conventions
- AIRS: 2025 flagged `airs_2025_bias_unverified` and excluded from all AIRS trends (annual full = 2003-2024, n=22).
- Stations (GSOM/GHCN): headline window 1981-2019. Windows with missing years (GSOM 2020-2024, GHCN 2007-2009) are
  labelled `*_gappy` with n and the missing years, and are not called robust.

- GRACE: headline = `series=monthly_deseasonalised_grace_headline_method` in trends.csv, computed by
  `ukpipe/grace_method.py` (same function as the blocking smoke test). Generic 12/12 annual and record-mean monthly
  GRACE rows are labelled as a different convention (not headline).

- `trends.csv` columns `role` (finding / forcing_diagnostic / sampling_diagnostic / different_convention /
  annual_includes_low_coverage_winter_months), `slope_unit` ("mm/yr per decade" for annual precip-type slopes),
  `test_family`, `n_tests_in_family`, primary Yue-Wang columns (`yw_p`, `yw_ols_neff_p`) and `mt_bonferroni_pass` /
  `mt_bh_pass` (Bonferroni / BH on `yw_p`). HAC and Hamed-Rao stay in `sens_*`. See qc_report
  "Multiple-testing summary" for which headline rows survive. A raw 0.05 Yue-Wang hit that fails the
  correction, or that disagrees with the OLS n_eff cross-check, is not a detection.
- Vegetation: official rows for peak season (JJA, 3/3) and growing season (Apr-Sep, 6/6, period `AMJJAS`) QC'd NDVI/EVI,
  2001-2025, both in the test family; results are season-sensitive (see qc_report). The annual 12/12 VI row is kept but
  labelled `annual_includes_low_coverage_winter_months` and is not a headline.
- GLDAS-2.1 snowfall and SWE: `forcing_diagnostic`, not findings (reasons in qc_report). LST clear-day counts: `sampling_diagnostic`.

## Known v1 limitations
- Station baseline, no fallback (cut item): a station enters a month's regional anomaly only with >=15 years of
  1991-2020 data for that calendar month. ukraine_bbox GSOM TAVG: 183 stations with data, 36 with >=1 baseline month,
  9 with a full 12-month baseline, 147 dropped (49 of the 183 end before 2006). GHCN TAVG: 27 with data, 25 with a
  full baseline, 0 ending before 2006. Counts per region/variable are in qc_report.md.
- MODIS: per-pixel QC before averaging (rules in qc_report "MODIS QC"); `no_qc` only on fallback. LST is clear-sky only
  (`lst_clear_sky_winter_bias`, LST only). VI QC removes ~32% of DJF area (snow), so annual VI trends carry a winter
  sampling effect (`vi_winter_snow_masked_sampling`); use JJA VI for trend claims.
- AIRS 2025 rows (monthly and annual/seasonal) carry `airs_2025_bias_unverified`.
- GPCC: only `precip` is read; the gauge-count fields (`gauge`, `gauge_int`) are unused.
- CHIRPS: only the global NetCDF archive is used; the bbox COG extract (differs from 2025-10) is a fallback, never spliced.
- GRACE smoke reference (14 Nov 2026, decided by the team lead via Thinker): overlap weights are the production method;
  the BLOCKING check is the production tidy series vs -11.242 ±0.005. The old cell-centre selection (-11.222) is a
  non-blocking 'legacy' check.
