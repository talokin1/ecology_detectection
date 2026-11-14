# Extra-sources catalog and Ukraine cut-out review

Date: 14 November 2026, Europe/Kiev  
Reviewer: Critique  
Catalog: `team-context/research/extra_sources.md`  
Cut-outs: `$UKRAINE_SAMPLES/extra/` (GISTEMP, HadCRUT5, Berkeley Earth, CRU-CY, GPCC; CHIRPS readme only)  
Methods: `$UKRAINE_SAMPLES/_staging/trend_methods.py`  
Scratch only under `team-context/team/reviews/`. Their files were not modified.

The team lead's rule: global datasets only, with Ukraine as a test cut-out. The catalog follows that rule (E-OBS, ECA&D, UHMI are listed as Low / regional-only). The problem is not Ukraine-only sources; it is treating GHCN-family temperature products as independent confirmation and ranking them as High.

## Verdict: approved with fixes

The catalog is usable: sources are global, sizes and logins are mostly measured not guessed, SPEI v2.6–v2.12 and CHIRPS v2 50°N pitfalls are correctly flagged, and the 1981–2025 temperature slopes from the cut-outs are all robust and sit in the same +0.55 to +0.62 °C/decade band as POWER / MERRA-2 / GHCN. That agreement is **not** independent confirmation. GISTEMP, HadCRUT5, Berkeley Earth and CRU-CY all draw heavily on GHCN/CLIMAT stations; annual correlations with our GHCN and POWER series are 0.92–0.99. GPCC is a useful long gauge-grid for precipitation, but it is not independent of GHCN gauges or of IMERG Final (2000–2024 r=0.981). ERA5 / ERA5-Land remain the highest-value *independent* sources and were correctly listed High — but not downloaded — while four near-duplicate temperature datasets were.

The HadCRUT5 cut-out is only four 5° cells (20–40°E, 45–50°N) and **drops all of Ukraine north of 50°N**. Precipitation 1981–2025 linear trends are not significant and do not agree in sign across products; a coarse-grid precip trend is much less fit for purpose than the temperature one.

## Ranked issues

### 1. Independence is overclaimed; the High list favours near-duplicates of GHCN/CLIMAT over new information

The catalog says priority reflects “independence from data we already have,” then rates GISTEMP, HadCRUT5, Berkeley Earth and CRU all **High**. Overlap wording:

- Berkeley Earth table: “Temperature reconstruction **independent of** GISTEMP, HadCRUT, CRU, POWER, GSOM/GHCN.”
- HadCRUT5 table: “**Independent** blend (CRUTEM5 + HadSST4) vs GISTEMP, Berkeley, CRU, POWER.”
- HadCRUT README: “**Independent** temperature reconstruction vs GISTEMP, Berkeley Earth, CRU TS/CY, and our NASA POWER / GSOM / GHCN samples.”
- GPCC table: “Gauge-based precip **independent of** IMERG, POWER/MERRA-2 and (mostly) CHIRPS.”

These products are different *algorithms* on largely the same station backbone (GHCN-D / GHCN-M / CLIMAT and related collections). POWER is MERRA-2 (r=1.000 on our annual T2M and PRECTOTCORR). IMERG Final is gauge-calibrated (typically against GPCC/GPCP).

Independently recomputed **annual 1981–2025** (Berkeley bbox 1981–2024; Berkeley country 1981–2020; GSOM T has the known 2020–2024 hole). Time is calendar-year means of 12 months (precip as annual totals). Approved methods (HAC lag-1 and Hamed–Rao lag=3 for annual series):

