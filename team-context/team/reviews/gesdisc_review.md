# GES DISC extension review (Ukraine trend analysis)

Date: 14 November 2026, Europe/Kiev  
Reviewer: Critique  
Entry: `$UKRAINE_SAMPLES/_staging/revise_analysis.py` + `gesdisc_extend.py`  
Outputs reviewed: `$UKRAINE_SAMPLES/analysis/trend_summary.csv`, `headline_findings.txt`  
Scratch only under `team-context/team/reviews/`. Their files were not modified.  
Official GLDAS reference: GES DISC *README Document for NASA GLDAS Version 2 Data Products*, last revised 13 August 2025 (`https://hydro1.gesdisc.eosdis.nasa.gov/data/GLDAS/README_GLDAS2.pdf`).

## Verdict: approved with fixes

The 72-test family, primary family of 11, IMERG units/Final-run path, AIRS variable choice (SurfAirTemp, ascending+descending), Qs *labelling* (storm surface runoff, Qsb not claimed as total runoff), MERRA-2 vs POWER same-source disclosure, and headline (still POWER/GSOM/GHCN warming; no “Ukraine soils drying” phrase) are in good shape. `revise_analysis.py` run in a ROOT-retargeted copy under `team-context/team/reviews/ukraine_samples_repro` reproduced `trend_summary.csv` and `headline_findings.txt` byte-for-byte (md5 `6a04b11568c4db97b427d6892498a08d` / `4d1afeea04ace7ec3fb5e17516115cb3`). The original tree was not written.

This is not a full approval: GLDAS monthly `Qs_acc` was not converted with the official `× 8 × days` formula (published Qs totals and slopes are too small by about 240×); GLDAS-2.1 soil-moisture / Evap / Tair “robust” calls lack the official forcing-inhomogeneity caveat, and the soil-moisture drying is not significant in JJA or in low-SWE months; GLDAS-2.1 Tair +0.922 °C/decade was not compared to MERRA-2/POWER on the same 2000–2025 window (those are +0.737); and the AIRS–MERRA-2 difference series was not reported (AIRS warms more slowly).

## Ranked issues

### 1. GLDAS Qs_acc monthly totals were not converted (must fix before any Qs number is used)

**Evidence.** The January 2000 GLDAS-2.1 sample file labels `Qs_acc` as kg m-2, long name “Storm surface runoff”, `cell_methods = time: mean`. Official README §3.5.6: monthly files are straight averages of 3-hourly data, so accumulated fields have units *per 3 hours*. Monthly total is

`Qs_acc (month) {kg m-2} = Qs_acc {kg m-2 / 3 hr} × 8 {3 hr/day} × days_in_month`.

`download_gesdisc_ukraine.py` correctly converts `Evap_tavg` (kg m-2 s-1 × 86400 × days). It leaves `Qs_acc` unscaled and `gesdisc_extend.py` sums those values as annual mm. Published GLDAS-2.1 annual Qs mean is 0.096 mm/year (range 0.022–0.232). After the official formula, annual mean is 23.11 mm/year (range 5.33–56.52). The published 2000–2025 slope is −0.043 mm/decade (HAC p=4.1e-05, HR p=0.00111, “robust”). On the corrected annual sums: OLS −10.40 mm/decade, Sen −9.63, HAC p=3.6e-05, HR p=0.00111, still robust. GLDAS-2.0 annual Qs (uncorrected mean 0.062 mm/year) has the same scaling error.

**What they got right.** The long name and findings text correctly call Qs “storm surface runoff” and say it is not total runoff (`Qsb` was not requested). No headline claims “runoff is declining.” “Bbox-mean totals are small” is an artifact of the missing conversion, not a physical result.

**Fix.** Apply `× 8 × days` in the monthly-to-annual step for all `_acc` fluxes, republish the 2.0 and 2.1 Qs rows, and drop or rewrite the “totals are small” clause. Keep the “not total runoff” label. Do not treat Qs as Qs+Qsb.

