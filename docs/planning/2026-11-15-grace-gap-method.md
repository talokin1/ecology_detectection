# GRACE in the app: a gap-aware method (proposal for the stats lead)

- Author: Molfarion (data engineer), 2026-11-15. SI-assisted (Claude); see `docs/08-si-usage-log.md`.
- Status: **proposal, needs the stats lead's decision** (D-G1 … D-G6 below) and a `stats-validator`
  run before anything reaches the UI. No code has been changed yet.
- Data: JPL GRACE/GRACE-FO mascons RL06.3Mv04 CRI (`TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4`,
  DOI 10.5067/TEMSC-3JC634), already cached: 2° land grid (in the data store, ADR-010) and 45 regional
  series. Units: cm of liquid water equivalent, anomaly vs the 2004.0–2009.999 mean, GIA-corrected by
  JPL, no gain factors applied.

## Why the current pipeline cannot take GRACE
`scripts/make_app_data.py` assumes complete records: `usable()` drops any series with a missing
month, and the map's yearly means need all 12 months. GRACE misses 11% of months, so today it would
give zero analyses and an empty map.

## Facts (measured on the cached 2° grid)
| | |
|---|---|
| Record | 2002-04 … 2026-09, 294 months, **261 with data (88.8%)** |
| Months per year | 2002: 7 · 2003: 11 · 2004–2010: 12 · 2011–2012: 10 · 2013–2016: 9 · **2017: 5 · 2018: 5** · 2019–2025: 12 · 2026: 9 |
| Main gap | 2017-07 … 2018-05 (11 months, between GRACE and GRACE-FO), plus 2018-08, 2018-09 |
| Other gaps | 2011–2016: one month in about five (battery management of the ageing GRACE satellites) |
| Calendar coverage | every calendar month has 20–23 years of data (S3: ≥ 5 needed) |
| Pattern | gaps are **global**: a missing month is missing in every square, so all squares share one set of valid months/years |
| True resolution | 3° mascons (~300 km); the 0.5° grid repeats each mascon's value (checked) |

