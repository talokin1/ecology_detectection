# scripts

Idempotent data fetch / precompute scripts with a CLI (`python scripts/<name>.py --help`).
Each writes outputs to `data/cache/` with a `*.provenance.json` sidecar (see `nasa-data-access` skill).

| Script | What it does | Output |
|---|---|---|
| `make_geo.py` | Downloads Natural Earth (public domain; Ukrainian point of view for borders), simplifies it, builds the prepared-region outlines | `frontend/public/basemap/*.geojson`, `data/regions/regions.geojson` |
| `make_app_data.py` | Web-app data from the **real** frozen cache (NASA POWER regional series, daily inputs, 2° grids); never downloads. Verdicts, map and follow-up checks with `trend_stats.py`; deeper checks with `trend_detective.climate_stats` | `frontend/public/data/` |
| `check_data.py` | Validates every web-app JSON file against `schema/` (run before committing data) | exit code 0/1 |
| `analyze_climate.py` | Offline statistics for caller-supplied regional JSON; no downloads | User-selected statistics JSON |
| `make_climate_example.py` | Generates reproducible synthetic monthly or daily inputs for `analyze_climate.py` | `examples/climate/input.json` by default |

Any other producer of web-app data must write the same files in the same format; `check_data.py` is the gate.

The offline JSON analyzer has a separate contract from the web-app build outputs. See
[`docs/climate-statistics-pipeline.md`](../docs/climate-statistics-pipeline.md) and
`schema/climate-{input,output}.schema.json`.
