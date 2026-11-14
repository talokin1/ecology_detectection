"""Writes qc_report.md next to this package from per-region outputs."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .core import GLOBAL, PIPE, SAMPLES, VARS
from .qc import crimea_check

FLAG_LEGEND = {
    "partial_year": "row belongs to a year with <12 valid months, incl. its NaN rows (excluded from annual values; e.g. 2026, IMERG 2025)",
    "missing_value": "value is NaN in this row (e.g. GSOM March 2026: no station report)",
    "short_record": "record spans <10 years",
    "outlier_5sigma": "deseasonalised anomaly beyond 5 SD of the series' anomalies",
    "out_of_range": "raw value outside the valid range in variables.yaml -> set NaN",
    "no_qc": "MODIS FALLBACK only (QC files missing): NO per-pixel QC applied (fill/range only)",
    "qc_pixel_masked": "MODIS per-pixel QC applied before area averaging (rules in 'MODIS QC' section)",
    "qc_low_coverage_lt50pct": "MODIS month where <50% of the region area survives QC (mostly Jan/Feb VI under snow)",
    "vi_winter_snow_masked_sampling": "NDVI/EVI: QC drops snow/cloud pixels (~32% of area in DJF), so winter means cover a varying snow-free subset; prefer JJA/growing-season VI for trends",
    "speed_of_monthly_mean_wind_underestimates_mean_speed": "MERRA-2 WS10M_from_mean_UV = |monthly-mean wind vector|, NOT mean wind speed (ukraine_mask mean 1.6 m/s vs POWER WS10M 4.3 m/s); use for flow persistence only",
    "terra_only": "MODIS Terra only, no Aqua",
    "lst_clear_sky_winter_bias": "MODIS LST is clear-sky only: winter means biased (LST_Day/LST_Night only, not NDVI/EVI); see LST_*_clear_days",
    "preaggregated_bbox_mean_centre_weights": "FALLBACK path only (global file missing): bbox mean computed at download (cell centres), not our overlap weights; bbox region only",
    "coarse_cells_extend_beyond_region": "5°/2° cell values average land+sea outside the region; overlap weights only",
    "missing_month_official": "GRACE month missing in the official product (NaN, no interpolation)",
    "grace_gracefo_gap": "GRACE -> GRACE-FO gap 2017-07..2018-05",
    "airs_2025_bias_unverified": "AIRS 2025 bias collapse not yet investigated: 2025 is EXCLUDED from all AIRS trends (column excluded_years)",
    "omi_row_anomaly_period": "OMI row anomaly (2007+); extract not filtered on XTrackQualityFlags",
    "own_country_mask": "country series with the producer's own mask (not our polygon)",
    "crimea_excluded": "producer mask excludes Crimea",
    "crimea_undocumented": "producer docs do not say whether Crimea is included",
    "mask_mismatch_vs_region": "producer mask differs from this region's mask (do not compare 1:1)",
    "absolute_not_anomaly": "CRU tmp is absolute °C; use tmp_anom for cross-source comparison",
    "station_anomaly_mean": "mean of station anomalies vs per-station 1991-2020 monthly normals (>=15 yrs)",
    "few_stations_lt3": "fewer than 3 stations contribute to this month's regional anomaly",
    "UP_stations_only": "only Ukrainian (UP) stations were downloaded, even for the bbox",
    "too_short_for_climate_inference": "SWOT ~3 years",
    "partial_record_1978-1991": "CCI SM assembled only for 1978-11..1991-12",
}

DEVIATIONS = """
- Tidy files are written as `data/tidy/<region>/<source>.parquet` (one folder per region) instead of a single
  `data/tidy/<source>.parquet`, so bbox and mask runs don't overwrite each other. Every row still carries `region`.
- Extra columns in the tidy schema: `anomaly` (deseasonalised by monthly climatology), `baseline`
  (`1991-2020` if every calendar month has >=20 baseline years, else `record_mean`), `independence_group`.
- Annual = 12/12 months only. The plan's alternative "mean of deseasonalised anomalies with >=10 months" was NOT
  built (the task said 12/12; it would be a second, labelled series - easy to add later).
- MERRA-2 (slv+flx), GLDAS 2.0/2.1, IMERG, AIRS, MODIS (MOD13C2 NDVI/EVI, MOD11C3 LST), GPCC and CHIRPS are now cut
  from the GLOBAL files under $GLOBAL_DATA (`ukpipe/loaders/global_grids.py`) with the same fractional-overlap
  x spherical-area weights as every other gridded loader, for any region in regions.yaml (generic; also the path to
  global regions). Only the region window is read from each file; per-region series are cached in data/cache/series.
  If a global file set is missing, the loader falls back to the old bbox extract (flag
  `preaggregated_bbox_mean_centre_weights`, bbox region only) - see `path` / `fallback_reason` in Source status.
  OMI and SWOT stay bbox-only (skipped for masks). Verification against the old extracts: section below.