### 2. GLDAS-2.1 soil-moisture drying is statistically robust on the annual 2.1 series only; it is not a demonstrated climate/soil fact (must caveat; do not headline)

**Evidence, official docs.** README §1.2.3: GLDAS-2.1 is forced by NOAA/GDAS atmospheric analysis, disaggregated GPCP V1.3 daily precipitation, and AGRMET radiation (AGRMET added 1 March 2001; January 2000–February 2001 are GDAS+GPCP only). Precipitation forcing is GPCP, not IMERG. §1.5.3: an apparent AGRMET climatology shift after 2011 could not be removed by the SRB scaling. The 13 August 2025 revision adds a switch to GALWEM radiation from 9 June 2025 (inside their last complete year, 2025). §1.6 Quality Issues: combining 2.0, 2.1, and 2.2 “may result in temporal discontinuities due to biases between the meteorological datasets,” and “a meteorological forcing dataset [may contain] its own discontinuities.” Findings contain no mention of “forcing” or inhomogeneity.

**Evidence, numbers (all independently recomputed).**  
- GLDAS-2.1 2000–2025 (n=26): SoilMoi0_10cm −1.260 kg/m²/decade (HAC p=0.00306, HR p=7e-06, robust); RootMoist −14.382 (HAC p=0.0130, HR p=0.00930, robust); Evap +16.020 mm/decade (HAC p=0.0116, HR p=0.0343, residual r=−0.27, called robust). These match the published figures.  
- GLDAS-2.0 1948–2014 SoilMoi: +0.085, not significant.  
- Overlap 2000–2014 (n=15): 2.0 SoilMoi −0.068 (n.s.) vs 2.1 −0.669 (n.s.) — already ~10× steeper in 2.1; RootMoist 2.0 −3.94 vs 2.1 −16.02. 2.1 is wetter in the overlap (SoilMoi bias 2.0−2.1 = −1.12 kg/m²; RootMoist −15.51).  
- Seasons, 2.1 2000–2025: JJA SoilMoi −0.90, HAC p=0.092, HR p=0.113, **not significant**; months with SWE < 1 kg/m² −0.55, HAC p=0.110, HR p=0.158, **not significant**; AMJJAS is robust (−0.91); DJF is stronger (−1.50) but method-dependent (HR p=0.071). JJA RootMoist −10.55, not significant.  
- Annual soil moisture is the unweighted mean of all 12 months. There is no unfrozen / snow-free / growing-season mask in the scripts.  
- Same-window precip (2000–2024) is not a significant drying signal: IMERG +3.81 mm/decade (n.s.), POWER PRECTOTCORR +13.75 (n.s.), MERRA-2 PRECTOTCORR +13.90 (n.s.).

**Units.** Top-layer `SoilMoi0_10cm_inst` in kg m-2 is the official unit (water amount in the 0–10 cm layer, not volumetric water content). Monthly means 14.0–40.4 kg/m² (mean 26.0) are physically sensible (~26 mm in a 100 mm layer). RootMoist mean 268 kg/m² is likewise sensible. These are `_inst` states and were correctly left in kg/m². Evap conversion (kg m-2 s-1 × 86400 × days) is correct.

**Fix.** Add the README forcing caveats next to every 2.1 “robust” soil, Evap, SWE, and Tair line. Do not headline “Ukraine soils drying.” Report JJA / low-SWE SM (currently not significant). Keep 2.0 and 2.1 un-spliced (already done). Treat 2.1 hydrological trends as potentially reflecting forcing changes.

### 3. GLDAS-2.1 Tair +0.922 °C/decade is steeper than MERRA-2 and POWER on the same 2000–2025 window

**Evidence (independently recomputed, complete years 2000–2025, n=26).**  
- GLDAS-2.1 Tair: OLS +0.922 °C/decade, Sen +0.916, HAC p=4.49e-06, HR p=5e-05, robust (matches findings).  
- MERRA-2 T2M: OLS +0.737, Sen +0.723, HAC p=9.11e-05, HR p=3.74e-09, robust.  
- POWER T2M: OLS +0.737, Sen +0.718, HAC p=9.53e-05, HR p=2.52e-09, robust.  
- GLDAS-2.1 vs MERRA-2: r=0.977, bias (GLDAS−MERRA) = −0.310 °C. vs POWER: r=0.977, bias = −0.231 °C.

