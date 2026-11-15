"""Offline tests of scripts/gap_aware.py (synthetic gappy series)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gap_aware as ga  # noqa: E402

DATES = pd.date_range("2003-01-01", "2025-12-01", freq="MS").values.astype("datetime64[M]")


def gappy(seed=0, trend=0.0, step=0.0):
    rng = np.random.default_rng(seed)
    t = np.arange(DATES.size) / 12.0
    season = 5 * np.sin(2 * np.pi * np.arange(DATES.size) / 12)
    v = trend * t + season + rng.normal(0, 0.5, DATES.size)
    v[DATES >= np.datetime64("2018-06")] += step
    gap = (DATES >= np.datetime64("2017-07")) & (DATES <= np.datetime64("2018-05"))
    v[gap] = np.nan
    v[::17] = np.nan  # scattered missing months, like 2011-2016
    return v


def test_yearly_means_need_nine_months():
    anom = np.zeros(DATES.size)
    anom[(DATES >= np.datetime64("2017-04")) & (DATES <= np.datetime64("2018-12"))] = np.nan
    years = np.arange(2003, 2026)
    out = ga.yearly_anomaly_means(DATES, anom, years)
    assert np.isnan(out[years == 2017]).all() and np.isnan(out[years == 2018]).all()
    assert np.isfinite(out[years == 2016]).all()


def test_grid_yearly_anomalies_removes_season_and_respects_gaps():
    cube = np.stack([gappy(1), gappy(2, trend=0.1)], axis=1)[:, :, None]  # (time, 2 squares, 1)
    out = ga.grid_yearly_anomalies(cube, DATES, 2003, 2025)
    assert out.shape == (23, 2, 1)
    years = np.arange(2003, 2026)
    assert np.isnan(out[years == 2017]).all() and np.isnan(out[years == 2018]).all()
    assert abs(np.nanmean(out[:, 0, 0])) < 0.3  # seasonal cycle gone, no trend
    slope = np.polyfit(years[np.isfinite(out[:, 1, 0])], out[np.isfinite(out[:, 1, 0]), 1, 0], 1)[0]
    assert slope == pytest.approx(0.1, abs=0.03)


def test_usable_gappy():
    assert ga.usable_gappy(gappy(), DATES) is None
    sparse = gappy()
    sparse[::3] = np.nan
    assert "of months have data" in ga.usable_gappy(sparse, DATES)


def test_pettitt_finds_a_step_and_not_noise():
    rng = np.random.default_rng(3)
    x = np.r_[rng.normal(0, 1, 60), rng.normal(2, 1, 60)]
    _, point, p = ga.pettitt(x)
    assert 55 <= point <= 64 and p < 0.001
    assert ga.pettitt(rng.normal(0, 1, 120))[2] > 0.05


def test_gap_break_flags_a_step_across_the_mission_gap_only():
    gap = ("2017-07", "2018-05")

    def anomalies(v):
        return v - np.tile(np.nanmean(v.reshape(-1, 12), axis=0), 23)

    hit = ga.gap_break(DATES, anomalies(gappy(4, step=3.0)), 0.0, gap)
    assert hit is not None and hit["shift"] > 2 and hit["before"] <= "2017-06"
    assert ga.gap_break(DATES, anomalies(gappy(5)), 0.0, gap) is None
