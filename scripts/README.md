# scripts

Idempotent data fetch / precompute scripts with a CLI (`python scripts/<name>.py --help`).
Each writes outputs to `data/cache/` with a `*.provenance.json` sidecar (see `nasa-data-access` skill).

| Script | What it does | Output |
|---|---|---|
| `make_geo.py` | Downloads Natural Earth (public domain; Ukrainian point of view for borders), simplifies it, builds the prepared-region outlines | `frontend/public/basemap/*.geojson`, `data/regions/regions.geojson` |
| `make_app_data.py` | Web-app data from the **real** frozen cache; never downloads. 13 variables (2° grids), 5 story regions and 42 IPCC regions (native series), 152 countries (area-weighted 2° squares). Verdicts, maps and follow-up checks with `trend_stats.py`; deeper checks with `trend_detective.climate_stats`. About 20 min; `--workers N` | `frontend/public/data/` |
| `make_country_regions.py` | Story regions as real borders (Natural Earth) | `data/catalog/regions_countries.yaml` |
| `crosscheck_country_grid.py` | Checks the country method (2° squares) against Ukraine's native series | printed table (quoted in `docs/10-methods.md`) |
| `check_data.py` | Validates every web-app JSON file against `schema/` (run before committing data) | exit code 0/1 |
| `analyze_climate.py` | Offline statistics for caller-supplied regional JSON; no downloads | User-selected statistics JSON |
| `make_climate_example.py` | Generates reproducible synthetic monthly or daily inputs for `analyze_climate.py` | `examples/climate/input.json` by default |

Any other producer of web-app data must write the same files in the same format; `check_data.py` is the gate.

The offline JSON analyzer has a separate contract from the web-app build outputs. See
[`docs/climate-statistics-pipeline.md`](../docs/climate-statistics-pipeline.md) and
`schema/climate-{input,output}.schema.json`.
