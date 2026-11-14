#!/usr/bin/env python3
from __future__ import annotations
import csv, gzip, json, os, re, shutil, tempfile
from collections import defaultdict
from datetime import date
from pathlib import Path
import numpy as np
from netCDF4 import Dataset, num2date

BBOX = dict(lon_min=22.1, lon_max=40.2, lat_min=44.4, lat_max=52.4)
OUT = Path("team-context/team/reviews/global")
_TMP = {}

def open_nc(path):
    path = str(path)
    tmp = None
    if path.endswith(".gz"):
        t = tempfile.NamedTemporaryFile(suffix=".nc", delete=False, dir=str(OUT))
        t.close()
        with gzip.open(path, "rb") as s, open(t.name, "wb") as d:
            shutil.copyfileobj(s, d, 8 << 20)
        tmp = t.name
        ds = Dataset(tmp)
    else:
        ds = Dataset(path)
    _TMP[id(ds)] = tmp
    return ds

def close_nc(ds):
    tmp = _TMP.pop(id(ds), None)
    ds.close()
    if tmp and os.path.exists(tmp):
        os.unlink(tmp)

def find_var(ds, names):
    if isinstance(names, str):
        names = [names]
    def rec(g):
        for n in names:
            if n in g.variables:
                return g.variables[n]
        for sg in g.groups.values():
            r = rec(sg)
            if r is not None:
                return r
        return None
    return rec(ds)

def wrap_lon(lon):
    lon = np.asarray(lon, dtype=float)
    return np.where(lon > 180, lon - 360, lon)

def weighted_mean(lat, lon, field, fill=None):
    lat = np.asarray(lat, dtype=float).reshape(-1)
    lon = wrap_lon(np.asarray(lon, dtype=float).reshape(-1))
    if np.ma.isMaskedArray(field):
        data = np.array(field.filled(np.nan), dtype=float)
    else:
        data = np.array(field, dtype=float)
    data = np.squeeze(data)
    if data.ndim == 3 and data.shape[0] == 1:
        data = data[0]
    lat2d, lon2d = np.meshgrid(lat, lon, indexing="ij")
    if data.shape != lat2d.shape:
        if data.T.shape == lat2d.shape:
            data = data.T
        else:
            raise ValueError(f"shape mismatch data={data.shape} lat={lat.size} lon={lon.size}")
    mask = (
        (lat2d >= BBOX["lat_min"]) & (lat2d <= BBOX["lat_max"])
        & (lon2d >= BBOX["lon_min"]) & (lon2d <= BBOX["lon_max"])
        & np.isfinite(data)
    )
    fills = [-9999.0, -999.0, -9.99e8, 9.99999987e14, 1e15]
    if fill is not None and np.isfinite(float(fill)):
        fills.append(float(fill))
    for fv in fills:
        mask &= data != fv
    mask &= np.abs(data) < 1e12
    w = np.cos(np.deg2rad(lat2d))
    w = np.where(mask, w, 0.0)
    n = int(mask.sum())
    if n == 0 or float(w.sum()) == 0:
        return float("nan"), 0
    return float(np.nansum(np.where(mask, data, 0.0) * w) / w.sum()), n

def annual_from_monthly(pairs):
    by = defaultdict(dict)
    for y, m, v in pairs:
        if v is not None and np.isfinite(v):
            by[int(y)][int(m)] = float(v)
    return {y: float(np.mean([md[m] for m in range(1, 13)])) for y, md in by.items() if len(md) == 12}

def max_abs_diff(a, b):
    keys = sorted(set(a) & set(b))
    diffs = []
    for k in keys:
        if np.isfinite(a[k]) and np.isfinite(b[k]):
            diffs.append((abs(a[k] - b[k]), k, a[k], b[k]))
    if not diffs:
        return {"n_overlap": len(keys), "n_finite": 0, "max_abs": None}
    mx, k, av, bv = max(diffs, key=lambda t: t[0])
    ad = np.array([t[0] for t in diffs])
    return {
        "n_overlap": len(keys), "n_finite": len(diffs),
        "max_abs": float(mx), "at": k, "a": av, "b": bv,
        "median_abs": float(np.median(ad)),
        "p95_abs": float(np.percentile(ad, 95)),
        "n_gt_0.01": int((ad > 0.01).sum()),
        "n_gt_0.1": int((ad > 0.1).sum()),
        "n_gt_1": int((ad > 1).sum()),
    }

