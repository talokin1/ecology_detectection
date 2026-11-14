# Web app plan (visual team)

Nov 14, 2026 · branch `viz` · implements [plan v2](2026-11-14-plan-v2.md)

Status: **draft for team review**. Open questions are at the end. The plan does not change any
decision in plan v2; where it found a contradiction it asks instead of choosing.

## 1. Ground rules (from plan v2)

- Static site, no server. Everything the app shows comes from precomputed JSON in `public/data/`.
- **The app computes no statistics.** No slopes, CIs, p-values, rounding or verdict logic in the
  browser. It reads, validates and draws. Texts (`headline`, `sentence`, `Insight.text`) are shown
  verbatim.
- All UI copy (labels, buttons, empty states) lives in one file, `src/strings/en.ts`. English only.
- Colour only in the data. White background, black UI, Inter, 1 px borders, 6 px radius, no
  gradients, shadows, emoji, badges or decorative animation.
- No click leads into a void: every route and every map click has a defined state, including
  "Investigation not open yet" and "Not enough data to judge".

## 2. Stack

| Concern | Choice | Why |
| --- | --- | --- |
| Build | Vite + React 18 + TypeScript (strict) | Plan v2 decision 8; fast dev server, static output |
| Routing | React Router, **hash routes** (`#/case/01`) | GitHub Pages has no SPA rewrites; hash links never 404 |
| Map | MapLibre GL JS | Plan v2; open source, no API key |
| Basemap | Self-hosted Natural Earth GeoJSON (coastlines, country borders) in `public/basemap/` | No third-party tile server that can fail during judging; public domain |
| Charts | Plotly (`plotly.js-basic-dist-min` + `react-plotly.js`) | Plan v2; built-in PNG export for "Download PNG" |
| Font | Inter via `@fontsource/inter` (self-hosted, OFL) | No Google Fonts call; tabular figures |
| Validation | JSON Schema files in `schema/` + Ajv in the browser | Same schema validates in Python (`build_all.py`) and in the app |
| Types | Generated from `schema/` with `json-schema-to-typescript` | One source of truth; types cannot drift from the schema |
| Tests | Vitest + Testing Library; Playwright smoke test of every route | Fast unit tests; smoke test catches dead clicks |
| Lint | ESLint + Prettier | Conventions in `docs/06-conventions.md` |
| Deploy | GitHub Actions → GitHub Pages on push to `main` | Plan v2; public, no login |

Prerequisite: Node.js LTS is not installed on the lead's machine yet
(`winget install OpenJS.NodeJS.LTS`, then reopen the terminal).

## 3. Repository layout

```
schema/                     shared zone (stats + viz agree on every change)
  index.schema.json
  analysis.schema.json
  map.schema.json
  catalog.schema.json
frontend/
  fixtures/                 synthetic JSON in the exact schema format (dev only)
  public/
    data/                   real JSON, written by build_all.py
    basemap/                Natural Earth GeoJSON
  src/
    main.tsx, App.tsx, routes.tsx
    data/                   loader (fetch + cache + Ajv), generated types
    state/                  URL <-> app state (parse/serialize)
    theme/                  tokens.css, palettes.ts (RdBu, BrBG, PuOr, Okabe-Ito)
    strings/en.ts           all UI copy
    components/             TopBar, TrendMap, MapLegend, SeriesChart, VerdictCard,
                            EvidenceScale, InsightList, CaseCard, CompareView,
                            CatalogTable, CatalogFilters, ExportMenu, NotOpenYet
    pages/                  MapPage, CasePage, ComparePage, CatalogPage, MethodsPage
scripts/make_fixtures.py    generates frontend/fixtures/ (synthetic series run through trend_stats.py)
```

`frontend/fixtures/` vs `frontend/public/data/`: the dev server reads fixtures until the first real
file exists. Every fixture carries `provenance.synthetic: true`, and the app then shows a visible
"Synthetic data, not a result" banner. A synthetic number can never reach a screenshot unlabelled.

## 4. Routes and URL state

The URL is the single source of truth for what is on screen, so "Share link" is just the current URL.

