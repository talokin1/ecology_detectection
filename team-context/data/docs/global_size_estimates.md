# Global size estimates and first-pass fetch

Compiled 14 November 2026, Europe/Kiev, for NASA Space Apps 2026 (data analysis only). Ukraine remains a cut-out of **global** products. This refines `team-context/data/docs/data_overview_extras.md` with live CMR, HTTP `Content-Length`, and directory-listing sizes checked this turn. Credentials were used only as an `Authorization: Bearer` header and are not stored in this folder.

**Units.** GB means 10^9 bytes (SI). GiB means 1024^3 bytes and is noted only when a publisher quotes that unit. “Slim” means the variables we already use, at monthly resolution, in compressed NetCDF-4 / gzip / the official compressed archive.

**Disk.** `/workspace` is on a filesystem whose `statvfs` size is 136,793,763,840 bytes (**127.40 GiB**, **136.79 GB**). The rule is to leave at least 20% free (**25.48 GiB** / **27.36 GB**). After the critique follow-up fetch, `df` reports **66 GiB available** (70,469,181,440 bytes = **65.63 GiB** / **70.47 GB**), **49% used**. That is well above the 20% floor. (An earlier wording called `df`’s “75G” free “75 GB”; that figure was **75 GiB ≈ 80.0 GB**. This document uses GB for 10⁹ bytes and GiB for 1024³ bytes.)

## How the figures were obtained

| Tag | Meaning |
|---|---|
| Measured (HEAD) | HTTP `Content-Length` (or a `Content-Range`) on the official file this turn |
| Measured (listing) | Sum of sizes in an official directory listing this turn |
| Measured (CMR, all N) | Sum of granule `SizeInBytes` (or Size × unit) over every granule in the collection |
| Measured (CMR sample) | Mean of a CMR granule-size sample, times `CMR-Hits` |
| Measured (on disk) | File size on this machine, after a complete download (GRACE also matches the official MD5) |
| Estimated (slim probe × N) | Used only for planning. Finished NASA slim sizes in the table are **measured on disk** after the complete fetch |
| Estimated (scale-up) | Measured Ukraine files scaled by official global cell counts (NASA POWER) |
| Estimated (grid math / samples) | Documented grid × years, or a mean of sampled daily files × day count |

One-month DAP4 probes (used for planning) are in `/tmp/slim_probes/`. The complete slim monthly archives are under `$GLOBAL_DATA/`.

## Size table

