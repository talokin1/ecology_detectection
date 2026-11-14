"""Global monthly grids from the NASA POWER Zarr archive, for the world trend map (T4, R-02).

``build_grid`` reads one variable for the whole globe from a POWER *temporal* monthly store,
masks the fill value, drops the empty future months the store pre-allocates, and coarsens the
native grid to a regular ``resolution_deg`` grid with an area-weighted, NaN-aware block mean.
The statistics side turns the cube into ``map.json`` (per-cell trend + FDR); no trend is
computed here.

Coarsening (see ``_axis_fractions``):
- Target cell edges are multiples of ``resolution_deg`` from -90 (lat) and -180 (lon), so a
  1° grid has 180 x 360 cells with centres at -89.5 ... 89.5 and -179.5 ... 179.5.
- ``method="centre"``: every native cell goes, whole, to the target cell that contains
  its centre. Cells are half-open ``[lo, hi)``, so a native centre that sits exactly on a target
  edge goes to the cell north / east of it; the native row at +90° goes to the northernmost row.
  The native column centred on -180° goes to the first column (-180 ... -180 + res).
- ``method="overlap"`` (default): each native cell is split between target cells in proportion to the
  overlap of its footprint (first-order conservative remapping). Native cell edges are halfway
  between centres, clipped to ±90°; longitude wraps at the antimeridian.
- Weight of a native cell = cos(latitude of its centre) x its assigned fraction. The native polar
  rows (centre at ±90°) therefore get weight 0, as in ``power_zarr._area_mean``.
- Default is ``overlap``: MERRA-2 longitudes (0.625°) do not nest in 1° cells, so ``centre`` gives
  uneven footprints (alternating 0.625° and 1.25° wide at 1°); on real T2M the two differ by up to
  6.5 °C in climatology near coasts and mountains (checked 2026-11-14).
- Missing native cells are left out of the mean. ``valid_fraction`` is the share of a target
  cell's (weighted) native area that has data, averaged over the months kept.

SI-assisted (Claude, Anthropic); pending team review (see docs/08-si-usage-log.md).
"""

from __future__ import annotations

import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy import sparse

from trend_detective import power_zarr

METHODS = ("centre", "overlap")
MAX_BAND_VALUES = 40_000_000  # native values read per latitude band (~160 MB float32)
SCRIPT = "backend/trend_detective/grids.py"


def default_cache_dir() -> Path:
    """``$CACHE_DIR/grids``; defaults to ``data/cache/grids`` in the repo."""
    base = os.environ.get("CACHE_DIR")
    root = Path(base) if base else power_zarr.REPO_ROOT / "data" / "cache"
    return root / "grids"


def grid_path(
    cache_dir: Path,
    variable: str,
    source: str,
    resolution_deg: float,
    land_only: bool = False,
    method: str = "overlap",
) -> Path:
    name = f"{source}_{variable}_{resolution_deg:g}deg"
    if land_only:
        name += "_land"
    if method != "overlap":  # default method has no suffix
        name += f"_{method}"
    return cache_dir / f"{name}.nc"


def _sidecar_path(path: Path) -> Path:
    return path.with_name(path.name + ".provenance.json")


