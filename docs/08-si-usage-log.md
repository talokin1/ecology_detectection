# 08 — Super Intelligence (SI / AI) Usage Log

Required by NASA Space Apps 2026 rules: the submission must describe how SI tools were used.
SI-generated images/videos need a visible watermark; SI-assisted code and data must be acknowledged
in descriptive text and metadata. SI must not be used to come up with the solution idea.

## Policy for this team
- Log every meaningful SI contribution below (one row per task, not per prompt).
- Code: keep the `Co-Authored-By` trailer in commits; mention SI assistance in the module docstring
  for substantially generated files (`"""... SI-assisted (Claude, Anthropic)."""`).
- Media: watermark "SI-generated" on any SI image/video frame.
- In-product SI features (e.g. variable suggestions, explanations) are labelled in the UI.

## Log
| Date | Who | Tool | What it was used for | Artifact(s) | Human review |
|---|---|---|---|---|---|
| 2026-11-14 | Lead | Claude (Anthropic) | Summarised challenge page, rules and data-access docs; drafted project setup docs, checklists, review skills and a reference statistics module | `docs/`, `.claude/`, `CLAUDE.md` | Lead |
| 2026-11-14 | Lead | Claude (Anthropic) | Repo onboarding review (found doc inconsistencies), git init, branch scheme proposal (approved by Lead), fixed primary-test wording in CLAUDE.md and architecture example | `README.md`, `CLAUDE.md`, `docs/00`, `docs/04`, `docs/06`, `requirements.txt` | Lead |
| 2026-11-14 | Lead | Claude (Anthropic) | Translated the team's Ukrainian plan v2 and statistics-methods notes into English (content and decisions are the team's) | `docs/planning/2026-11-14-plan-v2.md`, `docs/planning/2026-11-14-stats-methods.md` | Lead |
| 2026-11-14 | Lead | Claude (Anthropic) | Built the web app on branch `viz` from the team's plan v2 and web-app plan: React/MapLibre/Plotly frontend, JSON schema contract, synthetic-data generator (statistics via the team's `trend_stats.py`), geo/basemap script, tests. All data shown are synthetic and labelled as such in the UI | `frontend/`, `schema/`, `scripts/make_geo.py`, `scripts/make_synthetic_data.py`, `scripts/check_data.py`, `data/regions/` | Lead (pending) |
| 2026-11-14 | Molfarion | Claude (Anthropic) | Surveyed official and additional data sources (sizes, contents, access tests); wrote the POWER Zarr regional reader, its tests and fetch script; cross-checked `trend_stats.py` against an independent implementation on 7 real series | `docs/planning/2026-11-14-*.md`, `backend/trend_detective/power_zarr.py`, `backend/tests/`, `scripts/fetch_power_region.py`, `docs/decisions/ADR-003-*.md` | Molfarion (author self-review; second reviewer TBD) |
| 2026-11-14 | Molfarion | Claude (Anthropic) | Earthdata token check script; Earthdata helper (token from .env, sent only to *.nasa.gov, retries); MODIS NDVI (MOD13C2, OPeNDAP subsets) and GRACE-FO mascon regional readers with tests and fetch CLI; inspected real granules to confirm variable names, fill values and scale conventions | `backend/trend_detective/{earthdata,modis_ndvi,grace}.py`, `backend/tests/test_{earthdata,modis_ndvi,grace}.py`, `scripts/fetch_earthdata_region.py`, catalog, references | Molfarion (author self-review; second reviewer TBD) |
| 2026-11-14 | Molfarion | Claude (Anthropic) | Acquisition layer for objectives 1-2: catalog `access` field and unit/period fixes (solar radiation, IMERG), region presets file (example boxes only), `acquire.py` (get_series, fit-for-trend checks, region inventory), offline mode for Earthdata readers, inventory CLI, tests; 7 POWER variables added to the catalog (plain-language text pending team review); proposed case-region boxes (south_ukraine, north_europe, south_europe; IPCC AR6-based, pending team approval) and land-only averaging option; POWER daily store reader and daily-to-monthly aggregation (S2) with daily T2M_MAX/T2M_MIN/PRECTOTCORR for the case regions; measured sizes of all POWER stores and ~30 more CMR collections | `backend/trend_detective/acquire.py`, `data/catalog/{variables,regions}.yaml`, `scripts/region_inventory.py`, `backend/tests/test_acquire.py`, `docs/10-methods.md` | Molfarion (author self-review; second reviewer TBD) |
| 2026-11-14 | Molfarion | Claude (Anthropic), incl. 3 sub-agents | Data plan tasks: build script + freeze manifest (`scripts/build_data.py`, `data/catalog/build.yaml`), global grids for the world map (`grids.py`, `fetch_grid.py`; overlap regridding chosen after the centre rule shifted coastal cells), catalog `topic` + `how_measured` fields, citation texts, cache README, ADR-004 draft, Data Rods references marked discontinued; regenerated every cached series from committed code | `scripts/`, `backend/trend_detective/grids.py`, `backend/tests/`, `data/catalog/`, `data/cache/README.md`, `docs/09-references.md`, `docs/decisions/ADR-004-*.md`, `.claude/skills/nasa-data-access/` | Molfarion (author self-review; second reviewer TBD) |

## Draft text for the submission field "Use of Super Intelligence"
> We used Claude (Anthropic) as a development assistant: to summarise documentation, scaffold
> project documents, generate and review code (all SI-assisted commits are marked with a
> Co-Authored-By trailer), and to cross-check statistical calculations. The concept, variable
> selection and scientific interpretation were decided by the team. Inside the product, an SI
> assistant suggests catalog variables and explains already-computed statistics; it never
> generates data values, and its output is labelled in the interface.
(Update before submission.)