The sign is plausible and the series track closely, but the 2.1 rate is +0.185 °C/decade (~25%) steeper. Findings never report this same-window check (they only give POWER T2M 2001–2025 +0.797, a different window). Part of the gap may be domain: GLDAS used 2128 finite land cells every month (bbox at 0.25° is ~2317 cells; ocean and inland water are already filled). MERRA-2 T2M_n is 464/464 cells (all bbox cells, including the NW Black Sea). IMERG precipitation_n is 14480/14480. AIRS SurfAirTemp_n is typically 288 (a few missing retrievals). POWER is also an unmasked bbox mean. I did **not** compute a land-masked MERRA-2 series, so I cannot say how much of the +0.185 gap is land-vs-sea vs forcing inhomogeneity.

**Fix.** Publish the 2000–2025 Tair cross-check. Do not treat +0.922 as interchangeable with the headline +0.55 to +0.67 (different window and a land-only LSM). A land-masked MERRA-2 comparison would isolate the sea-inclusion effect.

### 4. 2.0-to-2.1 overlap bias: direction not stated; no-splice rule not written (they did not splice)

**Evidence.** Independently: n=15 years 2000–2014, r=0.913, mean 2.0 = 9.348 °C, mean 2.1 = 8.853 °C, bias (2.0 − 2.1) = +0.495 °C, RMSE 0.562 °C. Findings line 95 reports “r=0.913, bias=+0.495 °C, RMSE=0.562 °C” without saying 2.0 is the warmer series. The two streams are kept as separate trend families; there is no spliced long series in the CSV. Findings never say “do not splice without adjustment.” Official README §1.6 requires that warning. 2.1 itself has documented internal breaks (1 March 2001 AGRMET; post-2011 AGRMET climatology shift; 9 June 2025 GALWEM).

**Fix.** State the sign (2.0 warmer by 0.495 °C). Add an explicit no-splice sentence. If a long series is ever required, adjust by the overlap bias, document the join date, and still caveat 2.1 internal discontinuities.

### 5. AIRS +0.92 °C warm bias is mostly a level offset, but the trend rate is not the same as MERRA-2; no difference series was published

**Variable.** Sample and monthly CSV use `SurfAirTemp_A` and `SurfAirTemp_D` (surface air temperature, not skin). The series is the mean of ascending (Aqua ~13:30, day) and descending (~01:30, night). Findings header is accurate (“ascending+descending mean”).

**Bias vs trends (independently recomputed, complete years 2003–2025, n=23).** AIRS vs MERRA-2: r=0.942, bias (AIRS − MERRA) = +0.917 °C, RMSE 0.961 °C — matches findings. Same-window OLS: AIRS +0.721 °C/decade (robust, matches findings), MERRA-2 +0.917, POWER +0.918. AIRS-minus-MERRA-2 difference series: OLS −0.196 °C/decade, Sen −0.147, HAC p=0.079, HR p=0.081, **method-dependent, not a clear detection**. The 2025 difference collapses to +0.040 °C (other years are typically +0.6 to +1.5). AIRS 2025 has all 12 months. Excluding 2025 (n=22): difference OLS −0.110, HAC p=0.232, not significant; mean bias +0.957 °C. I could not verify why 2025 almost matches MERRA-2.

So the +0.92 °C figure is primarily a level offset, but AIRS still understates the 2003–2025 warming *rate* by about 0.20 °C/decade relative to MERRA-2/POWER. That was not reported.

**Fix.** Publish the AIRS − MERRA-2 difference series and the same-window slopes. Flag 2025 as an influential year. Keep calling the variable SurfAirTemp (A+D), not skin temperature.

### 6. Land-mask / grid consistency (should fix for cross-source claims)

