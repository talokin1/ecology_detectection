# v1.4 Yue–Wang verdict review (14 Nov 2026)

**Verdict: the pipeline rerun is consistent with ADR-003. Do not add a precipitation detection.**

The v1.4 code was run for `ukraine_bbox`, `ukraine_mask`, and `ukraine_mask_no_crimea`. The blocking smoke test passed (POWER T2M +0.5526, HadCRUT5 +0.5793, GRACE −11.242, tolerance ±0.005). An independent call to `trend_stats.py` reproduced the pipeline Yue–Wang and OLS n_eff p-values exactly on POWER T2M, POWER precipitation, HadCRUT5, and the GRACE headline anomalies.

Primary columns are repository Yue–Wang. `mt_bonferroni_pass` and `mt_bh_pass` are Bonferroni and Benjamini–Hochberg on `yw_p` (bbox annual family n = 135, monthly n = 65; mask annual n = 161). A row is a detection only when Yue–Wang and the OLS n_eff cross-check both sit under 0.05 and the correction being quoted passes. HAC and Hamed–Rao lag-3 stay in the sensitivity columns.

## POWER precipitation

| Region | OLS mm/decade | Yue–Wang p | OLS n_eff p | Bonferroni | BH | v1.3 call |
|---|---:|---:|---:|---|---|---|
| ukraine_bbox | +14.83 | 0.0194 | 0.0860 | fail | pass | method-dependent (HAC p = 0.135, Hamed–Rao p = 0.019) |
| ukraine_mask | +10.13 | 0.0766 | 0.2245 | fail | fail | not a detection |

The bbox Yue–Wang p-value is 0.019, which is what a Yue–Wang-only rule would call significant. The OLS cross-check does not agree (p = 0.086). Bonferroni fails. The mask is not significant. Other precipitation series (CHIRPS, IMERG, MERRA-2, GLDAS) do not agree in sign or significance. **Not a detection.** GPCC on the bbox does agree between Yue–Wang (p = 0.025) and OLS (p = 0.027) and passes BH only, at +3.28 mm/decade, and it fails on both masks. With the gauge network thinning (see `stats/gpcc_gauge_counts.md`) and the other products, it is not a headline.

## What did not flip

Temperature series and GRACE that survived Bonferroni under the v1.3 HAC/HR rule still survive Bonferroni under Yue–Wang on `ukraine_mask`. No previously robust warming or GRACE headline was lost. Headline rows whose raw call text changed are in `data/pipeline/outputs/verdict_changes_v1.3_to_v1.4.csv` (205 rows with a changed call string, including diagnostic labels). The new raw Yue–Wang hits that were not v1.3 "robust" calls (POWER wind, CRU PET, bbox growing-season EVI) all fail Bonferroni, and wind disagrees with the OLS cross-check. They are not detections.

## Multiple-testing survivors (headline rows, Yue–Wang Bonferroni)

On `ukraine_mask`: temperature series (POWER, MERRA-2, GISTEMP, HadCRUT5, Berkeley, CRU, GLDAS-2.0 Tair, GHCN/GSOM maxima and GSOM average, MODIS night LST) and GRACE TWS. CRU vapour pressure also survives. That matches the v1.3 Bonferroni set in kind. BH-only rows are listed in `qc_report.md` and are not Bonferroni detections.
