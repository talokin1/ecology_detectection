# Web app review and improvement plan (visual team)

Nov 14, 2026 · branch `viz` at commit `6f99501` · reviews the live app against
[plan v2](2026-11-14-plan-v2.md) and the [web app plan](2026-11-14-webapp-plan.md)

Status: **for team review**. Nothing in the application code was changed. Items marked
**challenges plan v2** need a team decision (see section 7).

How this review was made: the built app was served locally and captured with Playwright at
1440×900 ("desk") and 390×844 ("mob"), in light and dark themes. Every screen listed in the brief
was captured, plus a Europe zoom, hover tooltips, the "not open yet" popup, keyboard focus, and
two extra states: a "No clear trend yet" region (`#/region/north_europe?var=soil`) and an "A hint,
not proof" region (`#/region/ukraine?var=soil`). Six independent reviewers each looked through one
lens: art direction, maps and data viz, student comprehension, scientific honesty, code and
accessibility, and a simulated jury. Every finding below was checked against the screenshots,
the JSON or the source. Findings that could not be reproduced are listed in section 8.
Screenshot names follow `<screen>__<desk|mob>__<light|dark>[__fold].png`, where `__fold` means
the first viewport only. The screenshots are not committed; section 9 says how to rebuild them.

All data are synthetic. This review judges design, wording and logic, not numbers. Example copy
below uses synthetic numbers only to show the pattern. Real copy must come from the JSON.

## Implementation status (Nov 14, 2026, branch `viz`)

All P0 and P1 items and P2-1, P2-2, P2-3, P2-4, P2-5, P2-7 are implemented on synthetic data.
Checks: `scripts/check_data.py` (69 files), 20 unit and contract tests, 20 browser smoke tests
(including the P0-1 fold check, the P0-6 popup check, the P1-11 keyboard check and the P1-12 edge
cases), lint clean.

Defaults taken where section 7 asks the team (change any of them in one place):

| Question | Default taken | Where to change |
| --- | --- | --- |
| Q1 display size | 48 px for the one rate number per screen | `--fs-display` in `frontend/src/theme/tokens.css` |
| Q2 answers that take a side | Kept ("Yes, the record backs Grandma…"); generated from the verdict | `case_answer()` in `scripts/make_synthetic_data.py` |
| Q3 "likely" | Removed everywhere; "95% range" instead | templates + `strings/en.ts` |
| Q5 evidence scale | 3 segments (hint, evidence, strong); "No clear trend" = empty, "Not enough data" = hatched | `EvidenceScale` in `components/VerdictCard.tsx` |
| Q6 insight filter | Unified at q = 0.05 with 95% whiskers (was 0.10); stats-methods M11 says 0.10 | `FDR_INSIGHT_Q` |
| Q7 landing variable | Unchanged: case 01 (soil) | `default_case` in `index.json` |
| Q8 null case | Case 04 "Only the south?" (Ukraine, soil), question fixed before computing | `CASES` |
| Q9 dark theme | Kept; maps sit on a light plate in both themes | `--map-*` tokens |

Not done: P2-6 (per-cell confidence ranges; adds about 0.5 MB per map, needs a decision),
P2-8 (precompiled validators). The real stats pipeline must adopt the new JSON fields (see the
`schema/` diff) and the template wording; `stats-validator` must run on the first real files.

SI disclosure: this review was prepared with SI (Claude, with reviewer sub-agents). Log entry in
`docs/08-si-usage-log.md` still to be added.

---

## 1. Verdict in 5 lines

1. **What works:** the colour discipline, the question-first cases (the "Grandma" hook), the
   weaker-of-two-tests rule, the audit of how many checks were run, and a Methods page that is
   better than almost anything in this challenge.
2. **Why it looks "so-so":** every section is the same white bordered box with a circled number
   and a 14 px heading. The most important number is 26 px. Nothing leads the eye, and that
   uniform-card look reads as generic generated UI.
3. **The answer is hidden.** On every case page the verdict starts below the fold (y ≈ 860 on
   desktop; on mobile it is two to three screens down). On the map, "how sure" is encoded so that
   faint colour can mean "small trend", "could be chance" or "outside the region".
4. **A scientist on the jury will stop at the wording.** "Very unlikely to be chance" and "likely"
   (meaning a 95% range) read as the p-value fallacy and clash with IPCC calibrated language.
   Several story lines also contradict themselves (sections 3.4 and 3.5).
5. **Single biggest lever:** one "readout" answer strip at the top of every case, region and
   compare screen: the answer sentence, the rate as a large number, its 95% range and the evidence
   scale, all from JSON. After that, the significance encoding on the map.

## 2. Scorecard (1–5)

| Criterion | Now | Evidence |
| --- | --- | --- |
| Impact | 3 | The Grandma case and plain verdicts are classroom-ready, but the answer sits below the fold and only 6 regions can be opened. |
| Creativity | 4 | The checks audit, the very-dry-months count, the trend of the A−B gap and the false-alarm chart are distinctive. The landing screen itself looks like a generic map dashboard. |
| Validity | 3 | The methods are strong, but the on-screen wording overclaims, the map conflates three meanings of "faded", and some template rules contradict the verdict they sit next to (3.5). Synthetic data cap this score until real data arrive. |
| Relevance | 3 | Only NASA POWER is in use, and 18 of 21 catalog rows say "Planned". This rises to 4 with real POWER files and one satellite variable in a case. |
| Presentation | 3 | Calm and consistent, but the answer is below the fold, the cards are uniform, mobile charts break, and the map popup collides with the tooltip. (The simulated jury gave 4; I score 3 because of mobile and the fold.) |

The simulated jury's view: not a Global Nominee while the data are synthetic. With real data,
one literature cross-check on Methods and the P0 fixes below, it would be among the top few
projects in this challenge on statistical honesty (Best Use of Science).

## 3. Findings, ranked by impact on judges and students

### 3.1 The answer is below the fold on every case, region and compare page
- **Screen and state:** `#/case/01`, `/02`, `/03`, `#/region/sahel?var=precip`,
  `#/compare/ukraine/sahel?var=t2m`, desk and mob. Screenshots: `case-01__desk__light__fold`,
  `region-sahel-precip__desk__light__fold`, `case-01__mob__light__fold`.
- **What you see:** above the fold are the question, a small map and the chart. "Strong
  evidence: getting drier" starts at y ≈ 860–905 on desktop and about 2,000 px down on mobile.
  The teaser "Is she right?" is never answered in words anywhere on the page.
- **Why it matters:** this fails the 5-second test for "how much" and "how sure". A judge with
  3 minutes may never scroll.
- **Fix:** P0-1 (readout strip and grid reorder).

