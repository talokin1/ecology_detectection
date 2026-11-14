# CCI SM COMBINED v09.2 Ukraine-bbox findings (revised after Critique)

> **SUPERSEDED (2026-11-14).** Pre-pipeline analysis with the HAC/Hamed–Rao rule. The official test is repo MK Yue–Wang (ADR-002/ADR-003) with the OLS n_eff cross-check. Never send numbers from this file to the UI or slides (MC-4). **Restated 2026-11-14 (A2-05, conservative-verdict rule):** warm-season (Apr–Oct 7/7) soil moisture 1991–2024 shows **moderate drying**: Sen slope −0.0025 m³ m⁻³/decade (95% CI −0.0051 to −0.0004), repo MK Yue–Wang p = 0.01505, OLS n_eff cross-check p = 0.01695 (the two methods agree). Caveat: the result depends on the start year: from 2002 or 2003 it is not significant, and from 2007 (ASCAT) the sign flips (n.s.). Quote it as "moderate drying since 1991, sensitive to start year", never as a detection from 2002 on.

Date: 14 November 2026, Europe/Kiev  
Source: `$UKRAINE_SAMPLES/extra/cci_sm/cci_sm_combined_v09_2_ukraine_bbox_monthly.csv` and `$UKRAINE_SAMPLES/extra/cci_sm/cci_sm_combined_v09_2_ukraine_bbox_monthly.nc` (1978-11–2024-12, 554 months).  
Methods: `$UKRAINE_SAMPLES/_staging/trend_methods.py`.  
These notes **supersede** `cci_sm_trends_preliminary.txt`.

**Headline (mixed-season, 1991–2024):** no significant change (OLS ≈ 0).  
**Headline (warm season):** *(superseded, see banner: moderate drying 1991–2024, start-year sensitive)* there is **no robust drying signal**. The 1991–2024 Apr–Oct 7/7 seasonal-mean slope is negative and formally significant under annual HAC + Hamed–Rao, but it is start-point dependent (n.s. from 2002; sign flips from 2007) and residual 2002/2007 mean shifts remain. Do not headline “drying.” Do not headline the full 1978–2024 record.

## Product status (PUG / PVIR / FAQ)

COMBINED **v09.2 is break-adjusted.** The earlier claim that only the separate `break_adjusted_COMBINED` tree (through v07.1) was adjusted is inverted: from **v08.1** the adjustment is in the **main COMBINED product**.

What the official documents actually say:

- **PUG v09.1** (30 Sep 2024, §3.5, major processing step 6): “Break-adjusting all products using the method of Preimesberger et al. (2021).” Step 2 rescales all L2 inputs “into a common model-based climatology (for the COMBINED product)” so that values are “brought into the data space of the reference land surface model in COMBINED” and reported in m³ m⁻³.
- **PVIR v08.1** executive summary: “The break-adjusting routine, previously performed only on a separately distributed product, is now included in the main COMBINED product.” §5.1.7: “A break-adjustment in the COMBINED product is performed in v08.1 using the methodology set out in [Preimesberger et al., 2021].” And: “The reference data set for break detection and correction is ERA5.” Official sensor-transition dates tested: 1987-07-09, 1991-08-05, 1998-01-01, 2002-06-19, 2007-01-01, 2010-01-15, 2012-07-01, 2015-03-31.
- **PVIR v09.1** executive summary: “The break-adjusting routine is now included in all distributed products.” Datasets overview: “a break-adjustment in the COMBINED product is performed as of v08.1 using the methodology set out in Preimesberger et al. [2021].”
- **Project data page** marks Preimesberger et al. (2021) as **compulsory** when citing COMBINED.
- **Official FAQ** (“Is the product the absolute truth?”): “The COMBINED data set is rescaled to GLDAS v2.1 prior to merging. … this step imposes the absolute values and dynamic range (min-max) of the GLDAS-Noah product on the combined product. As a consequence, the combined product CANNOT be considered an independent data set representing absolute true soil moisture.” The same FAQ describes COMBINED as “including a temporal break correction.”

Cite: Preimesberger, W., Scanlon, T., Su, C.-H., Gruber, A. and Dorigo, W. (2021). Homogenization of Structural Breaks in the Global ESA CCI Soil Moisture Multisatellite Climate Data Record. IEEE TGRS 59(4), 2845–2862. doi:10.1109/TGRS.2020.3012896. Also the usual Dorigo / Gruber CCI SM papers.