def parse_times(var, berkeley=False):
    vals = np.array(var[:], dtype=float)
    units = getattr(var, "units", None)
    if berkeley or (units and "year" in str(units).lower()):
        out = []
        for t in np.atleast_1d(vals).astype(float):
            y = int(np.floor(t))
            m = int(np.floor((t - y) * 12) + 1)
            if m < 1:
                y, m = y - 1, 12
            if m > 12:
                y, m = y + 1, 1
            out.append(date(y, m, 1))
        return out
    dates = num2date(vals, units, calendar=getattr(var, "calendar", "standard"))
    return [date(int(d.year), int(d.month), 1) for d in np.atleast_1d(dates)]

def load_csv(path, date_col, val_col):
    rows = []
    with open(path, newline="") as f:
        lines = [ln for ln in f if not ln.startswith("#")]
        for rec in csv.DictReader(lines):
            d = rec[date_col]
            y, m = int(d[:4]), int(d[5:7])
            try:
                v = float(rec[val_col])
            except (TypeError, ValueError):
                v = float("nan")
            rows.append((y, m, v))
    return rows

def pack(comp, ua, extra=None):
    a = {f"{y:04d}-{m:02d}": v for y, m, v in comp}
    b = {f"{y:04d}-{m:02d}": v for y, m, v in ua}
    d = {
        "monthly": max_abs_diff(a, b),
        "annual_12of12": max_abs_diff(annual_from_monthly(comp), annual_from_monthly(ua)),
        "n_months_global": len(comp),
        "n_months_ua": len(ua),
    }
    if extra:
        d.update(extra)
    return d

WEST, EAST, SOUTH, NORTH = 22.1, 40.2, 44.4, 52.4

def rect_overlap(a0, a1, b0, b1):
    lo = max(min(a0, a1), min(b0, b1))
    hi = min(max(a0, a1), max(b0, b1))
    return (lo, hi) if hi > lo else None

def overlap_area(lat0, lat1, lon0, lon1):
    la = rect_overlap(lat0, lat1, SOUTH, NORTH)
    lo = rect_overlap(lon0, lon1, WEST, EAST)
    if la is None or lo is None:
        return 0.0
    return abs(np.radians(lo[1] - lo[0])) * abs(np.sin(np.radians(la[1])) - np.sin(np.radians(la[0])))

out = {}

# ---- CHIRPS diagnostics (recompute) ----
print("CHIRPS diag", flush=True)
ds = Dataset("$GLOBAL_DATA/chirps_v3/chirps-v3.0.monthly.nc")
lat = np.array(ds.variables["latitude"][:], dtype=float)
lon = np.array(ds.variables["longitude"][:], dtype=float)
times = parse_times(ds.variables["time"])
lat_ix = np.where((lat >= BBOX["lat_min"]) & (lat <= BBOX["lat_max"]))[0]
lon_ix = np.where((lon >= BBOX["lon_min"]) & (lon <= BBOX["lon_max"]))[0]
slat = slice(int(lat_ix.min()), int(lat_ix.max()) + 1)
slon = slice(int(lon_ix.min()), int(lon_ix.max()) + 1)
lat_sub, lon_sub = lat[slat], lon[slon]
var = ds.variables["precip"]
data = np.array(var[:, slat, slon], dtype=np.float64)
fill = getattr(var, "_FillValue", None)
if fill is not None:
    data = np.where(data == float(fill), np.nan, data)
data = np.where(data < -9000, np.nan, data)
wlat = np.cos(np.deg2rad(lat_sub)).reshape(1, -1, 1)
w = np.broadcast_to(wlat, data.shape).copy()
w[np.isnan(data)] = 0
num = np.nansum(np.nan_to_num(data) * w, axis=(1, 2))
den = w.sum(axis=(1, 2))
nvalid = np.isfinite(data).sum(axis=(1, 2))
means = np.where(den > 0, num / den, np.nan)
chirps_comp = [(t.year, t.month, float(means[i]), int(nvalid[i])) for i, t in enumerate(times)]
ds.close()
ua = load_csv("$UKRAINE_SAMPLES/extra/chirps_v3/chirps_v3_ukraine_bbox_monthly.csv", "time", "precip_mm")
ua_nv = {}
with open("$UKRAINE_SAMPLES/extra/chirps_v3/chirps_v3_ukraine_bbox_monthly.csv") as f:
    lines = [ln for ln in f if not ln.startswith("#")]
    for rec in csv.DictReader(lines):
        ua_nv[rec["time"]] = int(float(rec["n_valid_pixels"]))