### 3.2 On the maps, "how sure" collides with "how much", with "outside the region", and flips in dark theme
- **Screen and state:** world map in every variable; the case "Where" maps; dark theme.
  Screenshots: `map-t2m-case02__desk__light`, `case-01__desk__light__fold`,
  `region-sahel-precip__desk__light__fold`, `map-default__desk__dark`,
  `extra-europe-zoom__desk__{light,dark}`.
- **What you see:**
  - Non-significant cells are drawn by mixing the colour 62% toward the background
    (`frontend/src/components/TrendMap.tsx:65`). So a faded strong trend looks like a weak
    significant one: lightness carries both size and certainty.
  - On case maps, the area outside the region is faded with the same 62% (`TrendMap.tsx:164`,
    mask `fill-opacity: 0.62`). Neighbouring cells therefore look like "could still be chance".
    South of the Sahel box, a large significant wetting area shows as a flat grey-green block.
  - In dark theme the mix goes toward `#0f1114`. Faded cells become dark mud, and the darkest,
    strongest bins sink into the background, so the visual ranking of cells reverses between
    themes.
  - Stipple dots appear only from zoom 2.6 (`TrendMap.tsx:166`) and are never explained: the
    string `S.map.dots` exists in `en.ts:26` but nothing renders it. In the T2M field 79% of cells
    are significant, so when zoomed the dots form an even grey texture.
- **Why it matters:** a teenager cannot tell "small but sure" from "large but unsure". A
  scientist sees one mark meaning three things.
- **Fix:** P0-2.

