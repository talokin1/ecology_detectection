---
name: trend-viz
description: Visual language for the Earth System Trend Detective app and slides — trend maps, time-series charts, verdict cards, case-file screens, colour palettes, accessibility. Use whenever building or reviewing a chart, map, UI component, screenshot for the demo, or any colour/typography choice.
---

# Trend visualization

Goal: a student understands **what, where, how much, how sure** in 5 seconds, and a scientist finds
nothing misleading.

## Colour
- **Trend maps (diverging, centred on 0, symmetric limits)** — colour-blind safe ColorBrewer families:
  - temperature-like variables: `RdBu_r` (blue = cooling, red = warming)
  - water-like variables (precipitation, soil moisture, runoff, water storage, NDVI): `BrBG`
    (brown = drying/browning, teal-green = wetter/greener)
  - pollution (NO2, aerosols): `PuOr_r` or `RdBu_r` with legend text "cleaner ↔ more polluted"
- Limits: symmetric ±(98th percentile of |slope|), never auto min/max; label units per decade.
- Never rainbow/jet. Never encode meaning by colour alone (add sign, arrow, or text).
- Categorical series (≤ 5): Okabe–Ito palette (`#E69F00 #56B4E9 #009E73 #F0E442 #0072B2 #D55E00 #CC79A7`).
- Verdict colours: strong `#1B7837`-family outline + text label; none = neutral grey — do NOT use
  red/green as "good/bad"; a warming trend is not "green".

## Trend map
- Layer: per-cell Sen slope per decade; **stipple (dots) where FDR-significant** (q = 0.05); legend
  explains dots. Mask cells with insufficient data (hatched grey, legend "not enough data").
- Click a cell → open its time series panel. Hover tooltip: value ± CI, p, verdict word.
- Show the dataset name, period and method under the map (small caption).

## Time-series chart
- Raw monthly values: thin light-grey line (toggle). Deseasonalised anomalies: main line.
- Sen trend line in the series colour, with a translucent 95% CI band (fan from slope CI).
- Optional 12-month running mean (dashed, labelled) — never the trend itself.
- X axis years; Y axis with units; zero line for anomalies.
- Annotation in plain English on the chart: "+0.52 °C per decade (0.44–0.60)".
- Gaps shown as gaps (no interpolation across missing months).

## Verdict card
```
[icon] Strong evidence: getting warmer
+0.52 °C per decade  (likely 0.44 – 0.60)
Over 1981–2025 that is about +2.3 °C.
How sure? p < 0.001 · 540 months · method: Mann–Kendall (autocorrelation-corrected)
[What does this mean?]  [Download CSV]  [Methods]
```
For "no significant trend yet": show slope anyway, then "≈ N more years of data needed at this rate".

## Layout and type
- One primary question per screen; wizard ≤ 4 steps; persistent "Detective notebook" side panel with
  the current variable, region, period.
- Font sizes: chart labels ≥ 12 px, slide text ≥ 24 pt. Contrast WCAG AA.
- Dark/light themes must both keep diverging maps readable (test both).
- Every chart has alt text describing the trend in one sentence.

## Demo/slide images
- Export at 2× resolution; crop to the story; one message per image.
- SI-generated imagery must carry a visible "SI-generated" watermark; no NASA logos.

## Libraries
MapLibre GL (map), Plotly or ECharts (charts), `matplotlib` + `cartopy` for static figures in notebooks.
Use the same palettes across web and static figures (define once in `frontend/src/theme`).
