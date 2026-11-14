# Ukraine sample data — overview extras

14 November 2026, Europe/Kiev. Companion to `data_dictionary.md`. Overlap statistics are computed from the revised annual series in `$UKRAINE_SAMPLES/analysis/`. Global sizes use cited CMR / catalog / directory figures. GES DISC is now approved and verified (MERRA-2 monthly and GLDAS NOAH 0.25 monthly download with the EARTHDATA_TOKEN bearer); MERRA-2, GLDAS 2.0/2.1, IMERG Final, and AIRS are now pulled into `$UKRAINE_SAMPLES/`. OMI is still downloading (partial 2004-10–2006-12 on disk). AppEEARS is accessible (Earthdata login verified 14 Nov 2026, 12:40 Europe/Kiev) but 1 km rasters are not yet pulled. Hydrology Data Rods is discontinued, not blocked.

## 1. Overlaps

Several sources measure the same (or closely related) quantities. They do **not** share the same spatial support: POWER and MODIS are means over the wide bbox (land + some Black Sea + neighbours), while GSOM and GHCN-Daily are Ukraine (UP) stations, and the daily network is only 28 selected cities. Treat correlations as a consistency check, not a validation of a Ukraine-only average.

### What overlaps

| Theme | Sources | Spatial support | Overlapping period (complete years) |
|---|---|---|---|
| Air temperature | POWER T2M; GSOM TAVG; GHCN-Daily TAVG/TMAX/TMIN | 464 MERRA-2 cells in the bbox vs 204 UP monthly stations vs 28 UP daily stations (trends use long-record subsets) | 1981-2025, but GSOM long-record TAVG is **missing 2020-2024** |
| Land-surface vs air temperature | MODIS LST day/night (CMG 0.05deg) vs POWER T2M | Same bbox, different quantity (skin vs 2 m air) | **2001-2025** (drop MODIS 2000 and all 2026) |
| Precipitation | POWER PRECTOTCORR; GSOM PRCP; GHCN-Daily PRCP | Bbox reanalysis vs thinning UP stations | 1981-2025 on paper; GSOM PRCP coverage collapses after ~2000 and both station series are down to n=2 in several 2020s years |
| Vegetation | MODIS NDVI and EVI only (no second independent source in the extract) | Bbox CMG | 2001-2025 |
| Surface solar / wind | POWER only | CERES 1deg (solar, 1984-2025) and MERRA-2 (wind) | n/a (single source) |
| River water-surface elevation | SWOT Hydrocron only (too short to overlap a climate series) | 8 reaches, 2023-2026 | n/a |

### Agreement over the common period

Pearson *r* is on the overlapping annual values (equivalent to annual anomalies about the common-period mean). OLS and Theil-Sen slopes are per decade on those same years. GSOM temperature *raw* is the long-record network annual mean; GSOM 1981-2025 precipitation is stored as an anomaly only.

| Pair | Overlap | n years | r | OLS slopes (A, B) | OLS difference (A-B) | Theil-Sen (A, B) | Units |
|---|---|---:|---:|---|---|---|---|
| POWER T2M (bbox, C) vs GSOM TAVG raw (UP long-record, C) | 1981-2025 | 40 | 0.922 | 0.509, 0.492 | 0.017 | 0.49, 0.456 | C/decade |
| POWER T2M (bbox, C) vs GHCN-Daily tmean raw (UP long-record, C) | 1981-2025 | 45 | 0.94 | 0.553, 0.617 | -0.064 | 0.535, 0.607 | C/decade |
| GSOM TAVG raw vs GHCN-Daily tmean raw | 1981-2025 | 40 | 0.906 | 0.492, 0.524 | -0.032 | 0.456, 0.523 | C/decade |
| GSOM TAVG anomaly (1991-2020) vs GHCN-Daily T anomaly (1991-2020) | 1981-2025 | 40 | 0.93 | 0.563, 0.57 | -0.008 | 0.528, 0.573 | C/decade |
| POWER T2M 2001-2025 vs MODIS LST Day 2001-2025 | 2001-2025 | 25 | 0.846 | 0.797, 0.823 | -0.025 | 0.784, 0.897 | C/decade |
| POWER T2M 2001-2025 vs MODIS LST Night 2001-2025 | 2001-2025 | 25 | 0.961 | 0.797, 0.869 | -0.072 | 0.784, 0.875 | C/decade |
| MODIS LST Day vs MODIS LST Night | 2001-2025 | 25 | 0.785 | 0.823, 0.869 | -0.046 | 0.897, 0.875 | C/decade |
| GSOM PRCP anomaly vs GHCN-Daily P anomaly | 1981-2024 | 43 | 0.891 | 15.541, 8.961 | 6.579 | 8.518, 11.352 | mm/decade |
| GSOM PRCP anomaly 1981-2000 vs GHCN-Daily P anomaly 1981-2000 | 1981-2000 | 20 | 0.891 | 136.84, 92.467 | 44.373 | 120.787, 87.31 | mm/decade |
| POWER PRECTOTCORR anomaly vs 1991-2020 vs GSOM PRCP anomaly | 1981-2024 | 43 | 0.453 | 14.594, 15.541 | -0.946 | 16.882, 8.518 | mm/decade |
| POWER PRECTOTCORR anomaly vs 1991-2020 vs GHCN-Daily P anomaly | 1981-2024 | 44 | 0.532 | 17.232, 15.572 | 1.66 | 20.392, 14.091 | mm/decade |

