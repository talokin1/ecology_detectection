# ADR-004 — NASA POWER Zarr archive as the primary live data source

- Status: Proposed (pending data-engineer and lead approval)
- Date: 2026-11-14
- Deciders (names): _fill in_
- Requirement IDs: R-01, R-02, R-03, R-15, R-32

## Context
R-02 needs a regional, cos(lat)-weighted series for a user-chosen box, fast enough for a live
request (target < 3 s, `docs/04-architecture.md`) and without a login (R-32). Checked on 2026-11-14:

- NASA POWER REST API: no login, but its regional endpoint refuses boxes wider than 10° of longitude
  and takes one parameter per request.
- Giovanni Time Series API: needs an Earthdata token and returns single points only.
- Hydrology Data Rods: discontinued (GES DISC alert dated 2025-10-01; the old URL redirects to it).
  `nasa-data-access` skill step 5 and `docs/09-references.md` still point to it.
- NASA POWER Zarr archive on AWS Open Data (`https://nasa-power.s3.us-west-2.amazonaws.com/`):
  public HTTPS, no login. Monthly stores are chunked along time, so a region's whole history is a
  few small reads.

Measured from one team machine: Ukraine box, 549 months, 0.3–6 s on first read, 1–2 ms from cache.
A whole-globe read of one variable took about 58 s. Details:
`docs/planning/2026-11-14-data-sources-deep-dive.md`.

## Options
1. POWER REST API only — simplest; boxes limited to 10° longitude; one parameter per call.
2. Pre-fetch everything with `earthaccess` into `data/cache/` — any dataset; needs Earthdata login,
   hours of downloads, and only prepared regions work.
3. **POWER Zarr archive read live, cached per region** — any box on Earth, no login, three stores:
   MERRA-2 (88 monthly variables, 1981 →), GPM IMERG precipitation (1998 →), CERES SYN1deg clouds,
   aerosol and radiation (2001 →). Limited to what POWER republishes; no MODIS land, OMI, AIRS or GLDAS.

## Decision (proposed)
Option 3 for live regional series, implemented in `backend/trend_detective/power_zarr.py`, with the
REST API (option 1) as fallback and option 2 kept for the offline trend maps and non-POWER variables.

## Consequences
- R-02 works for any region without accounts; every cached series has a provenance sidecar.
- Whole-globe trend maps (R-15) cannot be computed per request; they stay an offline precompute.
- Dependencies added to `requirements.txt`: xarray, zarr, numcodecs (pinned together), fsspec,
  aiohttp, dask, pandas. Not yet tested on Windows.
- POWER publishes no DOI for the Zarr stores; references use the landing and registry pages.
- The time axes are pre-allocated to 2029; empty months are dropped by the reader.
- `power_srb` (1984–2000) and `power_syn1deg` (2001 →) must not be joined into one trend.
- Follow-up: catalog entries for POWER variables can set `variable_verified: true` once someone
  compares one series with the REST API; update `nasa-data-access` step 5 (Data Rods is gone).
