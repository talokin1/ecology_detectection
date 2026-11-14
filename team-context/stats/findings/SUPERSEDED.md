# stats/findings: superseded

SUPERSEDED (2026-11-14): pre-pipeline findings using HAC + Hamed–Rao wording. The official test is repo MK Yue–Wang with the OLS n_eff cross-check and the conservative verdict (.claude/skills/trend-stats/SKILL.md:26-28). Current numbers: data/pipeline/outputs/v1.4/. Never send numbers from this file to the UI or slides (MC-4).

This covers every file in this folder, including `trend_summary_pre_pipeline.csv` (a CSV cannot carry a banner). Its `mk_yw_p` column is pymannkendall's Yue–Wang and must not be quoted (see `sens_pymk_yw_p_do_not_use` in v1.4).

Soil moisture: **Restated 2026-11-14 (A2-05, conservative-verdict rule):** warm-season (Apr–Oct 7/7) soil moisture 1991–2024 shows **moderate drying**: Sen slope −0.0025 m³ m⁻³/decade (95% CI −0.0051 to −0.0004), repo MK Yue–Wang p = 0.01505, OLS n_eff cross-check p = 0.01695 (the two methods agree). Caveat: the result depends on the start year: from 2002 or 2003 it is not significant, and from 2007 (ASCAT) the sign flips (n.s.). Quote it as "moderate drying since 1991, sensitive to start year", never as a detection from 2002 on.
