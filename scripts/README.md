# scripts

Idempotent data fetch / precompute scripts with a CLI (`python scripts/<name>.py --help`).
Each writes outputs to `data/cache/` with a `*.provenance.json` sidecar (see `nasa-data-access` skill).

| Script | What it does | Output |
|---|---|---|
| `make_geo.py` | Downloads Natural Earth (public domain; Ukrainian point of view for borders), simplifies it, builds the prepared-region outlines | `frontend/public/basemap/*.geojson`, `data/regions/regions.geojson` |
| `make_synthetic_data.py` | **Synthetic** demo data in the exact web-app format. Inputs are invented; all statistics are computed with `trend_stats.py`; every file is flagged `synthetic: true` | `frontend/public/data/` |
| `check_data.py` | Validates every web-app JSON file against `schema/` (run before committing data) | exit code 0/1 |

The real pipeline (`build_all.py`, stats team) must write the same files in the same format;
`check_data.py` is the gate.
