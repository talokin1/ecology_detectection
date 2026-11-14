"""Regional monthly total water storage from the JPL GRACE/GRACE-FO mascon grid (R-02).

Dataset: TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4 (JPL RL06.3Mv04, CRI filter), PO.DAAC,
DOI 10.5067/TEMSC-3JC634. The whole record is one ~45 MB NetCDF file, downloaded once with
Earthdata Login (offline precompute only) to ``data/cache/raw/grace/``. Each regional series is
cached as CSV with a ``.provenance.json`` sidecar in ``<CACHE_DIR>/earthdata/``.

Values are liquid-water-equivalent thickness anomalies in cm relative to the 2004.0-2009.999 mean.
Only land cells (the product's ``land_mask``) are averaged, with cos(latitude) weights.

This module only acquires data. Trend statistics come from ``trend_stats.py``.

SI-assisted (Claude, Anthropic); reviewed by the team (see docs/08-si-usage-log.md).
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from . import earthdata
from .power_zarr import REPO_ROOT, Region, _git_commit, _select_box

SHORT_NAME = "TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4"
VERSION = "RL06.3Mv04"
DOI = "10.5067/TEMSC-3JC634"
LANDING_PAGE = "https://podaac.jpl.nasa.gov/dataset/TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4"
MASCON_SIZE_DEG = 3.0  # native resolution; the 0.5° grid is an interpolation of 3° mascons

VARIABLE_INFO = {
    "variable": "lwe_thickness",
    "source": "grace",
    "long_name": "Total water storage anomaly (GRACE/GRACE-FO)",
    "units": "cm",
    "definition": (
        "Change in all water on and under the land (snow, soil, lakes, groundwater), as an "
        "equivalent water depth relative to the 2004-2009 average, measured from Earth's gravity."
    ),
}


def raw_dir() -> Path:
    base = os.environ.get("CACHE_DIR")
    return (Path(base) if base else REPO_ROOT / "data" / "cache") / "raw" / "grace"


def default_cache_dir() -> Path:
    base = os.environ.get("CACHE_DIR")
    return (Path(base) if base else REPO_ROOT / "data" / "cache") / "earthdata"


def fetch_file(dest_dir: Path | None = None, *, check_newer: bool = True) -> Path:
    """Path to the newest mascon file (one granule holds the whole record).

    Uses a file already in ``dest_dir`` unless ``check_newer`` finds a newer granule in CMR.
    If CMR cannot be reached, falls back to the newest local file.
    """
    dest_dir = Path(dest_dir) if dest_dir is not None else raw_dir()
    local = sorted(dest_dir.glob("GRCTellus.JPL.*.GLO.RL06.3M.MSCNv04CRI.nc"))
    if local and not check_newer:
        return local[-1]
    try:
        (granule,) = earthdata.cmr_granules(SHORT_NAME)[-1:]
    except Exception:  # noqa: BLE001 - offline: any failure falls back to the local copy
        if local:
            return local[-1]
        raise
    url = earthdata.data_url(granule)
    return earthdata.download(url, dest_dir / url.rsplit("/", 1)[-1])


def assign_months(time_bounds: np.ndarray) -> pd.PeriodIndex:
    """Calendar month of each solution, following JPL's convention.

    Each solution goes to the month of its window midpoint; if that month is already taken by an
    earlier solution (shifted windows, e.g. 2015-04-12..05-11), it moves to the next month. With
    this rule the set of missing months equals the file's ``months_missing`` attribute.
    """
    tb = pd.DataFrame(time_bounds, columns=["start", "end"]).apply(pd.to_datetime)
    mids = tb["start"] + (tb["end"] - tb["start"]) / 2
    months: list[pd.Period] = []
    for mid in mids:
        m = mid.to_period("M")
        while months and m <= months[-1]:
            m += 1
        months.append(m)
    return pd.PeriodIndex(months, freq="M")


def _open(path: Path) -> xr.Dataset:
    ds = xr.open_dataset(path)
    ds = ds.assign_coords(lon=((ds.lon + 180) % 360) - 180).sortby("lon")
    return ds


def _area_mean(ds: xr.Dataset, region: Region, apply_scale_factor: bool) -> tuple[pd.Series, int]:
    lwe = _select_box(ds["lwe_thickness"], region)
    land = _select_box(ds["land_mask"], region) == 1
    n_land = int(land.sum())
    if n_land == 0:
        raise ValueError(f"region {region.name!r} has no GRACE land cells (open ocean?)")
    if apply_scale_factor:
        lwe = lwe * _select_box(ds["scale_factor"], region)
    lwe = lwe.where(land).load()
    weights = np.cos(np.deg2rad(lwe.lat)).clip(min=0)
    mean = lwe.weighted(weights).mean(("lat", "lon"), skipna=True).to_numpy()
    months = assign_months(ds["time_bounds"].to_numpy())
    s = pd.Series(mean, index=months.to_timestamp(), name="lwe_thickness").dropna()
    s.index.name = "month"
    return s.astype(float), n_land


def missing_months(s: pd.Series) -> list[str]:
    full = pd.period_range(s.index[0], s.index[-1], freq="M")
    have = set(pd.DatetimeIndex(s.index).to_period("M"))
    return [str(m) for m in full if m not in have]


def _cache_path(cache_dir: Path, region: Region, apply_scale_factor: bool) -> Path:
    """Keyed by region and options only, so a cached series is found without the raw file.

    The source file name is recorded in the provenance; ``refresh=True`` rebuilds from the
    newest file.
    """
    key = json.dumps([SHORT_NAME, VERSION, *region.bbox_key, apply_scale_factor])
    return cache_dir / f"grace_lwe_{hashlib.sha1(key.encode()).hexdigest()[:12]}.csv"


def region_series(
    region: Region,
    *,
    apply_scale_factor: bool = False,
    path: Path | str | None = None,
    cache_dir: Path | str | None = None,
    refresh: bool = False,
    offline: bool = False,
) -> pd.Series:
    """Monthly land-only, cos(lat)-weighted mean water-storage anomaly (cm) over ``region``.

    ``offline``: only return a cached series; raise ``NotCachedError`` instead of downloading.

    ``path``: a local mascon file (default: download/reuse the newest one). A cached series is
    returned without touching the network or the raw file, unless ``refresh`` is set or ``path``
    names a different file than the one the cache was built from.
    ``apply_scale_factor``: multiply by JPL's CLM-based gain factors before averaging. Off by
    default: they are meant for sub-mascon (< ~3°) land hydrology and are model-dependent.
    """
    cache_dir = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    out = _cache_path(cache_dir, region, apply_scale_factor)
    sidecar = out.with_name(out.name + ".provenance.json")

    if out.exists() and sidecar.exists() and not refresh:
        prov = json.loads(sidecar.read_text(encoding="utf-8"))
        if path is None or Path(path).name == prov.get("file"):
            s = pd.read_csv(out, parse_dates=["month"], index_col="month")["value"].astype(float)
            s.name = "lwe_thickness"
            s.attrs.update(prov["variable"] | {"region": region.name, "provenance": prov, "from_cache": True})
            return s

    if offline:
        raise earthdata.NotCachedError(
            f"GRACE series for {region.name!r} is not cached; run scripts/fetch_earthdata_region.py"
        )
    path = Path(path) if path is not None else fetch_file()
    with _open(path) as ds:
        s, n_land = _area_mean(ds, region, apply_scale_factor)
        attrs = dict(ds.attrs)
    gaps = missing_months(s)
    published_gaps = [m for m in str(attrs.get("months_missing", "")).split(";") if m]
    published_in_range = [m for m in published_gaps if str(s.index[0])[:7] <= m <= str(s.index[-1])[:7]]

    caveats = [
        "Values are anomalies relative to the 2004-2009 mean, not absolute water amounts.",
        "No data 2017-07 to 2018-05 (gap between GRACE and GRACE-FO) and some single months.",
        f"Effective resolution is ~{MASCON_SIZE_DEG:.0f}° (~300 km); small regions mix in neighbours.",
    ]
    height = region.lat_max - region.lat_min
    width = (region.lon_max - region.lon_min) % 360 or 360
    if height < MASCON_SIZE_DEG or width < MASCON_SIZE_DEG:
        caveats.append("This region is smaller than one mascon: treat the series as indicative only.")

    prov = {
        "source": "NASA PO.DAAC, JPL GRACE/GRACE-FO mascon grid (Earthdata Login)",
        "source_url": "https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-protected/"
                      f"{SHORT_NAME}/{path.name}",
        "short_name": SHORT_NAME,
        "version": VERSION,
        "file": path.name,
        "file_date_created": attrs.get("date_created"),
        "doi": DOI,
        "landing_page": LANDING_PAGE,
        "variable": VARIABLE_INFO,
        "region_name": region.name,
        "bbox": {"lat_min": region.lat_min, "lat_max": region.lat_max,
                 "lon_min": region.lon_min, "lon_max": region.lon_max},
        "time_range": {"start": s.index[0].strftime("%Y-%m"), "end": s.index[-1].strftime("%Y-%m")},
        "n_months": int(len(s)),
        "missing_months": gaps,
        "missing_months_match_published": gaps == published_in_range,
        "n_land_cells_0p5deg": n_land,
        "baseline": attrs.get("time_mean_removed"),
        "accessed": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "processing": [
            "converted longitudes 0..360 to -180..180",
            "selected 0.5° cells whose centres fall inside the bbox",
            "kept land cells only (product land_mask == 1)",
            ("multiplied by the product's CLM scale_factor" if apply_scale_factor
             else "no gain (scale) factors applied"),
            "area mean with cos(latitude) weights",
            "each solution assigned to its window-midpoint month; a month already taken moves the "
            "solution to the next month (matches the product's months_missing list)",
            "kept source units (cm liquid water equivalent)",
        ],
        "caveats": caveats,
        "script": "backend/trend_detective/grace.py",
        "git_commit": _git_commit(),
    }
    s.attrs.update(VARIABLE_INFO | {"region": region.name, "provenance": prov, "from_cache": False})
    cache_dir.mkdir(parents=True, exist_ok=True)
    s.rename("value").to_csv(out, lineterminator="\n")
    sidecar.write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
    return s