- MODIS scale handling from the raw global files: MOD13C2 VI physical = raw / 10000 (the file's scale_factor attribute
  is a divisor), valid raw -2000..10000, fill -3000; MOD11C3 LST = raw x 0.02 K, valid raw 7500-65535, fill 0.
  Per-pixel QC from the paired QC files is applied BEFORE area averaging (since 14 Nov 2026; `no_qc` only on fallback),
  see "MODIS QC". AIRS: per-cell nanmean of ascending and descending, then area-weighted.
- Units were recomputed from raw columns with the variables.yaml conversions and checked against the extract's own
  converted columns (max abs diff 0.0; see Source status -> checks); POWER/MERRA-2/IMERG/GLDAS precip and fluxes are mm/month everywhere.
- Ukraine-bbox extracts (POWER, CCI SM; CHIRPS in fallback) were cut on cell centres at download, so a <1-cell edge
  strip can be missing (e.g. POWER has no 52.5N row; 52.25-52.4N is uncovered). `coverage_frac` is now honest for
  every gridded loader: valid weighted area / TRUE region area (spherical bbox area or equal-area polygon area), so
  missing edge strips and sea/fill cells lower it (POWER bbox ~0.99, CHIRPS bbox ~0.95 because sea cells are fill).
- GRACE uses the official GLOBAL file in $GLOBAL_DATA/grace (same granule as the bbox cut) so overlap
  weights include the 44.0-44.5N row; land_mask cells only; dates = Researcher CSV `date` column.
- Berkeley Earth 1° uses the global file in $GLOBAL_DATA (overlap x land-fraction weights), not the
  centre-selected bbox CSV.
- Stations: regional series = mean of station anomalies (per-station 1991-2020 normals, >=15 years per month);
  stations without that baseline are excluded (no baseline fallback - cut item). Station selection = point in region.
  **v1 LIMITATION (baseline, no fallback):** see the "Station baseline coverage" table per region. ukraine_bbox GSOM
  TAVG: 183 stations with data, only 36 have >=1 calendar month with a 15-year 1991-2020 baseline and 9 a full
  12-month baseline; 147 are dropped (49 of the 183 end before 2006). GHCN TAVG: 27 stations with data, 25 with a full
  baseline, 0 ending before 2006. Station series are therefore thin (few_stations_lt3 months) and GSOM has no annual
  values 2020-2024.
- Station counts per trend window = min / median number of stations contributing to monthly regional anomalies in
  the window (stations need a 1991-2020 baseline).
- Station trends: the HEADLINE window for GSOM/GHCN is 1981-2019 (`1981-2019_station_window`, headline=True).
  1981-2025 (and full/2001-2025) is kept but labelled `*_gappy`, with n and the missing years
  (GSOM 2020-2024; GHCN 2007-2009) in `missing_years`, and robust_call says it is NOT treated as robust.
  GHCN 1981-2019 also lacks 2007-2009 (n=36), noted in its robust_call.
- AIRS: 2025 (airs_2025_bias_unverified) is excluded from every AIRS trend; annual full window = 2003-2024, n=22.
- GRACE smoke test (CHANGED 14 Nov 2026, decided by the team lead via Thinker): fractional-overlap weights are the
  PRODUCTION method for GRACE. The BLOCKING GRACE check is now the production tidy series vs -11.242 ±0.005.
  Overlap adds partial edge cells (44.0-44.5N row, 40.0-40.5E column, 22.0-22.5E at 0.8) vs the original
  cell-centre selection, which gave -11.222. That centre-selection check is kept as a documented NON-blocking
  'legacy' check. (Difference ~0.2%, far below the inter-mascon spread of 3.17 cm/decade.)
- GRACE in trends.csv (Critique v1.1 re-review): the HEADLINE GRACE row is `series=monthly_deseasonalised_grace_headline_method`,
  `window=headline_grace_method` (complete-year climatology, drop 2002/2017/2018/2026, time_center, monthly
  deseasonalised OLS), computed by `ukpipe/grace_method.py` - the SAME function the blocking smoke test calls
  (ukraine_bbox -11.242, n=235). The generic 12/12 annual GRACE rows are labelled `*_gappy_annual12of12_convention`
  (n=14, missing 2011-2018 because of the 2011+ missing months and the GRACE/GRACE-FO gap) and the generic monthly row
  `full_generic_convention` (record-mean climatology, month-start time, n=252); both are a different convention,
  headline=False, not robust/headline.
- AIRS 2025: annual/seasonal rows in annual_seasonal.parquet carry `airs_2025_bias_unverified` (any year/season containing
  a flagged month); 2025 is excluded from all AIRS trends.
