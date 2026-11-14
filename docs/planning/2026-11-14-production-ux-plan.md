# Production UX plan: map first, everything else on demand

Nov 14, 2026 · branch `viz` at commit `63f621b` · follows
[plan v2](2026-11-14-plan-v2.md) and the [review plan](2026-11-14-viz-review-and-plan.md)

Status: **approved by the lead (all recommendations in section 8) and implemented** on branch `viz`.

### Implementation status (Nov 14, 2026)

Done: A1–A13, B1–B8. Not done: tier C. Decisions D1–D7 applied as recommended
(D7: the first map is air temperature, `default_case` = 02).

Measured after the change (same script, first viewport, returning visitor):

| Screen | Text items | Words | Controls | Page length |
| --- | --- | --- | --- | --- |
| Explore, 1440×900 | 18 (was 94) | 33 (was 292) | 17 (was 26) | 1.0 screens |
| Full analysis `#/case/01`, 1440×900 | 37 HTML items + chart axis labels (was 65 in total) | 183 | 15 | 1.8 screens (was 2.6) |
| Explore, 390×844 | 15 (was 39) | 28 (was 101) | 16 | 1.0 screens (was 2.4) |

A first visit adds the one-time synthetic notice and the tour offer (22 items, 20 controls).
The budgets are now tests (`frontend/tests/smoke.spec.ts`, "noise budget"); they count HTML text
only, not chart axis labels. Deviation: the hint does not move the map camera to the region; the
region is outlined and labelled instead, which keeps the world view stable.

## 1. What the lead asked for

| # | Requirement | Short name |
| --- | --- | --- |
| U1 | There is too much visual noise. | Less noise |
| U2 | Everything on screen must be closable. | Closable |
| U3 | It must be possible to just look at the map with filters. | Map with filters |
| U4 | Use cases must not be shown as a list of "use cases". They should appear as hints. | Hints |
| U5 | It must look and work like a production tool for our real user, not like a hackathon project. | Production feel |
| U6 | We must still meet every hackathon requirement. | Compliance |

## 2. Where we are now (measured)

Counted with a Playwright script on the current build, first viewport only (no scrolling):

| Screen | Text items | Words | Controls | Page length |
| --- | --- | --- | --- | --- |
| Map, 1440×900 | 94 | 292 | 26 | 1.0 screens |
| Full analysis (`#/case/01`), 1440×900 | 65 | 236 | 10 | 2.6 screens |
| Map, 390×844 | 39 | 101 | 12 | 2.4 screens |

Why the map screen reads as a hackathon project:

- **Five blocks compete with the map at once:** the left rail (3 variables, 4 numbered cases, one
  of them expanded with a question, an answer and a button), the title box on the map, region
  labels with two lines each, the legend strip with three keys, and the six-row ledger with its
  caption. Nothing can be closed.
- **The map itself gets about half of the screen.** There is no state in which a visitor sees
  only the map and its controls.
- **Internal vocabulary is on screen:** "Investigations", "01 / 02 / 03 / 04", "Case 01",
  "Prepared regions, ranked", "Investigation not open yet", "SYNTHETIC demo field shaped like NASA
  POWER GWETROOT", numbered section kickers ("01 · Over time").
- **Clicking a region leaves the map** for a long page. There is no quick answer in place.
- **The synthetic-data banner** is a full-width black bar on every screen, forever.

## 3. Principles

1. **Map first.** On open, the visitor sees the map, one row of filters and a small legend.
2. **Everything else is on demand and closable.** A panel opens because the visitor asked for it,
   has a close button, closes with Escape, and has exactly one visible way to reopen it.
3. **Hints, not menus.** Our prepared questions appear one at a time, in context, as a suggestion
   the visitor can take or dismiss.
4. **Answer in place, depth one click away.** Clicking a region shows the answer next to the map;
   the full analysis is a link from there.
5. **One vocabulary, the visitor's.** No case numbers, no pipeline terms.
6. **Honesty is not noise.** The significance encoding, the 95% range, "How sure?" and the
   synthetic-data notice stay visible. They get smaller, never hidden.

## 4. Target experience

