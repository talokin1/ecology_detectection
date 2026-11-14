# Ukraine sample trend-methods review

**Reviewer:** Critique  
**Date:** 14 November 2026, afternoon (Europe/Kiev)  
**Scope:** Existing Ukraine extracts and trend analysis under `$UKRAINE_SAMPLES/` (NASA Space Apps 2026, “Be An Earth System Trend Detective!”).  
**Constraint:** No files in `ukraine_samples/` were modified. Scratch work and recomputations are under `team-context/team/reviews/`.

This is a methods review of the sample analysis, not a product-concept review. The team does not yet have a tool architecture; these findings are about whether the Ukraine numbers and wording are defensible if shown to judges.

---

## How this review was done

I read `TEAM_BRIEF.md`, `ukraine_samples/README.md`, `analysis/headline_findings.txt`, `analysis/trend_summary.csv`, `analysis/modis_findings.txt`, `analysis/swot_findings.txt`, the staging scripts (`analyze_and_plot.py`, `analyze_modis_and_finalize.py`, MODIS/SWOT download scripts), and the saved annual/monthly series.

I then recomputed, from those saved series (and, where needed, the raw POWER / GSOM / Hydrocron files):

- OLS slope per decade and classical p-values (to confirm the published table)
- lag-1 autocorrelation of OLS residuals, effective sample size \(n_{\mathrm{eff}}=n(1-r)/(1+r)\), and AR(1)-inflated OLS p-values and 95% CIs
- Newey–West HAC p-values (lags 1 and 3)
- time-aware Theil–Sen (`scipy.stats.theilslopes` vs actual year or decimal year)
- Mann–Kendall `original_test` (their method) plus Hamed–Rao and Yue–Wang modified MK, and trend-free pre-whitening, via `pymannkendall` 1.4.3

Results: `team-context/team/reviews/recomputed_trends.csv`, `team-context/team/reviews/meta_checks.json`, `team-context/team/reviews/recompute_checks.py`.

I did not invent numbers. Every figure below is either copied from their tables or produced by the script above.

---

## Verdict

The **1981–2025 warming headline is solid** and survives the tests they skipped. Three independent sources agree at about +0.55 to +0.67 °C/decade, Mann–Kendall p-values are ≪ 0.001, and lag-1 residual autocorrelation is only modest (r ≈ 0.14–0.21). After an AR(1) adjustment the POWER T2M p-value is still 4.0×10⁻⁶.

The **SWOT “rivers are falling” results are not defensible as trends**. The record is ~3.3 years; Theil–Sen slopes in the findings are too small by about a factor of 12 because Sen’s slope was treated as per year when it was per month; and monthly water-surface elevation is strongly autocorrelated. For the Kyiv / Desna month-of-year anomalies, classical OLS p = 0.0054 becomes p = 0.39 after an AR(1) adjustment (n_eff ≈ 4.8). Several other “significant” SWOT p-values also inflate or disappear.

Between those poles: seasonality was handled adequately for the climate series (annual or seasonal means), but **serial correlation and multiple testing were not handled at all**. That mainly threatens the *marginal* claims (POWER precipitation and wind, some MODIS EVI slices), not the warming.

---

## Top issues (evidence)

1. **SWOT Theil–Sen slopes are mis-scaled, and significance is inflated by autocorrelation and a ~3-year record (blocking).**  
   `pymannkendall.original_test(values)` uses a unit time index (1, 2, …, n). For annual data that is “per year,” and ×10 is correctly “per decade.” For SWOT monthly series, the same code yields a slope **per month**, still multiplied by 10. That is a change per 10 months, not per decade. Time-aware Sen slopes (decimal year) are ~12× larger and line up with OLS. Example, month-of-year anomalies:

   | Site (reach) | Their Theil–Sen (findings) | Their OLS (findings) | Time-aware Sen (this review) | OLS (this review) | Residual lag-1 r | OLS p → AR(1)-adj p |
   |---|---:|---:|---:|---:|---:|---|
   | Chernihiv / Dnieper | −0.069 m/decade | −1.789 | −1.247 | −1.791 | 0.21 | 0.029 → 0.078 |
   | Kyiv / Desna | −0.042 | −1.305 | −0.861 | −1.342 | **0.79** | **0.0054 → 0.39** |
   | “Lviv” / Dniester | −0.277 | −4.802 | −4.293 | −4.517 | 0.51 | 9×10⁻⁶ → 0.010 |
   | Kherson / Dnipro | −0.035 | −0.527 | −0.527 | −0.561 | 0.58 | 9×10⁻⁵ → **0.051** |
   | Pripyat border | −0.191 | −2.717 | −2.751 | −2.735 | 0.52 | 0.0055 → 0.13 |

   The findings already warn that 2023–2026 is “not a climatological trend,” then still label several series “significant” and the team brief says “SWOT river levels falling (Desna, Dnieper, Dniester).” The Kherson series also overlaps the 6 June 2023 Kakhovka dam destruction (they report pre-breach median WSE 0.16 m, n=59, vs post 0.06 m, n=208) — a step change will look like a trend in a 3.3-year window. The “Lviv_Dniester” reach is 531 km from Lviv (29.59°E, 46.81°N), which they noted, but it is still used in the falling-rivers claim. Ice-clim and dark-water flags were downloaded and **not** applied: among valid Desna observations, `ice_clim_f=1` in 27% (58 of 214) and `dark_frac>0.5` in 36%; on the mislocated Dniester reach, `dark_frac>0.5` in 46%.

2. **No handling of serial correlation in the published tests (blocking for SWOT; should-fix in the method used for everything).**  
   Scripts call `scipy.stats.linregress` and `mk.original_test` only. There is no pre-whitening, no Hamed–Rao / Yue–Wang MK, no effective sample size, and no HAC / AR(1) CIs — even though `lin_stderr_decade` is written to the table as if it were a ready-to-use uncertainty.  
   On **annual climate series** this is not fatal: POWER T2M residual r = 0.21, n_eff ≈ 29 of 45, AR(1)-adjusted p = 4.0×10⁻⁶; GSOM TAVG 1981–2025 r = 0.14, adjusted p = 1.2×10⁻⁵; GHCN tmean r = 0.17, adjusted p = 6.0×10⁻⁷. Warming stays significant.  
   On **monthly SWOT** it is fatal (see above).  
   Yue–Wang sometimes returned implausibly small p-values even where other tests did not (e.g. POWER precipitation yw p = 7×10⁻¹¹ vs original MK p = 0.023 and OLS p = 0.091). I treat Yue–Wang as unreliable here and lean on AR(1)-adjusted OLS, HAC, and Hamed–Rao.

