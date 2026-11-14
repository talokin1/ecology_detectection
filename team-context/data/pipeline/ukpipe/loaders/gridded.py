"""Loaders for sources with gridded data on the box (true regional aggregation).

Every loader: load_<src>(region) -> (list[tidy DataFrame], notes dict). Subsets to the
region bounds BEFORE reading values; weights = spherical cell area x fractional overlap.
"""
from __future__ import annotations

import gzip
import io
import shutil

import numpy as np
import pandas as pd
import xarray as xr

from ..core import GLOBAL, PIPE, SAMPLES, VARS, grid_aggregate, make_tidy
from ..regions import Region, bounds_from_centres, cell_weights

CACHE = PIPE / "data" / "cache"
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def _idx_overlap(b: np.ndarray, lo: float, hi: float, pad: float = 0.0):
    b0, b1 = np.minimum(b[:, 0], b[:, 1]), np.maximum(b[:, 0], b[:, 1])
    return np.where((b1 > lo - pad) & (b0 < hi + pad))[0]


def _extent_ok(region: Region, lat_b, lon_b):
    """Region must lie inside the extract extent, allowing one cell of slack: Ukraine-bbox
    extracts were cut on cell centres, so an edge strip < 1 cell can be missing (documented)."""
    tol = float(max(np.median(np.abs(np.diff(lat_b, axis=1))), np.median(np.abs(np.diff(lon_b, axis=1)))))
    return region.covered_by(np.min(lon_b), np.min(lat_b), np.max(lon_b), np.max(lat_b), tol=tol)


def _skip(src, why):
    return [], {"source": src, "status": "skipped", "reason": why}


# ---------------------------------------------------------------- NASA POWER
def _read_power(param):
    frames = []
    for tile in ("west", "east"):
        p = SAMPLES / "nasa_power" / f"POWER_monthly_{param}_{tile}_1981-2025.csv"
        body = p.read_text().split("-END HEADER-\n", 1)[1]
        frames.append(pd.read_csv(io.StringIO(body)))
    df = pd.concat(frames, ignore_index=True).drop_duplicates(["YEAR", "LAT", "LON"], keep="first")
    return df


def load_power(region: Region):
    out, notes = [], {"source": "nasa_power", "status": "ok", "variables": {}}
    fill = VARS["nasa_power"]["fill"]
    for var in VARS["nasa_power"]["variables"]:
        df = _read_power(var)
        lats = np.sort(df["LAT"].unique()); lons = np.sort(df["LON"].unique())
        lat_b, lon_b = bounds_from_centres(lats), bounds_from_centres(lons)
        if not _extent_ok(region, lat_b, lon_b):
            return _skip("nasa_power", "region outside POWER Ukraine-bbox extract")
        frac, area = cell_weights(region, lat_b, lon_b, tag=f"power_{len(lats)}x{len(lons)}")
        years = np.sort(df["YEAR"].unique())
        arr = np.full((len(years), 12, len(lats), len(lons)), np.nan)
        iy = np.searchsorted(years, df["YEAR"].to_numpy()); ila = np.searchsorted(lats, df["LAT"].to_numpy())
        ilo = np.searchsorted(lons, df["LON"].to_numpy())
        vals = df[MONTHS].to_numpy(float)
        vals[vals == fill] = np.nan
        arr[iy, :, ila, ilo] = vals
        data = arr.reshape(len(years) * 12, len(lats), len(lons))
        dates = pd.date_range(f"{years[0]}-01-01", periods=len(data), freq="MS")
        v, n, ne, cov = grid_aggregate(data, frac, area, region_area=region.area_km2)
        out.append(make_tidy("nasa_power", var, region.name, dates, v, n, ne, cov))
        notes["variables"][var] = dict(n_cells_in_file=int(len(df) / len(years)), grid=f"{len(lats)}x{len(lons)}",
                                       n_cells_weight_gt0=int((frac > 0).sum()), sum_frac=float(frac.sum()))
    # derived DTR (plan: POWER T2M_MAX - T2M_MIN)
    tmax = out[[d["variable"].iloc[0] for d in out].index("T2M_MAX")]
    tmin = out[[d["variable"].iloc[0] for d in out].index("T2M_MIN")]
    m = tmax[["date", "value", "n_valid"]].merge(tmin[["date", "value"]], on="date", suffixes=("_x", "_n"))
    out.append(make_tidy("derived", "DTR", region.name, m["date"], m["value_x"] - m["value_n"], m["n_valid"],
                         flags=["derived_from_POWER_T2M_MAX_minus_T2M_MIN"] * len(m)))
    return out, notes


