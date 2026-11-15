# 02 — Requirements Traceability Matrix

Every feature, PR and demo claim must map to a requirement ID.
Status: `todo` · `doing` · `done` · `verified` (independently checked) · `dropped` (with reason).
Priority: **M** = mandatory by challenge/rules · **S** = strongly scored (judging) · **C** = could.

## Challenge objectives (mandatory)
| ID | Requirement | Pri | Acceptance criteria | Owner | Status | Evidence |
|---|---|---|---|---|---|---|
| R-01 | Identify/select Earth-science variables that can be investigated for trends | M | User can browse/search ≥ 10 curated variables from ≥ 3 NASA sources, each with a plain-language definition and units | | doing | UI: `#/catalog` with topic/place filters; 12 variables with real data on the map (MERRA-2, CERES SYN1deg, GPM IMERG; ADR-008), 9 of them with regional answers. Data: catalog `access` field, 15 of 28 deliverable (13 POWER Zarr, GRACE, MODIS NDVI); `acquire.list_variables()`/`assess()`/`inventory()`; `scripts/region_inventory.py`; tests `backend/tests/test_acquire.py` |
| R-02 | Acquire the variable for a particular region | M | User selects a region (preset, bbox, or click) and the app retrieves the regional series; area mean is cos(lat)-weighted | | doing | UI: three sets of places: 152 countries (click any country), 42 IPCC AR6 world regions, 5 story regions with real borders (ADR-005 amendment 2, ADR-008); map click opens them. Data: Backend reader `backend/trend_detective/power_zarr.py` (bbox → cos(lat)-weighted monthly series, cached with provenance; 16 tests). Earthdata readers added: `modis_ndvi.py` (MOD13C2 NDVI via OPeNDAP subsets) and `grace.py` (GRACE/GRACE-FO mascon water storage), shared `earthdata.py`; CLI `scripts/fetch_earthdata_region.py`; backend tests 43 offline. Single entry point `acquire.get_series(variable_id, region)` (preset id from `data/catalog/regions.yaml` or any bbox; Earthdata variables served from cache only, so the app needs no token). Region set: 46 IPCC AR6 land reference regions as outlines (`ar6_*`, 43 built with POWER + GRACE; ADR-005 amendment 1). API endpoint and UI region selection still todo |
| R-03 | Generate and visualize a time series long enough for statistics | M | Chart shows raw + deseasonalised series, trend line, period, n; minimum length guard (warn if < 10 years / < 120 months) | | doing | Case 'Over time' chart: anomalies + raw toggle, trend line, period, n; insufficient state in UI. Data: cached POWER series cross-checked against the POWER REST API (11/11 checkable variables pass, `docs/planning/2026-11-14-power-rest-crosscheck.md`); CI data-freeze gate `scripts/check_cache.py` + `.github/workflows/data.yml` (Linux + Windows) |
| R-04 | Rate of change over time | M | Slope per decade (and total change over period, %) with 95% CI and units | | doing | Verdict card: rate/decade + likely range, total change, % for ratio variables; real NASA POWER data via `scripts/make_app_data.py` (1981–2025) |
| R-05 | Significance test (t-test / Mann-Kendall / CI) | M | Modified MK p-value + OLS t-test (effective n) shown; verdict text; validated by `stats-validator` | | doing | Verdict card 'How sure?' line: MK Yue-Wang + OLS n_eff; UI on real data: independent `stats-validator` re-computation of 8 headline claims (verdicts, map cells, daily indices) PASS WITH NOTES on 2026-11-15; notes addressed (pre-declared robustness line, region-average wording, outward-rounding note). Offline JSON pipeline 1.1.0 review fixes and independent numerical/cache checks: `docs/decisions/ADR-007-climate-statistics-review-fixes.md`, `backend/tests/test_climate_stats.py`; human scientific sign-off pending |
| R-06 | Visualization AND analysis in one tool ("full scope") | M | Both available in the same user flow without leaving the app | | doing | Map → case → verdict → findings in one flow (`frontend/`) |

## Challenge considerations (scored implicitly)
| ID | Requirement | Pri | Acceptance criteria | Owner | Status | Evidence |
|---|---|---|---|---|---|---|
| R-10 | Simple definitions of variables | S | Each catalog entry has ≤ 2-sentence definition + "why it might trend" | | doing | UI: definition + why it might trend for every variable. Data: all 28 entries have definition, why_it_trends, `how_measured`, `topic`; 7 new POWER texts pending team review |
| R-11 | Question-driven search (what / where) | S | Wizard of ≤ 4 questions returns ranked variable suggestions | | doing | Search in the top bar: “What are you curious about? / Where?” plus places, variables and questions (production UX plan B2) |
| R-12 | Demonstration examples users can watch | S | ≥ 2 guided "case files" playable end-to-end | | doing | 4 questions as hints on the map + 25-second guided tour; old links `#/case/01..04` open the full analysis (real data; answers rewritten from the real verdicts) |
| R-13 | SI suggests variables from region type / literature | C | Suggestions grounded in catalog; sources/rationale shown; disclosed as SI | | todo | |
| R-14 | Non-significant trends still informative | S | "Years until detectable" estimate + explanation | | doing | 'Years to detection' sentence on none/weak verdicts |
| R-15 | Regional opposite-sign trends ("where") | S | Per-pixel trend map with significance stippling, or two-region comparison | | doing | UI: world trend maps (T2M, PRECTOTCORR, GWETROOT) from the real 2° grids with BH FDR + Compare screen. Data: 2° T2M grid (26 MB, `grids.py`, `fetch_grid.py`; kept in git per ADR-006); case regions in ADR-005 |
| R-16 | Seasonal cycle handled | S | Deseasonalisation on by default for sub-annual data, toggle to view raw | | doing | Anomalies by default, 'Actual values' toggle |
| R-17 | Daily/monthly data support | C | Monthly default; daily aggregated to monthly | | doing | Daily POWER T2M_MAX/T2M_MIN/PRECTOTCORR feed the 'Deeper checks' (climate_stats daily indices, SPI/SPEI) for the 4 European regions |

## Submission rules (mandatory for eligibility)
| ID | Requirement | Pri | Acceptance criteria | Owner | Status | Evidence |
|---|---|---|---|---|---|---|
| R-30 | English in submission page and all linked materials | M | Repo, app UI, docs, slides/video subtitles in English | | doing | UI copy English only (`frontend/src/strings/en.ts`) |
| R-31 | Demo ≤ 30 s video or ≤ 7 slides, public link | M | Timed/ counted; opened in private browser window | | todo | |
| R-32 | Public final-project link, no login | M | Tested from private window + another network | | todo | |
| R-33 | ≥ 1 NASA data/resource used and listed | M | NASA Data field filled from `09-references.md` | | todo | |
| R-34 | All external resources listed in References | M | Code libs, datasets, images, fonts | | todo | |
| R-35 | SI usage disclosed; SI media watermarked | M | `08-si-usage-log.md` complete; watermarks visible | | todo | |
| R-36 | All team members registered for same Local Event, on Members tab | M | Checked on team page | | todo | |
| R-37 | Submitted before deadline (Sun 23:59 local event time) | M | Confirmation banner screenshot | | todo | |
| R-38 | No images/voices of minors; no NASA branding in generated content | M | Review of all media | | todo | |
| R-39 | FortiGuard Web Filter Classification requested for new site | C | Request sent | | todo | |
