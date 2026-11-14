"""Reference implementation of trend statistics for the Earth System Trend Detective.

Single source of truth for trend/significance computations. Depends only on numpy + scipy.
Methods and citations: docs/10-methods.md.

SI-assisted (Claude, Anthropic); reviewed and tested by the team (see tests).

Main entry point:
    analyze_series(dates, values, units=..., deseasonalize_monthly=True) -> dict
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable, Sequence

import numpy as np
from scipy import stats

__all__ = [
    "decimal_years",
    "monthly_climatology",
    "deseasonalize",
    "lag1_autocorr",
    "ols_trend",
    "mann_kendall",
    "sens_slope",
    "years_to_detect",
    "fdr_bh",
    "area_weighted_mean",
    "verdict",
    "analyze_series",
]

MAX_PAIRWISE_N = 3000  # Sen/MK are O(n^2); aggregate daily data to monthly above this.


# --------------------------------------------------------------------------- time helpers
def decimal_years(dates: Sequence) -> np.ndarray:
    """Convert datetime-like values to decimal years (e.g. 2000-07-01 -> ~2000.5)."""
    d = np.asarray(dates, dtype="datetime64[D]")
    years = d.astype("datetime64[Y]").astype(int) + 1970
    start = d.astype("datetime64[Y]").astype("datetime64[D]")
    nxt = (d.astype("datetime64[Y]") + np.timedelta64(1, "Y")).astype("datetime64[D]")
    frac = (d - start).astype(float) / (nxt - start).astype(float)
    return years + frac


def _months(dates: Sequence) -> np.ndarray:
    d = np.asarray(dates, dtype="datetime64[M]")
    return d.astype(int) % 12 + 1


# --------------------------------------------------------------------------- seasonality
def monthly_climatology(dates: Sequence, values: Sequence, baseline: tuple | None = None) -> np.ndarray:
    """Mean value for each calendar month (index 0 = January). NaN-aware.

    baseline: optional (start, end) datetime-like bounds for the climatology period.
    """
    v = np.asarray(values, dtype=float)
    m = _months(dates)
    sel = np.ones_like(v, dtype=bool)
    if baseline is not None:
        d = np.asarray(dates, dtype="datetime64[D]")
        sel = (d >= np.datetime64(baseline[0], "D")) & (d <= np.datetime64(baseline[1], "D"))
    clim = np.full(12, np.nan)
    for k in range(1, 13):
        vals = v[(m == k) & sel]
        if np.isfinite(vals).any():
            clim[k - 1] = np.nanmean(vals)
    return clim


def deseasonalize(dates: Sequence, values: Sequence, baseline: tuple | None = None):
    """Return (anomalies, climatology): values minus their calendar-month mean."""
    v = np.asarray(values, dtype=float)
    clim = monthly_climatology(dates, v, baseline)
    return v - clim[_months(dates) - 1], clim


# --------------------------------------------------------------------------- autocorrelation
def lag1_autocorr(x: Sequence) -> float:
    """Lag-1 autocorrelation coefficient of a series (NaNs dropped)."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 3:
        return float("nan")
    a = x - x.mean()
    den = np.sum(a * a)
    return float(np.sum(a[:-1] * a[1:]) / den) if den > 0 else float("nan")


def _acf(x: np.ndarray, nlags: int) -> np.ndarray:
    y = x - x.mean()
    n = len(x)
    acov = np.correlate(y, y, "full")[n - 1:] / n
    return acov[: nlags + 1] / acov[0]


def _clean(t, y):
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    ok = np.isfinite(t) & np.isfinite(y)
    t, y = t[ok], y[ok]
    order = np.argsort(t, kind="stable")
    return t[order], y[order]


# --------------------------------------------------------------------------- OLS
def ols_trend(t: Sequence, y: Sequence, alpha: float = 0.05, adjust_autocorr: bool = True) -> dict:
    """OLS slope with t-test. If adjust_autocorr, uses the lag-1 effective sample size
    n_eff = n (1 - r1) / (1 + r1) of the residuals (Santer et al., 2000).

    Slope units: units of y per unit of t (use decimal years -> per year).
    """
    t, y = _clean(t, y)
    n = t.size
    if n < 4:
        raise ValueError("Need at least 4 valid points for OLS trend.")
    b, a = np.polyfit(t, y, 1)
    resid = y - (a + b * t)
    r1 = lag1_autocorr(resid)
    n_eff = float(n)
    if adjust_autocorr and np.isfinite(r1) and r1 > 0:
        n_eff = max(3.0, n * (1 - r1) / (1 + r1))
    dof = n_eff - 2
    s_e = np.sqrt(np.sum(resid**2) / dof)
    s_b = s_e / np.sqrt(np.sum((t - t.mean()) ** 2))
    t_stat = b / s_b if s_b > 0 else np.inf
    p = 2 * stats.t.sf(abs(t_stat), dof)
    tc = stats.t.ppf(1 - alpha / 2, dof)
    return {
        "slope": float(b), "intercept": float(a), "se": float(s_b),
        "ci": [float(b - tc * s_b), float(b + tc * s_b)],
        "t": float(t_stat), "p": float(p), "n": int(n), "n_eff": float(n_eff),
        "r1": float(r1), "resid_std": float(np.std(resid, ddof=2)),
    }


