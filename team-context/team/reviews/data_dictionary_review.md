# Data dictionary review

**Reviewer:** Critique  
**Date:** 14 November 2026, afternoon (Europe/Kiev)  
**Scope:** Analytical correctness of `team-context/data/docs/data_dictionary.csv` (222 rows), `data_dictionary.md`, `station_coverage.csv`, `data_overview_extras.md`, and `scripts/build_data_dictionary.py`. Data-analysis use only. AppEEARS “still blocked” wording was not flagged (already being fixed). No files under `spaceapps/` or `ukraine_samples/` were modified.

The dictionary is mostly careful and numbers-first. Local extracts I spot-checked are right: POWER T2M 1981-01–2025-12, 464 cells, 250,560 records; solar 1984-01–2025-12, 144 cells, 72,576 records; GSOM 204 UP stations, 111,281 station-months, 1900-01–2026-10, with the published decade PRCP counts (2020s: 3 stations); MODIS C6.1 Terra CMG Feb 2000–Oct 2026, 321 months; `station_coverage.csv` matches the GHCN and GSOM files with 0 date/`n_valid` disagreements on all GSOM rows and all 135 GHCN station-variable rows (28 cities; SNWD at 26, TAVG/TMAX/TMIN at 27). Temperature and LST overlap *r* and slopes in the extras table recompute exactly from the revised annual series. Global-size arithmetic is consistent with the cited inputs; I did not re-query CMR, so I could not independently confirm hit counts or UMM file sizes. Official pages: MOD13C2/MOD11C3 Collection 6.1 is still the public CMG product (DOI 10.5067/MODIS/MOD13C2.061 and 10.5067/MODIS/MOD11C3.061); Collection 7 land reprocessing began 2 February 2026. AIRS3STM 7.0 is the correct AIRS-only monthly collection (2002-09 to present). POWER solar splice at 2000/2001 is real.

## Blocking

1. **GPM IMERG monthly units are wrong, and flux-rate conversions are missing from the pull checklist.**  
   `data_dictionary.md` / the CSV list `GPM_3IMERGM V07` units as **mm**. The official GPM IMERG Final monthly product (3IMERGM V07) stores precipitation as a monthly *mean rate in mm/hr*, not millimetres per month. Monthly totals are `value × hours in that calendar month` (about 672–744). Treating the field as mm (or as mm/day) would put any IMERG vs POWER/station comparison off by roughly two to three orders of magnitude. The same gap applies once MERRA-2 `M2TMNXFLX` or GLDAS Noah runoff/evapotranspiration/precipitation are pulled: those fluxes are typically **kg m⁻² s⁻¹**, which convert to mm/day as `× 86400`. GLDAS soil moisture in kg m⁻² (≈ mm) is stated correctly; the other fields are not.  
   **Fix:** State IMERG units as mm/hr and give the hours-in-month conversion. Use the **Final** run for climate trends (not Early/Late). Add the kg m⁻² s⁻¹ → mm conversion to checklist item 5 for MERRA-2 and GLDAS flux variables.

## Should fix

2. **The overlap table is numerically correct, but the precip “how to read” note overclaims.**  
   Recomputed from `$UKRAINE_SAMPLES/analysis/`: GSOM vs GHCN PRCP anomalies, 1981-2000, n=20, *r*=0.891, OLS **136.840 and 92.467 mm/decade** — exactly as published. Those 20-year slopes are a start-end effect (GSOM anomalies are −178 to −311 mm in 1981-1983 and much less dry later) and are about nine times the 1981-2024 GSOM slope of **15.541 mm/decade**. The extras text still calls 1981-2000 “the fairer station-vs-station check,” which invites a headline rate the longer record does not support. A second trap in the same table: GHCN OLS is **8.961 mm/decade** on the GSOM-overlap (n=43, 2021 dropped because GSOM has no 2021) but **15.572 mm/decade** on the full 1981-2024 GHCN series (n=44). Dropping only 2021 accounts for the whole difference.  
   **Fix:** Keep *r* as the agreement metric for 1981-2000. Do not present 137 / 92 mm/decade as a preferred climate rate. Disclose that the 8.961 vs 15.572 GHCN pair is one missing year, not two different products.