| Dataset | Resolution | Record (official / CMR this turn) | Full global size (native, all variables as distributed) | Slim global size (variables we use, monthly, compressed) | Basis | Fetch status | Path |
|---|---|---|---:|---:|---|---|---|
| NASA POWER monthly (7 params we use) | MERRA-2 0.5°×0.625° meteorology; CERES 1° solar | 1981–2025 (solar from 1984; treat pre-2001 solar as a splice) | No single official dump. A full-parameter monthly CSV extract would be several times the slim figure (order 20–40 GB if ~30–80 POWER parameters were requested); not measured | **5.54 GB** (5.16 GiB) | Estimated (scale-up of 12.36 MB of measured Ukraine CSVs: 464 MERRA-2 cells → 207,936; 144 CERES cells → 64,800). Six meteorology parameters 5.21 GB + solar 0.33 GB | **Skipped this pass** — API is regional/chunked, no one-file archive | Ukraine CSVs in `$UKRAINE_SAMPLES/nasa_power/` |
| NOAA GSOM (all stations) | Station monthly summaries | Station-dependent; official `gsom-latest.tar.gz` dated 6 Nov 2026 | **1.51 GB** (1,511,537,790 bytes) | ≤ 1.51 GB (the tarball is already monthly; a TAVG/TMAX/TMIN/PRCP-only cut would be smaller, not measured) | Measured (HEAD and listing) | **Skipped this pass** — useful, but not in the first monthly-grid queue | Official URL: `https://www.ncei.noaa.gov/data/global-summary-of-the-month/archive/gsom-latest.tar.gz` |
| NOAA GHCN-Daily (all stations) | Station daily | Current official tarball (HEAD 14 Nov 2026) | **3.83 GB** (3,825,867,971 bytes) for `ghcnd_all.tar.gz` | A monthly extract of TMAX/TMIN/TAVG/PRCP is essentially GSOM / GHCNm, not a second 3.8 GB grid. GHCNm TAVG only is 44.2 MB (`ghcnm.tavg.latest.qcf.tar.gz`, listing 14 Nov 2026) | Measured (HEAD) | **Skipped this pass** (requested unless small; 3.83 GB would fit, but daily full is not needed for the monthly kit) | `https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd_all.tar.gz` |
| MODIS MOD13C2.061 monthly VI CMG | 0.05° global | Feb 2000–Oct 2026, **321** months | **31.53 GB** | **5.77 GB** (5,771,738,931 bytes; NDVI + EVI, 321 files) | Full: measured (CMR, all 321). Slim: measured (on disk) | **Done** | `$GLOBAL_DATA/mod13c2_slim/` |
| MODIS MOD11C3.061 monthly LST CMG | 0.05° global | Feb 2000–Oct 2026, **321** months | **22.47 GB** | **5.24 GB** (5,238,693,688 bytes; LST_Day_CMG + LST_Night_CMG, 321 files) | Full: measured (CMR, all 321). Slim: measured (on disk) | **Done** | `$GLOBAL_DATA/mod11c3_slim/` |
| MODIS MOD13C2.061 QC (added after review) | 0.05° global | Feb 2000–Oct 2026, **321** months | Included in the 31.53 GB native VI files | **1.24 GB** (1,239,015,558 bytes; `CMG_0_05_Deg_Monthly_VI_Quality` + `CMG_0_05_Deg_Monthly_pixel_reliability`, 321 files) | Slim: measured (on disk) | **Done** | `$GLOBAL_DATA/mod13c2_qc/` |
| MODIS MOD11C3.061 QC + clear-sky (added after review) | 0.05° global | Feb 2000–Oct 2026, **321** months | Included in the 22.47 GB native LST files | **5.30 GB** (5,303,080,207 bytes; `QC_Day`, `QC_Night`, `Clear_sky_days`, `Clear_sky_nights`, 321 files). Clear-sky was cheap enough to include (the first-month probe under-ran later months; the full set is still well under the disk floor) | Slim: measured (on disk) | **Done** | `$GLOBAL_DATA/mod11c3_qc/` |
| MODIS MOD11A2.061 8-day 1 km LST | 1 km SIN tiles | 2000–present; **388,853** granules | **982.3 GB** (CMR sample mean 2.526 MB × hits; catalog “typical 3.6 MB” would be 1.40 TB — we prefer the live sample) | Still huge at 1 km; a monthly mosaic of day/night LST only would remain hundreds of GB | Estimated (CMR sample n=400) | **Skipped this pass** — 1 km, ~1 TB | — |
| MODIS MCD12Q1.061 yearly land cover | 500 m SIN tiles | Yearly; **7,875** granules | **40.81 GB** | Not monthly; a global yearly land-cover stack is still tens of GB | Estimated (CMR sample n=400) | **Skipped this pass** — yearly 500 m tiles, used for Kyiv UHI via AppEEARS rather than a global haul | — |
| SWOT L2 HR RiverSP Version D (reach + node) | Vector, pass-level | Mar 2023–present; **166,444** granules in the combined collection | **1.50 TB** combined (mixed sample). Better split: reach-only **297.7 GB** (73,308 granules, sample n=400); node-only **1.87 TB** (73,288 granules, sample n=400). This revises the earlier ~224 GB figure, which used a smaller hit count and a mixed mean | Hydrocron time series of selected reaches is the slim path (kilobytes to megabytes per basin), not a global shapefile dump | Estimated (CMR sample) | **Skipped this pass** — too large; use Hydrocron, as before | — |
| SWOT Hydrocron | Reach time series API | SWOT era (2023–) | No official global bulk dump | Per-reach JSON/CSV; size is reach-count × ~3 years, typically MB-scale for a country, not a climate-length record | n/a | **Skipped this pass** — already have a Ukraine extract; too short for a climate trend | `$UKRAINE_SAMPLES/swot_hydrocron/` |
| MERRA-2 M2TMNXSLV 5.12.4 monthly | 0.5°×0.625° | Jan 1980–Sep 2026, **561** months | **32.19 GB** | **0.891 GB** (891,108,130 bytes; T2M, QV2M, SLP, 561 files) | Full: measured (CMR, all 561). Slim: measured (on disk) | **Done** | `$GLOBAL_DATA/merra2_slv_slim/` |
| MERRA-2 M2TMNXFLX 5.12.4 monthly | 0.5°×0.625° | Jan 1980–Sep 2026, **561** months | **32.11 GB** | **0.774 GB** (773,787,005 bytes; PRECTOT, PRECTOTCORR, 561 files) | Full: measured (CMR, all 561). Slim: measured (on disk) | **Done** | `$GLOBAL_DATA/merra2_flx_slim/` |
| MERRA-2 M2TMNXSLV U10M + V10M (added after review) | 0.5°×0.625° | Jan 1980–Sep 2026, **561** months | Included in the 32.19 GB native SLV files | **0.786 GB** (786,238,152 bytes, 561 files) | Slim: measured (on disk) | **Done** | `$GLOBAL_DATA/merra2_slv_wind/` |
| MERRA-2 M2SMNXSLV T2MMAX + T2MMIN (added after review) | 0.5°×0.625° | Jan 1980–Sep 2026, **561** months | Monthly **statistics** collection `M2SMNXSLV` 5.12.4 (C1276812828-GES_DISC), not `M2TMNXSLV`. T2MMAX/T2MMIN are not in the time-averaged SLV files. | **0.583 GB** (583,006,644 bytes, 561 files) | Slim: measured (on disk) | **Done** | `$GLOBAL_DATA/merra2_statm_extremes/` |
| GLDAS NOAH 0.25° monthly 2.0 | 0.25° | Jan 1948–Dec 2014, **804** months | **19.08 GB** | **3.93 GB** (3,929,728,082 bytes; SoilMoi0_10cm, RootMoist, Evap, Qs, Qsb, SWE, Tair, 804 files) | Full native: measured (CMR, **800 of 804** granules; the total may be a few tenths of a percent low). Slim: measured (on disk, complete **804/804** months) | **Done** | `$GLOBAL_DATA/gldas20_slim/` |
| GLDAS NOAH 0.25° monthly 2.1 | 0.25° | Jan 2000–Jul 2026, **319** months | **7.64 GB** | **1.58 GB** (1,581,824,378 bytes; same seven variables, 319 files) | Full: measured (CMR, all 319). Slim: measured (on disk) | **Done** | `$GLOBAL_DATA/gldas21_slim/` |
| GLDAS 2.0 Rainf_f_tavg + Snowf_tavg (added after review) | 0.25° | Jan 1948–Dec 2014, **804** months | Included in the 19.08 GB native 2.0 files | **0.997 GB** (996,732,057 bytes, 804 files) | Slim: measured (on disk, 804/804) | **Done** | `$GLOBAL_DATA/gldas20_rainf/` |
| GLDAS 2.1 Rainf_f_tavg + Snowf_tavg (added after review) | 0.25° | Jan 2000–Jul 2026, **319** months | Included in the 7.64 GB native 2.1 files | **0.380 GB** (379,664,105 bytes, 319 files) | Slim: measured (on disk) | **Done** | `$GLOBAL_DATA/gldas21_rainf/` |
| GPM IMERG V07 Final monthly (3IMERGM) | 0.1° | Jan 1998–Sep 2025, **333** months (official collection; the Ukraine cut started 2000) | **5.94 GB** | **2.27 GB** (2,268,586,131 bytes; precipitation only, 333 files) | Full: measured (CMR, all 333). Slim: measured (on disk) | **Done** | `$GLOBAL_DATA/gpm_imerg_slim/` |
| AIRS 3STM 7.0 monthly | 1° | Sep 2002–Oct 2026, **290** months | **57.92 GB** | **0.241 GB** (241,075,185 bytes; SurfAirTemp and TotH2OVap, ascending + descending, 290 files). Variable subsetting saves ~240× | Full: measured (CMR, all 290). Slim: measured (on disk) | **Done** | `$GLOBAL_DATA/airs3stm_slim/` |
| OMI OMNO2d 004 daily | 0.25° | 1 Oct 2004 onward, **8,028** days | **109.2 GB** | A monthly composite of the two tropospheric NO2 columns would be much smaller (order 1–2 GB, not measured). We would not store 8,028 global daily files | Estimated (CMR sample n=400, mean 13.6 MB) | **Skipped this pass** — daily native is too large; prefer monthly composites later | Ukraine extract in `$UKRAINE_SAMPLES/omi/` |
| OMI OMTO3e 003 daily | 0.25° | 1 Oct 2004 onward, **8,035** days | **31.64 GB** | Same as OMNO2d: monthly ozone composites would be far smaller (not measured) | Estimated (CMR sample n=400, mean 3.94 MB) | **Skipped this pass** — daily native is large | — |
| GRACE/GRACE-FO JPL mascon CRI RL06.3Mv04 | 0.5° grid, 3° native mascons | Apr 2002–Sep 2026, 261 months, **1** granule | **46.37 MB** (46,365,171 bytes) | **46.37 MB** (the official file is already the monthly global product we use) | Measured (HEAD, CMR, on disk). MD5 `1567b9401ec2a704aab16598fcce5e70` verified | **Done** | `$GLOBAL_DATA/grace/GRCTellus.JPL.200204_202609.GLO.RL06.3M.MSCNv04CRI.nc` |
| GISTEMP v4 2° LOTI (1200 km) | 2° | Jan 1880–Oct 2026 | **25.89 MB** (25,885,943 bytes) gzip NetCDF | **25.89 MB** (single field; official file kept) | Measured (HEAD and on disk) | **Done** | `$GLOBAL_DATA/gistemp/gistemp1200_GHCNv4_ERSSTv5.nc.gz` plus official global/zonal CSVs |
| HadCRUT5.2.0.0 analysis ensemble mean | 5° | Jan 1850–Sep 2026 | **32.86 MB** (32,860,971 bytes). The 200-member ensemble (if needed for uncertainty) would be ~200×, not fetched | **32.86 MB** | Measured (HEAD on the UEA copy; on-disk file matches) | **Done** | `$GLOBAL_DATA/hadcrut5/HadCRUT.5.2.0.0.analysis.anomalies.ensemble_mean.nc` plus official summary CSVs |
| Berkeley Earth 1° land TAVG | 1° land | Jan 1750–Dec 2024 | **199.0 MB** (198,958,040 bytes) for Complete_TAVG_LatLong1.nc. Optional: TMAX 157.6 MB, TMIN 158.6 MB, land+ocean 1° 454.6 MB, equal-area 119.7 MB (all HEAD this turn) | **199.0 MB** (TAVG land is the series we use; TMAX/TMIN not fetched yet) | Measured (HEAD and on disk) | **Done** (TAVG land) | `$GLOBAL_DATA/berkeley_earth/Complete_TAVG_LatLong1.nc` |
| CRU TS v4.10 (and CRU-CY) | 0.5° land (TS); country averages (CY) | 1901–2025 | **3.65 GB** gzip for the 10 official grids (tmp, pre, tmn, tmx, pet, dtr, vap, wet, cld, frs), all HEAD this turn | **1.53 GB** for tmp+tmn+tmx+pre (1,525,146,772 bytes). CRU-CY country files are only tens of MB in total | Measured (HEAD) | **Skipped this pass** — GHCN-family, lower independence priority; sizes are small enough to pull later | Ukraine CY already in `$UKRAINE_SAMPLES/extra/cru_cy/` |
| GPCC Precipitation Analysis Monthly v2025 | 1° (also 0.25 / 0.5 / 2.5°) | Jan 1891–Aug 2026 | **0.444 GB** at 1° (443,882,757 bytes, 47 official chunks). Other resolutions, from the same style of listing: 0.5° **1.48 GB**, 0.25° **5.57 GB**, 2.5° **97.3 MB** | **0.444 GB** at 1° (the official 1° set is already monthly precipitation + gauge-count fields, gzip NetCDF) | Measured (listing and on disk, every 1° file size-checked) | **Done** (1°) | `$GLOBAL_DATA/gpcc_v2025_1deg/` |
| ERA5 monthly (used fields) | 0.25° | 1940–present (ERA5 final through Jun 2026; ERA5T lags ~days) | Official CDS/ECMWF archive is multi-petabyte (hourly, all variables, all levels) — do not pull globally | Order **8–13 GB** compressed for monthly t2m, total precipitation, and swvl1–4, 1940–2026 (26.0 GB uncompressed grid math: 721×1440×4 bytes×6 vars×12×87 years) | Full: cited. Slim: estimated (grid math) | **Skipped this pass** — no CDS login; the public ARCO store is hourly `chunk-1` and is a poor way to build a global monthly climatology | Ukraine 1940–1951 method sample in `$UKRAINE_SAMPLES/extra/era5_arco/` |
| ERA5-Land monthly (used fields) | 0.1° land | 1950–present | Very large as a global hourly archive (CDS) | Order **15–20 GB** compressed for the same six fields, land-only 0.1° (about 42 GB uncompressed) | Estimated (grid math) | **Skipped this pass** — CDS login required; not in the no-login ARCO bucket | — |
| CHIRPS v3.0 monthly | 0.05°, 60°S–60°N | **549 months, January 1981–September 2026** (complete; no internal gaps). The official monthly NetCDF does **not** include October 2026. The earlier COG-based Ukraine extract ran through October 2026 (550 months) and **diverges from this NetCDF from 2025-10 onward** (e.g. 2026-02 differs by 15.07 mm). Do not mix the two archives for 2025-10 and later. | **8.96 GB** (8,960,342,547 bytes) for the official monthly NetCDF. Monthly COGs are a separate archive (~30.14 MB each; about 16.6 GB for the 550-file COG tree through 2026-10) | **8.96 GB** (the official monthly NetCDF is already one precipitation field, mm/month) | Measured (HEAD and on disk) | **Done** | `$GLOBAL_DATA/chirps_v3/chirps-v3.0.monthly.nc` |
| ESA CCI SM COMBINED v09.2 daily | 0.25° | 1 Nov 1978–31 Dec 2024, **16,863** days | **27.5 GB** | A monthly mean of `sm` only would be about 1–2 GB compressed (0.25° × 554 months; not measured) | Estimated (mean of 25 measured daily HEAD sizes, mostly 1 June plus start/end, × 16,863 days). Winter files are smaller (2024-12-31 was 1.46 MB vs 2.33 MB on 2024-06-01), so 27.5 GB may be a slight overestimate | **Skipped this pass** — daily native is larger than the monthly kit; monthly composites can be built later via OPeNDAP | Partial Ukraine cut in `$UKRAINE_SAMPLES/extra/cci_sm/` |