| Route | Screen | Data |
| --- | --- | --- |
| `#/` | Map with case 01 card on top | `index.json`, `map/<variable>.json` |
| `#/map?var=<id>` | Map for another variable | same |
| `#/case/<case_id>` | Case: question → where → over time → verdict → what we found | `analysis/<region>__<variable>.json` |
| `#/region/<region_id>?var=<id>` | Case view for a prepared region that is not a named case | same |
| `#/compare/<region_a>/<region_b>?var=<id>` | Compare | 2 × analysis + `compare/<a>__<b>__<variable>.json` |
| `#/catalog?topic=&place=` | Catalog with filters | `catalog.json` |
| `#/methods#<anchor>` | Methods; `#anchor` targets the test behind a "How do we know?" link | `validation.json` + static text |

Unknown route or missing file → a page that says what is missing and links back to the map.

## 5. Screens → components

**Top bar (every screen).** Variable · region · period · source short name, plus "Share link". The
period is display-only: plan v2 forbids choosing the start year.

**Map.** `TrendMap` draws `map.json` as a raster: each grid cell coloured by `slope_per_decade` on a
symmetric diverging scale (`palette`, `limit` from JSON), stipple dots where `significant_fdr`,
hatched grey where `insufficient`. Prepared regions are outlined from `index.json`. Hover → cell
value and verdict word from JSON; click inside a prepared region → its case; click elsewhere →
`NotOpenYet` with the nearest prepared region. `MapLegend` explains colours, dots and hatching in
words ("dots: trend unlikely to be chance").

Rendering detail: the grid is drawn once into a canvas in Web Mercator rows and added as a MapLibre
canvas source; dots are a GeoJSON circle layer of significant cells only. A 1° global grid
(64,800 cells) renders in well under a second this way; GeoJSON polygons per cell would not.

**Case.** `RegionMap` (the same TrendMap zoomed to the region) → `SeriesChart` (anomalies as the
main line, raw monthly as a thin grey toggle, Sen line with 95% band, gaps as gaps, annotation text
from JSON) → `VerdictCard` (headline, `EvidenceScale`, rate with range, total change, one "How sure?"
line, "Two methods disagree" when flagged, years-to-detection sentence when present) →
`InsightList` (one sentence each + "How do we know?", footer "We ran N checks and show M" from
`insights_audit`).

**Compare.** Two `SeriesChart`s stacked on a shared x-axis, Okabe-Ito colours, two compact verdicts,
then the "Do the trends really differ?" answer from `compare.differ` and the neighbour suggestion.

**Catalog.** `CatalogFilters` (topic, place type) + `CatalogTable` (name, two-sentence definition,
source, period, link to its map). Data from `catalog.json`, built from `data/catalog/variables.yaml`.

**Methods.** Static text sections for the pipeline in plain words, the false-alarm chart from the
simulation, the literature cross-check (S12), the "we tested N, show M" audit per case, limitations
(reanalysis, grid size). Every number on this page comes from `validation.json`, not from the source
code.

**Export.** CSV of the series exactly as in JSON (no recomputation), chart PNG at 2× via Plotly,
Share link (copy URL).

## 6. What the viz side needs from the JSON contract

The UML in plan v2 is the starting point. To draw without computing, these fields must be added or
pinned down before the format is frozen:

| Gap | Proposal |
| --- | --- |
| `Region` shape | `{id, name, kind: bbox \| polygon, bbox: [w,s,e,n], geometry?: GeoJSON, centroid: [lon,lat]}` |
| `VariableRef` | `{id, name, units_label, palette, topic, place_types[]}` |
| Trend line and band | `trend.line: {dates[2], values[2]}` and `trend.band95: {dates[], lower[], upper[]}`; otherwise the browser would have to compute them |
| Gaps in series | `null` in `raw[]` / `anomaly[]` for missing months |
| Display strings for numbers | `trend.display: {rate, range, total}` already formatted ("+0.52 °C per decade") so rounding stays in Python |
| Chart annotation | `trend.annotation` string |
| "How sure?" line | `verdict.how_sure` string |
| Insight anchors | `Insight.methods_anchor` = an anchor id that exists on the Methods page |
| Insight audit | `insights_audit: {tested, shown, q}` (from stats-methods M11) |
| Map hover text | per-cell verdict word is too heavy; propose `map.levels[][]` as small ints (0–4) mapped to words in `strings/en.ts` |
| Map caption | `map.caption`: dataset, period, method |
| Map size | 1° grid, flat row-major arrays, values rounded in Python: about 0.5 MB raw, much less gzipped |
| Provenance | `{dataset, version, doi, accessed, processing[], synthetic: bool}` |
| Catalog filters | `topic` and `place_type` do not exist in `variables.yaml` yet (it has `biomes`); stats/data to add them |
| Methods numbers | `validation.json` produced by `validate_type1.py` and the S12 cross-check |