**How to read this.** Air-temperature sources should agree closely on year-to-year anomalies; a high *r* with a slightly different slope is expected because the bbox includes sea and neighbours and because GSOM thins after 2012 and skips 2020-2024. LST is a different physical quantity: daytime LST is warmer than 2 m air, but the *trend* over 2001-2025 should be compared with POWER T2M over **that same window**. Precipitation agreement is weaker and is further limited by the post-2000 station-coverage collapse. On 1981-2000, GSOM vs GHCN PRCP-anomaly *r* is 0.891 (n=20) — keep *r* as the agreement metric. Do not present the 136.84 / 92.47 mm/decade OLS slopes as a preferred climate rate: they are a start-end effect (GSOM anomalies are -178 to -311 mm in 1981-1983 and much less dry later) and are about nine times the 1981-2024 GSOM slope of 15.541 mm/decade. A second table trap: GHCN OLS is 8.961 mm/decade on the GSOM-overlap (n=43, 2021 dropped because GSOM has no 2021) but 15.572 mm/decade on the full 1981-2024 GHCN series (n=44). Dropping only 2021 accounts for the whole difference, not two different products.

## 2. Global size estimate

Rough storage if we pulled each dataset **globally**. Figures are documented catalog, directory, or CMR sizes, or a stated scale-up of our real POWER files. CMR queries were run on 14 November 2026. MB in CMR UMM are treated as 10^6-byte megabytes when converting to GB.

