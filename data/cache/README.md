# data/cache

Regional series and grids built from NASA data, with provenance. See `docs/planning/2026-11-14-data-plan.md`.

## Layout
| Folder | What | In git |
|---|---|---|
| `power_zarr/` | NASA POWER series: `<store>_<VARIABLE>_<hash>.csv` (monthly `month,value`; daily `date,value`) | yes |
| `earthdata/` | Earthdata series: GRACE `grace_lwe_<hash>.csv` (`month,value`), MODIS NDVI `mod13c2_ndvi_<hash>.csv` (`month,value,valid_fraction`) | yes |
| `grids/` | global monthly grids for the world map (NetCDF): `<store>_<VAR>_<res>deg.nc` | only grids the map uses, listed in `.gitignore` (ADR-006; now: T2M at 2°, 26.1 MB); rebuild others with `python scripts/fetch_grid.py --variable <VAR> --resolution 2` (~40 s, no login) |
| `raw/` | whole downloaded files (GRACE mascon NetCDF) | **no**, rebuilt by scripts |
| `MANIFEST.json` | every committed series **and map grid** (`kind`), with sha256, rows (months for grids), preset `region_id`, freeze date | yes |

Every file has a `<file>.provenance.json` sidecar: source, store or short name, version, DOI or landing page,
bbox, land_only, period, processing steps, caveats, access date, script and git commit. The `<hash>` is
derived from the variable, store, bounding box and options, so the same request always maps to the same file.

IPCC AR6 regions (`ar6_*` presets, ADR-005 amendment 1) are polygon outlines: their sidecars carry an
`outline` block (source, digest, vertex rings) and the hash also includes the outline digest. MANIFEST
`region_id` matches a preset by bbox and outline digest. Rebuild them with
`python scripts/build_data.py --only set:ar6 --workers 6 --with-earthdata` (GRACE needs the raw mascon file
or a token; POWER needs no login).

## Known quirks (B1-08, B1-11, B1-15)
- Daily series (`merra2_daily_*`) start at `1980-12-31` and end at the first day of the latest month
  (e.g. `2026-10-01`): the store's day boundary is UTC, so these stub days are kept as delivered.
  `monthly_from_daily` drops them (fewer than `min_fraction` of the month's days).
- `merra2_SNODP` for the Sahel is constant 0 (no snow); `assess()` returns `no_variation`, and the app must
  not show it as a trend.
- `land_only` is part of the file hash, so one box could get a land-only and an all-cells copy. The
  preset's `land_only` decides which one `acquire` reads; the unused all-cells N/S Europe PRECTOTCORR
  copies were dropped on 2026-11-14 (still in git history, commit b47dff5).
- Grids carry a global `bbox` plus a `grid` field (cell-centre origin and spacing).
- The canonical `ukraine` box is land-only since 2026-11-14 (Q2); the two monthly-store files
  `merra2_T2M_MAX_5d7bbc9d8b5e` (hottest hour of the month) and `merra2_PRECTOTCORR_SUM_3d18bd2d0015` are
  older all-cells ukraine copies, not build jobs.

## Rules
- **The data is frozen and committed.** Do not refetch on your own machine; pull. A refresh is a deliberate
  commit by the data engineer that also updates `MANIFEST.json`.
- Use `backend/trend_detective/acquire.py` to read series (`get_series`, `get_input_series`,
  `get_monthly_from_daily`). Earthdata series are served from this cache, so no token is needed.
- Never commit `.env`, tokens or raw files (> 50 MB).

## Rebuild (data engineer only; PowerShell or bash, from the repo root)
```
python scripts/fetch_power_region.py --variable T2M --name Ukraine --bbox 22 44 40.5 52.5
python scripts/fetch_earthdata_region.py --dataset grace --name Ukraine --bbox 22 44 40.5 52.5
python scripts/fetch_earthdata_region.py --dataset ndvi --name Ukraine --bbox 22 44 40.5 52.5
python scripts/region_inventory.py --region south_ukraine
```
Earthdata fetches need `EARTHDATA_TOKEN` in `.env` (see `.env.example`).
