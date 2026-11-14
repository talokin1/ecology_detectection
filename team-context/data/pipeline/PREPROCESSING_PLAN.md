# Preprocessing pipeline plan v2 (Thinker, revised per Critique 13:47) — Ukraine first, scale-ready

Goal: turn every raw extract into tidy, analysis-ready monthly/annual tables so we can quickly find interesting observations (trends, breaks, extremes, cross-source divergence). First version FAST; correctness over features.

## Design
- One loader per source (`loaders/<source>.py`) -> common schema. Region is config (`config/regions.yaml`): `ukraine_bbox` (22.1–40.2E, 44.4–52.4N, the approved-numbers region) and `ukraine_mask` (country polygon). Global = config only, no tiling work now.
- Long parquet `data/tidy/<source>.parquet`: source, variable, region, date (month start), value, unit, n_valid, n_effective_cells, coverage_frac, flags (partial_year, outlier_5sigma, no_qc, short_record, etc.).
- Wide monthly table per region for cross-source work.
- `config/variables.yaml`: raw unit, conversion, target unit, fill, scale/offset, valid range, independence group.

## Units (single targets)
- Temperature °C; precip mm/month everywhere: MERRA-2 kg m-2 s-1 x86400 x days; IMERG mm/hr x hours-in-month (check current extract is already mm/month); GLDAS Qs/Qsb accum x8 x days; CHIRPS 'mm' = mm/month; GPCC mm/month. Kelvin->°C; GHCN tenths; CRU tmp absolute °C -> anomaly before comparing.
- MODIS CMG: scale factors applied; the extract has NO QA bits -> flag `no_qc; Terra only; LST clear-sky (winter bias)`. Don't claim cloud filtering.

## Spatial
- Area (cos lat) weighting; fractional-overlap weights (not cell centres); record n_effective_cells.
- Coarse products (GRACE 3° mascons, HadCRUT 5°, GISTEMP 1200 km): overlap weights only, no fine polygon mask; GRACE stays at mascon level.
- Crimea: verify how the chosen Natural Earth file assigns it (don't assume). Default = internationally recognised borders (Crimea included), option to exclude. Cross-source comparisons must use the same mask; note Berkeley country files exclude Crimea, CRU-CY mask undocumented.

## Temporal
- Daily->monthly: temperature >=20 valid days; PRCP >=27 days (or full month) else NaN+flag. Apply GHCN QFLAG filter.
- Annual: 12/12 months, OR mean of deseasonalised anomalies with >=10 months (labelled). Seasons need 3/3; DJF year = year of Jan/Feb (Dec counts toward next year).
- Baseline 1991–2020 where available, else record mean (labelled). Deseasonalise monthly series by monthly climatology.
- Tag partial 2026 rows (MERRA-2 to Sep, GLDAS to Jul, AIRS/MODIS to Oct; IMERG 2025 partial); drop from annual trends.

## Stations (GHCN/GSOM)
- Output surviving station count per trend window. Station trend windows may end 2019 (labelled) given 2020–24 collapse (0/9 long-record TAVG usable). Anomalies before averaging.

## Series rules
- No splicing GLDAS 2.0/2.1. POWER solar 2001+ only. SWOT tagged too-short. GRACE: CSV date column, gaps NaN, no interpolation. OMI: row-anomaly flag (from 2007, XTrackQualityFlags). AIRS: investigate the 2025 bias collapse before using 2025 (flag until checked).
- Independence tags: POWER=MERRA-2; GISTEMP/HadCRUT/Berkeley/CRU/GHCN/GSOM = station family; IMERG gauge-calibrated w/ GPCC; CHIRPS uses GTS/GHCN/GPCC normals + ERA5 fill.

## Trends
- IMPORT vendor/trend_methods.py — do NOT reimplement (HAC lag-3 monthly, HR lag=3, negative-residual-AR flag, min_n=8, short-record label, hr_unequal_spacing, multiple-testing family count). v1.4 keeps that file as the sensitivity library. The primary test is the repo trend_stats.py Yue-Wang implementation (ADR-003).
- Pettitt changepoint: exploratory only, labelled anti-conservative under autocorrelation.

## Derived (v1 only)
- DTR = POWER T2M_MAX − T2M_MIN.
- Kyiv urban−rural night LST difference (when Researcher's AppEEARS MOD11A2+MCD12Q1 lands).
- >5σ anomaly flags; minimal qc_report.md (raw & gap-excluded % valid, gaps, min coverage, station counts).
- CUT for v1: hot/frost/heavy-precip days, cross-source P−ET, TWS−GLDAS, baseline fallback logic, global tiling.

## Smoke test (blocking)
Run region=ukraine_bbox and reproduce within ±0.005: POWER T2M +0.553 °C/dec (1981–2025); GRACE monthly deseasonalised −11.22 cm/dec; HadCRUT overlap +0.579 °C/dec. Masked-country results are NEW numbers, not checks.

## Deliverables
`team-context/data/pipeline/` package, `run_pipeline.py --region ukraine_bbox|ukraine_mask`, tidy parquet in `data/tidy/`, qc_report.md, smoke test passing.
