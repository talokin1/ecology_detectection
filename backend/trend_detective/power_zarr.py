"""Read a region's monthly time series from the public NASA POWER Zarr archive (R-02).

The archive is on AWS Open Data and needs no login. Only the chunks covering the requested
box are downloaded. Each result is cached as a small CSV in ``<CACHE_DIR>/power_zarr/`` with a
``<file>.provenance.json`` sidecar, so a region is fetched once and can be served offline.

This module only acquires data. Trend statistics come from ``trend_stats.py``.

SI-assisted (Claude, Anthropic); reviewed by the team (see docs/08-si-usage-log.md).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

BASE_URL = "https://nasa-power.s3.us-west-2.amazonaws.com/"
LANDING_PAGE = "https://power.larc.nasa.gov/"
REGISTRY_PAGE = "https://registry.opendata.aws/nasa-power/"
REPO_ROOT = Path(__file__).resolve().parents[2]

# Stores chunked for time-series reads ("temporal"), UTC versions. freq: M = monthly, D = daily.
SOURCES: dict[str, dict[str, str]] = {
    "merra2": {
        "path": "merra2/temporal/power_merra2_monthly_temporal_utc.zarr",
        "title": "MERRA-2 reanalysis (0.5° × 0.625°, from 1981)",
        "freq": "M",
    },
    "imerg": {
        "path": "imerg/temporal/power_imerg_monthly_temporal_utc.zarr",
        "title": "GPM IMERG precipitation (0.1°, from 1998)",
        "freq": "M",
    },
    "syn1deg": {
        "path": "syn1deg/temporal/power_syn1deg_monthly_temporal_utc.zarr",
        "title": "CERES SYN1deg radiation, clouds, aerosol (1°, from 2001)",
        "freq": "M",
    },
    # Daily MERRA-2. Note: in the *monthly* store T2M_MAX / T2M_MIN are the month's single hottest /
    # coldest hour (Kherson, July 2020: 38.5 °C vs 31.9 °C mean daily maximum). Formulas that need
    # mean daily Tmax/Tmin (e.g. Hargreaves PET) must use monthly_from_daily() on this store.
    "merra2_daily": {
        "path": "merra2/temporal/power_merra2_daily_temporal_utc.zarr",
        "title": "MERRA-2 reanalysis, daily (0.5° × 0.625°, from 1981)",
        "freq": "D",
    },
}
MAX_DAILY_VALUES = 2_000_000_000  # cells x days read in one go (~8 GB float32); larger boxes: split

FILL_VALUE = -999.0


def default_cache_dir() -> Path:
    """``$CACHE_DIR/power_zarr`` (see .env.example); defaults to ``data/cache`` in the repo."""
    base = os.environ.get("CACHE_DIR")
    root = Path(base) if base else REPO_ROOT / "data" / "cache"
    return root / "power_zarr"


@dataclass(frozen=True)
class Region:
    """A latitude/longitude box. Longitudes are in -180..180.

    A box that crosses the antimeridian has ``lon_min > lon_max`` (e.g. 170 to -170).
    """

    name: str
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float

    def __post_init__(self) -> None:
        if not (-90 <= self.lat_min < self.lat_max <= 90):
            raise ValueError("need -90 <= lat_min < lat_max <= 90")
        for lon in (self.lon_min, self.lon_max):
            if not -180 <= lon <= 180:
                raise ValueError("longitudes must be within -180..180")
        if self.lon_min == self.lon_max:
            raise ValueError("lon_min and lon_max must differ")

    @property
    def crosses_antimeridian(self) -> bool:
        return self.lon_min > self.lon_max

    @property
    def bbox_key(self) -> list[float]:
        """Bounds as floats, for cache keys (so 44 and 44.0 hit the same cache file)."""
        return [float(v) for v in (self.lat_min, self.lat_max, self.lon_min, self.lon_max)]


@cache
def open_source(source: str) -> xr.Dataset:
    """Open one of the POWER monthly stores lazily (metadata only)."""
    if source not in SOURCES:
        raise KeyError(f"unknown source {source!r}; choose from {sorted(SOURCES)}")
    import fsspec

    mapper = fsspec.get_mapper(BASE_URL + SOURCES[source]["path"])
    return xr.open_zarr(mapper, consolidated=True)


def list_variables(source: str = "merra2") -> list[str]:
    """Variable names in a source, without the per-hour-of-day variants (``T2M_00`` ...)."""
    ds = open_source(source)
    out = []
    for name, var in ds.data_vars.items():
        if var.ndim != 3:
            continue
        suffix = name.rsplit("_", 1)[-1]
        if len(suffix) == 2 and suffix.isdigit():
            continue
        out.append(name)
    return sorted(out)


def variable_info(variable: str, source: str = "merra2") -> dict[str, str]:
    """Name, units and plain-language definition as published with the data."""
    ds = open_source(source)
    if variable not in ds.data_vars:
        raise KeyError(f"{variable!r} is not in source {source!r}")
    attrs = ds[variable].attrs
    return {
        "variable": variable,
        "source": source,
        "long_name": str(attrs.get("long_name", variable)),
        "units": str(attrs.get("units", "")),
        "definition": str(attrs.get("definition", "")),
    }


def _select_box(da: xr.DataArray, region: Region) -> xr.DataArray:
    lat_slice = (
        slice(region.lat_min, region.lat_max)
        if float(da.lat[0]) < float(da.lat[-1])
        else slice(region.lat_max, region.lat_min)
    )
    da = da.sel(lat=lat_slice)
    if region.crosses_antimeridian:
        box = xr.concat(
            [da.sel(lon=slice(region.lon_min, 180)), da.sel(lon=slice(-180, region.lon_max))],
            dim="lon",
        )
    else:
        box = da.sel(lon=slice(region.lon_min, region.lon_max))
    if box.sizes["lat"] == 0 or box.sizes["lon"] == 0:
        raise ValueError(
            f"region {region.name!r} is smaller than one grid cell of this source; "
            "make the box larger"
        )
    return box


def _area_mean(box: xr.DataArray, freq: str = "M") -> pd.Series:
    """Area-weighted mean over the box for every time step, as a pandas Series.

    Monthly series are indexed by month start (``month``), daily series by date (``date``).
    """
    box = box.where(box != FILL_VALUE)
    weights = np.cos(np.deg2rad(box.lat)).clip(min=0)
    mean = box.weighted(weights).mean(("lat", "lon"), skipna=True)
    s = mean.to_series().dropna()  # also drops the pre-allocated future time steps
    if freq == "D":
        s.index = pd.DatetimeIndex(s.index).normalize()
        s.index.name = "date"
    else:
        s.index = pd.DatetimeIndex(s.index).to_period("M").to_timestamp()
        s.index.name = "month"
    return s.astype(float)


def monthly_from_daily(daily: pd.Series, how: str, min_fraction: float = 0.8) -> pd.Series:
    """Monthly values from a daily series (plan v2, S2).

    ``how="mean"`` for states (temperature, soil moisture): mean of the valid days.
    ``how="sum"`` for fluxes given per day (precipitation in mm/day): monthly total, computed as
    the mean of valid days times the number of days in the month, so a month with a few missing
    days is not biased low. A month is kept only if at least ``min_fraction`` of its days have a
    value. ``attrs["aggregation"]`` records the rule and the months dropped (for ``qc.aggregation``).
    """
    if how not in ("mean", "sum"):
        raise ValueError("how must be 'mean' or 'sum'")
    d = daily.dropna()
    months = pd.DatetimeIndex(d.index).to_period("M")
    g = d.groupby(months)
    mean, n_valid = g.mean(), g.size()
    days_in_month = pd.Series(mean.index.days_in_month, index=mean.index)
    frac = n_valid / days_in_month
    out = mean * days_in_month if how == "sum" else mean
    keep = frac >= min_fraction
    s = out[keep]
    s.index = s.index.to_timestamp()
    s.index.name = "month"
    s.name = daily.name
    units = daily.attrs.get("units", "")
    s.attrs = dict(daily.attrs)
    if how == "sum" and units.endswith("/day"):
        s.attrs["units"] = units[: -len("/day")] + "/month"
    s.attrs["aggregation"] = {
        "from": "daily", "how": how, "min_fraction_of_days": min_fraction,
        "months_dropped": [str(m) for m in frac.index[~keep]],
        "rule": ("mean of valid days" if how == "mean"
                 else "mean of valid days x days in month (monthly total)"),
    }
    return s.astype(float)


LAND_MASK_VARIABLE = "GWETROOT"  # MERRA-2 soil wetness exists only over land (no ocean, no ice sheets)


@cache
def land_mask() -> xr.DataArray:
    """True where MERRA-2 has land (cells with root-zone soil wetness), on the MERRA-2 grid."""
    da = open_source("merra2")[LAND_MASK_VARIABLE].isel(time=0).load()
    return da.notnull() & (da != FILL_VALUE)


def _apply_land_mask(box: xr.DataArray) -> xr.DataArray:
    """Mask non-land cells; other grids take the nearest MERRA-2 cell's land flag."""
    mask = land_mask().sel(lat=box.lat, lon=box.lon, method="nearest")
    mask = mask.assign_coords(lat=box.lat, lon=box.lon)
    return box.where(mask)


