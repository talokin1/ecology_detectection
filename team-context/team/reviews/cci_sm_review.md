# ESA CCI SM COMBINED v09.2 Ukraine-bbox review

Date: 14 November 2026, Europe/Kiev  
Reviewer: Critique  
Target: `$UKRAINE_SAMPLES/extra/cci_sm/` (README.md, monthly `.nc`/`.csv`, `cci_sm_trends_preliminary.txt`)  
Period: 1978-11 to 2024-12, 554 months, CEDA OPeNDAP daily → monthly, units m³ m⁻³  
Methods: imported `$UKRAINE_SAMPLES/_staging/trend_methods.py` (`trend_stats`); recomputes in `team-context/team/reviews/cci_sm_recompute.py` (`nice -n 19`, one thread). Scratch only under `team-context/team/reviews/`. No files outside that directory were modified.

## Verdict: approved with fixes

The extract is complete and correctly built: 554 months, units m³ m⁻³, fill excluded, intersection-area (spherical / cos(lat)) weights, same bbox as the other sources, and the published headline numbers all recompute from the CSV. The 1991–2024 all-month deseasonalized series is genuinely indistinguishable from zero. The Apr–Oct −0.003 m³ m⁻³/decade slope also recomputes, and it survives the equally spaced Apr–Oct seasonal-mean-per-year test that should be the primary call.

Two documentation/interpretation problems need to be fixed before this is handed to Thinker as analysis-ready: (1) COMBINED v09.2 **is** break-adjusted — the “no break adjustment / only v07.1” claim is inverted — and (2) residual 2002 and 2007 mean shifts are still visible in this bbox, and the Apr–Oct drying is start-point dependent (n.s. from 2002; sign flips from 2007). Do not headline “drying.” Keep 1991–2024 as the analysis window; do not headline the full 1978–2024 record.

## Ranked items

### 1. COMBINED v09.2 is break-adjusted; the “only v07.1” claim is backwards (should-fix)

The README, CSV header caveats, and `cci_sm_trends_preliminary.txt` all say v09.2 is a multi-sensor merge “with no break adjustment” and that “the open `break_adjusted_COMBINED` tree only goes to v07.1.” The separate tree ending at v07.1 is real, but the reason is the opposite of what is written.

- PVIR v08.1: “The break-adjusting routine, previously performed only on a separately distributed product, is now included in the main COMBINED product,” using Preimesberger et al. (2021), with ERA5 as the reference for detection and correction. Official transition dates: 1987-07-09, 1991-08-05, 1998-01-01, 2002-06-19, 2007-01-01, 2010-01-15, 2012-07-01, 2015-03-31.
- PUG v09.1, processing step 6: “Break-adjusting all products using the method of Preimesberger et al. (2021).”
- PVIR v09.1 executive summary: “The break-adjusting routine is now included in all distributed products.”
- The project page for v09.2 (a temporal extension of v09.1 to 2024-12, plus an uncertainty-budget, SMOS-angle, and rescaling-methodology update) makes Preimesberger et al. (2021) **compulsory** when citing COMBINED.

Drop the “not break-adjusted” label. Cite Preimesberger 2021. Still caveat that residual breaks can remain (see item 2) and that the homogenization is ERA5-referenced, so COMBINED is not independent of ERA5 on that step.

### 2. Residual 2002 and 2007 shifts, and Apr–Oct drying is start-point dependent — do not headline “drying” (should-fix)

Even after official break adjustment, a quick mean-shift check on the coverage-filtered, deseasonalized series still sees two material steps in this bbox (36-month windows, full record; Welch two-sample test):