| Dataset | Basis (cited) | Assumption | Global estimate | Ukraine extract we have |
|---|---|---|---:|---|
| MOD13C2.061 monthly VI CMG, Feb 2000-Oct 2026 | Earthdata catalog Dataset Size **98.1 MB**/granule; CMR hits **321** (matches our 321 months). README Harmony test: unsubsetted global HDF **101.30 MiB**. | 321 x 98.1 MB | 31.49 GB (or 31.76 GiB using the measured HDF) | DAP4 bbox subsets + 4 sample nc4 (1.98 MiB) |
| MOD11C3.061 monthly LST CMG, same period | Earthdata catalog **70 MB**/granule; CMR hits **321**. | 321 x 70 MB | 22.47 GB | included in the same folder |
| MOD11A2.061 8-day 1 km LST (not yet downloaded) | Earthdata catalog typical granule **3.6 MB**; live CMR hits **388,853**. A 400-granule CMR UMM sample had median **1.78 MB**, mean **2.53 MB**, max 9.59 MB. | Prefer sample mean; also show catalog typical. | **983.80 GB** at 2.53 MB mean, or 1.40 TB at 3.6 MB | none yet (AppEEARS now accessible, Earthdata login verified 14 Nov 2026 12:40 Europe/Kiev; rasters not yet pulled) |
| NASA POWER monthly (the 7 parameters we have, 1981/1984-2025, global grid) | Our real CSV sizes (11.08 MiB meteorology, 723.7 KiB solar) scaled by cell count. MERRA-2 0.5x0.625 deg = 207,360 cells vs our 464; CERES 1deg = 64,800 vs our 144. | Same CSV layout, no extra parameters. | **5.15 GiB** | 11.79 MiB |
| GHCN-Daily, all stations | NCEI directory https://www.ncei.noaa.gov/pub/data/ghcn/daily/ : `ghcnd_all.tar.gz` is **3,826,010,800 bytes** (dated 2026-11-12). | Use the official tarball, not the old ~5 TB climate-mirror figure (that included a duplicated superghcnd tree). | **3.56 GiB** | 28 station files + inventories (23.21 MiB) |
| NOAA GSOM (global monthly station summaries) | No single published archive size was found. Our extract is 8.43 MiB for 204 UP stations (111,281 station-months). | A global figure is **not estimated** rather than inventing a station count. | unknown (not invented) | 8.43 MiB |
| SWOT L2 HR RiverSP Reach, Version D, global | Live CMR hits **73,308**. UMM sizes on a 200-granule sample: min 0.23 MB, median **2.25 MB**, mean **3.05 MB**, max 17.6 MB. Our two sample zips are 2.0 MB and 4.08 MB. | 73,308 x sample mean (continent files vary a lot). | **223.59 GB** (median would be 164.94 GB) | two sample granules + Hydrocron (12.87 MiB) |
| MERRA-2 M2TMNXSLV monthly (now accessible, not yet pulled) | CMR hits **561**; UMM sizes on 20 granules ~**51.7 MB** each (range 51.6-51.9 MB). | 561 x 51.75 MB (native GES DISC files, 1980-present). | **29.03 GB** | none yet |
| GLDAS_NOAH025_M 2.1 monthly (now accessible, not yet pulled) | CMR hits **319**; UMM and the GES DISC directory listing for 2024 both show **~24 MB**/month. | 319 x 24 MB, Jan 2000-present. | **7.66 GB** | none yet |
| GPM IMERG monthly 3IMERGM V07 (GES DISC approved, not yet pulled) | CMR hits **333**; UMM sample mean **17.3 MB** (median 17.5). The 2023 IMERG technical documentation said “about 30 MB”; we use live CMR sizes. | 333 x 17.3 MB. | **5.76 GB** | none yet |
| GRACE/GRACE-FO JPL mascon CRI RL06.3 v04 (not downloaded) | CMR: **1** granule, UMM size **44.22 MB** for `GRCTellus.JPL.200204_202609.GLO.RL06.3M.MSCNv04CRI.nc` (Apr 2002-Sep 2026). Non-CRI sibling is 38.98 MB. | The whole record is one NetCDF. | **44 MB** | none |
| AIRS3STM 7.0 monthly (GES DISC approved, not yet pulled) | CMR version 7.0 hits **290**; UMM mean ~**200 MB**. | 290 x 200 MB. | 58.00 GB | none yet |
| OMI OMNO2d 004 daily (GES DISC approved, not yet pulled) | CMR version 004 hits **8,028**; UMM median ~**14.4 MB**. | Daily product; 8028 x 14.4 MB. Prefer a monthly composite for trends. | 115.60 GB | none yet |

**Practical reading.** A global analysis-ready kit is still modest if we stick to monthly CMG MODIS (~54 GB for VI+LST), POWER-like monthly meteorology (a few GB as CSV), GHCN-Daily (3.8 GB compressed), GLDAS monthly (~7.7 GB), MERRA-2 SLV monthly (~29 GB), and GRACE (44 MB). The things that blow up are **1 km MOD11A2** (~1 TB) and **global SWOT RiverSP** (order 200 GB). Prefer Hydrocron or a subsetted RiverSP extract over a global shapefile haul.

## 3. What we don’t need

Out of scope for data analysis of climate trends, or redundant with something we already have. This is not a request to delete files from the shared disk.