def _cache_path(cache_dir: Path, variable: str, region: Region, source: str,
                land_only: bool = False) -> Path:
    key = json.dumps([source, variable, *region.bbox_key] + (["land_only"] if land_only else []))
    digest = hashlib.sha1(key.encode()).hexdigest()[:12]
    return cache_dir / f"{source}_{variable}_{digest}.csv"


def _sidecar_path(path: Path) -> Path:
    return path.with_name(path.name + ".provenance.json")


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=5, check=True,
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _time_fields(s: pd.Series, freq: str) -> dict:
    if freq == "D":
        return {"frequency": "daily", "n_days": int(len(s)),
                "time_range": {"start": s.index[0].strftime("%Y-%m-%d"),
                               "end": s.index[-1].strftime("%Y-%m-%d")}}
    return {"frequency": "monthly", "n_months": int(len(s)),
            "time_range": {"start": s.index[0].strftime("%Y-%m"), "end": s.index[-1].strftime("%Y-%m")}}


def _provenance(ds: xr.Dataset, info: dict[str, str], region: Region, source: str, s: pd.Series,
                land_only: bool = False) -> dict:
    """Provenance record written next to every cached file (docs/06-conventions.md)."""
    return {
        "source": "NASA POWER Zarr archive (AWS Open Data)",
        "source_url": BASE_URL + SOURCES[source]["path"],
        "short_name": str(ds.attrs.get("id", SOURCES[source]["path"].rsplit("/", 1)[-1])),
        "version": str(ds.attrs.get("version", "unknown")),
        "doi": None,  # no DOI published for the Zarr stores; landing pages below
        "landing_page": LANDING_PAGE,
        "registry_page": REGISTRY_PAGE,
        "variable": info,
        "region_name": region.name,
        "bbox": {
            "lat_min": region.lat_min, "lat_max": region.lat_max,
            "lon_min": region.lon_min, "lon_max": region.lon_max,
        },
        **_time_fields(s, SOURCES[source].get("freq", "M")),
        "accessed": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "land_only": land_only,
        "processing": [
            "selected grid cells whose centres fall inside the bbox",
            *(["kept land cells only (MERRA-2 cells with root-zone soil wetness; nearest MERRA-2 "
               "cell for other grids); ocean, lakes and ice sheets excluded"] if land_only else []),
            f"masked fill value {FILL_VALUE}",
            "area mean with cos(latitude) weights, ignoring missing cells",
            "dropped time steps with no data (the store pre-allocates future dates)",
            "kept source units",
        ],
        "script": "backend/trend_detective/power_zarr.py",
        "git_commit": _git_commit(),
    }