3. **Marginal “significant” claims and no multiple-testing control (should-fix).**  
   `trend_summary.csv` has **43** tests. 33 have MK p < 0.05, 32 have OLS p < 0.05. Significance in the findings is decided **only** by MK p < 0.05, which produces inconsistent wording:

   - POWER PRECTOTCORR: OLS +14.57 mm/decade, **linear p = 0.091** (not significant), **MK p = 0.023** (“significant”). Residual r ≈ 0; HAC lag-1 p = 0.14. Autocorrelation is not the problem — OLS and MK disagree, and they picked the significant one.
   - POWER WS10M: linear p = 0.077, MK p = 0.022, also called “significant.”
   - MODIS EVI_JJA: the opposite — linear p = 0.038, MK p = 0.072, called “not significant.”

   A Bonferroni cut of 0.05/43 ≈ 0.00116 leaves 21 MK results significant. That cut is conservative because many tests are dependent (seasons, cities, overlapping vegetation windows), but it shows that EVI annual (MK p = 0.0072), EVI AMJJAS (p = 0.038), POWER precip, POWER wind, and several SWOT p-values should not be billed as clear detections. The README’s softer line, “precip ~+15 mm/decade (mostly not significant),” is closer to the evidence than the findings file’s “significant” label on POWER precip.

4. **GSOM temperature 1981–2025 is not a continuous 45-year record, and the network thins sharply (should-fix, disclosure).**  
   The findings say “n=40 years 1981–2025.” The 40 years are 1981–2019 and **2025 only**. **2020–2024 are entirely missing** from both the 1981–2025 and 1961–2025 anomaly series. Station count among the 9 long-record stations is 9 through 2012, **4 from 2013–2019 and in 2025**, and 0 in 2020–2024. The four stations that vanish after 2012 are Nikolaev, Feodosiia, Ai-Petri, and Lugansk; they were on average **0.91 °C warmer** than the five that remain (Shepetivka, Lubny, Poltava, Uman, Askaniia Nova) during 1981–2012. Because the series is anomalies vs each station’s 1991–2020 mean, dropping warmer stations should not by itself bias the mean anomaly, but spatial coverage collapses and the isolated 2025 point sits after a five-year hole. Truncating at 2019 changes the slope only slightly (+0.578 vs +0.563 °C/decade), and POWER/GHCN have no such hole, so the warming *conclusion* still holds. The wording “n=40 years 1981–2025” hides the gap.

5. **MODIS LST is compared with 1981–2025 air temperature as if it were steeper; most of that gap is the period, not the sensor (should-fix, wording).**  
   Published: POWER T2M 1981–2025 **+0.551 °C/decade**; MODIS LST 2001–2025 **+0.823 day / +0.869 night °C/decade**. Recomputed POWER T2M on the **same 2001–2025 window** is **+0.793 °C/decade** (p = 1.6×10⁻⁵, n=25) — in line with the LST rates. LST is not 2-m air temperature and Terra-only C6.1 without QC is still a product caveat, but the “a bit steeper” contrast in the README is largely an apples-to-oranges period comparison.

---

## What’s done well

- **Annual (or meteorological-season) aggregation** is the right first defence against a seasonal cycle dominating Mann–Kendall or OLS. That was applied consistently to POWER, GSOM, GHCN, and MODIS. SWOT is the only monthly analysis, and they did attempt month-of-year anomalies (with an explicit warning that this is not a climatological baseline).
- **Cross-source temperature check is real, not cosmetic.** POWER (MERRA-2 bbox mean), GSOM long-record anomalies, and GHCN-Daily city anomalies all give +0.55 to +0.67 °C/decade for 1981–2025, with city series (Kyiv +0.611, Lviv +0.617, Odesa +0.667, Kharkiv +0.681, Simferopol +0.638, Uzhhorod +0.503) in the same range. That is the result I would put in front of judges, with the autocorrelation caveat noted but not as a threat to the claim.
- **Incomplete 2026 is excluded** from climate annual trends; MODIS 2000 (starts in February) is also excluded. Good.
- **GSOM precipitation network collapse after ~2000 is flagged**, charted, and they computed a pre-collapse 1950–2000 series separately instead of naively trending all stations through the 2010s. That is the right instinct.
- **Station temperature uses 1991–2020 anomalies and a long-record filter**, which is the correct way to combine a changing set of stations.
- **GHCN-Daily quality flags are applied** (non-empty Q dropped); temperature units (tenths of °C) and precipitation (tenths of mm) are converted correctly.
- **POWER PRECTOTCORR** is converted mm/day × days-in-month with leap-aware February, and a year is kept only if all 12 months are present.
- **OLS, Theil–Sen, and Mann–Kendall are all reported**, and for annual series the two slopes usually agree closely (POWER T2M +0.551 vs +0.541; GHCN tmean +0.667 vs +0.672; MODIS night LST +0.869 vs +0.875). They also report n, start, and end.
- Several **data traps were already documented**: Lviv reach is not near Lviv; Kherson reach is not Kakhovka reservoir; bbox is not a Ukraine polygon; SWOT is a short record; POWER ANN for T2M_MAX/MIN is the annual extreme (and the *saved* series correctly used the mean of monthly values, not ANN).
- MODIS DAP4 subsets are complete: 321/321 months February 2000–October 2026, all HTTP 200. Valid-pixel counts are stable (NDVI_n 53,148–53,340; trend of annual-mean count ≈ −0.6 pixels/decade), so a collapsing spatial sample is not obviously aliasing the VI/LST trends.

---

## Checks requested

### 1. Seasonality

