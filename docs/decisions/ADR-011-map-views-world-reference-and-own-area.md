# ADR-011 — Tools to test a "here versus the world" idea: map views, world reference, your own area

- Status: Accepted by the Lead (2026-11-15); statistics reviewed by the `stats-validator` agent the same day (all numbers reproduced; its findings are folded into the decisions below); human second review pending
- Date: 2026-11-15
- Requirement IDs: R-02, R-04, R-05, R-06, R-15

## Context

The team wants visitors to be able to test an idea of the form "the world is warming, but this place
is doing something else" (the example that started it: local cooling around the North Atlantic next
to global warming). The Lead's decision: **no page built for one hypothesis and no prepared "story"
areas**. The app must give general tools, so that a visitor can run such a check on any variable and
any place. The map seasons and the area tool work for all fourteen variables; the comparison with the
world for eight (decision 2).

## Decisions

1. **Map views.** Besides the whole-year trend, the map offers one layer per three-month season
   (Dec–Feb, Mar–May, Jun–Aug, Sep–Nov; named by months because the map is global) and, for each of
   these five, a "compared with the world" layer where the variable has a sound world average
   (decision 2). Ten layers per variable (five without the comparison), all precomputed by
   `map_layer()` with the same per-square test (Sen, Mann–Kendall Yue–Wang on one value per year, BH
   FDR across squares).
   - A season's value is the mean of its three months; December counts towards the next year, so the
     first winter is left out (the same convention as `seasonal_series` for regions).
   - "Compared with the world" tests each square's yearly values **minus the world average of the same
     year**. It answers "faster or slower than the world?", not "is it changing?". The legend names
     the view and prints the world's own trend.
2. **The world average** is the area-weighted (cos latitude) mean of every 2° square with a complete
   record: the whole globe for global fields, land squares for land-only fields. For air temperature it
   therefore includes the oceans, which warm more slowly than land; the app says so wherever the
   comparison is shown. **Six variables get no comparison with the world** (`world_ref=False`). For four
   the review showed that their world average is not a sound yardstick; the two AIRS variables,
   added to the app by another change on the same day, have not been reviewed for this yet:
   - *MERRA-2 precipitation.* Its world mean falls by 1.0% per decade, but only because its ocean
     squares fall by 2.2% per decade (strong by our rule), while its land squares, which are corrected
     with gauges, rise by 0.9% (no clear trend) and the IMERG satellite record shows no fall either
     (`python scripts/area_stats.py --var precip --world`, `--var rain_sat --world`). A fall in ocean
     rain next to rising water vapour is the signature of observing-system changes. With that reference
     about half of the "differs from the world" verdicts for precipitation existed only because the
     reference drifts (e.g. Egypt, own trend 0.000, "strong" gap).
   - *Sea ice, snow cover, snow depth.* A mean over all sea or all land is mostly squares that never
     have any; for sea ice the Arctic loss and the Antarctic change cancel.
   - *AIRS air temperature and water vapour.* AIRS samples clear and partly cloudy scenes, and its
     world vapour trend disagrees with MERRA-2's; no world comparison until that is looked at.
   The other world averages carry a caveat in the app: a world mean from a reanalysis or a merged
   satellite product can drift when the observing system changes.
3. **Every regional analysis gets `vs_world`.** The monthly series "region minus world" goes through
   the full headline rule (weaker of two tests; most cautious of the four pre-declared calculations).
   Only a clear trend in that difference is reported as a difference. Wording rules, so that a headline
   never says more than the tests: "faster"/"more slowly" needs a clear gap, the same sign, and an
   established trend of the region or of the world (otherwise "moving apart"); a direction word such as
   "warming" needs the region's own verdict to be at least "evidence"; for ratio-scale variables
   (vapour, sunlight, evaporation, haze, ozone, satellite rain) the headline says "a larger/smaller
   change", because a smaller change in units can be the same change in percent, and the sentence gives
   both. Per season, the difference is tested on one value per year and the four seasons share one BH
   family (q = 0.05); that is a lighter test than the headline, and the page says so.