### 4.1 Explore (default route `#/`)

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│ Trend Detective   Explore  Catalog  Methods      [Search…]      Synthetic data  ⋯ │
├───────────────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────────┐       [+] │
│ │ Soil wetness ▾ ⓘ │ All trends · Clear only │ Both · Wetter · Drier │ Regions │   [−] │
│ └─────────────────────────────────────────────────────────────────────┘           │
│                                                                                   │
│                                 M A P                                             │
│                                                                                   │
│ ┌──────────────────────────────┐   ┌──────────────────────────────────────────┐   │
│ │ −1.2 ▮▮▮▮▮▮▮▮▮▮▮ +1.2  ⓘ  ×  │   │ Try: Is the soil in southern Ukraine     │   │
│ │ percentage points per decade │   │ drying out?            Next · ×          │   │
│ └──────────────────────────────┘   └──────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────────────────┘
```

- **Visible by default:** top bar, filter bar, zoom buttons, collapsed legend, one hint.
- **Gone from the default view:** left rail, case list, on-map title box, permanent region labels,
  ledger, caption, context line in the top bar.
- **Budget for this state at 1440×900:** at most 30 text items, 80 words, 18 controls
  (now 94 / 292 / 26). The map takes at least 85% of the area under the top bar.

### 4.2 After one click on a region

```
│ [filter bar]                                         ┌───────────────────────────┐│
│                                                      │ Southern Ukraine        × ││
│                                                      │ Soil wetness · 1981–2024  ││
│                M A P                                 │                           ││
│        (region outlined)                             │ −1.0  points per decade   ││
│                                                      │ Strong evidence: drier ▮▮▮││
│                                                      │ 95% range −1.6 to −0.4    ││
│                                                      │ ▂▃▅▃▂▁▁▂▁▁  (years + line)││
│                                                      │ Yes, the record backs…    ││
│ [legend]                                             │ Full analysis →  Compare… ││
│                                                      └───────────────────────────┘│
```

One click gives the time series, the rate, its 95% range and the significance verdict beside the
map. That is the whole challenge scope (objectives 1–4) on one screen, which is also the strongest
frame for the 30-second video.

### 4.3 Panels (all closable, all reopenable)

| Panel | Opens from | Default | Contents |
| --- | --- | --- | --- |
| Legend | Legend chip (bottom left) | Collapsed chip | Expanded: what strong colour, greyish colour, hatching and dots mean; source; projection note |
| Region quick look | Click on a region or a row | Closed | Section 4.2 |
| Regions compared (the former ledger) | "Regions" in the filter bar | Closed | Dot-and-whisker rows on one zero-centred axis; hover syncs with the map; a row opens the quick look |
| Questions to try (hints) | Hint chip; "Ideas" in the filter bar after dismissal | One hint shown | Our prepared questions for the current variable |
| About this data | "Synthetic data" tag; "⋯" menu | Closed | Synthetic notice, sources, credits |

Rules: one side panel at a time; Escape closes the top one and returns focus; panel state lives in
the URL, so a shared link opens the same view; dismissed hints are remembered per browser.

### 4.4 Full analysis page

Same content as today, less on screen at once: breadcrumb instead of "Case 01"; two selects
(region, variable) instead of nine chips; plain section headings without numbers; the readout,
the chart and "What we found" open; "How sure" shows its one-line summary and expands; seasons,
months, extreme months and downloads are collapsed with a one-line summary each.

### 4.5 Phone

Map on the first screen with two buttons ("Filters", "Regions"), the legend chip and one hint.
Quick look, regions and filters open as bottom sheets with a close button.

## 5. Work items

Effort: S = under 2 h, M = half a day, L = a day or more (human estimate).
"JSON" lists what the stats pipeline or templates must provide; "none" means the current
contract is enough.

### Tier A: declutter, closable panels, map with filters, hints (must)

| ID | Change | Meets | Files | JSON | Acceptance | Effort |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | **Panel component** used by every overlay: title, close button, Escape, focus returns to the opener, `aria` dialog semantics, state in the URL (`panel=`), one side panel at a time | U2 | new `components/Panel.tsx`, `state/` URL helper, `styles.css` | none | With every panel closed only the top bar, filter bar, zoom and attribution remain; each panel has exactly one visible way back; keyboard-only open and close works | M |
| A2 | **Explore layout**: full-bleed map; remove the left rail, the ledger under the map, the on-map title box and the caption | U1, U3 | `pages/MapPage.tsx`, `styles.css` | none | Budget in 4.1 met (add it to the smoke test); map ≥ 85% of the area under the top bar | S |
| A3 | **Filter bar**, one row: Variable; Show (All trends / Clear trends only); Direction (Both / the variable's two words); Regions on/off; read-only period. "Reset" appears only when something is not default. Filters only hide cells using the `significant` flag and the sign already in `map.json` | U3 | new `components/FilterBar.tsx`, `components/TrendMap.tsx` (mask in `paintGrid`), `strings/en.ts` | none | "Clear trends only" leaves no coloured cell with `significant = 0` (unit test on the mask); state is in the URL; an empty result shows "No squares match. Reset filters" | M |
| A4 | **Legend chip**: collapsed to the colour bar, three ticks and units; expands to the full explanation; closable; reopened from a "Legend" button | U1, U2 | `components/MapLegend.tsx` | none | Collapsed legend is at most 280 px wide and 2 lines; every mark on the map is still explained in the expanded state | S |
| A5 | **Regions compared** as a panel (right drawer; bottom sheet on phones), closed by default; a row opens the quick look | U1, U2 | `components/RegionLedger.tsx`, `pages/MapPage.tsx` | none | Hover sync still works; the phrase "Prepared regions, ranked" is gone | S |
| A6 | **Region quick look** (section 4.2): readout, yearly bars with trend line and band, answer sentence, "Full analysis", "Compare…" | U3, U5 | new `components/QuickLook.tsx`, reuse `Readout`, `TrendChart` | none (`analysis.json` has it all) | From a cold load, one click on a region shows time series, rate, 95% range and verdict next to the map; Escape closes it | M |
| A7 | **Cases become hints.** Remove the numbered list and every "Case 0X" label. One hint chip on Explore for the current variable ("Next", close; "Ideas" restores it). A hint sets the variable, moves the map to the region and opens the quick look with the question as its heading. Old links `#/case/01`–`04` keep working and open the full analysis | U4 | `pages/MapPage.tsx`, new `components/HintChip.tsx`, `pages/CasePage.tsx`, `strings/en.ts` | none (keep `index.cases` as is; only the UI word changes) | The word "Case" appears nowhere in the UI; a dismissed hint stays dismissed after reload and can be restored; all four old links open | M |
| A8 | **Quieter map**: region names only on hover, focus and for the selected region; thin outlines that thicken on hover; compact attribution | U1 | `components/TrendMap.tsx`, `styles.css` | none | No text is drawn on the map until the visitor points at something | S |
| A9 | **Synthetic-data notice**: the full banner shows once and can be closed; a "Synthetic data" tag stays in the top bar while any loaded file has `synthetic: true` and cannot be dismissed; it opens "About this data" | U1, U2, honesty rule | `components/Shell.tsx` | none | Tag visible on every screen with synthetic data; PNG and CSV stamps unchanged | S |
| A10 | **Slim top bar**: wordmark, Explore / Catalog / Methods, synthetic tag, one "⋯" menu (Copy link, theme, About). Remove the context line | U1 | `components/Shell.tsx`, `styles.css` | none | Top bar has at most 8 text items | S |
| A11 | **Full analysis page**: breadcrumb; region and variable selects; no numbered kickers; collapsed secondary sections with one-line summaries; "How do we know?" becomes one small help button per finding that opens the explanation in place (**changes plan v2** wording) | U1, U2, U5 | `pages/CasePage.tsx`, `pages/ComparePage.tsx`, `components/InsightList.tsx`, new `components/Disclosure.tsx` | none | First viewport ≤ 45 text items (now 65); page ≤ 2 screens with sections collapsed (now 2.6); rate, 95% range, verdict and the "How sure?" line visible without a click | M |
| A12 | **Phone layout** (section 4.5) | U5 | `styles.css`, `components/Panel.tsx`, `components/FilterBar.tsx` | none | At 390×844 the first screen is the map; no horizontal scroll; every sheet closes with its button | M |
| A13 | **Wording pass** (table below) | U4, U5 | `strings/en.ts`; caption template in the pipeline | `map.caption` text | None of the "Now" strings in the table remain | S |

