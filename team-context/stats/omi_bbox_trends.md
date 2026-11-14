# OMI bbox trends (14 Nov 2026)

The OMI files are single bbox means (22.1–40.2°E, 44.4–52.4°N). They have no grid, so `ukraine_mask` cannot be cut from them. The pipeline skips OMI on the masks for that reason. SWOT is the same kind of limit and is too short for a climate trend.

Test: repository `analyze_series` on annual means of months with at least 15 days, Yue–Wang primary, OLS n_eff cross-check. NO2 is scaled to 10^15 molecules cm^-2. This is a four-series family at most; none of the p-values are near 0.05, so Bonferroni would not create a detection either.

| Series | Years | n | Sen / decade | Yue–Wang p | OLS n_eff p | Call |
|---|---|---:|---:|---:|---:|---|
| Tropospheric NO2, cloud-screened, row-anomaly era | 2007–2025 | 19 | −0.066 × 10^15 cm^-2 | 0.32 | 0.60 | not significant |
| Tropospheric NO2, not cloud-screened | 2007–2025 | 19 | −0.039 × 10^15 cm^-2 | 0.77 | 0.83 | not significant |
| Total ozone column (OMTO3e) | 2005–2018 | 14 | +3.42 DU | 0.58 | 0.61 | not significant |

NO2 months on disk run 2004-10 through 2026-11 (266 months). Annual tests drop 2004 (starts in October) and 2026 (partial), and start in 2007 because of the row anomaly. Nineteen years is under the 20-year warning. Ozone months on disk run 2004-10 through 2018-12 (171 months). That extract was not extended, so the ozone conclusion is only through 2018. Fourteen years is a short record. Neither gas is a detection.