**Climate series: adequately handled, not by deseasonalized monthly anomalies, but by annual or seasonal means.**  
`analyze_and_plot.py` and `analyze_modis_and_finalize.py` explicitly “prefer annual series so the seasonal cycle does not dominate the test.” Trends are fit to annual means, or to DJF/MAM/JJA/SON (POWER T2M) or JJA/MAM/DJF / AMJJAS (MODIS). A monthly climatology was computed for the MODIS chart only; it was **not** subtracted before the MODIS trend fit, and it does not need to be for annual or single-season means.

**SWOT: they did subtract a month-of-year mean**, but with only ~3 years of data that “climatology” is the mean of three or four months. Residual seasonality and sampling artifacts remain. This is disclosed, then under-weighted in the interpretation.

Minor: POWER T2M DJF for 1981 uses January–February only (`np.nanmean` of missing Dec 1980 + Jan + Feb). Dropping 1981 changes the DJF slope from +0.529 to +0.546 °C/decade (p 0.0105 → 0.0115). Negligible.

### 2. Serial autocorrelation and inflated significance

**Not handled in the published analysis.** See Top issue 2.  
Recomputed lag-1 residual r and the effect on inference:

- Strong warming / LST / solar: r small to moderate; conclusions unchanged.
- POWER precip and wind: r ≈ 0; the issue is MK vs OLS, not AR(1).
- SWOT monthly anomalies: r = 0.21 to **0.79**; several “significant” OLS/MK results do not survive an AR(1) adjustment (Kyiv/Desna, Pripyat, Kherson at the 0.05 line, Chernihiv).

**Fix:** For annual series, report AR(1)-adjusted or HAC standard errors and a Hamed–Rao (or trend-free pre-whitened) MK p-value beside the classical ones. For monthly series, do not use `original_test` without accounting for the time step, and do not call a 3-year autocorrelated series a significant trend.

### 3. Sen’s slope vs OLS, and per-decade conversion

**Annual series: conversion is correct (slope × 10), and Sen vs OLS is generally consistent.**  
Largest annual disagreement of interest is GSOM PRCP 1981–2024: OLS **+15.54** vs Sen **+8.89** mm/decade (neither significant). That is a heavy-tail / outlier effect, not a unit bug. GSOM TAVG 1981–2025 Sen using their unit index is +0.544 vs a time-aware Sen of +0.528, because the 2019→2025 jump is treated as one step instead of six years. Small, but it is the same class of bug as SWOT, just less damaging on a mostly annual grid.

**SWOT monthly: conversion is wrong** (Top issue 1). OLS (decimal years × 10) is the quantity that is actually “per decade.” Their published Theil–Sen should not be placed next to it as if they were the same unit.

T2M_MAX / T2M_MIN: the **saved** annual series matches the **mean of the 12 monthly values**, not POWER `ANN`. For 1981, saved T2M_MAX is 18.99 °C vs ANN spatial mean 31.60 °C (the annual extreme). Findings text is correct; the current `analyze_and_plot.py` uses `g["ANN"].mean()` and would **not reproduce** the saved series if re-run. Mean-of-monthly-maxima is also not “mean of daily maxima”; in this POWER file each month’s T2M_MAX equals that month’s extreme (ANN equals the max of the 12 months). Document the metric clearly.

`trend_summary.csv` units for QV2M are **kg/kg**; the POWER header and the findings correctly say **g/kg**. The slope +0.163 /decade is only physical in g/kg (annual means are ~6 g/kg).

### 4. Record length, gaps, start/end effects

| Series | What the label says | What is actually there |
|---|---|---|
| GSOM TAVG 1981–2025 | n=40 years 1981–2025 | Missing **2020–2024**; 9 stations → 4 after 2012 |
| GSOM TAVG 1961–2025 | n=60 years 1961–2025 | Same 2020–2024 hole |
| GSOM / GHCN precip 1981–present | n=10 / n=6 long-record stations | GHCN P already n=2 in 2020–2024 (2025 missing); reconstructed GSOM P n=2 in 2020 and 2022–2024, **2021 and 2025 missing** |
| GHCN city tmean “1981–2025” | period column 1981–2025 | Kyiv, Lviv, Odesa, Simferopol end **2024** (n=44); Kharkiv n=43, 1981–2024; only Uzhhorod includes 2025 among the six cities |
| GHCN regional tmean | n=45, 1981–2025 | 2025 is present but only **9 of 24** long-record stations (20 in 2018–2021, 15 in 2022, 19 in 2023–2024). 2024 anomaly is **+2.57 °C**. Slope 1981–2023 = +0.623 vs 1981–2025 = +0.667 °C/decade |
| POWER T2M | complete 1981–2025, 464 cells | 2024 is also very warm (anomaly +2.26 °C vs 1991–2020). Slope 1981–2023 = +0.502 vs 1981–2025 = +0.551 °C/decade. Direction unchanged; the last two years do lift the rate |
| POWER ALLSKY | period column “1981–2025” | Actually **1984–2025**, n=42, and only **144 cells** (CERES grid, not the 464 MERRA-2 cells). Findings text is right; the CSV period field is not |
| SWOT | 2023–2026 | ~3.25–3.59 years, ~39–44 months. Reporting **metres per decade** extrapolates a short wiggle to 10 years |
| MODIS | 2001–2025 complete years | Sound. 2000 and 2026 correctly dropped |

Short records and end-point leverage should be shown (leave-last-years-out), not only n and a year range.

### 5. Spatial aggregation

