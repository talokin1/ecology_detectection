# GRACE / GRACE-FO JPL mascon review (Ukraine bbox)

Date: 14 November 2026, Europe/Kiev  
Reviewer: Critique  
Source: `$UKRAINE_SAMPLES/grace/` (README, monthly/annual CSVs, preliminary_trend.txt, bbox NetCDF) and `$UKRAINE_SAMPLES/_staging/download_grace_mascon.py`  
Methods: `$UKRAINE_SAMPLES/_staging/trend_methods.py`  
Scratch only under `team-context/team/reviews/`. Their files were not modified.

Official product: JPL RL06.3Mv04 CRI (`TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4`, DOI 10.5067/TEMSC-3JC634). User guide: https://grace.jpl.nasa.gov/data/get-data/jpl_global_mascons/. GES/JPL README attributes on the granule (time-mean 2004.000–2009.999; units cm equivalent water thickness).

## Verdict: approved with fixes

The pull is careful and reproducible. Units, CRI land mask, spherical area weights, 2004–2009 baseline, month assignment (including windows that straddle two calendar months), and the official gap list all check out. The full granule MD5 `1567b9401ec2a704aab16598fcce5e70` was re-verified on the raw file still in `/tmp/grace_work`. Their preliminary classical numbers match an independent recompute (unscaled annual OLS −11.131 cm/decade, Sen −10.952, 95% CI was reported as −13.764 to −8.807, classical MK p=6.277e-07, n=21 years 2003–2025 excluding 2002, 2017, 2018 and 2026).

Under the approved method the −11 cm/decade decline is still **robust**, on both the annual series and a deseasonalized monthly fit. Scaled vs unscaled trends agree to 0.01 cm/decade, consistent with JPL guidance to prefer the unscaled series for trends. The rate is plausible against published JPL-mascon basin trends for the Dnieper and Dniester.

It is not a full approval until the series is scored with HAC / Hamed–Rao (they already flagged this as missing), incomplete mid-record years are handled more strictly or replaced by the monthly deseasonalized fit, the 2017–2018 hole is flagged as unequal spacing, and findings wording treats this as a ~3° regional bbox signal (15 mascons), not an oblast-scale “Ukraine” series. Formal monthly uncertainties and the classical OLS SE (1.02 cm/decade) understate spatial uncertainty.

## Ranked issues

### 1. Annual means still include incomplete mid-record years (should fix before a headline number)

**What they got right.** Calendar-year means of available months are written for every year, with `n_months`, `n_expected`, and a `complete` flag. The preliminary trend drops 2002 (starts April, 7 of 9 expected months), 2017 and 2018 (5 months each, inter-mission / early FO), and incomplete 2026 (Jan–Sep). A minimum of 9 months is required. That is the correct treatment of the first/last years and the big gap.

**What remains.** Years with 9–11 months in mid-record were kept: 2003 (11, missing June), 2011 (10), 2012 (10), 2013–2016 (9 each). Partial years with a large seasonal TWS cycle can bias a calendar-year mean. Climatology from the 14 complete years (unscaled, cm): January −7.78, September −16.50, October −16.77 (driest), July–August also dry; late autumn/winter less dry. Seasonal sampling bias (mean of the climatology on available months minus the 12-month climatology):

| Year | n | missing | raw annual | sampling bias | bias-corrected |
|---|---|---|---|---|---|
| 2003 | 11 | 6 | −3.104 | −0.229 | −2.876 |
| 2011 | 10 | 1, 6 | −4.423 | −0.404 | −4.019 |
| 2012 | 10 | 5, 10 | −9.245 | +0.201 | −9.446 |
| 2013 | 9 | 3, 8, 9 | −5.561 | +0.522 | −6.083 |
| 2014 | 9 | 2, 7, 12 | −9.341 | −0.195 | −9.146 |
| 2015 | 9 | 6, 10, 11 | −11.386 | +1.187 | −12.573 |
| 2016 | 9 | 4, 9, 10 | −10.262 | +0.890 | −11.152 |
| 2017 (dropped) | 5 | 2, 7–12 | −6.682 | **+4.603** | −11.285 |
| 2018 (dropped) | 5 | 1–5, 8–9 | −14.597 | **−2.781** | −11.817 |
| 2002 (dropped) | 7 | 1–3, 6–7 | −3.111 | −2.116 | −0.995 |
| 2026 (dropped) | 9 | 10–12 | −21.685 | +1.705 | −23.390 |

