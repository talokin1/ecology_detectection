# Sources checked on 2026-11-14

> First pass. The detailed inventory (sizes, contents, measured speed) is in `2026-11-14-data-sources-deep-dive.md`,
> which also closes most items under "Not yet checked" below.

How each source was checked is in the last column: **browser** = opened and read in the browser,
**curl** = called from the terminal, **search** = found by web search only, not opened.

## Official resources

| Resource | What we learned | Usable in our app? | Checked |
|---|---|---|---|
| Challenge page (Details + Resources) | Full text saved in `2026-11-14-official-challenge-text.md` | — | browser |
| Hydrology Time Series (GES DISC) | Web viewer for point series: GLDAS 2.0/2.1, NLDAS, MERRA-2 hourly, IMERG half-hourly, GRACE-DA (US), SMERGE | For manual checks only | browser |
| Old "Data Rods" API (`hydro1.gesdisc...timeseries.cgi`) | **Discontinued.** The URL redirects to an alert dated 2025-10-01. Many tutorials and other teams' repos still use it | No | browser |
| Giovanni Time Series API (`api.giovanni.earthdata.nasa.gov/timeseries`) | Replaces Data Rods. Returns CSV for **one point**. Variable list is public: 867 variables (GLDAS 268, NLDAS 134, AIRS 217, FLDAS 83, MERRA-2 ~70, OMI ~27, GPM 15, OCO-2, TRMM, GPCP, NOBM ocean biology) | Yes, with an Earthdata token. Call without a token returned **403** | browser + curl |
| Giovanni web UI | Area-averaged time series and maps by hand, CSV download | For validation of our numbers | not opened this session |
| AppEEARS | API product list is public: 193 products (MODIS NDVI, LST, ET MOD16, snow, GPP, ...). Point and area extraction run as queued tasks | Yes for offline prep (needs Earthdata login, tasks take minutes to hours); not for live requests | curl (product list only) |
| NOAA Climate Data Online | Station data | Optional ground truth; API needs a free token | not opened |
| SeaWiFS chlorophyll paper (Acker et al. 2009) | Method template: regional time series from Giovanni → linear trend → significance. Found that flood events dominate coastal series; rivers with human impact mostly showed significant negative trends, Pearl River positive | A ready "opposite trends" story and a format for our case files | browser (abstract only) |
| KNMI Climate Explorer | Free trend and significance tools on many datasets. Now asks each visitor to confirm they are human | Validation by hand only; cannot be called from code | browser |
| CSA resources (RCM, SWOT, Geo.ca, SAR tutorial) | Radar and surface-water data, Canada-focused | Not needed for the core task | not opened |
| Medium and Statsig articles on trend tests | Background reading | — | not opened |

## Additional sources found

| Source | Why it matters | Checked |
|---|---|---|
| **NASA POWER Zarr on AWS** `https://nasa-power.s3.us-west-2.amazonaws.com/` | **Public, no login.** `merra2/temporal/power_merra2_monthly_temporal_utc.zarr`: 588 monthly steps from Jan 1981, grid 361×576 (0.5°×0.625°), ~470 variables. Chunks hold the whole time axis for a 30×30 cell block, so a region's full history is a few small reads. Each variable carries a plain-language `definition` attribute. Other folders: `imerg/` (GPM), `syn1deg/` and `srb/` (CERES radiation), `flashflux/`, `geosit/`, `gwm/` | curl (bucket listing and metadata) |
| NASA POWER REST API | Point monthly series 1981–2025 returned in one call, no key. Regional endpoint is capped at a 10° longitude span. 1388 monthly parameters | curl |
| CMR search API | Free-text dataset search without login (tested with "evapotranspiration monthly") | curl |
| CUAHSI HydroClient / HydroShare apps | Station hydrology (streamflow) search with a REST API. The Data Rods Explorer app depends on the discontinued service, so expect it to be broken | search |
| `skyborn` Python package | Has vectorised Mann-Kendall for xarray grids, with a GPCP tutorial | search |
| `climpred` docs | Example of Benjamini-Hochberg FDR masking on xarray fields | search |
| Earthdata forum thread | Giovanni time series API does not do area averages or spatial subsets; forum points to `harmony-py` for subsetting. Thread date unknown | search |

MERRA-2 variables in the POWER monthly Zarr that fit this challenge: `T2M`, `T2M_MAX`, `T2M_MIN`,
`TS`, `PRECTOTCORR`, `PRECSNO`, `EVLAND` (evaporation), `EVPTRNS` (transpiration), `GWETTOP`,
`GWETROOT`, `GWETPROF` (soil wetness), `FRSNO`, `SNODP`, `FRSEAICE`, `TSOIL1-6`, `QV2M`, `RH2M`,
`TQV` (column water vapour), `TO3` (ozone), `PS`, `SLP`, `WS10M`, `WS50M`, `PBLTOP`, `FROST_DAYS`,
`TROPT`, `TROPPB`, `TROPQ` (tropopause temperature, pressure, humidity: an "atmosphere level" variable).

## Not yet checked
- Contents of the `imerg/`, `syn1deg/`, `srb/` Zarr stores (variable names, time span).
- Whether the last steps of the monthly Zarr are filled (588 steps would run past today's date).
- Reading speed of the Zarr from our network.
- Whether the competitor repositories listed in `01-challenge-and-data.md` still exist.

## Links
- https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/
- https://disc.gsfc.nasa.gov/information/howto?title=Giovanni%20In%20The%20Cloud:%20Time%20Series%20Service
- https://api.giovanni.earthdata.nasa.gov/configured-variables/
- https://power.larc.nasa.gov/docs/services/aws/
- https://registry.opendata.aws/nasa-power/
- https://zarr.dev/blog/nasa-power-and-zarr/
- https://ntrs.nasa.gov/citations/20090042747
- https://forum.earthdata.nasa.gov/viewtopic.php?p=25242
- https://skyborn.readthedocs.io/en/stable/notebooks/mann_kendall_tutorial.html
- https://climpred.readthedocs.io/en/stable/examples/decadal/Significance.html
- https://help.hydroshare.org/apps/data-rods-explorer/
