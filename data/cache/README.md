# data/cache

Regional series and grids built from NASA data, with provenance. See `docs/planning/2026-11-14-data-plan.md`.

## Layout
| Folder | What | In git |
|---|---|---|
| `power_zarr/` | NASA POWER series: `<store>_<VARIABLE>_<hash>.csv` (monthly `month,value`; daily `date,value`) | yes |
| `earthdata/` | Earthdata series: GRACE `grace_lwe_<hash>.csv`, MODIS NDVI `mod13c2_ndvi_<hash>.csv` (`month,value,valid_fraction`) | yes |
| `grids/` | global monthly grids for the world map (NetCDF): `<store>_<VAR>_<res>deg.nc` | only grids the map uses, listed in `.gitignore` (ADR-006; now: T2M at 2°, 26.1 MB); rebuild others with `python scripts/fetch_grid.py --variable <VAR> --resolution 2` (~40 s, no login) |
| `raw/` | whole downloaded files (GRACE mascon NetCDF) | **no**, rebuilt by scripts |
| `MANIFEST.json` | every committed series with sha256, rows and freeze date | yes |

Every file has a `<file>.provenance.json` sidecar: source, store or short name, version, DOI or landing page,
bbox, land_only, period, processing steps, caveats, access date, script and git commit. The `<hash>` is
derived from the variable, store, bounding box and options, so the same request always maps to the same file.

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