Wording changes for A13:

| Now | New |
| --- | --- |
| "Investigations" (list heading) | removed; hints say "Try:" |
| "Case 01 · Grandma's drought" | removed; the question stands alone |
| "Open investigation →" | "Full analysis →" |
| "Prepared regions, ranked" | "Regions compared" |
| "Investigation not open yet" | "No detailed analysis for this place yet" |
| "What to look at" | "Variable" |
| "Keep investigating" | removed (selects in the header) |
| "SYNTHETIC demo field shaped like NASA POWER GWETROOT · …" (on screen) | "Demo data, not real measurements." The technical provenance stays in Methods and in the CSV |
| "01 · Over time", "02 · Where" … | "Over time", "Where" … |

### Tier B: production feel (should)

| ID | Change | Meets | Files | JSON | Acceptance | Effort |
| --- | --- | --- | --- | --- | --- | --- |
| B1 | **Guided tour** "Show me how" (4 steps, about 25 s, skippable, never auto-plays): filters → colours → fly to a region → verdict in the quick look. Offered once to new visitors; always in the "⋯" menu | U4, U6 (examples a user can watch) | new `components/Tour.tsx` | none | The tour runs end to end with the keyboard; closing it leaves the app in a normal state | M |
| B2 | **Search** in the top bar: places (prepared regions), variables (catalog) and our questions. With an empty query it shows "What are you curious about?" (topics) and "Where?" (place types) plus the questions | U4, U5, U6 (question-driven search) | new `components/Search.tsx` | none (`index.json`, `catalog.json`) | Typing "ukr" offers both Ukraine regions; choosing a topic then a place type lists matching variables | M |
| B3 | **Definitions in place**: an info button next to the variable (definition and "why it might change" from the catalog) and next to "95% range" and "clear trend" (glossary text) | U5, U6 (simple definitions) | `components/FilterBar.tsx`, `components/QuickLook.tsx` | none | Every variable name on screen has its definition one click away | S |
| B4 | **About and credits** (`#/about` or a panel): what the tool is (the tagline, finally shown), team, NASA data sources with links, references, licence, SI disclosure, repository link | U5, U6 (sources, SI disclosure) | new `pages/AboutPage.tsx`, `docs/09-references.md` as the source | none | Every source in `09-references.md` marked `used: yes` is listed | S |
| B5 | **Loading, empty and error states**: land outline first and the grid fades in; skeleton in the quick look; inline "Try again"; no bare "Loading…" | U5 | `components/Shell.tsx`, `TrendMap.tsx`, `QuickLook.tsx` | none | Throttled to Fast 3G, no screen shows only the word "Loading…" | S |
| B6 | **Site metadata**: page title per route, description, share image (a real screenshot, no NASA logo), `404.html` for GitHub Pages that redirects into the app, icons, `theme-color` | U5 | `index.html`, `public/`, route titles | none | A pasted link shows a title, text and image; an unknown path lands in the app | S |
| B7 | **Compare from the quick look**: "Compare…" lists the other regions and opens the existing compare screen; the "opposite ways" hint opens "Regions compared" with both rows highlighted | U3, U6 (opposite trends) | `QuickLook.tsx`, `MapPage.tsx` | none | Two clicks from the map to a comparison | S |
| B8 | **Noise budget in CI**: commit the counting script and assert the budgets of 4.1 and A11 in the smoke test; keep a screenshot set (1440, 1024, 390 px; light and dark) | U1 | `frontend/scripts/`, `tests/smoke.spec.ts` | none | CI fails if the default Explore view exceeds its budget | S |