## Totals

**Monthly slim kit now on disk under `$GLOBAL_DATA/` (39.69 GB).**

| Group | Slim size | Status |
|---|---:|---|
| GRACE + GISTEMP + HadCRUT5 + Berkeley TAVG 1° + GPCC 1° | **0.75 GB** | Done |
| NASA monthly slim (original variables): MERRA-2 SLV+FLX, GLDAS 2.0+2.1, IMERG, AIRS, MOD13C2, MOD11C3 | **20.70 GB** (3,510 files, 0 failures) | Done |
| CHIRPS v3 official monthly NetCDF (549 months, 1981-01–2026-09) | **8.96 GB** | Done |
| Added after review: MODIS QC (+ clear-sky), GLDAS Rainf+Snowf, MERRA-2 U10M/V10M, M2SMNXSLV T2MMAX/T2MMIN | **9.29 GB** (2,887 files, 0 failures) | Done |
| **On disk now** | **39.69 GB** (39,692,810,946 bytes) | `$GLOBAL_DATA/` |
| NASA POWER 7-parameter global CSVs (not fetched) | **5.54 GB** estimated | Skipped (chunked API) |
| Optional later: CRU TS tmp+tmn+tmx+pre, GSOM tarball, GHCN-Daily tarball | 1.53 + 1.51 + 3.83 = **6.87 GB** | Skipped this pass |

