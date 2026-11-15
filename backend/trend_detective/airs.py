"""Global monthly AIRS grids (surface air temperature, total water vapour) for the world map.

Dataset: Aqua/AIRS L3 Monthly Standard Physical Retrieval (AIRS-only) 1 degree x 1 degree V7.0,
short name AIRS3STM, version 7.0, GES DISC, DOI 10.5067/UBENJB9D3T2H (checked in CMR 2026-11-15).
"AIRS-only" = infrared-only retrieval for the whole record, so the record has no step when the
AMSU microwave instrument degraded. Independent of MERRA-2: a satellite retrieval, not a reanalysis.

What this module does (acquisition only; trends come from ``trend_stats.py``):
1. ``download``: for every monthly granule, one OPeNDAP (DAP4) subset with the four fields below
   (~0.8 MB instead of the ~200 MB HDF4 file), saved as ``raw/airs/months/<YYYY-MM>.nc``.
   Earthdata token from ``.env`` (see ``earthdata.py``); resumable; never printed.
2. ``build_grid``: day/night mean of the ascending (~1:30 pm local) and descending (~1:30 am)
   orbits, only where both exist (a single orbit would bias the mean towards day or night), then
   area-weighted coarsening to the app's 2° grid with ``grids.coarsen`` (1° cells nest exactly).
   Output and sidecar follow the format of the other map grids.

Units (from the AIRS V7 L3 user guide; the HDF4 file carries none, ranges checked on 2026-10):
SurfAirTemp in K (218–309 K), TotH2OVap in kg/m² (= mm of precipitable water, 0–59).

SI-assisted (Claude, Anthropic); pending team review (see docs/08-si-usage-log.md).
"""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import netCDF4
import numpy as np
import pandas as pd
import xarray as xr

from . import earthdata, grids, power_zarr

SHORT_NAME = "AIRS3STM"
VERSION = "7.0"
COLLECTION = "C1701805662-GES_DISC"
DOI = "10.5067/UBENJB9D3T2H"
LANDING_PAGE = "https://doi.org/10.5067/UBENJB9D3T2H"
TITLE = "Aqua/AIRS L3 Monthly Standard Physical Retrieval (AIRS-only) 1 degree x 1 degree V7.0"
OPENDAP = "https://opendap.earthdata.nasa.gov/collections/{collection}/granules/{granule}.dap.nc4"
FILL = -9999.0
SCRIPT = "backend/trend_detective/airs.py"

FIELDS = {
    "SurfAirTemp": {
        "long_name": "Surface air temperature (AIRS, day/night mean)",
        "units": "K",
        "definition": "Temperature of the air just above the surface retrieved from AIRS infrared radiances, "
        "mean of the ~1:30 am and ~1:30 pm overpasses.",
    },
    "TotH2OVap": {
        "long_name": "Total water vapour (AIRS, day/night mean)",
        "units": "kg/m2",
        "definition": "All the water vapour in the column of air above a square metre (precipitable water), "
        "retrieved from AIRS infrared radiances, mean of the ~1:30 am and ~1:30 pm overpasses.",
    },
}
ORBITS = {"A": "ascending", "D": "descending"}
PATHS = {f"{f}_{o}": f"/{orbit}/Data_Fields/{f}_{o}" for f in FIELDS for o, orbit in ORBITS.items()}
LAT_PATH, LON_PATH = "/location/Data_Fields/Latitude", "/location/Data_Fields/Longitude"
_NETCDF_LOCK = threading.Lock()  # netCDF4/HDF5 is not thread-safe


def default_cache_dir() -> Path:
    """The cache root (``$CACHE_DIR`` or ``data/cache``); grids go to ``grids/``, subsets to ``raw/airs/``."""
    return grids.default_cache_dir().parent


def months_dir(cache_dir: Path) -> Path:
    return Path(cache_dir) / "raw" / "airs" / "months"


def granule_month(granule: dict) -> pd.Timestamp:
    return pd.Timestamp(granule["time_start"][:7] + "-01")