| Transition | Δ mean (post−pre) | Cohen’s d | Welch p | Levene p |
|---|---|---|---|---|
| 1987-07 SMMR→SSM/I | +0.0098 | +1.00 | 1.2×10⁻⁴ | 0.086 |
| 1998-01 TMI | −0.0064 | −0.59 | 0.019 | 0.50 |
| **2002-06 AMSR-E** | **+0.0090** | **+0.76** | **0.0023** | 0.080 |
| **2007-01 ASCAT** | **−0.0078** | **−0.68** | **0.0053** | 0.070 |
| 2010-01 SMOS, 2012-07 AMSR2, 2015-04 SMAP | ≤0.003 | ≤0.26 | ≥0.30 | — |

The 1987 SMMR break is why the full 1978–2024 record must not be headlined (their “method-dependent” call is right). 1991–2024 avoids 1987 and is a defensible window relative to the full file (SSM/I is then established; official CCI trend maps often start 1991/1992). It is not a single-sensor period.

On the recommended Apr–Oct **seasonal mean per year** (7/7 months, equally spaced, annual HAC lag-1 + Hamed–Rao):

- 1991–2024: n=34, OLS **−0.00266** / Sen **−0.00251** m³ m⁻³/decade, HAC lag-1 p=0.0081, HR p=0.015. Call: robust at 0.05. (TFPW p=0.057, just above 0.05; residual r=−0.10 so HR is mildly anti-conservative.)
- 1992–2024 (after the official 1991-08 break): still robust, OLS −0.00223, HAC p=0.025, HR p=0.042.
- **2002-06–2024: n.s.**, OLS −0.00201, HAC p=0.38, HR p=0.24.
- **2007–2024: sign flips**, OLS **+0.00251**, Sen +0.00084, n.s.

So the 1991–2024 Apr–Oct slope is real in that window and under the correct test, but it is not stable to a later start and may still carry residual 2002/2007 steps. Do not call it a robust climate “drying” result. Report the seasonal-mean series as the primary Apr–Oct test, and state the start-point and residual-break caveats. The all-month 1991–2024 series (~0.000, n.s.) can stand as the headline for the mixed-season record.

### 3. Reframe Apr–Oct as a seasonal-mean-per-year series; the monthly “robust” call uses a gapped series (should-fix)

Apr–Oct is the right season: in 1991–2024 every Apr–Oct month passes the coverage filter (238 = 34 × 7). Winter is the gap. The published Apr–Oct test is a *monthly* deseasonalized series with a 5-month hole every year (median Δt=1/12 yr, max Δt=0.5 yr, 33 gaps). `hr_unequal_spacing` is True, and HAC lag-3 is also designed for equally spaced monthly data. Their note (“Hamed–Rao assumes equal spacing; this series has gaps”) is correct; the “robust at 0.05 (HAC lag-3 and Hamed–Rao)” wording should not be the primary call.

The equally spaced alternative they were asked to consider — one Apr–Oct mean per year — is complete 7/7 for all 34 years of 1991–2024, has `hr_unequal_spacing=False`, and gives the same slope (−0.00266) with annual HAC + HR still under 0.05 (item 2). Use that. Yue–Wang on the monthly Apr–Oct series is 8.9×10⁻¹³ and should stay out of the wording (known to be over-confident on these series).

### 4. `n_valid_days >= 5` is too loose for SMMR / the full record; it is adequate for 1991–2024 Apr–Oct (should-fix, window-dependent)

Mean valid days and filter pass rates by era (unfiltered file; filter = `weight_coverage >= 0.5` and `mean_n_valid_days >= 5`):

