"""Conservative-verdict rule (B-3). SI-assisted (GOD / Grok Bot), pending team review.

Rule: `.claude/skills/trend-stats/SKILL.md:26-28` on main. If the primary test (repo MK Yue-Wang) and the
OLS n_eff cross-check disagree on significance at 0.05, say so and use the more conservative verdict.

For a row where `yw_ols_neff_agree` is False:
- YW p < 0.05 but OLS n_eff p >= 0.05: the "significant at 0.05 (repo MK Yue-Wang ...)" call is replaced by
  METHOD_DEPENDENT_CALL everywhere it appears in `robust_call` (including "[raw call: ...]" suffixes), and
  `mt_bonferroni_pass` / `mt_bh_pass` are cleared.
- YW p >= 0.05 but OLS n_eff p < 0.05: the YW call is already the conservative one; a
  "methods disagree" note is appended and the multiple-testing flags are cleared.
The raw Yue-Wang call stays in `yw_raw_call`; `conservative_override` marks the rows that changed.
"""
from __future__ import annotations

import re

import pandas as pd

ALPHA = 0.05
METHOD_DEPENDENT_CALL = ("method-dependent: YW p<0.05, OLS n_eff p>=0.05, not a detection "
                         "(conservative verdict, SKILL.md rule 2)")
DISAGREE_NOTE = " [methods disagree: OLS n_eff p<0.05, YW p>=0.05; conservative verdict = not significant]"
_SIG = re.compile(r"(?<!not )significant at 0\.05 \(repo MK Yue-Wang; verdict [a-z]+\)")


def apply_conservative_verdict(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of a v1.4 trend table with the conservative-verdict rule applied."""
    out = df.copy()
    agree = (out["yw_p"] < ALPHA) == (out["yw_ols_neff_p"] < ALPHA)
    out["yw_ols_neff_agree"] = agree
    both_finite = out["yw_p"].notna() & out["yw_ols_neff_p"].notna()
    dis = (~agree) & both_finite
    yw_only = dis & (out["yw_p"] < ALPHA)
    ols_only = dis & (out["yw_p"] >= ALPHA)
    calls = out["robust_call"].astype(str)
    out.loc[yw_only, "robust_call"] = [_SIG.sub(METHOD_DEPENDENT_CALL, c) for c in calls[yw_only]]
    out.loc[ols_only, "robust_call"] = [c if DISAGREE_NOTE in c else c + DISAGREE_NOTE for c in calls[ols_only]]
    for col in ("mt_bonferroni_pass", "mt_bh_pass"):
        if col in out:
            out[col] = out[col].astype(bool) & ~dis
    out["conservative_override"] = dis
    return out


def violations(df: pd.DataFrame) -> pd.DataFrame:
    """Rows that still break the rule (gate for B-3: must be empty)."""
    dis = ~df["yw_ols_neff_agree"].astype(bool) & df["yw_p"].notna() & df["yw_ols_neff_p"].notna()
    bad_call = df["robust_call"].astype(str).str.contains(_SIG)
    bad_mt = df.get("mt_bh_pass", False) | df.get("mt_bonferroni_pass", False)
    return df[dis & (bad_call | bad_mt)]


# A2-07 / A2-12: pymannkendall's Yue-Wang p and the sensitivity Theil-Sen are NOT the reported result.
SENS_RENAMES = {
    "mk_yw_p": "sens_pymk_yw_p_do_not_use",
    "mk_yw_h": "sens_pymk_yw_h_do_not_use",
    "theil_sen_per_decade": "sens_theil_sen_per_decade",
    "theil_sen_per_year": "sens_theil_sen_per_year",
}


def rename_sensitivity_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={k: v for k, v in SENS_RENAMES.items() if k in df.columns})