# --------------------------------------------------------------------------- Mann-Kendall / Sen
def _mk_s(y: np.ndarray) -> float:
    s = 0.0
    for i in range(len(y) - 1):
        s += np.sign(y[i + 1:] - y[i]).sum()
    return s


def _mk_var(y: np.ndarray) -> float:
    n = len(y)
    _, counts = np.unique(y, return_counts=True)
    ties = counts[counts > 1]
    return (n * (n - 1) * (2 * n + 5) - np.sum(ties * (ties - 1) * (2 * ties + 5))) / 18.0


def _pairwise_slopes(t: np.ndarray, y: np.ndarray) -> np.ndarray:
    out = []
    for i in range(len(t) - 1):
        dt = t[i + 1:] - t[i]
        ok = dt != 0
        out.append((y[i + 1:][ok] - y[i]) / dt[ok])
    return np.concatenate(out) if out else np.array([])


def sens_slope(t: Sequence, y: Sequence, alpha: float = 0.05, var_s: float | None = None) -> dict:
    """Theil-Sen slope with a distribution-free CI (Sen 1968; Gilbert 1987).

    var_s: variance of the MK S statistic used for the CI. Default = no-autocorrelation
    variance (matches scipy.stats.theilslopes); pass the autocorrelation-corrected variance
    (mann_kendall(...)["var_s"]) to
    widen the CI for autocorrelated data.
    """
    t, y = _clean(t, y)
    n = t.size
    if n < 4:
        raise ValueError("Need at least 4 valid points for Sen's slope.")
    if n > MAX_PAIRWISE_N:
        raise ValueError(f"n={n} > {MAX_PAIRWISE_N}: aggregate to monthly before Sen/MK.")
    slopes = np.sort(_pairwise_slopes(t, y))
    med = float(np.median(slopes))
    intercept = float(np.median(y - med * t))
    if var_s is None:
        var_s = _mk_var(y)
    c = stats.norm.ppf(1 - alpha / 2) * np.sqrt(var_s)
    N = slopes.size
    m1 = (N - c) / 2.0          # 1-based rank of lower limit
    m2 = (N + c) / 2.0 + 1.0    # 1-based rank of upper limit
    ranks = np.arange(1, N + 1)
    lo = float(np.interp(m1, ranks, slopes))
    hi = float(np.interp(m2, ranks, slopes))
    return {"slope": med, "intercept": intercept, "ci": [lo, hi], "n_pairs": int(N)}