### 3.3 Wording overclaims what a p-value or an FDR flag means
- **Screen and state:** verdict sentence on every case ("…and the change is very unlikely to be
  chance"), ranges ("likely −1.5 to −0.5"), map legend ("Full colour: unlikely to be chance"),
  tooltip and popup per cell ("unlikely to be chance"), glossary "Likely range". Screenshots:
  `case-01__desk__light`, `extra-hover-world__desk__light`, `methods__desk__light`.
- **Why it matters:**
  - "Very unlikely to be chance" is the textbook p-value fallacy. Our own glossary correctly says
    a p-value "is not the chance that the trend is real", so the page contradicts itself.
  - In IPCC calibrated language, "likely" means at least 66%. Climate judges will read our 95%
    range as a 66% range.
  - FDR controls the share of false alarms among flagged cells. It does not make a single cell
    "unlikely to be chance".
- **Fix:** P0-3.

### 3.4 The story contradicts itself in four visible places
- **Case 03 on the map page.** The case list and card show "Same rain, opposite ways · Strong
  evidence: getting drier". That is only the south's verdict, so a student reads "both drying".
  Screenshot: `map-default__desk__light`.
- **Compare, same-direction pair.** The question is "Does air temperature … change the same way
  in Ukraine and Sahel?" and the answer is "Yes, the two trends really differ." Both regions show
  "Strong evidence: getting warmer", so "Yes" answers the opposite of what was asked and "differ"
  is heard as "one warms, one cools". Screenshot: `compare-ukraine-sahel__desk__light`.
- **Case 02.** The question asks "…and in which season the most?". No finding answers it. Winter
  (+0.87, 95% range 0.65–1.11) looks fastest, but its range overlaps summer's (0.28–0.66) by
  0.003, so the season insight is suppressed and the question is left open. This is the ideal
  "not proven yet is still a result" moment, and it is lost. Screenshot: `case-02__desk__light`.
- **Case 01.** "Is she right?" is never answered in words. P0-1 covers this.
- **Fix:** P0-4.

### 3.5 Generated texts and counts disagree with the verdict they sit next to (stats templates)
Checked in the JSON:
- **Weak verdict next to a range that excludes zero.** `ukraine__soil`: headline "A hint, not
  proof", but the range is shown as "likely −0.8 to 0.0" while the actual 95% interval is
  [−0.754, −0.017]. That range comes from Mann-Kendall/Sen (p = 0.04, which would be "Evidence");
  the verdict is the weaker regression level (p = 0.06). The same page then says "Too noisy to
  tell yet…", which plan v2 reserves for level `none`. Screenshot:
  `region-ukraine-soil-weak__desk__light`.
- **A ratio against a season that shows no trend.** "Summers are drying out more than three times
  as fast as winters." Winter is −0.08, and its range crosses zero, so the ratio is meaningless.
- **A month counted as passing while its range crosses zero.** March in `south_ukraine__soil`:
  p = 0.056, q = 0.073, 95% whisker [−1.04, +0.02], drawn in full colour as "passes". The filter
  uses q = 0.10 and the whiskers are 95%, so the chart contradicts itself.
- **The audit line says something false.** "We ran 17 checks… 13 held up… The findings above use
  only those." Total change, signal-vs-noise and neighbour are not among the 17 checks. On
  `north_europe__soil` the page says "0 held up" directly under two findings. The Methods table
  says case 01 shows 2 findings, while the case page shows 4.
- **Two roundings of one number.** `ukraine__precip` says "dropped by about 0.31 mm/day" in the
  verdict and "(−0.30 mm/day)" in the insight.
- **The total-change box drops its range for precipitation.** `VerdictCard.tsx:46` shows
  `percent ?? total_range`, so cases with a percent never show the range.
- **Fix:** P0-5.

### 3.6 The compare screens do not show the comparison
- **Screen and state:** `#/case/03`, `#/compare/ukraine/sahel?var=t2m`. Screenshots:
  `case-03__desk__light`, `compare-ukraine-sahel__desk__light`.
- **What you see:**
  - Both panels use the same data-coloured bars and black trend lines, so the two panels look
    identical. Region identity is an 8 px dot.
  - On the shared ±2 mm/day axis, the −0.10 vs +0.05 trend lines look flat. The "opposite ways"
    story cannot be seen, even though the JSON already has "−19% of the average" and "+12% of the
    average"; neither is shown.
  - Okabe-Ito blue marks region A, the drying south, on a screen where blue bars mean "below
    normal". The vermillion Sahel outline vanishes on the red temperature map.
  - The answer box takes two thirds of the width and leaves the rest empty. It uses an inset black
    accent bar (`styles.css:305`), the classic generic callout.
  - Case 03 skips the "Verdict" and "What we found" steps, so the 5-step rhythm breaks.
- **Fix:** P1-3.

### 3.7 The landing map does not say what the tool is or what "it" is
- **Screen and state:** `#/`, desk and mob. Screenshots: `map-default__desk__light`,
  `map-default__mob__light`.
- **What you see:**
  - The tagline "Is the Earth around you really changing? Follow the evidence." exists only in
    `frontend/src/strings/en.ts:7` and is never rendered.
  - "Where is it changing?" does not name the variable.
  - About eight white bordered boxes float on the map: case card, 4 region labels, legend, caption
    and attribution. The panel title (22 px) and the card title (19 px) compete.
  - Region labels show a rate without its evidence level. "Northern Europe +0.3 points per decade"
    (No clear trend yet) looks exactly like "Southern Ukraine −1.0" (Strong).
  - Web Mercator gives the Arctic about a quarter of the T2M map, which visually overweights polar
    warming. Our own area means use cos(latitude) weights for exactly this reason.
- **Fix:** P1-1 (hero redesign), plus P1-6 and P2-4.

### 3.8 Mobile breaks in ways a judge on a phone will see at once
- **Screen and state:** every screen at 390 px. Screenshots: `map-default__mob__light__full`,
  `case-01__mob__light`, `extra-notopen__mob__light`.
- **What you see:**
  - No legend on the first map screen: it comes after the case card.
  - The variable picker is about four screens down.
  - The "Great Plains" label is clipped at the left edge.
  - On the chart, year ticks are rotated and overlap.
  - The trend annotation is cut off ("…(likely −1.5").
  - The season and dry-month SVGs scale their 12 px text down to about 7 px.
  - "Copy link" is hidden (`styles.css:367`).
  - The top-bar readout (variable · region · period · source) is hidden at ≤ 1080 px
    (`styles.css:361`), against plan v2's "the top bar always shows".
- **Fix:** P0-7.

### 3.9 The map popup and tooltip collide and leave the screen
- **Screen and state:** `#/?var=t2m&case=none`, click on land or sea. Screenshots:
  `extra-notopen__desk__light`, `extra-notopen-land__desk__light`.
- **What you see:**
  - The hover tooltip stays on top of the "Investigation not open yet" popup and hides its first
    line.
  - The popup is clipped at the right and bottom edges (`MapPage.tsx:140`,
    `Math.min(popup.x + 12, 9999)`).
  - The popup cannot be reached by keyboard, does not close on Esc, and does not take or return
    focus.
  - "1200 km" has no thousands separator, unlike "2,200 km" elsewhere.
- **Fix:** P0-6.

### 3.10 The hierarchy and type scale make it look generic
- **Screen and state:** all case pages. Screenshot: `case-01__desk__light`.
- **What you see:**
  - Seven equal bordered cards, each with a circled step number.
  - The column split changes three times down the page (612/632, then 710/730, then 1fr/1fr), so
    the gutters never line up.
  - The hero number `−1.0` is 26 px with tabular figures switched off (`styles.css:236`).
  - About ten off-scale sizes are in use (11.5, 13, 13.5, 15, 18, 19, 26 px). Weight 650 renders
    as 700 because only static font files are loaded.
- **Fix:** P1-2.

### 3.11 Units and words a 15-year-old trips on
- **Soil "points".** "−1.0 points per decade" is never explained. The catalog says "from 0 (dry)
  to 1 (saturated)", the raw series says "% of saturation", and the anomalies say "points".
- **Legend title.** "Change points per decade" reads as "change points".
- **Toggle.** "Change from normal" reads as month-to-month change.
- **Raw help text.** It says "Monthly values as measured", but GWETROOT is reanalysis model output.
- **Region names in generated text.** "in Sahel" is missing "the" (template).
- **Square size.** "Each square on the map is about 100 km wide" (Map) vs "about 50 km per grid
  square" (Methods) is unexplained. The map is regridded to 1°.
- **Fix:** P0-8.

### 3.12 All three hero cases are "Strong evidence"
None of the cases shows the honest path the challenge values ("a trend is interesting even if
not significant"). "No clear trend yet" and years-to-detection are visible only on non-case region
pages. Screenshots: `region-neurope-soil-none__desk__light`. **Fix:** P1-7.

### 3.13 The time-series form buries the trend
- **What you see:** 528 one-pixel monthly bars dominate the chart. The 95% band is faint (10%
  opacity) under bars at 78% opacity. `series.annual` (44 yearly anomalies) is in every
  `analysis.json` but is never drawn.
- **Screenshots:** `case-01__desk__light__fold`, `case-03__desk__light`.
- **Fix:** P1-4.

### 3.14 Accessibility
- **Text contrast.** `--text-3 #7a818b` is 3.93:1 on white and fails AA for the 12 px provenance
  text, ticks and evidence labels.
- **Graphics contrast.** "Off" evidence segments are about 1.26:1, below the 3:1 minimum for
  graphics.
- **Map ARIA.** The map container has `role="img"` (`TrendMap.tsx:383`) but contains clickable
  region labels and zoom buttons, which screen readers then ignore.
- **Variable picker.** It uses `role="radio"` without arrow-key handling.
- **Tooltip.** It has `role="status"`, so a screen reader announces every mouse move.
- **Motion.** There is no `prefers-reduced-motion` handling.
- **Dark theme.** The "Basemap: Natural Earth" attribution is black on black.
- **Fix:** P0-9, P1-11.

### 3.15 The verdict waits for the map library
`CasePage.tsx:6-7` and `ComparePage.tsx` import `TrendMap` statically. The 1.09 MB chunk named
"MapLegend" is really maplibre-gl, so on a school laptop the verdict cannot render until it is
downloaded and parsed. A case page loads about 2.8 MB of JS plus about 0.45 MB of map JSON.
**Fix:** P1-8.

### 3.16 The browser still formats or derives some numbers
This breaks the rule "numbers never computed in the browser":
- `MapLegend.tsx:5-42` computes the bin edges and rounds them.
- `MapPage.tsx:151` rounds the haversine distance to the nearest region.
- `TrendMap.tsx:373` and `MapPage.tsx:145` build sign and decimals for cell values. The tooltip
  shows "+0.2" for one cell and "+0.25" for the next.
- `SmallCharts.tsx` prints `ci95` to 3 decimals ("−0.038") next to `display` ("−0.03").
- `MethodsPage.tsx` uses `toFixed` on false-alarm rates and hard-codes "a third" and "near 5%".

**Fix:** P1-9.

### 3.17 The catalog reads like a backlog
18 of 21 rows say "Planned". "NASA POWER (MERRA-2 meteorology + CERES solar)" is repeated five
times and wraps. The topic tag "other" is lower case. Screenshot: `catalog__desk__light`.
**Fix:** P1-10.

### 3.18 Smaller visual defects
- **Evidence scale.** It has 4 segments, not the 5 of plan v2. At "Strong" it looks like a thick
  dashed rule. In chips it reads like an ellipsis. "No clear trend" fills 1 of 4 segments, so it
  looks like "a little evidence".
- **Region outlines on case maps.** Case 02 shows the Southern Ukraine outline cutting through
  Ukraine. Case 01 shows a long straight line across the top. Case 03 labels unrelated regions.
- **Extremes chart.** Ticks are uneven (0, 4, 7), x ticks fall on odd years, and there is no cue
  when the trend failed the filter.
- **Exports.** The chart PNG carries no source, period or "synthetic" stamp.

**Fix:** P1-5 and P2.

### Known limitations: do they matter?
| Limitation | Matters? |
| --- | --- |
| Synthetic regional series and world map disagree | Only for demo screenshots. It goes away if the real pipeline produces both from one grid. Do not record the video on synthetic data. |
| 1° cells blocky when zoomed | No. It is honest; keep nearest-neighbour resampling. |
| Case card covers the Americas on wide screens | Low. The recommended hero (section 5) removes the card from the map. |
| Overlapping region labels hidden at world zoom | Low. Showing the evidence level on the labels that are visible (P1-6) matters more. |
| `stats-validator` not run | Must run on the first real files **before** the new wording in P0-3 and P0-5 ships. |

---

## 4. Improvement plan

The submission deadline is **2026-11-15, 23:59 local time** (challenge brief), so P0 must fit in
about one working day for the visual team plus a few template changes for the stats team.
Effort: S = under 2 h, M = half a day, L = a day or more.

### P0: must fix before showing judges

**P0-1. Readout strip: the answer above the fold on case, region and compare pages.**
- **Layout.** Directly under the question, add one full-width strip (about 120 px tall on
  desktop, stacked on mobile):
  - left: the rate as the one large number, e.g. `−1.0`, then its unit at 14 px on the same
    baseline;
  - middle: the headline at 22 px with the evidence scale and "95% range −1.5 to −0.5 ·
    1981–2024";
  - right: the answer sentence.
- **Grid.** Reorder to row 1: readout; row 2: Over time (7 of 12 columns) | Where (5); row 3:
  What we found (7) | How sure and total change (5).
- **Copy.** The answer sentence comes from JSON. Example pattern (synthetic numbers): case 01:
  "Yes, the record backs Grandma: since 1981 the soil has become about 4.4 points drier, and very
  dry months went from about 1 to about 3 a year." Case 02: "Yes. Ukraine is about 2.6 °C warmer
  than in 1981. Winter looks fastest, but we cannot yet tell it apart from the other seasons."
  Case 03: "Yes, in opposite directions: the south got about 19% drier, the north about 12% wetter,
  and the gap between them is growing."
- **Files:** `frontend/src/pages/CasePage.tsx`, `ComparePage.tsx`, `components/VerdictCard.tsx`
  (extract a `VerdictSummary` used three times), `styles.css`, `strings/en.ts`.
- **JSON:** `verdict.answer` (one sentence answering the case question; generic for region pages)
  and `compare.answer`.
- **Acceptance:** at 1440×900 and 390×844, without scrolling, a person can read the headline,
  the rate, its range and the evidence scale on case 01–03, a region page and the compare page.
- **Effort:** M (viz) + S (stats).

**P0-2. One honest significance encoding on every map.**
- **Encoding:**
  - Non-significant cells: **desaturated at the same lightness** (mix toward a neutral grey of
    equal L\*), not lightened. Lightness then means size only; colour strength means certainty.
  - No-data land: diagonal hatch on the land layer, so it can never look like a faded cell.
  - Case "Where" maps: drop the mask. Draw the region outline 3 px in ink on a 6 px background
    halo; cells outside keep their world-map colour.
  - Dark theme: draw the map on a light-neutral plate (`#E9EBEE` land/ocean) inside the dark UI,
    so the palette behaves exactly as in light mode.
  - Stipple: always render the dots key when dots are visible. Raise opacity to 0.65, and draw the
    dots in background colour on the two darkest bins.
- **Legend copy:**
  - Row labels: "Clear trend" and "Could be chance".
  - Key: "Strong colour (and dots when zoomed in): passes the map-wide test for false alarms
    (q = 0.05). Greyish colour: not enough evidence in this square. Hatched: not enough data."
  - Case map caption: "Outlined: the area we averaged. Squares outside are shown for context."
- **Files:** new `frontend/src/theme/encoding.ts` (`cellRgba`, `legendSwatches`, driven by
  `layer.bins`), `components/TrendMap.tsx`, `components/MapLegend.tsx`, `theme/palettes.ts`,
  `theme/tokens.css`, `strings/en.ts`.
- **JSON:** none.
- **Acceptance:**
  - (a) Light and dark screenshots side by side rank cells from strongest to weakest in the same
    order.
  - (b) A cell just outside the Sahel outline has the same colour on the case map as on the world
    map.
  - (c) Every mark visible on any map is explained in its legend.
  - (d) Each faded swatch is within ΔL\* < 5 of its full swatch (check with the `dataviz`
    validator script).
- **Effort:** M.

**P0-3. Wording that a climate scientist accepts (templates and `en.ts`).**

| Now | New |
| --- | --- |
| "…and the change is very unlikely to be chance." | "…A drift this large would be very rare if nothing were really changing (p < 0.001)." |
| "…and the change is unlikely to be chance." (moderate) | "…This would be rare if nothing were changing (p = 0.01)." |
| "likely −1.5 to −0.5" | "95% range −1.5 to −0.5" |
| "Trend with its likely range" (chart legend) | "Trend line; band: 95% range of the trend" |
| Legend "Full colour: unlikely to be chance" | "Clear trend (passes the map-wide test)" |
| Tooltip/popup "unlikely to be chance" / "could still be chance" | "passes the map-wide test" / "not enough evidence in this square" |
| Glossary "Likely range" | "95% range: if we repeated this analysis on many similar records, 95 out of 100 such ranges would contain the true rate." |

- **Files:** `frontend/src/strings/en.ts`, `pages/MethodsPage.tsx`, and the stats templates for
  `verdict.sentence`, `trend.display.range`, `trend.annotation`, the `total_change` insight, and
  compare `display.range`.
- **JSON:** template text only.
- **Acceptance:** searching `frontend/public/data` and `en.ts` finds no "likely" and no
  "unlikely to be chance".
- **Effort:** S + S.

**P0-4. Remove the four story contradictions.**
- **Case list and map card for compare cases.** Show the pair headline, e.g. "North wetter, south
  drier: the gap is growing". JSON: `index.cases[].headline`, generated from `compare`.
- **Compare answer: branch on the signs and the level** (stats template, `compare.answer`):
  - opposite signs: "They move in opposite directions: Northern Europe is getting wetter,
    Southern Europe drier."
  - same sign: "Both are warming, but Ukraine is warming faster, and the difference is bigger
    than chance would usually produce."
  - level `none`: "Not clearly: we cannot yet tell the difference apart from natural swings
    (p = 0.24)."
  - Rename "Change of the gap" to "How fast the gap grows".
- **Answer every case question.** When a case asks about seasons, always emit a season insight.
  For case 02 (synthetic numbers): "Winter shows the fastest warming (+0.87 °C per decade; other
  seasons about +0.5), but the ranges still overlap, so we cannot yet say winter is truly faster."
  JSON: insight `kind: "season_unresolved"`.
- **Files:** `pages/MapPage.tsx`, `pages/ComparePage.tsx`, `strings/en.ts`.
- **Acceptance:** for each case, the question on screen has an explicit one-sentence answer.
  Case 03 never shows a single-region verdict as the case headline.
- **Effort:** S + S.

**P0-5. Make generated texts and counts agree with the verdict (stats team, with viz support).**
- **Ranges.** Round CI bounds outward and never print a signless "0.0". When the methods
  disagree, the shown range must belong to the method that set the level, or the card says
  "Mann-Kendall: evidence (p = 0.04). Regression: a hint (p = 0.06). We report the weaker."
- **`not_yet`.** Emit the "Too noisy to tell yet" insight only for level `none`, as in plan v2.
- **Season ratio.** Use ratio wording only if the slower season passes the filter with the same
  sign. Otherwise: "Summers dry out fastest (−2.0 points per decade); winters show no clear
  change."
- **Month and season whiskers.** Their confidence level must match the filter: either q = 0.05
  with 95% whiskers, or keep q = 0.10 and draw 90% whiskers.
- **Audit line** (`en.ts` `audit`). New copy: "Besides the main test, we ran 17 follow-up checks
  (12 months, 4 seasons, extreme months). 13 held up after correcting for running many tests at
  once; most of them repeat the main trend month by month. Findings marked ✓ come from these
  checks." Use the glyph or a word, whichever the type rules allow.
- **Rounding.** One rounding source per number: total change in the verdict sentence and in the
  insight must be identical.
- **Total change box.** `VerdictCard.tsx:46` shows the range and the percent, not one or the
  other.
- **JSON:** `insights[].tested: bool`, `verdict.decided_by: "mk" | "ols"`, `percent_change_ci95`.
- **Acceptance:**
  - No full-colour month or season mark has a whisker crossing zero.
  - The Methods "Shown as findings" column equals the count of ✓ findings on each case page.
  - The weak Ukraine-soil page shows no "0.0" bound and no "Too noisy" line.
- **Effort:** M (stats) + S (viz).

**P0-6. Fix the map popup.**
- **Behaviour:**
  - Hide the hover tooltip while the popup is open.
  - Clamp the popup inside the map container on all four sides.
  - Esc closes it, focus moves to its heading on open and returns to the map on close.
  - Take the distance as text from JSON.
- **Copy:** "We have built full investigations (chart, verdict, findings) for a few regions. This
  square: +0.2 °C per decade, passes the map-wide test. For the full story, open the nearest one."
- **Files:** `pages/MapPage.tsx`, `components/TrendMap.tsx`, `strings/en.ts`.
- **JSON:** `index.regions[].distance` is not per cell, so drop the km figure or add
  `neighbour_text`. Recommendation: drop it.
- **Acceptance:** clicking at each of the four corners of the map at 1440 and 390 px shows the
  whole popup with no tooltip on top.
- **Effort:** S.

**P0-7. Mobile essentials.**
- **Map:** a one-line legend strip inside the bottom of the map: "← drier ▮▮▮▮▮ wetter →
  points per decade".
- **Top bar:** show the variable · region · period readout as a 12.5 px second line under the
  banner, and keep "Copy link".
- **Plotly below 600 px:** `tickangle: 0`, one tick per decade, and the annotation moved into an
  HTML caption above the plot.
- **SVG small charts:** measure the container width and draw at 1:1, with row labels above rows.
- **Labels:** hide map labels that do not fit fully on screen.
- **Files:** `components/Shell.tsx`, `components/SeriesChart.tsx`, `components/SmallCharts.tsx`,
  `components/TrendMap.tsx`, `pages/MapPage.tsx`, `styles.css`.
- **Acceptance:** at 390×844:
  - the first map screen shows the colour key;
  - no text is smaller than 12 px;
  - no tick labels overlap;
  - no text is clipped;
  - "Copy link" is visible.
- **Effort:** M.

**P0-8. Units and words.**
- **Soil units:** "percentage points per decade". First mention: "soil wetness, in percent of
  saturation (0% = bone dry, 100% = soaked)". The catalog uses the same scale.
- **Legend title:** "Trend · points per decade".
- **Toggle:** "Compared with normal" | "Actual values".
- **Axis:** "Difference from the 1981–2010 normal (°C)".
- **Raw help:** "Monthly values from the NASA POWER reanalysis (a weather model corrected with
  observations), seasons included."