Dropping 2017/2018/2002/2026 was necessary (2017 would have been biased wet by 4.6 cm). Among the years they kept, 2015–2016 are the largest biases (~1 cm). Seasonally correcting the n=21 set changes the OLS slope only from −11.131 to −11.197 cm/decade. Complete years only (n=14: 2004–2010 and 2019–2025) gives −11.966 (Sen −11.705), still robust. A monthly deseasonalized fit (month climatology from complete years, unscaled, drop 2002/2017/2018/2026, n=235) gives OLS −11.222, Sen −11.239.

**Fix.** Make the primary published number a monthly deseasonalized fit (or harmonic annual + semiannual + trend), not the n≥9 calendar means. If an annual series is kept, drop years with n<12 or apply the sampling-bias correction. Do not put 2017 or 2018 back in as raw annual means.

### 2. Approved methods not yet in `preliminary_trend.txt`; when applied, −11 cm/decade is still robust, but the 2017–2018 hole must be flagged

They correctly labelled the file as classical OLS / time-aware Sen / classical MK only, and asked for a HAC / Hamed–Rao re-run. Independently, unscaled annual n=21 (their year set):

- OLS −11.131 cm/decade, Sen −10.952 (matches their file)
- HAC lag-1 p=4.64e-08, HAC lag-3 p=5.91e-10
- Hamed–Rao (lag=3) p=6.28e-07, TFPW p=6.91e-07
- residual r=+0.118 (HR is not anti-conservative)
- `hr_unequal_spacing=True` because 2016→2019 is a 3-year step (median spacing 1 year)
- Call: **robust at 0.05 (HAC and Hamed–Rao)**

Scaled annual is −11.132 / Sen −10.947, also robust.

Deseasonalized monthly (approved rule: HAC lag-3 + HR lag=3), drop 2002/2017/2018/2026: OLS −11.222, Sen −11.239, HAC lag-3 p=8.3e-37, HR p=9.9e-12, residual r=+0.868, unequal spacing True, still **robust**. The strong monthly AR is why HAC lag-3 belongs in the headline, not classical OLS p=1.3e-09.

Including the sparse 2017–2018 months in the monthly deseasonalized series (2003–2025, n=245) gives −11.171, still robust. Using all 261 months including 2002 and 2026 gives −10.946, still robust.

**Fix.** Replace the preliminary block with the approved-method rows (annual and monthly deseasonalized). Flag `hr_unequal_spacing` on any series that skips 2017–2018. Do not use Yue–Wang for wording.

### 3. Resolution: 15 mascons, bbox ~1.8× Ukraine’s land area — not an oblast-scale “Ukraine” signal

**Processing is correctly described in the README** (3° native resolution, 15 unique land mascons, 528 of 576 half-degree cells, land area 1,074,881 km² vs full box 1,178,811 km²; Ukraine is about 0.60 million km²; no country polygon). Independently confirmed: 16×36 = 576 cell centres, `land_mask==1` on 528, 48 ocean cells, 15 mascon IDs.

Per-mascon OLS trends on the unscaled monthly series (all 261 months) all decline, but they are not the same:

- Range −4.79 to −15.75 cm/decade; median −9.37; standard deviation 3.17 cm/decade
- Steepest: mascons 548 and 549 (centroids 48.00°N, 29.25°E and 33.75°E; central / Dnieper–Dniester) at −15.75 and −14.87
- Weakest: mascon 629 (45.71°N, 33.36°E; Crimea / north-west Black Sea coast) at −4.79
- North-west mascons are milder (471 at 51°N, 23°E: −7.05)

This is one regional signal with leakage between neighbouring 3° caps. It must not be called a “Ukraine” trend at oblast or field scale, and the Black Sea is masked but neighbouring land (Belarus, Poland, Romania, Russia, Moldova, Slovakia, Hungary) remains in the mean.

**Fix.** Keep the README caveats in any findings headline. Say “Ukraine bbox land mean (15 JPL mascons, ~3°)” and quote the land area. Do not map this to oblasts.

### 4. Trend uncertainty should reflect 15 partly independent mascons and leakage, not only the classical SE