| Item | Why we don’t need it for the analysis |
|---|---|
| `swot_sample/` shapefiles, zips, and pass-540 preview PNG | Single-pass snapshots. Pass 012 has **zero** Ukraine-bbox reaches. Hydrocron is the SWOT time series. |
| Duplicate RiverSP zips once `extract/` and `extract_540/` exist | The unzipped shapefiles are enough; the zips only duplicate those bytes (~6 MB). |
| SWOT Hydrocron as a *climate-trend* input | 3.3-year record, ice/dark filters, fill-only discharge. Kherson is not a confirmed Kakhovka step (Apr-Jun -0.006 m, MW p=0.687; month FE + step HAC p=0.53). Keep Hydrocron only as a “too short for climate inference” methods demo. |
| Empty Hydrocron reach CSVs (7 files, header only) | Those SWORD IDs are not in the default RiverSP-D collection. |
| Most SWOT RiverSP discharge columns (`dschg_*`) and `ice_dyn_f` | Entirely fill in the Hydrocron extract; mostly fill in the sample shapefile. |
| AppEEARS catalog JSON/CSV (193 products) | Metadata only. The CMG variables we needed were fetched via LP DAAC. |
| SWOT CMR granule-count JSON, once size guidance is recorded | Metadata for planning downloads, not a variable to analyse. |
| POWER `ANN` column for T2M_MAX and T2M_MIN | Annual extreme, not the annual mean. |
| Unused POWER parameters we never downloaded | Out of scope until a new science question needs them. |
| `knmi_climexp/` (empty) and `login_required/` (empty) | Placeholders. The useful content is `login_required.md`. |
| `_staging/legacy/` scripts | Retired; they used unit-index Sen slopes and would overwrite revised results. Do not run. |
| `charts/` | Visualization belongs to the other team. |
| `ghcnd-stations.txt` as a data series | It is the global station inventory (useful metadata), not a climate time series. |
| GSOM PRCP after ~2000 as a regional precipitation trend | Coverage collapse; a naive all-station series is not a climate signal. |
| Partial year 2026 in GSOM, GHCN, MODIS, SWOT | Incomplete year; already excluded from climate annual trends. |
| Native MERRA-2 T2M / PRECTOTCORR as a *replacement* for POWER | POWER already provides those for this bbox. Pull native MERRA-2 only if we need fields POWER does not have. GLDAS soil moisture *is* new and worth pulling. |
| RADARSAT / Geo.ca | Not downloaded; not needed for this trend analysis. |

## 4. Preprocessing plan

Ordered checklist for anyone computing trends from these extracts. It follows the revised methods in the sample README, plus the spatial and splice issues the review already flagged.