- **POWER:** unweighted mean of 464 MERRA-2 cells (0.5° × 0.625°, lats 44.5–52.0°N, lons 22.5–40.0°E). No `cos(lat)` weighting. Southern cells are ~16% larger than northern ones (`cos(44.5)/cos(52.0) = 1.159`). Recomputation: mean absolute difference of unweighted vs cos-weighted annual T2M is **0.078 °C**; the trend is **+0.551 vs +0.552 °C/decade**. Negligible for the rate. A rough drop of 51 “open NW Black Sea” cells (lat ≤ 45.5° and lon ≥ 30°) gives +0.546 °C/decade. Also negligible.
- **The domain is still not Ukraine.** The bbox 22.1–40.2°E, 44.4–52.4°N has an approximate area of **1.19 million km²**, about **twice** the commonly cited area of Ukraine (~0.60 million km²). It includes the NW Black Sea and land in Moldova, Belarus, Russia, Romania, Poland, Slovakia, and Hungary. This is disclosed in the README. For a “Ukraine” story, use a country polygon and a land mask. It does not appear to be what drives the warming rate.
- **GSOM / GHCN:** unweighted mean of station anomalies. No area or latitude weighting. GSOM uses country code UP (good) but only 9 (then 4) long-record TAVG stations. GHCN-Daily is a **28-city subset**, not the full network — a bit warm-biased vs POWER (+0.667 vs +0.551) is plausible (urban / city siting), not proof of error.
- **MODIS:** unweighted mean of valid 0.05° CMG pixels in Y 752:912, X 4042:4404 (the bbox). No `cos(lat)`, no Ukraine polygon. “Valid” = fill/range only (NDVI/EVI raw in [−2000, 10000]; LST raw ≠ 0 and ≥ 7500). Land-water separation is implicit in which pixels are filled, not an explicit mask. Pixel counts are stable, so this is a modest issue compared with the bbox definition.

### 6. Data / product issues

- **MODIS is Terra-only (MOD13C2, MOD11C3), Collection 6.1.** Aqua (MYD) was not used. C6.1 is the right collection; residual Terra drift is a known literature caveat, not something I independently measured here.
- **No MODIS QA/QC was downloaded or applied.** The DAP4 subsets contain only NDVI, EVI, LST_Day, and LST_Night. Pixel Reliability, VI Quality, and LST QC bits were never requested. Cloudy or poor-quality monthly means can still fall inside the valid range.
- **OMI row anomaly, GPM IMERG versions, AIRS, MERRA-2/GLDAS from GES DISC:** not in this sample set (GES DISC still blocked). I could not check those product issues because the data are not here. NASA POWER already supplies MERRA-2 T2M and PRECTOTCORR and CERES all-sky SW without GES DISC; treat POWER as a reanalysis/satellite product, not in-situ.
- **GSOM download has no quality-flag columns** (only STATION, NAME, lat/lon, ELEVATION, DATE, PRCP, TAVG, TMAX, TMIN).
- **SWOT Hydrocron Version D:** fill `|x|>1e6` and `reach_q>2` dropped (good, incomplete). `ice_clim_f`, `ice_dyn_f`, and `dark_frac` were requested and **not used**. Several intended sites (Kharkiv/Donets, Izmail/Danube, Uzhhorod/Tisza, one Southern Bug and one Dniester ID) did not yield usable time series.
- **POWER T2M_MAX/MIN metric** and **QV2M units** as above.
- I did not attempt a Terra calibration-drift audit or a full black-sea / urban-fraction map; that would need QA layers and a land mask I did not rebuild from the eight example NetCDFs.

### 7. Multiple testing

43 related tests, no correction, MK-only “significant” flag. See Top issue 3. The product, when built, should either test pre-declared primary series (e.g. annual T, P, one vegetation index, one LST) or report FDR / at least warn that p < 0.05 across dozens of related series will produce false positives.

### 8. Are the headline claims supported?

**Supported (with the caveats already in this review):**

- Warming of about **+0.55 to +0.67 °C/decade since 1981** from POWER, GSOM, and GHCN, MK p < 10⁻⁶ (and still < 10⁻⁵ after AR(1)). This is the strongest result in the folder.
- MODIS annual NDVI 2001–2025 **not significant** (+0.008/decade, MK p = 0.107). Correctly stated.
- MODIS annual EVI a small increase (+0.008/decade, MK p = 0.007). Number is right; “significant” should be softened given multiplicity and the fact that growing-season NDVI is not increasing (AMJJAS/JJA NDVI slightly negative, not significant).
- GSOM / GHCN precipitation 1981–present **not significant**; early GSOM 1950–2000 **+22.1 mm/decade** (OLS p = 0.0044, MK p = 0.0058) is a supported secondary result, with the usual network and change-of-climatology (1961–1990 baseline) caveats.
- Incomplete-year and SWOT-short-record warnings, Lviv mislabel, and “Kherson is not Kakhovka” are accurate and should stay.

**Overclaimed or wrongly worded:**

- Findings call POWER precip and wind “significant” on MK alone despite non-significant OLS (and HAC p > 0.05).
- README / brief contrast of MODIS LST “a bit steeper” than 1981–2025 air temperature without a same-period comparison (POWER 2001–2025 is +0.793 °C/decade).
- “n=40 years 1981–2025” for GSOM TAVG without stating the 2020–2024 gap and the drop to four stations.
- City lines labelled “annual tmean 1981–2025” when most end in 2024.
- Team brief: “SWOT river levels falling (Desna, Dnieper, Dniester) … (Theil–Sen on month-of-year anomalies).” The Theil–Sen numbers they would be pointing to are the mis-scaled ones, the Desna signal is not robust to autocorrelation, Dniester is not the Lviv reach, and Dnieper at Kherson is entangled with a dam break. Do not take this sentence into a pitch deck.
- `trend_summary.csv` QV2M units `kg/kg` and ALLSKY / some GHCN period fields are wrong even when the findings text is right.

---

## Issues by severity, with concrete fixes

### Blocking (do not show these as findings until fixed)

1. **SWOT slopes and “significant decline” language.**  
   **Fix:** Recompute Sen’s slope against decimal year (or scale the unit-index slope by 12 months, then ×10 for a decade). Report change over the actual ~3.3-year span (or m/year), not m/decade, as the lead number. Apply `ice_clim_f` / dark-water filters and show a before/after. For Kherson, test a step at 6 June 2023 rather than a linear trend. Drop or relabel “Lviv_Dniester.” Do not call Desna / Pripyat / Chernihiv “significant” without an autocorrelation-robust p-value; several will not pass. Frame SWOT as a short operational record and a method demo, not a climate trend.