def mann_kendall(t: Sequence, y: Sequence, alpha: float = 0.05, method: str = "yue_wang") -> dict:
    """Mann-Kendall trend test.

    method="yue_wang" (default): variance inflated by the effective-sample-size factor
        eta = 1 + 2 * sum_{k=1}^{n-1} (1 - k/n) * r1^k, with r1 the lag-1 autocorrelation
        (clipped at >= 0) of the Sen-detrended series, i.e. an AR(1) noise model
        (Yue & Wang, 2004). Our Monte-Carlo check (validate_type1.py) gives ~5% false
        positives for AR(1) noise with phi = 0.3-0.6.
    method="hamed_rao": rank-ACF correction with significant lags only (Hamed & Rao, 1998).
        Found liberal in our simulations (10-21% false positives at phi = 0.3-0.6). Option only.
    method="original": classic MK (assumes independent data; strongly liberal if autocorrelated).
    """
    t, y = _clean(t, y)
    n = y.size
    if n < 4:
        raise ValueError("Need at least 4 valid points for Mann-Kendall.")
    if n > MAX_PAIRWISE_N:
        raise ValueError(f"n={n} > {MAX_PAIRWISE_N}: aggregate to monthly before Sen/MK.")
    s = _mk_s(y)
    var_s = _mk_var(y)
    correction = 1.0
    if method == "yue_wang":
        slope = sens_slope(t, y)["slope"]
        r1 = lag1_autocorr(y - slope * t)
        r1 = max(0.0, r1) if np.isfinite(r1) else 0.0
        k = np.arange(1, n)
        correction = 1 + 2 * np.sum((1 - k / n) * r1**k)
        var_s = var_s * correction
    elif method == "hamed_rao":
        slope = sens_slope(t, y)["slope"]
        detr = y - slope * t
        ranks = stats.rankdata(detr)
        rho = _acf(ranks, n - 1)
        bound = stats.norm.ppf(1 - alpha / 2) / np.sqrt(n)
        k = np.arange(1, n)
        sig = np.abs(rho[1:]) > bound
        terms = (n - k) * (n - k - 1) * (n - k - 2) * rho[1:]
        correction = 1 + 2.0 / (n * (n - 1) * (n - 2)) * np.sum(terms[sig])
        if correction <= 0:  # pathological; fall back to uncorrected variance
            correction = 1.0
        var_s = var_s * correction
    elif method != "original":
        raise ValueError("method must be 'yue_wang', 'hamed_rao' or 'original'")
    if s > 0:
        z = (s - 1) / np.sqrt(var_s)
    elif s < 0:
        z = (s + 1) / np.sqrt(var_s)
    else:
        z = 0.0
    p = 2 * stats.norm.sf(abs(z))
    tau = s / (0.5 * n * (n - 1))
    return {"method": method, "s": float(s), "var_s": float(var_s), "z": float(z),
            "p": float(p), "tau": float(tau), "n": int(n), "variance_correction": float(correction)}


# --------------------------------------------------------------------------- detectability
def years_to_detect(noise_std: float, noise_r1: float, trend_per_year: float,
                    obs_per_year: int = 12) -> float:
    """Years of data needed to detect a linear trend of this size with probability 0.90
    at the 5% level (Weatherhead et al., 1998, eq. 3, generalised to `obs_per_year`).

    n* = [ (3.3 * sigma_N * sqrt(12/f) / |w0|) * sqrt((1+phi)/(1-phi)) ]^(2/3)
    sigma_N: std of the noise (deseasonalised residuals), phi: their lag-1 autocorrelation,
    w0: trend per year, f: observations per year (12 for monthly; the original formula).
    """
    if not np.isfinite(trend_per_year) or trend_per_year == 0:
        return float("inf")
    phi = float(np.clip(noise_r1 if np.isfinite(noise_r1) else 0.0, -0.99, 0.99))
    factor = 3.3 * noise_std * np.sqrt(12.0 / obs_per_year) / abs(trend_per_year)
    return float((factor * np.sqrt((1 + phi) / (1 - phi))) ** (2.0 / 3.0))


# --------------------------------------------------------------------------- maps
def fdr_bh(pvals: Sequence, q: float = 0.05):
    """Benjamini-Hochberg FDR. Returns (significant_mask, adjusted_p) with input shape; NaNs stay NaN/False."""
    p = np.asarray(pvals, dtype=float)
    flat = p.ravel()
    ok = np.isfinite(flat)
    pv = flat[ok]
    m = pv.size
    adj_flat = np.full(flat.shape, np.nan)
    sig_flat = np.zeros(flat.shape, dtype=bool)
    if m:
        order = np.argsort(pv)
        ranked = pv[order] * m / np.arange(1, m + 1)
        ranked = np.minimum.accumulate(ranked[::-1])[::-1]
        adj = np.empty(m)
        adj[order] = np.minimum(ranked, 1.0)
        adj_flat[ok] = adj
        sig_flat[ok] = adj <= q
    return sig_flat.reshape(p.shape), adj_flat.reshape(p.shape)


def area_weighted_mean(field: np.ndarray, lats: Sequence) -> np.ndarray:
    """cos(latitude)-weighted spatial mean of field[..., lat, lon], NaN-aware."""
    f = np.asarray(field, dtype=float)
    w = np.cos(np.deg2rad(np.asarray(lats, dtype=float)))[:, None] * np.ones(f.shape[-1])
    w = np.broadcast_to(w, f.shape)
    valid = np.isfinite(f)
    num = np.where(valid, f * w, 0.0).sum(axis=(-2, -1))
    den = np.where(valid, w, 0.0).sum(axis=(-2, -1))
    with np.errstate(invalid="ignore", divide="ignore"):
        return num / den


# --------------------------------------------------------------------------- verdict
@dataclass
class Verdict:
    level: str          # strong | moderate | weak | none | insufficient
    direction: str      # increasing | decreasing | flat
    text: str


