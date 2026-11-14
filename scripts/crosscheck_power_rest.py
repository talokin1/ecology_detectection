r"""Cross-check our cached POWER series against the official NASA POWER REST API (data plan T13+, R-03).

Two independent checks per catalog variable, over one prepared region (default ``south_ukraine``,
which fits the REST regional limit of 10 degrees):

1. Cell values: every grid cell the REST regional endpoint returns is compared with the same cell
   of the POWER Zarr store we read (``power_zarr.open_source``). Shows that the archive we use holds
   the values NASA publishes.
2. Area mean: the cos(latitude)-weighted mean is recomputed from the REST cells with plain numpy
   (land mask: REST GWETROOT cells that are not the fill value; nearest such cell for coarser grids)
   and compared with the cached series the app uses (``acquire.get_series``). Tests our whole
   reader: box selection, land mask, weights, fill handling, units.

Pass criteria, fixed before the first run (2026-11-14): area-mean correlation >= 0.999 and mean
absolute difference <= 2% of the series' standard deviation. Known small differences: the REST
monthly values use local solar time (LST), the Zarr store UTC; REST rounds to 2 decimals.

Writes ``docs/planning/2026-11-14-power-rest-crosscheck.md`` and ``data/catalog/crosscheck_power_rest.json``.
Raw REST responses are kept in ``data/cache/raw/power_rest/`` (git-ignored). No login needed.

Usage (PowerShell or bash):
    python scripts/crosscheck_power_rest.py
    python scripts/crosscheck_power_rest.py --region south_ukraine --start 2001 --end 2024

SI-assisted (Claude, Anthropic); pending team review (see docs/08-si-usage-log.md).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from trend_detective import acquire, power_zarr  # noqa: E402

REST_URL = "https://power.larc.nasa.gov/api/temporal/monthly/regional"
RAW = ROOT / "data" / "cache" / "raw" / "power_rest"
DOC = ROOT / "docs" / "planning" / "2026-11-14-power-rest-crosscheck.md"
RESULTS = ROOT / "data" / "catalog" / "crosscheck_power_rest.json"
MIN_R = 0.999
MAX_MAD_OF_SD = 0.02
# REST units that differ from the Zarr store's, as factor: zarr = rest * factor
REST_TO_ZARR = {"kW-hr/m^2/day": 1000 / 24, "MJ/m^2/day": 1 / 0.0864}  # 1 W/m^2 = 0.0864 MJ/m^2/day


def fetch_rest(parameter: str, region: power_zarr.Region, start: int, end: int) -> dict:
    """REST regional response for one parameter (cached on disk; one parameter per request)."""
    RAW.mkdir(parents=True, exist_ok=True)
    bbox = "_".join(f"{v:g}" for v in (region.lon_min, region.lat_min, region.lon_max, region.lat_max))
    path = RAW / f"{parameter}_{bbox}_{start}_{end}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    params = {
        "parameters": parameter,
        "community": "AG",
        "latitude-min": region.lat_min,
        "latitude-max": region.lat_max,
        "longitude-min": region.lon_min,
        "longitude-max": region.lon_max,
        "start": start,
        "end": end,
        "format": "JSON",
    }
    for attempt in range(4):
        r = requests.get(REST_URL, params=params, timeout=300)
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        data = r.json()
        if not data.get("features"):
            raise RuntimeError(f"REST returned no cells for {parameter}: {data.get('messages') or data}")
        path.write_text(json.dumps(data), encoding="utf-8")
        return data
    r.raise_for_status()
    raise RuntimeError("unreachable")


def rest_cube(data: dict, parameter: str) -> tuple[pd.DataFrame, float, str]:
    """(DataFrame index month, columns (lat, lon)), fill value, units from a REST response."""
    fill = float(data["header"]["fill_value"])
    units = data["parameters"][parameter]["units"]
    cols = {}
    for f in data["features"]:
        lon, lat = f["geometry"]["coordinates"][:2]
        vals = {k: v for k, v in f["properties"]["parameter"][parameter].items() if not k.endswith("13")}
        cols[(round(lat, 4), round(lon, 4))] = pd.Series(vals, dtype=float)
    df = pd.DataFrame(cols)
    df.index = pd.to_datetime(df.index, format="%Y%m")
    return df.where(df != fill), fill, units


def area_mean(df: pd.DataFrame, land: pd.Series | None) -> pd.Series:
    lats = np.array([c[0] for c in df.columns])
    w = np.cos(np.deg2rad(lats)) * (
        land.reindex(df.columns).fillna(False).to_numpy() if land is not None else 1
    )
    vals = df.to_numpy()
    ok = np.isfinite(vals) & (w > 0)
    num = np.where(ok, vals, 0) @ w
    den = ok.astype(float) @ w
    return pd.Series(np.where(den > 0, num / np.where(den > 0, den, 1), np.nan), index=df.index).dropna()


def nearest_land(cells, land_cells: pd.Series) -> pd.Series:
    """Land flag of each cell = flag of the nearest REST MERRA-2 cell (coarser grids)."""
    pts = np.array(list(land_cells.index))
    out = {}
    for lat, lon in cells:
        i = int(np.argmin((pts[:, 0] - lat) ** 2 + (pts[:, 1] - lon) ** 2))
        out[(lat, lon)] = bool(land_cells.iloc[i])
    return pd.Series(out)


def check_variable(var: acquire.Variable, region_id: str, start: int, end: int, land: pd.Series) -> dict:
    reg = acquire.resolve_region(region_id)
    parameter, store = var.access["variable"], var.access.get("store", "merra2")
    base = {"variable_id": var.id, "parameter": parameter, "store": store}
    if var.entry.get("surface") == "ocean" and acquire.list_regions()[region_id].get("land_only"):
        return base | {
            "status": "n/a",
            "reason": "ocean variable; the region is land-only (refused by design)",
        }
    df, _, units = rest_cube(fetch_rest(parameter, reg, start, end), parameter)
    if df.notna().sum().sum() == 0:
        return base | {
            "status": "n/a",
            "reason": "the REST API returns only fill values for this parameter (monthly regional requests)",
        }
    factor = REST_TO_ZARR.get(units, 1.0)
    df = df * factor

    # 1. cells: REST vs Zarr at identical coordinates
    ds = power_zarr.open_source(store)
    box = power_zarr._select_box(ds[parameter], reg).sel(time=slice(f"{start}-01", f"{end}-12-31")).load()
    box = box.where(box != power_zarr.FILL_VALUE)
    z = box.to_dataframe(name="v")["v"].unstack(["lat", "lon"])
    z.index = pd.DatetimeIndex(z.index).to_period("M").to_timestamp()
    z.columns = [(round(a, 4), round(b, 4)) for a, b in z.columns]
    common = [c for c in df.columns if c in set(z.columns)]
    a, b = df[common].align(z[common], join="inner", axis=0)
    diff = (a - b).to_numpy()
    finite = np.isfinite(diff)
    cell = {
        "n_cells_rest": int(df.shape[1]),
        "n_cells_matched": len(common),
        "n_values": int(finite.sum()),
        "max_abs_diff": float(np.nanmax(np.abs(diff))) if finite.any() else None,
        "mean_abs_diff": float(np.nanmean(np.abs(diff))) if finite.any() else None,
        "share_within_rounding": float((np.abs(diff[finite]) <= 0.005 * max(1, factor) + 1e-9).mean())
        if finite.any()
        else None,
    }

    # 2. area mean: independent recomputation vs the cached series the app uses
    lo = bool(acquire.list_regions()[region_id].get("land_only"))
    mask = None
    if lo:
        mask = land if set(df.columns) <= set(land.index) else nearest_land(df.columns, land)
    rest_mean = area_mean(df, mask)
    cached = acquire.get_series(var.id, region_id)
    cached = cached[(cached.index.year >= start) & (cached.index.year <= end)]
    j = pd.concat([rest_mean.rename("rest"), cached.rename("ours")], axis=1, join="inner").dropna()
    sd = float(j["ours"].std())
    mad = float((j["rest"] - j["ours"]).abs().mean())
    r = float(j.corr().iloc[0, 1]) if sd > 0 else float("nan")
    passed = bool(sd > 0 and r >= MIN_R and mad <= MAX_MAD_OF_SD * sd)
    return base | {
        "status": "pass" if passed else "fail",
        "rest_units": units,
        "rest_to_zarr_factor": factor,
        "cells": cell,
        "area_mean": {
            "land_only": lo,
            "n_months": len(j),
            "r": r,
            "mean_abs_diff": mad,
            "max_abs_diff": float((j["rest"] - j["ours"]).abs().max()),
            "sd": sd,
            "mad_over_sd": mad / sd if sd > 0 else None,
        },
        "passed": passed,
    }


def _fmt(v, p: int = 3) -> str:
    return "-" if v is None else f"{v:.{p}g}"


def _row(res: dict) -> str:
    vid, par = res["variable_id"], res["parameter"]
    if res["status"] in ("n/a", "error"):
        why = res.get("reason") or res.get("error")
        return f"| {vid} | {par} | - | - | - | - | - | - | {res['status']}: {why} |"
    c, m = res["cells"], res["area_mean"]
    share = c["share_within_rounding"]
    cells = [
        f"{par} ({res['store']})",
        f"{c['n_cells_matched']}/{c['n_cells_rest']}",
        _fmt(c["max_abs_diff"]),
        f"{_fmt(100 * share if share is not None else None)}%",
        f"{m['r']:.5f}",
        _fmt(m["mad_over_sd"]),
        str(m["n_months"]),
        "pass" if res["passed"] else "**FAIL**",
    ]
    return f"| {vid} | " + " | ".join(cells) + " |"


def render(results: list[dict], region_id: str, start: int, end: int, accessed: str) -> str:
    lines = [
        "# Cross-check: cached POWER series vs the official POWER REST API",
        "",
        f"Generated by `scripts/crosscheck_power_rest.py` on {accessed}. Region `{region_id}`, "
        f"{start}-{end}. Do not edit by hand; rerun the script.",
        "",
        "**What it shows.** (1) *Cells*: the POWER Zarr archive we read holds the same values as the "
        "REST API NASA publishes, cell by cell. (2) *Area mean*: a mean recomputed independently from "
        "the REST cells (plain numpy, cos-latitude weights, land mask from REST GWETROOT fill values) "
        "matches the cached series the app uses, so box selection, land mask, weights, fill handling "
        "and units are right.",
        "",
        f"**Pass rule (fixed before the first run):** area-mean r >= {MIN_R} and mean absolute "
        f"difference <= {MAX_MAD_OF_SD:.0%} of the series' SD.",
        "",
        "**Cell differences are expected and small.** REST months are in local solar time, the Zarr "
        "store in UTC, so a few hours at each month boundary fall in a different month; REST also "
        'rounds to 2 decimals. "Within rounding" is the share of cell values that agree to 0.005; '
        "the remaining differences (max abs diff column) are consistent with the time-standard effect, "
        "which was not tested separately; they average out in the area mean.",
        "",
        "| Variable | Parameter | Cells matched | Cell max abs diff | Cells within rounding "
        "| Area-mean r | Mean abs diff / SD | Months | Result |",
        "|---|---|---|---|---|---|---|---|---|",
        *(_row(r) for r in results),
    ]
    n = {s: sum(1 for r in results if r["status"] == s) for s in ("pass", "fail", "n/a", "error")}
    checked = n["pass"] + n["fail"]
    lines += [
        "",
        f"{n['pass']} of {checked} checked variables pass; {n['n/a']} not checkable, {n['error']} errors.",
        "Units: REST serves solar radiation in MJ/m^2/day; converted with 1 W/m^2 = 0.0864 MJ/m^2/day "
        "(the catalog's `convert`), so a pass also confirms that factor.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--region", default="south_ukraine", help="preset id; box must be <= 10 degrees")
    p.add_argument("--start", type=int, default=2001)
    p.add_argument("--end", type=int, default=2024)
    args = p.parse_args(argv)
    reg = acquire.resolve_region(args.region)
    if reg.polygons or reg.lat_max - reg.lat_min > 10 or (reg.lon_max - reg.lon_min) % 360 > 10:
        p.error("the REST regional endpoint needs a plain box of at most 10 x 10 degrees")
    land_df, _, _ = rest_cube(fetch_rest("GWETROOT", reg, args.start, args.end), "GWETROOT")
    land = land_df.notna().any()
    results = []
    for var in acquire.list_variables(available_only=True).values():
        if var.reader != "power_zarr":
            continue
        try:
            res = check_variable(var, args.region, args.start, args.end, land)
        except Exception as exc:  # noqa: BLE001 - report and continue (e.g. parameter not served by REST)
            res = {
                "variable_id": var.id,
                "parameter": var.access["variable"],
                "passed": False,
                "status": "error",
                "error": f"{type(exc).__name__}: {str(exc)[:120]}",
            }
        print(
            f"{res['variable_id']:30} {res['status']}"
            + (
                f"  r={res['area_mean']['r']:.5f}"
                if "area_mean" in res
                else f"  {res.get('reason') or res.get('error')}"
            )
        )
        results.append(res)
    accessed = datetime.now(UTC).strftime("%Y-%m-%d")
    RESULTS.write_text(
        json.dumps(
            {
                "region": args.region,
                "period": [args.start, args.end],
                "accessed": accessed,
                "rest_url": REST_URL,
                "min_r": MIN_R,
                "max_mad_of_sd": MAX_MAD_OF_SD,
                "results": results,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    DOC.write_text(
        render(results, args.region, args.start, args.end, accessed), encoding="utf-8", newline="\n"
    )
    print(f"wrote {DOC.relative_to(ROOT)} and {RESULTS.relative_to(ROOT)}")
    return 0 if all(r["status"] in ("pass", "n/a") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