a = {f"{y:04d}-{m:02d}": v for y, m, v, n in chirps_comp}
b = {f"{y:04d}-{m:02d}": v for y, m, v in ua}
# diffs by period
rows = []
for k in sorted(set(a) & set(b)):
    dabs = abs(a[k]-b[k])
    rows.append((k, a[k], b[k], dabs, int(k[:4]) >= 2026))
# pre-2026 stats
pre = [r for r in rows if not r[4]]
y2026 = [r for r in rows if r[4]]
worst = sorted(rows, key=lambda r: -r[3])[:15]

# compare against ukraine cut nc if possible
ua_nc = Path("$UKRAINE_SAMPLES/extra/chirps_v3/chirps_v3_ukraine_bbox_monthly.nc")
pixel = None
if ua_nc.exists():
    ds2 = Dataset(str(ua_nc))
    print("  ua nc vars", list(ds2.variables), "dims", {k:len(v) for k,v in ds2.dimensions.items()}, flush=True)
    # try to align grids and compare a few months
    la2 = np.array(find_var(ds2, ["lat","latitude","y"])[:], dtype=float) if find_var(ds2, ["lat","latitude","y"]) is not None else None
    lo2 = np.array(find_var(ds2, ["lon","longitude","x"])[:], dtype=float) if find_var(ds2, ["lon","longitude","x"]) is not None else None
    p2 = find_var(ds2, ["precip","precipitation","precip_mm"])
    t2 = find_var(ds2, ["time","T"])
    pixel = {"ua_nc_vars": list(ds2.variables), "ua_nc_dims": {k:int(v.size) for k,v in ds2.dimensions.items()}}
    if la2 is not None:
        pixel["ua_lat"] = [float(la2.min()), float(la2.max()), int(la2.size)]
        pixel["ua_lon"] = [float(lo2.min()), float(lo2.max()), int(lo2.size)]
        pixel["glob_lat"] = [float(lat_sub.min()), float(lat_sub.max()), int(lat_sub.size)]
        pixel["glob_lon"] = [float(lon_sub.min()), float(lon_sub.max()), int(lon_sub.size)]
        # compare first and a 2026 month if possible
        t2d = parse_times(t2)
        d2 = np.array(p2[:], dtype=float)
        # match months
        idx2 = {f"{d.year:04d}-{d.month:02d}": i for i,d in enumerate(t2d)}
        idx1 = {f"{y:04d}-{m:02d}": i for i,(y,m,_,__) in enumerate(chirps_comp)}
        pixm = {}
        for ym in ["1981-01", "2000-07", "2020-07", "2026-02", "2026-09"]:
            if ym in idx1 and ym in idx2:
                A = data[idx1[ym]]
                B = d2[idx2[ym]]
                if A.shape != B.shape:
                    pixm[ym] = {"shapes": [list(A.shape), list(B.shape)]}
                else:
                    both = np.isfinite(A) & np.isfinite(B)
                    pixm[ym] = {
                        "max_abs": float(np.max(np.abs(A[both]-B[both]))) if both.any() else None,
                        "n_both": int(both.sum()),
                        "n_only_g": int((np.isfinite(A) & ~np.isfinite(B)).sum()),
                        "n_only_u": int((np.isfinite(B) & ~np.isfinite(A)).sum()),
                        "mean_g": float(np.nanmean(A)),
                        "mean_u": float(np.nanmean(B)),
                    }
        pixel["months"] = pixm
        # lat/lon exact match?
        if la2.size == lat_sub.size and lo2.size == lon_sub.size:
            pixel["lat_max_abs"] = float(np.max(np.abs(la2 - lat_sub)))
            pixel["lon_max_abs"] = float(np.max(np.abs(lo2 - lon_sub)))
    ds2.close()