- **Map intro:** "Each square is 1° of latitude and longitude (about 100 km at the equator).
  Colour: how fast the value changed per decade since 1981." Take "since 1981" from `period`.
- **Region names in sentences:** "the Sahel".
- **Files:** `strings/en.ts`, `data/catalog/variables.yaml`, stats templates.
- **JSON:** `variable.units_long`, `region.name_in_sentence`, `series.anomaly_units_label`
  (replaces the `'%' → 'points'` mapping in `SeriesChart.tsx:50`).
- **Acceptance:** a first-time reader can say what "−1.0 points per decade" means from the page
  alone.
- **Effort:** S.

**P0-9. Contrast fixes.**
- `--text-3` becomes `#6b7280` (4.83:1 on white).
- Off evidence segments use `--line-strong` with a 1 px outline.
- The map attribution uses `var(--text-2)` in both themes.
- **Files:** `theme/tokens.css`, `styles.css`.
- **Acceptance:** an automated contrast check (axe or Lighthouse) shows no AA text failures in
  either theme.
- **Effort:** S.

### P1: big visual upgrade

**P1-1. Hero map screen: "Map + ledger"** (direction B in section 5). Build it as specified
there.
- **Files:** `pages/MapPage.tsx`, new `components/RegionLedger.tsx`, `TrendMap.tsx`
  (`onHover`/`highlightIds` props), `styles.css`.