v09.2 is a temporal extension of v09.1 through 2024-12 (plus other updates). Break adjustment remains in the main COMBINED files we used. Residual breaks can still remain, and homogenization is **ERA5-referenced**, so COMBINED is not independent of ERA5 on that step.

## Independence (relabel)

COMBINED is **CDF-matched to GLDAS-Noah v2.1** (absolute level and dynamic range) and **break-adjusted against ERA5**. It is a satellite-based **anomaly/trend cross-check only**, not an independent data set in level or range, and not independent of ERA5 in the homogenization step. The surface layer is ~0–5 cm, not a root-zone or GLDAS layer-2 equivalent. Anomalies and trends still come from the satellite retrievals, with the residual-break caveat below.

## Residual mean shifts (this bbox)

Even after official break adjustment, residual steps are still visible here (from the Critique’s 36-month Welch checks on the coverage-filtered, deseasonalized series; not re-downloaded):

| Transition | Δ mean (post−pre) | Cohen’s d | Welch p |
|---|---|---|---|
| 1987-07 SMMR→SSM/I | +0.0098 | +1.00 | 1.2×10⁻⁴ |
| 1998-01 TMI | −0.0064 | −0.59 | 0.019 |
| **2002-06 AMSR-E** | **+0.0090** | **+0.76** | **0.0023** |
| **2007-01 ASCAT** | **−0.0078** | **−0.68** | **0.0053** |
| 2010-01 SMOS, 2012-07 AMSR2, 2015-04 SMAP | ≤0.003 | ≤0.26 | ≥0.30 |

The 1987 SMMR break is why the **full 1978–2024 record must not be headlined**. **1991–2024 is the primary window** (SSM/I is then established; official CCI trend maps often start 1991/1992) but it is still **multi-sensor** and can carry residual 2002/2007 steps.

## Coverage by era

Filter used for mixed-season monthly series: `weight_coverage >= 0.5` and `mean_n_valid_days >= 5`. That threshold is **too loose for the SMMR era** (months often have only ~5–8 valid days, so the cut lets almost the lower quartile through). It is adequate for **1991–2024 Apr–Oct**, where every month is well sampled. Max `weight_coverage` is **0.8442**, not 1, because Black Sea / Azov cells stay in the denominator.

- **SMMR 1978-11–1987-06**: 104 months; unfiltered n=104  mean days=7.0 (p25=5.1)  mean coverage=0.713; filter pass 75.96%. Apr–Oct: n=59  mean days=8.5 (p25=7.6)  mean coverage=0.798, pass 96.61%. DJF: n=27  mean days=4.4 (p25=2.8)  mean coverage=0.560, pass 40.74%.
- **SSM/I 1987-07–2002-05**: 179 months; unfiltered n=179  mean days=18.8 (p25=14.6)  mean coverage=0.800; filter pass 97.21%. Apr–Oct: n=104  mean days=22.6 (p25=20.9)  mean coverage=0.819, pass 100.00%. DJF: n=45  mean days=11.1 (p25=7.4)  mean coverage=0.753, pass 91.11%.
- **AMSR-E / ASCAT / later 2002-06–2024-12**: 271 months; unfiltered n=271  mean days=21.1 (p25=13.6)  mean coverage=0.798; filter pass 94.10%. Apr–Oct: n=159  mean days=27.3 (p25=25.5)  mean coverage=0.840, pass 100.00%. DJF: n=67  mean days=9.8 (p25=6.2)  mean coverage=0.692, pass 76.12%.

In 1991–2024 the all-month filter drops 20 months (19 in DJF and March 1996). Those winters should not be mixed into a monthly headline. Prefer the Apr–Oct 7/7 annual mean over a mixed-season annual with missing winters.

## Mask of sm == 1.0

The monthly grid had **46 cell-months with `sm == 1.0`** (physically implausible for volumetric soil moisture; porosity is typically ~0.3–0.6). All are DJF, mostly 2003–2008. They were **masked** and bbox means recomputed (largest single-month change was about −0.0045 m³ m⁻³ in 2006-01). **127 cell-months with `sm == 0`** were left unchanged (zero can be a dry retrieval). Trends below use the masked CSV.

Daily fetch pulled **only `sm`**, not `flag` or `sm_uncertainty`; snow/frozen masking is whatever the product already set to fill. There is **no Ukraine country mask** (same convention as the other bbox cut-outs); Crimea is inside the southern cells.

## Headline rows (recomputed)

Units: m³ m⁻³ per decade. Annual tests use HAC lag-1 + Hamed–Rao; monthly tests use HAC lag-3 + Hamed–Rao.

