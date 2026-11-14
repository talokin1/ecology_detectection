# Access methods — details and gotchas

Checked 2026-11-14 unless noted. Re-verify anything marked (unverified) before relying on it.

## NASA POWER
- Base: `https://power.larc.nasa.gov/api/temporal/{hourly|daily|monthly|climatology}/{point|regional}`
- Auth: none. Communities: `AG`, `RE`, `SB` (units differ slightly by community — fix one, use AG).
- Daily: 1981-01-01 → near real time. Monthly: by year; key `YYYY13` is the annual value — drop it.
- Point: up to 20 parameters per request. Regional: 1 parameter per request; bounding box limits apply
  (unverified exact size limit — test with the target region).
- Missing value: -999.
- Meteorology from MERRA-2; solar from GEWEX SRB (1984–2000) and CERES SYN1deg/FLASHFlux.
- Docs: https://power.larc.nasa.gov/docs/services/api/

## Giovanni (GES DISC)
- UI: https://giovanni.gsfc.nasa.gov/ — requires Earthdata Login since 2019 for full functionality.
- Services useful for us: Area-Averaged Time Series, Time Series Recurring Averages, Time-Averaged Map,
  Correlation Map. Export CSV/NetCDF.
- Cloud time-series API (`https://api.giovanni.earthdata.nasa.gov/timeseries`, bearer EDL token):
  single point only (per GES DISC support on the Earthdata Forum). Area averages: Harmony / cloud Giovanni
  services via `harmony-py` (see GES DISC tutorials repo `nasa/gesdisc-tutorials`).
- Large regions × long daily ranges can time out — use monthly products.

## GES DISC Hydrology Data Rods
- Point time series for GLDAS/NLDAS variables; REST keywords: variable, location, startDate, endDate, type.
- Landing: https://disc.gsfc.nasa.gov/information/tools?title=Hydrology%20Data%20Rods

## AppEEARS (LP DAAC)
- API: `https://appeears.earthdatacloud.nasa.gov/api/` — POST `login` with EDL creds → bearer token;
  submit point/area task; poll `task/{id}` (queued → processing → done, minutes); download bundle.
- Good for MODIS NDVI/LST subsets with QA filtering.

## earthaccess (Python)
- `earthaccess.login(strategy="netrc"|"environment")`, `search_data(short_name, version, temporal,
  bounding_box)`, `download(...)` or `open(...)` (streaming, faster in AWS us-west-2).

## CMR (catalog search, no auth)
- Collections: `https://cmr.earthdata.nasa.gov/search/collections.json?short_name=<SN>`
- Granules: `https://cmr.earthdata.nasa.gov/search/granules.json?short_name=<SN>&temporal=…&bounding_box=…`

## CMR check results (2026-11-14)
| Short name | Version | Provider | Coverage |
|---|---|---|---|
| M2TMNXSLV / M2TMNXFLX / M2TMNXAER / M2TMNXLND | 5.12.4 | GES_DISC | 1980-01 → ongoing |
| GLDAS_NOAH025_M, GLDAS_NOAH10_M | 2.1 | GES_DISC | 2000-01 → ongoing |
| GLDAS_NOAH025_M, GLDAS_NOAH10_M | 2.0 | GES_DISC | 1948-01 → 2014-12 |
| GPM_3IMERGM | 07 | GES_DISC | 1998-01 → 2025-09 |
| MOD13C2 / MOD11C3 | 061 | LPCLOUD | 2000-02 → ongoing |
| MYD11C3 | 061 | LPCLOUD | 2002-07 → ongoing |
| MOD10CM | 61 | NSIDC_CPRD | 2000-03 → ongoing |
| OMNO2d | 004 (also 003) | GES_DISC | 2004-10 → ongoing |
| OMTO3e | 003 / 004 | GES_DISC | 2004-10 → ongoing |
| AIRS3STM | 7.0 (also 006) | GES_DISC | 2002-09 → ongoing |
| TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4 | RL06.3Mv04 | POCLOUD | 2002-04 → ongoing |
| MODIS_AQUA_L3_SST_THERMAL_MONTHLY_4KM_DAYTIME_V2019.0 | 2019.0 | POCLOUD | 2002-07 → ongoing |