def _native_edges(centres: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Cell edges halfway between centres; outer edges half a step out, clipped to [lo, hi]."""
    mid = (centres[:-1] + centres[1:]) / 2
    step0, step1 = centres[1] - centres[0], centres[-1] - centres[-2]
    edges = np.concatenate([[centres[0] - step0 / 2], mid, [centres[-1] + step1 / 2]])
    return np.clip(edges, lo, hi)


def _axis_fractions(
    centres: np.ndarray, start: float, res: float, n: int, method: str, periodic: bool = False
) -> sparse.csr_matrix:
    """Sparse (n_native, n_target) matrix: fraction of each native cell given to each target cell.

    ``centres`` must be ascending. Rows sum to 1 for every native cell inside the target domain.
    """
    m = len(centres)
    span = n * res
    if method == "centre":
        pos = centres - start
        if periodic:
            pos = np.mod(pos, span)
        idx = np.floor(pos / res + 1e-9).astype(int)
        idx = np.clip(idx, 0, n - 1)  # the row at +90 (top edge) goes to the last cell
        return sparse.csr_matrix((np.ones(m), (np.arange(m), idx)), shape=(m, n))
    if method != "overlap":
        raise ValueError(f"method must be one of {METHODS}")
    lo_clip, hi_clip = (-np.inf, np.inf) if periodic else (start, start + span)
    edges = _native_edges(centres, lo_clip, hi_clip)
    rows, cols, vals = [], [], []
    shifts = (-span, 0.0, span) if periodic else (0.0,)
    for i in range(m):
        lo, hi = edges[i], edges[i + 1]
        width = hi - lo
        if width <= 0:
            continue
        for shift in shifts:
            a, b = lo + shift - start, hi + shift - start
            if b <= 0 or a >= span:
                continue
            for j in range(max(0, math.floor(a / res)), min(n, math.ceil(b / res))):
                ov = min(b, (j + 1) * res) - max(a, j * res)
                if ov > 1e-12:
                    rows.append(i)
                    cols.append(j)
                    vals.append(ov / width)
    return sparse.csr_matrix((vals, (rows, cols)), shape=(m, n))


def _check_resolution(resolution_deg: float) -> tuple[int, int]:
    nlat, nlon = 180 / resolution_deg, 360 / resolution_deg
    if resolution_deg <= 0 or abs(nlat - round(nlat)) > 1e-9 or abs(nlon - round(nlon)) > 1e-9:
        raise ValueError("resolution_deg must divide 180 exactly (e.g. 0.5, 1, 2, 2.5, 5)")
    return round(nlat), round(nlon)


def _month_start(time: xr.DataArray) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(time.values).to_period("M").to_timestamp().as_unit("ns")


def coarsen(
    da: xr.DataArray, resolution_deg: float, method: str = "overlap", max_band_values: int = MAX_BAND_VALUES
) -> xr.Dataset:
    """Area-weighted, NaN-aware coarsening of a (time, lat, lon) array to a regular global grid.

    ``da`` may be lazy (dask): it is read in latitude bands that each cover the full time axis,
    so every chunk of a location-chunked store is read once. Fill values must already be NaN.
    Returns ``value`` (time, lat, lon) float32 and ``valid_fraction`` (time, lat, lon) float32,
    with all time steps kept (drop empty months afterwards).
    """
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    nlat, nlon = _check_resolution(resolution_deg)
    da = da.transpose("time", "lat", "lon")
    if float(da.lat[0]) > float(da.lat[-1]):
        da = da.isel(lat=slice(None, None, -1))
    if float(da.lon[0]) > float(da.lon[-1]):
        da = da.isel(lon=slice(None, None, -1))
    lat_n, lon_n = da.lat.to_numpy().astype(float), da.lon.to_numpy().astype(float)
    nt = da.sizes["time"]

    flat = _axis_fractions(lat_n, -90.0, resolution_deg, nlat, method)  # (Lat, nlat)
    flon = _axis_fractions(lon_n, -180.0, resolution_deg, nlon, method, periodic=True)  # (Lon, nlon)
    wlat = sparse.diags(np.cos(np.deg2rad(lat_n)).clip(min=0)) @ flat  # cos weights folded in
    wlat_t = wlat.T.tocsr()  # (nlat, Lat)
    # total weight of each target cell (data or not) = column sums of the separable weights
    area = np.outer(np.asarray(wlat.sum(axis=0)).ravel(), np.asarray(flon.sum(axis=0)).ravel())

    num = np.zeros((nt, nlat, nlon))
    den = np.zeros((nt, nlat, nlon))
    chunk = 1
    if getattr(da, "chunks", None):
        chunk = max(da.chunks[1])
    rows = max(chunk, (max_band_values // max(1, nt * len(lon_n))) // chunk * chunk)
    for i0 in range(0, len(lat_n), rows):
        i1 = min(len(lat_n), i0 + rows)
        band = np.asarray(da.isel(lat=slice(i0, i1)).values, dtype=np.float64)  # (T, I, Lon)
        valid = np.isfinite(band)
        band = np.where(valid, band, 0.0)
        nb = i1 - i0
        # longitude: (T*I, Lon) @ (Lon, nlon)
        x = (flon.T @ band.reshape(nt * nb, -1).T).T.reshape(nt, nb, nlon)
        v = (flon.T @ valid.reshape(nt * nb, -1).T.astype(np.float64)).T.reshape(nt, nb, nlon)
        w = wlat_t[:, i0:i1]  # (nlat, I)
        for t in range(nt):
            num[t] += w @ x[t]
            den[t] += w @ v[t]
        del band, valid, x, v

    with np.errstate(invalid="ignore", divide="ignore"):
        value = np.where(den > 0, num / np.where(den > 0, den, 1.0), np.nan)
        frac = np.where(area > 0, den / np.where(area > 0, area, 1.0), 0.0)
    lat_c = -90.0 + resolution_deg * (np.arange(nlat) + 0.5)
    lon_c = -180.0 + resolution_deg * (np.arange(nlon) + 0.5)
    coords = {"time": da.time.values, "lat": lat_c, "lon": lon_c}
    return xr.Dataset(
        {
            "value": (("time", "lat", "lon"), value.astype(np.float32)),
            "valid_fraction": (("time", "lat", "lon"), np.clip(frac, 0, 1).astype(np.float32)),
        },
        coords=coords,
    )


def _trailing_empty(has_data: np.ndarray) -> int:
    """Number of time steps with no data at the end of the axis (pre-allocated future months)."""
    idx = np.flatnonzero(has_data)
    return len(has_data) if idx.size == 0 else len(has_data) - 1 - int(idx[-1])


def _grid_attrs(resolution_deg: float) -> dict:
    nlat, nlon = _check_resolution(resolution_deg)
    return {
        "lat0": -90.0 + resolution_deg / 2,
        "lon0": -180.0 + resolution_deg / 2,
        "dlat": float(resolution_deg),
        "dlon": float(resolution_deg),
        "nlat": nlat,
        "nlon": nlon,
        "grid_reference": "lat0/lon0 are the centre of the south-west cell; rows go north, columns east",
    }


def _provenance(
    src: xr.Dataset,
    info: dict,
    source: str,
    resolution_deg: float,
    method: str,
    land_only: bool,
    ds: xr.Dataset,
    interior_empty: list[str],
    n_dropped: int,
    native: dict,
) -> dict:
    t = pd.DatetimeIndex(ds.time.values)
    split = (
        "each native cell goes, whole, to the target cell containing its centre (half-open "
        "[lo, hi) cells; the native row at +90 goes to the northernmost row; the native column "
        "centred on -180 goes to the first column)"
        if method == "centre"
        else "each native cell is split between target cells in proportion to footprint overlap "
        "(native edges halfway between centres, clipped to +-90, longitude wraps)"
    )
    return {
        "source": "NASA POWER Zarr archive (AWS Open Data)",
        "source_url": power_zarr.BASE_URL + power_zarr.SOURCES[source]["path"],
        "short_name": str(src.attrs.get("id", power_zarr.SOURCES[source]["path"].rsplit("/", 1)[-1])),
        "version": str(src.attrs.get("version", "unknown")),
        "doi": None,  # no DOI published for the Zarr stores; landing pages below
        "landing_page": power_zarr.LANDING_PAGE,
        "registry_page": power_zarr.REGISTRY_PAGE,
        "variable": info,
        "grid": _grid_attrs(resolution_deg),
        "native_grid": native,
        "method": method,
        "frequency": "monthly",
        "n_months": len(t),
        "time_range": {"start": t[0].strftime("%Y-%m"), "end": t[-1].strftime("%Y-%m")},
        "months_without_data_kept_as_nan": interior_empty,
        "accessed": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "land_only": land_only,
        "processing": [
            (
                "read the whole globe for the variable from the temporal (location-chunked) store, "
                "in latitude bands covering the full time axis"
            ),
            f"masked fill value {power_zarr.FILL_VALUE}",
            *(
                [
                    (
                        "kept land cells only (MERRA-2 cells with root-zone soil wetness; nearest MERRA-2 "
                        "cell for other grids); ocean, lakes and ice sheets excluded"
                    )
                ]
                if land_only
                else []
            ),
            (
                f"coarsened to {resolution_deg:g} deg cells with edges at multiples of {resolution_deg:g} "
                "from -90 / -180"
            ),
            split,
            (
                "cell value = mean of native cells weighted by cos(latitude of native centre) x assigned "
                "fraction, ignoring missing native cells (native polar rows get weight 0)"
            ),
            "valid_fraction = weighted share of the cell's native area with data, per month",
            f"dropped {n_dropped} trailing time steps with no data (the store pre-allocates future dates)",
            "time labelled by month start",
            "kept source units; stored as float32 with zlib compression",
        ],
        "script": SCRIPT,
        "git_commit": power_zarr._git_commit(),
    }


def build_grid(
    variable: str,
    source: str = "merra2",
    resolution_deg: float = 1.0,
    *,
    land_only: bool = False,
    method: str = "overlap",
    cache_dir: Path | str | None = None,
    refresh: bool = False,
) -> xr.Dataset:
    """Global monthly grid of ``variable`` at ``resolution_deg``, cached as NetCDF.

    Returns a Dataset with ``<variable>`` (time, lat, lon) in source units, ``valid_fraction``
    (time, lat, lon; 0..1, share of native area with data in that month) and ``n_valid_months``
    (lat, lon). ``lat``/``lon`` are cell centres; ``time`` is month start. Grid attributes
    ``lat0, lon0, dlat, dlon, nlat, nlon`` follow the ``MapLayer`` contract (plan v2).
    """
    if source not in power_zarr.SOURCES or power_zarr.SOURCES[source].get("freq", "M") != "M":
        raise ValueError(f"source must be a monthly POWER store, got {source!r}")
    _check_resolution(resolution_deg)
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    cache_dir = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    path = grid_path(cache_dir, variable, source, resolution_deg, land_only, method)
    if path.exists() and not refresh:
        ds = xr.load_dataset(path)
        ds.attrs["from_cache"] = 1
        return ds

    src = power_zarr.open_source(source)
    if variable not in src.data_vars:
        raise KeyError(f"{variable!r} is not in source {source!r}")
    da = src[variable]
    da = da.where(da != power_zarr.FILL_VALUE)
    if land_only:
        da = power_zarr._apply_land_mask(da)
    native = {
        "nlat": int(da.sizes["lat"]),
        "nlon": int(da.sizes["lon"]),
        "lat_first": float(da.lat.min()),
        "lat_last": float(da.lat.max()),
        "lon_first": float(da.lon.min()),
        "lon_last": float(da.lon.max()),
    }
    out = coarsen(da, resolution_deg, method)

    has_data = np.asarray(np.isfinite(out["value"]).any(("lat", "lon")))
    n_drop = _trailing_empty(has_data)
    if n_drop == len(has_data):
        raise ValueError(f"no data for {variable!r} in source {source!r}")
    out = out.isel(time=slice(0, len(has_data) - n_drop))
    out = out.assign_coords(time=_month_start(out.time))
    interior_empty = [
        t.strftime("%Y-%m")
        for t, ok in zip(pd.DatetimeIndex(out.time.values), has_data[: out.sizes["time"]], strict=True)
        if not ok
    ]

    info = power_zarr.variable_info(variable, source)
    out = out.rename({"value": variable})
    out[variable].attrs.update({k: info[k] for k in ("long_name", "units", "definition")})
    out["valid_fraction"].attrs.update(
        {"long_name": "share of the cell's native area with data in this month", "units": "1"}
    )
    out["n_valid_months"] = np.isfinite(out[variable]).sum("time").astype(np.int16)
    out["n_valid_months"].attrs.update({"long_name": "number of months with a value", "units": "1"})
    out["lat"].attrs.update({"units": "degrees_north", "long_name": "latitude of cell centre"})
    out["lon"].attrs.update({"units": "degrees_east", "long_name": "longitude of cell centre"})
    prov = _provenance(
        src, info, source, resolution_deg, method, land_only, out, interior_empty, n_drop, native
    )
    out.attrs.update(
        {
            **_grid_attrs(resolution_deg),
            "variable": variable,
            "source": source,
            "method": method,
            "land_only": int(land_only),
            "title": f"{info['long_name']} ({source}, {resolution_deg:g} deg monthly grid)",
            "source_url": prov["source_url"],
            "source_version": prov["version"],
            "history": f"{prov['accessed']} built by {SCRIPT}",
        }
    )

    cache_dir.mkdir(parents=True, exist_ok=True)
    enc = {name: {"zlib": True, "complevel": 4, "shuffle": True} for name in out.data_vars}
    for name in (variable, "valid_fraction"):
        enc[name].update({"dtype": "float32", "_FillValue": np.float32(np.nan)})
    tmp = path.with_name(path.name + ".tmp")
    out.to_netcdf(tmp, encoding=enc, engine="netcdf4")
    tmp.replace(path)
    _sidecar_path(path).write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
    out.attrs["from_cache"] = 0
    return out


def grid_summary(path: Path | str) -> dict:
    """Dims, size on disk and time range of a cached grid (for reports)."""
    path = Path(path)
    with xr.open_dataset(path) as ds:
        t = pd.DatetimeIndex(ds.time.values)
        return {
            "path": str(path),
            "size_mb": round(path.stat().st_size / 1e6, 2),
            "dims": {k: int(v) for k, v in ds.sizes.items()},
            "variables": list(ds.data_vars),
            "time_range": {"start": t[0].strftime("%Y-%m"), "end": t[-1].strftime("%Y-%m")},
            "grid": {
                k: np.asarray(ds.attrs[k]).item()
                for k in ("lat0", "lon0", "dlat", "dlon", "nlat", "nlon")
                if k in ds.attrs
            },
        }
