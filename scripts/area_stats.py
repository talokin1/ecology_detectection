"""Trend of any longitude/latitude box, from the frozen 2-degree grids: the Python reference for
the web app's "your own area" tool (frontend/src/lib/area.ts and stats.ts compute the same in
the browser). Reads the frozen cache only.

Rules (the same as for countries, ADR-008): a square counts by the share of it inside the box
times cos(latitude); squares without a complete record are left out. One value per year (all
twelve months, or one season), then `make_app_data.yearly_values_trend`: Sen's slope,
Mann-Kendall with the Yue-Wang correction, regression with the lag-1 effective sample size, and
the weaker of the two verdict levels.

Usage (repo root):
  python scripts/area_stats.py --var t2m --box -46 46 -20 62
  python scripts/area_stats.py --var t2m --box -110 44 -90 60 --season mam --second -10 36 40 70
  python scripts/area_stats.py --fixture frontend/src/lib/stats.fixture.json
  python scripts/area_stats.py --var precip --world        # world, land-only and sea-only mean trends
  python scripts/area_stats.py --false-alarms               # how often the yearly rule cries wolf

--box and --second take WEST SOUTH EAST NORTH in degrees. --fixture writes the reference values
that the browser code is tested against (`npm test`, stats.test.ts).

SI-assisted (Claude, Anthropic).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_app_data as m  # noqa: E402


def yearly_grid(var: str, season: str = "year") -> tuple[np.ndarray, np.ndarray, m.Grid]:
    """(years, (n, lat, lon) one mean per year, grid) for a variable and 'year' or a map season."""
    spec = m.VARIABLES[var]
    grid = m.Grid(var)
    m.Y0 = spec["start"]
    m.Y1 = m.last_complete_year(grid.time[np.isfinite(grid.values).any(axis=(1, 2))])
    months = None if season == "year" else next(ms for code, _, ms in m.MAP_SEASONS if code == season)
    years, series = grid.period_means(months)
    return years, series, grid


def box_series(series: np.ndarray, grid: m.Grid, box) -> dict | None:
    """Weighted yearly mean of the squares a box overlaps; None if none of them has data."""
    w0, s0, e0, n0 = box
    dlat, dlon = float(grid.lat[1] - grid.lat[0]), float(grid.lon[1] - grid.lon[0])
    dy = np.clip(np.minimum(n0, grid.lat + dlat / 2) - np.maximum(s0, grid.lat - dlat / 2), 0, None)
    dx = np.clip(np.minimum(e0, grid.lon + dlon / 2) - np.maximum(w0, grid.lon - dlon / 2), 0, None)
    w = (dy[:, None] * dx[None, :]) / (dlat * dlon) * np.cos(np.deg2rad(grid.lat))[:, None]
    ok = np.isfinite(series).all(axis=0) & (w > 0)
    if not ok.any():
        return None
    values = (np.where(ok[None], series, 0.0) * (w * ok)[None]).sum(axis=(1, 2)) / (w * ok).sum()
    return {"values": values, "squares": int(ok.sum()), "coverage": float((w * ok).sum() / w.sum())}


def world_series(series: np.ndarray, grid: m.Grid) -> np.ndarray:
    return box_series(series, grid, (-180.0, -90.0, 180.0, 90.0))["values"]


def trend(years, values) -> dict | None:
    values = np.asarray(values, dtype=float)
    if years.size < 4 or np.all(values == values[0]):
        return None
    out = m.yearly_values_trend(years, values)
    if years.size < 10:
        out["level"] = "insufficient"
    return out


def describe(label: str, t: dict | None, units: str) -> str:
    if t is None:
        return f"{label}: no variation, nothing to test"
    lo, hi = t["ci95"]
    return (f"{label}: Sen {t['per_decade']:+.4f} {units}  95% range [{lo:+.4f}, {hi:+.4f}]  "
            f"MK p {t['p_mk']:.4g}  regression p {t['p_ols']:.4g}  n {t['n']}  verdict: {t['level']}")


def report(var: str, box, season: str, second=None) -> None:
    years, series, grid = yearly_grid(var, season)
    units = m.VARIABLES[var]["rate_units"]
    a = box_series(series, grid, box)
    if a is None:
        print("no square with a complete record inside this box")
        return
    world = world_series(series, grid)
    print(f"{var} · {season} · {int(years[0])}–{int(years[-1])} · box {box} · {a['squares']} squares · "
          f"{a['coverage']:.0%} of the box has data")
    print(describe("area          ", trend(years, a["values"]), units))
    print(describe("world average ", trend(years, world), units))
    print(describe("area − world  ", trend(years, a["values"] - world), units))
    if second:
        b = box_series(series, grid, second)
        if b is None:
            print("second box: no square with a complete record")
            return
        print(describe("second area   ", trend(years, b["values"]), units))
        print(describe("area − second ", trend(years, a["values"] - b["values"]), units))


def world_split(var: str, season: str) -> None:
    """Trend of the world mean and of its land and sea parts: is the world average a sound yardstick?"""
    years, series, grid = yearly_grid(var, season)
    units = m.VARIABLES[var]["rate_units"]
    land = np.isfinite(m.Grid("soil").values).any(axis=0)  # squares where the land-only soil field exists
    ok = np.isfinite(series).all(axis=0)
    w = np.cos(np.deg2rad(grid.lat))[:, None] * np.ones(series.shape[1:])
    print(f"{var} · {season} · {int(years[0])}–{int(years[-1])}")
    for label, mask in (("all squares ", ok), ("land squares", ok & land), ("sea squares ", ok & ~land)):
        if not mask.any():
            continue
        vals = (np.where(mask[None], series, 0.0) * (w * mask)[None]).sum(axis=(1, 2)) / (w * mask).sum()
        t = trend(years, vals)
        pct = 100 * t["per_decade"] / float(np.mean(vals)) if np.mean(vals) else float("nan")
        print(describe(label, t, units) + f"  ({pct:+.2f}% of its mean per decade)")


def false_alarms(runs: int = 1500) -> None:
    """Share of trend-free AR(1) series that the yearly rule calls 'evidence' or 'strong' (should be 5%)."""
    rng = np.random.default_rng(20261115)
    print(f"yearly rule, {runs} trend-free series per cell: share called evidence or strong")
    print("phi    n=45   n=25   n=10")
    for phi in (0.0, 0.3, 0.6, 0.8):
        row = []
        for n in (45, 25, 10):
            years = np.arange(2026 - n, 2026)
            hits = 0
            for _ in range(runs):
                e = rng.normal(0, 1, n + 50)
                x = np.empty(n + 50)
                x[0] = e[0]
                for k in range(1, n + 50):
                    x[k] = phi * x[k - 1] + e[k]
                hits += m.LEVEL_RANK[m.yearly_values_trend(years, x[50:])["level"]] >= 2
            row.append(f"{100 * hits / runs:5.1f}%")
        print(f"{phi:<5} " + " ".join(row))


# --------------------------------------------------------------------------- fixture for the browser port
AREA_CASES = [
    ("t2m", "year", [-46, 46, -20, 62]),          # ocean, whole year
    ("t2m", "mam", [-115, 44, -90, 60]),          # land, one season
    ("t2m", "djf", [-10.5, 36.2, 40.3, 69.9]),    # edges that cut through squares; winter starts a year later
    ("precip", "jja", [60, 5, 100, 35]),
    ("soil", "year", [-12, 34, 4, 46]),           # land-only field over a coast: part of the box has no data
    ("haze", "year", [100, 20, 125, 42]),         # shorter record
    ("sea_ice", "son", [-180, 66, 180, 90]),      # sea-only field
]


def synthetic_cases() -> list[dict]:
    rng = np.random.default_rng(20261115)
    out = []
    for n, phi, slope, digits in [(45, 0.0, 0.0, None), (45, 0.0, 0.03, None), (45, 0.5, 0.02, None),
                                  (45, 0.6, 0.0, None), (44, 0.3, -0.04, None), (25, 0.2, 0.05, None),
                                  (28, 0.5, -0.01, None), (45, 0.0, 0.02, 1), (45, 0.4, 0.0, 0),
                                  (12, 0.0, 0.1, None), (10, 0.3, -0.2, 1), (8, 0.0, 0.3, None),
                                  (45, 0.8, 0.01, None), (45, 0.0, 0.004, None),
                                  (10, 0.9, 0.0, None), (45, 0.97, 0.0, None), (4, 0.0, 0.5, None),
                                  (9, 0.0, 0.2, None), (30, 0.0, 0.0, 0)]:
        e = rng.normal(0, 1, n)
        x = np.empty(n)
        x[0] = e[0]
        for k in range(1, n):
            x[k] = phi * x[k - 1] + e[k]
        years = np.arange(2026 - n, 2026)
        vals = 12.0 + x + slope * (years - years[0])
        if digits is not None:  # rounded values make ties
            vals = np.round(vals, digits)
        out.append({"name": f"n={n} phi={phi} slope={slope} digits={digits}", "years": years.tolist(),
                    "values": vals.tolist(), "expected": trend(years, vals)})
    years = np.arange(1981, 2026)
    snow = np.round(np.maximum(0.0, rng.normal(0.3, 1.0, 45) - 0.02 * (years - 1981)), 2)  # mostly zeros
    out.append({"name": "zero-inflated", "years": years.tolist(), "values": snow.tolist(),
                "expected": trend(years, snow)})
    out.append({"name": "constant", "years": years.tolist(), "values": [7.5] * 45, "expected": None})
    return out


def write_fixture(path: Path) -> None:
    areas = []
    for var, season, box in AREA_CASES:
        years, series, grid = yearly_grid(var, season)
        a = box_series(series, grid, box)
        world = world_series(series, grid)
        areas.append({"variable": var, "season": season, "box": box, "years": years.tolist(),
                      "expected": {"values": a["values"].tolist(), "squares": a["squares"],
                                   "coverage": a["coverage"],
                                   "trend": trend(years, a["values"]), "world": trend(years, world),
                                   "gap": trend(years, a["values"] - world)}})
    doc = {"generated_by": "python scripts/area_stats.py --fixture frontend/src/lib/stats.fixture.json",
           "note": ("Reference values from trend_stats.py (through make_app_data.yearly_values_trend) "
                    "and the cached NetCDF grids. The browser code must reproduce them; never edit by hand."),
           "series": synthetic_cases(), "areas": areas}
    path.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {path}: {len(doc['series'])} series, {len(areas)} areas")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--var", choices=sorted(m.VARIABLES), help="app variable id")
    ap.add_argument("--box", type=float, nargs=4, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    ap.add_argument("--second", type=float, nargs=4, metavar=("WEST", "SOUTH", "EAST", "NORTH"),
                    help="a second box to compare with")
    ap.add_argument("--season", default="year", choices=["year"] + [c for c, _, _ in m.MAP_SEASONS])
    ap.add_argument("--fixture", type=Path, help="write the reference file for the browser tests")
    ap.add_argument("--world", action="store_true",
                    help="trend of the world mean and of its land and sea parts")
    ap.add_argument("--false-alarms", action="store_true",
                    help="Monte-Carlo false-alarm rate of the yearly rule")
    args = ap.parse_args()
    if args.fixture:
        write_fixture(args.fixture)
    elif args.false_alarms:
        false_alarms()
    elif args.var and args.world:
        world_split(args.var, args.season)
    elif args.var and args.box:
        report(args.var, args.box, args.season, args.second)
    else:
        ap.error("give --var with --box or --world, or --fixture, or --false-alarms")