4. **Your own area.** A visitor can drag a box anywhere on the map (land or sea), or type its
   coordinates, and get the rate, 95% range and verdict for it, its difference from the world average,
   and optionally its difference from a second box.
   - Averaging rule, the same as for countries (ADR-008): a square counts by the share of it inside
     the box times cos(latitude); squares without a complete record are left out and the panel reports
     the share of the box that had data.
   - A box cannot be precomputed, so the test runs in the browser. `frontend/src/lib/stats.ts` is a
     line-by-line port of `trend_stats.py` (Sen's slope with Mann–Kendall Yue–Wang ranges, OLS with the
     lag-1 effective sample size) combined exactly as `make_app_data.yearly_values_trend`, which is
     the yearly calculation already used as a stability check for every verdict. This is the one
     place where project rule "reuse `trend_stats.py`, never hand-roll a test" is met by a tested
     port instead of a call: `stats.test.ts` compares the port with values produced by the Python
     reference (`scripts/area_stats.py --fixture`) on 14 series (ties, short records, strong
     autocorrelation) and on 7 boxes computed from the NetCDF grids, on every build.
   - Input for the browser: `series/<variable>[__<season>].bin`, one mean per year for every square
     (float32 mean, float32 step size per square, int16 counts). A step is 1/32000 of that square's
     largest departure from its mean, so the rounding (half a step) is negligible next to the square's
     own year-to-year changes, including squares with very little rain or snow.
   - It is the **quick version**: one value per year, no stability checks, no monthly data. Countries
     and regions keep their fuller analysis, and the Methods page says to prefer it. The quick rule errs
     towards more confidence when years are strongly alike: on trend-free AR(1) series it says
     "evidence" or "strong" in 3–4% of cases without memory, about 7% at φ = 0.3 and 8–12% at φ = 0.6–0.8
     for 45 years (`python scripts/area_stats.py --false-alarms`); on the app's 1,790 regional series it
     is stronger than the cautious headline in about one case in ten. The panel and Methods state this.
   - `scripts/area_stats.py --var … --box W S E N [--season …] [--second …]` prints the same numbers
     from the cached grids, so any box result on the site can be reproduced without a browser.
5. **A stated limit on drawing boxes.** A box drawn around a patch that stood out on the map is no
   longer a fair test (the area was chosen because it looked unusual). The Methods page says so, and
   the area panel shows the warning directly under every result that reaches "evidence" or "strong".
   We do not ship any box of our own as a finding.

## What the example looks like in these data (context, not a finding of the app)

Checked while building, with `scripts/area_stats.py`, MERRA-2 air temperature 1981–2025. These boxes
were chosen after looking at the map, so by decision 5 they are leads, not results:
- world average +0.17 °C per decade (strong evidence);
- North Atlantic south of Greenland (46–62°N, 46–20°W): +0.13, no clear trend; minus the world −0.04,
  no clear difference;
- centre of North America in March–May (44–60°N, 115–90°W): −0.11, no clear trend.
Prepared regions, with the full monthly rule: all six North American IPCC regions have positive
whole-year rates (+0.21 to +0.35 °C per decade): four with strong evidence, North-western North America
with evidence, and North-eastern North America only a hint under the cautious rule. None shows cooling.
So the data do not show North America cooling; they show places where warming is not yet
distinguishable. Air temperature cannot say anything about ocean currents.

## Consequences

- `frontend/public/data/` grows by about 105 MB (110 map layers, 14 MB; 70 yearly-series binaries,
  91 MB). The binaries change only when the cache or the grid code changes. This runs against the aim
  of ADR-010 (keep large data out of git): the site is built from the repository, and this change had
  no write access to the bucket. Follow-up for the data engineer: serve `series/*.bin` from the GCS
  data store (public read, CORS for the site's origin) and drop them from git.
- Rebuilding the data needs the grids: `python scripts/sync_cache.py pull` first (ADR-010).
- Analysis files gain `vs_world`; `schema/analysis.schema.json`, `schema/map.schema.json` and the new
  `schema/series-index.schema.json` are the contract; `check_data.py` also checks that every
  variable has its ten map views and that every binary has the promised size.
- The assistant's container image holds a copy of the data and must be rebuilt after this change
  (`docs/11-assistant.md`, "Keep it in sync").
- Rankings, country labels and the quick-look panel always show the whole-year result; when the map
  shows another view they say so.

## Open after the review (not fixed here)
- Some MERRA-2 air-temperature trends for South Asia and Central America (e.g. Bangladesh, Honduras
  cooling) look at odds with the observational record. They predate this change (they are the regions'
  own verdicts) and are covered only by the general "reanalysis, not a measurement" caveat. They should
  be cross-checked against GISTEMP or Berkeley Earth before being quoted anywhere.
- The land-only world average weights every land square by cos(latitude) only, not by its land
  fraction (soil wetness reference +0.15 against +0.11 percentage points per decade; both "no clear
  trend").
- For fields with gaps (haze, ozone) the reference covers a slightly different set of squares in each
  season; the layers do not print that share.
