"""Tests for trend_stats.py. Run: python -m pytest -q .claude/skills/trend-stats/scripts

SI-assisted (Claude, Anthropic).
"""
import numpy as np
import pytest
from scipy import stats

import trend_stats as ts


def monthly_dates(start="1990-01", n=360):
    s = np.datetime64(start, "M")
    return np.arange(s, s + np.timedelta64(n, "M")).astype("datetime64[D]")


def ar1(n, phi, sigma, rng):
    e = rng.normal(0, sigma, n)
    x = np.empty(n)
    x[0] = e[0] / np.sqrt(1 - phi**2)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


def test_decimal_years():
    t = ts.decimal_years(np.array(["2000-01-01", "2001-01-01"], dtype="datetime64[D]"))
    assert t[0] == pytest.approx(2000.0) and t[1] == pytest.approx(2001.0)


def test_deseasonalize_removes_cycle():
    d = monthly_dates(n=240)
    m = ts._months(d)
    v = 10 + 5 * np.sin(2 * np.pi * m / 12)
    anom, clim = ts.deseasonalize(d, v)
    assert np.allclose(anom, 0, atol=1e-12)
    assert clim.shape == (12,)


def test_ols_matches_scipy_without_adjustment():
    rng = np.random.default_rng(0)
    t = np.arange(50, dtype=float)
    y = 0.2 * t + rng.normal(0, 1, 50)
    r = ts.ols_trend(t, y, adjust_autocorr=False)
    ref = stats.linregress(t, y)
    assert r["slope"] == pytest.approx(ref.slope)
    assert r["p"] == pytest.approx(ref.pvalue, rel=1e-6)
    assert r["se"] == pytest.approx(ref.stderr, rel=1e-6)


def test_sens_matches_scipy_theilslopes():
    rng = np.random.default_rng(1)
    t = np.arange(80, dtype=float)
    y = 0.05 * t + rng.normal(0, 1, 80)
    r = ts.sens_slope(t, y, alpha=0.05)
    ref = stats.theilslopes(y, t, alpha=0.95)
    assert r["slope"] == pytest.approx(ref.slope)
    assert r["ci"][0] == pytest.approx(ref.low_slope, rel=0.02)
    assert r["ci"][1] == pytest.approx(ref.high_slope, rel=0.02)


def test_mk_tau_matches_kendall_without_ties():
    rng = np.random.default_rng(2)
    y = rng.normal(0, 1, 60) + np.linspace(0, 1, 60)
    t = np.arange(60, dtype=float)
    r = ts.mann_kendall(t, y, method="original")
    assert r["tau"] == pytest.approx(stats.kendalltau(t, y).statistic)


def test_mk_detects_clear_trend():
    rng = np.random.default_rng(3)
    t = np.arange(120, dtype=float) / 12
    y = 0.5 * t + rng.normal(0, 0.5, 120)
    for method in ("original", "yue_wang", "hamed_rao"):
        assert ts.mann_kendall(t, y, method=method)["p"] < 1e-4


@pytest.mark.parametrize("phi", [0.3, 0.6])
def test_default_mk_controls_false_positives_under_ar1(phi):
    """Classic MK over-rejects with autocorrelated noise; the default (Yue-Wang) should stay near 5%."""
    rng = np.random.default_rng(4)
    n, runs = 240, 300
    t = np.arange(n, dtype=float) / 12
    fp_orig = fp_yw = 0
    for _ in range(runs):
        y = ar1(n, phi, 1.0, rng)
        fp_orig += ts.mann_kendall(t, y, method="original")["p"] < 0.05
        fp_yw += ts.mann_kendall(t, y)["p"] < 0.05
    assert fp_orig / runs > 0.10
    assert fp_yw / runs < 0.09


def test_ols_effective_n_controls_false_positives_under_ar1():
    rng = np.random.default_rng(5)
    n, runs = 200, 300
    t = np.arange(n, dtype=float) / 12
    fp = sum(ts.ols_trend(t, ar1(n, 0.6, 1.0, rng))["p"] < 0.05 for _ in range(runs))
    assert fp / runs < 0.10


def test_sen_ci_covers_truth():
    rng = np.random.default_rng(6)
    t = np.arange(240, dtype=float) / 12
    covered = 0
    for _ in range(200):
        y = 0.1 * t + rng.normal(0, 1, 240)
        lo, hi = ts.sens_slope(t, y)["ci"]
        covered += lo <= 0.1 <= hi
    assert 0.90 <= covered / 200 <= 0.99


def test_years_to_detect_reference_value():
    # sigma=1, phi=0, w=0.1/yr, monthly -> (33)^(2/3) ~ 10.29 years
    assert ts.years_to_detect(1.0, 0.0, 0.1) == pytest.approx(33 ** (2 / 3))
    assert ts.years_to_detect(1.0, 0.5, 0.1) > ts.years_to_detect(1.0, 0.0, 0.1)
    assert ts.years_to_detect(1.0, 0.0, 0.0) == float("inf")


def test_years_to_detect_is_roughly_calibrated():
    """At n* years, detection probability (OLS, 5%) should be near 0.9 for white monthly noise."""
    rng = np.random.default_rng(7)
    w, sigma = 0.1, 1.0
    n_years = ts.years_to_detect(sigma, 0.0, w)
    n = int(round(n_years * 12))
    t = np.arange(n) / 12
    hits = sum(ts.ols_trend(t, w * t + rng.normal(0, sigma, n), adjust_autocorr=False)["p"] < 0.05
               for _ in range(300))
    assert 0.8 <= hits / 300 <= 0.97


def test_fdr_matches_scipy():
    p = np.array([0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, np.nan])
    sig, adj = ts.fdr_bh(p, q=0.05)
    ref = stats.false_discovery_control(p[:-1], method="bh")
    assert np.allclose(adj[:-1], ref)
    assert np.isnan(adj[-1]) and not sig[-1]


def test_area_weighted_mean():
    lats = np.array([0.0, 60.0])
    field = np.array([[1.0, 1.0], [3.0, 3.0]])  # lat x lon
    # weights cos0=1, cos60=0.5 -> (1*1 + 3*0.5)/1.5 = 1.6667
    assert ts.area_weighted_mean(field, lats) == pytest.approx(5 / 3)
    field[1, 0] = np.nan
    assert np.isfinite(ts.area_weighted_mean(field, lats))


def test_analyze_series_end_to_end():
    rng = np.random.default_rng(8)
    d = monthly_dates("1981-01", 45 * 12)
    m = ts._months(d)
    t = ts.decimal_years(d) - 1981
    v = 10 + 8 * np.sin(2 * np.pi * (m - 4) / 12) + 0.03 * t + ar1(d.size, 0.5, 0.6, rng)
    v[5] = np.nan
    out = ts.analyze_series(d, v, units="K", variable_name="Air temperature")
    assert out["deseasonalized"] is True
    assert out["sen_slope_per_decade"] == pytest.approx(0.3, abs=0.1)
    assert out["verdict"]["level"] in ("strong", "moderate")
    assert out["verdict"]["direction"] == "increasing"
    assert out["n"] == d.size - 1


def test_verdict_insufficient_and_none():
    v = ts.verdict(0.5, [-1, 1], 0.1, "mm", 8, 30)
    assert v.level == "insufficient"
    v = ts.verdict(0.5, [-1, 1], 0.1, "mm", 20, 30)
    assert v.level == "none" and "10 more years" in v.text
