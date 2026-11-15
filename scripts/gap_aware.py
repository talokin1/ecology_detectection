"""Gap-aware helpers for monthly records with missing months (GRACE/GRACE-FO), used by
scripts/make_app_data.py. Method: docs/planning/2026-11-15-grace-gap-method.md (proposal D-G1..D-G6,
pending the stats lead's approval). Nothing here fills a gap: missing months stay missing.

- yearly_anomaly_means: one value per year from monthly anomalies, only for years with at least
  ``min_months`` valid months (D-G3: 9, which drops GRACE's 2017 and 2018).
- grid_yearly_anomalies: the same for every map square, with each square's own calendar-month normal.
- usable_gappy: the S3 rule for gappy satellite series (>= 80% valid months, every calendar month
  with >= 5 years for its normal).
- pettitt / gap_break: Pettitt (1979) level-shift test on Sen-detrended monthly anomalies; flags a
  significant shift whose break falls inside a known data gap (D-G6). The p-value is Pettitt's
  approximation, which ignores autocorrelation and is therefore liberal: it is used only to ADD a
  caveat, never to strengthen a verdict.

SI-assisted (Claude, Anthropic); pending team review (see docs/08-si-usage-log.md).
"""

from __future__ import annotations

import warnings

import numpy as np
from scipy.stats import rankdata

MIN_YEAR_MONTHS = 9
MIN_VALID_SHARE = 0.80
MIN_YEARS_PER_MONTH = 5


def _years_months(dates) -> tuple[np.ndarray, np.ndarray]:
    d = np.asarray(dates, dtype="datetime64[M]").astype(int)
    return d // 12 + 1970, d % 12 + 1


def yearly_anomaly_means(dates, anom, years, min_months: int = MIN_YEAR_MONTHS) -> np.ndarray:
    """Mean anomaly per year in ``years``; NaN where fewer than ``min_months`` months are valid."""
    y, _ = _years_months(dates)
    a = np.asarray(anom, dtype=float)
    out = np.full(len(years), np.nan)
    for k, yr in enumerate(years):
        v = a[(y == yr) & np.isfinite(a)]
        if v.size >= min_months:
            out[k] = float(v.mean())
    return out


def grid_yearly_anomalies(values, time, y0: int, y1: int, min_months: int = MIN_YEAR_MONTHS) -> np.ndarray:
    """(years, lat, lon) yearly mean anomalies of a (time, lat, lon) cube for y0..y1.

    Each square's normal is its own calendar-month mean over y0..y1 (NaN-aware); a year counts only
    where the square has at least ``min_months`` valid months that year.
    """
    v = np.asarray(values, dtype=float)
    y, m = _years_months(time)
    sel = (y >= y0) & (y <= y1)
    v, y, m = v[sel], y[sel], m[sel]
    anom = np.full_like(v, np.nan)
    with np.errstate(invalid="ignore"):
        for k in range(1, 13):
            idx = m == k
            if idx.any():
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN squares
                    clim = np.nanmean(v[idx], axis=0)
                anom[idx] = v[idx] - clim
    years = np.arange(y0, y1 + 1)
    out = np.full((years.size,) + v.shape[1:], np.nan)
    for k, yr in enumerate(years):
        block = anom[y == yr]
        n = np.isfinite(block).sum(axis=0)
        with np.errstate(invalid="ignore"):
            mean = np.nansum(block, axis=0) / np.where(n > 0, n, 1)
        out[k] = np.where(n >= min_months, mean, np.nan)
    return out


def usable_gappy(raw, dates, min_share: float = MIN_VALID_SHARE,
                 min_years_per_month: int = MIN_YEARS_PER_MONTH) -> str | None:
    """None if a gappy monthly series can carry a trend analysis, else the reason it cannot."""
    r = np.asarray(raw, dtype=float)
    ok = np.isfinite(r)
    if ok.mean() < min_share:
        return f"only {ok.mean():.0%} of months have data (needs {min_share:.0%})"
    _, m = _years_months(dates)
    for k in range(1, 13):
        if int(ok[m == k].sum()) < min_years_per_month:
            return f"calendar month {k} has fewer than {min_years_per_month} years for its normal"
    if np.nanstd(r) == 0:
        return "no variation"
    return None


def pettitt(values) -> tuple[float, int, float]:
    """Pettitt statistic K, index of the last value before the shift, approximate two-sided p."""
    x = np.asarray(values, dtype=float)
    n = x.size
    if n < 4:
        raise ValueError("need at least 4 values")
    ranks = rankdata(x)  # average ranks for ties
    u = 2 * np.cumsum(ranks) - np.arange(1, n + 1) * (n + 1)
    point = int(np.argmax(np.abs(u[:-1])))
    k = float(abs(u[point]))
    p = float(min(1.0, 2 * np.exp(-6 * k**2 / (n**3 + n**2))))
    return k, point, p


def gap_break(
    dates, anom, slope_per_year: float, gap: tuple[str, str], alpha: float = 0.05, tolerance_months: int = 3
) -> dict | None:
    """A significant Pettitt shift (on Sen-detrended anomalies) whose break lies inside ``gap``
    (first and last missing month, "YYYY-MM") or within ``tolerance_months`` of it (Pettitt places a
    step only approximately), else None."""
    d = np.asarray(dates, dtype="datetime64[M]")
    a = np.asarray(anom, dtype=float)
    ok = np.isfinite(a)
    d, a = d[ok], a[ok]
    t = d.astype(int) / 12.0
    resid = a - slope_per_year * t
    k, point, p = pettitt(resid)
    before, after = d[point], d[point + 1]
    g0 = np.datetime64(gap[0], "M") - np.timedelta64(tolerance_months, "M")
    g1 = np.datetime64(gap[1], "M") + np.timedelta64(tolerance_months, "M")
    in_gap = (before < g0 and after > g1) or (g0 <= before <= g1) or (g0 <= after <= g1)
    if p < alpha and in_gap:
        shift = float(resid[point + 1:].mean() - resid[: point + 1].mean())
        return {"before": str(before), "after": str(after), "p_approx": round(p, 4), "shift": shift}
    return None
