# 12 — Submission package (draft)

- Status: **draft for the team** (2026-11-15). SI-assisted (Claude, Anthropic); the concept, the name and
  the final wording are the team's (ADR-001). Logged in `docs/08-si-usage-log.md`.
- Marked **[TEAM]**: only the team can fill or decide. Marked **[VERIFY]**: re-check before submitting
  (CLAUDE.md: every number shown to judges goes through `stats-validator` first).
- Live app: https://talokin1.github.io/tellus/ · Repo: https://github.com/talokin1/tellus
- All numbers below come from the app's own data (`frontend/public/data/`, built 2026-11-15).

---

## 1. Project name [TEAM]
The app says **"Trend Detective"**; the repository was renamed **"tellus"**. Pick one and use it everywhere
(app `appName`, README, page title, video, slides). Options:
- **Trend Detective** — matches the challenge title; judges connect it instantly.
- **Tellus** (Latin "Earth") — short and distinctive; needs a subtitle, e.g.
  *"Tellus — an Earth System Trend Detective"*.

## 2. High-level project summary (~150 words)
> Is the soil in my region drying out? Is my country really warming? **[Name]** answers questions like
> these with NASA data, in plain words. Pick a place (any of 152 countries or 42 IPCC climate regions)
> and one of 14 NASA variables (air temperature, rain, soil wetness, water vapour, sunlight, haze,
> ozone and more), and get a verdict, from "strong evidence" to "no clear trend yet": **what** is
> changing, **how much** per decade, **how sure** we can be, and, on a world map that greys out squares
> where the trend could be chance, **where**. "No clear trend yet" is a real answer, often with how many
> more years of data it would take. Records run from 1981 (or since the satellite launched), with the
> seasons removed before any test. An AI assistant explains each result in the visitor's own language
> using only the app's computed numbers, and can suggest variables for a desert, a forest or a big
> city, citing news and research. [VERIFY count: 14, or 15 if GRACE ships]

## 3. Link to project demo [TEAM]
30-second video (script in section 9) or ≤ 7 slides (section 10). Must open logged-out in a private
window. Link: `________`

## 4. Link to final project
- App: https://talokin1.github.io/tellus/ (no login)
- Code: https://github.com/talokin1/tellus (public) [TEAM: confirm the repository is public]

## 5. Detailed project description

### What it does
A student, teacher or curious citizen asks a question such as *"Is the soil in southern Ukraine drying
out?"* and becomes a data detective:
1. **Find a variable** — 14 NASA variables, each with a one-sentence definition and "why it might
   change", filterable by topic and by type of place (desert, forest, farmland, city, cold places, …);
   a search bar ("What are you curious about? / Where?"); four guided example questions and a
   25-second tour; an AI assistant that suggests variables and places for a free-text question.
2. **Pick a place** — click any country or IPCC region on the world map (or read the trend of any
   2° square from the map). 11 of the 14 variables have a full answer for every place; snow cover,
   snow depth and sea ice are map-only.
3. **See the evidence** — the monthly record as differences from normal (seasonal cycle removed), the
   trend line and its 95% band, seasons, months and extreme months.
4. **Get a verdict** — "Strong evidence", "Evidence", "A hint, not proof", "No clear trend yet" or "Not
   enough data", with the rate per decade, total change and one plain sentence on how sure we are.
5. **Compare** — two places side by side, with a test on the *difference* of their trends; the world map
   shows where a variable moves in opposite directions.

Example from the live data [VERIFY]: in **southern Ukraine** the air warmed **+0.57 °C per decade since
1981 (95% range +0.42 to +0.73), strong evidence**, while root-zone soil wetness shows **no clear trend
yet (0.0 percentage points per decade, 95% range −0.6 to +0.7)**: grandma's garden may feel drier, but
the 45-year record cannot confirm it yet; the change is still small next to natural swings.

### How it works
- **Data** (NASA, cached and pinned by sha256 in `data/cache/MANIFEST.json`, large grids in a public
  data store, ADR-010): MERRA-2 reanalysis, GPM IMERG and CERES SYN1deg through the NASA POWER Zarr
  archive (1981/1998/2001–2025); AIRS satellite temperature and water vapour (2003–2025) via Earthdata
  OPeNDAP; [GRACE/GRACE-FO water stored on land (2003–2025) — VERIFY it is live].
- **Places**: area-weighted means (cos latitude) over country and IPCC AR6 region outlines on a 2° grid.
- **Statistics** (`docs/10-methods.md`): calendar-month anomalies → Sen's slope + Mann-Kendall with the
  Yue-Wang autocorrelation correction (primary) → OLS with lag-1 effective sample size (secondary) →
  verdict = the weaker of the two → headline = the most cautious of the full record, without the first
  two years, without the last two years, and on yearly means. Maps: per-square tests with Benjamini-
  Hochberg false-discovery control. "Years until detectable" (Weatherhead et al., 1998) for weak trends.
  Gaps are never filled and no value is invented; a place without enough data is left out.
