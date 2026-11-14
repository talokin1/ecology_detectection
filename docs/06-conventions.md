# 06 — Conventions

## Language
- Everything committed is **English** (code, comments, docs, UI strings, commit messages).

## Git
- `main` is always deployable and holds the shared project info (README, docs, catalog, Claude config).
- One long-lived work branch per area, merged into `main` via small PRs several times a day:

  | Branch | Scope |
  |---|---|
  | `data` | `scripts/` fetchers, `data/cache/` + provenance sidecars, catalog verification |
  | `stats` | `backend/` analysis engine (`trend_stats.py`, unchanged), case-file results, `notebooks/` checks |
  | `viz` | `frontend/` web app: variable picker, region, charts, verdict card, case files |
  | `story` | Submission text, demo video script / slides, `09-references.md`, `08-si-usage-log.md` |

- Before starting work: `git switch <branch>` then `git merge main` to pick up the latest shared changes.
- Commits: Conventional Commits with requirement IDs — `feat(stats): add years-to-detect to verdict (R-14)`.
- SI-assisted commits keep the `Co-Authored-By:` trailer of the SI tool (disclosure metadata).
- Every PR uses `.github/pull_request_template.md`, references requirement IDs, and gets ≥ 1 human review
  (Claude review via `peer-review` skill or `code-reviewer` agent is in addition, not instead).
- Never commit secrets, `.env`, `.netrc`, or large raw data (> 50 MB) — document how to rebuild instead.

## Python
- Python ≥ 3.11; `ruff` for lint/format; type hints on public functions; `pytest` tests next to code (`tests/`).
- Use `pathlib`, no hard-coded absolute paths (team works on Windows).
- Time handling: pandas `PeriodIndex`/`DatetimeIndex` in UTC; monthly data indexed by month start.
- Units: keep source units in raw cache; convert in one place (catalog `convert` field); always label units.
- Fill values / scale factors decoded explicitly (`xarray` `mask_and_scale=True`, check `_FillValue`).

## Frontend
- TypeScript strict; components small and named by domain (`VerdictCard`, `TrendMap`).
- All user-facing copy in one strings file (easy review by storyteller).
- Colour palettes from `trend-viz` skill only.

## Data and provenance
- Every cached file has a sidecar `*.provenance.json`: source URL/short name, version, DOI, spatial/temporal
  subset, access date, script + git commit that produced it.

## Definition of Done
- Requirement acceptance criteria met and status updated in `02-requirements-traceability.md`.
- Tests pass; numbers checked by `stats-validator` if shown to users.
- SI usage logged if applicable.
- English copy reviewed.