After this follow-up, the filesystem has **65.63 GiB** (70.47 GB) free, **49% used** — still well above the 20% floor of 25.48 GiB / 27.36 GB.

**Native full-archive totals we are not pulling:** MOD11A2 ~982 GB, SWOT RiverSP reach 298 GB + nodes 1.87 TB, OMI daily ~141 GB combined, MCD12Q1 ~41 GB, ERA5 official multi-PB, CCI SM daily ~27.5 GB, plus the unsubsetted MERRA-2 / GLDAS / AIRS / MODIS CMG natives (~200 GB together). Variable subsetting is what makes the NASA monthly kit practical: AIRS falls from 57.9 GB to 0.24 GB; the two MERRA-2 tavg collections’ used fields (T2M/QV2M/SLP + PRECTOT/PRECTOTCORR + U10M/V10M) are 2.45 GB slim; MODIS CMG VI+LST+QC+clear-sky is 17.54 GB slim versus 54.0 GB native.

Do **not** join GLDAS 2.0 and 2.1 into one series (they differ by about +0.5 °C on the overlap). Do **not** treat POWER meteorology as independent of MERRA-2. IMERG Final is gauge-calibrated with GPCC. The GISTEMP 1200 km and HadCRUT5 files are land–ocean blends. Do **not** mix the CHIRPS official monthly NetCDF with the COG archive from 2025-10 onward.

