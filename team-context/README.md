# team-context

Analysis archive for the NASA Space Apps 2026 challenge "Be An Earth System Trend Detective". This folder is the statistics and data work. The app, frontend, and submission kit live elsewhere in the repository.

## What is official

- Trend test: repository Mann–Kendall with the Yue–Wang AR(1) correction. See `../docs/decisions/ADR-003-yue-wang-official-for-ukraine-archive.md` and `../docs/10-methods.md`. HAC and Hamed–Rao lag-3 are sensitivity columns.
- Ukraine case (archive alternates; the canonical product region is the catalog `ukraine` [22.0, 44.0, 40.5, 52.5], land-only, ADR-005): bbox 22.1–40.2°E, 44.4–52.4°N (`ukraine_sa_bbox` in the catalog, `ukraine_bbox` here), plus `ukraine_mask` (Crimea included, primary) and `ukraine_mask_no_crimea`.
- Smoke test (OLS slopes, tolerance ±0.005): POWER T2M **+0.5526** °C/decade, HadCRUT5 **+0.5793** °C/decade, GRACE production overlap weights **−11.242** cm/decade.

## Layout

| Path | Contents |
|---|---|
| `team/` | Architecture, brief, handoffs, reviews |
| `data/docs/` | Data dictionary, coverage, size estimates |
| `data/fetch/` | Global-download scripts. Roots come from `UKRAINE_SAMPLES` and `GLOBAL_DATA` |
| `data/pipeline/` | Preprocessing and trend pipeline (v1.4) |
| `data/pipeline/outputs/` | v1.4 trend tables, the v1.3 archive, smoke result |
| `stats/` | Vendored `trend_methods.py`, caveats, OMI note, GPCC gauge counts |
| `tools/sync_check.py` | Refuses secrets, the team lead's name, agent ids, files over 50 MB, and denylisted data types |

## Run the pipeline from this checkout

Install `requirements-analysis.txt` from the repository root. Put the regional extracts and the global monthly archive somewhere on disk and export:

```bash
export UKRAINE_SAMPLES=/path/to/ukraine_samples
export GLOBAL_DATA=/path/to/global_data
export OMP_NUM_THREADS=2
```

If those directories sit next to the repository, the pipeline finds them without the variables. Natural Earth 10m admin-0 shapefiles are not in git. From `data/pipeline/`:

```bash
python fetch_natural_earth.py
nice -n 10 python run_pipeline.py --region ukraine_bbox ukraine_mask ukraine_mask_no_crimea
python smoke_test.py
```

`EARTHDATA_TOKEN` is read from the environment by the fetch scripts and is never written into this tree. ERA5 requests are `data/fetch/cds_requests.py`. They were not run: `CDSAPI_KEY` was unset. Do not commit either value.

## Credentials by name

Create an Earthdata Login and export `EARTHDATA_TOKEN`. Approve the GES DISC application once on that account. For AppEEARS, export `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD` and use the login endpoint; a raw bearer token is rejected. For ERA5, export `CDSAPI_KEY` after accepting the Copernicus licence. None of these values belong in the repository.

## Known limits

See `stats/CAVEATS.md`. Short version: OMI and SWOT are bbox means, not mask cuts. OMTO3e ozone on disk ends in 2018-12. The Kyiv 1 km urban-heat task was still processing, so it is not analysed. ERA5 was not downloaded. GPCC gauge counts inside the bbox fell after the 1980s (`stats/gpcc_gauge_counts.md`). Precipitation is not a detection.