cos(lat) weighting is implemented in `download_gesdisc_ukraine.weighted_mean` and stated in `gesdisc_extend.DOMAIN`. There is no land mask: fill/finite/bbox only. That is disclosed (“no land mask”; POWER domain caveat also says no country polygon / land mask). The inconsistency is across *products*: GLDAS is land-only by construction (2128 cells); MERRA-2, IMERG, AIRS, and POWER include the NW Black Sea. Cross-checks that mix GLDAS Tair/SM with MERRA-2/POWER/IMERG are therefore not like-for-like.

Day-weighted annual means: GLDAS-2.1 Tair unweighted (their `annualize`) +0.9223 vs day-weighted +0.9213 °C/decade; max |unweighted − day-weighted| = 0.097 °C, mean abs 0.056 °C. Negligible for the trend. They use the unweighted mean of 12 monthly means for temperature and soil moisture, and sums for precip/Evap/Qs. Not a ranked defect, but it should stay documented.

**Fix.** Either land-mask MERRA-2/IMERG/AIRS/POWER to the GLDAS land domain for overlap comparisons, or state clearly that GLDAS means are land-only and the others are not.

### 7. IMERG units and Final run are correct; slope agreement with POWER/MERRA-2/stations is weak; Hamed–Rao is strongly anti-conservative

**Units and run.** Sample `Grid/precipitation` units are mm/hr. Conversion is `× 24 × days` (= hours in the month) to `precip_mm`, then annual sum. Findings state this. Filenames are `3B-MO.MS.MRG.3IMERG....V07B.HDF5`; the section header is “GES DISC GPM IMERG Final monthly (GPM_3IMERGM v07)”. Residual r = −0.300176. The CSV correctly sets `hr_anti_conservative=True` and `hr_strongly_anti_conservative=True` (threshold is r < −0.3). Findings print r=−0.30 and only the weaker “anti-conservative when residual lag-1 AR is negative” sentence. The call is already “not significant” (HAC p=0.817, HR p=0.624), so wording is not an overclaim, just slightly under-specified.

**Same-window 2000–2024 trends (n=25), independently recomputed.** IMERG +3.807 mm/decade (Sen +11.17), not significant — matches findings. POWER PRECTOTCORR +13.75 (n.s.); MERRA-2 PRECTOTCORR +13.90 (n.s.); MERRA-2 PRECTOT +16.06 (n.s.); GHCN-Daily raw regional −18.08 (n.s.; the 2020s network is already disclosed as thin). Interannual r: vs MERRA-2 PRECTOT 0.901, vs PRECTOTCORR 0.930, vs POWER 0.929, vs GHCN raw 0.692. Biases match findings (IMERG wetter than PRECTOTCORR by ~+84 mm/year). So IMERG *tracks* MERRA-2/POWER year to year, but the *trend slopes* do not agree closely, and the station series has the opposite sign; all five are non-significant. Do not read this as IMERG confirming a precipitation trend.

**Fix.** Print residual r to three decimals, or note that it meets the r < −0.3 rule. Add the same-window slopes (all n.s.) if IMERG is compared to POWER/MERRA-2/stations. I did not independently confirm whether the official IMERG V07 record starts in January or June 2000; GES DISC served V07B files with finite values for January–May 2000, and 2000 is included as a complete annual year.

### 8. Minor: AIRS (and some MERRA-2) seasonal windows include 2026, annual windows do not

AIRS SurfAirTemp JJA is reported as n=24, 2003–2026 (CSV `start=2003, end=2026`). Annual AIRS correctly drops incomplete 2026 and uses 2003–2025. JJA 2026 is complete in the file (through 2026-10). Inconsistent year-end, not a units error. MERRA-2 T2M DJF is similarly labelled through 2026. Prefer a consistent “complete seasons only, ending 2025” rule, or say why 2026 is kept for seasons.

## Answers to the five questions (short)

