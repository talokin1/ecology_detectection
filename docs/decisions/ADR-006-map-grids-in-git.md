# ADR-006 — Commit the world-map grids the app uses (explicit whitelist)

- Status: Proposed (pending lead approval; data plan decision D2, merge plan v2 Q4)
- Date: 2026-11-14
- Deciders (names): _fill in_
- Requirement IDs: R-15, R-32

## Context
The world trend map (R-15) needs a global monthly grid. Building one from the POWER Zarr store takes
about 40 s per variable with no login (`scripts/fetch_grid.py`, `backend/trend_detective/grids.py`).
`main` ignores `*.nc` under `data/cache/` so that large raw files never reach git, and CLAUDE.md says
`data/cache` is "git-ignored if large". The static site (plan v2 decision 8) must build from the repo alone.

Measured on 2026-11-14 for T2M (1981-01 → 2026-09):
- 2° grid: **26.1 MB** per variable (area-conserving regridding; the global mean matches the native grid
  exactly: 14.288 °C in 1981, 14.955 °C in 2025).
- 1° grid: **97.9 MB** per variable, near GitHub's 100 MB hard limit.

## Options
1. Ignore all grids; every builder runs `fetch_grid.py` first (network needed, not reproducible offline).
2. **Commit only the grids the map uses, at 2°, each listed by name in `.gitignore`.**
3. Commit 1° grids, or use Git LFS (size limit / extra tooling for every team member).

## Decision (proposed)
Option 2. `.gitignore` keeps `data/cache/**/*.nc` and re-includes each map grid by its exact path
(today only `!data/cache/grids/merra2_T2M_2deg.nc`); no wildcard, so local test grids never slip in.
Each committed grid has a provenance sidecar and an entry in `data/cache/MANIFEST.json`.

## Consequences
- The map builds offline from a clone; ~26 MB per added variable, so each new grid is a deliberate
  `.gitignore` line plus a MANIFEST refresh by the data engineer.
- 2026-11-14: second grid added, `!data/cache/grids/grace_lwe_thickness_2deg_land.nc` (GRACE/GRACE-FO total
  water storage, 2002-04 → 2026-09, land cells only, 5.8 MB; `python scripts/fetch_grid.py --source grace`).
  Its time axis keeps months without a solution as all-NaN (33 months, including the 2017-07 → 2018-05 gap).
  Neighbouring 2° cells are not independent (mascons are ~3°), and glaciers/ice sheets count as land in the
  product mask, so their large negative values are ice loss; both are caveats in the sidecar.
- Other resolutions/variables are rebuilt with `python scripts/fetch_grid.py --variable <VAR> --resolution 2`.
- CLAUDE.md:66 should read: `data/cache   Pre-fetched NetCDF/Zarr/CSV (git-ignored if large, except map
  grids listed in .gitignore (ADR-006); document how to rebuild)` (lead edits CLAUDE.md).