Product `uncertainty` is the 1-sigma of each 3° mascon, not of a 0.5° pixel — they document this and combine unique mascons as if independent: sqrt(Σ (w_i u_i)²). Inter-mascon error covariance is omitted. Monthly formal uncertainties in the box are typically ~0.5–2 cm, which is small next to an 11 cm/decade change, but that formal error is not the right uncertainty for a *trend* over a 15-mascon average. The classical annual OLS SE is 1.02 cm/decade. The inter-mascon slope scatter (SD 3.17 cm/decade) is larger, and leakage plus the 2017–2018 hole are extra.

**Fix.** Report a spatial uncertainty (inter-mascon spread or a mascon-block standard error) alongside HAC errors. Do not present 1.02 cm/decade as the full uncertainty.

### 5. No GRACE / GRACE-FO offset check in the preliminary file (the offset is not significant when tested)

The inter-mission gap is correctly identified as **July 2017–May 2018** (11 months); June 2017 is present (window 23 May–29 June 2017). Early FO also skips 2018-08 and 2018-09. Other holes match `months_missing` exactly (independently confirmed). Quality notes after August 2016 (GRACE-B accelerometer transplant) and 21 June 2018 (GRACE-D transplant) are in the README.

They did not fit a mission step. A harmonic model (linear trend + annual + semiannual + FO dummy from 2018-06), HAC lag-3:

- All months: slope −9.918 cm/decade (p=5.2e-16), step **−1.82 cm** (SE 1.49, p=0.223)
- 2003–2025: slope −10.515, step −1.17 cm (p=0.446)
- Drop 2002/2017/2018/2026: slope −10.382, step −1.45 cm (p=0.401)

After a linear+seasonal fit *without* a step, mean residual of the last 12 GRACE months is +1.07 cm and of the first 12 FO months is +1.29 cm. There is no clear mission jump that explains the decline. The GRACE-only annual window 2003–2016 is already −10.234 cm/decade (Sen −10.938), HAC p=0.00090, HR p=0.00069, **robust**.

**Fix.** Publish the offset check. Do not treat a non-significant ~1–2 cm step as a reason to discard the trend; do not ignore it either.

### 6. The decline is not an artefact of one start or end year, but the FO-only window is too short to stand alone

Period means (unscaled annual, cm): 2003–2010 −0.57; 2011–2016 −8.37; 2019–2024 −17.25; 2019–2025 −18.40; 2004–2009 baseline years 0.000 (as required). 2025 is the driest year (−25.31). Sensitivity on the n=21 set, all still robust unless noted:

- Drop 2025: −10.579
- Drop 2003: −11.939
- Drop 2003 and 2025: −11.420
- GRACE 2003–2016 only: −10.234 (robust)
- Early 2003–2010: −6.160, **not significant** (n=8, HAC p=0.27)
- FO 2019–2025: n=7, below the approved `min_n=8`; classical OLS only −6.41 (p=0.41). 2019–2024: +3.56 (p=0.57). These short FO windows are dominated by interannual swings (dry 2020 and 2025, partial recovery 2023) and should not be reported as a separate climate trend.

**Fix.** Headline the long window (or the monthly deseasonalized fit). Use period means, not a 6–7 year FO slope, to describe the 2020s. Keep the 2025 dry year in the series but show the drop-2025 check.

### 7. (Not a defect in the pull, but must be in findings.) Plausibility vs GLDAS and the literature

**GLDAS-2.1, same 21 years as the GRACE annual set.** RootMoist −1.837 cm/decade (HAC p=0.015, HR p=0.007, robust); SWE −0.418 cm/decade (robust); Root+SWE −2.255 cm/decade. The published 2000–2025 RootMoist −14.4 kg m-2/decade is −1.44 cm/decade (SWE −0.26). About 2 cm/decade of the GRACE −11.1 is in the modelled root zone plus snow; most of the TWS decline is not. Groundwater or deeper soil is the residual *candidate*. That split was not computed: GLDAS Noah has no groundwater, SoilMoi 100–200 cm and canopy were not downloaded, and GLDAS-2.1 forcing is known to be inhomogeneous (see `team-context/team/reviews/gesdisc_review.md`). Do not write “Ukraine groundwater is falling at 9 cm/decade” from this residual alone.

**Literature (same JPL mascon family, overlapping window).** Lenczuk and Debowska (2026, *Advances in Geodesy and Geoinformation*), JPL mascons April 2002–February 2026: Dniester −1.35 cm/year (−13.5 cm/decade), Dnieper −0.90 cm/year (−9.0 cm/decade), Danube −0.81 cm/year. The Ukraine bbox covers much of the Dnieper and Dniester basins; −11.1 cm/decade sits between those two figures and is plausible. A Bug River basin study for 2012–2023 reported TWS about −9 mm/year (−9 cm/decade), also the same order (north-west of / overlapping the box; our north-west mascons are about −7 to −9 cm/decade). I did not independently recompute those published basin averages.

