# Findings: GRACE / GRACE-FO terrestrial water storage

> **SUPERSEDED (2026-11-14)**: pre-pipeline findings using HAC + Hamed–Rao wording. The official test is repo MK Yue–Wang with the OLS n_eff cross-check and the conservative verdict (.claude/skills/trend-stats/SKILL.md:26-28). Current numbers: data/pipeline/outputs/v1.4/. Never send numbers from this file to the UI or slides (MC-4).

Date: 14 November 2026 (Europe/Kiev)  
Product: JPL RL06.3Mv04 CRI mascons (`TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4`, DOI [10.5067/TEMSC-3JC634](https://doi.org/10.5067/TEMSC-3JC634)), unscaled `lwe_thickness` (cm equivalent water thickness), anomalies relative to 2004–2009.  
Methods: `$UKRAINE_SAMPLES/_staging/trend_methods.py` (OLS, AR(1), Newey–West HAC, time-aware Theil–Sen, Mann–Kendall, Hamed–Rao lag=3, TFPW). Yue–Wang is computed in the CSV but is not used for wording.  
Domain: **Ukraine bbox land mean (15 JPL mascons, ~3° native resolution).** The box is 22.1–40.2°E, 44.4–52.4°N. Land area in the CRI mask is **1,074,881 km²**, about **1.8× Ukraine’s land area** (~603,550 km²), and includes neighbouring land (Belarus, Poland, Romania, Moldova, Slovakia, Hungary, Russia). The Black Sea is masked. This is a regional signal with leakage between neighbouring 3° caps. It is **not** an oblast-, district- or field-scale Ukraine series, and it must not be mapped to individual oblasts.

These results replace `preliminary_trend.txt` (classical OLS / Sen / MK only), which is superseded.

## Headline

The primary published number is a **monthly deseasonalized** fit on the **unscaled** series. The month climatology is taken from the 14 complete years (2004–2010 and 2019–2025). Years 2002, 2017, 2018 and 2026 are dropped.

**-11.2 cm/decade** (precisely **-11.222**), n=235, residual lag-1 r=+0.87 (precisely +0.867), HAC lag-3 p=8.24e-37, time-aware Theil–Sen -11.239 cm/decade, Hamed–Rao (lag=3) p=9.88e-12. Call: **robust at 0.05 (HAC lag-3 and Hamed–Rao)**.

The strong monthly residual autocorrelation (r≈+0.87) is why HAC lag-3 belongs in the headline, not the classical OLS p-value. Hamed–Rao assumes equally spaced observations; this series skips the July 2017–May 2018 inter-mission gap, so **`hr_unequal_spacing=True`** and that caveat is part of the result. Including the sparse 2017–2018 months that exist (n=245) gives -11.171 cm/decade, still robust. Using all 261 months (including 2002 and 2026) gives -10.946 cm/decade, still robust. The scaled series, which JPL warns may not be suitable for trends, agrees to 0.01 cm/decade (-11.222).

## Annual results

Calendar-year means of available months are kept as a check, not as the headline. Mid-record years with 9–11 months (2003, 2011–2016) can be biased by the large seasonal TWS cycle (complete-year climatology: January -7.78 cm, October -16.77 cm, the driest month). Sampling-bias corrections for those years are in `grace_sampling_bias.csv`. Do not put raw 2017 or 2018 annual means back into a trend set (2017 would be biased wet by 4.6 cm).

| Series | n | OLS (cm/decade) | Theil–Sen | Residual r | Call |
|---|---:|---:|---:|---:|---|
| Annual, 21 years including 9–11-month years (2003–2016, 2019–2025) | 21 | -11.131 | -10.952 | +0.118 | robust at 0.05 (HAC and Hamed–Rao) |
| Same 21 years, seasonally bias-corrected | 21 | -11.197 | -11.188 | +0.133 | robust at 0.05 (HAC and Hamed–Rao) |
| Complete years only (2004–2010 and 2019–2025) | 14 | -11.966 | -11.705 | +0.087 | robust at 0.05 (HAC and Hamed–Rao) |

All three annual constructions are robust at 0.05 (HAC and Hamed–Rao) and also carry `hr_unequal_spacing=True` because of the 2016→2019 gap. The bias correction changes the 21-year slope only from -11.131 to -11.197 (about −11.20). Complete years only are slightly steeper (-11.966, about −11.97). The classical annual OLS SE is 1.02 cm/decade; that is not the full uncertainty (see spatial spread below).

## Approved-method rows

Full machine-readable rows, including AR(1), both HAC lags, TFPW and Yue–Wang, are in `grace_trend_rows.csv`. Yue–Wang is not used for wording.

| Series | n | OLS | Sen | Resid. r | HAC p | HR p | Unequal spacing | Call |
|---|---:|---:|---:|---:|---:|---:|:---:|---|
| Monthly deseas. (headline) | 235 | -11.222 | -11.239 | +0.867 | 8.24e-37 | 9.88e-12 | yes | robust at 0.05 (HAC lag-3 and Hamed–Rao) |
| Annual n=21 raw | 21 | -11.131 | -10.952 | +0.118 | 4.64e-08 | 6.28e-07 | yes | robust at 0.05 (HAC and Hamed–Rao) |
| Annual n=21 bias-corrected | 21 | -11.197 | -11.188 | +0.133 | 3.89e-08 | 6.28e-07 | yes | robust at 0.05 (HAC and Hamed–Rao) |
| Annual complete n=14 | 14 | -11.966 | -11.705 | +0.087 | 1.99e-07 | 0.000459 | yes | robust at 0.05 (HAC and Hamed–Rao) |
| GRACE-only 2003–2016 | 14 | -10.234 | -10.938 | +0.166 | 0.000899 | 1.52e-08 | no | robust at 0.05 (HAC and Hamed–Rao) |
| Drop 2025 (n=20) | 20 | -10.579 | -10.554 | +0.262 | 5.01e-07 | 2.55e-06 | yes | robust at 0.05 (HAC and Hamed–Rao) |
| Early 2003–2010 | 8 | -6.160 | -5.144 | +0.357 | 0.268 | 0.386 | no | not significant at 0.05 on HAC and Hamed–Rao |
| FO-only 2019–2025 | — | — | — | — | — | — | — | insufficient data / below min_n=8 |
| Monthly deseas. 2003–2025 incl. sparse 2017–18 | 245 | -11.171 | -11.201 | +0.867 | 1.48e-37 | 1.38e-12 | yes | robust at 0.05 (HAC lag-3 and Hamed–Rao) |
| GLDAS-2.1 Root+SWE (bbox, same 21 y) | 21 | -2.255 | -2.269 | +0.115 | 0.00624 | 0.0034 | yes | robust at 0.05 (HAC and Hamed–Rao) |
| CSR RL06.3 monthly deseas. | 235 | -9.810 | -9.756 | +0.829 | 4.90e-29 | 6.10e-11 | yes | robust at 0.05 (HAC lag-3 and Hamed–Rao) |
| CSR RL06.3 annual n=21 | 21 | -9.714 | -9.327 | +0.064 | 3.84e-07 | 9.04e-06 | yes | robust at 0.05 (HAC and Hamed–Rao) |

HAC p is lag-3 for monthly series and lag-1 for annual series, following the approved rule. Every series that skips 2017–2018 is flagged `hr_unequal_spacing`.

## Spatial uncertainty (15 mascons)

Per-mascon OLS trends on the unscaled monthly series (all 261 months) **all decline**. They are not the same rate:

- Range **−4.79 to −15.75** cm/decade (all negative); median **-9.37**; SD **3.17** cm/decade
- Steepest: mascons 548 and 549 (centroids 47.99°N, 29.25°E and 33.75°E; central / Dnieper–Dniester) at -15.75 and -14.87
- Weakest: mascon 629 (45.71°N, 33.36°E; Crimea / north-west Black Sea coast) at -4.79
- North-west mascon 471 (51°N, 23°E) is milder, -7.05

The inter-mascon slope scatter (SD 3.17 cm/decade) is larger than the classical annual OLS SE (1.02 cm/decade) and larger than formal monthly mascon uncertainties in the box (~0.5–2 cm). Those formal errors and the classical SE **understate** spatial uncertainty and leakage. Report the spread alongside HAC errors; do not present 1.02 cm/decade as the full uncertainty. Per-mascon rows are in `grace_mascon_trends.csv`.

## Mission-offset check

A harmonic model (linear trend + annual + semiannual + GRACE-FO step from 2018-06), HAC lag-3, on the unscaled monthly series:

| Window | n | Slope (cm/decade) | Step (cm) | Step SE | Step p |
|---|---:|---:|---:|---:|---:|
| All months | 261 | -9.916 | -1.82 | 1.49 | 0.223 |
| 2003–2025 | 245 | -10.513 | -1.17 | 1.53 | 0.445 |
| Drop 2002 / 2017 / 2018 / 2026 | 235 | -10.380 | -1.45 | 1.72 | 0.401 |

The estimated GRACE-FO step is about **−1.2 to −1.8 cm** and is **not significant** in any of these windows. After a linear + seasonal fit without a step, on 2003–2025, the mean residual of the last 12 GRACE months is +1.07 cm and of the first 12 GRACE-FO months is +1.29 cm. There is no clear mission jump that explains the decline.

The **GRACE-only** annual window 2003–2016 is already **-10.234 cm/decade** (Theil–Sen -10.938), HAC lag-1 p=0.000899, Hamed–Rao lag-3 p=1.52e-08. Call: **robust at 0.05 (HAC and Hamed–Rao)**. That window has no inter-mission hole (`hr_unequal_spacing=False`).

**The decline is not a mission artefact.** A non-significant ~1–2 cm step is not a reason to discard the trend, and it is not ignored.

## Robustness

Period means of the unscaled annual series (cm): 2003–2010 **-0.57**; 2011–2016 **-8.37**; 2019–2024 **-17.25**; 2019–2025 **-18.40**. The 2004–2009 baseline years average 0.000 cm, as required. 2025 is the driest year (-25.31 cm).

Sensitivity on the n=21 annual set, still robust unless noted:

- Drop 2025: **-10.579** cm/decade (robust at 0.05 (HAC and Hamed–Rao))
- Drop 2003: -11.939
- Drop 2003 and 2025: -11.420
- GRACE 2003–2016 only: -10.234 (robust, above)
- Early 2003–2010: -6.160, **not significant** (n=8, HAC lag-1 p=0.268)
- FO-only 2019–2025: n=7, **below the approved `min_n=8`**, so `trend_methods.py` does not return a robust call. Classical OLS only is -6.41 cm/decade (p=0.41). 2019–2024 is +3.56 (p=0.57). These short FO windows are dominated by interannual swings (dry 2020 and 2025, partial recovery 2023) and should not be reported as a separate climate trend.

Headline the long window (the monthly deseasonalized fit). Use period means, not a 6–7 year FO slope, to describe the 2020s. Keep the 2025 dry year in the series; the drop-2025 check remains robust at about −10.58 cm/decade.

## Interpretation (GLDAS and literature)

**GLDAS Noah 2.1, same 21 years as the GRACE annual set**, already in `$UKRAINE_SAMPLES/gldas/`. Root-zone soil moisture plus snow water equivalent were converted from kg m⁻² to cm (÷10). Using the bbox-cell columns (the series that matches the reviewer’s figure exactly): RootMoist **-1.837** cm/decade (robust); SWE **-0.418** (robust); Root+SWE **-2.255** cm/decade (robust). Land-cell-only Root+SWE is very close, -2.269. So about **2.3 cm/decade** of the GRACE **−11.2** is in the modelled root zone plus snow; most of the TWS decline is not.

That residual is **not** a groundwater measurement. GLDAS Noah has no groundwater store; deeper soil (100–200 cm) and canopy were not in this extract; and GLDAS-2.1 forcing is known to be inhomogeneous. Groundwater or deeper soil is a residual *candidate* only. Do not write that Ukraine groundwater is falling at ~9 cm/decade from this split.

**Literature, verified.** Lenczuk and Debowska (2026), *Advances in Geodesy and Geoinformation* 75(2): e77, use the recent JPL mascon solution for April 2002–February 2026 on 24 European basins. The paper states a Dniester trend of **−1.35 cm/year (−13.5 cm/decade)**, Dnieper **−0.90 cm/year (−9.0 cm/decade)**, and Danube **−0.81 cm/year (−8.1 cm/decade)**. The Ukraine bbox covers much of the Dnieper and Dniester basins; our regional rate of about −11.2 cm/decade sits between those two basin figures and is plausible. We did not recompute their basin averages. Article: https://wydawnictwo.pan.pl/index.php/agg/article/view/8062 (published 3 November 2026).

## Independent check: CSR RL06.3 mascons

An open CSR RL06.3 “all-corrections” granule (Apr 2002–Sep 2026, 0.25° grid, no Earthdata login; [CSR portal](https://www2.csr.utexas.edu/grace/RL0603_mascons.html); file `CSR_GRACE_GRACE-FO_RL0603_Mascons_all-corrections.nc`, 109 MB, downloaded 14 November 2026) was land-masked with CSR’s `LO_val` mask and averaged over the same bbox. GAD, GIA, C20/C30 and degree-1 are already applied in that file. The CSR land area in the box is 1,139,070 km² (2233 cells) — a slightly different coastline than JPL CRI. Monthly series: `csr_ukraine_tws_monthly.csv`.

On the same headline construction (complete-year month climatology, drop 2002/2017/2018/2026, n=235): CSR monthly deseasonalized OLS **-9.81 cm/decade** (Theil–Sen -9.76, residual r=+0.83, HAC lag-3 p=4.90e-29, Hamed–Rao p=6.10e-11). Call: **robust at 0.05 (HAC lag-3 and Hamed–Rao)**, also `hr_unequal_spacing=True`. CSR annual n=21 is -9.71 cm/decade, also robust.

CSR confirms a decline of the same sign and the same order of magnitude. It is about 1.4 cm/decade less steep than JPL (−9.81 vs −11.22 on the monthly deseasonalized fit). That centre-to-centre difference is expected (native mascon design, land mask, grid, and the GAD already in the CSR all-corrections file) and does not remove the regional drying signal.

## Where these numbers differ from Critique’s review

Almost all headline, annual, spatial, GLDAS bbox, period-mean and step results agree with `team-context/team/reviews/grace_review.md` to the precision printed there. The differences are:

1. **No-step residuals.** On a 2003–2025 harmonic fit, last-12 GRACE and first-12 FO mean residuals are **+1.07 cm and +1.29 cm**, matching Critique. On all 261 months they are +1.18 and +1.33 cm. The published check uses the 2003–2025 window.
2. **GRACE-only Hamed–Rao.** Approved-method Hamed–Rao (lag=3) on the raw 2003–2016 annual series is **p=1.52×10⁻⁸**, not 0.00069. Critique’s 0.00069 equals the classical Mann–Kendall p-value (and Hamed–Rao with lag=1) on the same series. The slope (−10.234) and HAC lag-1 p (0.00090) match. Both calls remain robust.
3. **Harmonic step slopes** differ from Critique by about 0.002 cm/decade (time encoding: we used the solution mid-date as a decimal year). Steps and p-values agree at the reported precision (−1.82, −1.17, −1.45 cm; p=0.223, 0.445, 0.401).
4. **Monthly residual r** is +0.867; Critique printed +0.868.
5. **GLDAS land-only** Root+SWE is −2.269 cm/decade; the bbox-cell series that reproduces Critique exactly is −2.255. Both are reported; the narrative uses −2.26.
6. **CSR** was not in the review (they could not verify a second centre). It is added here.

## Files

| File | What it is |
|---|---|
| `findings.md` | This document. |
| `grace_trend_rows.csv` | Approved-method rows for the table above. |
| `grace_sampling_bias.csv` | Annual means and seasonal sampling-bias corrections. |
| `grace_mascon_trends.csv` | Per-mascon OLS slopes. |
| `csr_ukraine_tws_monthly.csv` | CSR RL06.3 land-mean monthly series for the same bbox. |
| `findings_results.json` | Machine-readable recompute. |
| `preliminary_trend.txt` | **Superseded.** Classical-only check, retained for the record. |

Reproduce with:

    python $UKRAINE_SAMPLES/_staging/grace_findings.py

The CSR file is read from `/tmp/csr_work/` if present; JPL and GLDAS inputs are the files already in `$UKRAINE_SAMPLES/`.
