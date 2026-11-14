# backend

Python API and analysis engine (planned: FastAPI). See `docs/04-architecture.md`.

- Statistics: reuse `.claude/skills/trend-stats/scripts/trend_stats.py` (copy unchanged into the
  backend package together with its tests, or import it) — do not fork the maths.
- Endpoints (planned): `/catalog`, `/series`, `/trend`, `/suggest`.
- Secrets from environment variables only (`.env`, see `.env.example`).
