# 04 — Architecture (target)

Status: **draft** — confirm stack choices via ADRs before building.

## Overview
```
 ┌──────────── Frontend (static web app) ─────────────┐
 │ Wizard (what/where) → Variable picker (catalog)    │
 │ Map (MapLibre): region select + trend-map layer    │
 │ Time-series chart (raw / anomalies / trend + CI)   │
 │ Verdict card · Years-until-detectable · Export CSV │
 │ Case files (guided demos) · Glossary · Methods     │
 └───────────────▲───────────────────────▲────────────┘
                 │ JSON (REST)           │ static tiles / JSON
 ┌───────────────┴────────┐   ┌──────────┴──────────────┐
 │ Backend API (FastAPI)  │   │ Precomputed assets      │
 │ /catalog               │   │ trend maps (slope,p,FDR)│
 │ /series?var&region     │   │ case-file series        │
 │ /trend  (analysis)     │   │ (built by scripts/)     │
 │ /suggest (SI, grounded)│   └──────────▲──────────────┘
 └───────┬────────────────┘              │
         │                               │
 ┌───────▼─────────── Data layer ────────┴─────────────┐
 │ 1. Cache: monthly NetCDF/Zarr subsets (data/cache)  │
 │ 2. Live: NASA POWER API (no-login point/region)     │
 │ 3. Live (stretch): Giovanni / Harmony / earthaccess │
 │    with Earthdata token held server-side            │
 └─────────────────────────────────────────────────────┘
```

## Components
| Component | Responsibility | Proposed tech |
|---|---|---|
| Variable catalog | Curated variables, definitions, units, sources, DOIs, biome hints | `data/catalog/variables.yaml` → served as JSON |
| Fetchers | Download/subset/cache NASA data; idempotent; log provenance | Python: `earthaccess`, `harmony-py`, `requests`, `xarray`, `netCDF4` |
| Analysis engine | Series → QC → monthly → anomalies → trend tests → verdict JSON | Python: numpy, scipy, pandas; reference `trend_stats.py` |
| Trend-map builder | Per-pixel Sen's slope + modified MK + FDR → raster/tiles | Python + xarray, offline script |
| API | Thin REST layer with response caching | FastAPI + uvicorn |
| Frontend | Wizard, map, chart, verdict, case files | React + Vite + TypeScript, MapLibre GL, Plotly or ECharts |
| SI partner | Question/region type → catalog variables; explanation of computed stats | Google Gemini (`gemini-3.8-flash`) on Vertex AI, called from a FastAPI service on Cloud Run (`backend/trend_detective/assistant/`, ADR-009); prompt grounded server-side on the app's JSON + Methods page; outputs labelled as SI |
| Hosting | Public, no-login, stable for judging period | Frontend: Vercel/Netlify/GitHub Pages; API: Render/Fly/HF Spaces |

## Trend analysis contract (`/trend` response)
```json
{
  "variable": "T2M", "region": {"type": "bbox", "bounds": [22.0, 44.0, 40.5, 52.5], "land_only": true},
  "period": {"start": "1981-01", "end": "2025-12"}, "n": 540, "frequency": "monthly",
  "deseasonalized": true,
  "sen_slope_per_decade": 0.52, "sen_ci95_per_decade": [0.44, 0.60], "units": "K/decade",
  "mk": {"method": "yue_wang", "z": 7.9, "p": 1e-12, "tau": 0.24},
  "ols": {"slope_per_decade": 0.51, "ci95": [0.40, 0.62], "p": 1e-9, "n_eff": 120, "r1": 0.63},
  "total_change": 2.3, "percent_change": null,
  "years_to_detect": 14.2, "record_years": 45.0,
  "verdict": {"level": "strong", "text": "..."},
  "provenance": {"dataset": "...", "version": "...", "doi": "...", "accessed": "..."}
}
```
(Values above are placeholders, not results.)

## Non-functional
- Every API response carries provenance.
- No secrets in the frontend; SI and Earthdata calls only from the backend.
- Graceful degradation: if a live source fails, fall back to cached data and say so.
- Performance target: regional series + analysis < 3 s from cache.
