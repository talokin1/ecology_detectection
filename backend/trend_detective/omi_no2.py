"""Regional monthly tropospheric NO2 from OMI/Aura OMNO2d (daily L3, 0.25°), GES DISC (R-02).

OMNO2d is a global 0.25° daily grid (one ~15 MB HDF-EOS5 file per day since 2004-10-01). Each
day's box is cut out server-side with Earthdata OPeNDAP (a few KB per day for a city box), so a
full record is ~8,000 small requests. Needs Earthdata Login; offline precompute only.

Decoding (checked on a real v004 granule's DMR and data, 2026-11-14):

* variable ``/HDFEOS/GRIDS/ColumnAmountNO2/Data_Fields/ColumnAmountNO2TropCloudScreened``,
  float32, dims (YDim=720, XDim=1440), units ``molec/cm2``, ``scale_factor = 1``,
  ``add_offset = 0``, ``_FillValue = MissingValue = -1.2676506e30``;
* grid cell centres: latitude *ascending* from -89.875 (row 0) to 89.875, longitude from
  -179.875 (column 0) to 179.875;
* the product already screens retrievals (cloud fraction < 30 %, solar zenith < 85°, row-anomaly
  and VCD quality flags; see the variable's ``Description`` attribute);
* small negative values occur (retrieval noise after stratosphere subtraction). They are valid
  and are kept: clipping them would bias clean-air means upwards.

Aggregation:

1. per day: cos(lat)-weighted mean over valid cells of the box, plus the valid area fraction;
   the day counts only if ``valid_fraction >= min_valid_area_fraction`` (default 0.5), so a
   "city" mean is never a single suburban corner cell;
2. per month: plain mean of the valid days' box means; the month is kept only if it has at least
   ``min_valid_days`` (default 10) valid days, so the monthly value is not one or two days of
   weather. Day-to-day NO2 variability is ~50 % (wind, boundary layer), so 10 days put the
   sampling error of the monthly mean near 15 %; with fewer days it grows fast.

The daily box means are cached (``omno2d_daily_<hash>.csv``) so the monthly rules can be changed
without downloading again; the monthly series (``omno2d_<hash>.csv``: ``month,value,n_days``) has a
``.provenance.json`` sidecar. Both live in ``<CACHE_DIR>/earthdata/``.

This module only acquires data. Trend statistics come from ``trend_stats.py``.

SI-assisted (Claude, Anthropic); reviewed by the team (see docs/08-si-usage-log.md).
"""

from __future__ import annotations

import calendar
import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import netCDF4
import numpy as np
import pandas as pd

from . import earthdata
from .modis_ndvi import default_cache_dir
from .power_zarr import Region, _git_commit

SHORT_NAME = "OMNO2d"
VERSION = "004"
# From CMR collection metadata (collections.umm_json, 2026-11-14).
DOIS = {"004": "10.5067/AURA/OMI/DATA3407", "003": "10.5067/Aura/OMI/DATA3007"}
LANDING_PAGES = {
    "004": "https://www.earthdata.nasa.gov/data/catalog/ges-disc-limsn7l1rat-001",
    "003": "https://www.earthdata.nasa.gov/data/catalog/ges-disc-limsn7l1profiler-001",
}
OPENDAP = "https://opendap.earthdata.nasa.gov/collections/{collection}/granules/{granule}"

GRID = "/HDFEOS/GRIDS/ColumnAmountNO2"
NO2_VAR = f"{GRID}/Data_Fields/ColumnAmountNO2TropCloudScreened"

RES = 0.25
NROWS, NCOLS = 720, 1440
FILL = -1.2676506e30
FILL_THRESHOLD = -1e29  # anything at or below this is fill (float32 rounding of FILL)
MIN_VALID_AREA_FRACTION = 0.5
MIN_VALID_DAYS = 10
MAX_CELLS = 250_000  # about 125° x 125°; larger boxes belong in an offline map job
_NETCDF_LOCK = threading.Lock()

VARIABLE_INFO = {
    "variable": "NO2_trop",
    "source": "omno2d",
    "long_name": "Tropospheric nitrogen dioxide column (OMI, cloud-screened)",
    "units": "molecules/cm^2",
    "definition": (
        "The amount of NO2 gas, mostly from cars, power plants and industry, in the air between "
        "the ground and about 10 km up, counted as molecules above each square centimetre."
    ),
}