- **JSON:** in `index.verdicts[k]`, add numeric `rate_value` and `ci95: [lo, hi]` (position only)
  plus `range_text`.
- **Acceptance:** with no scrolling at 1440×900, a person can name the variable, the region
  changing fastest in each direction, and which regions have a clear trend.
- **Effort:** L.

**P1-2. Layout and type system.**
- **Grid:** one 12-column grid with the same 5/7 split on every row of case and compare pages.
- **Cards:** remove card borders; separate sections with a 1 px `--line` rule and 32 px space.
- **Step numbers:** replace the circled numbers with a tabular kicker, "02 · Where", at 12.5 px
  text-2. Derive step numbers from one section-order array.
- **Type:** keep 28/22/14/12.5. Add one display size, **48 px / 1.0, weight 600, tabular
  figures**, used only for the one rate number per screen. **Challenges plan v2** (no size above
  28): the number is the product, and at 26 px it reads like a table cell.
- **Tokens:** add tokens for type sizes, spacing and the panel width; collapse the ten literal
  sizes into them.
- **Files:** `styles.css`, `theme/tokens.css`, `pages/CasePage.tsx`, `pages/ComparePage.tsx`.
- **Acceptance:**
  - Column edges line up from top to bottom of case 01.
  - Searching `styles.css` finds no `font-size` that is not a token.
