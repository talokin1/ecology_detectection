# Data sources: what is inside, how big, how to use (checked 2026-11-14)

Every number here was read from the source itself on 2026-11-14, by opening the page in the
browser or by calling the API from the terminal. Where something was not checked, it says so.
"Raw size" means uncompressed array size computed from the store's own metadata; the bytes
actually stored and transferred are smaller (about 3.5× smaller for the one variable measured).

## Summary: which source for which job

| Job | Best source | Login | Why |
|---|---|---|---|
| Live regional time series, 1981–now | POWER Zarr on AWS | none | Whole history of a region in ~1 s |
| Quick point series | POWER REST API | none | One HTTP call, JSON |
| Satellite instruments (AIRS, OMI, MODIS atmosphere, GPM) and GLDAS, point series | Giovanni Time Series API | Earthdata token | 867 variables |
| Same, as area averages and maps, by hand | Giovanni web UI | Earthdata login | 2,049 variables; use to validate our numbers |
| MODIS land (NDVI, LST, ET, snow, fire) | AppEEARS | Earthdata login | Queued jobs; offline preparation only |
| Monthly gridded files for offline precompute | GES DISC / LP DAAC via `earthaccess` | Earthdata login | Sizes listed in section 5 |
| Headline validation series | NSIDC Sea Ice Index, NOAA CO2/CH4 CSVs | none | Tiny files with well-known trends |
| Ground stations | NOAA Climate Data Online | free token | Optional ground truth |

---

## 1. NASA POWER Zarr archive on AWS (not on the official list; our main find)

