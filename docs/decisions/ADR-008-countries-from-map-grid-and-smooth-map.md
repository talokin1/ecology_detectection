# ADR-008 — Countries from the 2° map grid, twelve variables, smooth map rendering

- Status: Accepted by the Lead (2026-11-15); statistics pending the usual second review
- Date: 2026-11-15
- Requirement IDs: R-01, R-02, R-06, R-15

## Context

The Lead asked for the final demo version: more variables than the three core ones, every country
selectable (not only five prepared regions), a smooth map instead of visible squares, and a calmer
analysis page. The Lead also allowed filling gaps with interpolated or synthetic values without saying
so. That part is **not adopted**: rule 2 of `CLAUDE.md` (scientific honesty) and the Validity criterion
forbid it, and it is not needed, because the frozen cache already holds real data for everything below.

## Decisions

1. **Twelve variables**, all real, all already in `data/cache/grids/`: air temperature, precipitation,
   soil wetness, evaporation, water vapour, snow cover, snow depth, sea ice, ozone (MERRA-2, 1981–2025);
   sunlight, haze (CERES SYN1deg, 2001–2025); rainfall from space (GPM IMERG, 1998–2025). Each variable
   uses its own whole-year period. Regional answers exist for nine of them; snow cover, snow depth and
   sea ice are map-only (see `docs/10-methods.md`, "Variables and their periods"). Left out on purpose:
   CERES cloud amount (two steps in its near-global mean, 2006 and 2022) and GRACE water storage (its
   mission gap needs its own missing-data rule).
2. **Three sets of places.**
   - *Our stories* (5): unchanged, native ~50 km series, with the `climate_stats` deeper checks for the
     three core variables. Their series for the other POWER variables were fetched from the public POWER
     archive with `build_data.py --only set:countries --only sahel` and frozen in `MANIFEST.json`.
   - *World regions* (42): the IPCC AR6 land regions already in the cache (native series). `ar6_rar`
     crosses the antimeridian and is not drawn.
   - *Countries* (152): outline from the committed basemap (Natural Earth 1:10m, Ukrainian point of
     view). **A country's value is the mean of the 2° map squares it overlaps, weighted by the area of
     overlap times cos(latitude).** Parts farther than about 1,000 km from the mainland (chain rule) are
     left out; countries under 20,000 km² are not offered; Antarctica and three disputed areas are
     skipped; Ukraine keeps its native-resolution story series.
3. **A region/variable pair is left out, never filled**, when a month is missing or when fewer than three
   calendar months hold a non-zero value in at least half of the years (e.g. snow in the tropics). The
   app then says there is too little of it there to measure a trend.
4. **Smooth map = drawing only.** The browser interpolates the per-square slopes bilinearly, runs the
   colour continuously through the palette and blends colour strength by the share of neighbouring
   squares that pass the map-wide test. Land-only fields are clipped to the coastline, sea ice to the
   sea. Tooltips, significance dots, rankings and every statistic use the real 2° squares. The legend and
   the Methods page say so.
5. **Cautious headline.** The verdict is the weakest of four pre-declared calculations (full record,
   without the first two years, without the last two years, yearly means); see "Robustness" in
   `docs/10-methods.md`. Adopted after the second `stats-validator` review of this change.
6. **Plain words first.** Each finding is one sentence; its numbers move to "How do we know?". The
   "How sure?" line is a plain sentence (`verdict.sure_plain`); p-values, the robustness line and the
   count of follow-up checks sit one click away. Nothing statistical was removed from the data files.

## Consequences

- Country numbers are coarser than story numbers and include some sea in coastal squares; this is
  stated on every country page (provenance caveat) and in Methods. Cross-check for Ukraine (same period,
  1981–2025): see `docs/10-methods.md`, "Countries".
- About 1,800 analysis files (~45 MB) are committed under `frontend/public/data/`.
- Comparisons and neighbour hints exist only among the five story regions.