- **Effort:** M.

**P1-3. Compare that shows the comparison.**
- **Bars:** draw the anomaly bars in neutral grey in compare mode.
- **Trend lines:** each region's trend line and 95% band in its Okabe-Ito colour (`#0072B2`,
  `#D55E00`).
- **New strip, "The gap: North minus South".** It shows the difference series with its own trend
  and band. It is the evidence for the answer.
- **Summary row above the charts** (from JSON): "Southern Europe: about 19% drier (strong
  evidence) · Northern Europe: about 12% wetter (evidence)".
- **Map:** region outlines in ink with "A" and "B" in the labels; label only A and B.
- **Answer:** at 5 of 12 columns beside the charts, with no inset bar.
- **Case 03** gets the compact verdict and findings for each region.
- **Files:** `pages/ComparePage.tsx`, `components/SeriesChart.tsx`, `components/TrendMap.tsx`,
  `styles.css`.
- **JSON:** `compare.gap_series: {dates, diff, line, band95}`, `compare.summary`.
- **Acceptance:** in case 03 the two trends visibly slope in opposite directions, and the gap
  strip's trend matches the number in the answer.
- **Effort:** M.

**P1-4. Time series: years first.**
- **Default view:** 44 annual bars from `series.annual`, coloured by sign. The Sen line is 2.5 px
  ink, drawn on top, with the band above the bars at 18% opacity.
- **Toggle:** "Each year | Each month | Actual values".
- **Axis and hover:** x ticks at 1981, 1990, 2000, 2010, 2020; hover "2010: +0.8 °C above
  normal".
- **Time of emergence:** a thin vertical marker at the emergence year, from `emergence.year`.
  Label: "On the trend line, the change grew bigger than a normal year-to-year swing around 1995."
- **Files:** `components/SeriesChart.tsx`, `strings/en.ts`.
- **JSON:** none (`series.annual` exists); emergence label text from the template.
- **Acceptance:** the trend and its band are visible at a glance on case 01–03 in both themes.
- **Effort:** M.

**P1-5. Evidence scale v2.**
- **Segments:** 5 segments (if the team confirms, see section 7), 8 px tall. Filled up to the
  level; the rest are 1 px outlined empty boxes. "No clear trend" shows all segments empty plus a
  flat marker.
- **Labels:** only the current level's label, in bold. Chips always show the word next to the
  glyph.
- **Logo:** use the same glyph as the logo instead of the stock chart icon.
- **Files:** `components/VerdictCard.tsx`, `components/Shell.tsx`, `styles.css`.
- **Acceptance:** a reader can tell "No clear trend" from "A hint" without reading the label.
- **Effort:** S.

**P1-6. Region labels carry the evidence word.**
- **Copy:** "Northern Europe / +0.3 points per decade · no clear trend". Use text-2 colour when
  the level is `none` or `weak`.
- **Style:** plain labels with a background halo and no box; only the active region is boxed.
- **Files:** `pages/MapPage.tsx`, `components/TrendMap.tsx`.
- **JSON:** none (`index.verdicts[].level` exists).
- **Acceptance:** every visible label shows its evidence word.
- **Effort:** S.

**P1-7. Add one honest null case.**
- Choose the region and variable **before** computing (to avoid cherry-picking), publish whatever
  comes out, and give it the same treatment as the other cases.
- Example with existing synthetic data: "Is all of Ukraine drying, or only the south?"
  (`ukraine__soil`, currently "A hint, not proof").
- **Files:** `index.json` (stats), no code.
- **Acceptance:** one of the cases on the map page shows "No clear trend yet" or "A hint, not
  proof" with its "more years needed" sentence.
- **Effort:** S.

**P1-8. Load the verdict before the map.**
- Lazy-load `TrendMap` inside a fixed-height `Suspense` box.
- Use `manualChunks: { maplibre: ['maplibre-gl'] }`.
- Draw the stipple into the canvas, or memoise it per layer, so a theme switch does not rebuild
  51k points.
- **Files:** `pages/CasePage.tsx`, `pages/ComparePage.tsx`, `vite.config.ts`,
  `components/TrendMap.tsx`.
- **Acceptance:** with network throttling (Fast 3G), the readout strip renders before the map
  chunk finishes.
- **Effort:** S.

**P1-9. No number formatting in the browser; all copy in `en.ts`.**
- Replace the browser-side formatting listed in 3.16 with JSON fields.
- Move the inline strings that the code review listed (CasePage, ComparePage, Shell, SeriesChart,
  SmallCharts, CatalogPage, most of MethodsPage) into `en.ts`.
- **JSON:**
  - `map.legend: {edges_text[], min_text, max_text}`
  - `map.value_decimals` (values pre-rounded)
  - `MonthTrend.display`, `Season.ci95_text`, `Month.ci95_text`
  - `validation.rows[].false_alarm_text` and `power_text`
  - `extremes.early.years`, `extremes.late.years`
- **Acceptance:** searching `src/` for `toFixed`, `Math.round` and `Math.abs` on statistics finds
  nothing outside chart geometry.
- **Effort:** M.

**P1-10. Catalog: "Ready to investigate" first.**
- **Section 1:** "Ready to investigate (3)", larger rows with a text link "Explore →".
- **Section 2:** "Coming next (18)", a compact table in text-2.
- **Copy:** shorten the source to "NASA POWER"; the full name goes on Methods. Fix the "other"
  topic tag.
- **Files:** `pages/CatalogPage.tsx`, `styles.css`, catalog build.
- **Acceptance:** the first screen of the catalog shows only explorable variables and the count
  of planned ones.
- **Effort:** S.

**P1-11. Keyboard and screen readers.**
- Move the map aria-label to the canvas and drop `role="img"` from the container.
- Variable picker and toggles: `aria-pressed` buttons, with no Link inside the group.
- Remove `role="status"` from the tooltip.
- When the case card closes, move focus to the case list.
- Respect `prefers-reduced-motion` (fitBounds, smooth scroll).
- Keyboard path on the map: with the canvas focused, arrow keys move a cell cursor and Enter
  opens it.
- **Files:** `components/TrendMap.tsx`, `pages/MapPage.tsx`, `styles.css`.
- **Acceptance:** every action on the map page works with the keyboard only, and VoiceOver or NVDA
  reads the region labels.
- **Effort:** M.

**P1-12. Caveat line and robustness for real data.**
- **Caveat line** under "How sure?": "Data: model-based reanalysis, about 50 km squares (map
  regridded to 1°). The trend is a straight line through 1981–2024; it shows what changed, not
  why."
- **Insufficient level:** hide the trend line, band and "Trend:" title when the level is
  `insufficient` (`SeriesChart.tsx`).
