"""Generic loaders for the GLOBAL monthly files under $GLOBAL_DATA.

One Product spec per dataset: file glob, date-from-filename, coordinate source, and per-variable
readers (raw -> units of config/variables.yaml). The engine:
  1. reads coordinates once, finds the lat/lon index window overlapping the region bounds,
  2. computes fractional-overlap x spherical-area weights once (cached by regions.cell_weights),
  3. reads ONLY that window from each monthly file (netCDF4 slice -> HDF5 chunk reads),
     aggregates immediately (nothing global is held in RAM), 2 worker processes,
  4. caches the regional monthly series in data/cache/series/ keyed on file list + region.
If the global directory is missing/empty the caller falls back to the old bbox extract loader.
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import os
import re
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import netCDF4
import numpy as np
import pandas as pd

from ..core import GLOBAL, PIPE, grid_aggregate, make_tidy
from ..regions import Region, bounds_from_centres, cell_weights, load_region

SERIES_CACHE = PIPE / "data" / "cache" / "series"
ENGINE_VERSION = "g1"
N_WORKERS = int(os.environ.get("UKPIPE_WORKERS", "2"))


def _ym(pat):
    def f(name):
        s = re.search(pat, name).group(1).replace(".", "")
        return pd.Timestamp(int(s[:4]), int(s[4:6]), 1)
    return f


def _doy(name):
    s = re.search(r"\.A(\d{4})(\d{3})\.", name)
    d = dt.date(int(s.group(1)), 1, 1) + dt.timedelta(days=int(s.group(2)) - 1)
    return pd.Timestamp(d.year, d.month, 1)


def _cmg_coords(n_lat=3600, n_lon=7200):
    lat = 90 - (np.arange(n_lat) + 0.5) * 180 / n_lat
    lon = -180 + (np.arange(n_lon) + 0.5) * 360 / n_lon
    return lat, lon


@dataclass
class VarSpec:
    path: str                      # variable path inside the file ("Grid/precipitation", "a/b/c/name")
    fill: float | None = None      # raw fill value (in addition to _FillValue)
    raw: Callable | None = None    # raw ndarray -> value in variables.yaml raw_unit
    combine: tuple = ()            # alternative: mean of these other VarSpec paths (AIRS A/D)
    derive: tuple | None = None    # (keys_needed, fn(*arrays)) computed PER CELL from earlier keys of the product
    qc: Callable | None = None     # fn(qc_dataset, ys, xs) -> bool "good pixel" mask, applied BEFORE area averaging
    from_qc: bool = False          # read `path` from the paired QC file instead of the data file
    mask_by: str | None = None     # only cells where this (already QC'd) key is valid


@dataclass
class Product:
    source: str
    subdir: str
    glob: str
    date: Callable
    coords: Callable               # (first_path) -> lat_centres, lon_centres
    vars: dict                     # yaml variable key -> VarSpec
    lonlat_order: bool = False     # IMERG stores (time, lon, lat)
    has_time: bool = True
    notes: str = ""
    extra: dict = field(default_factory=dict)


def _nc_coords(latn="lat", lonn="lon", grp=None):
    def f(p):
        with netCDF4.Dataset(p) as ds:
            g = ds[grp] if grp else ds
            return np.asarray(g[latn][:], float), np.asarray(g[lonn][:], float)
    return f


def _airs_coords(p):
    with netCDF4.Dataset(p) as ds:
        g = ds["location/Data_Fields"]
        return np.asarray(g["Latitude"][:, 0], float), np.asarray(g["Longitude"][0, :], float)


def _rawq(qds, path, ys, xs):
    v = qds[path]
    v.set_auto_maskandscale(False)  # QC value 0 = "good" although _FillValue is 0 -> never fill-mask QC bits
    return np.asarray(v[ys, xs])


def _popcount32(a):
    a = np.nan_to_num(a, nan=0).astype(np.uint32)
    return np.unpackbits(a.view(np.uint8).reshape(a.shape + (4,)), axis=-1).sum(-1).astype(np.float64)


VI_QC = "MOD_Grid_monthly_CMG_VI/Data_Fields/"
LST_QC = "MODIS_MONTHLY_0_05DEG_CMG_LST/Data_Fields/"


def _vi_good(qds, ys, xs):
    """MOD13C2 per-pixel QC: pixel_reliability in {0 good, 1 marginal} (excludes -1 fill, 2 snow/ice, 3 cloudy,
    4 estimated) AND VI_Quality bits 0-1 (MODLAND QA) in {00 VI produced good, 01 produced, check other QA}."""
    rel = _rawq(qds, VI_QC + "CMG_0_05_Deg_Monthly_pixel_reliability", ys, xs).astype(np.int16)
    viq = _rawq(qds, VI_QC + "CMG_0_05_Deg_Monthly_VI_Quality", ys, xs).astype(np.uint32)
    return ((rel == 0) | (rel == 1)) & ((viq & 0b11) <= 1)


def _lst_good(which):
    def f(qds, ys, xs):
        """MOD11C3 QC_Day/QC_Night: bits 0-1 mandatory QA, bits 6-7 average LST error.
        keep 00 (LST produced, good quality) OR (01 produced, other quality AND LST error bits <= 01, i.e. <= 2 K);
        drop 10/11 (not produced), and other-quality pixels with LST error > 2 K."""
        q = _rawq(qds, LST_QC + f"QC_{which}", ys, xs).astype(np.uint8)
        mand = q & 0b11
        err = (q >> 6) & 0b11
        return (mand == 0) | ((mand == 1) & (err <= 1))
    return f


PRODUCTS = {
    "merra2_slv": Product("merra2", "merra2_slv_slim", "*.nc4", _ym(r"\.(\d{6})\.nc4"), _nc_coords(),
                          {"T2M": VarSpec("T2M"), "QV2M": VarSpec("QV2M"), "SLP": VarSpec("SLP")}),
    "merra2_flx": Product("merra2", "merra2_flx_slim", "*.nc4", _ym(r"\.(\d{6})\.nc4"), _nc_coords(),
                          {"PRECTOTCORR": VarSpec("PRECTOTCORR"), "PRECTOT": VarSpec("PRECTOT")}),
    "gldas20": Product("gldas20", "gldas20_slim", "*.nc4", _ym(r"\.A(\d{6})\."), _nc_coords(),
                       {k: VarSpec(k) for k in ["SoilMoi0_10cm_inst", "RootMoist_inst", "SWE_inst", "Tair_f_inst",
                                                "Evap_tavg", "Qs_acc", "Qsb_acc"]}),
    "gldas21": Product("gldas21", "gldas21_slim", "*.nc4", _ym(r"\.A(\d{6})\."), _nc_coords(),
                       {k: VarSpec(k) for k in ["SoilMoi0_10cm_inst", "RootMoist_inst", "SWE_inst", "Tair_f_inst",
                                                "Evap_tavg", "Qs_acc", "Qsb_acc"]}),
    "gpm_imerg": Product("gpm_imerg", "gpm_imerg_slim", "*.nc4", _ym(r"\.(\d{6})\d\d-S"), _nc_coords(grp="Grid"),
                         {"precipitation": VarSpec("Grid/precipitation")}, lonlat_order=True),
    "airs": Product("airs", "airs3stm_slim", "*.nc4", _ym(r"AIRS\.(\d{4}\.\d{2})"), _airs_coords,
                    {"SurfAirTemp": VarSpec("", combine=("ascending/Data_Fields/SurfAirTemp_A", "descending/Data_Fields/SurfAirTemp_D")),
                     "TotH2OVap": VarSpec("", combine=("ascending/Data_Fields/TotH2OVap_A", "descending/Data_Fields/TotH2OVap_D"))},
                    has_time=False, notes="per-cell mean of ascending and descending where both exist, else the one available"),
    # MODIS HDF-EOS convention: VI physical = raw / 10000 (attribute 'scale_factor'=10000 is a DIVISOR); LST = raw * 0.02
    "mod13c2": Product("modis", "mod13c2_slim", "*.nc4", _doy, lambda p: _cmg_coords(),
                       {"NDVI": VarSpec("MOD_Grid_monthly_CMG_VI/Data_Fields/CMG_0_05_Deg_Monthly_NDVI", fill=-3000, raw=lambda a: a / 10000.0),
                        "EVI": VarSpec("MOD_Grid_monthly_CMG_VI/Data_Fields/CMG_0_05_Deg_Monthly_EVI", fill=-3000, raw=lambda a: a / 10000.0)},
                       has_time=False),
    "mod11c3": Product("modis", "mod11c3_slim", "*.nc4", _doy, lambda p: _cmg_coords(),
                       {"LST_Day_K": VarSpec("MODIS_MONTHLY_0_05DEG_CMG_LST/Data_Fields/LST_Day_CMG", fill=0, raw=lambda a: a * 0.02),
                        "LST_Night_K": VarSpec("MODIS_MONTHLY_0_05DEG_CMG_LST/Data_Fields/LST_Night_CMG", fill=0, raw=lambda a: a * 0.02)},
                       has_time=False),
    # --- added 14 Nov 2026 (global files pulled after review) ---
    "merra2_wind": Product("merra2", "merra2_slv_wind", "*.nc4", _ym(r"\.(\d{6})\.nc4"), _nc_coords(),
                           {"U10M": VarSpec("U10M"), "V10M": VarSpec("V10M"),
                            # speed computed PER CELL from the MONTHLY-MEAN components (M2TMNXSLV) -> |mean wind|,
                            # which underestimates the mean of the hourly speeds (vector cancellation)
                            "WS10M_from_mean_UV": VarSpec("", derive=(("U10M", "V10M"), lambda u, v: np.hypot(u, v)))}),
    "merra2_ext": Product("merra2", "merra2_statm_extremes", "*.nc4", _ym(r"\.(\d{6})\.nc4"), _nc_coords(),
                          {"T2MMAX": VarSpec("T2MMAX"), "T2MMIN": VarSpec("T2MMIN"),
                           "DTR": VarSpec("", derive=(("T2MMAX", "T2MMIN"), lambda a, b: a - b))},
                          notes="M2SMNXSLV: monthly mean of DAILY max/min 2 m temperature"),
    "gldas20_rainf": Product("gldas20", "gldas20_rainf", "*.nc4", _ym(r"\.A(\d{6})\."), _nc_coords(),
                             {"Rainf_f_tavg": VarSpec("Rainf_f_tavg"), "Snowf_tavg": VarSpec("Snowf_tavg"),
                              "Rain_liquid": VarSpec("", derive=(("Rainf_f_tavg", "Snowf_tavg"),
                                                                 lambda r, sn: np.clip(r - sn, 0, None)))}),
    "gldas21_rainf": Product("gldas21", "gldas21_rainf", "*.nc4", _ym(r"\.A(\d{6})\."), _nc_coords(),
                             {"Rainf_f_tavg": VarSpec("Rainf_f_tavg"), "Snowf_tavg": VarSpec("Snowf_tavg"),
                              "Rain_liquid": VarSpec("", derive=(("Rainf_f_tavg", "Snowf_tavg"),
                                                                 lambda r, sn: np.clip(r - sn, 0, None)))}),
    # MODIS with per-pixel QC from the paired *_qc files (same file names), applied BEFORE area averaging
    "mod13c2_qc": Product("modis", "mod13c2_slim", "*.nc4", _doy, lambda p: _cmg_coords(),
                          {"NDVI": VarSpec("MOD_Grid_monthly_CMG_VI/Data_Fields/CMG_0_05_Deg_Monthly_NDVI", fill=-3000,
                                           raw=lambda a: a / 10000.0, qc=_vi_good),
                           "EVI": VarSpec("MOD_Grid_monthly_CMG_VI/Data_Fields/CMG_0_05_Deg_Monthly_EVI", fill=-3000,
                                          raw=lambda a: a / 10000.0, qc=_vi_good)},
                          has_time=False, extra={"qc_subdir": "mod13c2_qc", "raw_range_key": "mod13c2"}),
    "mod11c3_qc": Product("modis", "mod11c3_slim", "*.nc4", _doy, lambda p: _cmg_coords(),
                          {"LST_Day_K": VarSpec(LST_QC + "LST_Day_CMG", fill=0, raw=lambda a: a * 0.02, qc=_lst_good("Day")),
                           "LST_Night_K": VarSpec(LST_QC + "LST_Night_CMG", fill=0, raw=lambda a: a * 0.02, qc=_lst_good("Night")),
                           "LST_Day_clear_days": VarSpec(LST_QC + "Clear_sky_days", from_qc=True, raw=_popcount32,
                                                         mask_by="LST_Day_K"),
                           "LST_Night_clear_days": VarSpec(LST_QC + "Clear_sky_nights", from_qc=True, raw=_popcount32,
                                                           mask_by="LST_Night_K")},
                          has_time=False, extra={"qc_subdir": "mod11c3_qc", "raw_range_key": "mod11c3"}),
}
VALID_RANGE_RAW = {"mod13c2": (-2000, 10000), "mod11c3": (7500, 65535)}


def _files(prod: Product):
    d = GLOBAL / prod.subdir
    return sorted(d.glob(prod.glob)) if d.exists() else []


def _window(prod: Product, region: Region, first: Path):
    lat, lon = prod.coords(first)
    lat_b, lon_b = bounds_from_centres(lat), bounds_from_centres(lon)
    lo0, la0, lo1, la1 = region.bounds
    lb0, lb1 = lat_b.min(1), lat_b.max(1)
    ob0, ob1 = lon_b.min(1), lon_b.max(1)
    iy = np.where((lb1 > la0) & (lb0 < la1))[0]
    ix = np.where((ob1 > lo0) & (ob0 < lo1))[0]
    ys, xs = slice(int(iy.min()), int(iy.max()) + 1), slice(int(ix.min()), int(ix.max()) + 1)
    return ys, xs, lat_b[ys], lon_b[xs]


def _read_var(ds, prod_key, vs: VarSpec, ys, xs, prod: Product):
    v = ds[vs.path]
    v.set_auto_maskandscale(False)
    if prod.lonlat_order:
        a = np.asarray(v[0, xs, ys], dtype=np.float64).T
    elif prod.has_time and v.ndim == 3:
        a = np.asarray(v[0, ys, xs], dtype=np.float64)
    else:
        a = np.asarray(v[ys, xs], dtype=np.float64)
    bad = ~np.isfinite(a)
    for attr in ("_FillValue", "missing_value"):
        if attr in v.ncattrs():
            bad |= a == float(np.asarray(getattr(v, attr)).ravel()[0])
    if vs.fill is not None:
        bad |= a == vs.fill
    rk = prod.extra.get("raw_range_key", prod_key)
    if rk in VALID_RANGE_RAW:
        lo, hi = VALID_RANGE_RAW[rk]
        bad |= (a < lo) | (a > hi)
    bad |= np.abs(a) >= 1e14
    a[bad] = np.nan
    return vs.raw(a) if vs.raw else a


def _worker(args):
    prod_key, region_name, files, ys, xs, lat_b, lon_b = args
    os.environ.setdefault("OMP_NUM_THREADS", "2")
    prod = PRODUCTS[prod_key]
    region = load_region(region_name)
    frac, area = cell_weights(region, lat_b, lon_b, tag=f"g_{prod_key}")
    out = []
    qdir = GLOBAL / prod.extra["qc_subdir"] if "qc_subdir" in prod.extra else None
    w = frac * area
    for f in files:
        rec = {"date": prod.date(f.name), "file": f.name}
        arrs = {}
        qds = netCDF4.Dataset(qdir / f.name) if qdir is not None else None
        try:
            with netCDF4.Dataset(f) as ds:
                for key, vs in prod.vars.items():
                    if vs.derive:
                        need, fn = vs.derive
                        with np.errstate(invalid="ignore"):
                            a = fn(*[arrs[k] for k in need])
                    elif vs.combine:
                        parts = [_read_var(ds, prod_key, VarSpec(p), ys, xs, prod) for p in vs.combine]
                        with np.errstate(invalid="ignore"):
                            a = np.nanmean(np.stack(parts), axis=0)
                    elif vs.from_qc:
                        a = vs.raw(_rawq(qds, vs.path, ys, xs).astype(np.float64))
                    else:
                        a = _read_var(ds, prod_key, vs, ys, xs, prod)
                    if vs.qc is not None:
                        # unQC'd diagnostics from the same pass, then mask failing pixels BEFORE averaging
                        v0, _, _, c0 = grid_aggregate(a[None], frac, area, region_area=region.area_km2)
                        rec[key + "__noqc"], rec[key + "__cov_noqc"] = v0[0], c0[0]
                        good = vs.qc(qds, ys, xs)
                        valid0 = np.isfinite(a)
                        a = np.where(good, a, np.nan)
                        d0 = float((w * valid0).sum())
                        rec[key + "__qc_kept_area_frac"] = float((w * np.isfinite(a)).sum()) / d0 if d0 > 0 else np.nan
                    if vs.mask_by:
                        a = np.where(np.isfinite(arrs[vs.mask_by]), a, np.nan)
                    arrs[key] = a
                    v, n, ne, cov = grid_aggregate(a[None], frac, area, region_area=region.area_km2)
                    rec[key], rec[key + "__n"], rec[key + "__ne"], rec[key + "__cov"] = v[0], n[0], ne[0], cov[0]
        finally:
            if qds is not None:
                qds.close()
        out.append(rec)
    return out


def _signature(prod_key, region: Region, files):
    h = hashlib.md5(f"{ENGINE_VERSION}|{prod_key}|{region.name}|{json.dumps(region.cfg, sort_keys=True, default=str)}".encode())
    prod = PRODUCTS.get(prod_key)
    qdir = GLOBAL / prod.extra["qc_subdir"] if prod is not None and "qc_subdir" in prod.extra else None
    for f in files:
        st = f.stat()
        h.update(f"{f.name}:{st.st_size}".encode())
        if qdir is not None:
            h.update(f"qc:{(qdir / f.name).stat().st_size}".encode())
    return h.hexdigest()[:16]


def regional_series(prod_key: str, region: Region) -> tuple[pd.DataFrame | None, dict]:
    prod = PRODUCTS[prod_key]
    files = _files(prod)
    if not files:
        return None, {"product": prod_key, "status": "no_global_files"}
    if "qc_subdir" in prod.extra:
        qdir = GLOBAL / prod.extra["qc_subdir"]
        missing = [f.name for f in files if not (qdir / f.name).exists()]
        if missing:
            return None, {"product": prod_key, "status": "qc_files_missing", "n_missing": len(missing)}
    lo0, la0, lo1, la1 = region.bounds
    SERIES_CACHE.mkdir(parents=True, exist_ok=True)
    cf = SERIES_CACHE / f"{prod_key}_{region.name}_{_signature(prod_key, region, files)}.parquet"
    ys, xs, lat_b, lon_b = _window(prod, region, files[0])
    info = {"product": prod_key, "dir": str(GLOBAL / prod.subdir), "n_files": len(files),
            "window_cells": f"{lat_b.shape[0]}x{lon_b.shape[0]}", "cache": cf.name}
    if cf.exists():
        info["status"] = "cached"
        return pd.read_parquet(cf), info
    chunks = [files[i::N_WORKERS * 4] for i in range(N_WORKERS * 4)]
    args = [(prod_key, region.name, c, ys, xs, lat_b, lon_b) for c in chunks if c]
    cell_weights(region, lat_b, lon_b, tag=f"g_{prod_key}")  # build weight cache once before forking
    with ProcessPoolExecutor(max_workers=N_WORKERS) as ex:
        recs = [r for part in ex.map(_worker, args) for r in part]
    df = pd.DataFrame(recs).sort_values("date").reset_index(drop=True)
    df.to_parquet(cf, index=False)
    info["status"] = "computed"
    return df, info


def _to_tidy(df, source, region, keys, flags_fn=None):
    out = []
    for k in keys:
        fl = flags_fn(df["date"], k) if flags_fn else None
        out.append(make_tidy(source, k, region.name, df["date"], df[k].to_numpy(float), df[k + "__n"],
                             df[k + "__ne"], df[k + "__cov"], flags=fl, preaggregated=False))
    return out


def load_from_global(prod_keys: list[str], source: str, region: Region, flags_fn=None, optional=()):
    """Returns (tidy list, notes) or (None, notes) if a REQUIRED global product is missing (-> fallback).
    `optional` products (add-on variables) are skipped with a note when their files are missing."""
    out, notes = [], {"source": source, "status": "ok", "path": "global_grid_overlap_weights", "products": []}
    for pk in list(prod_keys) + list(optional):
        df, info = regional_series(pk, region)
        notes["products"].append(info)
        if df is None:
            if pk in optional:
                info["optional_skipped"] = True
                continue
            notes["status"] = "no_global_files"
            return None, notes
        out += _to_tidy(df, source, region, list(PRODUCTS[pk].vars), flags_fn)
    return out, notes


# ------------------------------------------------------------------ GPCC (gzip NetCDF chunks)
def load_gpcc_global(region: Region):
    d = GLOBAL / "gpcc_v2025_1deg"
    files = sorted(d.glob("gpcc_precipitation_analysis_monthly_*_v2025_100.nc.gz")) if d.exists() else []
    if not files:
        return None, {"source": "gpcc", "status": "no_global_files"}
    SERIES_CACHE.mkdir(parents=True, exist_ok=True)
    cf = SERIES_CACHE / f"gpcc_{region.name}_{_signature('gpcc', region, files)}.parquet"
    if cf.exists():
        df = pd.read_parquet(cf)
    else:
        recs, frac = [], None
        for f in files:  # decompress one chunk at a time into memory, slice, free
            with netCDF4.Dataset("gpcc", memory=gzip.open(f).read()) as ds:
                if frac is None:
                    lat, lon = np.asarray(ds["lat"][:], float), np.asarray(ds["lon"][:], float)
                    lat_b, lon_b = bounds_from_centres(lat), bounds_from_centres(lon)
                    lo0, la0, lo1, la1 = region.bounds
                    iy = np.where((lat_b.max(1) > la0) & (lat_b.min(1) < la1))[0]
                    ix = np.where((lon_b.max(1) > lo0) & (lon_b.min(1) < lo1))[0]
                    ys, xs = slice(iy.min(), iy.max() + 1), slice(ix.min(), ix.max() + 1)
                    frac, area = cell_weights(region, lat_b[ys], lon_b[xs], tag="g_gpcc")
                t = netCDF4.num2date(ds["time"][:], ds["time"].units, only_use_cftime_datetimes=False)
                v = ds["precip"]; v.set_auto_maskandscale(False)
                a = np.asarray(v[:, ys, xs], float)
                a[(a <= -9999) | ~np.isfinite(a)] = np.nan
                val, n, ne, cov = grid_aggregate(a, frac, area, region_area=region.area_km2)
                for i, ti in enumerate(t):
                    recs.append(dict(date=pd.Timestamp(ti.year, ti.month, 1), precip=val[i], precip__n=n[i],
                                     precip__ne=ne[i], precip__cov=cov[i], file=f.name))
        df = pd.DataFrame(recs).drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)
        df.to_parquet(cf, index=False)
    return _to_tidy(df, "gpcc", region, ["precip"]), {"source": "gpcc", "status": "ok", "path": "global_grid_overlap_weights",
                                                      "n_files": len(files), "cache": cf.name}


# ------------------------------------------------------------------ CHIRPS v3 global NetCDF
def load_chirps_global(region: Region):
    p = GLOBAL / "chirps_v3" / "chirps-v3.0.monthly.nc"
    if not p.exists():
        return None, {"source": "chirps", "status": "no_global_files"}
    SERIES_CACHE.mkdir(parents=True, exist_ok=True)
    cf = SERIES_CACHE / f"chirps_{region.name}_{_signature('chirps', region, [p])}.parquet"
    if cf.exists():
        df = pd.read_parquet(cf)
    else:
        with netCDF4.Dataset(p) as ds:
            lat, lon = np.asarray(ds["latitude"][:], float), np.asarray(ds["longitude"][:], float)
            lat_b, lon_b = bounds_from_centres(lat), bounds_from_centres(lon)
            lo0, la0, lo1, la1 = region.bounds
            iy = np.where((lat_b.max(1) > la0) & (lat_b.min(1) < la1))[0]
            ix = np.where((lon_b.max(1) > lo0) & (lon_b.min(1) < lo1))[0]
            ys, xs = slice(iy.min(), iy.max() + 1), slice(ix.min(), ix.max() + 1)
            frac, area = cell_weights(region, lat_b[ys], lon_b[xs], tag="g_chirps")
            t = netCDF4.num2date(ds["time"][:], ds["time"].units, only_use_cftime_datetimes=False)
            v = ds["precip"]; v.set_auto_maskandscale(False)
            recs = []
            for i0 in range(0, len(t), 40):  # file chunk is 40 months
                a = np.asarray(v[i0:i0 + 40, ys, xs], float)
                a[(a <= -9999) | ~np.isfinite(a)] = np.nan
                val, n, ne, cov = grid_aggregate(a, frac, area, region_area=region.area_km2)
                for j in range(len(val)):
                    ti = t[i0 + j]
                    recs.append(dict(date=pd.Timestamp(ti.year, ti.month, 1), precip=val[j], precip__n=n[j],
                                     precip__ne=ne[j], precip__cov=cov[j]))
                del a
        df = pd.DataFrame(recs)
        df.to_parquet(cf, index=False)
    return _to_tidy(df, "chirps", region, ["precip"]), {"source": "chirps", "status": "ok", "path": "global_grid_overlap_weights",
                                                        "file": str(p), "cache": cf.name}