def parse_subset(content: bytes) -> dict[str, np.ndarray]:
    """Fields, latitudes and longitudes of one DAP4 response; fill values become NaN."""
    with _NETCDF_LOCK, netCDF4.Dataset("subset.nc4", memory=content) as nc:
        nc.set_auto_maskandscale(False)
        out = {k: np.asarray(nc[p][:], dtype=np.float32) for k, p in PATHS.items()}
        out["lat"] = np.asarray(nc[LAT_PATH][:, 0], dtype=np.float64)
        out["lon"] = np.asarray(nc[LON_PATH][0, :], dtype=np.float64)
    for k in PATHS:
        if out[k].shape != (180, 360):
            raise ValueError(f"{k}: shape {out[k].shape}, expected (180, 360)")
        out[k][out[k] == FILL] = np.nan
    return out


def fetch_month(granule: dict, cache_dir: Path) -> Path:
    """Download one month's subset to ``raw/airs/months/YYYY-MM.nc`` (skipped if present)."""
    month = granule_month(granule)
    dest = months_dir(cache_dir) / f"{month:%Y-%m}.nc"
    if dest.exists():
        return dest
    url = OPENDAP.format(collection=granule["collection_concept_id"], granule=granule["title"])
    r = earthdata.get(url, params={"dap4.ce": ";".join([*PATHS.values(), LAT_PATH, LON_PATH])}, timeout=180)
    f = parse_subset(r.content)
    ds = xr.Dataset(
        {k: (("lat", "lon"), f[k]) for k in PATHS},
        coords={"lat": f["lat"], "lon": f["lon"]},
        attrs={"granule": granule["title"], "month": f"{month:%Y-%m}"},
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    with _NETCDF_LOCK:
        ds.to_netcdf(tmp, encoding={k: {"zlib": True, "complevel": 4} for k in PATHS}, engine="netcdf4")
    tmp.replace(dest)
    return dest


def download(cache_dir: Path | None = None, workers: int = 6, end: str | None = None) -> list[Path]:
    """All monthly subsets (resumable). ``end``: last month to fetch, e.g. "2025-12"."""
    cache_dir = Path(cache_dir) if cache_dir else default_cache_dir()
    granules = earthdata.cmr_granules(SHORT_NAME, VERSION)
    if end:
        granules = [g for g in granules if granule_month(g) <= pd.Timestamp(end + "-01")]
    months = [granule_month(g) for g in granules]
    if len(set(months)) != len(months):
        raise ValueError("more than one granule for a month; refusing to guess which to use")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda g: fetch_month(g, cache_dir), granules))


def load_month_files(paths: list[Path]) -> xr.Dataset:
    """Stack monthly subsets into (time, lat, lon), latitudes south to north."""
    parts, times = [], []
    for p in sorted(paths):
        with xr.open_dataset(p) as d:
            parts.append(d.load())
            times.append(pd.Timestamp(d.attrs["month"] + "-01"))
    ds = xr.concat(parts, dim="time").assign_coords(time=times)
    return ds.sortby("lat")


def day_night_mean(ds: xr.Dataset, field: str) -> xr.DataArray:
    """Mean of the two overpasses where both have a value; NaN otherwise."""
    a, d = ds[f"{field}_A"], ds[f"{field}_D"]
    return ((a + d) / 2).where(np.isfinite(a) & np.isfinite(d))


def grid_path(cache_dir: Path, field: str, resolution_deg: float) -> Path:
    return Path(cache_dir) / "grids" / f"airs_{field}_{resolution_deg:g}deg.nc"


