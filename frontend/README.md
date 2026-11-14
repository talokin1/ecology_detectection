# frontend — Trend Detective web app

Static site (React + TypeScript + MapLibre GL + Plotly). It reads precomputed JSON from
`public/data/` and **computes no statistics**: every number, verdict and sentence comes from the
stats pipeline. Plan: [`docs/planning/2026-11-14-webapp-plan.md`](../docs/planning/2026-11-14-webapp-plan.md).

> The data currently in `public/data/` are **synthetic** (`provenance.synthetic = true`), generated
> by `scripts/make_synthetic_data.py`. The app shows a banner while any synthetic file is loaded.
> Real files from the stats pipeline replace them one by one, in the same format.

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
npm run smoke          # opens every route in a browser (needs `npm run build` first)
npm run lint
```

## Screens and routes (hash routing, works on GitHub Pages without rewrites)

| Route | Screen |
|---|---|
| `#/` | World trend map, case 01 open on top (`?var=t2m&case=02`) |
| `#/case/01` | Case: question → where → over time → verdict → what we found |
| `#/region/<id>?var=<var>` | Same layout for any prepared region |
| `#/compare/<a>/<b>?var=<var>` | Two regions, two verdicts, "do the trends really differ?" |
| `#/catalog?topic=&place=` | All catalog variables with filters |
| `#/methods?s=<section>` | Methods; `s` scrolls to the section behind a "How do we know?" link |

## Where things live

| Path | What |
|---|---|
| `../schema/*.schema.json` | The data contract shared with the stats team (single source of truth) |
| `src/data/types.gen.ts` | Types generated from the schema: `npm run gen:types` after any schema change |
| `src/data/load.ts` | Fetch + cache + Ajv validation of each file |
| `src/strings/en.ts` | All interface copy (English) |
| `src/theme/` | Colour tokens (light/dark) and data palettes (ColorBrewer, Okabe-Ito) |
| `src/components/TrendMap.tsx` | MapLibre map: the grid is painted into a Web Mercator canvas; full colour = passes FDR, faded = could be chance, dots when zoomed in |
| `src/components/SeriesChart.tsx` | Monthly anomaly bars, Sen trend line and 95% fan |
| `public/basemap/` | Natural Earth coastlines and borders (Ukrainian point of view), built by `scripts/make_geo.py` |

## Rebuild the data

```powershell
python scripts/make_geo.py                 # basemap + data/regions/regions.geojson
python scripts/make_synthetic_data.py      # synthetic demo data (until real data exist)
python scripts/check_data.py               # validate public/data against schema/
```