2. **Default significance recipe (linregress + original MK, MK p only) shipped as if it were judge-ready.**  
   **Fix:** Make the published test autocorrelation-aware (Hamed–Rao or TFPW MK; OLS with HAC or AR(1) effective n). Use one pre-declared rule for the word “significant,” and show OLS and MK together when they disagree. This is blocking for monthly data; it is a should-fix for the annual warming numbers, which already pass the stricter tests.

### Should fix

3. **Disclose GSOM gaps and network thinning** in the findings and on the chart (shade 2020–2024; annotate n=9 → n=4). Prefer POWER and GHCN as the continuous 1981–2025 temperature series; keep GSOM as corroboration with the hole visible.

4. **Do not call POWER precipitation or wind significant** in headlines. Report both p-values and say the signal is weak / method-dependent. Same for MODIS EVI AMJJAS (p ≈ 0.04).

5. **Multiple testing:** pre-declare a short primary list, or add BH-FDR, and say how many tests were run.

6. **Compare MODIS LST to air temperature over 2001–2025**, not 1981–2025. Keep the physical distinction (LST vs 2-m air).

7. **MODIS QA and Terra/Aqua:** request Pixel Reliability / LST QC in the DAP4 subset (or AppEEARS once login works); optionally add MYD13C2/MYD11C3 as a robustness series.

8. **Clean `trend_summary.csv` and script reproducibility:** QV2M units g/kg; ALLSKY period 1984–2025; city periods ending 2024 where needed; fix `power_annual_series()` so T2M_MAX/MIN do not silently switch to ANN on the next run; save the GSOM 1981–present PRCP anomaly series (it was computed and quoted but not written, unlike the 1950–2000 file).

9. **Precip station series after ~2013:** either stop the GHCN/GSOM precip trend when n becomes tiny (n=2 is not a regional series) or present those years as a sparse overlay, not part of the fitted sample without a warning on the chart.

10. **If the narrative is “Ukraine,”** mask to a country polygon and land only. The bbox disclaimer is not enough for a final figure title that says “Ukraine.”

### Nice to have

11. `cos(lat)` area weighting for POWER and MODIS (effect on T2M trend is ~0.001 °C/decade, but it is the correct default).
12. Leave-one-end-point / 1981–2023 vs 1981–2025 sensitivity on the combined chart (2024 is a +2.3 °C POWER anomaly).
13. GSOM quality flags if NCEI provides them; GHCN already has them.
14. A second humidity/wind/solar source when GES DISC or KNMI is available.
15. Parse and archive Hydrocron CSVs as real multi-line CSVs (several reach files are a single quoted line with literal `\n`, which is brittle).

---

## What I could not check, and why

- **GES DISC products (MERRA-2 from the archive, GLDAS, AIRS, OMI, GPM IMERG, hydrology data rods):** not present; access still blocked pending the user’s GES DISC app approval. OMI row-anomaly and IMERG version issues therefore could not be assessed.
- **AppEEARS rasters and KNMI Climate Explorer series:** not downloaded (token/login and human-check barriers, documented in `login_required.md`).
- **A full Ukraine-polygon vs bbox re-aggregation of MODIS** would require re-reading all monthly CMG fields with a land/country mask. Only eight example NetCDFs were kept; the time series were stored as pre-aggregated means. I checked the window definition and valid-pixel counts, not a polygon remap.
- **Terra residual calibration drift and Aqua minus Terra differences:** Aqua was not downloaded; I did not attempt a drift model from eight sample granules.
- **SWOT ice/dark impact on the fitted slopes:** I quantified flag rates on the raw Hydrocron files but did not re-filter and re-fit (would be the natural next fix, not done here so as not to invent a “corrected” SWOT headline).
- **Yue–Wang p-values** were computed but I do not recommend them as evidence in this dataset (unstable/too small). Hamed–Rao and AR(1)/HAC are the robust checks I stand behind.
- **Official product user guides** (POWER T2M_MAX monthly definition, MOD11C3 QC bit tables) were inferred from the files themselves (e.g. monthly T2M_MAX equals the annual extreme in the same row when that month is the year’s max). I did not fetch NASA documentation pages in this pass.

---

## Bottom line for the team

Keep the **cross-checked 1981–2025 warming** result; add autocorrelation-aware p-values and CIs, and they will still stand. Soft-pedal or drop **POWER precip/wind “significant,”** period-mismatched **MODIS vs air-temperature** wording, and any **SWOT “rivers falling”** claim. Fix the Sen-slope time scaling in the shared `trend_stats()` helper before it is reused in the app — it is correct for annual data and silently wrong for monthly data, which is exactly how a Trend Detective tool will be used.


---

## Re-review (revised analysis, 14 November 2026, Europe/Kiev)

**Reviewer:** Critique  
**Inputs checked:** `analysis/headline_findings.txt`, `trend_summary.csv` (47 tests), `swot_findings.txt`, `modis_findings.txt`, `swot_kherson_kakhovka_step.json`, `swot_quality_flag_counts.csv`, saved annual/seasonal/MODIS series, raw POWER T2M and Hydrocron reaches, and `_staging/trend_methods.py` / `revise_analysis.py` / leftover `analyze_and_plot.py` and `analyze_modis_and_finalize.py`.  
**Scratch:** `team-context/team/reviews/rereview_checks.py` (independent recomputation; nothing in `ukraine_samples/` was modified, and `revise_analysis.py` was not executed in place).

**Verdict: approved with minor fixes.**

The warming headline is still solid, and the claimed methodological revisions are real — not just wording. Bonferroni/BH counts, time-aware Sen, ice/dark SWOT filters, Desna AR(1) p, QV2M units, date ranges, GSOM 2020–2024 gap (plus the 1981–2019 slope), method-dependent labels for precip/wind/EVI_JJA, MODIS caveats, and the “rivers falling” withdrawal all check out against the data and against `trend_methods.py`. The remaining problems are concentrated in the Kherson “step −0.11 m” presentation (seasonality not handled; formal step tests are not significant), leftover old scripts that can overwrite the revised tables, and two method choices (HAC lag-1 only in the “robust” rule; Hamed–Rao with the library default of all lags) that did not flip the climate headlines here but are weak for monthly or negatively autocorrelated series.