**Fix.** Cite Lenczuk and Debowska (2026) next to the bbox rate. Keep the GLDAS comparison as an incomplete residual, with the 2.1 forcing caveat.

### 8. Minor: `lwe_thickness_cm` is the *scaled* series

The hydrology-oriented column is scale_factor applied; `lwe_thickness_unscaled_cm` is the trend baseline they prefer. The README says this clearly, but it is easy to grab the wrong column. Trends happen to agree to 0.01 cm/decade, so a mix-up would not change the headline rate, but it would be the wrong series relative to JPL’s trend warning.

## Answers to the processing checks

**Units.** `lwe_thickness` units are cm (Liquid_Water_Equivalent_Thickness). Independent land-only area-weighted unscaled means match the CSV to < 5×10^-7 cm.

**Land mask.** They used the in-file `land_mask` variable, whose description is “Land Mask that was used with the CRI filter” (binary 0/1). CRI has already split land/ocean mass in coastal mascons (`postprocess_3` on the granule). They keep `land_mask==1` only; they do not apply a fractional land weight. That is the standard CRI workflow, not a raw mascon LAND_MASK file from a separate ancillary. 48 ocean cells (north-west Black Sea) are dropped. GAD is not added to the land mean (official: GAD is added back to ocean pixels only).

**Area weighting.** Spherical cell area from `lat_bounds`/`lon_bounds`: R² Δλ (sin φn − sin φs), R=6371 km. Land area 1,074,880.811 km² matches an independent recompute. A simple cos(lat) approximation differs by a maximum relative 3×10^-6 on land cells; this is equivalent to cos(lat) weighting on a regular 0.5° grid for all practical purposes.

**Baseline.** Granule attribute `time_mean_removed: 2004.000 to 2009.999`. The regional unscaled mean over the 72 midpoints in 2004–2009 is −2.5×10^-17 cm (numerically zero). Annual 2004–2009 mean is 0.000 cm.

**Time stamps.** `time` is days since 2002-01-01; `time_bounds` are used. Midpoint-only labelling would double-count 2012-01 / 2015-04 and make 2011-12 and 2015-05 look missing. They assign each solution to a unique official calendar month: 244 windows lie inside one month, 15 by midpoint, 2 by majority/remaining overlap (2011-12 = 17 Dec 2011–15 Jan 2012; 2015-05 = 12 Apr–11 May 2015). After that assignment, holes match `months_missing` exactly. Some windows are short (13 days in January 2004, 17 days in May 2002). No extra unofficial gaps.

**Scaled vs unscaled.** JPL user guide (and Wiese et al., 2016): optional CLM 2002–2009 gain factors for continental hydrology at sub-mascon scale, applied after CRI, not for ice; “gain factors tend to be dominated by the annual cycles … and may thus not be suitable to quantify trends.” Area-weighted mean gain on land in this box is 1.002 (range −0.191 to 3.216). Fifteen Black Sea / Azov coastal land cells have small negative factors (CLM-fit artefacts). They correctly prefer unscaled for trend tests and show both. Annual OLS −11.131 (unscaled) vs −11.132 (scaled); monthly deseasonalized both −11.222.

## What was already done well

- Product, DOI, CRI version, ICE6G-D GIA, C20/C30 TN-14, geocenter, and “use the latest granule” (Kalman updates) are documented.
- Preliminary p-values are explicitly not for headlines.
- They did not splice 2017–2018 with interpolation in the trend set.
- README already warns about bbox vs country and 3° vs 0.5°.

## What I could not verify

- CSR or GSFC mascon comparison (only JPL is in the folder).
- A formal groundwater residual (deeper GLDAS soil layers and canopy were not downloaded).
- Exact published basin averages from Lenczuk and Debowska (2026) were not recomputed here; only their printed Dnieper / Dniester / Danube rates were used.
- Whether the 48 ocean-masked cells perfectly follow the coastline / Sea of Azov at 0.5° (the count and the CRI mask variable were checked, not a visual coastline audit).
- I did not re-download the granule from PO.DAAC; MD5 was checked against the official checksum file and the copy left in `/tmp/grace_work`.