- **Validation**: an AI-assisted re-computation (Claude, with separate code reading the raw grids)
  reproduced the headline verdicts and its notes were fixed [TEAM: add the human science lead's
  review once done]; a Monte-Carlo check of false-alarm rates (300 synthetic series) chose the Yue-Wang
  correction; the cached series match the live NASA POWER API (11 of 11 checkable variables).
  [TODO: one comparison with a published or Giovanni trend, see judge-panel fix 4]
- **AI assistant** (optional, clearly labelled): Google Gemini on Vertex AI, server-side. It sees only
  the app's computed results through read-only lookup tools, flags any number that is not in our data,
  answers in the visitor's language, and may search the web for context with cited sources, never for
  our statistics.
- **Stack**: Python (numpy, scipy, xarray, pandas) precompute → static JSON validated by JSON Schema →
  React + MapLibre + Plotly on GitHub Pages; FastAPI on Cloud Run for the assistant. Tests: Python
  (pytest), Vitest and Playwright smoke tests in CI.

### Why it matters
Trend claims are everywhere; tools that test them honestly are not. The app teaches the difference
between "it changed" and "we can tell it changed", shows that one place can warm while another cools,
and treats a non-significant result as useful information. It works for any country, so a classroom in
Kyiv, Nairobi or Lima can investigate its own region.

### Screenshots [TEAM]
2–3 images (JPG/PNG ≤ 10 MB): world map with a clear-trend filter; a place page with verdict and chart;
the assistant answering. Capture with `npx playwright` or by hand; no people in shot.

## 6. Use of Super Intelligence (not shown to judges)
> We used Claude (Anthropic) as a development assistant: summarising documentation, scaffolding
> documents, writing and reviewing code (SI-assisted commits carry a Co-Authored-By trailer), building
> data readers, and re-computing statistics with separate code as a cross-check (human review pending). Some teammates also used OpenAI Codex and a
> Grok-based agent team for code review and merges (see the log). The concept, the questions, the
> variable choices and the scientific interpretation are the team's. Inside the product, an AI
> assistant (Google Gemini on Vertex AI) explains already-computed statistics and suggests variables
> and places; it never generates data values, numbers it writes that are not in our analysis are
> flagged, web sources it uses are listed separately, and every answer is labelled as AI-generated.
> No AI-generated images or video are used. [TEAM: update if the video uses any AI media — it then
> needs a visible watermark.]

## 7. NASA Data (field text)
- NASA POWER (Prediction Of Worldwide Energy Resources), Zarr archive on AWS Open Data, POWER 10.0.0:
  monthly MERRA-2 meteorology (T2M, PRECTOTCORR, GWETROOT, EVLAND, TQV, TO3, FRSNO, SNODP, FRSEAICE),
  GPM IMERG precipitation (IMERG_PRECTOT) and CERES SYN1deg surface shortwave and aerosol optical depth
  (ALLSKY_SFC_SW_DWN, AOD_55_ADJ). https://power.larc.nasa.gov/ · https://registry.opendata.aws/nasa-power/
- MERRA-2 (GMAO) — https://gmao.gsfc.nasa.gov/reanalysis/MERRA-2/
- GPM IMERG — https://gpm.nasa.gov/data/imerg
- CERES SYN1deg — https://ceres.larc.nasa.gov/
- Aqua/AIRS L3 Monthly Standard Physical Retrieval (AIRS-only) 1°×1° V7.0, AIRS3STM 7.0, GES DISC,
  https://doi.org/10.5067/UBENJB9D3T2H
- [VERIFY live] JPL GRACE/GRACE-FO Mascon CRI RL06.3Mv04, TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4,
  PO.DAAC, https://doi.org/10.5067/TEMSC-3JC634
- NASA Earthdata (CMR, OPeNDAP, Earthdata Login) for discovery and subsetting.

## 8. Space agency partner data and other references
Copy from `docs/09-references.md` (rows marked `used: yes`) [TEAM: fill the empty `used` cells first]:
- Methods: Mann (1945); Kendall (1975); Sen (1968); Yue & Wang (2004); Hamed & Rao (1998); Hirsch,
  Slack & Smith (1982); Santer et al. (2000); Weatherhead et al. (1998); Benjamini & Hochberg (1995);
  Wilks (2016); Gilbert (1987); Iturbide et al. (2020) for IPCC AR6 regions; Watkins et al. (2015) and
  Wiese et al. (2016) for GRACE mascons; Rodell et al. (2009).