## Fetch log (this pass)

Original pull finished 14 November 2026, Europe/Kiev, with sizes verified. NASA slim: 3,510/3,510 granules, 0 failures (DAP4, 5 workers). CHIRPS: official NetCDF, `Content-Length` matched (**549 months, January 1981–September 2026**).

Critique follow-up (same day, finished 14:46 Europe/Kiev): 2,887/2,887 extra granules, 0 failures. T2MMAX/T2MMIN were taken from **M2SMNXSLV** (monthly statistics), because they are not in M2TMNXSLV. Clear-sky coverage was included with MOD11C3 QC (5.30 GB for QC+clear-sky together). The 2,245 `.nc4.nc4` filenames on the original MERRA-2 and GLDAS slim files were renamed to `.nc4`.

| Path | Files | Bytes | Notes |
|---|---:|---:|---|
| `$GLOBAL_DATA/grace/` | 1 NetCDF + notes | 46,365,171 (data file) | Official JPL CRI mascon; MD5 `1567b9401ec2a704aab16598fcce5e70` verified (a first copy was truncated and was replaced) |
| `$GLOBAL_DATA/gistemp/` | 1 gzip NetCDF + 4 official CSVs | 25,934,827 | Official 1200 km LOTI file hard-linked from the existing official copy |
| `$GLOBAL_DATA/hadcrut5/` | 1 NetCDF + 2 official CSVs | 33,039,776 | Official 5° ensemble-mean analysis, hard-linked |
| `$GLOBAL_DATA/berkeley_earth/Complete_TAVG_LatLong1.nc` | 1 | 198,958,040 | Land 1° TAVG |
| `$GLOBAL_DATA/gpcc_v2025_1deg/` | 47 | 443,882,757 | Every 1° chunk size-checked against the directory listing |
| `$GLOBAL_DATA/merra2_slv_slim/` | 561 | 891,108,130 | T2M, QV2M, SLP; Jan 1980–Sep 2026 |
| `$GLOBAL_DATA/merra2_flx_slim/` | 561 | 773,787,005 | PRECTOT, PRECTOTCORR; Jan 1980–Sep 2026 |
| `$GLOBAL_DATA/merra2_slv_wind/` | 561 | 786,238,152 | U10M, V10M from M2TMNXSLV; Jan 1980–Sep 2026 |
| `$GLOBAL_DATA/merra2_statm_extremes/` | 561 | 583,006,644 | T2MMAX, T2MMIN from **M2SMNXSLV**; Jan 1980–Sep 2026 |
| `$GLOBAL_DATA/gldas20_slim/` | 804 | 3,929,728,082 | 7 land variables; Jan 1948–Dec 2014 (complete 804/804) |
| `$GLOBAL_DATA/gldas20_rainf/` | 804 | 996,732,057 | Rainf_f_tavg + Snowf_tavg; Jan 1948–Dec 2014 |
| `$GLOBAL_DATA/gldas21_slim/` | 319 | 1,581,824,378 | Same 7 variables; Jan 2000–Jul 2026 |
| `$GLOBAL_DATA/gldas21_rainf/` | 319 | 379,664,105 | Rainf_f_tavg + Snowf_tavg; Jan 2000–Jul 2026 |
| `$GLOBAL_DATA/gpm_imerg_slim/` | 333 | 2,268,586,131 | precipitation; Jan 1998–Sep 2025 |
| `$GLOBAL_DATA/airs3stm_slim/` | 290 | 241,075,185 | SurfAirTemp + TotH2OVap A/D; Sep 2002–Oct 2026 |
| `$GLOBAL_DATA/mod13c2_slim/` | 321 | 5,771,738,931 | NDVI + EVI; Feb 2000–Oct 2026 |
| `$GLOBAL_DATA/mod13c2_qc/` | 321 | 1,239,015,558 | VI_Quality + pixel_reliability; Feb 2000–Oct 2026 |
| `$GLOBAL_DATA/mod11c3_slim/` | 321 | 5,238,693,688 | LST day + night; Feb 2000–Oct 2026 |
| `$GLOBAL_DATA/mod11c3_qc/` | 321 | 5,303,080,207 | QC_Day, QC_Night, Clear_sky_days, Clear_sky_nights; Feb 2000–Oct 2026 |
| `$GLOBAL_DATA/chirps_v3/chirps-v3.0.monthly.nc` | 1 | 8,960,342,547 | Official monthly NetCDF, **549 months, 1981-01–2026-09** |
| **Total** | | **39.69 GB** | |