### What was fixed correctly

- **“Robust” definition.** `trend_methods.robust_call` requires HAC lag-1 p < 0.05 and Hamed–Rao p < 0.05 (TFPW only if HR is missing). Classical MK alone is not enough. Recomputing the rule on all 47 CSV rows gave 0 disagreements with `robust_call`.
- **Multiple-testing counts.** Independently, with `statsmodels.stats.multitest.multipletests` on the 47 `hac1_p` values: unadjusted HAC p<0.05 = 33; Hamed–Rao p<0.05 = 36; both = 32; HAC Bonferroni rejects = 24; HAC BH-FDR (0.05) rejects = 32; Bonferroni α = 0.05/47 = 0.00106383 (they report 0.001064). Primary family of 11: Bonferroni α = 0.004545, 8 HAC Bonferroni rejects and 8 HAC BH rejects, 0 disagreements with the CSV. Primary series that fail unadjusted 0.05 (and Bonferroni) are POWER precip, GHCN precip, and annual NDVI — matching the findings text.
- **Time-aware Sen is used in the producing pipeline.** `trend_methods.trend_stats` calls `scipy.stats.theilslopes(values, actual year or decimal year)` and is what `revise_analysis.py` writes to the CSV. That covers annual POWER/GSOM/GHCN, POWER seasons, all 12 MODIS series, and SWOT month-of-year anomalies. Time-aware vs unit-index Sen is identical for evenly spaced POWER and MODIS annual series (difference 0) and differs where it should: GSOM PRCP_1981 8.518 vs 8.891 mm/decade; SWOT slopes are ~9–12× larger than the unit-index ×10 column (e.g. Lower Dniester −2.408 vs −0.262 m/decade).
- **SWOT filters, rename, Desna, and “rivers falling.”** Re-parsing Hydrocron and applying fill, `reach_q>2`, `ice_clim_f>=1`, and `dark_frac>0.5` reproduces `swot_quality_flag_counts.csv` exactly (Desna usable 101, ice 58, dark 76; Kherson usable 236; all eight sites match). `ice_dyn_f` is −999 in every row and is not used as a drop rule, as disclosed. Monthly anomaly trends recomputed with `trend_stats` match the CSV on n, slopes, HAC, HR, and AR(1) p (0 diffs). Desna: residual r = 0.574, AR(1)-adj p = 0.386, HAC lag-1 p = 0.079, called method-dependent. Lviv_Dniester is renamed Lower Dniester (29.59°E, 46.81°N). The findings no longer claim that rivers are falling; per-decade SWOT slopes are labelled as short-record extrapolations.
- **Precip, wind, EVI_JJA** are labelled method-dependent, with p-values that match the CSV (POWER precip HAC 0.142 vs MK/HR 0.0227; WS10M HAC 0.0881 vs MK 0.0184 / HR 0.00513; EVI_JJA HAC 0.0467 vs HR 0.0721).
- **GSOM 2020–2024 gap.** The 1981–2025 TAVG series has n = 40 and is missing 2020–2024. Truncating at 2019 gives OLS +0.578 °C/decade (CSV 0.5778), as disclosed. Station count 9 through 2012, 4 in 2013–2019, 0 in 2020–2024, 4 in 2025 is correct. (A parenthetical naming nit remains; see below.)
- **QV2M units and date ranges.** QV2M is `g/kg`, period 1981–2025. ALLSKY is 1984–2025, n = 42. GHCN city periods end in 2024 except Uzhhorod (1981–2025, n = 43).
- **POWER ANN is no longer used for the bbox annual series in `analyze_and_plot.py`.** The annual helper documents “mean of the 12 monthly spatial means” and warns not to use ANN for T2M_MAX/MIN (ANN is the annual extreme). Grid-cell T2M trends still use the ANN column, which is appropriate for T2M.
- **MODIS and domain caveats** (bbox ~2× Ukraine, Terra-only, no QA, no land mask, pixel-count stability, 2001–2025 complete years) are in the findings. LST is compared to POWER T2M 2001–2025, not 1981–2025.
- **Scripts vs CSV.** `trend_methods.trend_stats` applied to the saved climate, seasonal, and MODIS series reproduced the published slopes and p-values with 0 mismatches (including GHCN `tmean_regional_1981-2023`). SWOT re-filtering and Kherson median/MW/OLS/HAC numbers match the JSON and findings exactly. The producing script is `revise_analysis.py` + `trend_methods.py`, not `analyze_and_plot.py`. `revise_analysis.py` was not run against `ukraine_samples/` in this review.

### POWER T2M 2001–2025: +0.797 vs +0.793

Both numbers are correct for the series each of us used; the difference is the annual-mean definition, not an arithmetic error.

- Their +0.797 is OLS on the unweighted mean of the 12 monthly spatial means (the saved `power_T2M_bbox_annual.csv`). Recomputed: **+0.797205 °C/decade** (Sen +0.784348), which is what the CSV and findings report as +0.797 / +0.784.
- The earlier review’s +0.793 is OLS on the spatial mean of POWER’s ANN column. Recomputed: **+0.793156 °C/decade**.
- ANN is essentially a day-weighted annual mean: in 1981/1984 the max absolute difference vs a cell-level day-weighted mean of the 12 months is 0.005 °C; across all years, ANN vs the spatial mean of cell day-weighted annual values differs by at most 0.00034 °C. Day-weighted monthly-spatial means give the same 2001–2025 OLS slope as ANN, +0.793156.
- For 1981–2025 the same split is +0.552706 (their method, reported as +0.553) vs +0.551013 (ANN; the old table’s +0.551). For 1981–2023: +0.503447 vs +0.502019.

The gap is about **0.004 °C/decade**. It does not change the comparison with MODIS LST_Day (+0.823) or LST_Night (+0.869) over 2001–2025. ANN / day-weighting is slightly closer to a true annual mean; their unweighted-month method is also a standard choice and is applied consistently. Either can be kept; they should just name the definition (they already do in the script comments).

### Specific checks requested

