# Caveats for the Ukraine analysis archive

Read this before quoting a number from an older file in `stats/findings/`. Those files are the pre-pipeline record (HAC + Hamed–Rao wording). The official wording is ADR-003 and `data/pipeline/qc_report.md`.

## Trend test
Repository Yue–Wang is primary. OLS n_eff is the cross-check. If they disagree, it is not a detection. Bonferroni and BH are on the Yue–Wang p-value. HAC and Hamed–Rao lag-3 are sensitivity columns only. Do not use pymannkendall's Yue–Wang routine.

## Precipitation
No precipitation detection. POWER bbox Yue–Wang p = 0.019 disagrees with OLS n_eff p = 0.086, so under main's conservative-verdict rule (`.claude/skills/trend-stats/SKILL.md:26-28`) the row is **method-dependent, not a detection**, and its BH pass is cleared (B-3, 2026-11-14). The mask is not significant. Products disagree on the sign. GLDAS-2.0 `rainfall_liquid` (bbox, YW p = 0.040, OLS n_eff p = 0.067) is method-dependent too, and is a forcing diagnostic anyway. See `team/reviews/yw_v14_review.md` and `data/pipeline/outputs/v1.4/verdict_changes_b3.csv`.

## Wind
No wind-speed detection. POWER `WS10M` annual is Yue–Wang significant in all three regions (p = 0.024 / 0.033 / 0.034) but the OLS n_eff cross-check is not (p = 0.092 / 0.153 / 0.121). The conservative verdict is method-dependent, not a detection (B-3). Do not quote "stilling" as a finding.

## GPCC gauges
Gauges inside the bbox fell from about 500 in the 1980s to about 230 in 2020–2025 (`gpcc_gauge_counts.md`). Early decades are sparse (about 60 gauges in 1891–1929).

## GRACE
Headline is the overlap-weight monthly series: bbox −11.242 cm/decade, mask −12.120 cm/decade, mask without Crimea −12.364 cm/decade, n = 235, drop 2002/2017/2018/2026, time at the solution centre. Not groundwater. The dictionary lines that say GRACE was not downloaded are stale.

## AIRS 2025
2025 is excluded from AIRS trends (`airs_2025_bias_unverified`). The annual window is 2003–2024, n = 22.

## GLDAS
Do not splice 2.0 and 2.1. `Qs_acc` in the pipeline is ×8×days (mm/month). The pre-pipeline annual Qs totals were about 240× too small; do not quote them. On the mask, GLDAS-2.1 `Qs_acc` OLS slope is -10.87 mm/decade (Yue–Wang p = 0.000421); it passes BH and fails Bonferroni, and it is still a model runoff field. GLDAS precipitation and GLDAS-2.1 snow are forcing diagnostics, not observations.

## MODIS and vegetation
LST is clear-sky. VI QC removes snowy winter pixels. Use JJA and Apr–Sep, and do not headline a seasonal VI row that fails Bonferroni. Annual VI includes low-coverage winter months.

## Soil moisture
CCI COMBINED v09.2 is break-adjusted and scaled to GLDAS-Noah. Not an independent level check. **Restated 2026-11-14 (A2-05, conservative-verdict rule):** warm-season (Apr–Oct 7/7) soil moisture 1991–2024 shows **moderate drying**: Sen slope −0.0025 m³ m⁻³/decade (95% CI −0.0051 to −0.0004), repo MK Yue–Wang p = 0.01505, OLS n_eff cross-check p = 0.01695 (the two methods agree). Caveat: the result depends on the start year: from 2002 or 2003 it is not significant, and from 2007 (ASCAT) the sign flips (n.s.). Quote it as "moderate drying since 1991, sensitive to start year", never as a detection from 2002 on.

## OMI, SWOT, urban heat, ERA5
OMI and SWOT are bbox-only. OMI trends: `omi_bbox_trends.md`. Ozone ends in 2018-12. SWOT is about three years and is not a climate trend; the Kherson step is not a confirmed dam-break signal. The Kyiv 1 km urban-heat task was still processing, so there is no urban-minus-rural series. ERA5 was not downloaded (`CDSAPI_KEY` was unset).

## Masks
`ukraine_mask` uses Natural Earth 10m Ukraine point-of-view (Crimea included, 597,211 km²). `ukraine_mask_no_crimea` uses the default file (570,178 km²). Country series (Berkeley, CRU) use the producer's own mask. Shapefiles are fetched with `data/pipeline/fetch_natural_earth.py`, not committed.

## CHIRPS
Use the global monthly NetCDF only (1981-01 through 2026-09 in the archive file). Do not splice the bbox COG extract from 2025-10 onward.

## Stations
GSOM has no annual values in 2020–2024. The station headline window is 1981–2019. GHCN and GSOM share the GHCN family with GISTEMP, Berkeley, and CRU. They are not independent confirmations of POWER or MERRA-2.