| Series | Window | n | OLS °C/decade | Sen | HAC p | HR p | Call |
|---|---|---|---|---|---|---|---|
| GISTEMP 1200 km bbox | 1981–2025 | 45 | +0.561 | +0.547 | 4.3e-10 | ~0 | robust |
| HadCRUT5 analysis 1×4 (their cut-out) | 1981–2025 | 45 | +0.593 | +0.576 | 5.3e-10 | ~0 | robust |
| HadCRUT5 + 52.5° band | 1981–2025 | 45 | +0.579 | +0.570 | 4.4e-08 | ~0 | robust |
| Berkeley Earth 1° land bbox | 1981–2024 | 44 | +0.559 | +0.540 | 3.7e-07 | 4.0e-08 | robust |
| Berkeley Earth Ukraine *country* | 1981–2020 | 40 | +0.559 | +0.554 | 1.5e-05 | 2.1e-06 | robust |
| CRU-CY Ukraine tmp (absolute) | 1981–2025 | 45 | +0.559 | +0.565 | 4.8e-07 | 3.4e-08 | robust |
| POWER T2M bbox | 1981–2025 | 45 | +0.553 | +0.535 | 1.8e-07 | 5.7e-08 | robust |
| MERRA-2 T2M bbox | 1981–2025 | 45 | +0.554 | +0.536 | 1.5e-07 | 5.7e-08 | robust |
| GHCN-Daily tmean regional (raw) | 1981–2025 | 45 | +0.617 | +0.607 | 1.7e-07 | 5.7e-08 | robust |
| GSOM TAVG long-record (raw; gap 2020–24) | 1981–2019 + 2025 | 40 | +0.492 | +0.456 | 2.5e-05 | 1.9e-05 | robust |

Pearson r among GISTEMP, HadCRUT 1×4, Berkeley bbox, CRU-CY and POWER is **0.976–0.993** (n=44–45). vs GHCN: 0.940–0.955. vs GSOM (n=39–40): 0.922–0.970. That is the expected signature of a shared station network plus a smooth large-scale signal — not four independent detections.

**Truly (or much more) independent of our current stack:** ERA5 / ERA5-Land (different reanalysis; not MERRA-2); AIRS and MODIS LST (already in the samples); GRACE TWS; ESA CCI soil moisture and snow; GIMMS / AVHRR NDVI (pre-MODIS vegetation); CAMS composition. CHIRPS v3 is a useful high-res precip product but is not fully independent of gauges or of ERA5 (the catalog already says this). SPEIbase is built from CRU TS (also already said). TerraClimate is a high-res interpolation of CRU-like station fields plus reanalysis, not a new observing system.

**Fix.** Keep one GHCN-family grid (Berkeley land or CRU TS) as a *consistency* check, not as confirmation. Downgrade GISTEMP / HadCRUT / extra CRU-T / Berkeley from “High / independent” to “medium, same-observing-system cross-check.” Raise or keep High: ERA5, ERA5-Land, CCI SM, CHIRPS v3, GIMMS, GRACE (already held). Rewrite the three “independent” sentences above. Do not add these cut-outs to a confirmation count in findings.

### 2. The HadCRUT5 cut-out excludes all of Ukraine north of 50°N (and most of Crimea)

Confirmed from the official 5° analysis grid: cell centres in the bbox are latitude **47.5° only** (bounds 45–50°N) and longitudes 22.5, 27.5, 32.5, 37.5 (bounds 20–40°E). That is 1×4 = 4 cells, as their README says. The next northern row is centred at 52.5° (bounds 50–55°N). Its centre is 0.1° north of the bbox edge (52.4°N), so their “centres in the box” rule drops it. Kyiv (~50.45°N), Chernihiv, Zhytomyr, Rivne, Sumy and most of the northern oblasts therefore lie *outside* the cut-out. The 42.5° row (bounds 40–45°N) is also dropped, so Crimea (south of 45°N) is mostly excluded. The western cell (20–25°E) extends ~2° west of the bbox into neighbouring countries.

Including the 52.5° band (8 cells) changes the 1981–2025 OLS slope from **+0.593 to +0.579** °C/decade. Adding 42.5° as well (12 cells) gives **+0.550**. Temperature is spatially coherent, so the linear trend is still the same sign and still robust — but this is a poor “Ukraine” window, and the catalog must not treat the 1×4 series as equivalent to the 36-cell GISTEMP or 1° Berkeley means.