## 7. Milestones

Mapped to the "Visual delivers" column of plan v2. Each milestone ends deployed, not "works on my
machine".

| # | Deliverable | Done when | Req IDs |
| --- | --- | --- | --- |
| V0 | Node installed, Vite scaffold, lint, tests, Pages deploy of an empty shell | Public URL opens in a private window | R-32 |
| V1 | Draft `schema/` + `make_fixtures.py` + fixtures for 3 cases + typed loader with Ajv | Fixtures validate; stats team signs off the schema → **freeze** | R-06 |
| V2 | Skeleton: routes, top bar, Map page with TrendMap, Case page with SeriesChart + VerdictCard, all on fixtures | Every route renders; synthetic banner visible | R-03, R-04, R-05, R-15, R-16 |
| V3 | Switch to the first real file (Ukraine, T2M) and real `map.json` | Numbers on screen equal the JSON, checked by `stats-validator`; deployed | R-02, R-04, R-05 |
| V4 | Insights panel, Compare, case mode, catalog filters, NotOpenYet | All three cases play end to end | R-01, R-10, R-12, R-14, R-15 |
| V5 | Export (CSV, PNG, link), Methods page, dark theme, contrast and keyboard audit | WCAG AA contrast passes in both themes; every chart has alt text | R-34, R-30 |
| V6 | Feature freeze; Playwright smoke on every route; `judge-panel` run; 3-person test | A first-time visitor retells the verdict and one insight within 3 minutes | DoD of plan v2 |

V1 is the critical path for both teams: the stats team cannot freeze `analysis.json` alone, and
the viz team builds on fixtures from that moment on.

## 8. Quality checks

- Unit tests: URL state round-trip, verdict level → scale segments, loader rejects invalid JSON.
- Schema tests: every file in `fixtures/` and `public/data/` validates in CI.
- Smoke test: every route and every case opens with no console errors.
- Accessibility: keyboard reachable controls, visible focus, WCAG AA contrast, alt text from
  `verdict.sentence`, meaning never encoded by colour alone (dots, words, signs).
- References: Natural Earth, Inter, MapLibre, Plotly, React and other libraries go into
  `docs/09-references.md` as they are added (R-34).

## 9. Open questions for the team

1. **Verdict when MK and OLS disagree.** Plan v2 decision 10 says "take the weaker verdict"; the
   Verdict section says "show the better of the two". Which one? (Stats lead.) The UI only shows
   `verdict.level`, but the card copy for "Two methods disagree" depends on it.
2. **Evidence scale: 5 segments for which levels?** There are four graded levels (none, weak,
   moderate, strong) plus insufficient. Proposal: 4 filled segments + insufficient shown as an
   empty hatched scale, or 5 segments if a "very strong" level is intended.
3. **Verdict colour.** The `trend-viz` skill suggests a green outline for strong; plan v2 says
   colour only in data and black UI. Proposal: follow plan v2 (black/grey scale) and update the
   skill.
4. **Map grid resolution and variables.** 1° global for T2M first? Which other variables get a
   `map.json` (budget about 0.5 MB each)?
5. **Country borders.** Natural Earth ships point-of-view variants; we should use the Ukrainian
   point of view so that Crimea is shown as Ukraine. Confirm.
6. **Requirements R-11 (wizard) and R-13 (SI suggestions).** Plan v2 replaces the wizard with
   catalog filters and has no server for an SI assistant. Mark both as `dropped` with reasons in
   `02-requirements-traceability.md`?
7. **Mockups.** Export the five mockup images from the shared doc into `docs/planning/img/` so the
   build can be checked against them.
8. **Stale docs.** `docs/04-architecture.md` (FastAPI backend, wizard) and `docs/visual_vision.md`
   on `story` (green/yellow badges, LaTeX sidebar, timeline slider) conflict with plan v2. Update
   them and record the static-site stack as an ADR?
