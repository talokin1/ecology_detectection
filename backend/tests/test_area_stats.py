"""Offline tests for scripts/area_stats.py: box weights and the yearly rule (no data files needed)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "area_stats.py"


@pytest.fixture(scope="module")
def ast():
    spec = importlib.util.spec_from_file_location("area_stats", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["area_stats"] = mod
    try:
        spec.loader.exec_module(mod)
        yield mod
    finally:
        sys.modules.pop("area_stats", None)


def grid():
    return SimpleNamespace(lat=np.arange(-89.0, 90.0, 2.0), lon=np.arange(-179.0, 180.0, 2.0))


def test_whole_globe_box_is_the_cos_lat_mean(ast):
    g = grid()
    rng = np.random.default_rng(1)
    series = rng.normal(size=(12, g.lat.size, g.lon.size))
    out = ast.box_series(series, g, (-180.0, -90.0, 180.0, 90.0))
    w = np.cos(np.deg2rad(g.lat))[:, None] * np.ones((1, g.lon.size))
    want = (series * w[None]).sum(axis=(1, 2)) / w.sum()
    assert out["squares"] == g.lat.size * g.lon.size
    assert out["coverage"] == pytest.approx(1.0)
    np.testing.assert_allclose(out["values"], want, rtol=1e-12)
    np.testing.assert_allclose(ast.world_series(series, g), want, rtol=1e-12)


def test_a_square_counts_by_the_share_inside_the_box(ast):
    g = grid()
    series = np.zeros((10, g.lat.size, g.lon.size))
    i, j = int(np.argmin(np.abs(g.lat - 51))), int(np.argmin(np.abs(g.lon - 11)))
    series[:, i, j] = 4.0        # square 50..52 N, 10..12 E: fully inside
    series[:, i, j + 1] = 8.0    # square 50..52 N, 12..14 E: half inside (12..13 E)
    out = ast.box_series(series, g, (10.0, 50.0, 13.0, 52.0))
    assert out["squares"] == 2
    np.testing.assert_allclose(out["values"], (1.0 * 4.0 + 0.5 * 8.0) / 1.5)


def test_squares_without_a_complete_record_are_left_out(ast):
    g = grid()
    series = np.ones((10, g.lat.size, g.lon.size))
    i, j = int(np.argmin(np.abs(g.lat - 1))), int(np.argmin(np.abs(g.lon - 1)))
    series[3, i, j] = np.nan
    out = ast.box_series(series, g, (0.0, 0.0, 4.0, 2.0))  # two squares, one with a gap
    assert out["squares"] == 1
    assert out["coverage"] == pytest.approx(0.5)
    series[:, i, j + 1] = np.nan
    assert ast.box_series(series, g, (0.0, 0.0, 4.0, 2.0)) is None


def test_yearly_rule_levels(ast):
    years = np.arange(1981, 2026)
    rng = np.random.default_rng(7)
    noise = rng.normal(0, 0.2, years.size)
    up = ast.trend(years, 0.05 * (years - 1981) + noise)
    assert up["level"] == "strong" and up["per_decade"] == pytest.approx(0.5, abs=0.06)
    assert up["ci95"][0] < up["per_decade"] < up["ci95"][1]
    assert ast.trend(years, noise)["level"] in ("none", "weak")
    assert ast.trend(years, np.full(years.size, 3.0)) is None             # nothing varies
    assert ast.trend(years[:8], 0.3 * np.arange(8) + noise[:8])["level"] == "insufficient"  # under 10 years