def build_grid(field: str, resolution_deg: float = 2.0, cache_dir: Path | None = None) -> Path:
    """Coarsen the day/night mean of ``field`` to ``resolution_deg`` and write grid + sidecar."""
    if field not in FIELDS:
        raise KeyError(f"field must be one of {list(FIELDS)}")
    cache_dir = Path(cache_dir) if cache_dir else default_cache_dir()
    files = sorted(months_dir(cache_dir).glob("*.nc"))
    if not files:
        raise FileNotFoundError("no AIRS month files; run download first")
    raw = load_month_files(files)
    da = day_night_mean(raw, field)
    one_orbit = int((np.isfinite(raw[f"{field}_A"]) ^ np.isfinite(raw[f"{field}_D"])).sum())
    out = grids.coarsen(da, resolution_deg, "overlap").rename({"value": field})
    t = pd.DatetimeIndex(out.time.values)
    full = pd.date_range(t[0], t[-1], freq="MS")
    missing = [m.strftime("%Y-%m") for m in full.difference(t)]
    out = out.reindex(time=full)
    out[field].attrs.update({k: FIELDS[field][k] for k in ("long_name", "units", "definition")})
    out["valid_fraction"].attrs.update(
        {"long_name": "share of the cell's area with data in this month", "units": "1"}
    )
    out["n_valid_months"] = np.isfinite(out[field]).sum("time").astype(np.int16)
    out["lat"].attrs.update({"units": "degrees_north", "long_name": "latitude of cell centre"})
    out["lon"].attrs.update({"units": "degrees_east", "long_name": "longitude of cell centre"})

    accessed = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    prov = {
        "source": "NASA GES DISC (OPeNDAP, Earthdata Login)",
        "source_url": f"https://opendap.earthdata.nasa.gov/collections/{COLLECTION}/granules/",
        "short_name": SHORT_NAME,
        "version": VERSION,
        "title": TITLE,
        "doi": DOI,
        "landing_page": LANDING_PAGE,
        "variable": {"variable": field, "source": "airs", **FIELDS[field]},
        "grid": grids._grid_attrs(resolution_deg),
        "native_grid": {"nlat": 180, "nlon": 360, "resolution_deg": 1.0},
        "method": "overlap",
        "frequency": "monthly",
        "n_months": len(full),
        "time_range": {"start": full[0].strftime("%Y-%m"), "end": full[-1].strftime("%Y-%m")},
        "months_without_data_kept_as_nan": missing,
        "accessed": accessed,
        "land_only": False,
        "processing": [
            f"one OPeNDAP DAP4 subset per monthly granule: {', '.join(PATHS)} (no other fields)",
            f"masked fill value {FILL:g}",
            "day/night mean = (ascending ~1:30 pm + descending ~1:30 am) / 2, only where both orbits "
            f"have a value ({one_orbit} native cell-months with a single orbit were left out)",
            f"coarsened 1 deg to {resolution_deg:g} deg with grids.coarsen (overlap; 1 deg cells nest "
            "exactly), cos(latitude) weights, missing native cells left out",
            "valid_fraction = weighted share of the cell's native area with data, per month",
            "time labelled by month start; calendar months without a granule kept as NaN",
            "kept source units (K, kg/m2); stored as float32 with zlib compression",
        ],
        "caveats": [
            "satellite retrieval under clear and partly cloudy skies (cloud clearing); persistently "
            "overcast regions are sampled less",
            "surface air temperature is retrieved, not measured by a thermometer; compare its trends "
            "with MERRA-2 T2M as an independent check, not as the same quantity",
        ],
        "script": SCRIPT,
        "git_commit": power_zarr._git_commit(),
    }
    out.attrs.update(
        {
            **grids._grid_attrs(resolution_deg),
            "variable": field,
            "source": "airs",
            "method": "overlap",
            "land_only": 0,
            "title": f"{FIELDS[field]['long_name']} (AIRS3STM v7.0, {resolution_deg:g} deg monthly grid)",
            "source_url": prov["source_url"],
            "source_version": VERSION,
            "history": f"{accessed} built by {SCRIPT}",
        }
    )
    path = grid_path(cache_dir, field, resolution_deg)
    path.parent.mkdir(parents=True, exist_ok=True)
    enc = {name: {"zlib": True, "complevel": 4, "shuffle": True} for name in out.data_vars}
    for name in (field, "valid_fraction"):
        enc[name].update({"dtype": "float32", "_FillValue": np.float32(np.nan)})
    tmp = path.with_name(path.name + ".tmp")
    out.to_netcdf(tmp, encoding=enc, engine="netcdf4")
    tmp.replace(path)
    path.with_name(path.name + ".provenance.json").write_text(
        json.dumps(prov, indent=2) + "\n", encoding="utf-8"
    )
    return path