### Tier C: later

| ID | Change | Note |
| --- | --- | --- |
| C1 | "Hide interface" toggle: bare map with one button to bring the interface back | Cheap once A1 exists |
| C2 | Season filter on the map | Needs `map/<variable>__<season>.json` from the stats pipeline |
| C3 | Place-type filter for regions | Worth it only with more than about 10 regions |
| C4 | Print style for a full analysis (classroom handout) | |
| C5 | Ukrainian interface | Plan v2 decision 6: after the MVP |

## 6. Hackathon compliance (U6)

Every challenge requirement keeps a visible home. The right column is the guard that stops the
declutter from hiding it.

| Requirement | Now | After this plan | Guard |
| --- | --- | --- | --- |
| R-01 select variables | Left rail + Catalog | Variable select in the filter bar + Catalog + search (B2) | Variable control is always visible |
| R-02 variable for a region | Click a region → page | Click a region → quick look; regions also in the panel and search | Smoke test: one click opens the quick look |
| R-03 time series | Full page only | In the quick look **and** on the full page | A6 acceptance |
| R-04 rate of change | Full page readout | Quick look + full page | Rate and 95% range visible without a click (A11) |
| R-05 significance | Readout + "How sure?" | Quick look verdict + "How sure?" line on the full page | "How sure?" summary line is never collapsed |
| R-06 visualisation and analysis in one tool | Two pages | Map and analysis on **one screen** | Section 4.2 |
| R-10 simple definitions | Catalog only | Info button next to every variable (B3) + Catalog | B3 acceptance |
| R-11 question-driven search (what / where) | Proposed `dropped` | Search with "What are you curious about? / Where?" (B2). Can return to `doing` | B2 acceptance |
| R-12 examples a user can watch | Numbered case list | Hints (A7) + guided tour (B1) | Old `#/case/0X` links still open; tour in the menu |
| R-14 non-significant trends are informative | Verdict text, case 04 | Same, plus a hint for the "A hint, not proof" question so it is found | One hint points at a non-significant result |
| R-15 opposite-sign trends | Ledger always on screen | "Regions compared" panel + "opposite ways" hint (B7) | See decision D4: this is our signature view and it is now closed by default |
| R-16 seasonal cycle | Chart toggle, seasons chart | Same, in a collapsed section with a one-line summary | Summary line always visible |
| R-30 English | Yes | Yes | `strings/en.ts` only |
| R-32 public link, no login | Yes | Yes | CI smoke test |
| R-33, R-34 NASA data and references listed | Docs only | Also in the product (B4) | B4 acceptance |
| R-35 SI disclosure | Docs only | Also in the product (B4) | B4 acceptance |
| R-38 no NASA branding | Yes | Yes; the share image (B6) is our own screenshot | Review of B6 image |