# ---------------------------------------------------------------- GRACE
def load_grace(region: Region, weights: str = "overlap"):
    """weights="overlap" (pipeline default, fractional overlap) or "centre" (cell centres in region;
    the selection behind the approved -11.22 number, used only by the smoke test)."""
    gl = GLOBAL / "grace" / "GRCTellus.JPL.200204_202609.GLO.RL06.3M.MSCNv04CRI.nc"
    bb = SAMPLES / "grace" / "GRCTellus.JPL.200204_202609.GLO.RL06.3M.MSCNv04CRI_ukraine_bbox.nc"
    path = gl if gl.exists() else bb
    ds = xr.open_dataset(path, decode_times=False)
    lat_b = ds["lat_bounds"].values; lon_b = ds["lon_bounds"].values  # lon 0..360
    lo0, la0, lo1, la1 = region.bounds
    if lo0 < 0:
        return _skip("grace", "regions west of 0E need lon wrap (not in v1)")
    ila = _idx_overlap(lat_b, la0, la1); ilo = _idx_overlap(lon_b, lo0, lo1)
    if path == bb and not _extent_ok(region, lat_b, lon_b):
        return _skip("grace", "global file missing and region outside bbox extract")
    sub = ds.isel(lat=ila, lon=ilo)
    lat_b, lon_b = sub["lat_bounds"].values, sub["lon_bounds"].values
    land = sub["land_mask"].values.astype(float)
    lwe = sub["lwe_thickness"].values  # (t, y, x), unscaled
    lwe = np.where(np.abs(lwe) > 9e4, np.nan, lwe)
    mascon = sub["mascon_ID"].values
    tcen = sub["time"].values
    ds.close()
    frac, area = cell_weights(region, lat_b, lon_b, tag=f"grace_{path.name[:20]}_{len(ila)}x{len(ilo)}")
    if weights == "centre":
        LO, LA = np.meshgrid(lon_b.mean(1), lat_b.mean(1))
        frac = region.contains_points(LO, LA).astype(float)
    v, n, ne, cov = grid_aggregate(lwe, frac, area, extra_w=land, region_area=region.area_km2)
    # Dates: official unique-month assignment from the Researcher CSV (plan: "GRACE: CSV date column")
    csv = pd.read_csv(SAMPLES / "grace" / "ukraine_tws_monthly.csv")
    if len(csv) != len(tcen):
        raise RuntimeError("GRACE CSV / NetCDF month count mismatch")
    cen = pd.Timestamp("2002-01-01") + pd.to_timedelta(tcen, unit="D")
    dcheck = np.abs((pd.to_datetime(csv["time_center"]) - cen.normalize()).dt.days).max()
    dates = pd.to_datetime(csv["date"] + "-01")
    # gaps stay NaN (reindex to full monthly axis, no interpolation)
    full = pd.date_range(dates.min(), dates.max(), freq="MS")
    s = pd.DataFrame({"date": dates, "v": v, "n": n, "ne": ne, "cov": cov}).set_index("date").reindex(full)
    flags = np.where(s["v"].isna(), "missing_month_official", "")
    w = frac * area * land
    nmas = len(np.unique(mascon[w > 0]))
    t = make_tidy("grace", "lwe_thickness", region.name, s.index, s["v"], s["n"], s["ne"], s["cov"], flags=flags)
    t.loc[t["date"].between("2017-07-01", "2018-05-01"), "flags"] += ";grace_gracefo_gap"
    # decimal-year time of the actual solution centre, kept for the smoke test
    tc = pd.Series(csv["time_center"].to_numpy(), index=dates)
    return [t], {"source": "grace", "status": "ok", "file": str(path), "n_mascons": int(nmas),
                 "n_land_cells_weight_gt0": int((w > 0).sum()), "time_center_vs_csv_max_days": int(dcheck),
                 "time_center": tc}