3. **The preprocessing checklist is incomplete for the datasets you are about to pull, and it is missing two rules already approved in `trend_methods.py`.**  
   Item 11 correctly requires time-aware Sen, HAC lag-1 (annual) / lag-3 (monthly), Hamed–Rao at lag=3, no Yue–Wang wording, and a caution on negative residual AR. It does not carry over the approved short-record label (“too short for climate inference”) or the rule that strongly negative residual *r* (*r* < −0.3) must not confirm “robust” via Hamed–Rao. There is also no general minimum record length for a climate-trend claim (SWOT’s 3.3 years are flagged elsewhere; the checklist should say it once). Missing product steps, all documented on official pages and not in the extras checklist:
   - **GRACE/GRACE-FO JPL mascon RL06.3:** the native record has an ~11-month mission gap (GRACE ends July 2017, GRACE-FO starts June 2018; August 2017–May 2018 are missing). Do not interpolate the gap into a trend without saying so.
   - **OMI OMNO2d:** the row anomaly begins in 2007; use `XTrackQualityFlags` and do not treat unflagged row-anomaly pixels as a NO₂ trend.
   - **Annual means:** say whether the annual value is the unweighted mean of 12 monthly means or a day-weighted mean (POWER ANN is essentially day-weighted; the approved T2M series is the unweighted month-mean, +0.553 vs +0.551 °C/decade for 1981-2025).
   - **POWER solar:** official POWER documentation still places GEWEX SRB at 1984-01-01–2000-12-31 and CERES SYN1deg from 2001-01-01, and (in Data v10) applies quantile mapping to pre-2001 values. The on-disk solar header only names CERES SYN1deg and does not state a POWER data version, so I could not confirm that this extract includes the v10 correction. The checklist should mention that official correction rather than describing SRB as an unadjusted splice.
   - **GLDAS 2.1 vs 2.2:** 2.1 is the right long climate run; 2.2 assimilates GRACE and is not a drop-in substitute.
   - **Terra vs Aqua** when 1 km or Aqua MODIS is added (current CMG extract is correctly labelled Terra-only).  
   **Fix:** Add the short-record / negative-AR rules and the bullets above to the checklist. I could not re-verify live CMR granule counts.

4. **Kherson is still described as a confirmed step.**  
   `data_dictionary.md` (Hydrocron caveats): “Kherson / lower Dnipro may include the Kakhovka dam breach (a step, not a trend).” Checklist item 10: “the Kakhovka **step** at Kherson (do not fit a linear trend there).” The approved findings (14 Nov 2026) are that this is **not** a confirmed step: seasonally matched April–June difference −0.006 m, Mann–Whitney p=0.687; month FE + step −0.031 m, HAC lag-3 p=0.530. Do not fit a linear climate trend, but do not call it a step either.  
   **Fix:** Match the approved wording (“not a confirmed Kakhovka step”; too short and too seasonal).

5. **GHCN PRCP and SNWD rows copy a TMAX/TAVG end date.**  
   The `date_last` columns are right (PRCP 2026-03-20, SNWD 2026-03-12, TAVG/TMAX/TMIN 2026-11-06 — all match the QC-cleaned station files). The shared caveat on every GHCN row still says “Record through 2026-11-06.”  
   **Fix:** Per-variable end dates in the caveat, or drop the copied sentence and rely on `date_last`.

---

**Not flagged as errors:** Collection 6.1 vs C7 for the current MODIS CMG extract (C6.1 is what they have and is still the public CMG collection). Local POWER/GSOM/GHCN/MODIS start-end dates, fill values, and scale-factor notes (`raw/10000` with the inverted `scale_factor` attr; LST `× 0.02`; POWER −999; GHCN tenths + QFLAG). QV2M in g/kg. SWOT Version D, Hydrocron fill/`ice_dyn_f`/`dschg_c`, and “too short for a climate trend.” Global size estimates are not off by orders of magnitude if the cited CMR/catalog inputs are right. The dictionary does not list DOIs; that is a citation gap, not a wrong number.