def grid_index(region: Region) -> tuple[slice, slice]:
    """Row and column ranges (inclusive start, exclusive stop) of 0.25° cells centred in the box.

    Row 0 is the southernmost row (centre 89.875°S); column 0 is centred at 179.875°W.
    """
    if region.crosses_antimeridian:
        raise ValueError("NO2 boxes that cross the antimeridian are not supported; split the box")
    lat_c = -90 + RES / 2 + RES * np.arange(NROWS)
    lon_c = -180 + RES / 2 + RES * np.arange(NCOLS)
    eps = 1e-9
    rows = np.nonzero((lat_c >= region.lat_min - eps) & (lat_c <= region.lat_max + eps))[0]
    cols = np.nonzero((lon_c >= region.lon_min - eps) & (lon_c <= region.lon_max + eps))[0]
    if rows.size == 0 or cols.size == 0:
        raise ValueError(f"region {region.name!r} contains no 0.25° cell centre; widen the box")
    if rows.size * cols.size > MAX_CELLS:
        raise ValueError(f"region {region.name!r} is too large for an OPeNDAP subset; split it")
    return slice(int(rows[0]), int(rows[-1]) + 1), slice(int(cols[0]), int(cols[-1]) + 1)


def row_latitudes(rows: slice) -> np.ndarray:
    """Cell-centre latitudes of grid rows (south to north)."""
    return -90 + RES / 2 + RES * np.arange(rows.start, rows.stop)


def col_longitudes(cols: slice) -> np.ndarray:
    return -180 + RES / 2 + RES * np.arange(cols.start, cols.stop)


def constraint(rows: slice, cols: slice) -> str:
    """DAP4 constraint expression for the tropospheric NO2 column over the box."""
    return f"{NO2_VAR}[{rows.start}:{rows.stop - 1}][{cols.start}:{cols.stop - 1}]"


def box_mean(no2: np.ndarray, lat: np.ndarray) -> tuple[float, float]:
    """cos(lat)-weighted mean over valid cells, and the valid share of the box area.

    Valid = finite and not fill. Negative values are valid (retrieval noise). NaN mean if none.
    """
    no2 = np.asarray(no2, dtype=float)
    ok = np.isfinite(no2) & (no2 > FILL_THRESHOLD)
    w = np.broadcast_to(np.cos(np.deg2rad(lat))[:, None], no2.shape)
    w_all = float(w.sum())
    w_ok = float(w[ok].sum())
    if w_all == 0 or w_ok == 0:
        return float("nan"), 0.0
    return float((w[ok] * no2[ok]).sum() / w_ok), w_ok / w_all


def opendap_url(granule: dict) -> str:
    """The granule's Earthdata OPeNDAP URL (from its CMR links, else built from its title)."""
    for link in granule.get("links", []):
        href = link.get("href", "")
        if href.startswith("https://opendap.earthdata.nasa.gov/") and "/granules/" in href:
            return href
    title = quote(granule["title"], safe="")
    return OPENDAP.format(collection=granule["collection_concept_id"], granule=title)


def _fetch_day(granule: dict, rows: slice, cols: slice) -> tuple[float, float]:
    r = earthdata.get(opendap_url(granule) + ".dap.nc4", params={"dap4.ce": constraint(rows, cols)},
                      timeout=120)
    # Downloads run in parallel, but netCDF4/HDF5 is not thread-safe (parallel opens segfault),
    # so parsing is serialised.
    with _NETCDF_LOCK, netCDF4.Dataset("subset.nc4", memory=r.content) as nc:
        var = nc[GRID.strip("/")]["Data_Fields"].variables[NO2_VAR.rsplit("/", 1)[-1]]
        var.set_auto_maskandscale(False)  # scale 1, offset 0; fill handled in box_mean
        no2 = np.asarray(var[:])
    expected = (rows.stop - rows.start, cols.stop - cols.start)
    if no2.shape != expected:
        raise ValueError(f"{granule['title']}: subset shape {no2.shape}, expected {expected}")
    return box_mean(no2, row_latitudes(rows))


def _granule_day(granule: dict) -> pd.Timestamp:
    return pd.Timestamp(granule["time_start"][:10])


def monthly(daily: pd.DataFrame, *, min_valid_area_fraction: float = MIN_VALID_AREA_FRACTION,
            min_valid_days: int = MIN_VALID_DAYS, last_day: pd.Timestamp | None = None) -> pd.DataFrame:
    """Monthly means of valid days from a daily frame (index date; columns value, valid_fraction).

    Returns every calendar month from the first to the last complete month, with ``value`` (NaN
    if fewer than ``min_valid_days`` valid days) and ``n_days`` (valid days used). A trailing month
    is dropped if the data stop before its last day (``last_day``, default the last daily date).
    """
    daily = daily.sort_index()
    good = daily["value"].notna() & (daily["valid_fraction"] >= min_valid_area_fraction)
    vals = daily.loc[good, "value"]
    month_of = vals.index.to_period("M").to_timestamp()
    grouped = vals.groupby(month_of)
    last_day = pd.Timestamp(last_day) if last_day is not None else daily.index.max()
    end = last_day.to_period("M")
    if last_day.day < calendar.monthrange(last_day.year, last_day.month)[1]:
        end -= 1
    months = pd.period_range(daily.index.min().to_period("M"), end, freq="M").to_timestamp()
    out = pd.DataFrame({"value": grouped.mean(), "n_days": grouped.size()}).reindex(months)
    out["n_days"] = out["n_days"].fillna(0).astype(int)
    out.loc[out["n_days"] < min_valid_days, "value"] = np.nan
    out.index.name = "month"
    return out


