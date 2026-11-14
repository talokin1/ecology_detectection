"""Regional monthly vegetation greenness (NDVI) from MODIS Terra MOD13C2 v061 (R-02).

MOD13C2 is a global 0.05° monthly grid (one ~100 MB HDF4 file per month, LP DAAC). Instead of
downloading whole files, each month's box is cut out server-side with Earthdata OPeNDAP
(~200 KB per month for a country-sized box). Needs Earthdata Login; offline precompute only.
Each regional series is cached as CSV (``month,value,valid_fraction``) with a
``.provenance.json`` sidecar in ``<CACHE_DIR>/earthdata/``.

Decoding (checked on a real granule, 2026-11-14): NDVI is int16 with ``_FillValue = -3000`` and
the HDF4 convention ``scale_factor = 10000`` meaning *divide* by 10000. Do not let a CF decoder
apply it (it would multiply). Quality: ``pixel_reliability`` 0 (good) and 1 (marginal) are kept;
2 (snow/ice), 3 (cloudy) and 4 (estimated from history) are dropped.

A month is kept only if at least ``min_valid_fraction`` of the box's land area passed the
quality filter; otherwise its value is NaN (snowy winters, persistent cloud). This avoids a
regional mean that silently represents only the snow-free corner of the box.

This module only acquires data. Trend statistics come from ``trend_stats.py``.

SI-assisted (Claude, Anthropic); pending team review (see docs/08-si-usage-log.md).
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import netCDF4
import numpy as np
import pandas as pd

from . import earthdata
from .power_zarr import REPO_ROOT, Region, _git_commit

SHORT_NAME = "MOD13C2"
VERSION = "061"
DOI = "10.5067/MODIS/MOD13C2.061"
LANDING_PAGE = "https://lpdaac.usgs.gov/products/mod13c2v061/"
OPENDAP = "https://opendap.earthdata.nasa.gov/collections/{collection}/granules/{granule}.dap.nc4"

GRID = "/MOD_Grid_monthly_CMG_VI"
NDVI_VAR = f"{GRID}/Data_Fields/CMG_0_05_Deg_Monthly_NDVI"
REL_VAR = f"{GRID}/Data_Fields/CMG_0_05_Deg_Monthly_pixel_reliability"

RES = 0.05
NROWS, NCOLS = 3600, 7200
FILL = -3000
VALID_MIN, VALID_MAX = -2000, 10000
SCALE_DIVISOR = 10000.0
KEEP_RELIABILITY = (0, 1)
MIN_VALID_FRACTION = 0.8
MAX_CELLS = 4_000_000  # about 100° x 40°; larger boxes belong in an offline map job
_NETCDF_LOCK = threading.Lock()

VARIABLE_INFO = {
    "variable": "NDVI",
    "source": "mod13c2",
    "long_name": "Vegetation greenness (NDVI, MODIS Terra)",
    "units": "1",
    "definition": (
        "A satellite index of how green and leafy plants are, from -1 to 1; "
        "dense forest is near 0.8, bare soil near 0.1."
    ),
}


def default_cache_dir() -> Path:
    base = os.environ.get("CACHE_DIR")
    return (Path(base) if base else REPO_ROOT / "data" / "cache") / "earthdata"


def grid_index(region: Region) -> tuple[slice, slice]:
    """Row and column ranges (inclusive start, exclusive stop) of 0.05° cells centred in the box.

    Row 0 is the northernmost row (centre 89.975°N); column 0 is centred at 179.975°W.
    """
    if region.crosses_antimeridian:
        raise ValueError("NDVI boxes that cross the antimeridian are not supported; split the box")
    lat_c = 90 - RES / 2 - RES * np.arange(NROWS)
    lon_c = -180 + RES / 2 + RES * np.arange(NCOLS)
    eps = 1e-9
    rows = np.nonzero((lat_c >= region.lat_min - eps) & (lat_c <= region.lat_max + eps))[0]
    cols = np.nonzero((lon_c >= region.lon_min - eps) & (lon_c <= region.lon_max + eps))[0]
    if rows.size == 0 or cols.size == 0:
        raise ValueError(f"region {region.name!r} is smaller than one 0.05° cell")
    if rows.size * cols.size > MAX_CELLS:
        raise ValueError(f"region {region.name!r} is too large for an OPeNDAP subset; split it")
    return slice(int(rows[0]), int(rows[-1]) + 1), slice(int(cols[0]), int(cols[-1]) + 1)


def row_latitudes(rows: slice) -> np.ndarray:
    """Cell-centre latitudes of grid rows (the grid is fixed, so no coordinate request is needed)."""
    return 90 - RES / 2 - RES * np.arange(rows.start, rows.stop)


def constraint(rows: slice, cols: slice) -> str:
    """DAP4 constraint expression for NDVI and pixel reliability over the box.

    Coordinates are not requested: their variable names differ between production runs
    (``YDim_...`` in recent granules, ``Latitude`` in reprocessed older ones), the data paths do not.
    """
    r = f"[{rows.start}:{rows.stop - 1}]"
    c = f"[{cols.start}:{cols.stop - 1}]"
    return ";".join([f"{NDVI_VAR}{r}{c}", f"{REL_VAR}{r}{c}"])


def box_mean(ndvi_raw: np.ndarray, reliability: np.ndarray, lat: np.ndarray) -> tuple[float, float]:
    """cos(lat)-weighted mean NDVI over quality-passed land cells, and the valid land fraction.

    Land = cells with an NDVI value (ocean and unprocessed cells are fill). Returns NaN mean if no
    cell passes.
    """
    ndvi_raw = np.asarray(ndvi_raw)
    land = (ndvi_raw != FILL) & (ndvi_raw >= VALID_MIN) & (ndvi_raw <= VALID_MAX)
    ok = land & np.isin(reliability, KEEP_RELIABILITY)
    w = np.broadcast_to(np.cos(np.deg2rad(lat))[:, None], ndvi_raw.shape)
    w_land = float(w[land].sum())
    if w_land == 0:
        return float("nan"), 0.0
    w_ok = float(w[ok].sum())
    if w_ok == 0:
        return float("nan"), 0.0
    mean = float((w[ok] * ndvi_raw[ok]).sum() / w_ok / SCALE_DIVISOR)
    return mean, w_ok / w_land


def _fetch_month(granule: dict, rows: slice, cols: slice) -> tuple[float, float]:
    url = OPENDAP.format(collection=granule["collection_concept_id"], granule=granule["title"])
    r = earthdata.get(url, params={"dap4.ce": constraint(rows, cols)}, timeout=180)
    # Downloads run in parallel, but netCDF4/HDF5 is not thread-safe (parallel opens segfault,
    # seen 2026-11-14), so parsing is serialised.
    with _NETCDF_LOCK, netCDF4.Dataset("subset.nc4", memory=r.content) as nc:
        nc.set_auto_maskandscale(False)
        fields = nc[GRID]["Data_Fields"]
        ndvi = np.asarray(fields.variables[NDVI_VAR.rsplit("/", 1)[-1]][:])
        rel = np.asarray(fields.variables[REL_VAR.rsplit("/", 1)[-1]][:])
    expected = (rows.stop - rows.start, cols.stop - cols.start)
    if ndvi.shape != expected or rel.shape != expected:
        raise ValueError(f"{granule['title']}: subset shape {ndvi.shape}, expected {expected}")
    return box_mean(ndvi, rel, row_latitudes(rows))


def _granule_month(granule: dict) -> pd.Timestamp:
    return pd.Timestamp(granule["time_start"][:7] + "-01")


def _cache_path(cache_dir: Path, region: Region, min_valid_fraction: float) -> Path:
    key = json.dumps(
        [SHORT_NAME, VERSION, *region.bbox_key, list(KEEP_RELIABILITY), float(min_valid_fraction)]
    )
    return cache_dir / f"mod13c2_ndvi_{hashlib.sha1(key.encode()).hexdigest()[:12]}.csv"


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["month"], index_col="month")


def region_series(
    region: Region,
    *,
    min_valid_fraction: float = MIN_VALID_FRACTION,
    cache_dir: Path | str | None = None,
    refresh: bool = False,
    workers: int = 4,
    progress: bool = False,
    offline: bool = False,
) -> pd.Series:
    """Monthly cos(lat)-weighted mean NDVI over ``region`` (months failing the coverage rule dropped).

    Resumable: finished months are kept in ``<cache>.partial.csv`` until the series is complete.
    Without ``refresh``, a complete cached series is returned without any network access.
    ``offline``: only return a cached series; raise ``NotCachedError`` instead of downloading.
    """
    if region.polygons:  # the cache key and the subset are box-only; never average the whole box silently
        raise ValueError(f"region {region.name!r} has a polygon outline; this reader supports boxes only")
    rows, cols = grid_index(region)
    cache_dir = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    out = _cache_path(cache_dir, region, min_valid_fraction)
    sidecar = out.with_name(out.name + ".provenance.json")
    partial = out.with_name(out.name + ".partial.csv")

    if out.exists() and sidecar.exists() and not refresh:
        df = _read(out)
        prov = json.loads(sidecar.read_text(encoding="utf-8"))
        return _to_series(df, prov, region, from_cache=True)
    if offline:
        raise earthdata.NotCachedError(
            f"NDVI series for {region.name!r} is not cached; run scripts/fetch_earthdata_region.py"
        )

    granules = earthdata.cmr_granules(SHORT_NAME, VERSION)
    by_month = {_granule_month(g): g for g in granules}
    done = (
        _read(partial)
        if partial.exists() and not refresh
        else pd.DataFrame(columns=["value", "valid_fraction"], index=pd.DatetimeIndex([], name="month"))
    )
    todo = [m for m in sorted(by_month) if m not in done.index]

    cache_dir.mkdir(parents=True, exist_ok=True)
    if not partial.exists() or refresh:
        partial.write_text("month,value,valid_fraction\n", encoding="utf-8")
    failed: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_fetch_month, by_month[m], rows, cols): m for m in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            m = futures[fut]
            try:
                mean, frac = fut.result()
            except Exception as exc:  # noqa: BLE001 - record and keep going; a rerun retries it
                failed[f"{m:%Y-%m}"] = f"{type(exc).__name__}: {str(exc)[:120]}"
                continue
            with partial.open("a", encoding="utf-8") as fh:
                fh.write(f"{m:%Y-%m-%d},{mean!r},{frac!r}\n")
            if progress and (i % 20 == 0 or i == len(todo)):
                print(f"  {i}/{len(todo)} months fetched", flush=True)
    if failed:
        first = next(iter(sorted(failed.items())))
        raise RuntimeError(
            f"{len(failed)} of {len(todo)} months failed (first: {first[0]} {first[1]}); "
            f"finished months are kept in {partial.name}; run again to retry the rest"
        )

    df = _read(partial).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df["value"] = df["value"].where(df["valid_fraction"] >= min_valid_fraction)
    kept = df["value"].dropna()
    if kept.empty:
        raise ValueError(f"no month in {region.name!r} passed the coverage rule (no vegetated land?)")

    dropped = [f"{m:%Y-%m}" for m in df.index[df["value"].isna()]]
    prov = {
        "source": "NASA LP DAAC, MODIS Terra MOD13C2 v061 via Earthdata OPeNDAP (Earthdata Login)",
        "source_url": OPENDAP.format(collection=granules[0]["collection_concept_id"], granule="<granule>"),
        "short_name": SHORT_NAME,
        "version": VERSION,
        "doi": DOI,
        "landing_page": LANDING_PAGE,
        "variable": VARIABLE_INFO,
        "region_name": region.name,
        "bbox": {
            "lat_min": region.lat_min,
            "lat_max": region.lat_max,
            "lon_min": region.lon_min,
            "lon_max": region.lon_max,
        },
        "land_only": True,  # MOD13C2 NDVI is a land product (B1-07)
        "grid_rows": [rows.start, rows.stop - 1],
        "grid_cols": [cols.start, cols.stop - 1],
        "time_range": {"start": kept.index[0].strftime("%Y-%m"), "end": kept.index[-1].strftime("%Y-%m")},
        "n_months": len(kept),
        "n_granules": len(df),
        "months_dropped_low_coverage": dropped,
        "min_valid_fraction": min_valid_fraction,
        "accessed": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "processing": [
            "OPeNDAP subset of 0.05° cells whose centres fall inside the bbox",
            f"raw int16 NDVI: masked _FillValue {FILL} and values outside {VALID_MIN}..{VALID_MAX}",
            f"divided by {SCALE_DIVISOR:g} (HDF4 scale_factor convention)",
            "kept pixel_reliability 0 (good) and 1 (marginal); dropped snow/ice, cloudy, estimated",
            "area mean with cos(latitude) weights over quality-passed land cells",
            f"month set to NaN if quality-passed land area < {min_valid_fraction:.0%} of land area",
        ],
        "caveats": [
            "MODIS Terra only (from 2000-02); sensor ageing is corrected in Collection 6.1.",
            "Snowy or cloudy months are dropped, so winter months may be missing in cold regions.",
        ],
        "script": "backend/trend_detective/modis_ndvi.py",
        "git_commit": _git_commit(),
    }
    df.to_csv(out, lineterminator="\n")
    sidecar.write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
    partial.unlink(missing_ok=True)
    return _to_series(df, prov, region, from_cache=False)


def _to_series(df: pd.DataFrame, prov: dict, region: Region, *, from_cache: bool) -> pd.Series:
    s = df["value"].astype(float).dropna()
    s.name = "NDVI"
    s.attrs.update(
        VARIABLE_INFO
        | {
            "region": region.name,
            "provenance": prov,
            "from_cache": from_cache,
            "valid_fraction": df["valid_fraction"].reindex(s.index).tolist(),
        }
    )
    return s