### Mixed-season, 1991–2024 (primary all-month record)

Coverage-filtered, calendar-month deseasonalized monthly series: **n=388, OLS +0.00000 / Sen -0.00001 m³ m⁻³/decade, HAC lag-1 p=0.995, HAC lag-3 p=0.995, HR p=0.984, TFPW p=0.642, residual r=0.30. Call: not significant at 0.05 on HAC and Hamed–Rao.**  
This can stand as the headline for the mixed-season record: essentially zero, not significant.

### Warm season: equally spaced Apr–Oct seasonal mean per year (primary Apr–Oct test)

One mean of April–October per year, requiring **7/7 months**. Equally spaced (`hr_unequal_spacing=False`). Do **not** use the gapped monthly Apr–Oct series as the primary call.

- **1991-2024 (primary window)** (n=34): n=34, OLS -0.00266 / Sen -0.00251 m³ m⁻³/decade, HAC lag-1 p=0.00807, HAC lag-3 p=0.00413, HR p=0.015, TFPW p=0.0567, residual r=-0.10. Call: robust at 0.05 (HAC and Hamed–Rao).
- **1992-2024 (after official 1991-08 break)** (n=33): n=33, OLS -0.00223 / Sen -0.00203 m³ m⁻³/decade, HAC lag-1 p=0.0249, HAC lag-3 p=0.00996, HR p=0.0424, TFPW p=0.0578, residual r=-0.10. Call: robust at 0.05 (HAC and Hamed–Rao).
- **2002-2024** (n=23; 2002 Apr–Oct straddles the official 2002-06-19 AMSR-E start): n=23, OLS -0.00213 / Sen -0.00213 m³ m⁻³/decade, HAC lag-1 p=0.289, HAC lag-3 p=0.266, HR p=0.205, TFPW p=0.259, residual r=-0.18. Call: not significant at 0.05 on HAC and Hamed–Rao.
- **2003-2024 (first complete Apr–Oct after the 2002-06 AMSR-E start)** (n=22): n=22, OLS -0.00201 / Sen -0.00213 m³ m⁻³/decade, HAC lag-1 p=0.383, HAC lag-3 p=0.359, HR p=0.236, TFPW p=0.291, residual r=-0.18. Call: not significant at 0.05 on HAC and Hamed–Rao.
- **2007-2024 (from official ASCAT start)** (n=18): n=18, OLS +0.00251 / Sen +0.00084 m³ m⁻³/decade, HAC lag-1 p=0.332, HAC lag-3 p=0.259, HR p=0.762, TFPW p=0.592, residual r=-0.45. Call: not significant at 0.05 on HAC and Hamed–Rao.

**Start-point dependence:** the 1991–2024 (and 1992–2024) Apr–Oct 7/7 slope is negative and formally “robust” under annual HAC + HR, but it is **not stable** to a later start: from 2002–2024 (and 2003–2024) the slope is not significant, and from 2007 (ASCAT) the sign flips positive (n.s.). Residual r on the 1991–2024 seasonal series is slightly negative, so Hamed–Rao is mildly anti-conservative; TFPW is 0.057. Formal “robust at 0.05 (HAC and Hamed–Rao)” on the 1991–2024 row is therefore not a drying headline. Wording (pre-pipeline, superseded): **no robust drying signal.** Current wording: moderate drying since 1991, sensitive to start year (see banner).

### Annual means, 1991–2024, tightened to 12/12 months

Only years with all 12 months passing the coverage filter (n=22 of 34): **n=22, OLS +0.00041 / Sen +0.00016 m³ m⁻³/decade, HAC lag-1 p=0.625, HAC lag-3 p=0.612, HR p=0.866, TFPW p=0.608, residual r=0.11. Call: not significant at 0.05 on HAC and Hamed–Rao.**  
This stays not significant (as with the looser n_months≥6 rule). The 22 years are not equally spaced (missing 1996, 1997, 2003, 2006, 2010–2013, 2016–2019 because at least one winter month failed the coverage filter), so the HR equal-spacing assumption does not hold here; that does not change the n.s. call. Prefer the equally spaced Apr–Oct 7/7 annual mean over a mixed-season annual that drops winters.

## What not to do

- Do not headline “drying.”
- Do not headline the full 1978–2024 record (SMMR break; `n_valid_days >= 5` too loose).
- Do not treat COMBINED as independent of GLDAS-Noah in level/range, or of ERA5 in break adjustment.
- Yue–Wang p-values on the gapped monthly Apr–Oct series should stay out of the wording.