**Fix.** Either expand the HadCRUT window to include the 52.5° (and, if Crimea matters, 42.5°) row, or label the series as “central-southern belt 45–50°N only.” Do not present 4 cells as a regional analysis grid.

### 3. Land–ocean blends and 1200 km smoothing: Black Sea SST is in the GISTEMP and HadCRUT means

GISTEMP history attribute: `ILAND=1200, IOCEAN=NCDC/ER5, Base: 1951-1980`. They used `gistemp1200_GHCNv4_ERSSTv5.nc.gz` (1200 km), not the 250 km grid that also exists. The bbox contains **36** 2° cells (latitudes 45, 47, 49, 51 × longitudes 23, 25, …, 39) — not the “about 15–20” a 2° box might suggest at a glance. All 36 cells are filled in every month 1981–2025 (1200 km infills everything). Five of 36 centres sit over or next to the north-west Black Sea / Azov (45°N, 31–39°E). HadCRUT.5 comment: “2m air temperature over land blended with sea water temperature at a depth of 20cm.” The 32.5°E and 37.5°E cells in the 45–50°N band include Black Sea water. Berkeley `Complete_TAVG` is land-only (correct choice); CRU-CY is land-only by construction.

Splitting GISTEMP into those 5 “seaish” cells vs the other 31 changes the 1981–2025 OLS slope only from +0.561 (all) to +0.562 (landish) vs +0.552 (seaish). The *mean anomaly level* does differ (landish +1.136 °C, seaish +0.845, all +1.093, all vs 1951–1980). With 1200 km smoothing the “land” cells are already mixed with marine and far-field station data, so a land-only subset of this file is not a clean land mask.

**Fix.** State that GISTEMP LOTI and HadCRUT analysis include SST in coastal cells and that 1200 km smoothing reaches well outside the bbox (and outside Ukraine). If a tighter land temperature is needed, use Berkeley land, CRU, or GISTEMP 250 km — not 1200 km LOTI.

### 4. Precipitation 1981–2025 linear trends are not fit for a “detection,” and GPCC is not an independent check of IMERG or of our gauges

GPCC v2025 1° bbox annual totals (sum of monthly `precip`; January 1891 values around 43 mm and 1981–2025 annual mean **586 mm**, so these are mm/month, not mm/day — the README left units unconfirmed). CRU-CY Ukraine `pre` ANN is an annual total in mm (1981 ANN 662.5, 1981–2025 mean 548 mm).

| Series | Window | n | OLS mm/decade | Sen | Call |
|---|---|---|---|---|---|
| GPCC v2025 1° bbox | 1981–2025 | 45 | +4.51 | +5.49 | not significant (HAC p=0.54, HR p=0.51) |
| CRU-CY Ukraine pre | 1981–2025 | 45 | −0.88 | +0.95 | not significant (HAC p=0.90) |
| POWER PRECTOTCORR | 1981–2025 | 45 | +14.57 | +15.82 | method-dependent (same as the approved findings) |
| MERRA-2 PRECTOTCORR | 1981–2025 | 45 | +14.71 | +15.61 | method-dependent (r=1.000 with POWER) |
| GHCN-Daily PRCP raw | 1981–2024 | 44 | +16.36 | +18.31 | not significant (thin 2020s: n=2 in 2022–2024) |
| GSOM PRCP anomaly | 1981–2024 | 43 | +15.54 | +8.52 | not significant |
| IMERG | 2000–2024 | 25 | +3.81 | +11.17 | not significant |
| GPCC 2000–2024 | 2000–2024 | 25 | −8.24 | −5.54 | not significant |
| CRU-CY pre 2000–2024 | 2000–2024 | 25 | −12.15 | −12.80 | not significant |