**(1) GLDAS-2.1 Tair, overlap, SM drying, units, snow season.** Tair +0.922 is the same sign as MERRA-2/POWER 2000–2025 (+0.737 / +0.737) and tracks them (r=0.977) but is substantially steeper; that comparison is missing from the findings. Keep 2.0 and 2.1 separate; the +0.495 °C overlap bias is 2.0 minus 2.1 (2.0 warmer). Official docs confirm 2.1 forcing inhomogeneity (GDAS + GPCP v1.3 + AGRMET; not IMERG) and warn against unspliced combination. Soil-moisture drying is robust only on the 2.1 *annual* series; JJA and low-SWE months are not significant; 2.0 shows no long-term drying. 0–10 cm in kg/m² is the correct unit and the magnitudes make sense. Evap/precip rate conversions are correct. Snow/frozen season was not handled (annual mean of all 12 months).

**(2) Qs.** Labelled correctly as storm surface runoff and excluded from total-runoff (Qs+Qsb) claims. The *values* are wrong until `× 8 × days` is applied (issue 1).

**(3) AIRS.** SurfAirTemp, ascending+descending mean (day+night), not skin. The +0.92 °C bias is mainly a level offset; the difference-series trend is not clearly significant (HAC p=0.079), but same-window slopes still differ (AIRS +0.721 vs MERRA-2 +0.917). 2025 is an outlier in the difference.

**(4) IMERG.** Units fix is correct; Final V07B run is what was downloaded; Hamed–Rao is flagged strongly anti-conservative in the CSV (r=−0.300176). Trends agree with POWER/MERRA-2/stations only in being non-significant and in interannual correlation, not in slope.

**(5) MERRA-2 PRECTOTCORR vs POWER, r=1.000 (precip r=0.9998; T2M r=1.000).** Same MERRA-2 source; the tiny residual is aggregator vs native monthly means, as they already say. The opening headline attributes warming only to POWER, GSOM, and GHCN — it does not count MERRA-2 as a second independent confirmation. Keep it that way.

## Also checked (no new defect, or already covered)

- **Multiple testing.** CSV has 72 rows; `n_tests_in_full_family` is 72; Bonferroni α unique value 0.00069444. Independently: HAC p<0.05 = 48; HR p<0.05 = 50; both = 47; Bonferroni rejects = 32; BH-FDR rejects = 47. Matches the methods preamble. Primary family still 11 series (`primary_test=True` on the same POWER/GSOM/GHCN/MODIS annual set named in the preamble); Bonferroni α=0.004545. GES DISC rows are not in the primary family.
- **Headline overclaim.** The standing headline is still 1981–2025 warming +0.55 to +0.67 °C/decade across POWER, GSOM, and GHCN. The phrase “Ukraine soils drying” does not appear. The risk is the uncaveated “robust” labels on 2.1 SoilMoi, RootMoist, Evap, and Qs (issues 1–2).
- **Reproduction.** Copy at `team-context/team/reviews/ukraine_samples_repro` with ROOT retargeted in `revise_analysis.py`, `gesdisc_extend.py`, and `revise_charts_and_docs.py` (including the second hardcoded `ANALYSIS` path). `trend_summary.csv` and `headline_findings.txt` are byte-identical to the originals. Pandas `dayofyear` deprecations and SWOT time-format warnings still appear; `/tmp` pickle leftover remains cosmetic.

## What I could not verify

- How much of the GLDAS-2.1 vs MERRA-2 Tair rate gap is land-only vs sea-included vs forcing (no land-masked MERRA-2 series was built).
- Why the 2025 AIRS − MERRA-2 difference falls to +0.040 °C.
- Whether official IMERG V07 begins in January or June 2000 (Jan–May 2000 files exist and were used).
- Qsb (subsurface runoff) magnitudes — the variable was not downloaded.
- Whether SoilMoi is liquid-only or liquid+ice, beyond the SWE < 1 kg/m² monthly subset above.
- Whether any 2026 GLDAS-2.1 months in the monthly file are Early Product (annual trends stop at 2025, so this does not enter the published slopes).
