# Preprocessing pipeline v1.4 - QC report

Generated 2026-11-14 14:15 (Europe/Kiev). Regions run: ukraine_bbox, ukraine_mask, ukraine_mask_no_crimea.

Primary significance: repo Mann-Kendall with the Yue-Wang AR(1) correction (ADR-003). HAC and Hamed-Rao lag-3 are sensitivity columns.

Run: `cd team-context/data/pipeline && OMP_NUM_THREADS=2 nice -n 10 python run_pipeline.py --region ukraine_bbox ukraine_mask ukraine_mask_no_crimea && python smoke_test.py`

## Smoke test (blocking, region=ukraine_bbox, tolerance ±0.005)

Overall: **PASS** (run 2026-11-14T14:15:21)

| check | blocking | reference | upstream_exact | reproduced | diff | n | pass |
|---|---|---|---|---|---|---|---|
| POWER T2M annual 1981-2025 OLS (°C/decade) | True | +0.5530 | +0.5527 | +0.5526 | -0.0004 | 45 | True |
| HadCRUT5 overlap annual 1981-2025 OLS (°C/decade) | True | +0.5790 |  | +0.5793 | +0.0003 | 45 | True |
| GRACE production tidy series, overlap weights (cm/decade) | True | -11.2420 | -11.2420 | -11.2420 | +0.0000 | 235 | True |
| GRACE legacy cell-centre selection (cm/decade) [legacy, non-blocking] | False | -11.2220 | -11.2221 | -11.2221 | -0.0001 | 235 | True |

Non-blocking rows do not affect Overall. Change 14 Nov 2026 (decided by the team lead via Thinker): the blocking GRACE check is the production overlap-weighted series vs -11.242; the old cell-centre check (-11.222) is kept as a non-blocking legacy check.

## Crimea

Natural Earth 5.1.1 (10m admin-0), checked point-in-polygon, not assumed:

| place | default_UKR | default_RUS | ukr_pov_UKR |
|---|---|---|---|
| Simferopol | False | True | True |
| Sevastopol | False | True | True |
| Kerch | False | True | True |
| Kyiv | True | False | True |
| Donetsk | True | False | True |
| Luhansk | True | False | True |


- **Default file `ne_10m_admin_0_countries` (de-facto view) assigns Crimea to RUS.** Its UKR polygon is
  570,178 km², bounds [22.133, 45.214, 40.16, 52.369] (lat min 45.21 = the Berkeley Earth country
  polygon, 553,101 km²).
- **Ukraine point-of-view file `ne_10m_admin_0_countries_ukr` assigns Crimea to UKR**: 597,211 km²,
  bounds [22.133, 44.381, 40.16, 52.369]. The difference is 27,033 km² with bounds [32.482, 44.381, 36.638, 46.218]
  (Crimea + Sevastopol only; Donetsk/Luhansk are UKR in both files).
- **`ukraine_mask` (POV file, internationally recognised borders, Crimea INCLUDED) is the PRIMARY mask.**
  `ukraine_mask_no_crimea` (default file, Crimea excluded) is a SENSITIVITY variant only.
- `ukraine_bbox` (44.4-52.4N) contains essentially all of Crimea (its southern tip reaches 44.38N).
- Consistency: every gridded source (POWER, GRACE, HadCRUT5, GISTEMP, Berkeley 1°, CHIRPS, CCI SM, and now MERRA-2,
  GLDAS, IMERG, AIRS, MODIS, GPCC from global files) uses the SAME
  region polygon/weights per run, and stations are selected by the same polygon. Producer country series do not:
  Berkeley country file EXCLUDES Crimea (flag `crimea_excluded;mask_mismatch_vs_region` in `ukraine_mask`);
  CRU-CY is undocumented (`crimea_undocumented`). Don't compare those 1:1 with masked series.
- Stations in Crimea: GHCN (downloaded 28): SIMFEROPOL, KERCH, YALTA; GSOM: 20 of 204 UP stations.
  They are in `ukraine_mask` and `ukraine_bbox`, and would drop out of `ukraine_mask_no_crimea`.
- Coarse products: one HadCRUT 5° cell / GRACE mascons straddle Crimea and the Black Sea; overlap weights only.

## Units and conversions (single targets, config/variables.yaml)

| source | variable | raw_unit | conversion | unit | annual | group |
|---|---|---|---|---|---|---|
| nasa_power | T2M | °C | none | °C | mean | MERRA-2 |
| nasa_power | T2M_MAX | °C | none | °C | mean | MERRA-2 |
| nasa_power | T2M_MIN | °C | none | °C | mean | MERRA-2 |
| nasa_power | PRECTOTCORR | mm/day | per_day_to_month | mm/month | sum | MERRA-2 |
| nasa_power | QV2M | g/kg | none | g/kg | mean | MERRA-2 |
| nasa_power | WS10M | m/s | none | m/s | mean | MERRA-2 |
| nasa_power | ALLSKY_SFC_SW_DWN | kWh/m²/day | none | kWh/m²/day | mean | CERES |
| merra2 | T2M | K | K_to_C | °C | mean | MERRA-2 |
| merra2 | QV2M | kg/kg | scale | g/kg | mean | MERRA-2 |
| merra2 | SLP | Pa | scale | hPa | mean | MERRA-2 |
| merra2 | PRECTOTCORR | kg m-2 s-1 | per_s_to_month | mm/month | sum | MERRA-2 |
| merra2 | PRECTOT | kg m-2 s-1 | per_s_to_month | mm/month | sum | MERRA-2 |
| merra2 | U10M | m/s | none | m/s | mean | MERRA-2 |
| merra2 | V10M | m/s | none | m/s | mean | MERRA-2 |
| merra2 | WS10M_from_mean_UV | m/s | none | m/s | mean | MERRA-2 |
| merra2 | T2MMAX | K | K_to_C | °C | mean | MERRA-2 |
| merra2 | T2MMIN | K | K_to_C | °C | mean | MERRA-2 |
| merra2 | DTR | K | none | °C | mean | MERRA-2 |
| gldas20 | SoilMoi0_10cm_inst | kg/m² | none | kg/m² (≈mm) | mean | GLDAS-2.0 (Princeton forcing) |
| gldas20 | RootMoist_inst | kg/m² | none | kg/m² (≈mm) | mean | GLDAS-2.0 (Princeton forcing) |
| gldas20 | SWE_inst | kg/m² | none | kg/m² (≈mm) | mean | GLDAS-2.0 (Princeton forcing) |
| gldas20 | Tair_f_inst | K | K_to_C | °C | mean | GLDAS-2.0 (Princeton forcing) |
| gldas20 | Evap_tavg | kg m-2 s-1 | per_s_to_month | mm/month | sum | GLDAS-2.0 (Princeton forcing) |
| gldas20 | Qs_acc | kg m-2 per 3h | acc3h_to_month | mm/month | sum | GLDAS-2.0 (Princeton forcing) |
| gldas20 | Qsb_acc | kg m-2 per 3h | acc3h_to_month | mm/month | sum | GLDAS-2.0 (Princeton forcing) |
| gldas20 | precip_total | kg m-2 s-1 | per_s_to_month | mm/month | sum | GLDAS-2.0 (Princeton forcing) |
| gldas20 | snowfall | kg m-2 s-1 | per_s_to_month | mm/month | sum | GLDAS-2.0 (Princeton forcing) |
| gldas20 | rainfall_liquid | kg m-2 s-1 | per_s_to_month | mm/month | sum | GLDAS-2.0 (Princeton forcing) |
| gldas21 | SoilMoi0_10cm_inst | kg/m² | none | kg/m² (≈mm) | mean | GLDAS-2.1 (GDAS/GPCP forcing) |
| gldas21 | RootMoist_inst | kg/m² | none | kg/m² (≈mm) | mean | GLDAS-2.1 (GDAS/GPCP forcing) |
| gldas21 | SWE_inst | kg/m² | none | kg/m² (≈mm) | mean | GLDAS-2.1 (GDAS/GPCP forcing) |
| gldas21 | Tair_f_inst | K | K_to_C | °C | mean | GLDAS-2.1 (GDAS/GPCP forcing) |
| gldas21 | Evap_tavg | kg m-2 s-1 | per_s_to_month | mm/month | sum | GLDAS-2.1 (GDAS/GPCP forcing) |
| gldas21 | Qs_acc | kg m-2 per 3h | acc3h_to_month | mm/month | sum | GLDAS-2.1 (GDAS/GPCP forcing) |
| gldas21 | Qsb_acc | kg m-2 per 3h | acc3h_to_month | mm/month | sum | GLDAS-2.1 (GDAS/GPCP forcing) |
| gldas21 | precip_total | kg m-2 s-1 | per_s_to_month | mm/month | sum | GLDAS-2.1 (GDAS/GPCP forcing) |
| gldas21 | snowfall | kg m-2 s-1 | per_s_to_month | mm/month | sum | GLDAS-2.1 (GDAS/GPCP forcing) |
| gldas21 | rainfall_liquid | kg m-2 s-1 | per_s_to_month | mm/month | sum | GLDAS-2.1 (GDAS/GPCP forcing) |
| gpm_imerg | precipitation | mm/hr | per_hour_to_month | mm/month | sum | IMERG (gauge-calibrated with GPCC) |
| airs | SurfAirTemp | K | K_to_C | °C | mean | AIRS |
| airs | TotH2OVap | kg/m² | none | kg/m² (≈mm) | mean | AIRS |
| modis | LST_Day | K | K_to_C | °C | mean | MODIS Terra |
| modis | LST_Night | K | K_to_C | °C | mean | MODIS Terra |
| modis | NDVI | index | none | index | mean | MODIS Terra |
| modis | EVI | index | none | index | mean | MODIS Terra |
| modis | LST_Day_clear_days | days | none | days | mean | MODIS Terra |
| modis | LST_Night_clear_days | days | none | days | mean | MODIS Terra |
| omi | ColumnAmountNO2Trop | molec/cm² | none | molec/cm² | mean | OMI |
| omi | ColumnAmountNO2TropCloudScreened | molec/cm² | none | molec/cm² | mean | OMI |
| grace | TWS | cm | none | cm EWH anomaly | mean | GRACE |
| hadcrut5 | tas_anomaly | K anomaly | none | °C anomaly (1961-1990) | mean | station family (GHCN/CLIMAT) |
| gistemp | tas_anomaly | K anomaly | none | °C anomaly (1951-1980) | mean | station family (GHCN/CLIMAT) |
| berkeley | tas_anomaly | °C anomaly | none | °C anomaly (1951-1980) | mean | station family (GHCN/CLIMAT) |
| berkeley_country | tas_anomaly | °C anomaly | none | °C anomaly (1951-1980) | mean | station family (GHCN/CLIMAT) |
| cru_cy | tmp | °C | none | °C | mean | station family (GHCN/CLIMAT) |
| cru_cy | tmp_anom | °C anomaly | none | °C anomaly (1961-1990) | mean | station family (GHCN/CLIMAT) |
| cru_cy | tmn | °C | none | °C | mean | station family (GHCN/CLIMAT) |
| cru_cy | tmx | °C | none | °C | mean | station family (GHCN/CLIMAT) |
| cru_cy | dtr | °C | none | °C | mean | station family (GHCN/CLIMAT) |
| cru_cy | pre | mm/month | none | mm/month | sum | station family (GHCN/CLIMAT) |
| cru_cy | pet | mm/day | per_day_to_month | mm/month | sum | station family (GHCN/CLIMAT) |
| cru_cy | vap | hPa | none | hPa | mean | station family (GHCN/CLIMAT) |
| cru_cy | wet | days | none | days | sum | station family (GHCN/CLIMAT) |
| gpcc | precip | mm/month | none | mm/month | sum | GPCC gauges (shares gauges with GHCN; calibrates IMERG) |
| chirps | precip | mm (monthly total) | none | mm/month | sum | CHIRPS (uses GTS/GHCN/GPCC normals + ERA5 fill) |
| cci_sm | sm | m³/m³ | none | m³/m³ | mean | ESA CCI SM |
| ghcn | TAVG | tenths °C | tenths | °C | mean | station family (GHCN/CLIMAT) |
| ghcn | TMAX | tenths °C | tenths | °C | mean | station family (GHCN/CLIMAT) |
| ghcn | TMIN | tenths °C | tenths | °C | mean | station family (GHCN/CLIMAT) |
| ghcn | PRCP | tenths mm | tenths | mm/month | sum | station family (GHCN/CLIMAT) |
| gsom | TAVG | °C | none | °C | mean | station family (GHCN/CLIMAT) |
| gsom | TMAX | °C | none | °C | mean | station family (GHCN/CLIMAT) |
| gsom | TMIN | °C | none | °C | mean | station family (GHCN/CLIMAT) |
| gsom | PRCP | mm | none | mm/month | sum | station family (GHCN/CLIMAT) |
| swot | wse | m | none | m | mean | SWOT |
| derived | DTR | °C | none | °C | mean | MERRA-2 |

Conversion keys: per_s_to_month = x86400 x days; per_day_to_month = x days; per_hour_to_month = x24 x days; acc3h_to_month = x8 x days (GLDAS 3-hourly accumulations); tenths = x0.1; K_to_C = -273.15.

## Verification: global-file cuts vs old bbox extracts (ukraine_bbox)

`verify_global_vs_bbox.py`. diff = global - old on MONTHLY values (unit column); trends = OLS on 12/12 annual values per decade (trend_unit; precip/flux annual totals) over common complete years (AIRS to 2024).

| source | variable | unit | n_common | first | last | corr | mean_diff | max_abs_diff | rel_mean_diff_pct | trend_unit | trend_new | trend_old | trend_diff | trend_years |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| merra2 | PRECTOT | mm/month | 561 | 1980-01 | 2026-09 | 0.9995 | 0.3006 | 2.8232 | 0.5368 | mm/yr per decade | 0.6867 | 0.3764 | 0.3103 | 1980-2025 |
| merra2 | PRECTOTCORR | mm/month | 561 | 1980-01 | 2026-09 | 0.9994 | 0.0312 | 2.5801 | 0.0628 | mm/yr per decade | 6.5490 | 6.3760 | 0.1730 | 1980-2025 |
| merra2 | QV2M | g/kg | 561 | 1980-01 | 2026-09 | 1.0000 | -0.0311 | 0.0791 | -0.5133 | g/kg per decade | 0.1554 | 0.1569 | -0.0015 | 1980-2025 |
| merra2 | SLP | hPa | 561 | 1980-01 | 2026-09 | 0.9999 | -0.0040 | 0.1755 | -0.0004 | hPa per decade | -0.1139 | -0.1165 | 0.0025 | 1980-2025 |
| merra2 | T2M | °C | 561 | 1980-01 | 2026-09 | 1.0000 | -0.1151 | 0.3139 | -1.0791 | °C per decade | 0.5786 | 0.5805 | -0.0019 | 1980-2025 |
| gldas20 | Evap_tavg | mm/month | 804 | 1948-01 | 2014-12 | 1.0000 | 0.0377 | 0.3668 | 0.0887 | mm/yr per decade | 5.5481 | 5.5253 | 0.0229 | 1948-2014 |
| gldas20 | Qs_acc | mm/month | 804 | 1948-01 | 2014-12 | 0.9999 | -0.0201 | 0.3612 | -1.6108 | mm/yr per decade | -0.2858 | -0.2970 | 0.0112 | 1948-2014 |
| gldas20 | Qsb_acc | mm/month | 804 | 1948-01 | 2014-12 | 0.9998 | -0.0141 | 0.4804 | -0.3219 | mm/yr per decade | 1.7510 | 1.7652 | -0.0142 | 1948-2014 |
| gldas20 | RootMoist_inst | kg/m² (≈mm) | 804 | 1948-01 | 2014-12 | 1.0000 | -0.5551 | 1.8799 | -0.2115 | kg/m² (≈mm) per decade | 2.4549 | 2.4559 | -0.0009 | 1948-2014 |
| gldas20 | SWE_inst | kg/m² (≈mm) | 804 | 1948-01 | 2014-12 | 1.0000 | -0.0519 | 0.7962 | -0.9595 | kg/m² (≈mm) per decade | -0.1737 | -0.1747 | 0.0010 | 1948-2014 |
| gldas20 | SoilMoi0_10cm_inst | kg/m² (≈mm) | 804 | 1948-01 | 2014-12 | 1.0000 | -0.0191 | 0.1398 | -0.0735 | kg/m² (≈mm) per decade | 0.0865 | 0.0854 | 0.0012 | 1948-2014 |
| gldas20 | Tair_f_inst | °C | 804 | 1948-01 | 2014-12 | 1.0000 | 0.0369 | 0.1006 | 0.3620 | °C per decade | 0.2110 | 0.2119 | -0.0009 | 1948-2014 |
| gldas21 | Evap_tavg | mm/month | 319 | 2000-01 | 2026-07 | 1.0000 | 0.0441 | 0.5264 | 0.0845 | mm/yr per decade | 15.5818 | 16.0203 | -0.4385 | 2000-2025 |
| gldas21 | Qs_acc | mm/month | 319 | 2000-01 | 2026-07 | 0.9999 | -0.0223 | 0.4218 | -1.1473 | mm/yr per decade | -10.3038 | -10.4023 | 0.0985 | 2000-2025 |
| gldas21 | Qsb_acc | mm/month | 319 | 2000-01 | 2026-07 | 0.9999 | -0.0993 | 1.0760 | -1.1857 | mm/yr per decade | -11.1074 | -10.9713 | -0.1361 | 2000-2025 |
| gldas21 | RootMoist_inst | kg/m² (≈mm) | 319 | 2000-01 | 2026-07 | 1.0000 | -0.6775 | 1.6414 | -0.2524 | kg/m² (≈mm) per decade | -14.4160 | -14.3820 | -0.0341 | 2000-2025 |
| gldas21 | SWE_inst | kg/m² (≈mm) | 319 | 2000-01 | 2026-07 | 1.0000 | -0.1676 | 1.4833 | -1.9672 | kg/m² (≈mm) per decade | -2.5827 | -2.6113 | 0.0286 | 2000-2025 |
| gldas21 | SoilMoi0_10cm_inst | kg/m² (≈mm) | 319 | 2000-01 | 2026-07 | 1.0000 | -0.0269 | 0.1760 | -0.1035 | kg/m² (≈mm) per decade | -1.2617 | -1.2604 | -0.0012 | 2000-2025 |
| gldas21 | Tair_f_inst | °C | 319 | 2000-01 | 2026-07 | 1.0000 | 0.0395 | 0.0960 | 0.3737 | °C per decade | 0.9266 | 0.9223 | 0.0042 | 2000-2025 |
| gpm_imerg | precipitation | mm/month | 309 | 2000-01 | 2025-09 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | mm/yr per decade | 3.8066 | 3.8066 | 0.0000 | 2000-2024 |
| airs | SurfAirTemp | °C | 290 | 2002-09 | 2026-10 | 0.9999 | -0.2494 | 0.6761 | -2.2292 | °C per decade | 0.8194 | 0.8154 | 0.0041 | 2003-2024 |
| airs | TotH2OVap | kg/m² (≈mm) | 290 | 2002-09 | 2026-10 | 0.9999 | -0.1614 | 0.4203 | -1.0027 | kg/m² (≈mm) per decade | 0.1468 | 0.1614 | -0.0147 | 2003-2024 |
| modis | EVI | index | 321 | 2000-02 | 2026-10 | 0.9891 | 0.0075 | 0.1152 | 2.7696 | index per decade | 0.0065 | 0.0076 | -0.0011 | 2001-2025 |
| modis | LST_Day | °C | 321 | 2000-02 | 2026-10 | 1.0000 | 0.0767 | 0.2508 | 0.4689 | °C per decade | 0.8214 | 0.8226 | -0.0012 | 2001-2025 |
| modis | LST_Night | °C | 321 | 2000-02 | 2026-10 | 1.0000 | 0.0434 | 0.1556 | 0.4903 | °C per decade | 0.8686 | 0.8690 | -0.0004 | 2001-2025 |
| modis | NDVI | index | 321 | 2000-02 | 2026-10 | 0.9567 | 0.0217 | 0.2654 | 4.4227 | index per decade | 0.0046 | 0.0077 | -0.0032 | 2001-2025 |
| gpcc | precip | mm/month | 1628 | 1891-01 | 2026-08 | 0.9983 | -0.1636 | 5.2608 | -0.3410 | mm/yr per decade | 3.2836 | 3.2263 | 0.0573 | 1891-2025 |
| chirps | precip | mm/month | 549 | 1981-01 | 2026-09 | 0.9997 | -0.0143 | 15.0676 | -0.0251 | mm/yr per decade | 1.8321 | 1.7178 | 0.1142 | 1981-2025 |

Why they differ:
- Cell-centre vs overlap: the extracts selected cells whose CENTRE is inside 22.1-40.2E / 44.4-52.4N; the new cut
  weights every intersecting cell by its overlap fraction x spherical area (MERRA-2 0.5x0.625, GPCC/AIRS 1 deg, GLDAS
  0.25 deg). This explains MERRA-2 T2M -0.12 °C (extra southern sea/coast row), GPCC max 5 mm, GLDAS 0.2-2 %.
- MODIS: extract = UNWEIGHTED, unQC'd pixel mean; new = area-weighted AND per-pixel QC'd (since 14 Nov 2026). LST
  still matches (corr 1.000, trend diff <=0.0012 °C/decade). NDVI/EVI corr drops to 0.957/0.989 because QC removes
  snow/cloud pixels in winter (see "MODIS QC"); before QC the area-weighted cut matched at corr 1.000 (diff <=0.0047).
- AIRS: extract = mean of the ascending and descending bbox means; new = per-cell nanmean(A, D) then weighted
  (mean diff -0.25 °C, trend 2003-2024 +0.819 vs +0.815).
- IMERG: 0.1 deg cell edges coincide with the bbox edges so both methods select identical cells: exact match.
- Units: all precip/flux in mm/month via the same variables.yaml conversions; no unit mismatches found.
- Version: CHIRPS differs only from 2025-10 on (max 15.1 mm in 2026-02; <0.33 mm before) = preliminary months
  re-processed between the two downloads; it also moves the CHIRPS 1981-2025 trend by +0.11 mm/yr per decade.