| Era | n mo. | mean days (p25) | pass | Apr–Oct days / pass | DJF days / pass |
|---|---|---|---|---|---|
| 1978-11–1987-06 SMMR | 104 | **7.0 (5.1)** | 0.76 | 8.5 / 0.97 | **4.4 / 0.41** |
| 1987-07–1991-07 SSM/I early | 49 | 19.9 (15.4) | 0.98 | 22.8 / 1.00 | 13.5 / 0.92 |
| 1991-08–2002-05 SSM/I+TMI | 130 | 18.4 (13.9) | 0.97 | 22.6 / 1.00 | 10.3 / 0.91 |
| 2002-06–2006-12 +AMSR-E | 55 | 20.5 (18.0) | 0.96 | 24.9 / 1.00 | 12.0 / 0.85 |
| 2007-01–2011-09 +ASCAT | 57 | 21.7 (12.9) | 0.95 | 28.5 / 1.00 | 8.5 / 0.79 |
| 2011-10–2012-06 AMSR-E gap | 9 | 18.2 (10.3) | 0.89 | 27.9 / 1.00 | 8.8 / 0.67 |
| 2012-07–2015-03 +AMSR2 | 33 | 19.4 (9.2) | 0.91 | 27.6 / 1.00 | 6.8 / 0.67 |
| 2015-04–2024-12 +SMAP | 117 | 21.8 (14.9) | 0.94 | 27.7 / 1.00 | 10.5 / 0.75 |

SMMR months often have only ~5–8 valid days, so the threshold lets almost the lower quartile through and treats a 5-day SMMR mean as equivalent to a ~28-day ASCAT/SMAP mean. Do not use 1978–1990, or the full-record monthly series, as a climate trend without a much stricter day cut or a warm-season-only annual mean. For **1991–2024 Apr–Oct**, every month is well sampled (~16–30 days); tightening `min_days` to 10 leaves the Apr–Oct 7/7 seasonal slope unchanged at −0.00266. Tightening to 15–20 days starts dropping years and the seasonal test becomes method-dependent or n.s. — that is a sample-size effect, not a reason to keep ≥5 for SMMR.

The 1991–2024 all-month filter drops 20 months, all in DJF (and one March): Jan 6, Feb 9, Mar 1, Dec 4. DJF keep-rate is 91% in 1991–2001 and ~77% after 2002; DJF day counts have no trend over 1991–2024 (p=0.86). Kept vs dropped DJF means are almost identical (0.2496 vs 0.2492), so winter-coverage bias is not an obvious mean shift in this window, but those winters still should not be mixed into a “monthly” headline. The calendar-month coverage table in the preliminary notes averages SMMR and modern winters together (DJF ~8.4–8.5 days) and should be split by era.

### 5. README overclaims independence from GLDAS (and misses ERA5) (should-fix)

Official FAQ (CCI SM): the COMBINED data set is rescaled to **GLDAS-Noah v2.1** before merging, “to obtain a final product in absolute volumetric units [m³ m⁻³]. … this step imposes the absolute values and dynamic range (min–max) of the GLDAS-Noah product on the combined product. As a consequence, the combined product CANNOT be considered an independent data set representing absolute true soil moisture.” ATBD/PUG v09.x: all L2 inputs to COMBINED are CDF-matched to GLDAS v2.1. Break adjustment (item 1) additionally uses ERA5.

The README currently says this is “a different observing system from GLDAS / ERA5-Land” and an “Independent-of-stations satellite soil moisture cross-check of ERA5/ERA5-Land `swvl` and (when available) TerraClimate / GLDAS soil moisture.” That overstates independence of the *absolute level* and the climatology, and of the homogenization step. Anomalies and trends still come from the satellite retrievals, with the residual-break caveat above. Say: not independent of GLDAS-Noah in absolute level or dynamic range; not independent of ERA5 in the break adjustment; usable as a satellite-based anomaly/trend cross-check only with those labels. Surface layer is ~0–5 cm, not a root-zone or GLDAS layer-2 equivalent.

### 6. Headline numbers recompute; spatial weights, units, and bbox are correct (OK, with notes)

Imported `trend_stats` on the coverage-filtered, window-climatology-deseasonalized CSV reproduces the published text to the printed precision:

