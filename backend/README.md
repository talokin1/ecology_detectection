# backend

Python API and analysis engine (planned: FastAPI). See `docs/04-architecture.md`.

- Statistics: reuse `.claude/skills/trend-stats/scripts/trend_stats.py` (copy unchanged into the
  backend package together with its tests, or import it) — do not fork the maths.
- Endpoints (planned): `/catalog`, `/series`, `/trend`, `/suggest`.
- Secrets from environment variables only (`.env`, see `.env.example`).

## Offline JSON climate statistics

`trend_detective.climate_stats.analyze(payload)` computes descriptive statistics, trends,
seasonal profiles, daily indices, drought indices, uncertainty and document-wide FDR from
caller-supplied JSON. It supports all catalog variables without fetching data.

CLI: `python scripts/analyze_climate.py --input input.json --output statistics.json`.
See [input/output contracts and methods](../docs/climate-statistics-pipeline.md).