def _key(*parts) -> str:
    return hashlib.sha1(json.dumps(list(parts)).encode()).hexdigest()[:12]


def _daily_path(cache_dir: Path, region: Region, version: str) -> Path:
    return cache_dir / f"omno2d_daily_{_key(SHORT_NAME, version, *region.bbox_key)}.csv"


def _cache_path(cache_dir: Path, region: Region, version: str, min_valid_area_fraction: float,
                min_valid_days: int) -> Path:
    key = _key(SHORT_NAME, version, *region.bbox_key, float(min_valid_area_fraction), int(min_valid_days))
    return cache_dir / f"omno2d_{key}.csv"


def _read_daily(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["date"], index_col="date")


def region_series(
    region: Region,
    *,
    version: str = VERSION,
    min_valid_area_fraction: float = MIN_VALID_AREA_FRACTION,
    min_valid_days: int = MIN_VALID_DAYS,
    cache_dir: Path | str | None = None,
    refresh: bool = False,
    workers: int = 4,
    progress: bool = False,
    offline: bool = False,
) -> pd.Series:
    """Monthly mean tropospheric NO2 (molecules/cm^2) over ``region``; sparse months dropped.

    Resumable: finished days are kept in ``<daily>.partial.csv`` until every granule is done.
    Without ``refresh``, a cached monthly series (or cached daily means) is used without any
    network access. ``offline``: only return a cached series; raise ``NotCachedError`` otherwise.
    """
    if version not in DOIS:
        raise ValueError(f"unknown OMNO2d version {version!r}; choose from {sorted(DOIS)}")
    rows, cols = grid_index(region)
    cache_dir = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    out = _cache_path(cache_dir, region, version, min_valid_area_fraction, min_valid_days)
    sidecar = out.with_name(out.name + ".provenance.json")
    daily_path = _daily_path(cache_dir, region, version)
    partial = daily_path.with_name(daily_path.name + ".partial.csv")

    if out.exists() and sidecar.exists() and not refresh:
        df = pd.read_csv(out, parse_dates=["month"], index_col="month")
        prov = json.loads(sidecar.read_text(encoding="utf-8"))
        return _to_series(df, prov, region, from_cache=True)
    if offline:
        raise earthdata.NotCachedError(
            f"NO2 series for {region.name!r} is not cached; run scripts/fetch_omi_no2.py"
        )

    failed: dict[str, str] = {}
    meta_path = daily_path.with_name(daily_path.name + ".meta.json")
    if daily_path.exists() and meta_path.exists() and not refresh:
        daily = _read_daily(daily_path)
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        granules = earthdata.cmr_granules(SHORT_NAME, version)
        if not granules:
            raise RuntimeError(f"CMR returned no {SHORT_NAME} v{version} granules")
        by_day = {_granule_day(g): g for g in granules}
        done = _read_daily(partial) if partial.exists() and not refresh else pd.DataFrame(
            columns=["value", "valid_fraction"], index=pd.DatetimeIndex([], name="date"))
        todo = [d for d in sorted(by_day) if d not in done.index]

        cache_dir.mkdir(parents=True, exist_ok=True)
        if not partial.exists() or refresh:
            partial.write_text("date,value,valid_fraction\n", encoding="utf-8")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_fetch_day, by_day[d], rows, cols): d for d in todo}
            for i, fut in enumerate(as_completed(futures), 1):
                d = futures[fut]
                try:
                    mean, frac = fut.result()
                except Exception as exc:  # noqa: BLE001 - record and keep going; a rerun retries it
                    failed[f"{d:%Y-%m-%d}"] = f"{type(exc).__name__}: {str(exc)[:120]}"
                    continue
                with partial.open("a", encoding="utf-8") as fh:
                    fh.write(f"{d:%Y-%m-%d},{mean!r},{frac!r}\n")
                if progress and (i % 100 == 0 or i == len(todo)):
                    print(f"  {i}/{len(todo)} days fetched", flush=True)
        if failed:
            first = next(iter(sorted(failed.items())))
            raise RuntimeError(
                f"{len(failed)} of {len(todo)} days failed (first: {first[0]} {first[1]}); "
                f"finished days are kept in {partial.name}; run again to retry the rest"
            )
        daily = _read_daily(partial).sort_index()
        daily = daily[~daily.index.duplicated(keep="last")]
        meta = {
            "collection_concept_id": granules[0]["collection_concept_id"],
            "n_granules": len(by_day),
            "first_day": f"{min(by_day):%Y-%m-%d}",
            "last_day": f"{max(by_day):%Y-%m-%d}",
        }
        daily.to_csv(daily_path, lineterminator="\n")
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        partial.unlink(missing_ok=True)

    df = monthly(daily, min_valid_area_fraction=min_valid_area_fraction, min_valid_days=min_valid_days,
                 last_day=pd.Timestamp(meta["last_day"]))
    kept = df["value"].dropna()
    if kept.empty:
        raise ValueError(f"no month in {region.name!r} has {min_valid_days} valid days")

    n_valid_days = int((daily["value"].notna() & (daily["valid_fraction"] >= min_valid_area_fraction)).sum())
    lat, lon = row_latitudes(rows), col_longitudes(cols)
    prov = {
        "source": f"NASA GES DISC, OMI/Aura {SHORT_NAME} v{version} via Earthdata OPeNDAP (Earthdata Login)",
        "source_url": OPENDAP.format(collection=meta["collection_concept_id"], granule="<granule>"),
        "short_name": SHORT_NAME,
        "version": version,
        "doi": DOIS[version],
        "landing_page": LANDING_PAGES[version],
        "variable": VARIABLE_INFO | {"source_variable": NO2_VAR, "source_units": "molec/cm2"},
        "units_note": "values are in molecules/cm^2; they are often reported in 1e15 molecules/cm^2",
        "region_name": region.name,
        "bbox": {"lat_min": region.lat_min, "lat_max": region.lat_max,
                 "lon_min": region.lon_min, "lon_max": region.lon_max},
        "grid_rows": [rows.start, rows.stop - 1],
        "grid_cols": [cols.start, cols.stop - 1],
        "cell_centres": {"lat": [round(float(lat[0]), 3), round(float(lat[-1]), 3)],
                         "lon": [round(float(lon[0]), 3), round(float(lon[-1]), 3)],
                         "n_cells": int(lat.size * lon.size)},
        "time_range": {"start": kept.index[0].strftime("%Y-%m"), "end": kept.index[-1].strftime("%Y-%m")},
        "granule_days": {"first": meta["first_day"], "last": meta["last_day"], "n": meta["n_granules"]},
        "n_days_valid": n_valid_days,
        "n_months": int(len(kept)),
        "n_months_total": int(len(df)),
        "months_dropped_few_days": [f"{m:%Y-%m}" for m in df.index[df["value"].isna()]],
        "rules": {"min_valid_area_fraction": min_valid_area_fraction, "min_valid_days": min_valid_days},
        "accessed": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "processing": [
            "OPeNDAP subset of 0.25° cells whose centres fall inside the bbox, one request per daily granule",
            f"masked _FillValue {FILL:g} (scale_factor 1, add_offset 0); negative values kept",
            "daily box mean with cos(latitude) weights over valid cells; valid area fraction recorded",
            f"day used only if valid cells cover >= {min_valid_area_fraction:.0%} of the box area",
            "monthly value = mean of the used days' box means",
            f"month set to NaN if fewer than {min_valid_days} days were used",
            "trailing calendar month dropped if the granules stop before its last day",
        ],
        "caveats": [
            "OMI row anomaly (since 2007, worse after 2009) removes part of the swath, so fewer "
            "valid days in later years; the affected rows are flagged and excluded in the product.",
            "Cloud-screened: only retrievals with cloud fraction < 30 % are gridded, so cloudy "
            "days (frequent in winter) are missing and the monthly mean is a clear-sky mean.",
            "Daily L3 has gaps (orbit gaps, missing granules, screening); months with too few "
            "valid days are dropped, more often in winter.",
            "Aura overpass is about 13:30 local solar time: one early-afternoon snapshot per day, "
            "not a daily average; afternoon NO2 is lower than morning rush-hour NO2.",
            "Tropospheric column (whole lower atmosphere), not ground-level concentration.",
            "Aura has been drifting from its original orbit in recent years (later local overpass "
            "time); check the OMNO2 README before relying on the last years of the record.",
        ],
        "script": "backend/trend_detective/omi_no2.py",
        "git_commit": _git_commit(),
    }
    df.to_csv(out, lineterminator="\n")
    sidecar.write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
    return _to_series(df, prov, region, from_cache=False)


def _to_series(df: pd.DataFrame, prov: dict, region: Region, *, from_cache: bool) -> pd.Series:
    s = df["value"].astype(float).dropna()
    s.name = "NO2_trop"
    s.attrs.update(VARIABLE_INFO | {"region": region.name, "provenance": prov, "from_cache": from_cache,
                                     "n_days": df["n_days"].reindex(s.index).astype(int).tolist()})
    return s