Progress JSON and scripts: `team-context/data/fetch/`.

**Skipped, and why:** 1 km MOD11A2 (~1 TB), MCD12Q1 (40.8 GB yearly tiles), SWOT RiverSP (298 GB reaches, 1.87 TB nodes), OMI daily (109 + 32 GB), GHCN-Daily full tarball (not needed once we have monthly station summaries), GSOM and CRU TS (small enough later, lower priority than the independent monthly grids), ERA5/ERA5-Land (no CDS login; ARCO is hourly), ESA CCI SM daily (27.5 GB; monthly composites can be built later via OPeNDAP), NASA POWER global (chunked API, no single file). CSR GRACE was not fetched globally (optional). IMERG gauge-relative weighting remains optional and is not in the slim files.


## Notes on revised figures

- MERRA-2 FLX (32.11 GB native, 0.774 GB slim) was missing from the earlier overview, which only had SLV (~29 GB, now 32.19 GB native / 0.891 GB slim on a complete 561-granule CMR sum and a complete download).
- GLDAS 2.0 (804 months, 19.08 GB native, 3.93 GB slim) was also missing; only 2.1 was listed.
- IMERG V07 Final monthly is 333 granules from **1998-01 to 2025-09** (5.94 GB native, 2.27 GB slim), not 2000-only.
- SWOT Version D is much larger than the earlier 224 GB estimate once node files and the full 166,444-granule combined collection are counted. Reach-only is 297.7 GB.
- GSOM is no longer “unknown”: the official `gsom-latest.tar.gz` is 1.51 GB.
- AIRS slim (0.24 GB) is the biggest subsetting win and is now on disk globally.

- After Critique’s review (14 Nov 2026, 14:24 Europe/Kiev), QC, Rainf/Snowf, U10M/V10M, and monthly T2MMAX/T2MMIN were pulled into sibling directories (2,887 files, 0 failures, **9.29 GB**). T2MMAX/T2MMIN come from **M2SMNXSLV** (monthly statistics), not from M2TMNXSLV.
- NASA slim filenames originally had a cosmetic double suffix (`.nc4.nc4`) because the fetcher appended `.nc4` to a producer id that already ended in `.nc4`. All **2,245** affected files (MERRA-2 SLV/FLX and GLDAS 2.0/2.1) were renamed to a single `.nc4`. New pulls use the corrected naming.
- CHIRPS official monthly NetCDF is **549 months, January 1981–September 2026**, not 550 / October 2026. From **2025-10 onward** it diverges from the COG archive used for the earlier Ukraine extract; do not mix the two.
- GLDAS 2.0 **native** size remains “CMR, 800 of 804 granules” and may be a few tenths of a percent low. The slim 2.0 files (original seven variables and the Rainf/Snowf add-on) are complete **804/804**.