def region_series(
    variable: str,
    region: Region,
    source: str = "merra2",
    *,
    cache_dir: Path | str | None = None,
    use_cache: bool = True,
    refresh: bool = False,
    land_only: bool = False,
) -> pd.Series:
    """Area-weighted mean of ``variable`` over ``region`` for every month (or day, for a daily
    source such as ``merra2_daily``; see ``monthly_from_daily``).

    Returns a Series indexed by month start (or date), containing only time steps that have data.
    The Series' ``name`` is the variable and ``attrs`` holds units and long name.
    ``land_only``: average land cells only (see ``land_mask``), e.g. precipitation "over Europe".
    """
    cache_dir = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    path = _cache_path(cache_dir, variable, region, source, land_only)

    if use_cache and not refresh and path.exists():
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        s = df["value"].astype(float)
        s.name = variable
        sidecar = _sidecar_path(path)
        if sidecar.exists():
            prov = json.loads(sidecar.read_text(encoding="utf-8"))
            s.attrs.update(prov.get("variable", {}))
            s.attrs["region"] = region.name
            s.attrs["provenance"] = prov
        s.attrs["from_cache"] = True
        return s

    ds = open_source(source)
    if variable not in ds.data_vars:
        raise KeyError(f"{variable!r} is not in source {source!r}")
    freq = SOURCES[source].get("freq", "M")
    box = _select_box(ds[variable], region)
    if freq == "D" and box.size > MAX_DAILY_VALUES:
        raise ValueError(f"daily read for {region.name!r} is too large ({box.size:,} values); split the box")
    box = box.load()
    if land_only:
        box = _apply_land_mask(box)
    s = _area_mean(box, freq)
    if s.empty:
        raise ValueError(
            f"no data for {variable!r} in region {region.name!r} "
            "(for example a land-only variable over open ocean, or an ocean variable with land_only)"
        )
    s.name = variable
    info = variable_info(variable, source)
    prov = _provenance(ds, info, region, source, s, land_only)
    s.attrs.update(info | {"region": region.name, "provenance": prov, "from_cache": False})

    if use_cache:
        cache_dir.mkdir(parents=True, exist_ok=True)
        s.rename("value").to_csv(path, lineterminator="\n")
        _sidecar_path(path).write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
    return s