1. **Decide the domain.** Replace the rectangular bbox with a Ukraine polygon (and a land mask for MODIS/POWER) before recomputing area means. Until then, disclose that the box is ~2x the country and includes sea and neighbours. If the bbox is retained, area-weight grid cells by `cos(latitude)` (a check on unweighted POWER T2M changed the 1981-2025 OLS rate only from +0.553 to +0.554 C/decade, but the polygon still matters for interpretation).
2. **Partial years are not annual values.** An annual mean needs 12/12 months, so 2026 and MODIS 2000 (starts in February) have no annual value; they are listed in `missing_years`, not silently dropped, and complete years are never dropped (SKILL.md rule 9). Monthly series keep every month.
3. **Apply fill values and scale factors before any statistic.** POWER: treat `-999` as missing. MODIS VI: `_FillValue=-3000`, valid range -2000 to 10000, then `raw/10000` (do not trust auto-scale: the file’s `scale_factor` attr is 10000). MODIS LST: `_FillValue=0`, valid range 7500-65535, then `raw x 0.02` (Kelvin). SWOT: mask `-999`, `-999999999999`, and implausible `|x|` (use >=1e11 for sentinels; also inspect uncertainty fields for `|x|>1e6`). GSOM: empty cells are missing (no sentinels in this extract). GHCN-Daily: convert tenths (TMAX/TMIN/TAVG/PRCP) and drop rows with a non-blank **QFLAG**.
4. **QC beyond fills.** MODIS: current series are fill/range only — if 1 km LST arrives, use QC bits and treat cloud gaps as missing, not zeros. SWOT: drop `reach_q>2`, `ice_clim_f>=1`, `dark_frac>0.5`; do not use `ice_dyn_f` (all fill). GHCN: do not treat MFLAG/SFLAG as failures. GSOM: no flag columns were downloaded.
5. **Units and flux conversions.** QV2M is **g/kg**, not kg/kg. PRECTOTCORR is mm/day — multiply by days in the month and sum to mm/year. LST comparisons with air temperature should be in C over the **same years**. Never use POWER `ANN` for T2M_MAX/T2M_MIN. When GES DISC files are pulled: GPM IMERG Final monthly (3IMERGM V07) precipitation is a **mean rate in mm/hr**, not mm or mm/day — monthly total is `value × hours in that calendar month` (about 672–744). Use the **Final** run for climate trends, not Early/Late. MERRA-2 `M2TMNXFLX` and GLDAS precip, ET, and runoff are typically **kg m⁻² s⁻¹**; convert to mm/day as `× 86400`. GLDAS soil moisture in kg m⁻² (≈ mm) is already a storage and does not use that conversion.
6. **Temporal aggregation.** Prefer **annual** or meteorological-season series so the seasonal cycle does not dominate the test. Build DJF from complete Dec-Feb winters only. For SWOT, monthly means are for the methods demo, not a 30-year trend. Say whether each annual value is the unweighted mean of 12 monthly means or a day-weighted mean. POWER `ANN` is essentially day-weighted; the approved T2M series is the unweighted month-mean (1981-2025 OLS +0.553 vs +0.551 °C/decade).
7. **Anomalies.** For station temperature (and precip where used), take anomalies versus each station’s **1991-2020** mean, then average **long-record stations only**. For MODIS and POWER-vs-LST, use a common 2001-2025 window rather than mixing with 1981-2025 air-temperature anomalies.
8. **Station selection.** Declare the long-record rule up front. Disclose GSOM TAVG thinning (9 stations to 2012, 4 in 2013-2019 and 2025, **none in 2020-2024**) and that GSOM/GHCN PRCP in the 2020s can fall to n=2. Do not treat those years as a regional mean.
9. **Solar splice.** Official POWER documentation places GEWEX SRB at 1984-01-01–2000-12-31 and CERES SYN1deg from 2001-01-01, and (in Data v10) applies quantile mapping to pre-2001 values. The on-disk solar header only names CERES SYN1deg and does not state a POWER data version, so this extract has **not been confirmed as Data v10**. For `ALLSKY_SFC_SW_DWN`, either restrict trends to **2001-2025** (CERES only) or test a breakpoint at 2001. Do not treat the pre-2001 segment as an unadjusted raw SRB splice, and do not headline a 1984-2025 slope without that check. Data do not begin in 1981.
10. **Homogenization / breakpoints.** GSOM/GHCN are not homogenized in this extract. At least flag known network changes (post-2012 thinning, 2020-2024 hole, war-related 2022 gaps). Kherson is **not a confirmed Kakhovka step** (Apr-Jun difference -0.006 m, Mann-Whitney p=0.687; month FE + step -0.031 m, HAC lag-3 p=0.530); still do not fit a linear climate trend there (too short and too seasonal). For GRACE/GRACE-FO JPL mascons, the native record has an ~11-month mission gap (GRACE ends July 2017, GRACE-FO starts June 2018; **August 2017–May 2018** are missing). Do not interpolate that gap into a trend without saying so. A formal breakpoint test is desirable if time allows; it is not already in the tables.
11. **Trend tests.** Use time-aware Theil-Sen (against calendar year, not unit index). Report OLS with AR(1)-inflated errors and Newey-West HAC (lag 1 annual, lag 3 monthly), plus Hamed-Rao MK at **lag=3** (not the all-lag default) and TFPW. These are **sensitivity** columns only. The primary test is repo MK Yue-Wang (ADR-002/ADR-003) with the OLS n_eff cross-check; if they disagree, use the more conservative verdict (SKILL.md:26-28). Label series that are too short for a climate-trend claim (including SWOT’s 3.3 years) **“too short for climate inference.”**
12. **Multiple testing.** Use the pre-declared primary family and the full family sizes already stored on `trend_summary.csv`, with Bonferroni and Benjamini-Hochberg flags. Do not call borderline seasonal tests “significant” in the headline.
13. **Cross-source check.** For any headline (especially temperature), show POWER, GSOM (with the gap disclosed), and GHCN together; for 2001-2025 also show MODIS LST. If they disagree, do not average them silently.
14. **New GES DISC variables now on disk, and AppEEARS when pulled.** MERRA-2, GLDAS 2.0/2.1, IMERG, and AIRS are pulled; apply the same fill, scale, QC, annual-aggregation, anomaly, and autocorrelation-aware tests, plus the flux conversions in item 5 (IMERG is already stored as mm/month; MERRA-2 precip and GLDAS Evap are already converted). Use **GLDAS 2.1** from 2000 onward and 2.0 only to extend before 2000; 2.2 is not in the extract. Do not use GLDAS Qs_mm until the unit fix is finished. Native MERRA-2 overlaps POWER T2M/PRECTOTCORR. AppEEARS is now accessible (Earthdata login verified 14 Nov 2026, 12:40 Europe/Kiev) but 1 km rasters are not yet pulled. For a future 1 km urban-heat demo, define urban vs rural pixels from MCD12Q1, prefer night LST, and test the **urban-rural difference series** before claiming an intensifying UHI. Keep Terra and Aqua as separate series if MODIS is expanded (the current CMG extract is Terra-only). For OMI OMNO2d, the row anomaly begins in 2007; use `XTrackQualityFlags` and do not treat unflagged row-anomaly pixels as a NO2 trend.

## Dataset DOIs

See the DOI table in `data_dictionary.md`. The same identifiers are in the `doi` column of `data_dictionary.csv`.
