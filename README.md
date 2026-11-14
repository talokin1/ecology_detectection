# Earth System Trend Detective

> Working title — NASA Space Apps Challenge 2026 · Challenge: **Be An Earth System Trend Detective!**

A tool that helps students and the science-curious public **choose an Earth-science variable measured
by NASA missions or produced by NASA models, pick a region, see how it changes over time, and find out
what is changing, where, by how much, and whether the change is statistically significant.**

## Status
Project initialised. See `docs/02-requirements-traceability.md` for progress.

## How it works (planned)
1. **Ask** — a short wizard (what are you curious about? where?) suggests variables from a curated
   catalog of NASA datasets (MERRA-2, GLDAS, GPM IMERG, MODIS, OMI, AIRS, GRACE/GRACE-FO, NASA POWER).
2. **Look** — a map shows where the variable is rising or falling; click any place to see its time series.
3. **Test** — the seasonal cycle is removed, the trend is measured (Theil–Sen slope per decade with a 95%
   confidence interval) and tested (Mann–Kendall corrected for autocorrelation).
4. **Conclude** — a plain-language verdict, plus how many more years of data a not-yet-significant trend
   would need.

Methods: [`docs/10-methods.md`](docs/10-methods.md).

## Repository layout
| Path | Content |
|---|---|
| `backend/` | API and analysis engine |
| `frontend/` | Web application |
| `data/catalog/` | Curated variable catalog |
| `data/cache/` | Cached data subsets (rebuilt by `scripts/`) |
| `scripts/` | Data fetch and precompute scripts |
| `notebooks/` | Exploration |
| `docs/` | Requirements, architecture, methods, decisions, references |
| `.claude/` | Claude Code skills, subagents and settings used by the team |

## Branches
`main` is always deployable. Work happens in `data`, `stats`, `viz` and `story` and is merged into
`main` via small pull requests — see [`docs/06-conventions.md`](docs/06-conventions.md).

## Development
```bash
pip install -r requirements.txt
python -m pytest -q .claude/skills/trend-stats/scripts      # statistics reference tests
python .claude/skills/trend-stats/scripts/validate_type1.py # Monte-Carlo validation table
```
Copy `.env.example` to `.env` for Earthdata credentials (never commit `.env`).

## Offline JSON statistics

Analyze supplied regional daily/monthly/annual values without NASA access:

```bash
python scripts/analyze_climate.py --input examples/climate/input.json --output statistics.json
```

Install `requirements-climate-stats.txt` for the standalone dependency set. See
[input format, computed statistics and limitations](docs/climate-statistics-pipeline.md).
The bundled example data are synthetic.

## Use of Super Intelligence (SI)
This project uses SI tools (Claude by Anthropic) as a development assistant. See
[`docs/08-si-usage-log.md`](docs/08-si-usage-log.md).

## Data and references
[`docs/09-references.md`](docs/09-references.md). NASA data are used under NASA's open data policy.
NASA does not endorse this project.

## Team
See [`docs/05-team-and-roles.md`](docs/05-team-and-roles.md).