- 1991–2024 monthly: n=388 (20 dropped, DJF kept=83/102), OLS −0.0000045 ≈ **−0.000**, Sen −0.00002, OLS p=0.994, HAC lag-3 p=0.995, HR p=0.973, YW p=0.919, n_eff≈207.6, r=0.30. Call: not significant.
- 1991–2024 Apr–Oct monthly: n=238, OLS **−0.00266** (printed −0.003), Sen −0.00281, OLS p=0.000619, HAC lag-3 p=0.00293, HR p=0.00508, TFPW p=0.000226. Matches their line exactly.
- 1991–2024 annual (their n_months≥6 rule): n=34, OLS −0.00007 ≈ **−0.000**, HAC lag-1 p=0.924, HR p=0.895. n.s.
- Full record monthly: n=508, OLS **−0.00145** (printed −0.001), HAC lag-3 p=0.0249, HR p=0.070. Method-dependent.
- Full Apr–Oct monthly: n=320, OLS **−0.00314** (printed −0.003), HAC lag-3 p=3.45×10⁻⁵, HR p=0.000225.

CSV vs an independent intersection-area recompute from the monthly NetCDF: max |Δ| on `sm_m3m3`, `weight_coverage`, and `mean_n_valid_days` is 5×10⁻⁷; cell counts match exactly. Weights are spherical rectangle intersection with bbox 22.1–40.2°E, 44.4–52.4°N (Δlon × Δsin(lat), i.e. overlap × cos(lat)) — the same bbox as the other extra sources. 33×73 = 2409 cells, all with positive overlap; 2040 are ever-valid (land), 369 never-valid (water / fill). Late-period MJJAS `weight_coverage` is exactly the land-weight fraction **0.8442**, so a 0.5 threshold is ~59% of land; in 1991–2024 Apr–Oct, coverage is effectively full land. Neighbouring land in the bbox is included; Crimea is inside the southern cells (centres to 44.375°N); no Ukraine-polygon / Crimea mask is applied (same convention as the other bbox cuts). vs an unweighted land mean the monthly difference is small (max 0.0014, mean 0.00048 m³ m⁻³).

Units are volumetric m³ m⁻³ (valid 0–1); daily fill −9999 is excluded. The 1991 window and mid-month decimal year (`year + (month−0.5)/12`) match `cci_sm_trends.py`. `trend_methods.py` is imported, not copied. They did not use the word “drying” in the preliminary notes.

## Nits

- Annual rule `n_months >= 6` is looser than the team’s 12/12 or deseasonalized ≥10: in 1991–2024, 12 of 34 years have <12 kept months and 2 have <10; tightening to ≥10 leaves the annual result n.s. (OLS +0.00015). Prefer the Apr–Oct 7/7 annual mean over a mixed-season annual with missing winters.
- 46 cell-months have `sm == 1.0` (physically implausible for volumetric SM; mostly DJF 2003–2008) and 127 have `sm == 0`; too few to move the bbox mean.
- Daily fetch pulled only `sm`, not `flag` / `sm_uncertainty`; snow/frozen masking is whatever the product already set to fill. That is acceptable if stated.
- The calendar-month coverage table should be split by era (item 4); all-era DJF means hide the SMMR vs SSM/I jump (1986 DJF ~3.5 days vs 1989–90 ~18 days).
- Max `weight_coverage` is 0.844, not 1, because Black Sea / Azov cells stay in the denominator; say so.
- Compulsory COMBINED citation is Preimesberger et al. (2021), TGRS 59(4), plus the usual Dorigo/Gruber CCI SM papers.

## What I did not re-fetch

I did not re-download CEDA daily files. Completeness, units, and weights were taken from the kept monthly NetCDF/CSV and the fetch/assemble scripts. Break-adjustment and GLDAS/ERA5 dependence are from the official v08.1/v09.1 PVIR and PUG and the v09.2 project page, not from a file attribute on the daily granules (those attributes were not retained in the monthly aggregate).

## Paths

- Notes: `team-context/team/reviews/cci_sm_review.md`
- Recompute script / results: `team-context/team/reviews/cci_sm_recompute.py`, `team-context/team/reviews/cci_sm_recompute_results.json`, `team-context/team/reviews/cci_sm_recomp_monthly.csv`, `team-context/team/reviews/cci_sm_grid.npz`
