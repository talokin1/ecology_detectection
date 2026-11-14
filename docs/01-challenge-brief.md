# 01 — Challenge Brief: "Be An Earth System Trend Detective!"

Source: https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/
(Details + Resources tabs, read 2026-11-14). Difficulty: Advanced. Subjects: Earth Science, Software.

## 1. Context
- Satellite instruments (MODIS, OMI, AIRS, GPM) and global models (MERRA-2, GLDAS) provide a huge
  number of variables. Two difficulties: (a) choosing variables that could indicate change,
  (b) analysing them.
- Key insight stated by the challenge: **the same variable can trend one way in one region and the
  opposite way in another, even when the same process drives both.**
- The tool must determine **what is changing, where, how much, and whether it is "significant."**
- Audience: high-school and college students, public with some science background →
  make them "data detectives".
- Competition: ~1,289 teams registered on this challenge (2026-11-14) — differentiation is essential.

## 2. Requirements
### Objectives (mandatory — "full scope" = visualization + analysis)
1. Identify Earth-science variables of interest that can be investigated for trends.
2. Acquire the variable for a particular region (most trends are not global).
3. Generate and visualize a time series long enough for statistical analysis.
4. Basic statistics: rate of change over time + significance test (t-test, Mann-Kendall,
   or confidence intervals).

### Potential considerations (optional, but scored implicitly)
- Simple definitions of variables.
- A short series of questions (what/where) that drives the variable search.
- A couple of demonstration examples the user can watch.
- SI (AI) to suggest variables likely to trend in an area, from news/papers or region type
  (desert, rainforest, tidal estuary, atmosphere above a large city).
- Daily/monthly data are easiest; hourly/3-hourly exist.
- A trend is interesting even if not significant; a longer record may make it significant.
- CUAHSI hydrology tools.
- Trends can be non-linear and hidden by seasonal cycles; linear trends are enough for scope.

### Submission rules (from Project Submission + Judging guides)
- English on the submission page and **all linked materials** (video may be in another
  language with English subtitles).
- Demo: **video ≤ 30 s** OR **slides ≤ 7** (incl. title/intro). Exceeding = not eligible.
- Public links, no login, for demo and final project. New website → request FortiGuard
  Web Filter Classification.
- ≥ 1 NASA data/resource for Global Award eligibility; all references listed; SI usage described.
- SI: images/videos watermarked; code/data acknowledged in text + metadata; SI must not be used
  to come up with the solution idea; no NASA branding in generated content.
- Team 1–6 people (Universal Event ≥ 2), all registered for the same Local Event.
- Deadline: Sunday 2026-11-15, 23:59 local time of the team's Local Event.

## 3. Resources listed by the challenge
NASA: Giovanni · Hydrology Time Series (Data Rods) · AppEEARS · NOAA Climate Data Online ·
NTRS article "Time-Series Analysis of Remotely-Sensed SeaWiFS Chlorophyll in River-Influenced
Coastal Regions" (20090042747).
Partners/other: KNMI Climate Explorer · article on trend tests · guide to statistical significance ·
CSA: RADARSAT Constellation Mission data, Geo.ca, SWOT, ecosystem monitoring page,
SAR Python tutorial.

## 4. Bottlenecks
| # | Bottleneck | Mitigation |
|---|---|---|
| B1 | Earthdata Login required (Giovanni, AppEEARS, Data Rods); Giovanni cloud time-series API = single point only; area averages via Harmony; AppEEARS async queue; timeouts on big regions × long daily series | Pre-fetch & cache curated monthly datasets; NASA POWER API (MERRA-2/CERES based, daily since 1981) for live point/region queries; EDL token server-side only |
| B2 | Variable chaos: cryptic names, units, fill values, scale factors | Curated catalog with plain-language definitions and unit conversions |
| B3 | Statistical traps: seasonality, autocorrelation, short records, sensor discontinuities, area weighting, multiple testing on maps | `trend-stats` skill defaults; `stats-validator` agent |
| B4 | Per-pixel trend maps are heavy | Precompute offline, serve as tiles/PNG + JSON |
| B5 | Public, stable hosting during weeks of judging | Static-first frontend; backend on a free tier with cached responses; fallback static JSON |
| B6 | Presentation limits (30 s / 7 slides, English) | Dedicated storyteller role; `submission-kit` skill |

## 5. Candidate differentiators (proposal — team must decide, see ADR-001)
1. Trend **map** (per-pixel slope + significance stippling), click a pixel → its time series.
2. "Detective verdict" with honest statistics (deseasonalised, autocorrelation-aware MK, Sen's slope + CI) in plain language.
3. "Years until detectable" estimate (Weatherhead et al., 1998) for non-significant trends.
4. "Opposing trends" mode: same variable, two regions, opposite signs, shared process.
5. Guided "case files" (demo investigations), incl. one local (Ukraine) case.
6. SI partner that maps questions/region type to catalog variables and explains computed numbers (grounded, never inventing values).
7. Reproducibility: CSV export, methods page, dataset DOIs.

## 6. Target technical outcome
Web app (map + time series + wizard + verdict) backed by a Python analysis engine and a curated
data layer (cached NASA datasets + live NASA POWER), public GitHub repo, live URL, 30-s demo video
with English subtitles (or 7 slides), and a complete submission page. Details: `04-architecture.md`.
