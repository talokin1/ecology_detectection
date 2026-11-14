"""OFFICIAL trend significance (decided by the team lead via Thinker, 14 Nov 2026 15:17): the repo's Mann-Kendall with the
Yue & Wang (2004) AR(1) effective-sample-size correction, Theil-Sen slope and verdict.

The implementation is imported, not copied, from the checkout's
.claude/skills/trend-stats/scripts/trend_stats.py (override with TREND_STATS_PY).
Methods: docs/10-methods.md and ADR-002. Intended parameters, as documented there and in
SKILL.md: alpha=0.05; method="yue_wang" (r1 = lag-1 autocorrelation of the Sen-detrended series, clipped at >= 0);
Sen CI uses the YW-corrected Var(S); monthly series -> analyze_series(obs_per_year=12, deseasonalize_monthly=True);
annual/seasonal series -> analyze_series(obs_per_year=1, deseasonalize_monthly=False). Verdict levels:
insufficient (<10 yr) | strong (p<0.01 and CI excludes 0) | moderate (p<0.05) | weak (p<0.10) | none.
The GRACE headline method keeps its own anomaly/time construction (grace_method.py) and is tested with the repo's
mann_kendall(method="yue_wang") + sens_slope(var_s=...) + verdict() building blocks.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from .paths import load_module, trend_stats_py

REPO_TS_PATH = trend_stats_py()
ALPHA = 0.05
TS = load_module(REPO_TS_PATH, "repo_trend_stats")
REPO_TS_MD5 = hashlib.md5(REPO_TS_PATH.read_bytes()).hexdigest()

EMPTY = dict(yw_p=np.nan, yw_z=np.nan, yw_tau=np.nan, yw_variance_correction=np.nan, yw_sen_slope_per_decade=np.nan,
             yw_sen_ci95_lo_decade=np.nan, yw_sen_ci95_hi_decade=np.nan, yw_n=np.nan, yw_record_years=np.nan,
             yw_verdict_level="", yw_verdict_direction="", yw_ols_neff_p=np.nan, yw_noise_r1=np.nan,
             yw_years_to_detect=np.nan, yw_error="", yw_warning="")


def _pack(res, gaps_frac=np.nan):
    out = dict(EMPTY)
    out.update(yw_p=res["mk"]["p"], yw_z=res["mk"]["z"], yw_tau=res["mk"]["tau"],
               yw_variance_correction=res["mk"]["variance_correction"],
               yw_sen_slope_per_decade=res["sen_slope_per_decade"],
               yw_sen_ci95_lo_decade=res["sen_ci95_per_decade"][0], yw_sen_ci95_hi_decade=res["sen_ci95_per_decade"][1],
               yw_n=res["n"], yw_record_years=res["record_years"], yw_verdict_level=res["verdict"]["level"],
               yw_verdict_direction=res["verdict"]["direction"], yw_ols_neff_p=res["ols"]["p"],
               yw_noise_r1=res["noise"]["r1"], yw_years_to_detect=res["years_to_detect"])
    w = []
    if res["record_years"] < 20:
        w.append("record<20yr")
    if np.isfinite(gaps_frac) and gaps_frac > 0.2:
        w.append(f"gaps>{20}%")
    out["yw_warning"] = ";".join(w)
    return out


def yw_annual(years, values):
    """Annual (or one-season-per-year) series. Dates = 1 Jan of each year (decimal year = integer year)."""
    years = np.asarray(years, int); values = np.asarray(values, float)
    ok = np.isfinite(values)
    try:
        dates = np.array([f"{y}-01-01" for y in years[ok]], dtype="datetime64[D]")
        res = TS.analyze_series(dates, values[ok], obs_per_year=1, deseasonalize_monthly=False, alpha=ALPHA)
    except Exception as e:  # documented, NOT patched (e.g. n<4, n>3000)
        out = dict(EMPTY); out["yw_error"] = f"{type(e).__name__}: {e}"; return out
    span = years[ok].max() - years[ok].min() + 1
    return _pack(res, 1 - ok.sum() / span)


def yw_monthly(dates, values):
    """Monthly series; the repo deseasonalises itself (record-mean calendar-month climatology)."""
    d = pd.DatetimeIndex(dates); v = np.asarray(values, float)
    ok = np.isfinite(v)
    try:
        res = TS.analyze_series(d[ok].values.astype("datetime64[D]"), v[ok], obs_per_year=12,
                                deseasonalize_monthly=True, alpha=ALPHA)
    except Exception as e:
        out = dict(EMPTY); out["yw_error"] = f"{type(e).__name__}: {e}"; return out
    span = (d[ok].max().year - d[ok].min().year) * 12 + d[ok].max().month - d[ok].min().month + 1
    return _pack(res, 1 - ok.sum() / span)


def yw_on_anomalies(t, anomalies, units=""):
    """Pre-built anomalies at given decimal-year times (GRACE headline method): repo building blocks."""
    t = np.asarray(t, float); y = np.asarray(anomalies, float)
    ok = np.isfinite(t) & np.isfinite(y); t, y = t[ok], y[ok]
    try:
        mk = TS.mann_kendall(t, y, alpha=ALPHA, method="yue_wang")
        sen = TS.sens_slope(t, y, alpha=ALPHA, var_s=mk["var_s"])
        ols = TS.ols_trend(t, y, alpha=ALPHA, adjust_autocorr=True)
        resid = y - (sen["intercept"] + sen["slope"] * t)
        nstd, nr1 = float(np.std(resid, ddof=1)), TS.lag1_autocorr(resid)
        rec = float(t.max() - t.min() + 1 / 12)
        nstar = TS.years_to_detect(nstd, nr1, sen["slope"], 12)
        vd = TS.verdict(mk["p"], [c * 10 for c in sen["ci"]], sen["slope"] * 10, units, rec, nstar)
    except Exception as e:
        out = dict(EMPTY); out["yw_error"] = f"{type(e).__name__}: {e}"; return out
    res = {"mk": mk, "sen_slope_per_decade": sen["slope"] * 10, "sen_ci95_per_decade": [c * 10 for c in sen["ci"]],
           "n": int(y.size), "record_years": rec, "verdict": {"level": vd.level, "direction": vd.direction},
           "ols": {"p": ols["p"]}, "noise": {"r1": nr1}, "years_to_detect": nstar}
    return _pack(res)


def yw_raw_call(r):
    if r.get("yw_error"):
        return f"repo-YW not computed ({r['yw_error']})"
    if r.get("yw_verdict_level") == "insufficient":
        return "insufficient record (<10 yr; repo verdict)"
    p = r.get("yw_p")
    if p is None or not np.isfinite(p):
        return "repo-YW not computed"
    lvl = r.get("yw_verdict_level")
    if p < ALPHA:
        return f"significant at 0.05 (repo MK Yue-Wang; verdict {lvl})"
    return f"not significant at 0.05 (repo MK Yue-Wang; verdict {lvl})"