## MODIS QC (per-pixel, before area averaging)

Rules (`ukpipe/loaders/global_grids.py`, `_vi_good` / `_lst_good`):
- MOD13C2 NDVI/EVI: keep a pixel if `CMG_0_05_Deg_Monthly_pixel_reliability` is 0 (good) or 1 (marginal) AND
  `VI_Quality` bits 0-1 (MODLAND QA) are 00 (good) or 01 (produced, check other QA). Dropped: reliability -1 (fill),
  2 (snow/ice), 3 (cloudy), 4 (estimated), MODLAND 10/11.
- MOD11C3 LST_Day/LST_Night: `QC_Day`/`QC_Night` bits 0-1 (mandatory QA) = 00 (good) kept; = 01 (other quality) kept only
  if bits 6-7 (average LST error) = 00 (<=1 K) or 01 (<=2 K); 10/11 (not produced) dropped. QC value 0 means "good"
  even though the QC _FillValue is 0, so QC bits are never fill-masked; missing LST is caught by the LST fill.
- No clear-sky-days threshold is applied; `LST_Day_clear_days` / `LST_Night_clear_days` (popcount of the
  Clear_sky_days/nights bit fields, mean over QC'd pixels) are published so the clear-sky winter bias can be judged.
- Months with <50% of the region surviving QC are kept but flagged `qc_low_coverage_lt50pct`.

QC impact (`compare_modis_qc.py`, same cached pass; annual 12/12 OLS 2001-2025 per decade):

| region | variable | area_removed_by_qc_pct_mean | area_removed_by_qc_pct_max | months_qc_coverage_lt50pct | months_lost | mean_diff_qc_minus_noqc | trend_qc_per_decade | trend_noqc_per_decade | trend_diff | trend_DJF_qc | trend_DJF_noqc | trend_JJA_qc | trend_JJA_noqc | robust_qc | robust_noqc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ukraine_bbox | NDVI | 8.768 | 87.11 | 24 | 0 | 0.02181 | 0.004572 | 0.007749 | -0.003177 | 0.01972 | 0.02868 | -0.001173 | -0.001118 | method-dependent (not treated as a clear detection) | not significant at 0.05 on HAC and Hamed–Rao |
| ukraine_bbox | EVI | 8.768 | 87.11 | 24 | 0 | 0.007566 | 0.006542 | 0.007611 | -0.001069 | 0.007452 | 0.01055 | 0.009392 | 0.009432 | HAC significant; Hamed–Rao anti-conservative (negative residual AR); not treated as robust | robust at 0.05 (HAC and Hamed–Rao) |
| ukraine_bbox | LST_Day | 0.2884 | 2.832 | 0 | 0 | -0.002908 | 0.8214 | 0.8211 | 0.0003973 | 1.473 | 1.47 | 0.6323 | 0.6325 | robust at 0.05 (HAC and Hamed–Rao) | robust at 0.05 (HAC and Hamed–Rao) |
| ukraine_bbox | LST_Night | 0.3369 | 2.053 | 0 | 0 | -0.01032 | 0.8686 | 0.8676 | 0.0009774 | 1.546 | 1.544 | 0.8085 | 0.8079 | robust at 0.05 (HAC and Hamed–Rao) | robust at 0.05 (HAC and Hamed–Rao) |
| ukraine_mask | NDVI | 8.589 | 90.66 | 22 | 0 | 0.0207 | 0.00214 | 0.004742 | -0.002603 | 0.01783 | 0.02472 | -0.0006034 | -0.0005382 | not significant at 0.05 on HAC and Hamed–Rao | not significant at 0.05 on HAC and Hamed–Rao |
| ukraine_mask | EVI | 8.589 | 90.66 | 22 | 0 | 0.007244 | 0.00518 | 0.006064 | -0.0008834 | 0.005649 | 0.008047 | 0.01142 | 0.01147 | HAC significant; Hamed–Rao anti-conservative (negative residual AR); not treated as robust | robust at 0.05 (HAC and Hamed–Rao) |
| ukraine_mask | LST_Day | 0.275 | 3.915 | 0 | 0 | -0.002738 | 0.889 | 0.8884 | 0.0005931 | 1.517 | 1.515 | 0.6775 | 0.6776 | robust at 0.05 (HAC and Hamed–Rao) | robust at 0.05 (HAC and Hamed–Rao) |
| ukraine_mask | LST_Night | 0.2862 | 2.307 | 0 | 0 | -0.008046 | 0.858 | 0.8574 | 0.0006088 | 1.558 | 1.557 | 0.7933 | 0.7927 | robust at 0.05 (HAC and Hamed–Rao) | robust at 0.05 (HAC and Hamed–Rao) |
| ukraine_mask_no_crimea | NDVI | 8.916 | 93.14 | 23 | 0 | 0.02115 | 0.002732 | 0.005272 | -0.00254 | 0.01921 | 0.02566 | 0.0003066 | 0.0003765 | not significant at 0.05 on HAC and Hamed–Rao | not significant at 0.05 on HAC and Hamed–Rao |
| ukraine_mask_no_crimea | EVI | 8.916 | 93.14 | 23 | 0 | 0.007258 | 0.005511 | 0.006364 | -0.0008533 | 0.006061 | 0.008267 | 0.01238 | 0.01243 | HAC significant; Hamed–Rao anti-conservative (negative residual AR); not treated as robust | robust at 0.05 (HAC and Hamed–Rao) |
| ukraine_mask_no_crimea | LST_Day | 0.2302 | 3.828 | 0 | 0 | -0.0008024 | 0.8963 | 0.8958 | 0.0004129 | 1.529 | 1.527 | 0.6692 | 0.6692 | robust at 0.05 (HAC and Hamed–Rao) | robust at 0.05 (HAC and Hamed–Rao) |
| ukraine_mask_no_crimea | LST_Night | 0.2165 | 2.027 | 0 | 0 | -0.005115 | 0.8623 | 0.862 | 0.0002937 | 1.568 | 1.568 | 0.7915 | 0.791 | robust at 0.05 (HAC and Hamed–Rao) | robust at 0.05 (HAC and Hamed–Rao) |

% of valid area removed by QC, by season:

| region | variable | DJF | JJA | MAM | SON |
|---|---|---|---|---|---|
| ukraine_bbox | EVI | 31.8 | 0.06 | 2.73 | 0.92 |
| ukraine_bbox | LST_Day | 0.66 | 0.12 | 0.16 | 0.22 |
| ukraine_bbox | LST_Night | 0.75 | 0.19 | 0.2 | 0.22 |
| ukraine_bbox | NDVI | 31.8 | 0.06 | 2.73 | 0.92 |
| ukraine_mask | EVI | 31.8 | 0.06 | 2.07 | 0.95 |
| ukraine_mask | LST_Day | 0.66 | 0.11 | 0.14 | 0.2 |
| ukraine_mask | LST_Night | 0.65 | 0.17 | 0.15 | 0.18 |
| ukraine_mask | NDVI | 31.8 | 0.06 | 2.07 | 0.95 |
| ukraine_mask_no_crimea | EVI | 33 | 0.06 | 2.15 | 0.98 |
| ukraine_mask_no_crimea | LST_Day | 0.57 | 0.09 | 0.11 | 0.16 |
| ukraine_mask_no_crimea | LST_Night | 0.49 | 0.14 | 0.11 | 0.14 |
| ukraine_mask_no_crimea | NDVI | 33 | 0.06 | 2.15 | 0.98 |

Reading: LST QC removes <0.4% of area (the CMG LST is already clear-sky) and moves trends by <=0.001 °C/decade.
VI QC removes ~32% of the area in DJF (snow/ice and cloud), raises winter NDVI (mean +0.02), and roughly halves the
annual NDVI trend; annual EVI stays HAC-significant but is no longer robust (Hamed-Rao anti-conservative). JJA VI trends
are unchanged by QC, so the QC change is a winter-sampling effect: use JJA/growing-season VI for trend claims.

## Multiple-testing summary (headline rows)

Primary test (v1.4, ADR-003): repo Mann-Kendall Yue-Wang. `mt_bonferroni_pass` / `mt_bh_pass` are
Bonferroni and Benjamini-Hochberg on `yw_p` inside each test family (annual, or monthly). The OLS n_eff
cross-check is `yw_ols_neff_p`; `yw_ols_neff_agree` is whether the two tests agree at 0.05. HAC and
Hamed-Rao lag-3 remain sensitivity columns (`sens_mt_*`). A headline is a detection only when Yue-Wang is
significant at 0.05, the OLS cross-check agrees, and the quoted multiple-testing correction passes.
The lists below are computed from this run. v1.3 called a row robust only when HAC and Hamed-Rao both
passed; that rule is no longer the wording.

POWER solar (`ALLSKY_SFC_SW_DWN`) has a source break (GEWEX SRB before 2001, CERES from 2001). The
pipeline uses 2001+ only. Do not headline it unless this run's Yue-Wang row survives Bonferroni or BH
and agrees with OLS n_eff. GLDAS precipitation and evaporation are forcing diagnostics, not observations.

- `ukraine_bbox`: Bonferroni pass: airs:SurfAirTemp, berkeley:tas_anomaly, ghcn:TAVG_anom, ghcn:TMAX_anom, gistemp:tas_anomaly, gldas20:Tair_f_inst, grace:TWS, gsom:TAVG_anom, gsom:TMAX_anom, hadcrut5:tas_anomaly, merra2:QV2M, merra2:T2M, merra2:T2MMAX, merra2:T2MMIN, modis:LST_Night, nasa_power:QV2M, nasa_power:T2M, nasa_power:T2M_MAX. BH only: ghcn:TMIN_anom, gldas20:Evap_tavg, gldas21:Qs_acc, gldas21:RootMoist_inst, gldas21:SoilMoi0_10cm_inst, gldas21:Tair_f_inst, gpcc:precip, gsom:TMIN_anom, modis:LST_Day, nasa_power:ALLSKY_SFC_SW_DWN, nasa_power:PRECTOTCORR, nasa_power:T2M_MIN, nasa_power:WS10M. Yue-Wang raw 0.05 but fail BH: gldas20:rainfall_liquid, gldas21:Evap_tavg, modis:EVI (Apr-Sep).
- `ukraine_mask`: Bonferroni pass: berkeley:tas_anomaly, berkeley_country:tas_anomaly, cru_cy:tmn, cru_cy:tmp, cru_cy:tmp_anom, cru_cy:tmx, cru_cy:vap, ghcn:TMAX_anom, gistemp:tas_anomaly, gldas20:Tair_f_inst, grace:TWS, gsom:TAVG_anom, gsom:TMAX_anom, hadcrut5:tas_anomaly, merra2:T2M, merra2:T2MMAX, merra2:T2MMIN, modis:LST_Night, nasa_power:T2M, nasa_power:T2M_MAX. BH only: airs:SurfAirTemp, cru_cy:dtr, cru_cy:wet, ghcn:TAVG_anom, ghcn:TMIN_anom, gldas20:Evap_tavg, gldas21:Qs_acc, gldas21:RootMoist_inst, gldas21:SoilMoi0_10cm_inst, gldas21:Tair_f_inst, gsom:TMIN_anom, merra2:QV2M, modis:LST_Day, nasa_power:QV2M, nasa_power:T2M_MIN. Yue-Wang raw 0.05 but fail BH: cru_cy:pet, modis:EVI (JJA), nasa_power:ALLSKY_SFC_SW_DWN, nasa_power:WS10M.
- `ukraine_mask_no_crimea`: Bonferroni pass: berkeley:tas_anomaly, berkeley_country:tas_anomaly, cru_cy:tmn, cru_cy:tmp, cru_cy:tmp_anom, cru_cy:tmx, cru_cy:vap, ghcn:TMAX_anom, gistemp:tas_anomaly, gldas20:Tair_f_inst, grace:TWS, gsom:TAVG_anom, gsom:TMAX_anom, hadcrut5:tas_anomaly, merra2:T2M, merra2:T2MMAX, merra2:T2MMIN, modis:LST_Night, nasa_power:T2M, nasa_power:T2M_MAX. BH only: airs:SurfAirTemp, cru_cy:dtr, cru_cy:wet, ghcn:TAVG_anom, ghcn:TMIN_anom, gldas20:Evap_tavg, gldas21:Qs_acc, gldas21:RootMoist_inst, gldas21:SoilMoi0_10cm_inst, gldas21:Tair_f_inst, gsom:TMIN_anom, merra2:QV2M, modis:EVI (JJA), modis:LST_Day, nasa_power:QV2M, nasa_power:T2M_MIN. Yue-Wang raw 0.05 but fail BH: cru_cy:pet, nasa_power:ALLSKY_SFC_SW_DWN, nasa_power:WS10M.

## Growing-season vegetation (QC'd MODIS NDVI/EVI)

Peak season = JJA (3/3 months); growing season = Apr-Sep (6/6 months, period `AMJJAS` in annual_seasonal);
both for 2001-2025 (the years of the annual 12/12 row), both in the official annual test family. The annual 12/12 VI row is
kept but labelled `annual_includes_low_coverage_winter_months` (22 Jan/Feb months with <50% QC coverage over the record)
and is not a headline. **Results are season-sensitive.** Read `yw_p` (primary) next to `yw_ols_neff_p` and the
HAC/Hamed-Rao sensitivity columns. A seasonal VI row is not a detection unless Yue-Wang and the OLS cross-check
agree and the quoted multiple-testing correction passes. Neither season is preferred.

| region | variable | series | years | n | slope_per_decade | yw_p | yw_ols_neff_p | hac1_p | mk_hr_p | call | bonferroni | bh | headline |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ukraine_bbox | NDVI | annual_ANN_12of12 | 2001-2025 | 25 | +0.00457 | 0.199 | 0.11 | 0.0768 | 0.00771 | annual includes 22 Jan/Feb months with <50% QC coverage (snow) in this window (24 over the | False | False | False |
| ukraine_bbox | NDVI | seasonal_JJA_3of3_peak_season | 2001-2025 | 25 | -0.00117 | 0.657 | 0.821 | 0.827 | 0.657 | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | True |
| ukraine_bbox | NDVI | seasonal_AprSep_6of6_growing_season | 2001-2025 | 25 | -0.00121 | 0.528 | 0.771 | 0.708 | 0.191 | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | True |
| ukraine_bbox | EVI | annual_ANN_12of12 | 2001-2025 | 25 | +0.00654 | 0.00302 | 0.00101 | 0.000242 | 0 | annual includes 22 Jan/Feb months with <50% QC coverage (snow) in this window (24 over the | False | True | False |
| ukraine_bbox | EVI | seasonal_JJA_3of3_peak_season | 2001-2025 | 25 | +0.00939 | 0.0973 | 0.0469 | 0.0571 | 0.0973 | not significant at 0.05 (repo MK Yue-Wang; verdict weak) | False | False | True |
| ukraine_bbox | EVI | seasonal_AprSep_6of6_growing_season | 2001-2025 | 25 | +0.00771 | 0.0471 | 0.0248 | 0.00273 | 1.94e-11 | significant at 0.05 (repo MK Yue-Wang; verdict moderate) | False | False | True |
| ukraine_mask | NDVI | annual_ANN_12of12 | 2001-2025 | 25 | +0.00214 | 0.624 | 0.474 | 0.416 | 0.624 | annual includes 19 Jan/Feb months with <50% QC coverage (snow) in this window (22 over the | False | False | False |
| ukraine_mask | NDVI | seasonal_JJA_3of3_peak_season | 2001-2025 | 25 | -0.00060 | 0.528 | 0.918 | 0.921 | 0.528 | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | True |
| ukraine_mask | NDVI | seasonal_AprSep_6of6_growing_season | 2001-2025 | 25 | -0.00321 | 0.414 | 0.479 | 0.39 | 0.0355 | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | True |
| ukraine_mask | EVI | annual_ANN_12of12 | 2001-2025 | 25 | +0.00518 | 0.065 | 0.0108 | 0.00587 | 0.000866 | annual includes 19 Jan/Feb months with <50% QC coverage (snow) in this window (22 over the | False | False | False |
| ukraine_mask | EVI | seasonal_JJA_3of3_peak_season | 2001-2025 | 25 | +0.01142 | 0.0471 | 0.0296 | 0.0325 | 0.0471 | significant at 0.05 (repo MK Yue-Wang; verdict moderate) | False | False | True |
| ukraine_mask | EVI | seasonal_AprSep_6of6_growing_season | 2001-2025 | 25 | +0.00706 | 0.141 | 0.051 | 0.0158 | 0.000921 | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | True |
| ukraine_mask_no_crimea | NDVI | annual_ANN_12of12 | 2001-2025 | 25 | +0.00273 | 0.498 | 0.381 | 0.336 | 0.498 | annual includes 20 Jan/Feb months with <50% QC coverage (snow) in this window (23 over the | False | False | False |
| ukraine_mask_no_crimea | NDVI | seasonal_JJA_3of3_peak_season | 2001-2025 | 25 | +0.00031 | 0.591 | 0.957 | 0.958 | 0.591 | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | True |
| ukraine_mask_no_crimea | NDVI | seasonal_AprSep_6of6_growing_season | 2001-2025 | 25 | -0.00266 | 0.559 | 0.555 | 0.475 | 0.149 | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | True |
| ukraine_mask_no_crimea | EVI | annual_ANN_12of12 | 2001-2025 | 25 | +0.00551 | 0.0471 | 0.0087 | 0.00633 | 0.0471 | annual includes 20 Jan/Feb months with <50% QC coverage (snow) in this window (23 over the | False | False | False |
| ukraine_mask_no_crimea | EVI | seasonal_JJA_3of3_peak_season | 2001-2025 | 25 | +0.01238 | 0.0235 | 0.0194 | 0.0195 | 0.0235 | significant at 0.05 (repo MK Yue-Wang; verdict moderate) | False | True | True |
| ukraine_mask_no_crimea | EVI | seasonal_AprSep_6of6_growing_season | 2001-2025 | 25 | +0.00762 | 0.0973 | 0.0366 | 0.0104 | 4.71e-05 | not significant at 0.05 (repo MK Yue-Wang; verdict weak) | False | False | True |

## Region `ukraine_bbox`

Bounds [22.1, 44.4, 40.2, 52.4]; 73 series; 19.4 s.

### Source status

| source | status | details |
|---|---|---|
| nasa_power | ok | {} |
| grace | ok | {"file": "$GLOBAL_DATA/grace/GRCTellus.JPL.200204_202609.GLO.RL06.3M.MSCNv04CRI.nc", "n_mascons": 15, "n_land_cells_weight_gt0": 560, "time_center_vs_csv_max_days": 0} |
| hadcrut5 | ok | {"n_cells_weight_gt0": 15, "sum_frac": 5.792} |
| gistemp | ok | {"n_cells_weight_gt0": 50} |
| berkeley | ok | {"n_cells_weight_gt0": 166, "weight": "area x overlap x land_mask fraction"} |
| chirps | ok | {"path": "global_grid_overlap_weights", "file": "$GLOBAL_DATA/chirps_v3/chirps-v3.0.monthly.nc", "cache": "chirps_ukraine_bbox_a7c5a48e436cb8be.parquet"} |
| cci_sm | ok | {"note": "record 1978-11..1991-12 only"} |
| merra2 | ok | {"path": "global_grid_overlap_weights", "products": [{"product": "merra2_slv", "dir": "$GLOBAL_DATA/merra2_slv_slim", "n_files": 561, "window_cells": "17x30", "cache": "merra2_slv_ukraine_bbox_5dfde50564399045.parquet", "status": "cached"}, {"product": "merra2_flx", "dir": "$GLOBAL_DATA/merra2_flx_slim", "n_files": 561, "window_cells": "17x30", "cache": "merra2_flx_ukraine_bbox_2bce88e428930a39.pa |
| gldas20 | ok | {"path": "global_grid_overlap_weights", "products": [{"product": "gldas20", "dir": "$GLOBAL_DATA/gldas20_slim", "n_files": 804, "window_cells": "33x73", "cache": "gldas20_ukraine_bbox_65fb0c399b6c71ab.parquet", "status": "cached"}, {"product": "gldas20_rainf", "dir": "$GLOBAL_DATA/gldas20_rainf", "n_files": 804, "window_cells": "33x73", "cache": "gldas20_rainf_ukraine_bbox_9a90372deb28f426.parquet |
| gldas21 | ok | {"path": "global_grid_overlap_weights", "products": [{"product": "gldas21", "dir": "$GLOBAL_DATA/gldas21_slim", "n_files": 319, "window_cells": "33x73", "cache": "gldas21_ukraine_bbox_613915cdf88a113b.parquet", "status": "cached"}, {"product": "gldas21_rainf", "dir": "$GLOBAL_DATA/gldas21_rainf", "n_files": 319, "window_cells": "33x73", "cache": "gldas21_rainf_ukraine_bbox_1d410ba85e1075e8.parquet |
| gpm_imerg | ok | {"path": "global_grid_overlap_weights", "products": [{"product": "gpm_imerg", "dir": "$GLOBAL_DATA/gpm_imerg_slim", "n_files": 333, "window_cells": "81x181", "cache": "gpm_imerg_ukraine_bbox_93316a02cd4dbb3b.parquet", "status": "cached"}]} |
| airs | ok | {"path": "global_grid_overlap_weights", "products": [{"product": "airs", "dir": "$GLOBAL_DATA/airs3stm_slim", "n_files": 290, "window_cells": "9x19", "cache": "airs_ukraine_bbox_13acde4a5697ff3a.parquet", "status": "cached"}]} |
| modis | ok | {"path": "global_grid_overlap_weights", "products": [{"product": "mod13c2_qc", "dir": "$GLOBAL_DATA/mod13c2_slim", "n_files": 321, "window_cells": "160x363", "cache": "mod13c2_qc_ukraine_bbox_ad93482c93b5cf93.parquet", "status": "cached"}, {"product": "mod11c3_qc", "dir": "$GLOBAL_DATA/mod11c3_slim", "n_files": 321, "window_cells": "160x363", "cache": "mod11c3_qc_ukraine_bbox_fc4d3c7a6208f4ac.parq |
| omi | ok | {"note": "n_valid = days with data; coverage = days/days_in_month"} |
| gpcc | ok | {"path": "global_grid_overlap_weights", "n_files": 47, "cache": "gpcc_ukraine_bbox_a27d0d3e1d5e7e00.parquet"} |
| cru_cy | skipped | {"reason": "country (Ukraine) series; only used for ukraine_mask* regions"} |
| berkeley_country | skipped | {"reason": "country (Ukraine) series; only used for ukraine_mask* regions"} |
| ghcn | ok | {"n_stations_in_region": 28, "n_qflag_values_removed": 4022} |
| gsom | ok | {"n_stations_in_region": 204} |
| swot | ok | {"n_reaches": 8} |

### Per-variable QC

| source | variable | unit | first | last | pct_valid_raw | pct_valid_gap_excluded | n_gaps | longest_gap_months | complete_years | min_coverage_frac | min_n_valid | baseline | flag_counts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nasa_power | T2M | °C | 1981-01 | 2025-12 | 100 | 100 | 0 | 0 | 45 | 0.978 | 464 | 1991-2020 |  |
| nasa_power | T2M_MAX | °C | 1981-01 | 2025-12 | 100 | 100 | 0 | 0 | 45 | 0.978 | 464 | 1991-2020 |  |
| nasa_power | T2M_MIN | °C | 1981-01 | 2025-12 | 100 | 100 | 0 | 0 | 45 | 0.978 | 464 | 1991-2020 |  |
| nasa_power | PRECTOTCORR | mm/month | 1981-01 | 2025-12 | 100 | 100 | 0 | 0 | 45 | 0.978 | 464 | 1991-2020 |  |
| nasa_power | QV2M | g/kg | 1981-01 | 2025-12 | 100 | 100 | 0 | 0 | 45 | 0.978 | 464 | 1991-2020 |  |
| nasa_power | WS10M | m/s | 1981-01 | 2025-12 | 100 | 100 | 0 | 0 | 45 | 0.978 | 464 | 1991-2020 |  |
| nasa_power | ALLSKY_SFC_SW_DWN | kWh/m²/day | 2001-01 | 2025-12 | 100 | 100 | 0 | 0 | 25 | 0.944 | 144 | 1991-2020 | partial_year=204; missing_value=204 |
| derived | DTR | °C | 1981-01 | 2025-12 | 100 | 100 | 0 | 0 | 45 |  | 464 | 1991-2020 | derived_from_POWER_T2M_MAX_minus_T2M_MIN=540 |
| grace | TWS | cm EWH anomaly | 2002-04 | 2026-09 | 88.8 | 100 | 18 | 11 | 14 | 0.905 | 560 | record_mean | partial_year=126; missing_month_official=33; missing_value=33; grace_gracefo_gap=11 |
| hadcrut5 | tas_anomaly | °C anomaly (1961-1990) | 1850-01 | 2026-09 | 100 | 100 | 0 | 0 | 176 | 0.995 | 15 | 1991-2020 | coarse_cells_extend_beyond_region=2121; partial_year=9; outlier_5sigma=2 |
| gistemp | tas_anomaly | °C anomaly (1951-1980) | 1880-01 | 2026-10 | 100 | 100 | 0 | 0 | 146 | 1 | 50 | 1991-2020 | coarse_cells_extend_beyond_region=1762; partial_year=10; outlier_5sigma=4 |
| berkeley | tas_anomaly | °C anomaly (1951-1980) | 1750-01 | 2024-12 | 100 | 100 | 1 | 1 | 274 | 0.839 | 151 | 1991-2020 | partial_year=12; outlier_5sigma=2; missing_value=1 |
| chirps | precip | mm/month | 1981-01 | 2026-09 | 100 | 100 | 0 | 0 | 45 | 0.948 | 5.56e+04 | 1991-2020 | partial_year=9 |
| cci_sm | sm | m³/m³ | 1978-11 | 2024-12 | 100 | 100 | 0 | 0 | 46 | 0.122 | 296 | 1991-2020 | partial_record_1978-1991=554; winter_low_coverage=554; partial_year=2 |
| merra2 | T2M | °C | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 510 | 1991-2020 | partial_year=9 |
| merra2 | QV2M | g/kg | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 510 | 1991-2020 | partial_year=9 |
| merra2 | SLP | hPa | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 510 | 1991-2020 | partial_year=9 |
| merra2 | PRECTOTCORR | mm/month | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 510 | 1991-2020 | partial_year=9 |
| merra2 | PRECTOT | mm/month | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 510 | 1991-2020 | partial_year=9 |
| merra2 | U10M | m/s | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 510 | 1991-2020 | partial_year=9 |
| merra2 | V10M | m/s | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 510 | 1991-2020 | partial_year=9 |
| merra2 | WS10M_from_mean_UV | m/s | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 510 | 1991-2020 | speed_of_monthly_mean_wind_underestimates_mean_speed=561; partial_year=9 |
| merra2 | T2MMAX | °C | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 510 | 1991-2020 | partial_year=9 |
| merra2 | T2MMIN | °C | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 510 | 1991-2020 | partial_year=9 |
| merra2 | DTR | °C | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 510 | 1991-2020 | partial_year=9 |
| gldas20 | SoilMoi0_10cm_inst | kg/m² (≈mm) | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.895 | 2.16e+03 | 1991-2020 |  |
| gldas20 | RootMoist_inst | kg/m² (≈mm) | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.895 | 2.16e+03 | 1991-2020 |  |
| gldas20 | SWE_inst | kg/m² (≈mm) | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.895 | 2.16e+03 | 1991-2020 | outlier_5sigma=8 |
| gldas20 | Tair_f_inst | °C | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.898 | 2.16e+03 | 1991-2020 |  |
| gldas20 | Evap_tavg | mm/month | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.895 | 2.16e+03 | 1991-2020 |  |
| gldas20 | Qs_acc | mm/month | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.895 | 2.16e+03 | 1991-2020 | outlier_5sigma=5 |
| gldas20 | Qsb_acc | mm/month | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.895 | 2.16e+03 | 1991-2020 | outlier_5sigma=4 |
| gldas20 | precip_total | mm/month | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.898 | 2.16e+03 | 1991-2020 |  |
| gldas20 | snowfall | mm/month | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.895 | 2.16e+03 | 1991-2020 | outlier_5sigma=2 |
| gldas20 | rainfall_liquid | mm/month | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.895 | 2.16e+03 | 1991-2020 |  |
| gldas21 | SoilMoi0_10cm_inst | kg/m² (≈mm) | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.895 | 2.16e+03 | 1991-2020 | partial_year=7 |
| gldas21 | RootMoist_inst | kg/m² (≈mm) | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.895 | 2.16e+03 | 1991-2020 | partial_year=7 |
| gldas21 | SWE_inst | kg/m² (≈mm) | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.895 | 2.16e+03 | 1991-2020 | partial_year=7; outlier_5sigma=1 |
| gldas21 | Tair_f_inst | °C | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.898 | 2.16e+03 | 1991-2020 | partial_year=7 |
| gldas21 | Evap_tavg | mm/month | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.895 | 2.16e+03 | 1991-2020 | partial_year=7 |
| gldas21 | Qs_acc | mm/month | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.895 | 2.16e+03 | 1991-2020 | partial_year=7; outlier_5sigma=3 |
| gldas21 | Qsb_acc | mm/month | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.895 | 2.16e+03 | 1991-2020 | partial_year=7; outlier_5sigma=1 |
| gldas21 | precip_total | mm/month | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.898 | 2.16e+03 | 1991-2020 | partial_year=7 |
| gldas21 | snowfall | mm/month | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.895 | 2.16e+03 | 1991-2020 | partial_year=7 |
| gldas21 | rainfall_liquid | mm/month | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.895 | 2.16e+03 | 1991-2020 | partial_year=7 |
| gpm_imerg | precipitation | mm/month | 1998-01 | 2025-09 | 100 | 100 | 0 | 0 | 27 | 1 | 1.47e+04 | 1991-2020 | partial_year=9 |
| airs | SurfAirTemp | °C | 2002-09 | 2026-10 | 100 | 100 | 0 | 0 | 23 | 1 | 171 | record_mean | partial_year=14; airs_2025_bias_unverified=12 |
| airs | TotH2OVap | kg/m² (≈mm) | 2002-09 | 2026-10 | 100 | 100 | 0 | 0 | 23 | 1 | 171 | record_mean | partial_year=14; airs_2025_bias_unverified=12 |
| modis | NDVI | index | 2000-02 | 2026-10 | 100 | 100 | 0 | 0 | 25 | 0.117 | 6.59e+03 | 1991-2020 | qc_pixel_masked=321; terra_only=321; vi_winter_snow_masked_sampling=321; qc_low_coverage_lt50pct=24; partial_year=21 |
| modis | EVI | index | 2000-02 | 2026-10 | 100 | 100 | 0 | 0 | 25 | 0.117 | 6.59e+03 | 1991-2020 | qc_pixel_masked=321; terra_only=321; vi_winter_snow_masked_sampling=321; qc_low_coverage_lt50pct=24; partial_year=21 |
| modis | LST_Day | °C | 2000-02 | 2026-10 | 100 | 100 | 0 | 0 | 25 | 0.83 | 4.84e+04 | 1991-2020 | qc_pixel_masked=321; terra_only=321; lst_clear_sky_winter_bias=321; partial_year=21 |
| modis | LST_Night | °C | 2000-02 | 2026-10 | 100 | 100 | 0 | 0 | 25 | 0.893 | 5.22e+04 | 1991-2020 | qc_pixel_masked=321; terra_only=321; lst_clear_sky_winter_bias=321; partial_year=21 |
| modis | LST_Day_clear_days | days | 2000-02 | 2026-10 | 100 | 100 | 0 | 0 | 25 | 0.83 | 4.84e+04 | 1991-2020 | qc_pixel_masked=321; terra_only=321; partial_year=21; outlier_5sigma=1 |
| modis | LST_Night_clear_days | days | 2000-02 | 2026-10 | 100 | 100 | 0 | 0 | 25 | 0.893 | 5.22e+04 | 1991-2020 | qc_pixel_masked=321; terra_only=321; partial_year=21 |
| omi | ColumnAmountNO2Trop | molec/cm² | 2004-10 | 2026-11 | 100 | 100 | 0 | 0 | 21 | 0.367 | 11 | record_mean | preaggregated_bbox_mean_centre_weights=266; omi_row_anomaly_period=239; partial_year=14 |
| omi | ColumnAmountNO2TropCloudScreened | molec/cm² | 2004-10 | 2026-11 | 100 | 100 | 0 | 0 | 21 | 0.367 | 11 | record_mean | preaggregated_bbox_mean_centre_weights=266; omi_row_anomaly_period=239; partial_year=14 |
| gpcc | precip | mm/month | 1891-01 | 2026-08 | 100 | 100 | 0 | 0 | 135 | 0.975 | 166 | 1991-2020 | partial_year=8 |
| ghcn | TAVG_anom | °C anomaly (1991-2020) | 1881-01 | 2026-10 | 99.4 | 99.4 | 6 | 3 | 140 | 0.04 | 1 | 1991-2020 | station_anomaly_mean=1750; UP_stations_only=1750; few_stations_lt3=186; partial_year=70; missing_value=11; outlier_5sigma=3 |
| ghcn | TMAX_anom | °C anomaly (1991-2020) | 1881-01 | 2026-10 | 99.7 | 99.7 | 4 | 2 | 142 | 0.0385 | 1 | 1991-2020 | station_anomaly_mean=1750; UP_stations_only=1750; few_stations_lt3=173; partial_year=46; missing_value=5 |
| ghcn | TMIN_anom | °C anomaly (1991-2020) | 1881-01 | 2026-10 | 99.6 | 99.6 | 6 | 2 | 140 | 0.0385 | 1 | 1991-2020 | station_anomaly_mean=1750; UP_stations_only=1750; few_stations_lt3=82; partial_year=70; missing_value=7; outlier_5sigma=3 |
| ghcn | PRCP_anom | mm/month anomaly (1991-2020) | 1881-01 | 2025-07 | 99.8 | 99.8 | 3 | 1 | 141 | 0.0769 | 1 | 1991-2020 | station_anomaly_mean=1735; UP_stations_only=1735; few_stations_lt3=195; partial_year=43; missing_value=3; outlier_5sigma=1 |
| gsom | TAVG_anom | °C anomaly (1991-2020) | 1900-01 | 2026-10 | 98.5 | 98.5 | 9 | 5 | 120 | 0.0278 | 1 | 1991-2020 | station_anomaly_mean=1522; UP_stations_only=1522; partial_year=82; missing_value=23; few_stations_lt3=12; outlier_5sigma=3 |
| gsom | TMAX_anom | °C anomaly (1991-2020) | 1900-01 | 2026-10 | 99.7 | 99.7 | 4 | 2 | 124 | 0.0256 | 1 | 1991-2020 | station_anomaly_mean=1522; UP_stations_only=1522; partial_year=34; few_stations_lt3=8; missing_value=5 |
| gsom | TMIN_anom | °C anomaly (1991-2020) | 1900-01 | 2026-10 | 98.5 | 98.5 | 8 | 5 | 121 | 0.027 | 1 | 1991-2020 | station_anomaly_mean=1522; UP_stations_only=1522; partial_year=70; missing_value=22; few_stations_lt3=10; outlier_5sigma=4 |
| gsom | PRCP_anom | mm/month anomaly (1991-2020) | 1900-01 | 2025-07 | 99.9 | 99.9 | 1 | 1 | 124 | 0.0952 | 2 | 1991-2020 | station_anomaly_mean=1507; UP_stations_only=1507; few_stations_lt3=67; partial_year=19; outlier_5sigma=1; missing_value=1 |
| swot | wse_Chernihiv_Dnieper | m | 2023-08 | 2026-11 | 77.5 | 77.5 | 1 | 9 | 0 |  |  | record_mean | too_short_for_climate_inference=31; reach_not_regional=31; partial_year=31; short_record=31 |
| swot | wse_Chernivtsi_Prut | m | 2023-08 | 2026-10 | 84.6 | 84.6 | 1 | 6 | 0 |  |  | record_mean | too_short_for_climate_inference=33; reach_not_regional=33; partial_year=33; short_record=33 |
| swot | wse_Kherson_Dnieper | m | 2023-04 | 2026-11 | 86.4 | 86.4 | 1 | 6 | 0 |  |  | record_mean | too_short_for_climate_inference=38; reach_not_regional=38; partial_year=38; short_record=38 |
| swot | wse_Kyiv_Desna | m | 2023-08 | 2026-11 | 75 | 75 | 1 | 10 | 0 |  |  | record_mean | too_short_for_climate_inference=30; reach_not_regional=30; partial_year=30; short_record=30 |
| swot | wse_Lower_Dniester | m | 2023-07 | 2026-11 | 78 | 78 | 1 | 9 | 0 |  |  | record_mean | too_short_for_climate_inference=32; reach_not_regional=32; partial_year=32; short_record=32 |
| swot | wse_Odesa_Dniester | m | 2023-08 | 2026-11 | 85 | 85 | 1 | 6 | 0 |  |  | record_mean | too_short_for_climate_inference=34; reach_not_regional=34; partial_year=34; short_record=34 |
| swot | wse_Pripyat_border | m | 2023-08 | 2026-11 | 72.5 | 72.5 | 1 | 11 | 0 |  |  | record_mean | too_short_for_climate_inference=29; reach_not_regional=29; partial_year=29; short_record=29 |
| swot | wse_Vinnytsia_SouthernBug | m | 2023-07 | 2026-11 | 85.4 | 85.4 | 1 | 6 | 0 |  |  | record_mean | too_short_for_climate_inference=35; reach_not_regional=35; partial_year=35; short_record=35 |

### Headline trends (annual full window; stations 1981-2019; GRACE = headline method, monthly; VI = peak-season JJA and growing-season Apr-Sep)

`mt_bonferroni_pass` / `mt_bh_pass` are Bonferroni / Benjamini-Hochberg (q<0.05) on the primary Yue-Wang p-value, across the whole test family (all windows and roles; family size in `n_tests_in_family`). `yw_ols_neff_agree` is the OLS effective-n cross-check. HAC / Hamed-Rao are sensitivity only (`sensitivity_call_hac_hr`). Forcing/sampling diagnostics, different-convention rows and the annual VI rows are not headlines (column `role` in trends.csv).

| source | variable | unit | series | window | start | end | n | lin_slope_per_decade | yw_p | yw_ols_neff_p | yw_ols_neff_agree | robust_call | mt_bonferroni_pass | mt_bh_pass | test_family | n_tests_in_family | excluded_years |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nasa_power | T2M | °C | annual_ANN_12of12 | full | 1981 | 2025 | 45 | 0.5526 | 9.79e-06 | 4.334e-06 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 135 |  |
| nasa_power | T2M_MAX | °C | annual_ANN_12of12 | full | 1981 | 2025 | 45 | 0.5592 | 8.737e-06 | 1.6e-06 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 135 |  |
| nasa_power | T2M_MIN | °C | annual_ANN_12of12 | full | 1981 | 2025 | 45 | 0.6039 | 0.001698 | 0.0003349 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 135 |  |
| nasa_power | PRECTOTCORR | mm/year | annual_ANN_12of12 | full | 1981 | 2025 | 45 | 14.83 | 0.01939 | 0.086 | False | significant at 0.05 (repo MK Yue-Wang; verdict moderate) | False | True | annual | 135 |  |
| nasa_power | QV2M | g/kg | annual_ANN_12of12 | full | 1981 | 2025 | 45 | 0.1626 | 2.905e-05 | 2.446e-05 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 135 |  |
| nasa_power | WS10M | m/s | annual_ANN_12of12 | full | 1981 | 2025 | 45 | -0.02336 | 0.02425 | 0.09197 | False | significant at 0.05 (repo MK Yue-Wang; verdict moderate) | False | True | annual | 135 |  |
| nasa_power | ALLSKY_SFC_SW_DWN | kWh/m²/day | annual_ANN_12of12 | full | 2001 | 2025 | 25 | 0.05379 | 0.02651 | 0.01493 | True | significant at 0.05 (repo MK Yue-Wang; verdict moderate) | False | True | annual | 135 |  |
| derived | DTR | °C | annual_ANN_12of12 | full | 1981 | 2025 | 45 | -0.04466 | 0.4396 | 0.6574 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| hadcrut5 | tas_anomaly | °C anomaly (1961-1990) | annual_ANN_12of12 | full | 1850 | 2025 | 176 | 0.09543 | 9.943e-08 | 1.041e-08 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 135 |  |
| gistemp | tas_anomaly | °C anomaly (1951-1980) | annual_ANN_12of12 | full | 1880 | 2025 | 146 | 0.159 | 5.62e-11 | 2.149e-12 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 135 |  |
| berkeley | tas_anomaly | °C anomaly (1951-1980) | annual_ANN_12of12 | full | 1750 | 2024 | 274 | 0.06061 | 9.274e-11 | 2.918e-12 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 135 |  |
| chirps | precip | mm/year | annual_ANN_12of12 | full | 1981 | 2025 | 45 | 1.832 | 0.6884 | 0.8686 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| cci_sm | sm | m³/m³ | annual_ANN_12of12 | full | 1979 | 2024 | 46 | -0.0006032 | 0.6472 | 0.5538 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| merra2 | T2M | °C | annual_ANN_12of12 | full | 1980 | 2025 | 46 | 0.5786 | 1.768e-06 | 4.787e-07 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 135 |  |
| merra2 | QV2M | g/kg | annual_ANN_12of12 | full | 1980 | 2025 | 46 | 0.1554 | 0.0001197 | 0.0001201 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 135 |  |
| merra2 | SLP | hPa | annual_ANN_12of12 | full | 1980 | 2025 | 46 | -0.1139 | 0.2329 | 0.2173 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| merra2 | PRECTOTCORR | mm/year | annual_ANN_12of12 | full | 1980 | 2025 | 46 | 6.549 | 0.1383 | 0.5911 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| merra2 | PRECTOT | mm/year | annual_ANN_12of12 | full | 1980 | 2025 | 46 | 0.6867 | 0.7543 | 0.9565 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| merra2 | U10M | m/s | annual_ANN_12of12 | full | 1980 | 2025 | 46 | -0.04363 | 0.4718 | 0.3664 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| merra2 | V10M | m/s | annual_ANN_12of12 | full | 1980 | 2025 | 46 | -0.02184 | 0.2184 | 0.217 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| merra2 | WS10M_from_mean_UV | m/s | annual_ANN_12of12 | full | 1980 | 2025 | 46 | -0.01957 | 0.527 | 0.4561 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| merra2 | T2MMAX | °C | annual_ANN_12of12 | full | 1980 | 2025 | 46 | 0.6169 | 1.963e-06 | 2.929e-07 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 135 |  |
| merra2 | T2MMIN | °C | annual_ANN_12of12 | full | 1980 | 2025 | 46 | 0.5702 | 1.06e-05 | 3.172e-06 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 135 |  |
| merra2 | DTR | °C | annual_ANN_12of12 | full | 1980 | 2025 | 46 | 0.04672 | 0.2053 | 0.1951 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| gldas20 | SoilMoi0_10cm_inst | kg/m² (≈mm) | annual_ANN_12of12 | full | 1948 | 2014 | 67 | 0.08654 | 0.7043 | 0.527 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| gldas20 | RootMoist_inst | kg/m² (≈mm) | annual_ANN_12of12 | full | 1948 | 2014 | 67 | 2.455 | 0.5292 | 0.2706 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| gldas20 | SWE_inst | kg/m² (≈mm) | annual_ANN_12of12 | full | 1948 | 2014 | 67 | -0.1737 | 0.8313 | 0.5948 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| gldas20 | Tair_f_inst | °C | annual_ANN_12of12 | full | 1948 | 2014 | 67 | 0.211 | 0.0003115 | 0.0001761 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 135 |  |
| gldas20 | Evap_tavg | mm/year | annual_ANN_12of12 | full | 1948 | 2014 | 67 | 5.548 | 0.003758 | 0.001832 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 135 |  |
| gldas20 | Qs_acc | mm/year | annual_ANN_12of12 | full | 1948 | 2014 | 67 | -0.2858 | 0.4671 | 0.525 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| gldas20 | Qsb_acc | mm/year | annual_ANN_12of12 | full | 1948 | 2014 | 67 | 1.751 | 0.3153 | 0.52 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| gldas20 | precip_total | mm/year | annual_ANN_12of12 | full | 1948 | 2014 | 67 | 5.041 | 0.15 | 0.2079 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| gldas20 | snowfall | mm/year | annual_ANN_12of12 | full | 1948 | 2014 | 67 | -1.561 | 0.6117 | 0.5396 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| gldas20 | rainfall_liquid | mm/year | annual_ANN_12of12 | full | 1948 | 2014 | 67 | 6.611 | 0.03975 | 0.06661 | False | significant at 0.05 (repo MK Yue-Wang; verdict moderate) | False | False | annual | 135 |  |
| gldas21 | SoilMoi0_10cm_inst | kg/m² (≈mm) | annual_ANN_12of12 | full | 2000 | 2025 | 26 | -1.262 | 0.008316 | 0.007392 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 135 |  |
| gldas21 | RootMoist_inst | kg/m² (≈mm) | annual_ANN_12of12 | full | 2000 | 2025 | 26 | -14.42 | 0.01978 | 0.01778 | True | significant at 0.05 (repo MK Yue-Wang; verdict moderate) | False | True | annual | 135 |  |
| gldas21 | Tair_f_inst | °C | annual_ANN_12of12 | full | 2000 | 2025 | 26 | 0.9266 | 0.0005847 | 0.0001975 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 135 |  |
| gldas21 | Evap_tavg | mm/year | annual_ANN_12of12 | full | 2000 | 2025 | 26 | 15.58 | 0.04258 | 0.01413 | True | significant at 0.05 (repo MK Yue-Wang; verdict moderate) | False | False | annual | 135 |  |
| gldas21 | Qs_acc | mm/year | annual_ANN_12of12 | full | 2000 | 2025 | 26 | -10.3 | 0.0009456 | 0.0002178 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 135 |  |
| gldas21 | Qsb_acc | mm/year | annual_ANN_12of12 | full | 2000 | 2025 | 26 | -11.11 | 0.5085 | 0.3186 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| gldas21 | precip_total | mm/year | annual_ANN_12of12 | full | 2000 | 2025 | 26 | -12.43 | 0.6593 | 0.5508 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| gldas21 | rainfall_liquid | mm/year | annual_ANN_12of12 | full | 2000 | 2025 | 26 | 9.35 | 0.636 | 0.5749 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| gpm_imerg | precipitation | mm/year | annual_ANN_12of12 | full | 1998 | 2024 | 27 | 2.892 | 0.8025 | 0.8698 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| airs | SurfAirTemp | °C | annual_ANN_12of12 | full | 2003 | 2024 | 22 | 0.8194 | 0.0003076 | 3.601e-05 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 135 | 2025 |
| airs | TotH2OVap | kg/m² (≈mm) | annual_ANN_12of12 | full | 2003 | 2024 | 22 | 0.1468 | 0.07113 | 0.1744 | True | not significant at 0.05 (repo MK Yue-Wang; verdict weak) | False | False | annual | 135 | 2025 |
| modis | NDVI | index | seasonal_JJA_3of3_peak_season | 2001-2025_JJA | 2001 | 2025 | 25 | -0.001173 | 0.6572 | 0.8214 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) [peak season (JJA); season-sensit | False | False | annual | 135 |  |
| modis | NDVI | index | seasonal_AprSep_6of6_growing_season | 2001-2025_AMJJAS | 2001 | 2025 | 25 | -0.001213 | 0.5283 | 0.7709 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) [growing season (Apr-Sep); season | False | False | annual | 135 |  |
| modis | EVI | index | seasonal_JJA_3of3_peak_season | 2001-2025_JJA | 2001 | 2025 | 25 | 0.009392 | 0.09728 | 0.04689 | False | not significant at 0.05 (repo MK Yue-Wang; verdict weak) [peak season (JJA); season-sensit | False | False | annual | 135 |  |
| modis | EVI | index | seasonal_AprSep_6of6_growing_season | 2001-2025_AMJJAS | 2001 | 2025 | 25 | 0.00771 | 0.04713 | 0.02478 | True | significant at 0.05 (repo MK Yue-Wang; verdict moderate) [growing season (Apr-Sep); season | False | False | annual | 135 |  |
| modis | LST_Day | °C | annual_ANN_12of12 | full | 2001 | 2025 | 25 | 0.8214 | 0.003507 | 0.002748 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 135 |  |
| modis | LST_Night | °C | annual_ANN_12of12 | full | 2001 | 2025 | 25 | 0.8686 | 0.0003356 | 3.913e-05 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 135 |  |
| omi | ColumnAmountNO2Trop | molec/cm² | annual_ANN_12of12 | full | 2005 | 2025 | 21 | -6.155e+13 | 0.4955 | 0.5211 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| omi | ColumnAmountNO2TropCloudScreened | molec/cm² | annual_ANN_12of12 | full | 2005 | 2025 | 21 | -2.673e+13 | 0.3748 | 0.5689 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| gpcc | precip | mm/year | annual_ANN_12of12 | full | 1891 | 2025 | 135 | 3.284 | 0.02455 | 0.02657 | True | significant at 0.05 (repo MK Yue-Wang; verdict moderate) | False | True | annual | 135 |  |
| ghcn | TAVG_anom | °C anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 36 | 0.5547 | 0.0003703 | 0.0002884 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) [headline window; note missing year | True | True | annual | 135 |  |
| ghcn | TMAX_anom | °C anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 39 | 0.7057 | 9.589e-06 | 6.205e-06 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 135 |  |
| ghcn | TMIN_anom | °C anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 39 | 0.426 | 0.001892 | 0.001219 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 135 |  |
| ghcn | PRCP_anom | mm/year anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 39 | 10.5 | 0.413 | 0.4216 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| gsom | TAVG_anom | °C anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 39 | 0.5271 | 4.932e-05 | 3.8e-05 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 135 |  |
| gsom | TMAX_anom | °C anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 39 | 0.657 | 4.815e-06 | 4.193e-06 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 135 |  |
| gsom | TMIN_anom | °C anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 39 | 0.4539 | 0.0006083 | 0.0002884 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 135 |  |
| gsom | PRCP_anom | mm/year anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 39 | 17.59 | 0.3926 | 0.2941 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 135 |  |
| grace | TWS | cm EWH anomaly | monthly_deseasonalised_grace_headline_method | headline_grace_method | 2003.04 | 2025.96 | 235 | -11.24 | 1.098e-05 | 4.62e-07 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | monthly | 65 | 2002,2017,2018,2026 |

### Station baseline coverage (v1 limitation: no baseline fallback)

| source | variable | stations_with_data | stations_with_any_baseline_month | stations_with_full_12month_baseline | stations_dropped_no_baseline | stations_ending_before_2006 | station_months_failing_day_rule |
|---|---|---|---|---|---|---|---|
| ghcn | TAVG | 27 | 25 | 25 | 2 | 0 | 1.21e+03 |
| ghcn | TMAX | 27 | 26 | 19 | 1 | 0 | 3.25e+03 |
| ghcn | TMIN | 27 | 26 | 20 | 1 | 0 | 3.97e+03 |
| ghcn | PRCP | 28 | 13 | 6 | 15 | 22 | 7.74e+03 |
| gsom | TAVG | 183 | 36 | 9 | 147 | 49 |  |
| gsom | TMAX | 186 | 39 | 15 | 147 | 45 |  |
| gsom | TMIN | 186 | 37 | 9 | 149 | 11 |  |
| gsom | PRCP | 201 | 21 | 10 | 180 | 190 |  |

### Station counts per trend window (annual 12/12)

| source | variable | window | headline | n | missing_years | stations_min | stations_median | lin_slope_per_decade | robust_call |
|---|---|---|---|---|---|---|---|---|---|
| ghcn | TAVG_anom | full_gappy | False | 140 | 1941,1943,2007,2008,2009 | 1 | 11 | 0.129 | gappy window: 5 missing years (1941, 1943, 2007-2009), n=140; not treated as robust - use 1981-2019 station window |
| ghcn | TAVG_anom | 1981-2025_gappy | False | 42 | 2007,2008,2009 | 2 | 25 | 0.634 | gappy window: 3 missing years (2007-2009), n=42; not treated as robust - use 1981-2019 station window |
| ghcn | TAVG_anom | 2001-2025_gappy | False | 22 | 2007,2008,2009 | 2 | 22 | 0.98 | gappy window: 3 missing years (2007-2009), n=22; not treated as robust - use 1981-2019 station window |
| ghcn | TAVG_anom | 1981-2019_station_window | True | 36 | 2007,2008,2009 | 9 | 25 | 0.555 | significant at 0.05 (repo MK Yue-Wang; verdict strong) [headline window; note missing years 2007-2009, n=36] |
| ghcn | TMAX_anom | full_gappy | False | 142 | 1883,1884 | 1 | 12 | 0.164 | gappy window: 2 missing years (1883-1884), n=142; not treated as robust - use 1981-2019 station window |
| ghcn | TMAX_anom | 1981-2025 | False | 45 |  | 1 | 19 | 0.734 | significant at 0.05 (repo MK Yue-Wang; verdict strong) |
| ghcn | TMAX_anom | 2001-2025 | False | 25 |  | 1 | 17 | 0.874 | significant at 0.05 (repo MK Yue-Wang; verdict strong) |
| ghcn | TMAX_anom | 1981-2019_station_window | True | 39 |  | 4 | 20 | 0.706 | significant at 0.05 (repo MK Yue-Wang; verdict strong) |
| ghcn | TMIN_anom | full_gappy | False | 140 | 1883,1884,2021,2022 | 1 | 12 | 0.177 | gappy window: 4 missing years (1883-1884, 2021-2022), n=140; not treated as robust - use 1981-2019 station window |
| ghcn | TMIN_anom | 1981-2025_gappy | False | 43 | 2021,2022 | 1 | 19 | 0.524 | gappy window: 2 missing years (2021-2022), n=43; not treated as robust - use 1981-2019 station window |
| ghcn | TMIN_anom | 2001-2025_gappy | False | 23 | 2021,2022 | 1 | 16 | 0.679 | gappy window: 2 missing years (2021-2022), n=23; not treated as robust - use 1981-2019 station window |
| ghcn | TMIN_anom | 1981-2019_station_window | True | 39 |  | 4 | 21 | 0.426 | significant at 0.05 (repo MK Yue-Wang; verdict strong) |
| ghcn | PRCP_anom | full_gappy | False | 141 | 1942,2021 | 1 | 6 | 8.7 | gappy window: 2 missing years (1942, 2021), n=141; not treated as robust - use 1981-2019 station window |
| ghcn | PRCP_anom | 1981-2019_station_window | True | 39 |  | 1 | 6 | 10.5 | not significant at 0.05 (repo MK Yue-Wang; verdict none) |
| gsom | TAVG_anom | full_gappy | False | 120 | 1941,2020,2021,2022,2023,2024 | 1 | 11 | 0.152 | gappy window: 6 missing years (1941, 2020-2024), n=120; not treated as robust - use 1981-2019 station window |
| gsom | TAVG_anom | 1981-2025_gappy | False | 40 | 2020,2021,2022,2023,2024 | 1 | 17 | 0.525 | gappy window: 5 missing years (2020-2024), n=40; not treated as robust - use 1981-2019 station window |
| gsom | TAVG_anom | 2001-2025_gappy | False | 20 | 2020,2021,2022,2023,2024 | 1 | 9 | 0.555 | gappy window: 5 missing years (2020-2024), n=20; not treated as robust - use 1981-2019 station window |
| gsom | TAVG_anom | 1981-2019_station_window | True | 39 |  | 4 | 17 | 0.527 | significant at 0.05 (repo MK Yue-Wang; verdict strong) |
| gsom | TMAX_anom | full_gappy | False | 124 | 2021,2024 | 1 | 18 | 0.163 | gappy window: 2 missing years (2021, 2024), n=124; not treated as robust - use 1981-2019 station window |
| gsom | TMAX_anom | 1981-2025_gappy | False | 43 | 2021,2024 | 1 | 26 | 0.669 | gappy window: 2 missing years (2021, 2024), n=43; not treated as robust - use 1981-2019 station window |
| gsom | TMAX_anom | 2001-2025_gappy | False | 23 | 2021,2024 | 1 | 22 | 0.752 | gappy window: 2 missing years (2021, 2024), n=23; not treated as robust - use 1981-2019 station window |
| gsom | TMAX_anom | 1981-2019_station_window | True | 39 |  | 4 | 27 | 0.657 | significant at 0.05 (repo MK Yue-Wang; verdict strong) |
| gsom | TMIN_anom | full_gappy | False | 121 | 2020,2021,2022,2023,2024 | 1 | 12 | 0.161 | gappy window: 5 missing years (2020-2024), n=121; not treated as robust - use 1981-2019 station window |
| gsom | TMIN_anom | 1981-2025_gappy | False | 40 | 2020,2021,2022,2023,2024 | 1 | 18 | 0.477 | gappy window: 5 missing years (2020-2024), n=40; not treated as robust - use 1981-2019 station window |
| gsom | TMIN_anom | 2001-2025_gappy | False | 20 | 2020,2021,2022,2023,2024 | 1 | 10 | 0.542 | gappy window: 5 missing years (2020-2024), n=20; not treated as robust - use 1981-2019 station window |
| gsom | TMIN_anom | 1981-2019_station_window | True | 39 |  | 4 | 19 | 0.454 | significant at 0.05 (repo MK Yue-Wang; verdict strong) |
| gsom | PRCP_anom | full_gappy | False | 124 | 2021 | 2 | 10 | 10.8 | gappy window: 1 missing years (2021), n=124; not treated as robust - use 1981-2019 station window |
| gsom | PRCP_anom | 1981-2019_station_window | True | 39 |  | 4 | 10 | 17.6 | not significant at 0.05 (repo MK Yue-Wang; verdict none) |

## Region `ukraine_mask`

Bounds [22.13283980300011, 44.38104889500005, 40.1595430910001, 52.36894928000008]; 73 series; 21.1 s.

### Source status

| source | status | details |
|---|---|---|
| nasa_power | ok | {} |
| grace | ok | {"file": "$GLOBAL_DATA/grace/GRCTellus.JPL.200204_202609.GLO.RL06.3M.MSCNv04CRI.nc", "n_mascons": 13, "n_land_cells_weight_gt0": 347, "time_center_vs_csv_max_days": 0} |
| hadcrut5 | ok | {"n_cells_weight_gt0": 11, "sum_frac": 2.945995604365763} |
| gistemp | ok | {"n_cells_weight_gt0": 36} |
| berkeley | ok | {"n_cells_weight_gt0": 110, "weight": "area x overlap x land_mask fraction"} |
| chirps | ok | {"path": "global_grid_overlap_weights", "file": "$GLOBAL_DATA/chirps_v3/chirps-v3.0.monthly.nc", "cache": "chirps_ukraine_mask_f07596e81c21681d.parquet"} |
| cci_sm | ok | {"note": "record 1978-11..1991-12 only"} |
| merra2 | ok | {"path": "global_grid_overlap_weights", "products": [{"product": "merra2_slv", "dir": "$GLOBAL_DATA/merra2_slv_slim", "n_files": 561, "window_cells": "17x30", "cache": "merra2_slv_ukraine_mask_47fb1faeac2be7b0.parquet", "status": "cached"}, {"product": "merra2_flx", "dir": "$GLOBAL_DATA/merra2_flx_slim", "n_files": 561, "window_cells": "17x30", "cache": "merra2_flx_ukraine_mask_494248df7fdf5af7.pa |
| gldas20 | ok | {"path": "global_grid_overlap_weights", "products": [{"product": "gldas20", "dir": "$GLOBAL_DATA/gldas20_slim", "n_files": 804, "window_cells": "33x73", "cache": "gldas20_ukraine_mask_8d02d9418c0b4a68.parquet", "status": "cached"}, {"product": "gldas20_rainf", "dir": "$GLOBAL_DATA/gldas20_rainf", "n_files": 804, "window_cells": "33x73", "cache": "gldas20_rainf_ukraine_mask_4e71ae1eca7dc5ae.parquet |
| gldas21 | ok | {"path": "global_grid_overlap_weights", "products": [{"product": "gldas21", "dir": "$GLOBAL_DATA/gldas21_slim", "n_files": 319, "window_cells": "33x73", "cache": "gldas21_ukraine_mask_8a5181b69ec82658.parquet", "status": "cached"}, {"product": "gldas21_rainf", "dir": "$GLOBAL_DATA/gldas21_rainf", "n_files": 319, "window_cells": "33x73", "cache": "gldas21_rainf_ukraine_mask_4732f96b3f3fc176.parquet |
| gpm_imerg | ok | {"path": "global_grid_overlap_weights", "products": [{"product": "gpm_imerg", "dir": "$GLOBAL_DATA/gpm_imerg_slim", "n_files": 333, "window_cells": "81x181", "cache": "gpm_imerg_ukraine_mask_b8048aca7b5fdac0.parquet", "status": "cached"}]} |
| airs | ok | {"path": "global_grid_overlap_weights", "products": [{"product": "airs", "dir": "$GLOBAL_DATA/airs3stm_slim", "n_files": 290, "window_cells": "9x19", "cache": "airs_ukraine_mask_50fa0a881b14bcdf.parquet", "status": "cached"}]} |
| modis | ok | {"path": "global_grid_overlap_weights", "products": [{"product": "mod13c2_qc", "dir": "$GLOBAL_DATA/mod13c2_slim", "n_files": 321, "window_cells": "161x362", "cache": "mod13c2_qc_ukraine_mask_4cf3c5064736f0f2.parquet", "status": "cached"}, {"product": "mod11c3_qc", "dir": "$GLOBAL_DATA/mod11c3_slim", "n_files": 321, "window_cells": "161x362", "cache": "mod11c3_qc_ukraine_mask_73cdd1e538dd1383.parq |
| omi | skipped | {"reason": "samples hold only a pre-computed Ukraine-bbox mean (no grid); not valid for this region"} |
| gpcc | ok | {"path": "global_grid_overlap_weights", "n_files": 47, "cache": "gpcc_ukraine_mask_7c476e697564856a.parquet"} |
| cru_cy | ok | {"mask": "CRU-CY country mask; Crimea in/out undocumented -> mask mismatch vs region"} |
| berkeley_country | ok | {"mask": "Berkeley polygon 553,101 km\u00b2, 45.21-52.37N: Crimea EXCLUDED"} |
| ghcn | ok | {"n_stations_in_region": 27, "n_qflag_values_removed": 4022} |
| gsom | ok | {"n_stations_in_region": 191} |
| swot | skipped | {"reason": "samples hold only a pre-computed Ukraine-bbox mean (no grid); not valid for this region"} |

### Per-variable QC

| source | variable | unit | first | last | pct_valid_raw | pct_valid_gap_excluded | n_gaps | longest_gap_months | complete_years | min_coverage_frac | min_n_valid | baseline | flag_counts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nasa_power | T2M | °C | 1981-01 | 2025-12 | 100 | 100 | 0 | 0 | 45 | 0.999 | 295 | 1991-2020 |  |
| nasa_power | T2M_MAX | °C | 1981-01 | 2025-12 | 100 | 100 | 0 | 0 | 45 | 0.999 | 295 | 1991-2020 |  |
| nasa_power | T2M_MIN | °C | 1981-01 | 2025-12 | 100 | 100 | 0 | 0 | 45 | 0.999 | 295 | 1991-2020 |  |
| nasa_power | PRECTOTCORR | mm/month | 1981-01 | 2025-12 | 100 | 100 | 0 | 0 | 45 | 0.999 | 295 | 1991-2020 |  |
| nasa_power | QV2M | g/kg | 1981-01 | 2025-12 | 100 | 100 | 0 | 0 | 45 | 0.999 | 295 | 1991-2020 |  |
| nasa_power | WS10M | m/s | 1981-01 | 2025-12 | 100 | 100 | 0 | 0 | 45 | 0.999 | 295 | 1991-2020 |  |
| nasa_power | ALLSKY_SFC_SW_DWN | kWh/m²/day | 2001-01 | 2025-12 | 100 | 100 | 0 | 0 | 25 | 0.991 | 103 | 1991-2020 | partial_year=204; missing_value=204 |
| derived | DTR | °C | 1981-01 | 2025-12 | 100 | 100 | 0 | 0 | 45 |  | 295 | 1991-2020 | derived_from_POWER_T2M_MAX_minus_T2M_MIN=540 |
| grace | TWS | cm EWH anomaly | 2002-04 | 2026-09 | 88.8 | 100 | 18 | 11 | 14 | 0.989 | 347 | record_mean | partial_year=126; missing_month_official=33; missing_value=33; grace_gracefo_gap=11 |
| hadcrut5 | tas_anomaly | °C anomaly (1961-1990) | 1850-01 | 2026-09 | 100 | 100 | 0 | 0 | 176 | 1 | 11 | 1991-2020 | coarse_cells_extend_beyond_region=2121; partial_year=9; outlier_5sigma=2 |
| gistemp | tas_anomaly | °C anomaly (1951-1980) | 1880-01 | 2026-10 | 100 | 100 | 0 | 0 | 146 | 1 | 36 | 1991-2020 | coarse_cells_extend_beyond_region=1762; partial_year=10; outlier_5sigma=4 |
| berkeley | tas_anomaly | °C anomaly (1951-1980) | 1750-01 | 2024-12 | 100 | 100 | 1 | 1 | 274 | 0.95 | 107 | 1991-2020 | partial_year=12; outlier_5sigma=2; missing_value=1 |
| chirps | precip | mm/month | 1981-01 | 2026-09 | 100 | 100 | 0 | 0 | 45 | 1 | 3.04e+04 | 1991-2020 | partial_year=9 |
| cci_sm | sm | m³/m³ | 1978-11 | 2024-12 | 100 | 100 | 0 | 0 | 46 | 0.121 | 160 | 1991-2020 | partial_record_1978-1991=554; winter_low_coverage=554; partial_year=2 |
| merra2 | T2M | °C | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 299 | 1991-2020 | partial_year=9 |
| merra2 | QV2M | g/kg | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 299 | 1991-2020 | partial_year=9 |
| merra2 | SLP | hPa | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 299 | 1991-2020 | partial_year=9 |
| merra2 | PRECTOTCORR | mm/month | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 299 | 1991-2020 | partial_year=9 |
| merra2 | PRECTOT | mm/month | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 299 | 1991-2020 | partial_year=9 |
| merra2 | U10M | m/s | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 299 | 1991-2020 | partial_year=9 |
| merra2 | V10M | m/s | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 299 | 1991-2020 | partial_year=9 |
| merra2 | WS10M_from_mean_UV | m/s | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 299 | 1991-2020 | speed_of_monthly_mean_wind_underestimates_mean_speed=561; partial_year=9 |
| merra2 | T2MMAX | °C | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 299 | 1991-2020 | partial_year=9 |
| merra2 | T2MMIN | °C | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 299 | 1991-2020 | partial_year=9 |
| merra2 | DTR | °C | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 299 | 1991-2020 | partial_year=9 |
| gldas20 | SoilMoi0_10cm_inst | kg/m² (≈mm) | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.982 | 1.28e+03 | 1991-2020 |  |
| gldas20 | RootMoist_inst | kg/m² (≈mm) | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.982 | 1.28e+03 | 1991-2020 |  |
| gldas20 | SWE_inst | kg/m² (≈mm) | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.982 | 1.28e+03 | 1991-2020 | outlier_5sigma=9 |
| gldas20 | Tair_f_inst | °C | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.987 | 1.29e+03 | 1991-2020 |  |
| gldas20 | Evap_tavg | mm/month | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.982 | 1.28e+03 | 1991-2020 | outlier_5sigma=1 |
| gldas20 | Qs_acc | mm/month | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.982 | 1.28e+03 | 1991-2020 | outlier_5sigma=6 |
| gldas20 | Qsb_acc | mm/month | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.982 | 1.28e+03 | 1991-2020 | outlier_5sigma=4 |
| gldas20 | precip_total | mm/month | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.987 | 1.29e+03 | 1991-2020 |  |
| gldas20 | snowfall | mm/month | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.982 | 1.28e+03 | 1991-2020 | outlier_5sigma=1 |
| gldas20 | rainfall_liquid | mm/month | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.982 | 1.28e+03 | 1991-2020 |  |
| gldas21 | SoilMoi0_10cm_inst | kg/m² (≈mm) | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.982 | 1.28e+03 | 1991-2020 | partial_year=7 |
| gldas21 | RootMoist_inst | kg/m² (≈mm) | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.982 | 1.28e+03 | 1991-2020 | partial_year=7 |
| gldas21 | SWE_inst | kg/m² (≈mm) | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.982 | 1.28e+03 | 1991-2020 | partial_year=7; outlier_5sigma=2 |
| gldas21 | Tair_f_inst | °C | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.987 | 1.29e+03 | 1991-2020 | partial_year=7 |
| gldas21 | Evap_tavg | mm/month | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.982 | 1.28e+03 | 1991-2020 | partial_year=7 |
| gldas21 | Qs_acc | mm/month | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.982 | 1.28e+03 | 1991-2020 | partial_year=7; outlier_5sigma=3 |
| gldas21 | Qsb_acc | mm/month | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.982 | 1.28e+03 | 1991-2020 | partial_year=7; outlier_5sigma=1 |
| gldas21 | precip_total | mm/month | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.987 | 1.29e+03 | 1991-2020 | partial_year=7 |
| gldas21 | snowfall | mm/month | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.982 | 1.28e+03 | 1991-2020 | partial_year=7 |
| gldas21 | rainfall_liquid | mm/month | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.982 | 1.28e+03 | 1991-2020 | partial_year=7 |
| gpm_imerg | precipitation | mm/month | 1998-01 | 2025-09 | 100 | 100 | 0 | 0 | 27 | 1 | 7.81e+03 | 1991-2020 | partial_year=9 |
| airs | SurfAirTemp | °C | 2002-09 | 2026-10 | 100 | 100 | 0 | 0 | 23 | 1 | 110 | record_mean | partial_year=14; airs_2025_bias_unverified=12 |
| airs | TotH2OVap | kg/m² (≈mm) | 2002-09 | 2026-10 | 100 | 100 | 0 | 0 | 23 | 1 | 110 | record_mean | partial_year=14; airs_2025_bias_unverified=12 |
| modis | NDVI | index | 2000-02 | 2026-10 | 100 | 100 | 0 | 0 | 25 | 0.0933 | 2.8e+03 | 1991-2020 | qc_pixel_masked=321; terra_only=321; vi_winter_snow_masked_sampling=321; qc_low_coverage_lt50pct=22; partial_year=21 |
| modis | EVI | index | 2000-02 | 2026-10 | 100 | 100 | 0 | 0 | 25 | 0.0933 | 2.8e+03 | 1991-2020 | qc_pixel_masked=321; terra_only=321; vi_winter_snow_masked_sampling=321; qc_low_coverage_lt50pct=22; partial_year=21 |
| modis | LST_Day | °C | 2000-02 | 2026-10 | 100 | 100 | 0 | 0 | 25 | 0.87 | 2.64e+04 | 1991-2020 | qc_pixel_masked=321; terra_only=321; lst_clear_sky_winter_bias=321; partial_year=21 |
| modis | LST_Night | °C | 2000-02 | 2026-10 | 100 | 100 | 0 | 0 | 25 | 0.975 | 2.95e+04 | 1991-2020 | qc_pixel_masked=321; terra_only=321; lst_clear_sky_winter_bias=321; partial_year=21 |
| modis | LST_Day_clear_days | days | 2000-02 | 2026-10 | 100 | 100 | 0 | 0 | 25 | 0.87 | 2.64e+04 | 1991-2020 | qc_pixel_masked=321; terra_only=321; partial_year=21 |
| modis | LST_Night_clear_days | days | 2000-02 | 2026-10 | 100 | 100 | 0 | 0 | 25 | 0.975 | 2.95e+04 | 1991-2020 | qc_pixel_masked=321; terra_only=321; partial_year=21 |
| gpcc | precip | mm/month | 1891-01 | 2026-08 | 100 | 100 | 0 | 0 | 135 | 1 | 110 | 1991-2020 | partial_year=8 |
| cru_cy | tmp | °C | 1901-01 | 2025-12 | 100 | 100 | 0 | 0 | 125 |  |  | 1991-2020 | own_country_mask=1500; crimea_undocumented=1500; absolute_not_anomaly=1500; outlier_5sigma=1 |
| cru_cy | tmp_anom | °C anomaly (1961-1990) | 1901-01 | 2025-12 | 100 | 100 | 0 | 0 | 125 |  |  | 1991-2020 | own_country_mask=1500; crimea_undocumented=1500; outlier_5sigma=1 |
| cru_cy | tmn | °C | 1901-01 | 2025-12 | 100 | 100 | 0 | 0 | 125 |  |  | 1991-2020 | own_country_mask=1500; crimea_undocumented=1500; outlier_5sigma=4 |
| cru_cy | tmx | °C | 1901-01 | 2025-12 | 100 | 100 | 0 | 0 | 125 |  |  | 1991-2020 | own_country_mask=1500; crimea_undocumented=1500 |
| cru_cy | dtr | °C | 1901-01 | 2025-12 | 100 | 100 | 0 | 0 | 125 |  |  | 1991-2020 | own_country_mask=1500; crimea_undocumented=1500 |
| cru_cy | pre | mm/month | 1901-01 | 2025-12 | 100 | 100 | 0 | 0 | 125 |  |  | 1991-2020 | own_country_mask=1500; crimea_undocumented=1500 |
| cru_cy | pet | mm/month | 1901-01 | 2025-12 | 100 | 100 | 0 | 0 | 125 |  |  | 1991-2020 | own_country_mask=1500; crimea_undocumented=1500 |
| cru_cy | vap | hPa | 1901-01 | 2025-12 | 100 | 100 | 0 | 0 | 125 |  |  | 1991-2020 | own_country_mask=1500; crimea_undocumented=1500 |
| cru_cy | wet | days | 1901-01 | 2025-12 | 100 | 100 | 0 | 0 | 125 |  |  | 1991-2020 | own_country_mask=1500; crimea_undocumented=1500 |
| berkeley_country | tas_anomaly | °C anomaly (1951-1980) | 1750-01 | 2020-12 | 99.8 | 99.8 | 4 | 5 | 267 |  |  | 1991-2020 | own_country_mask=3252; crimea_excluded=3252; mask_mismatch_vs_region=3252; partial_year=48; missing_value=8; outlier_5sigma=3 |
| ghcn | TAVG_anom | °C anomaly (1991-2020) | 1881-01 | 2026-10 | 99.4 | 99.4 | 6 | 3 | 140 | 0.04 | 1 | 1991-2020 | station_anomaly_mean=1750; UP_stations_only=1750; few_stations_lt3=186; partial_year=70; missing_value=11; outlier_5sigma=3 |
| ghcn | TMAX_anom | °C anomaly (1991-2020) | 1881-01 | 2026-10 | 99.7 | 99.7 | 4 | 2 | 142 | 0.0385 | 1 | 1991-2020 | station_anomaly_mean=1750; UP_stations_only=1750; few_stations_lt3=173; partial_year=46; missing_value=5 |
| ghcn | TMIN_anom | °C anomaly (1991-2020) | 1881-01 | 2026-10 | 99.6 | 99.6 | 6 | 2 | 140 | 0.0385 | 1 | 1991-2020 | station_anomaly_mean=1750; UP_stations_only=1750; few_stations_lt3=82; partial_year=70; missing_value=7; outlier_5sigma=3 |
| ghcn | PRCP_anom | mm/month anomaly (1991-2020) | 1881-01 | 2025-07 | 99.8 | 99.8 | 3 | 1 | 141 | 0.0769 | 1 | 1991-2020 | station_anomaly_mean=1735; UP_stations_only=1735; few_stations_lt3=195; partial_year=43; missing_value=3; outlier_5sigma=1 |
| gsom | TAVG_anom | °C anomaly (1991-2020) | 1900-01 | 2026-10 | 98.5 | 98.5 | 9 | 5 | 120 | 0.0286 | 1 | 1991-2020 | station_anomaly_mean=1522; UP_stations_only=1522; partial_year=82; missing_value=23; few_stations_lt3=12; outlier_5sigma=3 |
| gsom | TMAX_anom | °C anomaly (1991-2020) | 1900-01 | 2026-10 | 99.7 | 99.7 | 4 | 2 | 124 | 0.0263 | 1 | 1991-2020 | station_anomaly_mean=1522; UP_stations_only=1522; partial_year=34; few_stations_lt3=8; missing_value=5 |
| gsom | TMIN_anom | °C anomaly (1991-2020) | 1900-01 | 2026-10 | 98.5 | 98.5 | 8 | 5 | 121 | 0.0278 | 1 | 1991-2020 | station_anomaly_mean=1522; UP_stations_only=1522; partial_year=70; missing_value=22; few_stations_lt3=10; outlier_5sigma=4 |
| gsom | PRCP_anom | mm/month anomaly (1991-2020) | 1900-01 | 2025-07 | 99.9 | 99.9 | 1 | 1 | 124 | 0.1 | 2 | 1991-2020 | station_anomaly_mean=1507; UP_stations_only=1507; few_stations_lt3=67; partial_year=19; outlier_5sigma=1; missing_value=1 |

### Headline trends (annual full window; stations 1981-2019; GRACE = headline method, monthly; VI = peak-season JJA and growing-season Apr-Sep)

`mt_bonferroni_pass` / `mt_bh_pass` are Bonferroni / Benjamini-Hochberg (q<0.05) on the primary Yue-Wang p-value, across the whole test family (all windows and roles; family size in `n_tests_in_family`). `yw_ols_neff_agree` is the OLS effective-n cross-check. HAC / Hamed-Rao are sensitivity only (`sensitivity_call_hac_hr`). Forcing/sampling diagnostics, different-convention rows and the annual VI rows are not headlines (column `role` in trends.csv).

| source | variable | unit | series | window | start | end | n | lin_slope_per_decade | yw_p | yw_ols_neff_p | yw_ols_neff_agree | robust_call | mt_bonferroni_pass | mt_bh_pass | test_family | n_tests_in_family | excluded_years |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nasa_power | T2M | °C | annual_ANN_12of12 | full | 1981 | 2025 | 45 | 0.5561 | 2.083e-05 | 1.249e-05 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| nasa_power | T2M_MAX | °C | annual_ANN_12of12 | full | 1981 | 2025 | 45 | 0.5685 | 4.396e-05 | 3.881e-06 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| nasa_power | T2M_MIN | °C | annual_ANN_12of12 | full | 1981 | 2025 | 45 | 0.6192 | 0.003143 | 0.0008879 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| nasa_power | PRECTOTCORR | mm/year | annual_ANN_12of12 | full | 1981 | 2025 | 45 | 10.13 | 0.07663 | 0.2245 | True | not significant at 0.05 (repo MK Yue-Wang; verdict weak) | False | False | annual | 161 |  |
| nasa_power | QV2M | g/kg | annual_ANN_12of12 | full | 1981 | 2025 | 45 | 0.1436 | 0.0003239 | 0.0003586 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| nasa_power | WS10M | m/s | annual_ANN_12of12 | full | 1981 | 2025 | 45 | -0.02186 | 0.03286 | 0.1533 | False | significant at 0.05 (repo MK Yue-Wang; verdict moderate) | False | False | annual | 161 |  |
| nasa_power | ALLSKY_SFC_SW_DWN | kWh/m²/day | annual_ANN_12of12 | full | 2001 | 2025 | 25 | 0.04963 | 0.04217 | 0.03798 | True | significant at 0.05 (repo MK Yue-Wang; verdict moderate) | False | False | annual | 161 |  |
| derived | DTR | °C | annual_ANN_12of12 | full | 1981 | 2025 | 45 | -0.05076 | 0.3859 | 0.6701 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| hadcrut5 | tas_anomaly | °C anomaly (1961-1990) | annual_ANN_12of12 | full | 1850 | 2025 | 176 | 0.09569 | 1.452e-07 | 1.701e-08 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| gistemp | tas_anomaly | °C anomaly (1951-1980) | annual_ANN_12of12 | full | 1880 | 2025 | 146 | 0.1606 | 6.807e-11 | 3.663e-12 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| berkeley | tas_anomaly | °C anomaly (1951-1980) | annual_ANN_12of12 | full | 1750 | 2024 | 274 | 0.06112 | 1.625e-10 | 5.231e-12 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| chirps | precip | mm/year | annual_ANN_12of12 | full | 1981 | 2025 | 45 | -4.583 | 0.9766 | 0.684 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| cci_sm | sm | m³/m³ | annual_ANN_12of12 | full | 1979 | 2024 | 46 | -0.0007456 | 0.3707 | 0.4482 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| merra2 | T2M | °C | annual_ANN_12of12 | full | 1980 | 2025 | 46 | 0.5893 | 3.375e-06 | 1.206e-06 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| merra2 | QV2M | g/kg | annual_ANN_12of12 | full | 1980 | 2025 | 46 | 0.1368 | 0.0008303 | 0.001074 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| merra2 | SLP | hPa | annual_ANN_12of12 | full | 1980 | 2025 | 46 | -0.1052 | 0.3437 | 0.2712 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| merra2 | PRECTOTCORR | mm/year | annual_ANN_12of12 | full | 1980 | 2025 | 46 | 1.515 | 0.2929 | 0.8995 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| merra2 | PRECTOT | mm/year | annual_ANN_12of12 | full | 1980 | 2025 | 46 | 0.6042 | 0.6777 | 0.9654 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| merra2 | U10M | m/s | annual_ANN_12of12 | full | 1980 | 2025 | 46 | -0.03989 | 0.57 | 0.4538 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| merra2 | V10M | m/s | annual_ANN_12of12 | full | 1980 | 2025 | 46 | -0.02519 | 0.2114 | 0.2083 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| merra2 | WS10M_from_mean_UV | m/s | annual_ANN_12of12 | full | 1980 | 2025 | 46 | -0.02121 | 0.5285 | 0.4953 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| merra2 | T2MMAX | °C | annual_ANN_12of12 | full | 1980 | 2025 | 46 | 0.6358 | 1.88e-06 | 4.744e-07 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| merra2 | T2MMIN | °C | annual_ANN_12of12 | full | 1980 | 2025 | 46 | 0.5784 | 2.384e-05 | 9.31e-06 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| merra2 | DTR | °C | annual_ANN_12of12 | full | 1980 | 2025 | 46 | 0.05748 | 0.2247 | 0.1625 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas20 | SoilMoi0_10cm_inst | kg/m² (≈mm) | annual_ANN_12of12 | full | 1948 | 2014 | 67 | 0.06012 | 0.893 | 0.6894 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas20 | RootMoist_inst | kg/m² (≈mm) | annual_ANN_12of12 | full | 1948 | 2014 | 67 | 2.114 | 0.6963 | 0.3449 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas20 | SWE_inst | kg/m² (≈mm) | annual_ANN_12of12 | full | 1948 | 2014 | 67 | -0.1951 | 0.8215 | 0.6103 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas20 | Tair_f_inst | °C | annual_ANN_12of12 | full | 1948 | 2014 | 67 | 0.2234 | 0.0002307 | 0.000155 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| gldas20 | Evap_tavg | mm/year | annual_ANN_12of12 | full | 1948 | 2014 | 67 | 5.805 | 0.004242 | 0.001764 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| gldas20 | Qs_acc | mm/year | annual_ANN_12of12 | full | 1948 | 2014 | 67 | -0.4166 | 0.3907 | 0.3698 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas20 | Qsb_acc | mm/year | annual_ANN_12of12 | full | 1948 | 2014 | 67 | 0.9037 | 0.4574 | 0.7312 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas20 | precip_total | mm/year | annual_ANN_12of12 | full | 1948 | 2014 | 67 | 4.07 | 0.2296 | 0.3343 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas20 | snowfall | mm/year | annual_ANN_12of12 | full | 1948 | 2014 | 67 | -1.567 | 0.6714 | 0.5841 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas20 | rainfall_liquid | mm/year | annual_ANN_12of12 | full | 1948 | 2014 | 67 | 5.647 | 0.1217 | 0.131 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas21 | SoilMoi0_10cm_inst | kg/m² (≈mm) | annual_ANN_12of12 | full | 2000 | 2025 | 26 | -1.43 | 0.002488 | 0.002976 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| gldas21 | RootMoist_inst | kg/m² (≈mm) | annual_ANN_12of12 | full | 2000 | 2025 | 26 | -16.59 | 0.007709 | 0.007062 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| gldas21 | Tair_f_inst | °C | annual_ANN_12of12 | full | 2000 | 2025 | 26 | 0.9538 | 0.0003333 | 0.0001415 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| gldas21 | Evap_tavg | mm/year | annual_ANN_12of12 | full | 2000 | 2025 | 26 | 10.8 | 0.3106 | 0.1261 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas21 | Qs_acc | mm/year | annual_ANN_12of12 | full | 2000 | 2025 | 26 | -10.87 | 0.0004209 | 0.0004918 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| gldas21 | Qsb_acc | mm/year | annual_ANN_12of12 | full | 2000 | 2025 | 26 | -10.59 | 0.4536 | 0.3395 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas21 | precip_total | mm/year | annual_ANN_12of12 | full | 2000 | 2025 | 26 | -18.33 | 0.378 | 0.3863 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas21 | rainfall_liquid | mm/year | annual_ANN_12of12 | full | 2000 | 2025 | 26 | 4.289 | 0.7755 | 0.8082 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gpm_imerg | precipitation | mm/year | annual_ANN_12of12 | full | 1998 | 2024 | 27 | -5.827 | 0.6465 | 0.7337 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| airs | SurfAirTemp | °C | annual_ANN_12of12 | full | 2003 | 2024 | 22 | 0.8282 | 0.0005292 | 6.065e-05 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 | 2025 |
| airs | TotH2OVap | kg/m² (≈mm) | annual_ANN_12of12 | full | 2003 | 2024 | 22 | 0.1353 | 0.1426 | 0.2199 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 | 2025 |
| modis | NDVI | index | seasonal_JJA_3of3_peak_season | 2001-2025_JJA | 2001 | 2025 | 25 | -0.0006034 | 0.5283 | 0.9184 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) [peak season (JJA); season-sensit | False | False | annual | 161 |  |
| modis | NDVI | index | seasonal_AprSep_6of6_growing_season | 2001-2025_AMJJAS | 2001 | 2025 | 25 | -0.003215 | 0.4137 | 0.4791 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) [growing season (Apr-Sep); season | False | False | annual | 161 |  |
| modis | EVI | index | seasonal_JJA_3of3_peak_season | 2001-2025_JJA | 2001 | 2025 | 25 | 0.01142 | 0.04713 | 0.02961 | True | significant at 0.05 (repo MK Yue-Wang; verdict moderate) [peak season (JJA); season-sensit | False | False | annual | 161 |  |
| modis | EVI | index | seasonal_AprSep_6of6_growing_season | 2001-2025_AMJJAS | 2001 | 2025 | 25 | 0.007063 | 0.1412 | 0.05102 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) [growing season (Apr-Sep); season | False | False | annual | 161 |  |
| modis | LST_Day | °C | annual_ANN_12of12 | full | 2001 | 2025 | 25 | 0.889 | 0.003016 | 0.002462 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| modis | LST_Night | °C | annual_ANN_12of12 | full | 2001 | 2025 | 25 | 0.858 | 0.0002986 | 3.001e-05 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| gpcc | precip | mm/year | annual_ANN_12of12 | full | 1891 | 2025 | 135 | 2.578 | 0.07195 | 0.09849 | True | not significant at 0.05 (repo MK Yue-Wang; verdict weak) | False | False | annual | 161 |  |
| cru_cy | tmp | °C | annual_ANN_12of12 | full | 1901 | 2025 | 125 | 0.1701 | 6.846e-08 | 1.03e-08 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| cru_cy | tmp_anom | °C anomaly (1961-1990) | annual_ANN_12of12 | full | 1901 | 2025 | 125 | 0.1701 | 6.976e-08 | 1.03e-08 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| cru_cy | tmn | °C | annual_ANN_12of12 | full | 1901 | 2025 | 125 | 0.194 | 3.587e-11 | 4.95e-12 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| cru_cy | tmx | °C | annual_ANN_12of12 | full | 1901 | 2025 | 125 | 0.1464 | 3.242e-05 | 7.135e-06 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| cru_cy | dtr | °C | annual_ANN_12of12 | full | 1901 | 2025 | 125 | -0.04758 | 0.0005158 | 0.0003013 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| cru_cy | pre | mm/year | annual_ANN_12of12 | full | 1901 | 2025 | 125 | 2.225 | 0.1641 | 0.1891 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| cru_cy | pet | mm/year | annual_ANN_12of12 | full | 1901 | 2025 | 125 | 3.832 | 0.02941 | 0.0238 | True | significant at 0.05 (repo MK Yue-Wang; verdict moderate) | False | False | annual | 161 |  |
| cru_cy | vap | hPa | annual_ANN_12of12 | full | 1901 | 2025 | 125 | 0.07141 | 2.517e-10 | 6.895e-12 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| cru_cy | wet | days | annual_ANN_12of12 | full | 1901 | 2025 | 125 | -0.7726 | 0.009316 | 0.014 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| berkeley_country | tas_anomaly | °C anomaly (1951-1980) | annual_ANN_12of12 | full | 1751 | 2020 | 267 | 0.05422 | 6.852e-09 | 4.535e-10 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| ghcn | TAVG_anom | °C anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 36 | 0.5547 | 0.0003703 | 0.0002884 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) [headline window; note missing year | False | True | annual | 161 |  |
| ghcn | TMAX_anom | °C anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 39 | 0.7057 | 9.589e-06 | 6.205e-06 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| ghcn | TMIN_anom | °C anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 39 | 0.426 | 0.001892 | 0.001219 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| ghcn | PRCP_anom | mm/year anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 39 | 10.5 | 0.413 | 0.4216 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gsom | TAVG_anom | °C anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 39 | 0.527 | 5.139e-05 | 3.642e-05 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| gsom | TMAX_anom | °C anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 39 | 0.66 | 5.44e-06 | 4.034e-06 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| gsom | TMIN_anom | °C anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 39 | 0.4506 | 0.0005627 | 0.0003004 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| gsom | PRCP_anom | mm/year anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 39 | 17.46 | 0.4247 | 0.2972 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| grace | TWS | cm EWH anomaly | monthly_deseasonalised_grace_headline_method | headline_grace_method | 2003.04 | 2025.96 | 235 | -12.12 | 6.711e-06 | 1.592e-07 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | monthly | 72 | 2002,2017,2018,2026 |

### Station baseline coverage (v1 limitation: no baseline fallback)

| source | variable | stations_with_data | stations_with_any_baseline_month | stations_with_full_12month_baseline | stations_dropped_no_baseline | stations_ending_before_2006 | station_months_failing_day_rule |
|---|---|---|---|---|---|---|---|
| ghcn | TAVG | 27 | 25 | 25 | 2 | 0 | 1.21e+03 |
| ghcn | TMAX | 27 | 26 | 19 | 1 | 0 | 3.25e+03 |
| ghcn | TMIN | 27 | 26 | 20 | 1 | 0 | 3.97e+03 |
| ghcn | PRCP | 27 | 13 | 6 | 14 | 21 | 7.74e+03 |
| gsom | TAVG | 171 | 35 | 9 | 136 | 46 |  |
| gsom | TMAX | 174 | 38 | 14 | 136 | 42 |  |
| gsom | TMIN | 174 | 36 | 9 | 138 | 11 |  |
| gsom | PRCP | 188 | 20 | 10 | 168 | 177 |  |

### Station counts per trend window (annual 12/12)

| source | variable | window | headline | n | missing_years | stations_min | stations_median | lin_slope_per_decade | robust_call |
|---|---|---|---|---|---|---|---|---|---|
| ghcn | TAVG_anom | full_gappy | False | 140 | 1941,1943,2007,2008,2009 | 1 | 11 | 0.129 | gappy window: 5 missing years (1941, 1943, 2007-2009), n=140; not treated as robust - use 1981-2019 station window |
| ghcn | TAVG_anom | 1981-2025_gappy | False | 42 | 2007,2008,2009 | 2 | 25 | 0.634 | gappy window: 3 missing years (2007-2009), n=42; not treated as robust - use 1981-2019 station window |
| ghcn | TAVG_anom | 2001-2025_gappy | False | 22 | 2007,2008,2009 | 2 | 22 | 0.98 | gappy window: 3 missing years (2007-2009), n=22; not treated as robust - use 1981-2019 station window |
| ghcn | TAVG_anom | 1981-2019_station_window | True | 36 | 2007,2008,2009 | 9 | 25 | 0.555 | significant at 0.05 (repo MK Yue-Wang; verdict strong) [headline window; note missing years 2007-2009, n=36] |
| ghcn | TMAX_anom | full_gappy | False | 142 | 1883,1884 | 1 | 12 | 0.164 | gappy window: 2 missing years (1883-1884), n=142; not treated as robust - use 1981-2019 station window |
| ghcn | TMAX_anom | 1981-2025 | False | 45 |  | 1 | 19 | 0.734 | significant at 0.05 (repo MK Yue-Wang; verdict strong) |
| ghcn | TMAX_anom | 2001-2025 | False | 25 |  | 1 | 17 | 0.874 | significant at 0.05 (repo MK Yue-Wang; verdict strong) |
| ghcn | TMAX_anom | 1981-2019_station_window | True | 39 |  | 4 | 20 | 0.706 | significant at 0.05 (repo MK Yue-Wang; verdict strong) |
| ghcn | TMIN_anom | full_gappy | False | 140 | 1883,1884,2021,2022 | 1 | 12 | 0.177 | gappy window: 4 missing years (1883-1884, 2021-2022), n=140; not treated as robust - use 1981-2019 station window |
| ghcn | TMIN_anom | 1981-2025_gappy | False | 43 | 2021,2022 | 1 | 19 | 0.524 | gappy window: 2 missing years (2021-2022), n=43; not treated as robust - use 1981-2019 station window |
| ghcn | TMIN_anom | 2001-2025_gappy | False | 23 | 2021,2022 | 1 | 16 | 0.679 | gappy window: 2 missing years (2021-2022), n=23; not treated as robust - use 1981-2019 station window |
| ghcn | TMIN_anom | 1981-2019_station_window | True | 39 |  | 4 | 21 | 0.426 | significant at 0.05 (repo MK Yue-Wang; verdict strong) |
| ghcn | PRCP_anom | full_gappy | False | 141 | 1942,2021 | 1 | 6 | 8.7 | gappy window: 2 missing years (1942, 2021), n=141; not treated as robust - use 1981-2019 station window |
| ghcn | PRCP_anom | 1981-2019_station_window | True | 39 |  | 1 | 6 | 10.5 | not significant at 0.05 (repo MK Yue-Wang; verdict none) |
| gsom | TAVG_anom | full_gappy | False | 120 | 1941,2020,2021,2022,2023,2024 | 1 | 11 | 0.152 | gappy window: 6 missing years (1941, 2020-2024), n=120; not treated as robust - use 1981-2019 station window |
| gsom | TAVG_anom | 1981-2025_gappy | False | 40 | 2020,2021,2022,2023,2024 | 1 | 16 | 0.525 | gappy window: 5 missing years (2020-2024), n=40; not treated as robust - use 1981-2019 station window |
| gsom | TAVG_anom | 2001-2025_gappy | False | 20 | 2020,2021,2022,2023,2024 | 1 | 9 | 0.561 | gappy window: 5 missing years (2020-2024), n=20; not treated as robust - use 1981-2019 station window |
| gsom | TAVG_anom | 1981-2019_station_window | True | 39 |  | 4 | 17 | 0.527 | significant at 0.05 (repo MK Yue-Wang; verdict strong) |
| gsom | TMAX_anom | full_gappy | False | 124 | 2021,2024 | 1 | 17.5 | 0.162 | gappy window: 2 missing years (2021, 2024), n=124; not treated as robust - use 1981-2019 station window |
| gsom | TMAX_anom | 1981-2025_gappy | False | 43 | 2021,2024 | 1 | 25 | 0.672 | gappy window: 2 missing years (2021, 2024), n=43; not treated as robust - use 1981-2019 station window |
| gsom | TMAX_anom | 2001-2025_gappy | False | 23 | 2021,2024 | 1 | 21 | 0.759 | gappy window: 2 missing years (2021, 2024), n=23; not treated as robust - use 1981-2019 station window |
| gsom | TMAX_anom | 1981-2019_station_window | True | 39 |  | 4 | 26 | 0.66 | significant at 0.05 (repo MK Yue-Wang; verdict strong) |
| gsom | TMIN_anom | full_gappy | False | 121 | 2020,2021,2022,2023,2024 | 1 | 12 | 0.161 | gappy window: 5 missing years (2020-2024), n=121; not treated as robust - use 1981-2019 station window |
| gsom | TMIN_anom | 1981-2025_gappy | False | 40 | 2020,2021,2022,2023,2024 | 1 | 17 | 0.474 | gappy window: 5 missing years (2020-2024), n=40; not treated as robust - use 1981-2019 station window |
| gsom | TMIN_anom | 2001-2025_gappy | False | 20 | 2020,2021,2022,2023,2024 | 1 | 10 | 0.546 | gappy window: 5 missing years (2020-2024), n=20; not treated as robust - use 1981-2019 station window |
| gsom | TMIN_anom | 1981-2019_station_window | True | 39 |  | 4 | 18 | 0.451 | significant at 0.05 (repo MK Yue-Wang; verdict strong) |
| gsom | PRCP_anom | full_gappy | False | 124 | 2021 | 2 | 10 | 10.6 | gappy window: 1 missing years (2021), n=124; not treated as robust - use 1981-2019 station window |
| gsom | PRCP_anom | 1981-2019_station_window | True | 39 |  | 4 | 10 | 17.5 | not significant at 0.05 (repo MK Yue-Wang; verdict none) |

## Region `ukraine_mask_no_crimea`

Bounds [22.13283980300011, 45.21356842700004, 40.1595430910001, 52.36894928000008]; 73 series; 20.6 s.

### Source status

| source | status | details |
|---|---|---|
| nasa_power | ok | {} |
| grace | ok | {"file": "$GLOBAL_DATA/grace/GRCTellus.JPL.200204_202609.GLO.RL06.3M.MSCNv04CRI.nc", "n_mascons": 13, "n_land_cells_weight_gt0": 336, "time_center_vs_csv_max_days": 0} |
| hadcrut5 | ok | {"n_cells_weight_gt0": 9, "sum_frac": 2.821649406799645} |
| gistemp | ok | {"n_cells_weight_gt0": 34} |
| berkeley | ok | {"n_cells_weight_gt0": 104, "weight": "area x overlap x land_mask fraction"} |
| chirps | ok | {"path": "global_grid_overlap_weights", "file": "$GLOBAL_DATA/chirps_v3/chirps-v3.0.monthly.nc", "cache": "chirps_ukraine_mask_no_crimea_4db0ad7d0d866240.parquet"} |
| cci_sm | ok | {"note": "record 1978-11..1991-12 only"} |
| merra2 | ok | {"path": "global_grid_overlap_weights", "products": [{"product": "merra2_slv", "dir": "$GLOBAL_DATA/merra2_slv_slim", "n_files": 561, "window_cells": "16x30", "cache": "merra2_slv_ukraine_mask_no_crimea_aa61321b17197e1c.parquet", "status": "cached"}, {"product": "merra2_flx", "dir": "$GLOBAL_DATA/merra2_flx_slim", "n_files": 561, "window_cells": "16x30", "cache": "merra2_flx_ukraine_mask_no_crimea |
| gldas20 | ok | {"path": "global_grid_overlap_weights", "products": [{"product": "gldas20", "dir": "$GLOBAL_DATA/gldas20_slim", "n_files": 804, "window_cells": "30x73", "cache": "gldas20_ukraine_mask_no_crimea_9c1e4daabd4ad915.parquet", "status": "cached"}, {"product": "gldas20_rainf", "dir": "$GLOBAL_DATA/gldas20_rainf", "n_files": 804, "window_cells": "30x73", "cache": "gldas20_rainf_ukraine_mask_no_crimea_4bbe |
| gldas21 | ok | {"path": "global_grid_overlap_weights", "products": [{"product": "gldas21", "dir": "$GLOBAL_DATA/gldas21_slim", "n_files": 319, "window_cells": "30x73", "cache": "gldas21_ukraine_mask_no_crimea_84eb1de5d083d909.parquet", "status": "cached"}, {"product": "gldas21_rainf", "dir": "$GLOBAL_DATA/gldas21_rainf", "n_files": 319, "window_cells": "30x73", "cache": "gldas21_rainf_ukraine_mask_no_crimea_605f |
| gpm_imerg | ok | {"path": "global_grid_overlap_weights", "products": [{"product": "gpm_imerg", "dir": "$GLOBAL_DATA/gpm_imerg_slim", "n_files": 333, "window_cells": "72x181", "cache": "gpm_imerg_ukraine_mask_no_crimea_9eb48dfc0ade45fd.parquet", "status": "cached"}]} |
| airs | ok | {"path": "global_grid_overlap_weights", "products": [{"product": "airs", "dir": "$GLOBAL_DATA/airs3stm_slim", "n_files": 290, "window_cells": "8x19", "cache": "airs_ukraine_mask_no_crimea_de4a01c0cdd1cab8.parquet", "status": "cached"}]} |
| modis | ok | {"path": "global_grid_overlap_weights", "products": [{"product": "mod13c2_qc", "dir": "$GLOBAL_DATA/mod13c2_slim", "n_files": 321, "window_cells": "144x362", "cache": "mod13c2_qc_ukraine_mask_no_crimea_6dd43cef093614f5.parquet", "status": "cached"}, {"product": "mod11c3_qc", "dir": "$GLOBAL_DATA/mod11c3_slim", "n_files": 321, "window_cells": "144x362", "cache": "mod11c3_qc_ukraine_mask_no_crimea_2 |
| omi | skipped | {"reason": "samples hold only a pre-computed Ukraine-bbox mean (no grid); not valid for this region"} |
| gpcc | ok | {"path": "global_grid_overlap_weights", "n_files": 47, "cache": "gpcc_ukraine_mask_no_crimea_ae1e98ebed965be8.parquet"} |
| cru_cy | ok | {"mask": "CRU-CY country mask; Crimea in/out undocumented -> mask mismatch vs region"} |
| berkeley_country | ok | {"mask": "Berkeley polygon 553,101 km\u00b2, 45.21-52.37N: Crimea EXCLUDED"} |
| ghcn | ok | {"n_stations_in_region": 24, "n_qflag_values_removed": 3855} |
| gsom | ok | {"n_stations_in_region": 171} |
| swot | skipped | {"reason": "samples hold only a pre-computed Ukraine-bbox mean (no grid); not valid for this region"} |

### Per-variable QC

| source | variable | unit | first | last | pct_valid_raw | pct_valid_gap_excluded | n_gaps | longest_gap_months | complete_years | min_coverage_frac | min_n_valid | baseline | flag_counts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nasa_power | T2M | °C | 1981-01 | 2025-12 | 100 | 100 | 0 | 0 | 45 | 0.999 | 279 | 1991-2020 |  |
| nasa_power | T2M_MAX | °C | 1981-01 | 2025-12 | 100 | 100 | 0 | 0 | 45 | 0.999 | 279 | 1991-2020 |  |
| nasa_power | T2M_MIN | °C | 1981-01 | 2025-12 | 100 | 100 | 0 | 0 | 45 | 0.999 | 279 | 1991-2020 |  |
| nasa_power | PRECTOTCORR | mm/month | 1981-01 | 2025-12 | 100 | 100 | 0 | 0 | 45 | 0.999 | 279 | 1991-2020 |  |
| nasa_power | QV2M | g/kg | 1981-01 | 2025-12 | 100 | 100 | 0 | 0 | 45 | 0.999 | 279 | 1991-2020 |  |
| nasa_power | WS10M | m/s | 1981-01 | 2025-12 | 100 | 100 | 0 | 0 | 45 | 0.999 | 279 | 1991-2020 |  |
| nasa_power | ALLSKY_SFC_SW_DWN | kWh/m²/day | 2001-01 | 2025-12 | 100 | 100 | 0 | 0 | 25 | 0.991 | 97 | 1991-2020 | partial_year=204; missing_value=204 |
| derived | DTR | °C | 1981-01 | 2025-12 | 100 | 100 | 0 | 0 | 45 |  | 279 | 1991-2020 | derived_from_POWER_T2M_MAX_minus_T2M_MIN=540 |
| grace | TWS | cm EWH anomaly | 2002-04 | 2026-09 | 88.8 | 100 | 18 | 11 | 14 | 0.994 | 336 | record_mean | partial_year=126; missing_month_official=33; missing_value=33; grace_gracefo_gap=11 |
| hadcrut5 | tas_anomaly | °C anomaly (1961-1990) | 1850-01 | 2026-09 | 100 | 100 | 0 | 0 | 176 | 1 | 9 | 1991-2020 | coarse_cells_extend_beyond_region=2121; partial_year=9; outlier_5sigma=2 |
| gistemp | tas_anomaly | °C anomaly (1951-1980) | 1880-01 | 2026-10 | 100 | 100 | 0 | 0 | 146 | 1 | 34 | 1991-2020 | coarse_cells_extend_beyond_region=1762; partial_year=10; outlier_5sigma=4 |
| berkeley | tas_anomaly | °C anomaly (1951-1980) | 1750-01 | 2024-12 | 100 | 100 | 1 | 1 | 274 | 0.966 | 102 | 1991-2020 | partial_year=12; outlier_5sigma=2; missing_value=1 |
| chirps | precip | mm/month | 1981-01 | 2026-09 | 100 | 100 | 0 | 0 | 45 | 1 | 2.91e+04 | 1991-2020 | partial_year=9 |
| cci_sm | sm | m³/m³ | 1978-11 | 2024-12 | 100 | 100 | 0 | 0 | 46 | 0.107 | 139 | 1991-2020 | partial_record_1978-1991=554; winter_low_coverage=554; partial_year=2 |
| merra2 | T2M | °C | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 283 | 1991-2020 | partial_year=9 |
| merra2 | QV2M | g/kg | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 283 | 1991-2020 | partial_year=9 |
| merra2 | SLP | hPa | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 283 | 1991-2020 | partial_year=9 |
| merra2 | PRECTOTCORR | mm/month | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 283 | 1991-2020 | partial_year=9 |
| merra2 | PRECTOT | mm/month | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 283 | 1991-2020 | partial_year=9 |
| merra2 | U10M | m/s | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 283 | 1991-2020 | partial_year=9 |
| merra2 | V10M | m/s | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 283 | 1991-2020 | partial_year=9 |
| merra2 | WS10M_from_mean_UV | m/s | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 283 | 1991-2020 | speed_of_monthly_mean_wind_underestimates_mean_speed=561; partial_year=9 |
| merra2 | T2MMAX | °C | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 283 | 1991-2020 | partial_year=9 |
| merra2 | T2MMIN | °C | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 283 | 1991-2020 | partial_year=9 |
| merra2 | DTR | °C | 1980-01 | 2026-09 | 100 | 100 | 0 | 0 | 46 | 1 | 283 | 1991-2020 | partial_year=9 |
| gldas20 | SoilMoi0_10cm_inst | kg/m² (≈mm) | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.987 | 1.24e+03 | 1991-2020 |  |
| gldas20 | RootMoist_inst | kg/m² (≈mm) | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.987 | 1.24e+03 | 1991-2020 |  |
| gldas20 | SWE_inst | kg/m² (≈mm) | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.987 | 1.24e+03 | 1991-2020 | outlier_5sigma=10 |
| gldas20 | Tair_f_inst | °C | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.993 | 1.24e+03 | 1991-2020 |  |
| gldas20 | Evap_tavg | mm/month | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.987 | 1.24e+03 | 1991-2020 | outlier_5sigma=1 |
| gldas20 | Qs_acc | mm/month | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.987 | 1.24e+03 | 1991-2020 | outlier_5sigma=6 |
| gldas20 | Qsb_acc | mm/month | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.987 | 1.24e+03 | 1991-2020 | outlier_5sigma=4 |
| gldas20 | precip_total | mm/month | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.993 | 1.24e+03 | 1991-2020 |  |
| gldas20 | snowfall | mm/month | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.987 | 1.24e+03 | 1991-2020 | outlier_5sigma=1 |
| gldas20 | rainfall_liquid | mm/month | 1948-01 | 2014-12 | 100 | 100 | 0 | 0 | 67 | 0.987 | 1.24e+03 | 1991-2020 |  |
| gldas21 | SoilMoi0_10cm_inst | kg/m² (≈mm) | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.987 | 1.24e+03 | 1991-2020 | partial_year=7 |
| gldas21 | RootMoist_inst | kg/m² (≈mm) | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.987 | 1.24e+03 | 1991-2020 | partial_year=7 |
| gldas21 | SWE_inst | kg/m² (≈mm) | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.987 | 1.24e+03 | 1991-2020 | partial_year=7; outlier_5sigma=2 |
| gldas21 | Tair_f_inst | °C | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.993 | 1.24e+03 | 1991-2020 | partial_year=7 |
| gldas21 | Evap_tavg | mm/month | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.987 | 1.24e+03 | 1991-2020 | partial_year=7 |
| gldas21 | Qs_acc | mm/month | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.987 | 1.24e+03 | 1991-2020 | partial_year=7; outlier_5sigma=3 |
| gldas21 | Qsb_acc | mm/month | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.987 | 1.24e+03 | 1991-2020 | partial_year=7; outlier_5sigma=1 |
| gldas21 | precip_total | mm/month | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.993 | 1.24e+03 | 1991-2020 | partial_year=7 |
| gldas21 | snowfall | mm/month | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.987 | 1.24e+03 | 1991-2020 | partial_year=7 |
| gldas21 | rainfall_liquid | mm/month | 2000-01 | 2026-07 | 100 | 100 | 0 | 0 | 26 | 0.987 | 1.24e+03 | 1991-2020 | partial_year=7 |
| gpm_imerg | precipitation | mm/month | 1998-01 | 2025-09 | 100 | 100 | 0 | 0 | 27 | 1 | 7.45e+03 | 1991-2020 | partial_year=9 |
| airs | SurfAirTemp | °C | 2002-09 | 2026-10 | 100 | 100 | 0 | 0 | 23 | 1 | 104 | record_mean | partial_year=14; airs_2025_bias_unverified=12 |
| airs | TotH2OVap | kg/m² (≈mm) | 2002-09 | 2026-10 | 100 | 100 | 0 | 0 | 23 | 1 | 104 | record_mean | partial_year=14; airs_2025_bias_unverified=12 |
| modis | NDVI | index | 2000-02 | 2026-10 | 100 | 100 | 0 | 0 | 25 | 0.0686 | 1.98e+03 | 1991-2020 | qc_pixel_masked=321; terra_only=321; vi_winter_snow_masked_sampling=321; qc_low_coverage_lt50pct=23; partial_year=21 |
| modis | EVI | index | 2000-02 | 2026-10 | 100 | 100 | 0 | 0 | 25 | 0.0686 | 1.98e+03 | 1991-2020 | qc_pixel_masked=321; terra_only=321; vi_winter_snow_masked_sampling=321; qc_low_coverage_lt50pct=23; partial_year=21 |
| modis | LST_Day | °C | 2000-02 | 2026-10 | 100 | 100 | 0 | 0 | 25 | 0.867 | 2.51e+04 | 1991-2020 | qc_pixel_masked=321; terra_only=321; lst_clear_sky_winter_bias=321; partial_year=21 |
| modis | LST_Night | °C | 2000-02 | 2026-10 | 100 | 100 | 0 | 0 | 25 | 0.979 | 2.84e+04 | 1991-2020 | qc_pixel_masked=321; terra_only=321; lst_clear_sky_winter_bias=321; partial_year=21 |
| modis | LST_Day_clear_days | days | 2000-02 | 2026-10 | 100 | 100 | 0 | 0 | 25 | 0.867 | 2.51e+04 | 1991-2020 | qc_pixel_masked=321; terra_only=321; partial_year=21 |
| modis | LST_Night_clear_days | days | 2000-02 | 2026-10 | 100 | 100 | 0 | 0 | 25 | 0.979 | 2.84e+04 | 1991-2020 | qc_pixel_masked=321; terra_only=321; partial_year=21 |
| gpcc | precip | mm/month | 1891-01 | 2026-08 | 100 | 100 | 0 | 0 | 135 | 1 | 104 | 1991-2020 | partial_year=8 |
| cru_cy | tmp | °C | 1901-01 | 2025-12 | 100 | 100 | 0 | 0 | 125 |  |  | 1991-2020 | own_country_mask=1500; crimea_undocumented=1500; absolute_not_anomaly=1500; outlier_5sigma=1 |
| cru_cy | tmp_anom | °C anomaly (1961-1990) | 1901-01 | 2025-12 | 100 | 100 | 0 | 0 | 125 |  |  | 1991-2020 | own_country_mask=1500; crimea_undocumented=1500; outlier_5sigma=1 |
| cru_cy | tmn | °C | 1901-01 | 2025-12 | 100 | 100 | 0 | 0 | 125 |  |  | 1991-2020 | own_country_mask=1500; crimea_undocumented=1500; outlier_5sigma=4 |
| cru_cy | tmx | °C | 1901-01 | 2025-12 | 100 | 100 | 0 | 0 | 125 |  |  | 1991-2020 | own_country_mask=1500; crimea_undocumented=1500 |
| cru_cy | dtr | °C | 1901-01 | 2025-12 | 100 | 100 | 0 | 0 | 125 |  |  | 1991-2020 | own_country_mask=1500; crimea_undocumented=1500 |
| cru_cy | pre | mm/month | 1901-01 | 2025-12 | 100 | 100 | 0 | 0 | 125 |  |  | 1991-2020 | own_country_mask=1500; crimea_undocumented=1500 |
| cru_cy | pet | mm/month | 1901-01 | 2025-12 | 100 | 100 | 0 | 0 | 125 |  |  | 1991-2020 | own_country_mask=1500; crimea_undocumented=1500 |
| cru_cy | vap | hPa | 1901-01 | 2025-12 | 100 | 100 | 0 | 0 | 125 |  |  | 1991-2020 | own_country_mask=1500; crimea_undocumented=1500 |
| cru_cy | wet | days | 1901-01 | 2025-12 | 100 | 100 | 0 | 0 | 125 |  |  | 1991-2020 | own_country_mask=1500; crimea_undocumented=1500 |
| berkeley_country | tas_anomaly | °C anomaly (1951-1980) | 1750-01 | 2020-12 | 99.8 | 99.8 | 4 | 5 | 267 |  |  | 1991-2020 | own_country_mask=3252; crimea_excluded=3252; partial_year=48; missing_value=8; outlier_5sigma=3 |
| ghcn | TAVG_anom | °C anomaly (1991-2020) | 1881-01 | 2026-10 | 99.1 | 99.1 | 7 | 3 | 139 | 0.0455 | 1 | 1991-2020 | station_anomaly_mean=1750; UP_stations_only=1750; few_stations_lt3=689; partial_year=82; missing_value=15; outlier_5sigma=3 |
| ghcn | TMAX_anom | °C anomaly (1991-2020) | 1881-01 | 2026-10 | 99.5 | 99.5 | 5 | 3 | 141 | 0.0435 | 1 | 1991-2020 | station_anomaly_mean=1750; UP_stations_only=1750; few_stations_lt3=189; partial_year=58; missing_value=8 |
| ghcn | TMIN_anom | °C anomaly (1991-2020) | 1881-01 | 2026-10 | 99.5 | 99.5 | 6 | 3 | 140 | 0.0435 | 1 | 1991-2020 | station_anomaly_mean=1750; UP_stations_only=1750; few_stations_lt3=131; partial_year=70; missing_value=9; outlier_5sigma=3 |
| ghcn | PRCP_anom | mm/month anomaly (1991-2020) | 1881-01 | 2019-12 | 99.9 | 99.9 | 1 | 1 | 138 | 0.0909 | 1 | 1991-2020 | station_anomaly_mean=1668; UP_stations_only=1668; few_stations_lt3=216; partial_year=12; outlier_5sigma=1; missing_value=1 |
| gsom | TAVG_anom | °C anomaly (1991-2020) | 1900-01 | 2026-10 | 98.4 | 98.4 | 9 | 5 | 120 | 0.0333 | 1 | 1991-2020 | station_anomaly_mean=1522; UP_stations_only=1522; partial_year=82; few_stations_lt3=27; missing_value=24; outlier_5sigma=2 |
| gsom | TMAX_anom | °C anomaly (1991-2020) | 1900-01 | 2026-10 | 99.3 | 99.3 | 8 | 3 | 121 | 0.0303 | 1 | 1991-2020 | station_anomaly_mean=1522; UP_stations_only=1522; partial_year=70; missing_value=11; few_stations_lt3=9 |
| gsom | TMIN_anom | °C anomaly (1991-2020) | 1900-01 | 2026-10 | 98.5 | 98.5 | 8 | 5 | 121 | 0.0323 | 1 | 1991-2020 | station_anomaly_mean=1522; UP_stations_only=1522; partial_year=70; missing_value=23; few_stations_lt3=20; outlier_5sigma=3 |
| gsom | PRCP_anom | mm/month anomaly (1991-2020) | 1900-01 | 2019-12 | 100 | 100 | 0 | 0 | 120 | 0.125 | 2 | 1991-2020 | station_anomaly_mean=1440; UP_stations_only=1440; few_stations_lt3=10 |

### Headline trends (annual full window; stations 1981-2019; GRACE = headline method, monthly; VI = peak-season JJA and growing-season Apr-Sep)

`mt_bonferroni_pass` / `mt_bh_pass` are Bonferroni / Benjamini-Hochberg (q<0.05) on the primary Yue-Wang p-value, across the whole test family (all windows and roles; family size in `n_tests_in_family`). `yw_ols_neff_agree` is the OLS effective-n cross-check. HAC / Hamed-Rao are sensitivity only (`sensitivity_call_hac_hr`). Forcing/sampling diagnostics, different-convention rows and the annual VI rows are not headlines (column `role` in trends.csv).

| source | variable | unit | series | window | start | end | n | lin_slope_per_decade | yw_p | yw_ols_neff_p | yw_ols_neff_agree | robust_call | mt_bonferroni_pass | mt_bh_pass | test_family | n_tests_in_family | excluded_years |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nasa_power | T2M | °C | annual_ANN_12of12 | full | 1981 | 2025 | 45 | 0.5565 | 3.11e-05 | 1.794e-05 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| nasa_power | T2M_MAX | °C | annual_ANN_12of12 | full | 1981 | 2025 | 45 | 0.5711 | 3.919e-05 | 5.38e-06 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| nasa_power | T2M_MIN | °C | annual_ANN_12of12 | full | 1981 | 2025 | 45 | 0.6209 | 0.004389 | 0.00118 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| nasa_power | PRECTOTCORR | mm/year | annual_ANN_12of12 | full | 1981 | 2025 | 45 | 9.597 | 0.09829 | 0.2484 | True | not significant at 0.05 (repo MK Yue-Wang; verdict weak) | False | False | annual | 161 |  |
| nasa_power | QV2M | g/kg | annual_ANN_12of12 | full | 1981 | 2025 | 45 | 0.1407 | 0.0004471 | 0.0005761 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| nasa_power | WS10M | m/s | annual_ANN_12of12 | full | 1981 | 2025 | 45 | -0.02378 | 0.03406 | 0.1206 | False | significant at 0.05 (repo MK Yue-Wang; verdict moderate) | False | False | annual | 161 |  |
| nasa_power | ALLSKY_SFC_SW_DWN | kWh/m²/day | annual_ANN_12of12 | full | 2001 | 2025 | 25 | 0.04891 | 0.04713 | 0.04455 | True | significant at 0.05 (repo MK Yue-Wang; verdict moderate) | False | False | annual | 161 |  |
| derived | DTR | °C | annual_ANN_12of12 | full | 1981 | 2025 | 45 | -0.04977 | 0.4092 | 0.6859 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| hadcrut5 | tas_anomaly | °C anomaly (1961-1990) | annual_ANN_12of12 | full | 1850 | 2025 | 176 | 0.09609 | 1.385e-07 | 1.671e-08 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| gistemp | tas_anomaly | °C anomaly (1951-1980) | annual_ANN_12of12 | full | 1880 | 2025 | 146 | 0.162 | 6.912e-11 | 3.334e-12 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| berkeley | tas_anomaly | °C anomaly (1951-1980) | annual_ANN_12of12 | full | 1750 | 2024 | 274 | 0.0611 | 1.661e-10 | 5.654e-12 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| chirps | precip | mm/year | annual_ANN_12of12 | full | 1981 | 2025 | 45 | -5.306 | 0.9298 | 0.6367 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| cci_sm | sm | m³/m³ | annual_ANN_12of12 | full | 1979 | 2024 | 46 | -0.0006559 | 0.452 | 0.507 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| merra2 | T2M | °C | annual_ANN_12of12 | full | 1980 | 2025 | 46 | 0.591 | 5.436e-06 | 1.854e-06 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| merra2 | QV2M | g/kg | annual_ANN_12of12 | full | 1980 | 2025 | 46 | 0.1339 | 0.001097 | 0.001612 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| merra2 | SLP | hPa | annual_ANN_12of12 | full | 1980 | 2025 | 46 | -0.103 | 0.3735 | 0.2851 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| merra2 | PRECTOTCORR | mm/year | annual_ANN_12of12 | full | 1980 | 2025 | 46 | 0.8562 | 0.3289 | 0.9431 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| merra2 | PRECTOT | mm/year | annual_ANN_12of12 | full | 1980 | 2025 | 46 | 1.146 | 0.6374 | 0.9358 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| merra2 | U10M | m/s | annual_ANN_12of12 | full | 1980 | 2025 | 46 | -0.03908 | 0.6225 | 0.4672 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| merra2 | V10M | m/s | annual_ANN_12of12 | full | 1980 | 2025 | 46 | -0.02562 | 0.2201 | 0.2085 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| merra2 | WS10M_from_mean_UV | m/s | annual_ANN_12of12 | full | 1980 | 2025 | 46 | -0.02347 | 0.5395 | 0.4609 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| merra2 | T2MMAX | °C | annual_ANN_12of12 | full | 1980 | 2025 | 46 | 0.639 | 3.162e-06 | 6.633e-07 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| merra2 | T2MMIN | °C | annual_ANN_12of12 | full | 1980 | 2025 | 46 | 0.5797 | 3.192e-05 | 1.455e-05 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| merra2 | DTR | °C | annual_ANN_12of12 | full | 1980 | 2025 | 46 | 0.05928 | 0.213 | 0.1603 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas20 | SoilMoi0_10cm_inst | kg/m² (≈mm) | annual_ANN_12of12 | full | 1948 | 2014 | 67 | 0.06104 | 0.9364 | 0.6837 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas20 | RootMoist_inst | kg/m² (≈mm) | annual_ANN_12of12 | full | 1948 | 2014 | 67 | 2.154 | 0.6673 | 0.3348 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas20 | SWE_inst | kg/m² (≈mm) | annual_ANN_12of12 | full | 1948 | 2014 | 67 | -0.1989 | 0.8397 | 0.6167 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas20 | Tair_f_inst | °C | annual_ANN_12of12 | full | 1948 | 2014 | 67 | 0.2253 | 0.0002022 | 0.0001578 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| gldas20 | Evap_tavg | mm/year | annual_ANN_12of12 | full | 1948 | 2014 | 67 | 5.909 | 0.004169 | 0.001279 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| gldas20 | Qs_acc | mm/year | annual_ANN_12of12 | full | 1948 | 2014 | 67 | -0.4363 | 0.3515 | 0.3655 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas20 | Qsb_acc | mm/year | annual_ANN_12of12 | full | 1948 | 2014 | 67 | 0.929 | 0.452 | 0.7308 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas20 | precip_total | mm/year | annual_ANN_12of12 | full | 1948 | 2014 | 67 | 4.192 | 0.1867 | 0.3215 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas20 | snowfall | mm/year | annual_ANN_12of12 | full | 1948 | 2014 | 67 | -1.543 | 0.6937 | 0.5985 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas20 | rainfall_liquid | mm/year | annual_ANN_12of12 | full | 1948 | 2014 | 67 | 5.745 | 0.1217 | 0.1246 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas21 | SoilMoi0_10cm_inst | kg/m² (≈mm) | annual_ANN_12of12 | full | 2000 | 2025 | 26 | -1.44 | 0.002546 | 0.00326 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| gldas21 | RootMoist_inst | kg/m² (≈mm) | annual_ANN_12of12 | full | 2000 | 2025 | 26 | -16.65 | 0.007329 | 0.00692 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| gldas21 | Tair_f_inst | °C | annual_ANN_12of12 | full | 2000 | 2025 | 26 | 0.9626 | 0.0004162 | 0.0001582 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| gldas21 | Evap_tavg | mm/year | annual_ANN_12of12 | full | 2000 | 2025 | 26 | 12.8 | 0.2011 | 0.06763 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas21 | Qs_acc | mm/year | annual_ANN_12of12 | full | 2000 | 2025 | 26 | -11.28 | 0.0004209 | 0.0004987 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| gldas21 | Qsb_acc | mm/year | annual_ANN_12of12 | full | 2000 | 2025 | 26 | -10.41 | 0.5968 | 0.3613 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas21 | precip_total | mm/year | annual_ANN_12of12 | full | 2000 | 2025 | 26 | -16.66 | 0.378 | 0.429 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gldas21 | rainfall_liquid | mm/year | annual_ANN_12of12 | full | 2000 | 2025 | 26 | 6.03 | 0.6524 | 0.7311 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gpm_imerg | precipitation | mm/year | annual_ANN_12of12 | full | 1998 | 2024 | 27 | -6.137 | 0.6767 | 0.7167 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| airs | SurfAirTemp | °C | annual_ANN_12of12 | full | 2003 | 2024 | 22 | 0.828 | 0.0008671 | 8.856e-05 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 | 2025 |
| airs | TotH2OVap | kg/m² (≈mm) | annual_ANN_12of12 | full | 2003 | 2024 | 22 | 0.1264 | 0.1759 | 0.2499 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 | 2025 |
| modis | NDVI | index | seasonal_JJA_3of3_peak_season | 2001-2025_JJA | 2001 | 2025 | 25 | 0.0003066 | 0.5912 | 0.9574 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) [peak season (JJA); season-sensit | False | False | annual | 161 |  |
| modis | NDVI | index | seasonal_AprSep_6of6_growing_season | 2001-2025_AMJJAS | 2001 | 2025 | 25 | -0.002657 | 0.5593 | 0.5548 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) [growing season (Apr-Sep); season | False | False | annual | 161 |  |
| modis | EVI | index | seasonal_JJA_3of3_peak_season | 2001-2025_JJA | 2001 | 2025 | 25 | 0.01238 | 0.02349 | 0.01945 | True | significant at 0.05 (repo MK Yue-Wang; verdict moderate) [peak season (JJA); season-sensit | False | True | annual | 161 |  |
| modis | EVI | index | seasonal_AprSep_6of6_growing_season | 2001-2025_AMJJAS | 2001 | 2025 | 25 | 0.007622 | 0.09728 | 0.0366 | False | not significant at 0.05 (repo MK Yue-Wang; verdict weak) [growing season (Apr-Sep); season | False | False | annual | 161 |  |
| modis | LST_Day | °C | annual_ANN_12of12 | full | 2001 | 2025 | 25 | 0.8963 | 0.003016 | 0.002535 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| modis | LST_Night | °C | annual_ANN_12of12 | full | 2001 | 2025 | 25 | 0.8623 | 0.0002206 | 3.588e-05 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| gpcc | precip | mm/year | annual_ANN_12of12 | full | 1891 | 2025 | 135 | 2.448 | 0.0934 | 0.1201 | True | not significant at 0.05 (repo MK Yue-Wang; verdict weak) | False | False | annual | 161 |  |
| cru_cy | tmp | °C | annual_ANN_12of12 | full | 1901 | 2025 | 125 | 0.1701 | 6.846e-08 | 1.03e-08 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| cru_cy | tmp_anom | °C anomaly (1961-1990) | annual_ANN_12of12 | full | 1901 | 2025 | 125 | 0.1701 | 6.976e-08 | 1.03e-08 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| cru_cy | tmn | °C | annual_ANN_12of12 | full | 1901 | 2025 | 125 | 0.194 | 3.587e-11 | 4.95e-12 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| cru_cy | tmx | °C | annual_ANN_12of12 | full | 1901 | 2025 | 125 | 0.1464 | 3.242e-05 | 7.135e-06 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| cru_cy | dtr | °C | annual_ANN_12of12 | full | 1901 | 2025 | 125 | -0.04758 | 0.0005158 | 0.0003013 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| cru_cy | pre | mm/year | annual_ANN_12of12 | full | 1901 | 2025 | 125 | 2.225 | 0.1641 | 0.1891 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| cru_cy | pet | mm/year | annual_ANN_12of12 | full | 1901 | 2025 | 125 | 3.832 | 0.02941 | 0.0238 | True | significant at 0.05 (repo MK Yue-Wang; verdict moderate) | False | False | annual | 161 |  |
| cru_cy | vap | hPa | annual_ANN_12of12 | full | 1901 | 2025 | 125 | 0.07141 | 2.517e-10 | 6.895e-12 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| cru_cy | wet | days | annual_ANN_12of12 | full | 1901 | 2025 | 125 | -0.7726 | 0.009316 | 0.014 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| berkeley_country | tas_anomaly | °C anomaly (1951-1980) | annual_ANN_12of12 | full | 1751 | 2020 | 267 | 0.05422 | 6.852e-09 | 4.535e-10 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| ghcn | TAVG_anom | °C anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 36 | 0.5525 | 0.0004991 | 0.0005656 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) [headline window; note missing year | False | True | annual | 161 |  |
| ghcn | TMAX_anom | °C anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 39 | 0.692 | 7.339e-06 | 1.09e-05 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| ghcn | TMIN_anom | °C anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 39 | 0.4286 | 0.002575 | 0.001536 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| ghcn | PRCP_anom | mm/year anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 39 | 15.78 | 0.2614 | 0.2659 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| gsom | TAVG_anom | °C anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 39 | 0.52 | 0.0001716 | 0.0001387 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| gsom | TMAX_anom | °C anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 39 | 0.6511 | 1.018e-05 | 1.188e-05 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | annual | 161 |  |
| gsom | TMIN_anom | °C anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 39 | 0.4443 | 0.001241 | 0.001073 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | False | True | annual | 161 |  |
| gsom | PRCP_anom | mm/year anomaly (1991-2020) | annual_ANN_12of12 | 1981-2019_station_window | 1981 | 2019 | 39 | 12.75 | 0.4124 | 0.3406 | True | not significant at 0.05 (repo MK Yue-Wang; verdict none) | False | False | annual | 161 |  |
| grace | TWS | cm EWH anomaly | monthly_deseasonalised_grace_headline_method | headline_grace_method | 2003.04 | 2025.96 | 235 | -12.36 | 6.547e-06 | 1.303e-07 | True | significant at 0.05 (repo MK Yue-Wang; verdict strong) | True | True | monthly | 72 | 2002,2017,2018,2026 |

### Station baseline coverage (v1 limitation: no baseline fallback)

| source | variable | stations_with_data | stations_with_any_baseline_month | stations_with_full_12month_baseline | stations_dropped_no_baseline | stations_ending_before_2006 | station_months_failing_day_rule |
|---|---|---|---|---|---|---|---|
| ghcn | TAVG | 24 | 22 | 22 | 2 | 0 | 1.09e+03 |
| ghcn | TMAX | 24 | 23 | 17 | 1 | 0 | 2.95e+03 |
| ghcn | TMIN | 24 | 23 | 18 | 1 | 0 | 3.55e+03 |
| ghcn | PRCP | 24 | 11 | 4 | 13 | 20 | 7.01e+03 |
| gsom | TAVG | 156 | 30 | 7 | 126 | 44 |  |
| gsom | TMAX | 158 | 33 | 10 | 125 | 39 |  |
| gsom | TMIN | 159 | 31 | 7 | 128 | 11 |  |
| gsom | PRCP | 168 | 16 | 7 | 152 | 161 |  |

### Station counts per trend window (annual 12/12)

| source | variable | window | headline | n | missing_years | stations_min | stations_median | lin_slope_per_decade | robust_call |
|---|---|---|---|---|---|---|---|---|---|
| ghcn | TAVG_anom | full_gappy | False | 139 | 1941,1943,2007,2008,2009,2022 | 1 | 9 | 0.14 | gappy window: 6 missing years (1941, 1943, 2007-2009, 2022), n=139; not treated as robust - use 1981-2019 station window |
| ghcn | TAVG_anom | 1981-2025_gappy | False | 41 | 2007,2008,2009,2022 | 7 | 22 | 0.639 | gappy window: 4 missing years (2007-2009, 2022), n=41; not treated as robust - use 1981-2019 station window |
| ghcn | TAVG_anom | 2001-2025_gappy | False | 21 | 2007,2008,2009,2022 | 7 | 20 | 1.02 | gappy window: 4 missing years (2007-2009, 2022), n=21; not treated as robust - use 1981-2019 station window |
| ghcn | TAVG_anom | 1981-2019_station_window | True | 36 | 2007,2008,2009 | 7 | 22 | 0.552 | significant at 0.05 (repo MK Yue-Wang; verdict strong) [headline window; note missing years 2007-2009, n=36] |
| ghcn | TMAX_anom | full_gappy | False | 141 | 1883,1884,2022 | 1 | 10 | 0.17 | gappy window: 3 missing years (1883-1884, 2022), n=141; not treated as robust - use 1981-2019 station window |
| ghcn | TMAX_anom | 1981-2025_gappy | False | 44 | 2022 | 1 | 17 | 0.732 | gappy window: 1 missing years (2022), n=44; not treated as robust - use 1981-2019 station window |
| ghcn | TMAX_anom | 2001-2025_gappy | False | 24 | 2022 | 1 | 16 | 0.897 | gappy window: 1 missing years (2022), n=24; not treated as robust - use 1981-2019 station window |
| ghcn | TMAX_anom | 1981-2019_station_window | True | 39 |  | 4 | 18 | 0.692 | significant at 0.05 (repo MK Yue-Wang; verdict strong) |
| ghcn | TMIN_anom | full_gappy | False | 140 | 1883,1884,2021,2022 | 1 | 10 | 0.175 | gappy window: 4 missing years (1883-1884, 2021-2022), n=140; not treated as robust - use 1981-2019 station window |
| ghcn | TMIN_anom | 1981-2025_gappy | False | 43 | 2021,2022 | 1 | 17 | 0.532 | gappy window: 2 missing years (2021-2022), n=43; not treated as robust - use 1981-2019 station window |
| ghcn | TMIN_anom | 2001-2025_gappy | False | 23 | 2021,2022 | 1 | 14 | 0.694 | gappy window: 2 missing years (2021-2022), n=23; not treated as robust - use 1981-2019 station window |
| ghcn | TMIN_anom | 1981-2019_station_window | True | 39 |  | 3 | 18 | 0.429 | significant at 0.05 (repo MK Yue-Wang; verdict strong) |
| ghcn | PRCP_anom | full_gappy | False | 138 | 1942 | 1 | 4 | 8.52 | gappy window: 1 missing years (1942), n=138; not treated as robust - use 1981-2019 station window |
| ghcn | PRCP_anom | 1981-2019_station_window | True | 39 |  | 1 | 4 | 15.8 | not significant at 0.05 (repo MK Yue-Wang; verdict none) |
| gsom | TAVG_anom | full_gappy | False | 120 | 1941,2020,2021,2022,2023,2024 | 1 | 9 | 0.17 | gappy window: 6 missing years (1941, 2020-2024), n=120; not treated as robust - use 1981-2019 station window |
| gsom | TAVG_anom | 1981-2025_gappy | False | 40 | 2020,2021,2022,2023,2024 | 1 | 14 | 0.52 | gappy window: 5 missing years (2020-2024), n=40; not treated as robust - use 1981-2019 station window |
| gsom | TAVG_anom | 2001-2025_gappy | False | 20 | 2020,2021,2022,2023,2024 | 1 | 8 | 0.574 | gappy window: 5 missing years (2020-2024), n=20; not treated as robust - use 1981-2019 station window |
| gsom | TAVG_anom | 1981-2019_station_window | True | 39 |  | 4 | 14 | 0.52 | significant at 0.05 (repo MK Yue-Wang; verdict strong) |
| gsom | TMAX_anom | full_gappy | False | 121 | 2020,2021,2022,2023,2024 | 1 | 14 | 0.17 | gappy window: 5 missing years (2020-2024), n=121; not treated as robust - use 1981-2019 station window |
| gsom | TMAX_anom | 1981-2025_gappy | False | 40 | 2020,2021,2022,2023,2024 | 1 | 22.5 | 0.621 | gappy window: 5 missing years (2020-2024), n=40; not treated as robust - use 1981-2019 station window |
| gsom | TMAX_anom | 2001-2025_gappy | False | 20 | 2020,2021,2022,2023,2024 | 1 | 20 | 0.65 | gappy window: 5 missing years (2020-2024), n=20; not treated as robust - use 1981-2019 station window |
| gsom | TMAX_anom | 1981-2019_station_window | True | 39 |  | 4 | 23 | 0.651 | significant at 0.05 (repo MK Yue-Wang; verdict strong) |
| gsom | TMIN_anom | full_gappy | False | 121 | 2020,2021,2022,2023,2024 | 1 | 9 | 0.175 | gappy window: 5 missing years (2020-2024), n=121; not treated as robust - use 1981-2019 station window |
| gsom | TMIN_anom | 1981-2025_gappy | False | 40 | 2020,2021,2022,2023,2024 | 1 | 14 | 0.47 | gappy window: 5 missing years (2020-2024), n=40; not treated as robust - use 1981-2019 station window |
| gsom | TMIN_anom | 2001-2025_gappy | False | 20 | 2020,2021,2022,2023,2024 | 1 | 9 | 0.563 | gappy window: 5 missing years (2020-2024), n=20; not treated as robust - use 1981-2019 station window |
| gsom | TMIN_anom | 1981-2019_station_window | True | 39 |  | 4 | 14 | 0.444 | significant at 0.05 (repo MK Yue-Wang; verdict strong) |
| gsom | PRCP_anom | full | False | 120 |  | 2 | 7 | 13.2 | significant at 0.05 (repo MK Yue-Wang; verdict strong) |
| gsom | PRCP_anom | 1981-2019_station_window | True | 39 |  | 4 | 7 | 12.8 | not significant at 0.05 (repo MK Yue-Wang; verdict none) |

## Flag legend

| flag | meaning |
|---|---|
| partial_year | row belongs to a year with <12 valid months, incl. its NaN rows (excluded from annual values; e.g. 2026, IMERG 2025) |
| missing_value | value is NaN in this row (e.g. GSOM March 2026: no station report) |
| short_record | record spans <10 years |
| outlier_5sigma | deseasonalised anomaly beyond 5 SD of the series' anomalies |
| out_of_range | raw value outside the valid range in variables.yaml -> set NaN |
| no_qc | MODIS FALLBACK only (QC files missing): NO per-pixel QC applied (fill/range only) |
| qc_pixel_masked | MODIS per-pixel QC applied before area averaging (rules in 'MODIS QC' section) |
| qc_low_coverage_lt50pct | MODIS month where <50% of the region area survives QC (mostly Jan/Feb VI under snow) |
| vi_winter_snow_masked_sampling | NDVI/EVI: QC drops snow/cloud pixels (~32% of area in DJF), so winter means cover a varying snow-free subset; prefer JJA/growing-season VI for trends |
| speed_of_monthly_mean_wind_underestimates_mean_speed | MERRA-2 WS10M_from_mean_UV = |monthly-mean wind vector|, NOT mean wind speed (ukraine_mask mean 1.6 m/s vs POWER WS10M 4.3 m/s); use for flow persistence only |
| terra_only | MODIS Terra only, no Aqua |
| lst_clear_sky_winter_bias | MODIS LST is clear-sky only: winter means biased (LST_Day/LST_Night only, not NDVI/EVI); see LST_*_clear_days |
| preaggregated_bbox_mean_centre_weights | FALLBACK path only (global file missing): bbox mean computed at download (cell centres), not our overlap weights; bbox region only |
| coarse_cells_extend_beyond_region | 5°/2° cell values average land+sea outside the region; overlap weights only |
| missing_month_official | GRACE month missing in the official product (NaN, no interpolation) |
| grace_gracefo_gap | GRACE -> GRACE-FO gap 2017-07..2018-05 |
| airs_2025_bias_unverified | AIRS 2025 bias collapse not yet investigated: 2025 is EXCLUDED from all AIRS trends (column excluded_years) |
| omi_row_anomaly_period | OMI row anomaly (2007+); extract not filtered on XTrackQualityFlags |
| own_country_mask | country series with the producer's own mask (not our polygon) |
| crimea_excluded | producer mask excludes Crimea |
| crimea_undocumented | producer docs do not say whether Crimea is included |
| mask_mismatch_vs_region | producer mask differs from this region's mask (do not compare 1:1) |
| absolute_not_anomaly | CRU tmp is absolute °C; use tmp_anom for cross-source comparison |
| station_anomaly_mean | mean of station anomalies vs per-station 1991-2020 monthly normals (>=15 yrs) |
| few_stations_lt3 | fewer than 3 stations contribute to this month's regional anomaly |
| UP_stations_only | only Ukrainian (UP) stations were downloaded, even for the bbox |
| too_short_for_climate_inference | SWOT ~3 years |
| partial_record_1978-1991 | CCI SM assembled only for 1978-11..1991-12 |

## Deviations, choices and open items


- Tidy files are written as `data/tidy/<region>/<source>.parquet` (one folder per region) instead of a single
  `data/tidy/<source>.parquet`, so bbox and mask runs don't overwrite each other. Every row still carries `region`.
- Extra columns in the tidy schema: `anomaly` (deseasonalised by monthly climatology), `baseline`
  (`1991-2020` if every calendar month has >=20 baseline years, else `record_mean`), `independence_group`.
- Annual = 12/12 months only. The plan's alternative "mean of deseasonalised anomalies with >=10 months" was NOT
  built (the task said 12/12; it would be a second, labelled series - easy to add later).
- MERRA-2 (slv+flx), GLDAS 2.0/2.1, IMERG, AIRS, MODIS (MOD13C2 NDVI/EVI, MOD11C3 LST), GPCC and CHIRPS are now cut
  from the GLOBAL files under $GLOBAL_DATA (`ukpipe/loaders/global_grids.py`) with the same fractional-overlap
  x spherical-area weights as every other gridded loader, for any region in regions.yaml (generic; also the path to
  global regions). Only the region window is read from each file; per-region series are cached in data/cache/series.
  If a global file set is missing, the loader falls back to the old bbox extract (flag
  `preaggregated_bbox_mean_centre_weights`, bbox region only) - see `path` / `fallback_reason` in Source status.
  OMI and SWOT stay bbox-only (skipped for masks). Verification against the old extracts: section below.
- MODIS scale handling from the raw global files: MOD13C2 VI physical = raw / 10000 (the file's scale_factor attribute
  is a divisor), valid raw -2000..10000, fill -3000; MOD11C3 LST = raw x 0.02 K, valid raw 7500-65535, fill 0.
  Per-pixel QC from the paired QC files is applied BEFORE area averaging (since 14 Nov 2026; `no_qc` only on fallback),
  see "MODIS QC". AIRS: per-cell nanmean of ascending and descending, then area-weighted.
- Units were recomputed from raw columns with the variables.yaml conversions and checked against the extract's own
  converted columns (max abs diff 0.0; see Source status -> checks); POWER/MERRA-2/IMERG/GLDAS precip and fluxes are mm/month everywhere.
- Ukraine-bbox extracts (POWER, CCI SM; CHIRPS in fallback) were cut on cell centres at download, so a <1-cell edge
  strip can be missing (e.g. POWER has no 52.5N row; 52.25-52.4N is uncovered). `coverage_frac` is now honest for
  every gridded loader: valid weighted area / TRUE region area (spherical bbox area or equal-area polygon area), so
  missing edge strips and sea/fill cells lower it (POWER bbox ~0.99, CHIRPS bbox ~0.95 because sea cells are fill).
- GRACE uses the official GLOBAL file in $GLOBAL_DATA/grace (same granule as the bbox cut) so overlap
  weights include the 44.0-44.5N row; land_mask cells only; dates = Researcher CSV `date` column.
- Berkeley Earth 1° uses the global file in $GLOBAL_DATA (overlap x land-fraction weights), not the
  centre-selected bbox CSV.
- Stations: regional series = mean of station anomalies (per-station 1991-2020 normals, >=15 years per month);
  stations without that baseline are excluded (no baseline fallback - cut item). Station selection = point in region.
  **v1 LIMITATION (baseline, no fallback):** see the "Station baseline coverage" table per region. ukraine_bbox GSOM
  TAVG: 183 stations with data, only 36 have >=1 calendar month with a 15-year 1991-2020 baseline and 9 a full
  12-month baseline; 147 are dropped (49 of the 183 end before 2006). GHCN TAVG: 27 stations with data, 25 with a full
  baseline, 0 ending before 2006. Station series are therefore thin (few_stations_lt3 months) and GSOM has no annual
  values 2020-2024.
- Station counts per trend window = min / median number of stations contributing to monthly regional anomalies in
  the window (stations need a 1991-2020 baseline).
- Station trends: the HEADLINE window for GSOM/GHCN is 1981-2019 (`1981-2019_station_window`, headline=True).
  1981-2025 (and full/2001-2025) is kept but labelled `*_gappy`, with n and the missing years
  (GSOM 2020-2024; GHCN 2007-2009) in `missing_years`, and robust_call says it is NOT treated as robust.
  GHCN 1981-2019 also lacks 2007-2009 (n=36), noted in its robust_call.
- AIRS: 2025 (airs_2025_bias_unverified) is excluded from every AIRS trend; annual full window = 2003-2024, n=22.
- GRACE smoke test (CHANGED 14 Nov 2026, decided by the team lead via Thinker): fractional-overlap weights are the
  PRODUCTION method for GRACE. The BLOCKING GRACE check is now the production tidy series vs -11.242 ±0.005.
  Overlap adds partial edge cells (44.0-44.5N row, 40.0-40.5E column, 22.0-22.5E at 0.8) vs the original
  cell-centre selection, which gave -11.222. That centre-selection check is kept as a documented NON-blocking
  'legacy' check. (Difference ~0.2%, far below the inter-mascon spread of 3.17 cm/decade.)
- GRACE in trends.csv (Critique v1.1 re-review): the HEADLINE GRACE row is `series=monthly_deseasonalised_grace_headline_method`,
  `window=headline_grace_method` (complete-year climatology, drop 2002/2017/2018/2026, time_center, monthly
  deseasonalised OLS), computed by `ukpipe/grace_method.py` - the SAME function the blocking smoke test calls
  (ukraine_bbox -11.242, n=235). The generic 12/12 annual GRACE rows are labelled `*_gappy_annual12of12_convention`
  (n=14, missing 2011-2018 because of the 2011+ missing months and the GRACE/GRACE-FO gap) and the generic monthly row
  `full_generic_convention` (record-mean climatology, month-start time, n=252); both are a different convention,
  headline=False, not robust/headline.
- AIRS 2025: annual/seasonal rows in annual_seasonal.parquet carry `airs_2025_bias_unverified` (any year/season containing
  a flagged month); 2025 is excluded from all AIRS trends.
- GLDAS-2.1 `snowfall` and `SWE_inst` are labelled `role=forcing_diagnostic` (not findings, headline=False): 2.1 snow
  disagrees with 2.0 over 2000-2014 (annual means 78 vs 131 mm/yr, overlap slopes +14.6 vs -0.9, both n.s.), the 2000-2025
  window spans the 2.1 forcing breaks (Mar 2001, AGRMET after 2011, GALWEM from Jun 2025), dropping 2000 and 2025 gives
  ~-16 mm/yr per decade (n.s.), the HAC p fails Bonferroni in the annual family, and no non-GLDAS-2.1 snow source exists here.
- `LST_Day_clear_days` / `LST_Night_clear_days` are `role=sampling_diagnostic` (not climate headlines).
- Slope units: `slope_unit` in trends.csv = series unit + " per decade"; annual precip-type slopes are "mm/yr per decade"
  (e.g. GLDAS-2.1 snowfall -22.7 mm/yr per decade, about -20% of its 115.5 mm/yr mean per decade).
- Multiple testing (v1.4): primary p-values are repo Mann-Kendall Yue-Wang (`yw_p`). Bonferroni and
  Benjamini-Hochberg are applied inside the annual family and inside the monthly family.
  `mt_bonferroni_pass` / `mt_bh_pass` are those Yue-Wang corrections. HAC and Hamed-Rao lag-3 stay as
  sensitivity columns (`sens_*`). `robust_call` is the raw Yue-Wang 0.05 call (plus the diagnostic
  labels). A row is a detection only when Yue-Wang and the OLS n_eff cross-check agree and the
  Yue-Wang p-value survives the correction being quoted. Family sizes are in `n_tests_in_family`.
- GLDAS precip residual: `precip_total - rainfall_liquid - snowfall` is not identically zero (max |0.29| mm/month) because
  liquid rain is clipped at 0 per cell and Snowf has a slightly smaller valid mask than Rainf_f (e.g. 1,281 vs 1,288 cells,
  Jan 2000). The official liquid-only `Rainf_tavg` was NOT fetched, so liquid rain is derived (Rainf_f - Snowf).
- GPCC/CHIRPS levels: production (overlap-weighted, global files) 1981-2025 ANN means are GPCC 585.35 and CHIRPS
  686.78 mm/yr vs the old centre-cut bbox extracts 586.39 / 686.69 (ukraine_bbox) - the documented overlap-vs-centre
  effect, not a bug. Quote the production numbers.
- Mid-run loader bug (14 Nov 2026, v1.2 build, fixed before the final run): extending the cache signature to include
  MODIS QC files looked up `PRODUCTS[prod_key]`, which has no entry for the GPCC/CHIRPS custom loaders -> KeyError ->
  both sources FAILED in one intermediate run (status visible in run_meta). Fixed with `PRODUCTS.get`; the final series
  are clean overlap-weighted cuts (verified by Critique).
- AIRS 2025 is still a 12/12 year in annual_seasonal.parquet, but every 2025 AIRS annual/seasonal row carries
  `airs_2025_bias_unverified` and 2025 is excluded from all AIRS trends.
- GPCC: only `precip` is read. The `gauge` / `gauge_int` station-count fields in the v2025 files are NOT used (no gauge
  weighting or gauge-density flag in v1; early (1891+) values rest on sparse gauges).
- MODIS QC layers landed (14 Nov 2026): production MODIS is per-pixel QC'd (`qc_pixel_masked`); `no_qc` is only set
  if the QC files are missing (fallback to the unQC'd global files, then the old bbox extract).
- New global add-ons (14 Nov 2026), all via the same cutter (overlap weights, region config, cache, optional products
  skip with a note if their files are missing - the main source then still loads):
  - MERRA-2 U10M, V10M (M2TMNXSLV monthly means) and `WS10M_from_mean_UV` = sqrt(U10M²+V10M²) per cell, then averaged.
    Because the inputs are MONTHLY MEANS this is the speed of the mean wind vector, which UNDERESTIMATES the mean wind
    speed (directional cancellation): ukraine_mask mean 1.6 m/s vs POWER WS10M 4.3 m/s. Flagged; not a wind-speed climatology.
  - MERRA-2 T2MMAX, T2MMIN from M2SMNXSLV (monthly mean of DAILY max/min, verified: Jul 1980 bbox 24.2 / 14.5 °C vs
    T2M 19.6 °C), °C; `DTR` = T2MMAX - T2MMIN per cell (source merra2; the older `derived:DTR` is POWER-based).
  - GLDAS 2.0 and 2.1 (separate series, NO splice): `precip_total` = Rainf_f_tavg, `snowfall` = Snowf_tavg,
    `rainfall_liquid` = Rainf_f - Snowf per cell; kg m-2 s-1 -> mm/month (x86400 x days in month). In GLDAS-2,
    Rainf_f_tavg is already the TOTAL precipitation rate (rain + snow, forcing), so rain + snow is NOT added
    (that would double count snow); liquid rain is derived instead. Level check (ukraine_mask, 2001-2020 annual means):
    GLDAS 2.1 precip_total 726 mm/yr vs GPCC 574, MERRA-2 PRECTOTCORR 586, CHIRPS 687 -> GLDAS 2.1 forcing is wet;
    GLDAS forcing datasets changed over time, so treat GLDAS precip trends as model-forcing diagnostics, not observations.
- CHIRPS uses ONLY the global NetCDF archive (chirps-v3.0.monthly.nc, 1981-01..2026-09). The bbox COG extract is a
  fallback if that file is missing and is never spliced on (it differs from 2025-10 onward).
- Kyiv urban-rural night LST: NOT built - AppEEARS MOD11A2/MCD12Q1 data has not landed (folder empty).
- ERA5 ARCO 1940-1951 sample not loaded (12-year sample; not in the plan).
- Cut items skipped per plan: hot/frost/heavy-precip days, P-ET, TWS-GLDAS, baseline fallback, global tiling.
- Version/extent notes from the global files: IMERG global starts 1998-01 (extract 2000-06); CHIRPS global v3.0 file
  ends 2026-09 (bbox nc had 2026-10) and differs from the bbox nc only from 2025-10 on (preliminary months
  re-processed); MERRA-2 global ends 2026-09.
