---
name: nasa-data-access
description: How to find, fetch, subset, cache and document NASA Earth-science data for the Trend Detective project (NASA POWER, Giovanni, GES DISC/Harmony, earthaccess, AppEEARS, CMR). Use whenever code downloads data, calls a NASA API, adds a variable to the catalog, handles Earthdata Login, or converts units/fill values.
---

# NASA data access

Catalog of approved variables: `data/catalog/variables.yaml`. Access details per service:
`references/access-methods.md`. Every dataset used must also be listed in `docs/09-references.md`.

## Decision tree
1. **Need a meteorological variable for a point or small region, live, no login?** → NASA POWER API
   (`T2M`, `PRECTOTCORR`, `GWETROOT`, `ALLSKY_SFC_SW_DWN`, `SNODP`, …). Monthly or daily from 1981.
   Regional requests: one parameter per request.
2. **Need a gridded field for a trend map or a non-POWER variable?** → pre-fetch offline with
   `earthaccess` (search + download) or Harmony subsetting (`harmony-py`) and cache a regional
   subset as NetCDF/Zarr in `data/cache/`. Never fetch whole global archives at request time.
3. **Need a quick area-averaged series to cross-check?** → Giovanni UI "Area-Averaged Time Series"
   (CSV export). The Giovanni cloud time-series API returns single points only.
4. **MODIS land products for a small area?** → AppEEARS (async task; poll status) or `earthaccess`
   + subsetting of the 0.05° CMG monthly product.
5. **Hydrology point series?** → GES DISC Hydrology Data Rods (GLDAS/NLDAS).

## Rules
- **Auth**: Earthdata Login via `~/.netrc` (`machine urs.earthdata.nasa.gov login … password …`) or
  `EARTHDATA_TOKEN` in `.env`. Backend only. Never in frontend, logs, notebooks outputs or git.
- **Verify before use**: confirm collection short name/version in CMR
  (`https://cmr.earthdata.nasa.gov/search/collections.json?short_name=…`) and open one granule to confirm
  variable name, units, `_FillValue`, `scale_factor`; then set `variable_verified: true` in the catalog.
- **Decode correctly**: `xr.open_dataset(..., mask_and_scale=True)`; MODIS HDF/CMG scale factors
  (NDVI ×0.0001, LST ×0.02 K); convert units in one place (catalog `convert`).
- **Monthly first**: aggregate daily → monthly (mean for states, sum or mean-rate for fluxes;
  document which) and require ≥ 80% valid days per month.
- **Do not splice versions** (e.g. GLDAS v2.0 + v2.1) without an overlap comparison — it creates false trends.
- **Provenance sidecar** for every cached file: `<file>.provenance.json` with source, short name, version,
  DOI/landing page, bbox, time range, access date, script path, git commit.
- **Politeness/limits**: cache responses; back off on HTTP 429/503; POWER ≤ 20 params per point request.
- **Fallback**: if a live source fails during the demo, serve cached data and show "cached on <date>".

## Minimal POWER example
```python
import requests, pandas as pd
url = "https://power.larc.nasa.gov/api/temporal/monthly/point"
params = dict(parameters="T2M", community="AG", longitude=30.52, latitude=50.45,
              start=1981, end=2025, format="JSON")
js = requests.get(url, params=params, timeout=60).json()
raw = js["properties"]["parameter"]["T2M"]          # keys "YYYYMM"; month "13" = annual mean
s = pd.Series({k: v for k, v in raw.items() if not k.endswith("13")})
s.index = pd.to_datetime(s.index, format="%Y%m"); s = s.where(s > -900)   # -999 = missing
```
(Verified live 2026-11-14: monthly point + regional endpoints respond without login; header sources
SYN1DEG, MERRA2, POWER.)

## Minimal earthaccess example (gridded, offline precompute)
```python
import earthaccess, xarray as xr
earthaccess.login(strategy="netrc")
res = earthaccess.search_data(short_name="M2TMNXSLV", version="5.12.4",
                              temporal=("1981-01", "2025-12"), bounding_box=(22, 44, 40, 52.5))
files = earthaccess.download(res, "data/cache/raw/M2TMNXSLV")
ds = xr.open_mfdataset(files, combine="by_coords")["T2M"].sel(lat=slice(44, 52.5), lon=slice(22, 40))
```
