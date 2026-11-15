# frontend — Trend Detective web app

Static site (React + TypeScript + MapLibre GL + Plotly). It reads precomputed JSON from
`public/data/` and **computes no statistics**: every number, verdict and sentence comes from the
stats pipeline. Plan: [`docs/planning/2026-11-14-webapp-plan.md`](../docs/planning/2026-11-14-webapp-plan.md).

> The data in `public/data/` are **real NASA POWER (MERRA-2) data** from the frozen cache in
> `data/cache/`, built by `scripts/make_app_data.py` (`provenance.synthetic = false`). The app still
> shows a banner if any file is ever flagged `synthetic: true`.

## Run it (Windows PowerShell)

```powershell
cd frontend
npm install
npm run dev            # http://localhost:5173
```

## Check it

```powershell
npm run build          # type-check + production build into dist/
npm test               # unit tests + every JSON file against schema/
npx playwright install chromium   # once
npm run smoke          # opens every route in a browser (needs `npm run build` first); `$env:SMOKE_PORT = "4321"` picks another port
npm run lint
```

## Screens and routes (hash routing, works on GitHub Pages without rewrites)

| Route | Screen |
|---|---|
| `#/` | Explore: full-screen map, filter bar, legend chip, one suggested question |
| `#/?var=precip&show=clear&panel=quick&region=sahel` | URL state: variable, filter (`all`, `clear`, `clear_pos`, `clear_neg`), open panel (`quick` or `regions`), region, question (`q`) |
| `#/?var=t2m&s=mam&vs=world` | Map view: `s` = months averaged each year (`djf`, `mam`, `jja`, `son`; whole year when absent), `vs=world` = the change compared with the world average (ADR-011) |
| `#/?var=t2m&panel=area&area=-46,46,-20,62&area2=-75,34,-50,44` | "Your own area": a box as west,south,east,north (drawn on the map or typed), optionally a second box to compare with; computed in the browser |
| `#/?tour=1` | Starts the 25-second guided tour |
| `#/case/01`, `#/region/<id>?var=<var>` | Full analysis: answer strip, chart, map, findings; secondary sections collapsed |
| `#/compare/<a>/<b>?var=<var>` | Two regions and the trend of the gap between them |
| `#/catalog?topic=&place=` | All catalog variables with filters |
| `#/methods?s=<section>` | Methods; `s` scrolls to a section |
| `#/about` | What the tool is, data sources, AI disclosure, code |

Every overlay is a closable panel (`components/Panel.tsx`): close button, Escape, focus returns to
the opener. The noise budget of the Explore view is a test in `tests/smoke.spec.ts`.

## Where things live

| Path | What |
|---|---|
| `../schema/*.schema.json` | The data contract shared with the stats team (single source of truth) |
| `src/data/types.gen.ts` | Types generated from the schema: `npm run gen:types` after any schema change |
| `src/data/load.ts` | Fetch + cache + Ajv validation of each file |
| `src/strings/en.ts` | All interface copy (English) |
| `src/theme/` | Colour tokens (light/dark) and data palettes (ColorBrewer, Okabe-Ito) |
| `src/components/TrendMap.tsx` | MapLibre map: the grid is painted into a Web Mercator canvas; full colour = passes FDR, faded = could be chance, dots when zoomed in |
| `src/lib/stats.ts`, `src/lib/area.ts` | The only statistics computed in the browser: the yearly trend test for an area the visitor draws. A port of `trend_stats.py`; `stats.test.ts` checks it against `stats.fixture.json`, written by `python scripts/area_stats.py --fixture frontend/src/lib/stats.fixture.json` |
| `src/components/AreaPanel.tsx`, `VsWorld.tsx`, `LinesChart.tsx` | The answer for a drawn area; a region next to the world average |
| `public/data/series/` | One mean per year for every 2° square (binary), read by the area tool |
| `src/components/SeriesChart.tsx` | Monthly anomaly bars, Sen trend line and 95% fan |
| `public/basemap/` | Natural Earth coastlines and borders (Ukrainian point of view), built by `scripts/make_geo.py` |

## Rebuild the data

```powershell
python scripts/make_geo.py                 # basemap + data/regions/regions.geojson
python scripts/make_app_data.py           # real data from data/cache/ (needs requirements.txt)
python scripts/check_data.py               # validate public/data against schema/
```