out["chirps"] = pack([(y,m,v) for y,m,v,n in chirps_comp], ua, {
    "n_valid_global_minmax": [int(nvalid.min()), int(nvalid.max())],
    "n_valid_ua": ua_nv.get("1981-01"),
    "grid": {"nlat": int(lat_sub.size), "nlon": int(lon_sub.size),
             "lat": [float(lat_sub.min()), float(lat_sub.max())],
             "lon": [float(lon_sub.min()), float(lon_sub.max())]},
    "ua_only": sorted({f"{y:04d}-{m:02d}" for y,m,v in ua} - set(a)),
    "pre2026": max_abs_diff({k:a[k] for k in a if k < "2026-01"}, {k:b[k] for k in b if k < "2026-01"}),
    "y2026": [{"k": r[0], "g": r[1], "u": r[2], "abs": r[3]} for r in y2026],
    "worst15": [{"k": r[0], "g": r[1], "u": r[2], "abs": r[3]} for r in worst],
    "pixel_vs_ua_nc": pixel,
})
print("  monthly", out["chirps"]["monthly"], "pre2026", out["chirps"]["pre2026"], "ua_only", out["chirps"]["ua_only"], flush=True)

# ---- HadCRUT ----
print("HadCRUT", flush=True)
ds = Dataset("$GLOBAL_DATA/hadcrut5/HadCRUT.5.2.0.0.analysis.anomalies.ensemble_mean.nc")
lat = np.array(ds.variables["latitude"][:], dtype=float)
lon = np.array(ds.variables["longitude"][:], dtype=float)
lat_b = np.array(ds.variables["latitude_bnds"][:], dtype=float)
lon_b = np.array(ds.variables["longitude_bnds"][:], dtype=float)
tas = ds.variables["tas_mean"]
times = parse_times(ds.variables["time"])
cells = []
for i in range(lat.size):
    for j in range(lon.size):
        area = overlap_area(lat_b[i, 0], lat_b[i, 1], lon_b[j, 0], lon_b[j, 1])
        if area > 0:
            cells.append((i, j, area))
data = np.array(tas[:], dtype=float)
if np.ma.isMaskedArray(tas[:]):
    data = np.array(np.ma.filled(tas[:], np.nan), dtype=float)
fill = getattr(tas, "_FillValue", None)
if fill is not None:
    data = np.where(data == float(fill), np.nan, data)
comp = []
for t, d in enumerate(times):
    num = den = 0.0
    for i, j, area in cells:
        v = data[t, i, j]
        if np.isfinite(v):
            num += v * area
            den += area
    comp.append((d.year, d.month, (num / den) if den else float("nan")))
ds.close()
ua = load_csv("$UKRAINE_SAMPLES/extra/hadcrut5/hadcrut5_ukraine_bbox_monthly.csv", "date", "tas_anomaly_C")
out["hadcrut"] = pack(comp, ua, {"n_overlap_cells": len(cells)})
print(" ", out["hadcrut"]["monthly"], "cells", len(cells), flush=True)

# ---- GISTEMP ----
print("GISTEMP", flush=True)
# find date col
with open("$UKRAINE_SAMPLES/extra/gistemp/gistemp_ukraine_bbox_monthly.csv") as f:
    cols = [ln for ln in f if not ln.startswith("#")][0].strip().split(",")
print("  gistemp cols", cols, flush=True)
datecol = "date" if "date" in cols else "time"
ds = open_nc("$GLOBAL_DATA/gistemp/gistemp1200_GHCNv4_ERSSTv5.nc.gz")
lat = np.array(ds.variables["lat"][:], dtype=float)
lon = wrap_lon(np.array(ds.variables["lon"][:], dtype=float))
times = parse_times(ds.variables["time"])
pvar = ds.variables["tempanomaly"]
cells = []
for i, la in enumerate(lat):
    for j, lo in enumerate(lon):
        area = overlap_area(la - 1.0, la + 1.0, lo - 1.0, lo + 1.0)
        if area > 0:
            cells.append((i, j, area))
data = np.array(pvar[:], dtype=float)
if np.ma.isMaskedArray(pvar[:]):
    data = np.array(np.ma.filled(pvar[:], np.nan), dtype=float)
fill = getattr(pvar, "_FillValue", None)
if fill is not None:
    data = np.where(data == float(fill), np.nan, data)
data = np.where(np.abs(data) > 1e10, np.nan, data)
comp = []
for t, d in enumerate(times):
    num = den = 0.0
    for i, j, area in cells:
        v = data[t, i, j]
        if np.isfinite(v):
            num += v * area
            den += area
    comp.append((d.year, d.month, (num / den) if den else float("nan")))