**HAC lag-1 only — adequate for these annual series, thin for monthly SWOT.**  
They compute Newey–West at lags 1 and 3 but the “robust” rule uses only lag-1. Recoding “robust” as HAC lag-3 p<0.05 AND Hamed–Rao p<0.05 produced **0 call flips** among the 47 tests. For annual climate series that is reassuring (residual r is mostly modest). For monthly SWOT anomalies it is less so: Kherson anomaly residual ACF is 0.38, 0.54, 0.32 at lags 1–3; Odesa 0.32, 0.31, 0.25; Desna 0.57, 0.11, −0.07. HAC lag-3 still leaves Lower Dniester and Odesa below 0.05 (p = 2.44×10⁻⁶ and 0.00651). Longer HAC lags on n≈30 with 3–5 month gaps (Desna max gap 4.97 months) are not reliable and are not recommended as a new rule. The lag-1 “robust” definition did not change any wording in this table, but for monthly series the rule should require lag-3 agreement, or at least report it in the findings, not only in the CSV.

**Hamed–Rao implementation is the library, with the weak default lag.**  
They call `pymannkendall.hamed_rao_modification_test` (v1.4.3), not a hand-rolled test. That is the right function. With `lag=None` (their call), the package sets `lag = n` and loops over all lags, adding only “significant” rank ACFs of a *unit-index* detrended series. The docstring itself says you can use `lag=3`, “which also [was] proposed by Hamed and Rao (1998).” Published `mk_hr_p` values match the all-lag default exactly on the climate and MODIS series I recomputed.

Re-running HR with `lag=3` did **not** flip any 0.05 decision on the climate/MODIS series I tested (WS10M moves from 0.00513 to 0.0184, still <0.05). It does matter for SWOT: Desna HR p = 6.67×10⁻⁶ (all lags) vs **0.117** (lag=3); Chernihiv 0.0394 vs **0.0564**. Both reaches are already called method-dependent because of HAC, so wording does not change. Two further limitations remain: (1) negative residual autocorrelation shrinks the HR variance and is anti-conservative — EVI_AMJJAS residual r = −0.51, classical MK p = 0.0377, HR p = 4.5×10⁻¹² (same at lag=3, because lag-1 is included); (2) HR assumes equally spaced observations, which is a poor fit to the GSOM 2020–2024 hole and to SWOT months missing after ice/dark filters. Yue–Wang is stored and correctly not used for wording.

**Kherson “step” does not handle seasonality; the wording overreaches.**  
Published numbers recompute exactly: usable pre n = 59 (2023-04-05 to 2023-06-05, 60 days), post n = 177 (2023-06-06 to 2026-11-10); median pre 0.1617 m, post 0.0539 m, median step **−0.1078 m**; Mann–Whitney p = 3.32×10⁻⁷; OLS dummy −0.1059 m (p = 0.294); HAC lag-3 p = 0.0974; time+step coefficient **+0.1504 m**, HAC lag-3 p = 0.147. They are right not to use a linear climate trend, and they do print the non-significant OLS/HAC p-values.

They do **not** deseasonalize or seasonally match the step. Pre is only April, May, and 5 early-June observations. Post covers March–December over ~3.5 years. Mann–Whitney assumes iid samples and is confounded by the seasonal cycle. Independent checks:

- Post April–June only: median 0.1557 m, matched-season step **−0.006 m**, MW p = **0.687**.
- Cleaner April–May window (pre-June is only five pre-breach days): step **−0.0938 m**, MW p = 0.00083 (pre n=54, post n=27).
- That April–May difference is not a persistent level shift: Apr–May medians are 0.1634 m (2023 pre), **0.1799 m in 2024** (higher than pre), −0.0405 m in 2025, and 0.0828 m in 2026 (n=9 each post year).
- Month fixed effects + step (months that actually have data): step **−0.031 m**, OLS p = 0.823, HAC lag-3 p = 0.530.
- Month FE + time + step: step **+0.220 m** (sign flip), HAC lag-3 p = 0.018 (the decline is absorbed by the time term).

Leading with “step −0.11 m; Mann–Whitney p=3.32e-07” presents an all-season median gap as a Kakhovka level shift. The formal dummy/HAC tests they already computed do not support that, and a seasonally matched April–June comparison essentially removes it. The CSV still labels the Kherson *linear* anomaly row `robust at 0.05` (and it is one of the 24 Bonferroni rejects) even though the variable is named `WSE_monthly_anomaly_m_for_reference_only` and the domain says it is not a trend.

### Remaining issues

**Should-fix**

1. **Kherson step wording and seasonality** (evidence above). Do not lead with the all-season median and MW p. Either report a seasonally matched contrast (and the year-to-year April–May spread) or say that a simple pre/post median difference is not a clean step estimate. Drop or qualify “treated as a step change.” Remove the Kherson linear row from the “robust” count and from the family of 47 if it is not being interpreted as a trend.

2. **Leftover scripts can clobber the revised results.** `analyze_and_plot.py` (line 47) and `analyze_modis_and_finalize.py` (line 38) still define a local `trend_stats` that uses unit-index Sen (`mk.original_test` slope × 10) and classical MK only, then write `analysis/trend_summary.csv` and `headline_findings.txt`. Re-running them would undo the revision. Retire, guard, or point them at `trend_methods.py`.

3. **Hamed–Rao should not use the all-lag default, and should not be treated as confirmatory when residual r is strongly negative.** Call `hamed_rao_modification_test(..., lag=3)`. Keep EVI_AMJJAS as “not a clear headline detection”; the published HR p = 4.5×10⁻¹² is not a credible confirmation of the modest classical MK p = 0.0377. The “robust” label on that row is in tension with the caveat (HAC is actually *more* significant than OLS here because negative AR makes unadjusted tests conservative, so the detection is not imaginary — the HR p-value is).

**Nice-to-have**

4. **HAC “robust” rule:** include lag-3 agreement for monthly series, or state in the methods preamble that lag-3 was checked and did not change calls (true for this table).

5. **GSOM coverage sentence.** “4 from 2013–2019 and in 2025 (Shepetivka, Lubny, Poltava, Uman; Askaniia Nova ends 2019)” blends two different sets. With a ≥10-month year rule, 2013–2019 are Shepetivka, Lubny, Uman, and Askaniia Nova; 2025 are Shepetivka, Lubny, Poltava, and Uman. Poltava has no ≥10-month year in 2013–2019 (it last qualifies in 2012, then 2025). The count of four in each window is correct.