- **Schema:** allow `null` slope in the schema, so Python never invents one.
- **Empty states:** add empty states for empty `seasons` or `monthly_profile` (currently a crash
  in `SmallCharts.tsx`).
- **Error boundary:** add a route error boundary.
- **Fixtures and smoke routes:** insufficient data, gaps, `extremes: null`, empty insights.
- **Files:** `components/SeriesChart.tsx`, `components/SmallCharts.tsx`, `main.tsx`,
  `schema/analysis.schema.json`, `scripts/make_synthetic_data.py`, `tests/smoke.spec.ts`.
- **JSON:** `provenance.caveat`.
- **Acceptance:** the smoke test passes on the four new edge-case fixtures with no console errors.
- **Effort:** M.

### P2: polish

| # | Change | Files | JSON | Acceptance | Effort |
| --- | --- | --- | --- | --- | --- |
| P2-1 | Extremes chart: even integer ticks, decade x ticks, faded with "could still be chance" when `!passes_fdr`, subtitle from JSON | `SmallCharts.tsx` | `extremes.display` | The North Europe soil chart is visibly faded | S |
| P2-2 | Season chart: dashed reference line "All year −1.0" from `display.rate_value`; symmetric ticks; help text "Hollow marks could still be chance" (the marks are hollow, not faded) | `SmallCharts.tsx`, `en.ts` | none | The reference line matches the readout number | S |
| P2-3 | Export provenance: the PNG gets a footer annotation (dataset, period, "SYNTHETIC" while synthetic); the CSV header gets units, CI level, version/DOI and access date | `lib/exporters.ts`, `SeriesChart.tsx` | existing `provenance` | An exported PNG shows its source | S |
| P2-4 | Projection: map caption "This map enlarges areas near the poles." Make slide and video figures in Equal Earth (cartopy) | `MapLegend.tsx`/caption, notebooks | none | The caption is visible on the map page | S |
| P2-5 | 11-class palettes with a neutral centre; legend ticks at ±limit, ±limit/2, 0 from JSON | `palettes.ts`, `MapLegend.tsx` | `map.legend.edges_text` | A value of ±0.001 shows neutral | S |
| P2-6 | Tooltip with the cell's 95% range | `TrendMap.tsx` | `ci95_low[]`, `ci95_high[]` per cell (about +0.5 MB per map; decide) | The tooltip shows the range | M |
| P2-7 | Case maps: draw only the case's own region(s); hide zoom buttons under 500 px; `fitBounds` padding 24 | `TrendMap.tsx`, `CasePage.tsx` | none | No foreign outline crosses case 02's Ukraine | S |
| P2-8 | Precompiled Ajv validators; canvas source instead of `toDataURL` | `data/load.ts`, `TrendMap.tsx` | none | The main chunk shrinks | S |

### Suggested order for the next 24 hours
1. Stats team: template changes P0-3, P0-4 and P0-5, plus `verdict.answer`, then run
   `stats-validator` on the first real files.
2. Visual team: P0-1, P0-2, P0-6, P0-9 (morning); P0-7 and P0-8 (afternoon).
3. If time remains: P1-2, P1-4 and P1-6 give the largest visual gain per hour. P1-1 is the
   showpiece but L-sized; build it only if P0 is green by midday.
4. Record screenshots and the video only after real data and the P0 fixes.

---

## 5. Bold directions for the hero map screen

All three keep colour in data only, render numbers only from JSON, and work at 390 px.