## Proposal
1. **Period**: complete calendar years **2003–2025** (2002 starts in April; 2026 is partial).
   That is 276 months, 31 missing (**88.8% valid**, passes S3's 80%).
2. **Normal and anomalies**: calendar-month climatology from the available months of 2003–2025
   (20+ years each); no gap filling, no interpolation.
3. **Primary test (unchanged)**: Sen's slope + Mann-Kendall with Yue-Wang on monthly anomalies at
   their true decimal-year times; missing months are simply absent (`trend_stats` already drops NaN).
   **Caveat (D-G2)**: the lag-1 autocorrelation is then computed on the gap-compressed series, so a
   pair across a gap counts as "neighbours". Option A: accept (17 of 244 neighbour pairs span a gap; all but one gap are 1–2 months).
   Option B: compute r1 only over pairs exactly one month apart (small change in `trend_stats.py`,
   owned by the stats team).
4. **Secondary test (unchanged)**: OLS + lag-1 effective sample size, same treatment of gaps.
5. **Robustness checks (unchanged rule)**: without the first two years, without the last two years,
   and on yearly means. A yearly mean needs **≥ 9 valid months** of anomalies, which drops **2017 and
   2018** (5 months each); state that on the card.
6. **Break check (S4, mandatory for GRACE)**: Pettitt on the monthly anomalies. If a significant step
   falls in the 2017–2018 mission gap, the card shows the caveat ("a jump at the change of satellites;
   read with care"), not a stronger verdict.
7. **Map**: per-square yearly means (≥ 9 months) for 2003–2025 without 2017–2018 (21 years); Sen + MK
   Yue-Wang on those years with **true year spacing** (the current map code uses index spacing and
   must be changed for this layer); BH FDR across squares as for every map. Because squares sit inside
   3° mascons, neighbouring squares are near-copies: the caption says so and does not present the
   share of significant squares as independent evidence.
8. **Seasons, months, extremes (D-G4)**: seasons are tested only on years where all three months
   exist (fewer years, stated). **Extremes off for GRACE**: counting "extreme months" per year is
   biased when 3–7 months are missing.
9. **Which places (D-G5)**: GRACE cannot resolve places smaller than a mascon. Show regional answers
   only for regions of **≥ 2 mascons of land (about 200,000 km²)**: all 42 IPCC regions and the larger
   countries; smaller countries get "too small for GRACE to see" instead of a verdict.
10. **Wording**: "Water stored on land (groundwater, soil moisture, snow, lakes and rivers together)".
    Trend unit cm per decade. Caveats on the card: one satellite measures the total, not which part
    changed; the 2017–2018 gap; coastal leakage.

## Decisions for the stats lead
| ID | Question | Proposal |
|---|---|---|
| D-G1 | Period | 2003–2025 complete years |
| D-G2 | Yue-Wang r1 across gaps | A (accept) for the demo; B later |
| D-G3 | Yearly-mean rule | ≥ 9 valid months (drops 2017, 2018) |
| D-G4 | Extremes | off for GRACE |
| D-G5 | Minimum region size | ≥ 2 mascons (~200,000 km² of land) |
| D-G6 | Break check | Pettitt; caveat if significant in the mission gap |

## Validation before the UI
- `stats-validator` re-computes 3 regions independently (e.g. IPCC SAS / northern India, ARP, WNA).
- Sign check against published GRACE results: declines over northern India, the Middle East and
  California's Central Valley (Rodell et al., 2018, *Nature* 557: 651–659,
  doi:10.1038/s41586-018-0123-1; the stats lead confirms which regions to use from the paper). Agreement in sign is the bar; our
  period and smoothing differ, so magnitudes need not match.

## Work after approval (data engineer + stats)
`gap_aware` flag in the variable spec; `usable()` accepts ≥ 80% valid months for such variables;
map code with true year spacing and year filter; Pettitt caveat wiring; region-size filter; catalog
and Methods text; assistant image rebuild. Estimate: 4–6 hours including validation.

## Validation result (stats-validator, 2026-11-15) — NOT ready for main
Built on branch `grace` (123 regional analyses, map, `scripts/gap_aware.py`). Ukraine (−11.9 cm/decade,
strong), Iran (−12.6, strong) and India (−4.7, moderate) reproduced with independent code (PASS WITH
NOTES). Blocking issues before publishing:
1. **Yearly stability check cannot pass smooth, slowing declines.** Its OLS effective sample size
   falls to the floor of 3 (1 degree of freedom) when yearly residual r1 ≳ 0.75, so 42 of 123 GRACE
   cards are downgraded: Greenland −118 cm/decade "a hint", Norway −60 "none", Saudi Arabia −7.6
   "a hint", Arabian Peninsula −5.3 [−5.8, −4.8] "none". Options for the stats lead (ADR):
   (a) treat the yearly check as not informative when its n_eff < 5 and use its MK-YW result;
   (b) cap a downgrade at one level; (c) at least: headline "clear decline, not confirmed by the
   yearly check", no "moves up and down" sentence and no years-to-detection when the full record
   is strong or moderate. The rule applies to every variable, so re-check other layers too.
2. **Iran: Caspian Sea inside the product's land mask** (up to ~13% of the trend; −10.9 without the
   coastal squares, still strong): needs a caveat.
3. **Norway includes Svalbard** (country cluster rule): its −60 is glacier ice loss; exclude or label.
4. **Mission-gap caveat**: say "may jump (offset or a real wet/dry spell)"; the Pettitt approximate p is
   liberal (AR(1) Monte Carlo p 0.5–0.8 for the 3 flagged places); set the gap end to 2018-09 (2018-08
   and 2018-09 are missing too) or say why not; ar6_eau's break is the 2017–19 drought, not the gap.
5. India declines to 2019 and partly recovers since: consider a "decline, partial recovery" finding.
6. Methods: solutions sit on their window-midpoint month (up to one month off).