# ---------------------------------------------------------------- HadCRUT5
def load_hadcrut5(region: Region):
    ds = xr.open_dataset(SAMPLES / "extra" / "hadcrut5" / "HadCRUT.5.2.0.0.analysis.anomalies.ensemble_mean.nc")
    lat_b = ds["latitude_bnds"].values; lon_b = ds["longitude_bnds"].values
    lo0, la0, lo1, la1 = region.bounds
    ila = _idx_overlap(lat_b, la0, la1); ilo = _idx_overlap(lon_b, lo0, lo1)
    sub = ds["tas_mean"].isel(latitude=ila, longitude=ilo)
    data = sub.values; dates = pd.DatetimeIndex(sub["time"].values)
    ds.close()
    frac, area = cell_weights(region, lat_b[ila], lon_b[ilo], tag="hadcrut5")
    v, n, ne, cov = grid_aggregate(data, frac, area, region_area=region.area_km2)
    return [make_tidy("hadcrut5", "tas_mean", region.name, dates, v, n, ne, cov)], \
        {"source": "hadcrut5", "status": "ok", "n_cells_weight_gt0": int((frac > 0).sum()), "sum_frac": float(frac.sum())}


# ---------------------------------------------------------------- GISTEMP
def _gistemp_nc():
    nc = CACHE / "gistemp1200_GHCNv4_ERSSTv5.nc"
    if not nc.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        with gzip.open(SAMPLES / "extra" / "gistemp" / "gistemp1200_GHCNv4_ERSSTv5.nc.gz") as fi, open(nc, "wb") as fo:
            shutil.copyfileobj(fi, fo)
    return nc


def load_gistemp(region: Region):
    ds = xr.open_dataset(_gistemp_nc())
    lat_b = bounds_from_centres(ds["lat"].values); lon_b = bounds_from_centres(ds["lon"].values)
    lo0, la0, lo1, la1 = region.bounds
    ila = _idx_overlap(lat_b, la0, la1); ilo = _idx_overlap(lon_b, lo0, lo1)
    sub = ds["tempanomaly"].isel(lat=ila, lon=ilo)
    data = sub.values; dates = pd.DatetimeIndex(sub["time"].values)
    ds.close()
    frac, area = cell_weights(region, lat_b[ila], lon_b[ilo], tag="gistemp")
    v, n, ne, cov = grid_aggregate(data, frac, area, region_area=region.area_km2)
    return [make_tidy("gistemp", "tempanomaly", region.name, dates, v, n, ne, cov)], \
        {"source": "gistemp", "status": "ok", "n_cells_weight_gt0": int((frac > 0).sum())}