close_nc(ds)
ua = load_csv("$UKRAINE_SAMPLES/extra/gistemp/gistemp_ukraine_bbox_monthly.csv", datecol, "tas_anomaly_C")
out["gistemp"] = pack(comp, ua, {"n_overlap_cells": len(cells), "cols": cols})
print(" ", out["gistemp"]["monthly"], "cells", len(cells), flush=True)

# ---- Berkeley ----
print("Berkeley", flush=True)
ds = Dataset("$GLOBAL_DATA/berkeley_earth/Complete_TAVG_LatLong1.nc")
lat = np.array(ds.variables["latitude"][:], dtype=float)
lon = np.array(ds.variables["longitude"][:], dtype=float)
times = parse_times(ds.variables["time"], berkeley=True)
pvar = ds.variables["temperature"]
data = pvar[:]
comp = []
n0 = None
for t, d in enumerate(times):
    mean, n = weighted_mean(lat, lon, data[t], fill=getattr(pvar, "_FillValue", None))
    if n0 is None:
        n0 = n
    comp.append((d.year, d.month, mean))
# check unique months (no dups)
keys = [f"{y:04d}-{m:02d}" for y,m,_ in comp]
from collections import Counter
dups = [k for k,c in Counter(keys).items() if c>1]
ds.close()
ua = load_csv("$UKRAINE_SAMPLES/extra/berkeley_earth/berkeley_earth_ukraine_bbox_monthly.csv", "time", "tavg_anomaly_C")
out["berkeley"] = pack(comp, ua, {"n_cells": n0, "dups": dups, "span": [times[0].isoformat(), times[-1].isoformat(), len(times)]})
print(" ", out["berkeley"]["monthly"], "n_cells", n0, "dups", dups, flush=True)

# ---- AIRS ----
print("AIRS", flush=True)
files = {}
for p in Path("$GLOBAL_DATA/airs3stm_slim").glob("AIRS.*"):
    m = re.search(r"AIRS\.(\d{4})\.(\d{2})", p.name)
    if m:
        files[m.group(1)+m.group(2)] = p

def airs_mean(path):
    ds = Dataset(str(path))
    try:
        lat = np.array(find_var(ds, ["Latitude", "lat"])[:], dtype=float)
        lon = np.array(find_var(ds, ["Longitude", "lon"])[:], dtype=float)
        if lat.ndim > 1:
            lat1 = lat[:, 0] if lat.shape[1] > 1 else np.unique(lat)
            lon1 = lon[0, :] if lon.shape[0] > 1 else np.unique(lon)
        else:
            lat1, lon1 = lat, lon
        va = find_var(ds, ["SurfAirTemp_A"])
        vd = find_var(ds, ["SurfAirTemp_D"])
        fill = getattr(va, "_FillValue", None)
        ma, na = weighted_mean(lat1, lon1, va[:], fill=fill)
        md, nd = weighted_mean(lat1, lon1, vd[:], fill=fill)
        comb = 0.5 * (ma + md) if (np.isfinite(ma) and np.isfinite(md)) else (ma if np.isfinite(ma) else md)
        return comb, ma, md, na, nd, lat1.size, lon1.size
    finally:
        ds.close()

ua_airs = {}
with open("$UKRAINE_SAMPLES/airs/airs_ukraine_monthly.csv", newline="") as f:
    for rec in csv.DictReader(f):
        ua_airs[rec["date"]] = {"combined": float(rec["SurfAirTemp"]), "A": float(rec["SurfAirTemp_A"]), "D": float(rec["SurfAirTemp_D"])}
sample = {}
for ym in ["200209", "201007", "202007", "202610"]:
    if ym in files:
        comb, ma, md, na, nd, nlat, nlon = airs_mean(files[ym])
        key = f"{ym[:4]}-{ym[4:]}"
        sample[key] = {
            "combined": comb, "A": ma, "D": md, "nA": na, "nD": nd, "nlat": nlat, "nlon": nlon,
            "ua": ua_airs.get(key),
            "abs_diff_combined": abs(comb - ua_airs[key]["combined"]) if key in ua_airs else None,
        }
out["airs_sample"] = sample
print(" ", sample, flush=True)

(OUT / "spotcheck3_results.json").write_text(json.dumps(out, default=str, indent=2))
print("WROTE spotcheck3_results.json")