Gauge-grid vs reanalysis slopes do not even agree in sign on 2000–2024. Interannual r (1981–2025): GPCC vs CRU-CY 0.956; GPCC vs POWER 0.888; GPCC vs GHCN raw 0.704; POWER vs GHCN only 0.479. On 2000–2024, GPCC vs IMERG is **0.981**. That is not independence: IMERG Final is gauge-adjusted. GPCC vs our GHCN/GSOM is moderate, not a separate confirmation (shared gauges, but different station sets, interpolation, and domains).

Precipitation has a much shorter spatial correlation length than temperature. A 1° bbox mean that includes neighbouring land, and a 5° product that we did not use for precip, cannot resolve oblast-scale rainfall trends. Our GSOM PRCP counts fall to 3 then 1 stations in 2022–2025 (TAVG long-record GSOM is 4 after 2013, and missing 2020–2024). GPCC v2025 merges Full Data with a Monitoring extension; recent gauge density in this box was **not verifiable** here because the official chunks were discarded after the mean was written (no `gauge` count column in the CSV).

**Fix.** Confirm GPCC units as mm/month in the README. Do not call GPCC independent of IMERG or of GHCN. Do not headline a 1981–2025 precip slope from any of these series. If a gauge-grid is kept, retain monthly gauge counts in the cut-out.

### 5. Country extracts are not the bbox, and the Berkeley country files are stale

CRU-CY and the Berkeley `ukraine-TAVG/TMAX/TMIN-Trend.txt` files are country integrals, not the 22.1–40.2°E, 44.4–52.4°N bbox used for POWER, GISTEMP, HadCRUT, Berkeley’s 1° grid, and GPCC. That is the right thing for a “Ukraine” number, but it is a different domain (~0.6 million km² vs a bbox of ~1.19 million km², about twice Ukraine, with neighbouring land and the north-west Black Sea).

Berkeley country header: latitude 45.21–52.37°N, longitude 22.13–40.16°E, area **553,101 km²**, “approximately 212” stations. Southern Crimea is around 44.4–45.2°N, so this polygon appears to exclude most of Crimea; 553,101 km² is also well below the commonly cited ~0.60 million km² for Ukraine. CRU-CY is labelled `Country = Ukraine` and uses area-weighted means of CRU TS; the bundled `Read_Me_CRU_CY.txt` does **not** say whether Crimea or a post-2014 boundary is in the mask. I could not verify the CRU-CY polygon.

The country series are not current with the grid. Last months in the downloaded files: TAVG **2020-12**, TMAX **2019-06**, TMIN **2018-12**. The 1° bbox grid goes through 2024-12. The catalog line “country series follow the field; grid extract ends 2024-12” is misleading.

**Fix.** State domain (country vs bbox) on every comparison. Record the Berkeley country end dates. Re-fetch the country files or stop using them after 2020. Document the CRU-CY Ukraine mask (Crimea in or out).

### 6. Baselines and absolute vs anomaly are mostly handled, but must stay visible in any joint plot

Verified: GISTEMP 1951–1980 regional mean ≈ 0; HadCRUT 1961–1990 mean −0.005 °C; Berkeley land 1951–1980 ≈ 0. CRU-CY tmp is **absolute °C** (1981–2025 mean 9.23 °C), not an anomaly; ANN is rounded to 0.1 °C (max |ANN − mean of 12 months| = 0.058 °C). HadCRUT NetCDF units are K for the anomaly (same size as °C); they named the column `tas_anomaly_C`. They downloaded the infilled **analysis** ensemble mean, not the non-infilled product (the README mentions the latter; it was not cut). Early Berkeley months can be missing; 1981–2020 country and 1981–2024 bbox have no missing months.

**Fix.** Never overlay CRU absolute temperature on a 1951–1980 or 1961–1990 anomaly axis without converting. If HadCRUT is used in data-sparse early years, compare analysis vs non-infilled.

