# ADR-003 — Yue–Wang is the official test for the Ukraine analysis archive

- Status: Accepted
- Date: 2026-11-14
- Deciders: team lead (15:17, via Thinker). Critique's opposite proposal was not adopted.
- Requirement IDs: R-04, R-05, R-16

## Context
`docs/10-methods.md` and ADR-002 already name Mann–Kendall with the Yue & Wang (2004) AR(1) correction, implemented in `.claude/skills/trend-stats/scripts/trend_stats.py`, as the repository default. The Ukraine case study had been worded with a different pair: OLS Newey–West HAC (lag 1 on annual series, lag 3 on monthly) and Hamed–Rao with lag fixed at 3, in `trend_methods.py`. "Robust" meant both of those p-values were below 0.05.

Those are not the same test as the repository's Hamed–Rao (significant-lag rank ACF). pymannkendall's Yue–Wang routine is also not the repository routine: on the three series below it reports p-values near zero where `trend_stats.mann_kendall(..., method="yue_wang")` does not.

Critique asked to keep HAC + Hamed–Rao lag-3 as the only published primary (`team-context/team/reviews/stats_archive_review.md`). The team lead rejected that and kept the repository Yue–Wang test as the official primary. This ADR records that decision. ADR-002 and `docs/10-methods.md` stay as they are.

## Options
1. HAC + Hamed–Rao lag-3 as the published primary, repository Yue–Wang as a sensitivity column (Critique's proposal).
2. **Repository Yue–Wang as the published primary, HAC + Hamed–Rao lag-3 kept as sensitivity columns** (team lead, 15:17).
3. pymannkendall Yue–Wang as the primary. Rejected: it does not match `trend_stats.py`.

## Decision
Option 2.

- Import `trend_stats.py`. Do not reimplement it. The pipeline loads it from the checkout (override `TREND_STATS_PY`).
- Primary p-value: `mann_kendall(..., method="yue_wang")` via `analyze_series` for annual and monthly series. The GRACE headline row keeps its own anomaly and `time_center` construction, then calls the same building blocks.
- Cross-check: OLS with lag-1 effective n (`ols_trend(..., adjust_autocorr=True)`). If Yue–Wang and that cross-check disagree at 0.05, the row is not a detection. Use the more conservative result.
- Multiple testing: Bonferroni and Benjamini–Hochberg (q = 0.05) on the Yue–Wang p-values, separately for the annual family and the monthly family (`mt_bonferroni_pass`, `mt_bh_pass`). A family-wise claim has to name which correction it passed.
- Sensitivity, not wording: vendored `team-context/stats/trend_methods.py` (same bytes as `team-context/data/pipeline/vendor/trend_methods.py`). Columns `hac1_p` / `hac3_p` / `mk_hr_p` and `sens_mt_*`. The library body matches the pre-archive file (SHA-256 `53c68403550f19024ed36cdf45e92c0d92e2e17ab9532decafa53140893bac4a`) except one comment: the review path no longer contains a machine-absolute prefix. Committed SHA-256 is `b49dad62cd993a15b79d038654022a2400326357d753e593ab0e98f8c7b4ac70`.
- Do not call a row a detection from Hamed–Rao or Yue–Wang alone when the cross-check or the quoted multiple-testing correction fails.

## Evidence checked on 14 Nov 2026
Independent calls to `trend_stats.py` match the v1.4 pipeline columns exactly on three bbox series:

| Series | OLS slope / decade | Sen / decade | Yue–Wang p | OLS n_eff p |
|---|---:|---:|---:|---:|
| POWER T2M annual 1981–2025 | +0.5526 °C | +0.5343 °C | 9.79e-06 | 4.33e-06 |
| GRACE headline monthly anomalies | −11.242 cm | −11.258 cm | 1.10e-05 | 4.62e-07 |
| POWER PRECTOTCORR annual 1981–2025 | +14.83 mm | +16.09 mm | 0.0194 | 0.0860 |

POWER precipitation is the row that changes wording. HAC p = 0.135 (not significant) and Hamed–Rao p = 0.019, so v1.3 called it method-dependent. Yue–Wang p = 0.0194, but the OLS cross-check is 0.086, Bonferroni fails, and the Ukraine mask is not significant (Yue–Wang p = 0.077). Benjamini–Hochberg passes on the bbox only. It is not a detection. Detail: `team-context/team/reviews/yw_v14_review.md`.

## Consequences
- v1.3 trend tables stay in `team-context/data/pipeline/outputs/archive_v1.3/` as the HAC/HR record.
- v1.4 tables and `qc_report.md` use Yue–Wang for `robust_call` and for `mt_*`.
- Temperature series and GRACE that were Bonferroni survivors under HAC/HR remain Bonferroni survivors under Yue–Wang on the primary mask. No previously robust warming or GRACE headline was lost.
- Smoke test is unchanged: it checks OLS slopes (POWER +0.5526, HadCRUT5 +0.5793, GRACE −11.242, tolerance ±0.005), not the p-value column.