### A. "Full-bleed readout"
- **Layout (1440×900):** the map fills the whole area under the top bar. There is no left rail;
  the variable switch is a segmented control at the top left of the map ("Air temperature |
  Precipitation | Soil wetness"). At the bottom left there is one readout panel (420 px wide):
  case number, question, the large rate number, headline, evidence scale, answer sentence and
  "Open investigation →". "‹ Case 1 of 3 ›" steps through the cases.
- **The eye sees first:** the colour field, then the one large number in the panel.
- **Interaction:** stepping a case moves the camera to its region (instant under reduced motion)
  and outlines it; hover shows the cell tooltip; clicking a region opens its case.
- **Pros:** cinematic, ideal for a 30-second video.
- **Cons:** the panel still covers part of the map; region comparison needs clicks; on mobile the
  panel becomes a bottom sheet.

### B. "Map + ledger" (recommended)
- **Layout (1440×900):**
  - **Left rail, 280 px:**
    - Variable list as three compact rows; each row is the name plus its words ("drier / wetter").
    - Below the list, three cases, each showing its answer line.
  - **Main area, upper about 60% (about 470 px):**
    - The map.
    - Title over the map, top left, at 22 px, taken from the variable's words: "Where is the soil
      getting drier or wetter?". Under it at 12.5 px: "Trend per decade · 1981–2024 · NASA POWER".
    - A one-line legend strip along the bottom edge of the map.
    - No floating case card.
  - **Main area, lower about 40%: the ledger, "Prepared regions, ranked".** One row per region, 6
    rows, sorted by rate. Each row has:
    - the region name, right-aligned, 14 px;
    - a dot-and-whisker mark on one zero-centred axis that is shared by all rows. The dot is
      filled when the level is moderate or strong and hollow otherwise; its colour is the map's
      palette bin. The whisker shows the 95% range in ink.
    - the rate as tabular text;
    - the evidence glyph and its word.
  - The row of the active case is bold and has "Open case 01 →".
- **The eye sees first:** the colour field and the title question. A second later, the ledger,
  where opposite signs fall on either side of the zero line. That is the challenge's key insight
  ("the same variable can trend one way in one region and the opposite way in another") made
  visible without a click.
- **Interaction:**
  - Hovering a row highlights that region's outline on the map, and hovering a region highlights
    its row.
  - Clicking a row or a region opens the case.
  - Switching the variable re-sorts the ledger (instant under reduced motion).
  - Clicking empty map shows the clamped "not open yet" popup, which also highlights the nearest
    row.
- **Mobile:** the map at 55% of the viewport height with the legend strip, then the ledger, then
  the cases. The ledger is the readable part on a phone, which is exactly where the map is weakest.
- **JSON:** `index.verdicts[k].rate_value`, `ci95`, `range_text` (P1-1).
- **Why recommended:** it adds information instead of decoration, turns one number into context
  a 15-year-old reads at a glance, gives the app a memorable signature mark (the ledger, reused on
  slides), and removes the case card that covers the Americas.

### C. "Three small worlds"
- **Layout:** three equal world maps in a row (temperature, precipitation, soil), each about
  360 px wide, with its own one-line readout underneath ("Warming almost everywhere; fastest in
  the Arctic"), all on the same grid. Below them, the cases.
- **The eye sees first:** three different patterns side by side, so "variables behave
  differently" is understood immediately.
- **Interaction:** clicking a map enlarges it to the full-width single-map view; the readout
  sentences come from JSON (`map.summary`).
- **Pros:** strongest "pick a variable" story.
- **Cons:** small maps lose detail; the readout sentences need careful stats wording; weak on
  mobile (stacked maps).

**Recommendation: B**, with the readout panel from A reused as the case page's top strip (P0-1),
so the same answer mark appears on every screen.

## 6. Keep as it is

- **Colour discipline:** RdBu for temperature, BrBG for water, symmetric limits at the 98th
  percentile (checked: T2M 0.8 vs p98 0.79), "≤ / ≥" end labels, and plain words at the ends of
  the colour bar ("drier / wetter"). This is what makes the app look like an instrument, not a
  product.
- **Question-first cases and the Grandma hook.** They are the human entry point; the jury named
  them first.
- **The weaker-of-two-tests rule, with a visible "two methods disagree" line and both p-values in
  "How sure?"** Rare honesty; keep it (fix only the range mismatch in P0-5).
- **Compare tests the trend of the A−B difference**, instead of comparing two verdicts. This is
  correct and uncommon.
- **"No clear trend yet", "A hint, not proof" and the years-to-detection sentence**, phrased "if
  the current rate held" and rounded to 5.
- **The checks audit ("we ran 17, N held up")** and the Methods false-alarm chart with its 10/20/40
  year toggle. These are the most memorable elements; fix the wording, do not remove them.
- **"How do we know?" links** under every finding.
- **The very-dry-months count ("about 0.7 a year → about 3.4 a year")**, the most teen-graspable
  number in the app.
- **The honest "Investigation not open yet" state** (fix its placement only).
- **The black synthetic banner, the SYNTHETIC flag in the CSV and the provenance footer.**
- **Engineering:** strict Ajv loader against the shared schema, generated types, a contract test,
  hash routes with `base: './'`, a self-hosted basemap and fonts, and a smoke test that clicks the
  map.
- **The "What this cannot tell you" list on Methods**, with its explicit no-attribution statement.

## 7. Open questions for the team

1. **Display size 48 px** for the one rate number per screen (P1-2). Challenges plan v2's type
   sizes. Owner: visual lead.
2. **Answer sentences that take a side** ("Yes, the record backs Grandma"). Generated by the stats
   templates from the verdict. Acceptable tone, or keep it neutral? Owner: stats lead + copy.
3. **"Likely" vs "95% range."** P0-3 drops "likely" everywhere. The comprehension reviewer
   proposed "probably"; I rejected that (section 8). Confirm. Owner: stats lead.
4. **Verdict rule when the methods disagree.** Plan v2 says "weaker" in decision 10 and "better"
   in the Verdict section; the app and Methods use "weaker". Fix plan v2's Verdict section.
   (Already open as web app plan Q1.)
5. **Evidence scale: 4 or 5 segments** (plan v2 says 5; four graded levels exist). Web app plan
   Q2; P1-5 depends on it.
6. **Insights filter at q = 0.10, map at q = 0.05.** Unify, or explain on screen why they differ.
   Also whether the season comparison should test the DJF−JJA difference series (like Compare)
   instead of CI overlap. Owner: stats lead.
7. **Landing variable.** Plan v2 decision 1 opens case 01 (soil, a pale map). The jury suggests
   temperature as the more striking first map. Team's call.
8. **Case 04 as a pre-registered null case** (P1-7): which region and variable, chosen before
   computing?
9. **Dark theme for the submission.** Plan v2 makes it optional. Ship light only if P0-2's dark
   fix is not done in time?
10. **Projection.** Keep Mercator with a caption (P2-4), or switch to MapLibre's globe or an
    equal-area view later?
11. **Any-place investigation** (the jury's suggestion: click any land cell for a lightweight
    case). This conflicts with plan v2 decision 2 and is a scope decision, not a design fix.
12. **"Predict, then reveal"** (the jury's suggestion: ask "drying? yes / no / can't tell" before
    showing the verdict). Good teaching practice, but it adds a step. Team's call.
13. **A "what scientists think drives this" line** per case, marked "context, not tested here"
    with a citation (e.g. IPCC AR6 for the north-wetter/south-drier pattern). It speaks to the
    challenge's "same process, opposite trends" point, but it brushes against our no-attribution
    rule. Team's call.
14. **`docs/10-methods.md` power claim.** It says Yue-Wang keeps "comparable power", but at
    φ = 0.6 and n = 120 its power is 0.137 vs 0.47 for the uncorrected test (whose power is
    inflated by false alarms). Stats lead to reword.

## 8. Rejected findings

| Finding (reviewer) | Why rejected |
| --- | --- |
| "The 95% band can't be seen" (maps) | It is visible in `case-01__desk__light__fold` and `case-02__desk__light`: faint, not invisible. Kept only the form change in P1-4. |
| Add "This mostly follows from the overall drying" to the extremes insight (honesty) | That sentence would itself be an untested claim. Kept only the "fade when it fails the filter" part (P2-1). |
| Replace "likely" with "probably" (comprehension) | Still an uncalibrated probability word, and it collides with IPCC language. Replaced by "95% range" (P0-3). |
| Show "528 months (worth about 51 independent ones)" in "How sure?" (honesty) | 51 is the regression's effective n, while the headline test is Mann-Kendall with its own variance correction. Putting it on the card mixes the two tests. Fine on Methods. |
| "Northern Europe soil is 'a hint'" (maps) | Wrong detail: it is "No clear trend yet". The finding itself (labels lack the evidence level) holds; P1-6. |
| Popup clamp bug at `MapPage.tsx:202/213` (code review) | Wrong line numbers; reproduced at `MapPage.tsx:140` and `:151` and kept (P0-6). |
| "The header says NASA POWER while the data are synthetic" (jury) | The banner, the caption and the case meta line all say synthetic. Not an app defect; relevant only to the video and submission page. |
| Any-place investigation as a fix (jury) | Not a design defect; a scope change against plan v2 decision 2. Moved to open questions (Q11). |
| Precompiled Ajv standalone as a priority (code review) | Real, but no visible gain before the deadline. Moved to P2-8. |
| "Zero sits on a bin edge, so ±0.001 gets a sign colour" as a P0/P1 issue (maps) | Reproducible, but the two central bins are near-white, so the visual effect is negligible. Downgraded to P2-5. |

## 9. Rebuilding the screenshots

The capture script lived in a scratch directory and is not committed. To rebuild:
`cd frontend; npm ci; npm run build; npx vite preview --port 4174`. Then run a Playwright script
that opens each route listed in section 3, waits for `.topbar` and (on case pages)
`.series-chart .main-svg`, waits 3.5 s for MapLibre, sets `localStorage['td-theme']` for dark,
and launches Chromium with `--use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader`.
If the team wants, this can become `frontend/scripts/screens.mjs` so every PR can attach the same
set.