### 7. Ranking and “next downloads” should follow independence and new variables, not ease of a 25 MB grid

What they already got right: ERA5 / ERA5-Land as High; CHIRPS v3 not v2; SPEI not analysis-ready until v2.13; TerraClimate / PSL / digital.csic blockers recorded; no Ukraine-only primary source; ODbL share-alike on CRU flagged. What is off: four GHCN-family temperature grids are High and were downloaded, while ERA5 (no CDS key, but ARCO Zarr is described), CCI SM (only Medium), and CHIRPS v3 (High but no raster) were not. GitHub helper repos as a Medium “source” does not belong in the same table as data.

**Fix.** Reorder: (1) ERA5 monthly / ERA5-Land, (2) CHIRPS v3 COG subset, (3) CCI SM, (4) one station-grid T and GPCC/CRU precip as consistency checks, (5) SPEI v2.13 and TerraClimate when servers recover. Treat GISTEMP 1200 km and HadCRUT 5° as optional context, not core evidence.

## Coarse-grid counts (cut-outs)

| Product | Grid | Cells whose centres fall in the bbox | Land / ocean | Share outside Ukraine |
|---|---|---|---|---|
| GISTEMP 1200 km | 2° | **36** (4×9). All filled. | Land–ocean blend; 5/36 centres are Black Sea / Azov-ish. 1200 km smoothing mixes the rest. | The bbox is ~2× Ukraine; smoothing reaches still further. Northern 52–52.4°N strip is outside the 51° cell (50–52°). |
| HadCRUT5 analysis | 5° | **4** (1×4), 20–40°E, 45–50°N only | Blend of land air and SST | Drops all land north of 50°N and most of Crimea; western cell includes 20–22.1°E neighbours. |
| Berkeley Earth land | 1° | Header: nlat=8, nlon=18 (144 centres). Official grid was discarded after cutting, so I could not recount valid land cells per month. | Land-only (ocean is missing) | Neighbouring land in the bbox remains. Country series are a different, smaller domain (553,101 km²). |
| GPCC v2025 | 1° | nlat=8, nlon=18 (same centre rule). 1891–2026-08, 1628 months; 1981–2025 complete (540/540). | Land product; README calls it “land cells.” Gauge counts not kept. | Same bbox over-coverage as other 1° cuts. |
| CRU-CY | 0.5° parent, country mean | Not a bbox cut-out | Land | Country mask, Crimea not documented. |

A 1981–2025 linear trend is still reasonable **for temperature** (large-scale coherence; all series robust and within ~0.06 °C/decade of POWER except GHCN +0.617 and GSOM +0.492 with a gap). It is **not** a solid detection tool **for precipitation** (issue 4).

## What was already done well

- Global-only rule, with regional datasets parked at Low.
- SPEI v2.6–v2.12 PET unit-conversion bug and “do not use until v2.13” warning.
- CHIRPS v2 50°N cutoff would miss most of Ukraine, including Kyiv.
- GPCC product-page size quotes vs actual 5-year 1° chunk sizes, called out.
- CRU TS global files measured (~426 MB tmp, ~665 MB pre gzip) and not pulled in full.
- CDS / CEDA / IRI login blockers and TerraClimate HTTP 500 recorded honestly.
- Cosine-latitude means; 2004-style complete-year annualisation is possible from the monthly CSVs (no missing months in 1981–2025 for GISTEMP, HadCRUT, GPCC).
- Baselines in READMEs are generally right (GISTEMP 1951–1980, HadCRUT 1961–1990, Berkeley 1951–1980).

## What I could not verify

