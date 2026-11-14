#!/usr/bin/env python3
"""Autocorrelation-aware trend tests used by the Ukraine sample analysis.

Theil–Sen is always computed against the actual time axis (calendar year or
decimal year) via scipy.stats.theilslopes. Do not use pymannkendall's unit-index
slope for monthly data (that slope is per observation step, not per year).

Hamed–Rao is called with lag=3 (as proposed by Hamed and Rao 1998). The
pymannkendall default lag=None uses all lags and is not used here. Negative
residual lag-1 autocorrelation makes Hamed–Rao anti-conservative; those rows are
flagged, and a strongly negative residual r (r < -0.3) is not allowed to satisfy
the “robust” rule. Hamed–Rao also assumes equally spaced observations, which
GSOM’s 2020–2024 hole and SWOT months missing after ice/dark filters violate.

Yue–Wang MK is computed but not used for wording: it can return implausibly
small p-values on these series (see team-context/team/reviews/ukraine_methods_review.md).

For monthly series the “robust” rule uses HAC lag-3, not only lag-1.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pymannkendall as mk
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.multitest import multipletests

# Residual lag-1 below this is treated as strongly anti-conservative for HR.
STRONG_NEG_R = -0.3
HR_LAG = 3


def lag1(x) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 4:
        return float("nan")
    return float(np.corrcoef(x[1:], x[:-1])[0, 1])


def _unequal_spacing(time: np.ndarray) -> bool:
    if len(time) < 3:
        return False
    dts = np.diff(time)
    med = float(np.median(dts))
    if not np.isfinite(med) or med <= 0:
        return False
    return bool(np.any(dts > 1.5 * med + 1e-12))


def trend_stats(time, values, min_n: int = 8) -> Optional[dict]:
    """OLS + AR(1)-adjusted OLS + Newey–West HAC + time-aware Sen + MK variants.

    `time` must be in years (or decimal years). Slopes in the result are
    *per year* (`*_per_year`) and *per decade* (`*_per_decade` = per_year * 10).

    Hamed–Rao uses lag=3. See module docstring for anti-conservative and
    equal-spacing caveats.
    """
    time = np.asarray(time, dtype=float)
    values = np.asarray(values, dtype=float)
    mask = np.isfinite(time) & np.isfinite(values)
    time, values = time[mask], values[mask]
    n = int(len(values))
    if n < min_n:
        return None

    order = np.argsort(time)
    time, values = time[order], values[order]

    lr = stats.linregress(time, values)
    fitted = lr.intercept + lr.slope * time
    resid = values - fitted
    r = lag1(resid)
    r_series = lag1(values)
    if np.isfinite(r) and abs(r) < 0.99:
        infl = math.sqrt((1.0 + r) / (1.0 - r))
        n_eff = n * (1.0 - r) / (1.0 + r)
    else:
        infl, n_eff = float("nan"), float(n)
    se = lr.stderr
    se_adj = se * infl if np.isfinite(infl) else float("nan")
    if np.isfinite(se_adj) and se_adj > 0 and n_eff > 3:
        t_adj = lr.slope / se_adj
        df = max(n_eff - 2, 1)
        p_ar1 = float(2 * stats.t.sf(abs(t_adj), df))
        tcrit = float(stats.t.ppf(0.975, df))
        ci_lo_ar1 = (lr.slope - tcrit * se_adj) * 10
        ci_hi_ar1 = (lr.slope + tcrit * se_adj) * 10
    else:
        p_ar1 = ci_lo_ar1 = ci_hi_ar1 = float("nan")
        se_adj = float("nan")

    tcrit_n = float(stats.t.ppf(0.975, n - 2))
    ci_lo_ols = (lr.slope - tcrit_n * se) * 10
    ci_hi_ols = (lr.slope + tcrit_n * se) * 10

    X = sm.add_constant(time)
    model = sm.OLS(values, X).fit()
    hac = {}
    for nl in (1, 3):
        h = model.get_robustcov_results(cov_type="HAC", maxlags=nl)
        hac[f"hac{nl}_p"] = float(h.pvalues[1])
        hac[f"hac{nl}_se_decade"] = float(h.bse[1] * 10)

    sen = stats.theilslopes(values, time)
    mk_orig = mk.original_test(values)

    def _mk(fn):
        try:
            res = fn(values)
            return float(res.p), bool(res.h)
        except Exception:
            return float("nan"), None

    try:
        hr_res = mk.hamed_rao_modification_test(values, lag=HR_LAG)
        hr_p, hr_h = float(hr_res.p), bool(hr_res.h)
    except Exception:
        hr_p, hr_h = float("nan"), None
    yw_p, yw_h = _mk(mk.yue_wang_modification_test)
    tfpw_p, tfpw_h = _mk(mk.trend_free_pre_whitening_modification_test)

    start, end = float(time.min()), float(time.max())
    return {
        "n": n,
        "start": start,
        "end": end,
        "lin_slope_per_year": float(lr.slope),
        "lin_slope_per_decade": float(lr.slope * 10),
        "lin_intercept": float(lr.intercept),
        "lin_r": float(lr.rvalue),
        "lin_p": float(lr.pvalue),
        "lin_stderr_decade": float(se * 10) if se is not None else float("nan"),
        "lin_ci95_lo_decade": ci_lo_ols,
        "lin_ci95_hi_decade": ci_hi_ols,
        "r_resid_lag1": r,
        "r_series_lag1": r_series,
        "n_eff_ar1": float(n_eff),
        "lin_p_ar1": p_ar1,
        "lin_stderr_ar1_decade": float(se_adj * 10) if np.isfinite(se_adj) else float("nan"),
        "lin_ci95_ar1_lo_decade": ci_lo_ar1,
        "lin_ci95_ar1_hi_decade": ci_hi_ar1,
        **hac,
        "theil_sen_per_year": float(sen[0]),
        "theil_sen_per_decade": float(sen[0] * 10),
        "mk_p": float(mk_orig.p),
        "mk_h": bool(mk_orig.h),
        "mk_trend": mk_orig.trend,
        "mk_z": float(mk_orig.z),
        "mk_hr_p": hr_p,
        "mk_hr_h": hr_h,
        "mk_hr_lag": HR_LAG,
        "hr_anti_conservative": bool(np.isfinite(r) and r < 0),
        "hr_strongly_anti_conservative": bool(np.isfinite(r) and r < STRONG_NEG_R),
        "hr_unequal_spacing": _unequal_spacing(time),
        "mk_tfpw_p": tfpw_p,
        "mk_tfpw_h": tfpw_h,
        "mk_yw_p": yw_p,
        "mk_yw_h": yw_h,
        # kept only to document the unit-index pitfall; not used in wording
        "theil_sen_unitindex_x10": float(mk_orig.slope * 10),
    }


def robust_call(
    tr: Optional[dict],
    alpha: float = 0.05,
    monthly: bool = False,
    short_record: bool = False,
) -> str:
    """Label used in findings.

    Annual series: HAC lag-1 p < 0.05 and Hamed–Rao (lag=3) p < 0.05.
    Monthly series: HAC lag-3 p < 0.05 and Hamed–Rao (lag=3) p < 0.05.
    Strongly negative residual AR (r < -0.3) makes HR anti-conservative; those
    rows are not called robust on the basis of HR. Short records (SWOT ~3.3 yr)
    are labelled too short for climate inference even if unadjusted p-values
    are small.
    """
    if tr is None:
        return "insufficient data"
    if short_record:
        return "too short for climate inference"
    hac = tr.get("hac3_p") if monthly else tr.get("hac1_p")
    hr = tr.get("mk_hr_p")
    tfpw = tr.get("mk_tfpw_p")
    r = tr.get("r_resid_lag1", float("nan"))
    strongly_ac = bool(np.isfinite(r) and r < STRONG_NEG_R)
    if strongly_ac:
        if hac is not None and np.isfinite(hac) and hac < alpha:
            return "HAC significant; Hamed–Rao anti-conservative (negative residual AR); not treated as robust"
        # fall through without using HR as the modified-MK confirmation
        mod_p = tfpw if tfpw is not None and np.isfinite(tfpw) else float("nan")
    else:
        mod_p = hr if hr is not None and np.isfinite(hr) else tfpw
    if hac is None or not np.isfinite(hac) or mod_p is None or not np.isfinite(mod_p):
        return "tests incomplete"
    if hac < alpha and mod_p < alpha:
        tag = "HAC lag-3 and Hamed–Rao" if monthly else "HAC and Hamed–Rao"
        return f"robust at 0.05 ({tag})"
    if (hac < alpha) != (mod_p < alpha) or (tr["lin_p"] < alpha) != (tr["mk_p"] < alpha):
        return "method-dependent (not treated as a clear detection)"
    return "not significant at 0.05 on HAC and Hamed–Rao"


def fmt_trend(
    tr: Optional[dict],
    unit_per_decade: str,
    lead: str = "decade",
    monthly: bool = False,
    short_record: bool = False,
) -> str:
    if tr is None:
        return "insufficient data"
    start, end = tr["start"], tr["end"]
    if start == int(start) and end == int(end):
        span = f"{int(start)}–{int(end)}"
    else:
        span = f"{start:.2f}–{end:.2f}"
    call = robust_call(tr, monthly=monthly, short_record=short_record)
    sen = tr["theil_sen_per_decade"]
    hr_p = tr["mk_hr_p"]
    hr_txt = f"<1e-16" if (hr_p is not None and np.isfinite(hr_p) and hr_p == 0) else f"{hr_p:.3g}"
    notes = []
    if tr.get("hr_anti_conservative"):
        notes.append("Hamed–Rao is anti-conservative when residual lag-1 AR is negative")
    if tr.get("hr_unequal_spacing"):
        notes.append("Hamed–Rao assumes equal spacing; this series has gaps")
    note = ("  " + "; ".join(notes) + ".") if notes else ""
    return (
        f"{tr['lin_slope_per_decade']:+.3f} {unit_per_decade} "
        f"(OLS p={tr['lin_p']:.3g}, AR(1)-adj p={tr['lin_p_ar1']:.3g}, "
        f"HAC lag-1 p={tr['hac1_p']:.3g}, HAC lag-3 p={tr['hac3_p']:.3g}; "
        f"n_eff≈{tr['n_eff_ar1']:.1f}, residual r={tr['r_resid_lag1']:.2f}); "
        f"time-aware Theil–Sen {sen:+.3f}; "
        f"MK p={tr['mk_p']:.3g}, Hamed–Rao (lag=3) p={hr_txt}, TFPW p={tr['mk_tfpw_p']:.3g}; "
        f"n={tr['n']}, {span}. Call: {call}.{note}"
    )


def add_multiple_testing(
    rows: list[dict],
    p_col: str,
    prefix: str,
    family_size_key: str = "n_tests_in_family",
) -> None:
    pvals = []
    idx = []
    for i, r in enumerate(rows):
        p = r.get(p_col)
        if p is not None and np.isfinite(p):
            pvals.append(float(p))
            idx.append(i)
    n = len(pvals)
    if n == 0:
        return
    bon = 0.05 / n
    rej_b, p_b, _, _ = multipletests(pvals, alpha=0.05, method="bonferroni")
    rej_h, p_h, _, _ = multipletests(pvals, alpha=0.05, method="fdr_bh")
    for j, i in enumerate(idx):
        rows[i][f"{prefix}_bonferroni_alpha"] = bon
        rows[i][f"{prefix}_bonferroni_p"] = float(p_b[j])
        rows[i][f"{prefix}_bonferroni_reject"] = bool(rej_b[j])
        rows[i][f"{prefix}_bh_q"] = float(p_h[j])
        rows[i][f"{prefix}_bh_reject"] = bool(rej_h[j])
        rows[i][family_size_key] = n


def year_label(start, end) -> str:
    if float(start) == int(float(start)) and float(end) == int(float(end)):
        return f"{int(start)}-{int(end)}"
    return f"{float(start):.2f}-{float(end):.2f}"