6. **“Robust” on ~3.3-year Lower Dniester and Odesa series.** p-values remain <0.05 at HAC lag-3 and HR lag=3, and the short-record disclaimer is present. Still, “robust” has no minimum record length; a climate-trend reading is not justified and they already say so.

7. **CSV inconsistency:** `n_tests_in_family` is 11 on the 11 primary rows and 47 on the other 36. Findings text is fine. The primary family also includes both T2M 1981–2025 and T2M 2001–2025, which are not independent (already flagged as “many tests are dependent”).

8. **Stale cos(lat) comparison.** Findings still quote “+0.551 vs +0.552 °C/decade,” which matches the old ANN-based T2M slope, while the current headline T2M is +0.553 (unweighted monthly means). Recompute cos(lat) on the current annual series or label the comparison.

### Headline overreach after the revision

The opening line — 1981–2025 warming of about +0.55 to +0.67 °C/decade, robust across POWER, GSOM (gap disclosed), and GHCN after AR(1)/HAC and Hamed–Rao — is supported (POWER +0.553, GSOM +0.563, GHCN +0.667 °C/decade; all HAC and HR p-values ≪ 0.05, and all three survive primary-family Bonferroni). SWOT is correctly framed as a short operational record, not a climate decline.

What still overreaches, in descending seriousness: the Kherson “step −0.11 m” / MW p presentation; calling EVI_AMJJAS “robust” while also saying it is not a clear headline detection (and citing a tiny all-lag/negative-AR HR p); and using “robust” for two 3.3-year SWOT reaches (already caveated). No remaining climate headline looks like the old “rivers are falling” or MK-only “significant precip/wind” problem.

---


---

## Final check (14 November 2026, Europe/Kiev)

**Verdict: approved.**

The seven re-review fixes are in the files and they check out. I did not modify `$UKRAINE_SAMPLES/`. Reproduction was run in a copy at `team-context/team/reviews/ukraine_samples_rerun/` (the entry point hardcodes `ROOT = Path("$UKRAINE_SAMPLES")`, so only that path was retargeted in the copy).

1. **Kherson is not a confirmed step, and the linear row is gone.** The family is 46 rows, with 0 Kherson/Kakhovka trend rows. Findings and JSON lead with the seasonal qualification: matched April–June step −0.006 m, MW p = 0.687; month FE + step −0.031 m, OLS p = 0.823, HAC lag-3 p = 0.530; April–May year medians 0.1634 / 0.1799 / −0.0405 / 0.0828 m. Headline: “Kherson is not a confirmed Kakhovka step.”

2. **Entry point and reproduction.** Legacy scripts live in `_staging/legacy/` and exit immediately under `__main__` (`SystemExit`, exit code 1) before `main()`. Running `revise_analysis.py` in the copy reproduced `trend_summary.csv`, `swot_kherson_kakhovka_step.json`, `headline_findings.txt`, `swot_findings.txt`, `modis_findings.txt`, `swot_quality_flag_counts.csv`, and the other analysis CSVs **byte-for-byte**.

3. **Hamed–Rao lag=3.** Every CSV row has `mk_hr_lag=3`. Negative residual AR is flagged (`hr_anti_conservative` on 19/46 rows with r<0). Strongly negative r (r < −0.3) appears only on NDVI_AMJJAS and EVI_AMJJAS; EVI_AMJJAS is labelled “HAC significant; Hamed–Rao anti-conservative (negative residual AR); not treated as robust,” not “robust.” `hr_unequal_spacing` is True on the gappy GSOM series (TAVG_1981, TAVG_1961, PRCP_1981), Kharkiv, Uzhhorod, and all seven SWOT trend rows (not on the gap-free 1981–2019 GSOM truncate). Chernihiv: HAC lag-3 p = 0.104, HR p = 0.0564, call “not significant.” Chernivtsi: HAC lag-3 p = 0.0504, HR p = 0.0263, call “method-dependent.”

4. **Monthly “robust” uses HAC lag-3.** Under that rule, only Lower Dniester and Odesa would be “robust at 0.05 (HAC lag-3 and Hamed–Rao)”; both are instead labelled “too short for climate inference.” Other SWOT calls are unchanged if the short-record override is removed.

5. **GSOM wording.** 2013–2019: Askaniia Nova, Lubny, Shepetivka, Uman; 2025: Lubny, Poltava, Shepetivka, Uman; Poltava has no ≥10-month year in 2013–2019; Askaniia Nova ends 2019.

6. **Lower Dniester and Odesa** are labelled too short for climate inference in the CSV and the findings (with the short-record disclaimer on the domain).

7. **cos(lat) and family sizes.** Independent recompute of 1981–2025 T2M: unweighted monthly-spatial OLS **+0.552706** °C/decade (reported +0.553) vs cos(lat)-weighted monthly-spatial OLS **+0.553847** (reported +0.554). Full family size 46 is on every row (`n_tests_in_full_family`). Primary family size 11 is on the 11 primary rows (`n_tests_in_primary_family`); the other 35 rows have NaN there, despite the findings saying both sizes are “stored on each row.”

**Bonferroni/BH for 46 tests** were independently recomputed from `hac1_p`: α = 0.05/46 = 0.00108696 (findings: 0.001087); HAC lag-1 p<0.05 = 32; HR (lag=3) p<0.05 = 34; both = 31; HAC Bonferroni rejects = 23; HAC BH-FDR rejects = 31; 0 disagreements with the CSV. Primary family: 8 Bonferroni and 8 BH rejects, α = 0.004545, 0 disagreements. Every CSV `robust_call` appears in `headline_findings.txt`, and the 46 “Call:” lines match the 46-row table.

No blocking leftover. Cosmetic only: `n_tests_in_primary_family` is NaN off the primary rows; T2M SON is flagged “HR anti-conservative” at residual r = −0.00; the entry point still pickles a run context to `/tmp`.

---