def verdict(p: float, slope_ci: Iterable[float], slope_per_decade: float, units: str,
            record_years: float, years_needed: float, variable_name: str = "This variable") -> Verdict:
    lo, hi = slope_ci
    direction = "increasing" if slope_per_decade > 0 else "decreasing" if slope_per_decade < 0 else "flat"
    mag = f"{abs(slope_per_decade):.3g} {units} per decade"
    if record_years < 10:
        return Verdict("insufficient", direction,
                       f"The record is only {record_years:.1f} years long - too short to judge a trend reliably.")
    excludes_zero = (lo > 0 and hi > 0) or (lo < 0 and hi < 0)
    if p < 0.01 and excludes_zero:
        level, lead = "strong", "Strong evidence"
    elif p < 0.05:
        level, lead = "moderate", "Evidence"
    elif p < 0.10:
        level, lead = "weak", "Weak, suggestive evidence"
    else:
        level = "none"
        more = max(0.0, years_needed - record_years)
        tail = (f" If the current rate continued, about {more:.0f} more years of data would likely be needed to detect it."
                if np.isfinite(more) else "")
        return Verdict(level, direction,
                       f"No statistically significant trend yet (p = {p:.2f}). {variable_name} shows a change of "
                       f"{mag}, but natural variability is too large to rule out chance.{tail}")
    return Verdict(level, direction,
                   f"{lead} that {variable_name.lower()} is {direction}: about {mag} "
                   f"(95% range {lo:.3g} to {hi:.3g}), p = {p:.2g}.")


# --------------------------------------------------------------------------- pipeline
def analyze_series(dates: Sequence, values: Sequence, units: str = "", variable_name: str = "This variable",
                   deseasonalize_monthly: bool = True, obs_per_year: int = 12, alpha: float = 0.05) -> dict:
    """Full trend analysis of one regional series. Returns a JSON-serialisable dict.

    Expected input: monthly (obs_per_year=12) or annual (1) values. Aggregate daily data first.
    """
    d = np.asarray(dates, dtype="datetime64[D]")
    v = np.asarray(values, dtype=float)
    series = v.copy()
    deseason = bool(deseasonalize_monthly and obs_per_year == 12)
    if deseason:
        series, _ = deseasonalize(d, v)
    t = decimal_years(d)
    ok = np.isfinite(series)
    t_ok, y_ok = t[ok], series[ok]
    if y_ok.size < 4:
        raise ValueError("Not enough valid data points.")
    record_years = float(t_ok.max() - t_ok.min() + 1.0 / obs_per_year)

    mk = mann_kendall(t_ok, y_ok, alpha=alpha, method="yue_wang")
    sen = sens_slope(t_ok, y_ok, alpha=alpha, var_s=mk["var_s"])
    ols = ols_trend(t_ok, y_ok, alpha=alpha, adjust_autocorr=True)
    resid = y_ok - (sen["intercept"] + sen["slope"] * t_ok)
    noise_std = float(np.std(resid, ddof=1))
    noise_r1 = lag1_autocorr(resid)
    n_star = years_to_detect(noise_std, noise_r1, sen["slope"], obs_per_year)

    per_dec = sen["slope"] * 10
    ci_dec = [c * 10 for c in sen["ci"]]
    total_change = sen["slope"] * (t_ok.max() - t_ok.min())
    mean_level = float(np.nanmean(v))
    # Only meaningful for ratio-scale variables (precipitation, NO2, NDVI), not for temperature in degC/K.
    pct = float(100 * total_change / abs(mean_level)) if np.isfinite(mean_level) and mean_level != 0 else None
    vd = verdict(mk["p"], ci_dec, per_dec, units, record_years, n_star, variable_name)

    return {
        "period": {"start": str(d[ok].min()), "end": str(d[ok].max())},
        "n": int(y_ok.size), "record_years": record_years, "obs_per_year": obs_per_year,
        "deseasonalized": deseason, "units": units,
        "sen_slope_per_decade": per_dec, "sen_ci95_per_decade": ci_dec,
        "mk": {k: mk[k] for k in ("method", "z", "p", "tau", "variance_correction")},
        "ols": {"slope_per_decade": ols["slope"] * 10, "ci95_per_decade": [c * 10 for c in ols["ci"]],
                "p": ols["p"], "n_eff": ols["n_eff"], "r1": ols["r1"]},
        "total_change": float(total_change),
        "percent_change_of_mean": pct,
        "noise": {"std": noise_std, "r1": float(noise_r1)},
        "years_to_detect": n_star,
        "verdict": asdict(vd),
    }