- GLDAS-2.1 `snowfall` and `SWE_inst` are labelled `role=forcing_diagnostic` (not findings, headline=False): 2.1 snow
  disagrees with 2.0 over 2000-2014 (annual means 78 vs 131 mm/yr, overlap slopes +14.6 vs -0.9, both n.s.), the 2000-2025
  window spans the 2.1 forcing breaks (Mar 2001, AGRMET after 2011, GALWEM from Jun 2025), dropping 2000 and 2025 gives
  ~-16 mm/yr per decade (n.s.), the HAC p fails Bonferroni in the annual family, and no non-GLDAS-2.1 snow source exists here.
- `LST_Day_clear_days` / `LST_Night_clear_days` are `role=sampling_diagnostic` (not climate headlines).
- Slope units: `slope_unit` in trends.csv = series unit + " per decade"; annual precip-type slopes are "mm/yr per decade"
  (e.g. GLDAS-2.1 snowfall -22.7 mm/yr per decade, about -20% of its 115.5 mm/yr mean per decade).
- Multiple testing (v1.4): primary p-values are repo Mann-Kendall Yue-Wang (`yw_p`). Bonferroni and
  Benjamini-Hochberg are applied inside the annual family and inside the monthly family.
  `mt_bonferroni_pass` / `mt_bh_pass` are those Yue-Wang corrections. HAC and Hamed-Rao lag-3 stay as
  sensitivity columns (`sens_*`). `robust_call` is the raw Yue-Wang 0.05 call (plus the diagnostic
  labels). A row is a detection only when Yue-Wang and the OLS n_eff cross-check agree and the
  Yue-Wang p-value survives the correction being quoted. Family sizes are in `n_tests_in_family`.
- GLDAS precip residual: `precip_total - rainfall_liquid - snowfall` is not identically zero (max |0.29| mm/month) because
  liquid rain is clipped at 0 per cell and Snowf has a slightly smaller valid mask than Rainf_f (e.g. 1,281 vs 1,288 cells,
  Jan 2000). The official liquid-only `Rainf_tavg` was NOT fetched, so liquid rain is derived (Rainf_f - Snowf).
- GPCC/CHIRPS levels: production (overlap-weighted, global files) 1981-2025 ANN means are GPCC 585.35 and CHIRPS
  686.78 mm/yr vs the old centre-cut bbox extracts 586.39 / 686.69 (ukraine_bbox) - the documented overlap-vs-centre
  effect, not a bug. Quote the production numbers.
- Mid-run loader bug (14 Nov 2026, v1.2 build, fixed before the final run): extending the cache signature to include
  MODIS QC files looked up `PRODUCTS[prod_key]`, which has no entry for the GPCC/CHIRPS custom loaders -> KeyError ->
  both sources FAILED in one intermediate run (status visible in run_meta). Fixed with `PRODUCTS.get`; the final series
  are clean overlap-weighted cuts (verified by Critique).
- AIRS 2025 is still a 12/12 year in annual_seasonal.parquet, but every 2025 AIRS annual/seasonal row carries
  `airs_2025_bias_unverified` and 2025 is excluded from all AIRS trends.
- GPCC: only `precip` is read. The `gauge` / `gauge_int` station-count fields in the v2025 files are NOT used (no gauge
  weighting or gauge-density flag in v1; early (1891+) values rest on sparse gauges).