# ---------------------------------------------------------------- Berkeley Earth 1° (global file)
def load_berkeley(region: Region):
    p = GLOBAL / "berkeley_earth" / "Complete_TAVG_LatLong1.nc"
    if not p.exists():
        return _skip("berkeley", "global Complete_TAVG_LatLong1.nc not on box")
    ds = xr.open_dataset(p, decode_times=False)
    lat_b = bounds_from_centres(ds["latitude"].values); lon_b = bounds_from_centres(ds["longitude"].values)
    lo0, la0, lo1, la1 = region.bounds
    ila = _idx_overlap(lat_b, la0, la1); ilo = _idx_overlap(lon_b, lo0, lo1)
    land = ds["land_mask"].isel(latitude=ila, longitude=ilo).values
    data = ds["temperature"].isel(latitude=ila, longitude=ilo).values
    t = ds["time"].values
    ds.close()
    yr = np.floor(t).astype(int); mo = np.floor((t - yr) * 12).astype(int) + 1
    dates = pd.to_datetime(dict(year=yr, month=mo, day=1))
    frac, area = cell_weights(region, lat_b[ila], lon_b[ilo], tag="berkeley1deg")
    v, n, ne, cov = grid_aggregate(data, frac, area, extra_w=land, region_area=region.area_km2)
    return [make_tidy("berkeley", "temperature", region.name, dates, v, n, ne, cov)], \
        {"source": "berkeley", "status": "ok", "n_cells_weight_gt0": int((frac * land > 0).sum()),
         "weight": "area x overlap x land_mask fraction"}


# ---------------------------------------------------------------- CHIRPS v3 (bbox extract)
def load_chirps(region: Region):
    ds = xr.open_dataset(SAMPLES / "extra" / "chirps_v3" / "chirps_v3_ukraine_bbox_monthly.nc")
    lat_b = bounds_from_centres(ds["lat"].values); lon_b = bounds_from_centres(ds["lon"].values)
    if not _extent_ok(region, lat_b, lon_b):
        ds.close(); return _skip("chirps", "region outside CHIRPS Ukraine-bbox extract")
    lo0, la0, lo1, la1 = region.bounds
    ila = _idx_overlap(lat_b, la0, la1); ilo = _idx_overlap(lon_b, lo0, lo1)
    frac, area = cell_weights(region, lat_b[ila], lon_b[ilo], tag="chirps005")
    da = ds["precip"].isel(lat=ila, lon=ilo)
    dates = pd.DatetimeIndex(da["time"].values)
    vs, ns, nes, covs = [], [], [], []
    for i0 in range(0, len(dates), 120):  # chunk in time to cap RAM
        chunk = da.isel(time=slice(i0, i0 + 120)).values
        chunk = np.where(chunk < -9000, np.nan, chunk)
        r = grid_aggregate(chunk, frac, area, region_area=region.area_km2)
        vs.append(r[0]); ns.append(r[1]); nes.append(r[2]); covs.append(r[3])
        del chunk
    ds.close()
    return [make_tidy("chirps", "precip", region.name, dates, np.concatenate(vs), np.concatenate(ns),
                      np.concatenate(nes), np.concatenate(covs))], \
        {"source": "chirps", "status": "ok", "n_pixels_weight_gt0": int((frac > 0).sum())}


# ---------------------------------------------------------------- ESA CCI SM (bbox extract, partial)
def load_cci_sm(region: Region):
    ds = xr.open_dataset(SAMPLES / "extra" / "cci_sm" / "cci_sm_combined_v09_2_ukraine_bbox_monthly.nc")
    lat_b = bounds_from_centres(ds["lat"].values); lon_b = bounds_from_centres(ds["lon"].values)
    if not _extent_ok(region, lat_b, lon_b):
        ds.close(); return _skip("cci_sm", "region outside CCI SM Ukraine-bbox extract")
    data = ds["sm"].values; dates = pd.DatetimeIndex(ds["time"].values)
    ds.close()
    frac, area = cell_weights(region, lat_b, lon_b, tag="cci025")
    v, n, ne, cov = grid_aggregate(data, frac, area, region_area=region.area_km2)
    t = make_tidy("cci_sm", "sm", region.name, dates, v, n, ne, cov,
                  flags=["partial_record_1978-1991;winter_low_coverage"] * len(dates))
    return [t], {"source": "cci_sm", "status": "ok", "note": "record 1978-11..1991-12 only"}