- GPCC gauge counts per cell in recent years (chunks discarded; no count column in the CSV).
- The exact CRU-CY “Ukraine” polygon (Crimea / post-2014).
- Berkeley Earth licence text on the live landing page (catalog says CC BY-NC, “confirm on the landing page”).
- GISTEMP 250 km vs 1200 km on this bbox (250 km file not downloaded).
- HadCRUT5 non-infilled cut-out (not downloaded).
- Whether Ukraine is in GRDC-Caravan’s 25 countries (catalog already says unverified).
- Full licence text for GPCC Terms of Use and Copernicus CDS (catalog already marks these unread).
- I did not re-download any official file; grid geometry was taken from the kept GISTEMP and HadCRUT NetCDFs and from CSV headers.

---

## Fixes + CHIRPS v3 + CCI SM (14 November 2026, Europe/Kiev)

Recomputed only what was needed: HadCRUT overlap weights vs the official analysis NetCDF, CHIRPS NetCDF units/coverage vs the CSV, and 1981–2025 (complete years) trends under `trend_methods.py`. Existing POWER / IMERG / GPCC annual series were reused. Their files were not modified. No full pipelines were rerun.

### Verdict: approved with minor fixes

The reported extra-sources fixes check out. There is no blocking processing error. HadCRUT now uses 15 overlap cells and GISTEMP 50, both flagged land-ocean; weights are intersection area on the sphere (Δlon × Δsin(lat), equivalent to overlap area × cos(lat)); the HadCRUT CSV matches the official NetCDF (max |CSV − recompute| = 5.0×10⁻⁷ °C over 2121 months). Berkeley 1° is documented as the primary consistency check and ends 2024-12. CRU-CY anomalies use stated month-wise 1961–1990 and 1951–1980 baselines (max residual 3.3×10⁻⁷ °C). Independence overclaims for the GHCN-family temperature products and for GPCC vs IMERG are gone.

CHIRPS v3 (1981-01–2026-10) is correctly cut and annualised once incomplete 2026 is dropped. The remaining should-fix is that the CHIRPS independence caveat mentions only ERA5 gap-fill, not the official station inputs (GTS, GHCN, GPCC normals). CCI SM is partial as stated; nothing in the assembled 1978-11–1991-12 series is wrong. No CHIRPS or CCI trend was published in the catalog or READMEs to check.

### Ranked items

### 1. CHIRPS v3 is not fully independent of GPCC / GHCN — caveat covers only ERA5 (should-fix)

Catalog and `chirps_v3/README.md` say v3 “fills some gaps with 0.25° ERA5, so it is not fully independent of ERA5,” and still rank CHIRPS High as “(much more) independent of our existing POWER / MERRA-2 / GHCN / IMERG stack.” The official `README-CHIRPSv3.0.txt` kept with the cut-out also lists operational station inputs: WMO GTS, NOAA GHCN, SSOD, CONAGUA; “about 80,000 new station normals from the Global Precipitation Climatology Centre (GPCC)” incorporated into CHPclim2; “more than 90 sources of station data”; plus a switch to gauge-undercatch-corrected stations (v3 wetter than v2). That is a shared-observing-system overlap with GPCC and GHCN, not only with ERA5. Do not add CHIRPS as independent confirmation of GPCC or GHCN precip. IR + high resolution still make it useful, and it is less tightly tied to IMERG than GPCC is (2000–2024 r = 0.830 vs GPCC–IMERG r = 0.981 from the earlier review).

### 2. HadCRUT’s 15-cell *count* and weights are correct; the cell *values* still cover far more than Ukraine (documented, not a processing error)

Fifteen 5° cells is the right overlap set for bbox 22.1–40.2°E × 44.4–52.4°N: latitudes 42.5 / 47.5 / 52.5 × longitudes 22.5 / 27.5 / 32.5 / 37.5 / 42.5 (3 × 5). Intersection-area weights in `hadcrut5_overlap_cells.csv` match an independent Δlon × Δsin(lat) recompute (max |area| = 4.4×10⁻⁷). Weight shares: 47.5°N row 63.6%, 52.5°N 28.3%, 42.5°N 8.0%; longitude 22.5°E strip (cell 20–25°E) 16.0%; 42.5°E sliver 1.1%; the old four centres-in-box cells 62.9%; one seaish cell (42.5°N, 32.5°E, land_frac = 0.199) 2.2% of weight, so landish (14 cells) is 97.8%. CSV `tas_anomaly_C` matches the official ensemble-mean NetCDF under those weights. 1981–2025 (n = 45, complete years) approved-method trends, all robust at 0.05: overlap 15-cell OLS +0.579 / Sen +0.564 °C/decade; landish +0.582 / +0.568; old 4-cell audit +0.593 / +0.576. GISTEMP 50 overlap cells (5 × 10) also check: 1981–2025 OLS +0.560 vs old 36-centre +0.561 °C/decade.