Judging criteria: Presentation gains the most (clean first screen, answer in place). Impact gains
through usability. Creativity is at risk only if the regions comparison and the "years to
detection" message become hard to find, which D4 and the hints guard. Validity and Relevance are
unchanged: no number, test or wording about certainty is removed.

**The first 30 seconds of a judge** must still work without reading instructions: open the link →
see the map → click the hint → read the answer with its evidence level → open "Full analysis".
That path is three clicks and is also the storyboard for the video.

## 7. What stays as it is

- The significance encoding on the map (colour strength for certainty, hatching for no data).
- The readout: one large rate, evidence glyph, 95% range, answer sentence.
- The wording rules from the review ("95% range", no "unlikely to be chance").
- The dot-and-whisker comparison of regions; only its place changes.
- Compare with the gap chart, Methods, Catalog content, exports with provenance.
- The JSON contract, the tests, hash routes, GitHub Pages deploy.

## 8. Decisions needed from the lead

| # | Decision | Recommendation |
| --- | --- | --- |
| D1 | Clicking a region opens the quick look instead of navigating to a page. **Changes plan v2** (sequence diagram) | Yes; the full page stays one click away |
| D2 | First screen: plan v2 decision 1 says "map with a case already open on top". It becomes "map with one question as a hint". **Changes plan v2** | Yes; this is requirement U4 |
| D3 | The synthetic banner becomes a one-time banner plus a permanent tag | Yes; the tag must not be dismissible while data are synthetic |
| D4 | "Regions compared" closed by default. It is our most original view, and judges may not open it | Closed by default, but the "opposite ways" hint opens it and the tour shows it. Alternative: open it on a first visit only |
| D5 | "How do we know?" links become small help buttons that open the explanation in place | Yes |
| D6 | Functional icons (close, info, search, menu). Plan v2 bans decorative icons only | Allow these four, each with an accessible name |
| D7 | Default variable on first open: soil wetness (today) or air temperature (reads fastest on a bare map; open since the review, Q7) | Air temperature |

## 9. Order of work

The submission deadline is Sunday 2026-11-15, 23:59 local time. Real data, the
`stats-validator` run and the video still depend on other people, so interface work must not
consume the whole day.

1. A1 (panel) → A2, A3, A8 (bare map with filters). This alone satisfies U1 and U3.
2. A4, A5, A6 (legend, regions, quick look). U2 is satisfied.
3. A7, A13 (hints and wording). U4 is satisfied.
4. A9, A10, A11, A12 (banner, top bar, full page, phone).
5. Checkpoint: all tests green, budgets met, merge and deploy.
6. B1 (tour) and B4 (about) first, because the video and the submission page need them; then B6,
   B2, B3, B5, B7, B8 as time allows.
7. Freeze the interface before recording the video.

## 10. Dependencies and open items outside this plan

- **PR #3** (stale-cache fix) is open and not merged. Until it is merged, a visitor who had the
  site open before a deploy can see a data-contract error for up to 10 minutes.
- **Real NASA data** and the **`stats-validator`** run are still pending; the synthetic tag stays
  until then. Do not record the video on synthetic data.
- The caption template (A13) is in the data pipeline; whoever owns the real pipeline must use the
  new wording.
- After this plan, `docs/02-requirements-traceability.md` should move R-11 back from proposed
  `dropped` to `doing` (B2).

## 11. How the baseline was measured

A Playwright script opens the built app at the given viewport, waits 4 seconds, and counts
visible text nodes, words, and interactive controls (`a`, `button`, `select`) inside the first
viewport, plus page height in screens. B8 commits this script so the budgets become a test.