- Maps and fonts: Natural Earth (public domain), Inter (SIL OFL 1.1), ColorBrewer palettes (Apache-2.0),
  Okabe-Ito palette.
- Software: numpy, scipy, pandas, xarray, netCDF4, earthaccess, shapely, PyYAML, jsonschema, FastAPI,
  uvicorn, google-genai, React, React Router, Vite, TypeScript, MapLibre GL JS, Plotly.js, Ajv, Vitest,
  Playwright, ESLint.
- Services: Google Cloud (Cloud Run, Vertex AI Gemini, Cloud Storage), GitHub Pages.
- Partner resources: none used in the final product [TEAM: confirm; KNMI Climate Explorer only if the
  planned validation is done].

## 9. 30-second demo video script
English narration or burned-in English subtitles; no minors; no NASA logos; ≤ 30.0 s (check with
`ffprobe`). Screen recording of the live app.

| Time | Picture | Words (≈ 65 words) |
|---|---|---|
| 0:00–0:04 | Title card: "Is the soil really drying out?" | "Grandma says her garden is drying out. Is she right?" |
| 0:04–0:12 | App: southern Ukraine → soil wetness → "No clear trend yet" | "NASA's 45-year record says: no clear trend yet. The change is still smaller than natural swings." |
| 0:12–0:19 | Same place → air temperature → "Strong evidence: +0.57 °C per decade" | "But the air? Strong evidence of warming: 0.57 degrees per decade. Same place, two honest answers." |
| 0:19–0:24 | World map, "Clear trends only" switched on | "Any of 14 NASA variables, any country, with the chance trends greyed out." |
| 0:24–0:27 | Assistant explaining the verdict (English, or Ukrainian with burned-in English subtitles) | "An AI assistant explains the numbers the app computed, and flags any it can't trace." |
| 0:27–0:30 | Closing frame with name and URL | "[Name]. Be an Earth trend detective." |

(The team page already shows the team name, so the video opens on the hook.)
[VERIFY] the two numbers on screen at recording time.

## 10. Seven-slide outline (if slides instead of video)
1. Title — name, team, members, challenge.
2. Problem — many variables; trends differ by place; students cannot test significance.
3. Solution — screenshot of a place page; one-line value proposition.
4. Experience — question → map → verdict (three screenshots).
5. Science — NASA sources; Sen + autocorrelation-corrected Mann-Kendall + FDR; independent validation.
6. Case — southern Ukraine: soil "no clear trend yet" vs air "strong evidence of warming" (+0.57 °C
   per decade); plus one validated pair of places trending in opposite directions [TODO].
7. Impact and next steps — classrooms, any region, more NASA instruments; links.

## 11. Eligibility checklist (status 2026-11-15)
| Item | Status |
|---|---|
| All members on the team page, same Local Event, not waitlisted (R-36) | ⬜ [TEAM] |
| Every field filled, English (R-30) | ⬜ draft above |
| Demo ≤ 30 s or ≤ 7 slides, public link, works logged out (R-31) | ⬜ [TEAM] |
| Final project link public, loads logged out on another network (R-32) | 🟡 app public; test from another network; confirm repo public |
| ≥ 1 NASA dataset in the NASA Data field (R-33) | ✅ section 7 |
| References complete (R-34) | 🟡 section 8; fill `used` cells in `09-references.md` |
| SI usage described; SI media watermarked; no NASA branding (R-35, R-38) | 🟡 section 6; check the video |
| Both checkboxes ticked, "Submit for Judging", confirmation screenshot (R-37) | ⬜ [TEAM] |
| Before Sunday 23:59 local time of the Local Event (R-37) | ⬜ [TEAM] |

## 12. Judge-panel review (simulated, 2026-11-15): 4 / 4 / 4 / 4 / 2
Impact, Creativity, Validity, Relevance, Presentation. Fixed in this draft: the video script (wrong
place for +0.54, "years needed" that the soil card does not show), "independent validation" wording,
the summary (plain words first), "any 2° square" and "every variable" overclaims; in the app: About-page
repository link and source list, the raw-values help text naming POWER reanalysis for every source.
Still open, ranked:
1. Record the demo and add 3 screenshots; pick one name everywhere [TEAM].
2. One external validation line (a published trend or a Giovanni area average, e.g. MERRA-2 T2M for
   Ukraine) and the human science lead's review.
3. One validated example of opposite trends in two places (the challenge's own sentence).
4. A named gap from the challenge: GRACE (water, if it ships) or AIRS at one pressure level
   ("levels of the atmosphere").
5. A 10-minute test with two or three adult students or a teacher, quoted as evidence of impact.