- MODIS QC layers landed (14 Nov 2026): production MODIS is per-pixel QC'd (`qc_pixel_masked`); `no_qc` is only set
  if the QC files are missing (fallback to the unQC'd global files, then the old bbox extract).
- New global add-ons (14 Nov 2026), all via the same cutter (overlap weights, region config, cache, optional products
  skip with a note if their files are missing - the main source then still loads):
  - MERRA-2 U10M, V10M (M2TMNXSLV monthly means) and `WS10M_from_mean_UV` = sqrt(U10M²+V10M²) per cell, then averaged.
    Because the inputs are MONTHLY MEANS this is the speed of the mean wind vector, which UNDERESTIMATES the mean wind
    speed (directional cancellation): ukraine_mask mean 1.6 m/s vs POWER WS10M 4.3 m/s. Flagged; not a wind-speed climatology.
  - MERRA-2 T2MMAX, T2MMIN from M2SMNXSLV (monthly mean of DAILY max/min, verified: Jul 1980 bbox 24.2 / 14.5 °C vs
    T2M 19.6 °C), °C; `DTR` = T2MMAX - T2MMIN per cell (source merra2; the older `derived:DTR` is POWER-based).
  - GLDAS 2.0 and 2.1 (separate series, NO splice): `precip_total` = Rainf_f_tavg, `snowfall` = Snowf_tavg,
    `rainfall_liquid` = Rainf_f - Snowf per cell; kg m-2 s-1 -> mm/month (x86400 x days in month). In GLDAS-2,
    Rainf_f_tavg is already the TOTAL precipitation rate (rain + snow, forcing), so rain + snow is NOT added
    (that would double count snow); liquid rain is derived instead. Level check (ukraine_mask, 2001-2020 annual means):
    GLDAS 2.1 precip_total 726 mm/yr vs GPCC 574, MERRA-2 PRECTOTCORR 586, CHIRPS 687 -> GLDAS 2.1 forcing is wet;
    GLDAS forcing datasets changed over time, so treat GLDAS precip trends as model-forcing diagnostics, not observations.
- CHIRPS uses ONLY the global NetCDF archive (chirps-v3.0.monthly.nc, 1981-01..2026-09). The bbox COG extract is a
  fallback if that file is missing and is never spliced on (it differs from 2025-10 onward).
- Kyiv urban-rural night LST: NOT built - AppEEARS MOD11A2/MCD12Q1 data has not landed (folder empty).
- ERA5 ARCO 1940-1951 sample not loaded (12-year sample; not in the plan).
- Cut items skipped per plan: hot/frost/heavy-precip days, P-ET, TWS-GLDAS, baseline fallback, global tiling.
- Version/extent notes from the global files: IMERG global starts 1998-01 (extract 2000-06); CHIRPS global v3.0 file
  ends 2026-09 (bbox nc had 2026-10) and differs from the bbox nc only from 2025-10 on (preliminary months
  re-processed); MERRA-2 global ends 2026-09.
"""


def _md(df: pd.DataFrame) -> str:
    if df.empty:
        return "_(none)_\n"
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        out.append("| " + " | ".join("" if (isinstance(v, float) and np.isnan(v)) else (f"{v:.3g}" if isinstance(v, float) else str(v)) for v in r) + " |")
    return "\n".join(out) + "\n"


def _crimea_stations(ck_geom_diff=None):
    import shapely
    from .regions import load_polygon
    nd = PIPE / "data" / "raw_aux" / "natural_earth"
    diff = shapely.difference(load_polygon(nd / "ne_10m_admin_0_countries_ukr" / "ne_10m_admin_0_countries_ukr.shp", "UKR"),
                              load_polygon(nd / "ne_10m_admin_0_countries" / "ne_10m_admin_0_countries.shp", "UKR"))
    g = pd.read_csv(SAMPLES / "noaa_ghcn" / "ukraine_bbox_stations.csv")
    ids = {f.name.split(".")[0] for f in (SAMPLES / "noaa_ghcn" / "daily_by_station").glob("*.csv.gz")}
    g = g[g.id.isin(ids)]
    gh = g[shapely.contains_xy(diff, g.lon, g.lat)]
    s = pd.read_csv(SAMPLES / "noaa_gsom" / "gsom_ukraine_UP_stations.csv", usecols=["STATION", "NAME", "LATITUDE", "LONGITUDE"]).drop_duplicates("STATION")
    gs = s[shapely.contains_xy(diff, s.LONGITUDE, s.LATITUDE)]
    return list(gh.name), len(gs), len(s)


def write_data_dictionary():
    """pipeline/data_dictionary.csv: one row per OUTPUT variable (from config/variables.yaml + global product specs)."""
    from .loaders import global_grids as GG
    prod_of = {}
    for pk, p in GG.PRODUCTS.items():
        for k in p.vars:
            prod_of.setdefault((p.source, k), []).append(f"{pk} ({p.subdir}{'+' + p.extra['qc_subdir'] if 'qc_subdir' in p.extra else ''})")
    rows = []
    for src, sv in VARS.items():
        if src == "defaults":
            continue
        for k, v in sv["variables"].items():
            rows.append(dict(source=src, variable=v.get("out_name", k), file_variable=k, unit=v.get("unit"),
                             raw_unit=v.get("raw_unit"), conversion=v.get("conversion"), annual_agg=v.get("agg"),
                             valid_range=v.get("valid_range"), flags=";".join(x for x in (sv.get("qc_flag", ""), v.get("qc_flag", "")) if x),
                             global_products="; ".join(prod_of.get((src, k), [])), note=v.get("note", ""),
                             source_note=sv.get("note", ""), independence_group=v.get("group", sv.get("group"))))
    pd.DataFrame(rows).to_csv(PIPE / "data_dictionary.csv", index=False)


def write_report():
    regions = sorted(p.name for p in (PIPE / "data" / "tidy").iterdir() if (p / "run_meta.json").exists())
    L = ["# Preprocessing pipeline v1.4 - QC report", "",
         f"Generated {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')} (Europe/Kiev). Regions run: {', '.join(regions)}.", "",
         "Primary significance: repo Mann-Kendall with the Yue-Wang AR(1) correction (ADR-003). "
         "HAC and Hamed-Rao lag-3 are sensitivity columns.", "",
         "Run: `cd team-context/data/pipeline && OMP_NUM_THREADS=2 nice -n 10 python run_pipeline.py "
         "--region ukraine_bbox ukraine_mask && python smoke_test.py`", ""]
    sm = PIPE / "data" / "smoke_test_results.json"
    L.append("## Smoke test (blocking, region=ukraine_bbox, tolerance ±0.005)\n")
    if sm.exists():
        s = json.loads(sm.read_text())
        L.append(f"Overall: **{'PASS' if s['all_pass'] else 'FAIL'}** (run {s['run_at']})\n")
        sdf = pd.DataFrame(s["results"])[["check", "blocking", "reference", "upstream_exact", "reproduced", "diff", "n", "pass"]]
        for c in ["reference", "upstream_exact", "reproduced", "diff"]:
            sdf[c] = sdf[c].map(lambda v: "" if pd.isna(v) else f"{v:+.4f}")
        L.append(_md(sdf))
        L.append("Non-blocking rows do not affect Overall. Change 14 Nov 2026 (decided by the team lead via Thinker): the "
                 "blocking GRACE check is the production overlap-weighted series vs -11.242; the old cell-centre "
                 "check (-11.222) is kept as a non-blocking legacy check.\n")
    else:
        L.append("_not run yet_\n")

    L.append("## Crimea\n")
    ck = crimea_check()
    try:
        ghcn_cr, n_gsom_cr, n_gsom = _crimea_stations()
    except Exception as e:  # pragma: no cover
        ghcn_cr, n_gsom_cr, n_gsom = [f"error {e}"], -1, -1
    m = ck["membership"]
    L.append(f"Natural Earth {ck['ne_version']} (10m admin-0), checked point-in-polygon, not assumed:\n")
    L.append(_md(pd.DataFrame(m).T.reset_index().rename(columns={"index": "place"})))
    L.append(f"""
- **Default file `ne_10m_admin_0_countries` (de-facto view) assigns Crimea to RUS.** Its UKR polygon is
  {ck['area_km2_default_UKR']:,} km², bounds {ck['default_bounds']} (lat min 45.21 = the Berkeley Earth country
  polygon, 553,101 km²).
- **Ukraine point-of-view file `ne_10m_admin_0_countries_ukr` assigns Crimea to UKR**: {ck['area_km2_ukr_pov_UKR']:,} km²,
  bounds {ck['ukr_pov_bounds']}. The difference is {ck['area_km2_difference']:,} km² with bounds {ck['difference_bounds']}
  (Crimea + Sevastopol only; Donetsk/Luhansk are UKR in both files).
- **`ukraine_mask` (POV file, internationally recognised borders, Ukraine incl. Crimea) is the only Ukraine mask.**
  The default file is used only for this check; there is no without-Crimea variant.
- `ukraine_bbox` (44.4-52.4N) contains essentially all of Crimea (its southern tip reaches 44.38N).
- Consistency: every gridded source (POWER, GRACE, HadCRUT5, GISTEMP, Berkeley 1°, CHIRPS, CCI SM, and now MERRA-2,
  GLDAS, IMERG, AIRS, MODIS, GPCC from global files) uses the SAME
  region polygon/weights per run, and stations are selected by the same polygon. Producer country series do not:
  Berkeley country file EXCLUDES Crimea (flag `crimea_excluded;mask_mismatch_vs_region` in `ukraine_mask`);
  CRU-CY is undocumented (`crimea_undocumented`). Don't compare those 1:1 with masked series.
- Stations in Crimea: GHCN (downloaded 28): {', '.join(ghcn_cr) if ghcn_cr else 'none'}; GSOM: {n_gsom_cr} of {n_gsom} UP stations.
  They are in `ukraine_mask` and `ukraine_bbox`.
- Coarse products: one HadCRUT 5° cell / GRACE mascons straddle Crimea and the Black Sea; overlap weights only.
""")
    L.append("## Units and conversions (single targets, config/variables.yaml)\n")
    rows = []
    for src, sv in VARS.items():
        if src == "defaults":
            continue
        for k, v in sv["variables"].items():
            rows.append(dict(source=src, variable=v.get("out_name", k), raw_unit=v.get("raw_unit"), conversion=v.get("conversion"),
                             unit=v.get("unit"), annual=v.get("agg"), group=v.get("group", sv.get("group"))))
    L.append(_md(pd.DataFrame(rows)))
    L.append("Conversion keys: per_s_to_month = x86400 x days; per_day_to_month = x days; per_hour_to_month = x24 x days; "
             "acc3h_to_month = x8 x days (GLDAS 3-hourly accumulations); tenths = x0.1; K_to_C = -273.15.\n")
    vp = PIPE / "data" / "verify_global_vs_bbox.csv"
    L.append("## Verification: global-file cuts vs old bbox extracts (ukraine_bbox)\n")
    if vp.exists():
        v = pd.read_csv(vp)
        L.append("`verify_global_vs_bbox.py`. diff = global - old on MONTHLY values (unit column); trends = OLS on "
                 "12/12 annual values per decade (trend_unit; precip/flux annual totals) over common complete years (AIRS to 2024).\n")
        cols = ["source", "variable", "unit", "n_common", "first", "last", "corr", "mean_diff", "max_abs_diff",
                "rel_mean_diff_pct", "trend_unit", "trend_new", "trend_old", "trend_diff", "trend_years"]
        vv = v[cols].copy()
        for c in ["corr", "mean_diff", "max_abs_diff", "rel_mean_diff_pct", "trend_new", "trend_old", "trend_diff"]:
            vv[c] = vv[c].map(lambda x: f"{x:.4f}")
        L.append(_md(vv))
        L.append("""Why they differ:
- Cell-centre vs overlap: the extracts selected cells whose CENTRE is inside 22.1-40.2E / 44.4-52.4N; the new cut
  weights every intersecting cell by its overlap fraction x spherical area (MERRA-2 0.5x0.625, GPCC/AIRS 1 deg, GLDAS
  0.25 deg). This explains MERRA-2 T2M -0.12 °C (extra southern sea/coast row), GPCC max 5 mm, GLDAS 0.2-2 %.
- MODIS: extract = UNWEIGHTED, unQC'd pixel mean; new = area-weighted AND per-pixel QC'd (since 14 Nov 2026). LST
  still matches (corr 1.000, trend diff <=0.0012 °C/decade). NDVI/EVI corr drops to 0.957/0.989 because QC removes
  snow/cloud pixels in winter (see "MODIS QC"); before QC the area-weighted cut matched at corr 1.000 (diff <=0.0047).
- AIRS: extract = mean of the ascending and descending bbox means; new = per-cell nanmean(A, D) then weighted
  (mean diff -0.25 °C, trend 2003-2024 +0.819 vs +0.815).
- IMERG: 0.1 deg cell edges coincide with the bbox edges so both methods select identical cells: exact match.
- Units: all precip/flux in mm/month via the same variables.yaml conversions; no unit mismatches found.
- Version: CHIRPS differs only from 2025-10 on (max 15.1 mm in 2026-02; <0.33 mm before) = preliminary months
  re-processed between the two downloads; it also moves the CHIRPS 1981-2025 trend by +0.11 mm/yr per decade.
""")
    else:
        L.append("_not run yet (python verify_global_vs_bbox.py)_\n")
    L.append("## MODIS QC (per-pixel, before area averaging)\n")
    L.append("""Rules (`ukpipe/loaders/global_grids.py`, `_vi_good` / `_lst_good`):
- MOD13C2 NDVI/EVI: keep a pixel if `CMG_0_05_Deg_Monthly_pixel_reliability` is 0 (good) or 1 (marginal) AND
  `VI_Quality` bits 0-1 (MODLAND QA) are 00 (good) or 01 (produced, check other QA). Dropped: reliability -1 (fill),
  2 (snow/ice), 3 (cloudy), 4 (estimated), MODLAND 10/11.
- MOD11C3 LST_Day/LST_Night: `QC_Day`/`QC_Night` bits 0-1 (mandatory QA) = 00 (good) kept; = 01 (other quality) kept only
  if bits 6-7 (average LST error) = 00 (<=1 K) or 01 (<=2 K); 10/11 (not produced) dropped. QC value 0 means "good"
  even though the QC _FillValue is 0, so QC bits are never fill-masked; missing LST is caught by the LST fill.
- No clear-sky-days threshold is applied; `LST_Day_clear_days` / `LST_Night_clear_days` (popcount of the
  Clear_sky_days/nights bit fields, mean over QC'd pixels) are published so the clear-sky winter bias can be judged.
- Months with <50% of the region surviving QC are kept but flagged `qc_low_coverage_lt50pct`.
""")
    mq = PIPE / "data" / "modis_qc_impact.csv"
    if mq.exists():
        m_ = pd.read_csv(mq)
        cols = ["region", "variable", "area_removed_by_qc_pct_mean", "area_removed_by_qc_pct_max", "months_qc_coverage_lt50pct",
                "months_lost", "mean_diff_qc_minus_noqc", "trend_qc_per_decade", "trend_noqc_per_decade", "trend_diff",
                "trend_DJF_qc", "trend_DJF_noqc", "trend_JJA_qc", "trend_JJA_noqc", "robust_qc", "robust_noqc"]
        mm = m_[cols].copy()
        for c in cols[2:-2]:
            mm[c] = mm[c].map(lambda x: f"{x:.4g}")
        L.append("QC impact (`compare_modis_qc.py`, same cached pass; annual 12/12 OLS 2001-2025 per decade):\n")
        L.append(_md(mm))
        ms = PIPE / "data" / "modis_qc_impact_seasonal.csv"
        if ms.exists():
            sp_ = pd.read_csv(ms).pivot_table(index=["region", "variable"], columns="season",
                                              values="area_removed_by_qc_pct_mean").reset_index()
            L.append("% of valid area removed by QC, by season:\n")
            L.append(_md(sp_.round(2)))
        L.append("""Reading: LST QC removes <0.4% of area (the CMG LST is already clear-sky) and moves trends by <=0.001 °C/decade.
VI QC removes ~32% of the area in DJF (snow/ice and cloud), raises winter NDVI (mean +0.02), and roughly halves the
annual NDVI trend; annual EVI stays HAC-significant but is no longer robust (Hamed-Rao anti-conservative). JJA VI trends
are unchanged by QC, so the QC change is a winter-sampling effect: use JJA/growing-season VI for trend claims.
""")
    L.append("## Multiple-testing summary (headline rows)\n")
    L.append("""Primary test (v1.4, ADR-003): repo Mann-Kendall Yue-Wang. `mt_bonferroni_pass` / `mt_bh_pass` are
Bonferroni and Benjamini-Hochberg on `yw_p` inside each test family (annual, or monthly). The OLS n_eff
cross-check is `yw_ols_neff_p`; `yw_ols_neff_agree` is whether the two tests agree at 0.05. HAC and
Hamed-Rao lag-3 remain sensitivity columns (`sens_mt_*`). A headline is a detection only when Yue-Wang is
significant at 0.05, the OLS cross-check agrees, and the quoted multiple-testing correction passes.
The lists below are computed from this run. v1.3 called a row robust only when HAC and Hamed-Rao both
passed; that rule is no longer the wording.

POWER solar (`ALLSKY_SFC_SW_DWN`) has a source break (GEWEX SRB before 2001, CERES from 2001). The
pipeline uses 2001+ only. Do not headline it unless this run's Yue-Wang row survives Bonferroni or BH
and agrees with OLS n_eff. GLDAS precipitation and evaporation are forcing diagnostics, not observations.
""")
    for reg in regions:
        tp_ = PIPE / "data" / "tidy" / reg / "trends.csv"
        if not tp_.exists():
            continue
        t_ = pd.read_csv(tp_)
        h_ = t_[t_.headline == True]  # noqa: E712
        def lab(d):
            sfx = d.window.str.extract(r"_(JJA|AMJJAS)$")[0].fillna("")
            names = d.source + ":" + d.variable + sfx.map(lambda x: f" ({'JJA' if x == 'JJA' else 'Apr-Sep'})" if x else "")
            return ", ".join(sorted(set(names))) or "none"
        raw_sig = h_[h_.robust_call.astype(str).str.startswith("significant at 0.05")]
        L.append(f"- `{reg}`: Bonferroni pass: {lab(h_[h_.mt_bonferroni_pass])}. "
                 f"BH only: {lab(h_[h_.mt_bh_pass & ~h_.mt_bonferroni_pass])}. "
                 f"Yue-Wang raw 0.05 but fail BH: {lab(raw_sig[~raw_sig.mt_bh_pass])}.")
    L.append("")
    vi_rows = []
    for reg in regions:
        tp_ = PIPE / "data" / "tidy" / reg / "trends.csv"
        if tp_.exists():
            t_ = pd.read_csv(tp_)
            t_ = t_[(t_.source == "modis") & t_.variable.isin(["NDVI", "EVI"]) & ~t_.series.str.startswith("monthly")]
            for _, r_ in t_.iterrows():
                vi_rows.append(dict(region=reg, variable=r_.variable, series=r_.series, years=f"{int(r_.start)}-{int(r_.end)}",
                                    n=int(r_.n), slope_per_decade=f"{r_.lin_slope_per_decade:+.5f}",
                                    yw_p=f"{r_.yw_p:.3g}" if pd.notna(r_.yw_p) else "",
                                    yw_ols_neff_p=f"{r_.yw_ols_neff_p:.3g}" if pd.notna(r_.get("yw_ols_neff_p", float('nan'))) else "",
                                    hac1_p=f"{r_.hac1_p:.3g}", mk_hr_p=f"{r_.mk_hr_p:.3g}",
                                    call=str(r_.robust_call).split(" [")[0].replace("ANNUAL 12/12", "annual")[:90],
                                    bonferroni=r_.mt_bonferroni_pass, bh=r_.mt_bh_pass, headline=r_.headline))
    if vi_rows:
        L.append("## Growing-season vegetation (QC'd MODIS NDVI/EVI)\n")
        L.append("""Peak season = JJA (3/3 months); growing season = Apr-Sep (6/6 months, period `AMJJAS` in annual_seasonal);
both for 2001-2025 (the years of the annual 12/12 row), both in the official annual test family. The annual 12/12 VI row is
kept but labelled `annual_includes_low_coverage_winter_months` (22 Jan/Feb months with <50% QC coverage over the record)
and is not a headline. **Results are season-sensitive.** Read `yw_p` (primary) next to `yw_ols_neff_p` and the
HAC/Hamed-Rao sensitivity columns. A seasonal VI row is not a detection unless Yue-Wang and the OLS cross-check
agree and the quoted multiple-testing correction passes. Neither season is preferred.
""")
        L.append(_md(pd.DataFrame(vi_rows)))
    for reg in regions:
        d = PIPE / "data" / "tidy" / reg
        meta = json.loads((d / "run_meta.json").read_text())
        L.append(f"## Region `{reg}`\n")
        L.append(f"Bounds {meta['bounds']}; {meta['n_series']} series; {meta['seconds']} s.\n")
        L.append("### Source status\n")
        srows = []
        for s, n in meta["sources"].items():
            extra = {k: v for k, v in n.items() if k not in ("source", "status", "seconds", "variables")}
            srows.append(dict(source=s, status=n.get("status"), details=json.dumps(extra, default=str)[:400]))
        L.append(_md(pd.DataFrame(srows)))
        qc = pd.read_csv(d / "qc_variables.csv")
        L.append("### Per-variable QC\n")
        cols = ["source", "variable", "unit", "first", "last", "pct_valid_raw", "pct_valid_gap_excluded", "n_gaps",
                "longest_gap_months", "complete_years", "min_coverage_frac", "min_n_valid", "baseline", "flag_counts"]
        L.append(_md(qc[[c for c in cols if c in qc]]))
        tp = d / "trends.csv"
        if tp.exists():
            tr = pd.read_csv(tp)
            if "headline" in tr:
                h = tr[tr.headline == True]  # noqa: E712
                L.append("### Headline trends (annual full window; stations 1981-2019; GRACE = headline method, monthly; "
                         "VI = peak-season JJA and growing-season Apr-Sep)\n")
                L.append("`mt_bonferroni_pass` / `mt_bh_pass` are Bonferroni / Benjamini-Hochberg (q<0.05) on the "
                         "primary Yue-Wang p-value, across the whole test family (all windows and roles; family size in "
                         "`n_tests_in_family`). `yw_ols_neff_agree` is the OLS effective-n cross-check. HAC / Hamed-Rao "
                         "are sensitivity only (`sensitivity_call_hac_hr`). Forcing/sampling diagnostics, "
                         "different-convention rows and the annual VI rows are not headlines (column `role` in trends.csv).\n")
                cols = ["source", "variable", "unit", "series", "window", "start", "end", "n", "lin_slope_per_decade",
                        "yw_p", "yw_ols_neff_p", "yw_ols_neff_agree", "robust_call", "mt_bonferroni_pass",
                        "mt_bh_pass", "test_family", "n_tests_in_family", "excluded_years"]
                hh = h[[c for c in cols if c in h.columns]].copy()
                hh["robust_call"] = hh["robust_call"].str.slice(0, 90)
                for c in ["start", "end"]:
                    hh[c] = hh[c].map(lambda v: "" if pd.isna(v) else (f"{int(v)}" if float(v).is_integer() else f"{v:.2f}"))
                for c in ["lin_slope_per_decade", "yw_p", "yw_ols_neff_p"]:
                    if c in hh.columns:
                        hh[c] = hh[c].map(lambda v: "" if pd.isna(v) else f"{v:.4g}")
                L.append(_md(hh))
            sn = [(s_, v_, k_) for s_, n_ in meta["sources"].items() if s_ in ("gsom", "ghcn")
                  for v_, k_ in n_.get("variables", {}).items()]
            if sn:
                L.append("### Station baseline coverage (v1 limitation: no baseline fallback)\n")
                L.append(_md(pd.DataFrame([dict(source=a, variable=b, **{k: x for k, x in c.items()}) for a, b, c in sn])))
            st = tr[tr.source.isin(["ghcn", "gsom"]) & (tr.series == "annual_ANN_12of12")]
            if len(st):
                L.append("### Station counts per trend window (annual 12/12)\n")
                L.append(_md(st[["source", "variable", "window", "headline", "n", "missing_years", "stations_min", "stations_median", "lin_slope_per_decade", "robust_call"]]))
    L.append("## Flag legend\n")
    L.append(_md(pd.DataFrame([dict(flag=k, meaning=v) for k, v in FLAG_LEGEND.items()])))
    L.append("## Deviations, choices and open items\n")
    L.append(DEVIATIONS)
    text = "\n".join(L)
    for src, dst in ((str(GLOBAL), "$GLOBAL_DATA"), (str(SAMPLES), "$UKRAINE_SAMPLES")):
        text = text.replace(src, dst)
    (PIPE / "qc_report.md").write_text(text)
    write_data_dictionary()
    return PIPE / "qc_report.md"