Overlap weights only scale each *value* by the bbox intersection; they do not crop the 5° cell itself. The 15 values still average land and SST over 20–45°E, 40–55°N. That is inherent to a 5° land–ocean blend and is already caveated. Keep HadCRUT as coarse context; Berkeley 1° remains the right primary consistency check.

### 3. CHIRPS v3 processing is sound; 1981–2025 precip is not a detection (evidence, not a defect)

Units are monthly totals, not mm/day: no `scale_factor`; NetCDF `precip` units attribute is `mm` (CSV/README say mm/month); fill = −9999; January 1981 = 77.33 mm; 1981–2025 mean of complete-year sums = 686.69 mm/year (wetter than GPCC 586.4 and POWER 590.4, consistent with the official undercatch correction; 2000–2024 CHIRPS mean 698.2 vs IMERG 695.4). Coverage north of 50°N is complete in the files: 48 latitudes, valid fraction = 1.0 in every one of the 550 months, no NaN or fill rows. The 2,828 invalid pixels (55,092 / 57,920 valid, constant every month — a static mask) sit in the south (invalid fraction 0.453 at 44.425°N; 0.308 in lat ≤ 46.5°N, lon ≥ 30°E), i.e. Black Sea / Azov, not a formal land-sea mask variable. 2026 is January–October only and was correctly excludable from annual trends (CSV and NetCDF dates align; all 550 monthly means match to 5.0×10⁻⁷ mm).

Approved-method annual trends, complete years only:

- 1981–2025 (n = 45): CHIRPS OLS +1.72 / Sen +4.94 mm/decade, HAC p = 0.883, HR p = 0.688, r = −0.127, not significant. GPCC +4.51 / +5.49, not significant. POWER +14.57 / +15.82, method-dependent (same as the earlier review).
- 2000–2024 (n = 25): CHIRPS −1.22 / −1.64, not significant; GPCC −8.24 / −5.54, not significant (r = −0.359, cannot confirm via HR); IMERG +3.81 / +11.17, not significant; POWER +13.75 / +10.12, not significant.

Correlations of annual totals: CHIRPS vs GPCC r = 0.851 (1981–2025) and 0.827 (2000–2024); vs POWER 0.807 and 0.765; vs MERRA-2 0.809 (1981–2025); vs IMERG 0.830 (2000–2024).

### 4. Nits (one line each)

CRU baselines, Berkeley ending 2024-12, and removal of “independent confirmation” wording for the GHCN-family T products / GPCC vs IMERG were verified as reported. CCI SM COMBINED v09.2 monthly file is 1978-11–1991-12 (158 months, sm in m³ m⁻³, winter coverage low as documented); `_years/cci_sm_1992.nc` already holds a complete January–December 1992 (12 months) that has not been assembled — a resume leftover, not an error in the published series. CHIRPS NetCDF units attribute is `mm` rather than `mm/month` (values are monthly totals).

### What I could not verify

- I did not re-download official CHIRPS COGs or CCI daily files; coverage and units were taken from the kept NetCDF / CSV / official readme.
- No trend was computed for CCI SM (partial record; none requested).
- I did not independently recount GISTEMP 50-cell overlap means from the official 1200 km grid this pass (cell table is 5 × 10 as claimed; trends were taken from the new CSV).