- **Address:** `https://nasa-power.s3.us-west-2.amazonaws.com/` (also `s3://nasa-power`, region us-west-2).
- **Access:** public, anonymous HTTPS. No account, key or token. Version "POWER 10.0.0".
- **Structure:** 7 source folders, 70 Zarr stores. Each store exists twice: `temporal/` (chunked
  so one location's full history is one read; use this for time series and trends) and
  `spatial/` (one chunk per time step for the whole globe; use this for maps of a single date).
  Most also exist in UTC and local-solar-time (`lst`) versions; use `utc`.
- **Metadata:** every variable has `long_name`, `units` and a plain-language `definition`
  attribute. These can feed the "simple definitions of variables" the challenge asks for.

### Stores (UTC versions)

| Folder | What it is | Grid | Step | Time span | Variables | Raw size |
|---|---|---|---|---|---|---|
| `merra2` monthly | MERRA-2 reanalysis meteorology | 0.5°×0.625° (361×576) | month | 1981-01 → 2026-09 | 88 base (472 with per-hour variants) | 231 GB |
| `merra2` annual | same, yearly means | same | year | 1981 → | 88 | 19 GB |
| `merra2` climatology | long-term monthly means | same | 12 months + annual | — | 198 | 6 GB |
| `merra2` daily | same | same | day | 1981-01-01 → | 74 | 1,102 GB |
| `merra2` hourly | same | same | hour | 1981 → | 49 | 17,507 GB |
| `imerg` monthly | GPM IMERG precipitation | 0.1° (1800×3600) | month | 1998-01 → 2026-10 | 1 (`IMERG_PRECTOT`, mm/day) | 10 GB |
| `imerg` daily | same + liquid-phase probability, retrieval count | 0.1° | day | 1998-01-01 → | 3 | 757 GB |
| `imerg` annual / climatology | same | 0.1° | year / 12 months | 1998 → | 1 | 0.8 / 0.3 GB |
| `syn1deg` monthly | CERES SYN1deg radiation, clouds, aerosol | 1° (180×360) | month | 2001-01 → 2026-08 | 127 base (849 total) | 77 GB |
| `syn1deg` daily / hourly | same | 1° | day / hour | 2001 → | 45 / 41 | 128 / 2,834 GB |
| `srb` monthly | GEWEX SRB surface radiation | 1° | month | 1984-01 → **2000-12** | 33 | 4.7 GB |
| `srb` daily | same | 1° | day | 1984 → 2000 | 17 | 74 GB |
| `geosit` daily / hourly | GEOS-IT near-real-time meteorology | 0.5°×0.625° | day / hour | 2020 → | 72 / 47 | 219 / 3,428 GB |
| `flashflux` daily | CERES FLASHFlux near-real-time radiation | 1° | day | 2024 → | 5 | 2.8 GB |

Notes from the checks:
- Time axes are pre-allocated to 2029-12; the months after the last real one are empty.
  Always drop empty months. Last filled month seen: MERRA-2 2026-09, IMERG 2026-10, SYN1deg 2026-08.
- `srb` stops in 2000 and `syn1deg` starts in 2001. Joining them makes a step change at the
  seam, so do not compute one trend across both.
- Measured compressed size: `T2M` in the monthly MERRA-2 store is 262 objects, 139 MB
  (raw 489 MB). Monthly temporal chunks are 588 months × 30×30 cells.
- `gwm/` folder exists but holds no Zarr stores at the two levels listed; contents not checked.

### Variables in the MERRA-2 monthly store (88)
- **Temperature:** `T2M`, `T2M_MAX`, `T2M_MIN`, `T2M_RANGE`, `T2MDEW`, `T2MWET`, `T10M` (+max/min/range), `TS` (skin, +max/min/range), `TSURF`, `TSOIL1`–`TSOIL6`.
- **Water:** `PRECTOTCORR` (mm/day), `PRECTOTCORR_SUM` (mm), `PRECSNO`, `PRECSNOLAND`, `EVLAND` (land evaporation), `EVPTRNS` (evapotranspiration energy flux), `GWETTOP`, `GWETROOT`, `GWETPROF` (soil wetness, 0–1), `QV2M`, `QV10M`, `RH2M`, `TQV` (column water vapour).
- **Snow and ice:** `FRSNO` (snow cover fraction), `SNODP` (snow depth), `FRSEAICE` (sea-ice fraction), `FROST_DAYS`.
- **Atmosphere:** `PS`, `SLP`, `TO3` (total ozone), `PBLTOP`, `TROPT`, `TROPPB`, `TROPQ` (tropopause temperature, pressure, humidity), `RHOA`.
- **Wind:** `WS2M`, `WS10M`, `WS50M` (+max/min/range), `U`/`V` components, `WD*` directions.
- **Derived:** heating and cooling degree days (`HDD*`, `CDD*`), `Z0M`, `DISPH`.
- The `_00` … `_23` variants are means for each hour of day; ignore them.

### Variables in SYN1deg monthly (127) and SRB monthly (33)
Surface and top-of-atmosphere shortwave and longwave irradiance (all-sky and clear-sky, up and
down, direct and diffuse), PAR, UVA, UVB, UV index, `CLOUD_AMT` (+day/night), `CLOUD_OD`,
`AOD_55_ADJ` (aerosol optical depth), surface albedo (`ALLSKY_SRF_ALB`, `SRF_ALB_ADJ`), `PW`
(precipitable water), `TS_ADJ`, clearness indices, `CLRSKY_DAYS`.

### Measured performance (our own test, from this machine)
| Request | Cells read | Time |
|---|---|---|
| Open MERRA-2 monthly store | metadata | 3.9 s |
| Ukraine box, one variable, all 588 months | 18×29 | 0.3–1.7 s |
| Sahel box | 17×81 | 0.6 s |
| Arctic cap 70–90°N | 41×576 | 3.8 s |
| Whole globe, annual means 1981–2025 | 361×576 | 58 s |
| IMERG monthly, Ukraine box | 85×185 | 2.3 s |
| SYN1deg / SRB monthly, Ukraine box | 9×19 | 0.7–1.0 s |

So: regional requests can be live; whole-globe maps must be precomputed.

Trend results from the same test (monthly anomalies, least-squares slope with 95 % interval;
Mann-Kendall with Hamed-Rao correction on annual means). These are a first run to prove the
pipeline, not validated findings:

| Series | Slope per decade | OLS p | Mann-Kendall (annual) |
|---|---|---|---|
| Ukraine 2 m temperature | +0.53 °C (±0.11) | 6e-19 | increasing, p=1e-8 |
| Ukraine precipitation (MERRA-2) | +0.04 mm/day (±0.035) | 0.03 | increasing, p=0.03 |
| Ukraine precipitation (IMERG, 1998–) | +0.06 mm/day (±0.08) | 0.13 | no trend |
| Ukraine snow-cover fraction | −0.008 (±0.006) | 0.009 | no trend, p=0.15 |
| Sahel precipitation | +0.09 mm/day (±0.04) | 7e-6 | no trend, p=0.16 |
| Arctic sea-ice fraction 70–90°N | −0.014 (±0.002) | 1e-50 | decreasing, p=2e-10 |
| Global mean 2 m temperature (annual, OLS) | +0.17 °C | 3e-14 | not run |

Two lessons already visible: the two tests can disagree (Sahel, snow), because monthly
anomalies are autocorrelated and make the simple test over-confident; and two datasets for
the same variable can disagree (MERRA-2 vs IMERG precipitation). Both are good teaching
material for the app.

### How to read it
Implemented in `backend/trend_detective/power_zarr.py` (CLI: `scripts/fetch_power_region.py`).
```python
import fsspec, xarray as xr
ds = xr.open_zarr(fsspec.get_mapper(
    "https://nasa-power.s3.us-west-2.amazonaws.com/merra2/temporal/power_merra2_monthly_temporal_utc.zarr"),
    consolidated=True)
box = ds["T2M"].sel(lat=slice(44, 52.5), lon=slice(22, 40.5)).load()
```
Version pins that worked: `xarray==2024.9.0`, `zarr==2.18.3`, `numcodecs<0.14`, `numpy<2.2`,
plus `fsspec`, `aiohttp`, `dask`. The newest xarray with zarr 2 failed with a `zarr_format` error.

---

## 2. NASA POWER REST API
- **Address:** `https://power.larc.nasa.gov/api/temporal/{hourly|daily|monthly|climatology}/point`
- **Access:** no key. JSON, CSV or NetCDF output.
- **Content:** same data as the Zarr archive. Parameter counts per community (AG, RE, SB are
  identical): hourly 105, daily 152, monthly 1,388, climatology 1,634.
- **Checked:** a point request for 21 monthly parameters, 1981–2025, returned in one call
  (585 values per parameter, which is 45 years × 13: the 12 months plus what looks like an annual value).
- **Limits found:** the regional endpoint refuses boxes wider than 10° of longitude. Missing
  values are `-999` (seen for radiation before 1984), so mask them before any statistics.
- **Use:** fallback when the Zarr path is slow, and the simplest way to prototype.

---

## 3. Giovanni (official resource)

### Web UI — `https://giovanni.gsfc.nasa.gov/giovanni/`
- **2,049 variables in 177 products**, valid range 1948-01-01 to today (catalog read from the page).
- By type: Reanalysis 734, Observation 755, Model 560.
- By time step: **monthly 1,292**, daily 478, hourly 143, 3-hourly 83, 8-day 39, half-hourly 8, weekly 6.
- By grid: 0.5×0.625° 736, 1° 587, 0.25° 234, 0.125° 172, 0.1° 88, 0.5° 71, 4 km 44, 9 km 34, 0.01° 27.
- By discipline (overlapping): Water and Energy Cycle 816, Atmospheric Dynamics 765, Hydrology
  672, Aerosols 268, Atmospheric Chemistry 241, Oceanography 82, Ocean Biology 52, Cryosphere 18.
- Plot types include time-averaged map and **area-averaged time series**, with CSV download.
- Works with "limited access" without login; full access needs a free Earthdata login.

Variables by instrument or model, with the monthly products most useful for trends:

| Source | Variables | Key monthly products (grid, span) | What they hold |
|---|---|---|---|
| MERRA-2 | 734 | `M2TMNXSLV`, `M2TMNXLND`, `M2TMNXFLX`, `M2TMNXAER`, `M2TMNXRAD`, `M2TMNXINT`, `M2TMNXOCN`, `M2TMNXGLC`, pressure-level `M2IMNPASM`/`M2IMNPANA` (0.5×0.625°, 1980-01 → 2026-09); `M2SMNXEDI` | Temperature, humidity, wind, snow, soil wetness, energy fluxes, aerosols (dust, black carbon, sulfate), cloud, ozone and temperature **by pressure level**, 34 extreme-weather indices (consecutive dry days, cold spells, ...) |
| AIRS | 359 | `AIRS3STM` v7.0 (1°, 2002-09 → 2026-10), 42 variables | Air and surface temperature, water vapour, clouds, outgoing longwave, methane, CO, ozone; day and night passes |
| GLDAS | 268 | `GLDAS_NOAH025_M` 2.0 (0.25°, 1948 → 2014) and 2.1 (2000 → 2026-07), 36 variables each | Evapotranspiration, soil moisture by layer, runoff, snow water, canopy water, heat fluxes |
| MODIS Aqua / Terra | 104 / 54 | `MOD08_M3`/`MYD08_M3` (1°, 2000/2002 →), SST 4 and 9 km, chlorophyll 4 km (2002-07 → 2025-11) | Aerosol optical depth, cloud properties, water vapour; sea surface temperature; ocean colour |
| NLDAS | 134 | `NLDAS_NOAH0125_M`, `NLDAS_FORA0125_M` (0.125°, 1979 →, North America only) | Hydrology and forcing |
| SeaWiFS | 106 | chlorophyll 9 km, aerosol (1997-09 → 2010-12) | Ended record; the data used in the official paper |
| FLDAS | 99 | `FLDAS_NOAH01_C_GL_M` (0.1°, 1982-01 → 2026-09), 28 variables + ready-made anomaly product | Evapotranspiration, runoff, rainfall, soil moisture, at the finest global grid here |
| OMI | 44 | daily only: `OMNO2d` (0.25°, 2004-10 →), `OMTO3d`, `OMSO2e`, `OMAERUVd`, `OMHCHOd`, `OMUVBd` | NO2, ozone, SO2, aerosol, formaldehyde, UV |
| NCA-LDAS | 33 | daily, 1979 → 2016, US | Includes streamflow and flooded area |
| TRMM | 22 | `TRMM_3B43` (0.25°, 1998 → 2019) | Precipitation, ended |
| GPM | 15 | `GPM_3IMERGM` (0.1°, 1998-01 → 2025-09) | Precipitation |
| GPCP | ~19 | `GPCPMON` 3.3 (0.5°, 1983 → 2025-12) | Longest satellite-gauge precipitation |
| MOPITT | 12 | `MOP03JM` (1°, 2000-03 → 2025-01) | Carbon monoxide, surface and profile |
| GRACE-DA | 6 | weekly, 0.25° global (2003 →) | Groundwater and soil moisture percentiles |
| OCO-2/GEOS | 2 | monthly 0.5×0.625° (2015-01 → 2022-02) | Column CO2; short record |
| Others | — | AMSR-E/AMSR-2 soil moisture, Aquarius salinity (2011–2015), MISR aerosol (to 2017), NOBM ocean biology model (1998–2015), TOMS ozone (1978–2005) | |

Measurement groups with the most variables: Atmospheric Moisture 191, Soil Moisture 135,
Precipitation 131, Air Temperature 129, Cloud Properties 121, Aerosol Optical Depth 92,
Wind 69, Snow/Ice 65, Heat Flux 63, Soil Temperature 57, Ozone 52, Evaporation 40,
Evapotranspiration 34, Runoff 31, CO 33, CH4 16, SO2 12, Chlorophyll 10, NO2 4, CO2 4, **Streamflow 3**.

### Time Series API — `https://api.giovanni.earthdata.nasa.gov/timeseries`
- Replaces the Data Rods service, which was shut down (alert dated 2025-10-01; the old URL
  now redirects to that alert).
- **867 variables** (list is public at `/configured-variables/`): GLDAS 268, NLDAS 134,
  AIRS 217, FLDAS 83, MERRA-2 about 70, NCA-LDAS 33, OMI about 27, GPM 15, NOBM 8, GRACE-DA 6,
  TRMM 2, GPCP 2, SMERGE 2, OCO-2 1.
- Request: `?data=<variable id>&location=[lat,lon]&time=<start>/<end>`; returns CSV.
- **Needs an Earthdata bearer token** (our call without one got HTTP 403).
- **One point per call.** No area average, no box (per an Earthdata forum answer, date unknown).
- Use: add satellite instruments beside model data for a chosen point; cache results.

### Hydrology Time Series viewer (official resource)
Web viewer on the same API: pick a variable and a point, get an interactive plot, export PNG
and CSV. Collections: GLDAS Noah 3-hourly 2.0/2.1, NLDAS (4 models), MERRA-2 hourly (5
products), IMERG half-hourly, GRACE-DA (US), SMERGE. Manual tool; good for spot checks.

---

## 4. AppEEARS (official resource)
- **Address:** `https://appeears.earthdatacloud.nasa.gov/` ; API at `/api/`.
- **193 products** (public list). By platform: VIIRS (S-NPP 25, NOAA-20 23, NOAA-21 22),
  MODIS Terra 25, Aqua 23, Combined 9, ECOSTRESS 14, PACE 12, Landsat ARD 10, EMIT 7, SMAP 5,
  HLS 4, elevation models 10, DAYMET 1, US National Park Service water balance 2.
- By time step: daily 72, 8-day 46, 16-day 22, yearly 12, monthly 8, static 10.
- By resolution: 500 m 70, 1 km 43, 30 m 22, 70 m 14, 250 m 8.
- Longest records useful for trends (all MODIS Terra, v061, 2000 → present):

| Product | Content | Grid | Step |
|---|---|---|---|
| MOD13A3 | Vegetation indices NDVI, EVI | 1 km | monthly |
| MOD13Q1 / A1 / A2 | same | 250 m / 500 m / 1 km | 16-day |
| MOD11A2 | Land surface temperature day and night | 1 km | 8-day |
| MOD10A2 / A1 | Snow cover | 500 m | 8-day / daily |
| MOD16A2GF / A3GF | Evapotranspiration, gap-filled | 500 m | 8-day / yearly |
| MOD17A2HGF / A3HGF | Gross / net primary production | 500 m | 8-day / yearly |
| MOD15A2H | Leaf area index | 500 m | 8-day |
| MCD64A1 | Burned area | 500 m | monthly |
| MCD12Q1 | Land cover type | 500 m | yearly (2001 →) |
| MOD44B | Tree / vegetation cover fraction | 250 m | yearly |

- Short records (limited for trends): SMAP soil moisture 2015 →, HLS 30 m 2013/2015 →, PACE 2024 →.
- **How it works:** submit a point list or polygon; the job is queued; results are CSV (points)
  or GeoTIFF/NetCDF (areas). Needs Earthdata login. Job time was not tested.
- **Use:** offline preparation of NDVI, land-surface temperature and snow series for our demo
  regions. Not suitable for answering a user's click live.

---

## 5. Monthly gridded collections for offline precompute (sizes from CMR)

CMR (`https://cmr.earthdata.nasa.gov/search/`) is NASA's public metadata catalog; it needs no
login to search. Total size = granule count × average size of the 20 newest files.
Downloading the files needs an Earthdata login (`earthaccess` Python package).

| Collection | Content | Grid | Span | Files | Per file | Total |
|---|---|---|---|---|---|---|
| `M2TMNXSLV` 5.12.4 | MERRA-2 single-level (T, humidity, wind) | 0.5×0.625° | 1980-01 → 2026-09 | 561 | 75 MB | 42 GB |
| `M2TMNXLND` | MERRA-2 land (soil, snow, evaporation, runoff) | same | same | 561 | 80 MB | 45 GB |
| `M2TMNXFLX` | MERRA-2 surface fluxes, precipitation | same | same | 561 | 74 MB | 41 GB |
| `M2TMNXAER` | MERRA-2 aerosols | same | same | 561 | 80 MB | 45 GB |
| `M2IMNPASM` | MERRA-2 on pressure levels | same, many levels | same | 561 | 1.6 GB | 919 GB |
| `GLDAS_NOAH025_M` 2.1 | GLDAS land surface | 0.25° | 2000-01 → 2026-07 | 319 | 24 MB | 7.7 GB |
| `GLDAS_NOAH025_M` 2.0 | same, older forcing | 0.25° | 1948-01 → 2014-12 | 804 | 24 MB | 19 GB |
| `FLDAS_NOAH01_C_GL_M` | FLDAS land surface | 0.1° | 1982-01 → 2026-09 | 537 | 125 MB | 67 GB |
| `AIRS3STM` 7.0 | AIRS monthly, with vertical levels | 1° | 2002-09 → 2026-10 | 290 | 201 MB | 58 GB |
| `GPM_3IMERGM` 07 | IMERG precipitation | 0.1° | 1998-01 → 2025-09 | 333 | 18 MB | 6 GB |
| `GPCPMON` 3.2 | GPCP precipitation | 0.5° | 1983-01 → 2023-12 | 492 | 6.5 MB | 3.2 GB |
| `TRMM_3B43` 7 | TRMM precipitation | 0.25° | 1998 → 2019 | 264 | 3.7 MB | 1 GB |
| `OMNO2d` 003 | OMI NO2, daily | 0.25° | 2004-10 → 2026-03 | 7,800 | 12 MB | 97 GB |
| `OMTO3d` 003 | OMI ozone, daily | 1° | 2004-10 → 2026-11 | 8,036 | 0.6 MB | 4.7 GB |
| `OMSO2e` 003 | OMI SO2, daily | 0.25° | 2004-10 → 2026-03 | 7,804 | 3.2 MB | 25 GB |
| `OMAERUVd` 003 | OMI aerosol, daily | 1° | 2004-10 → 2026-11 | 8,036 | 0.6 MB | 4.5 GB |
| `OCO2_GEOS_L3CO2_MONTH` | CO2 | 0.5×0.625° | 2014-06 → 2022-02 | 86 | 3.2 MB | 0.3 GB |
| `MOD13C2` 061 | MODIS NDVI/EVI | 0.05° | 2000-02 → 2026-10 | 321 | 99 MB | 32 GB |
| `MOD11C3` 061 | MODIS land surface temperature | 0.05° | 2000-02 → 2026-10 | 321 | 70 MB | 22.5 GB |
| `MOD10CM` 61 | MODIS snow cover | 0.05° | 2000-03 → 2026-10 | 315 | 1.4 MB | 0.4 GB |
| `MOD08_M3` 6.1 | MODIS aerosol, cloud, water vapour | 1° | 2000-02 → 2026-10 | 321 | 357 MB | 115 GB |
| `MCD64A1` 061 | MODIS burned area (tiles) | 500 m | 2000-11 → 2026-09 | 83,336 | 1.3 MB | 105 GB |
| `MCD12C1` 061 | Land cover | 0.05° | 2001 → 2025 | 25 | 1.2 GB | 30 GB |
| `NSIDC-0051` v2 | Sea-ice concentration | 25 km polar | 1978-10 → 2025-12 | 35,600 | 0.1 MB | 2.3 GB |
| `NASA_SSH_REF_SIMPLE_GRID_V1` | Sea surface height | gridded | 1992-10 → 2026-05 | 1,750 | 1.1 MB | 1.9 GB |
| GRACE/GRACE-FO JPL mascon RL06.3 v4 | Water storage anomaly | 0.5° | 2002-04 → (one file) | 1 | 44 MB | 44 MB |
| `CERES_EBAF` Ed4.2.1 | Earth's energy budget | 1° | 2000-03 → (one file) | 1 | 2 GB | 2 GB |

Cheapest high-value additions: MOD10CM snow (0.4 GB), GRACE mascon (44 MB), GPM_3IMERGM (6 GB,
already in POWER Zarr), GLDAS 2.1 (7.7 GB), OMTO3d ozone (4.7 GB).
Note OMI has no monthly product: daily files must be averaged to months ourselves.

---

## 6. Other official resources

| Resource | What is inside | Access | Use for us |
|---|---|---|---|
| **NOAA Climate Data Online** | Station data: Daily Summaries, Global Summary of the Month / Year, Normals (daily, monthly, annual), hourly and 15-minute precipitation, marine data, weather radar | REST API v2 with free token; 5 requests/s, 10,000/day | Optional: station series next to our gridded one |
| **KNMI Climate Explorer** | Over 10 TB: station temperature and precipitation, reanalyses, CMIP model output; built-in time series, anomalies, trend with significance | Web only; asks each visitor to confirm they are human | Validate our trends by hand; no API |
| **SeaWiFS paper** (Acker et al. 2009) | Method the organisers hold up as the example; details below | PDF, 8.4 MB | Template for our analysis and case files |
| **Medium article** (trend tests) | Python walk-through on toy methane data: linear regression, Mann-Kendall, seasonal Mann-Kendall, unit-root tests; lowers the slope until the tests stop detecting it | Web | Idea for an interactive "how much data until it is significant" demo |
| **Statsig guide** | Plain explanation of p-values, hypotheses, significance level, t-test (written for A/B tests) | Web | Wording for our in-app explanations |
| **CSA RADARSAT Constellation** | Radar imagery; some products free through Canada's EODMS portal under a licence | Portal with registration | Not needed |
| **CSA SAR Python tutorial** | Beginner notebook: plot a RADARSAT raster of British Columbia wildfires with `osgeo` and `cartopy`; QGIS guide | GitHub | Not needed |
| **SWOT mission page** | Information only; launched 2022-12, so the record is too short for trends | Web | Not needed |
| **Geo.ca**, CSA ecosystems page | Canadian open geodata portal; general information | Web | Only if we pick a Canadian case |
| **CUAHSI** (named in the challenge text) | HydroClient: search and download station hydrology (streamflow, etc.); time-series viewer app. Its Data Rods Explorer app depends on the discontinued NASA service | Web + REST | Optional streamflow ground truth; not opened in the browser this session |

### What the official paper actually did (read from the PDF text)
1. Data: SeaWiFS monthly chlorophyll, 9 km grid, January 1998 – December 2007.
2. Regions: hand-drawn boxes off nine river mouths (Amazon, Congo, Orinoco, Mississippi east
   and west, Pearl, Eel, Ganges, Po, Guadalquivir), each some distance from the coast.
3. Series: Giovanni area average, exported as text, loaded into Excel.
4. Trend: least-squares linear regression on the monthly values.
5. Significance: F-test from ANOVA, p < 0.05; R² reported as fit quality.
6. Second view: monthly anomalies (month value minus that month's long-term mean), averaged
   per year, then regression again.
7. Reported per river: distance, significance F, F-value, slope, R², average value.
8. Findings: Amazon, Congo, Orinoco decreasing but **not significant**; Mississippi (both
   sections) and Po significantly decreasing; Eel significantly increasing; Pearl increasing,
   close to significant. Flood events dominate some series.

This is the level the organisers consider a complete answer. Anything we add on top
(autocorrelation handling, maps, multiple datasets) is a bonus.

---

## 7. Small no-login reference series (for validation and demos)
| Series | File | Size | Span |
|---|---|---|---|
| Arctic / Antarctic sea-ice extent, per month | `noaadata.apps.nsidc.org/NOAA/G02135/{north,south}/monthly/data/{N,S}_MM_extent_v4.0.csv` | 2.4 KB each | 1979 → 2026 (September: 7.05 → 4.81 million km²) |
| Mauna Loa CO2 monthly | `gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.csv` | 39 KB | 1958 → |
| Global CH4 monthly | `gml.noaa.gov/webdata/ccgg/trends/ch4/ch4_mm_gl.csv` | 24 KB | 1983 → |
| GISTEMP global temperature | `data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv` | not measured | 1880 → |

`data.giss.nasa.gov` refused connections from this machine today, so GISTEMP could not be
fetched. The sea-ice pair (Arctic falling, Antarctic different) is a ready "opposite
directions" example.

---

## 8. Other teams (GitHub, checked today)
A GitHub search for "trend detective" NASA repositories updated since September returned 50,
most pushed in the last two days. The four from our earlier notes still exist:

| Repository | Stack | Size | Last push |
|---|---|---|---|
| entitySource/trend_detective | TypeScript | 121 MB | 2026-11-11 |
| nasa-earth-detectives/nasa-earth-trend-detective | TypeScript | 25 MB | 2026-11-13 |
| iammahmudhasan/Be-An-Earth-System-Trend-Detective- | JavaScript | 117 MB | 2026-10-01 |
| GOHSUNJIN/TerraTrend | JavaScript | 16 MB | 2026-10-30 |

About half of the 50 are Python. One is named `power-trend-detective`, so we are not the
only team using POWER. Their code was not read this session.

---

## 9. Not checked
- AppEEARS job turnaround time; any download through `earthaccess` (we have no Earthdata login set up).
- Giovanni Time Series API with a real token.
- Contents of POWER `gwm/`; daily and hourly stores were sized from metadata only, not read.
- CUAHSI and KNMI tools were not exercised; GISTEMP was unreachable.
- Other teams' code.
