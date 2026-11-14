#!/usr/bin/env python3
"""Rerun NaN-broken comparisons (GLDAS, IMERG, GPCC, CHIRPS, GRACE, HadCRUT, Berkeley, AIRS)."""
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
    fills = [-9999.0, -999.0, -9.99e8, 9.99999987e14, 1e15, -9999.9]
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
    n_overlap = len(keys)
    n_ok = len(diffs)
    n_nan = n_overlap - n_ok
    if not diffs:
        return {"n_overlap": n_overlap, "n_finite": 0, "n_nan": n_nan, "max_abs": None}
    mx, k, av, bv = max(diffs, key=lambda t: t[0])
    return {"n_overlap": n_overlap, "n_finite": n_ok, "n_nan": n_nan, "max_abs": float(mx), "at": k, "a": av, "b": bv}

def parse_times(var):
    vals = np.array(var[:])
    units = getattr(var, "units", None)
    calendar = getattr(var, "calendar", "standard")
    if units and "year" in str(units).lower():
        # Berkeley "year A.D." mid-month
        out = []
        for t in np.atleast_1d(vals).astype(float):
            y = int(np.floor(t))
            m = int(np.round((t - y) * 12 + 0.5))
            if m == 0:
                y, m = y - 1, 12
            if m == 13:
                y, m = y + 1, 1
            out.append(date(y, m, 1))
        return out
    dates = num2date(vals, units, calendar=calendar)
    out = []
    for d in np.atleast_1d(dates):
        out.append(date(int(d.year), int(d.month), 1))
    return out

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

def gesdisc_csv(path, col):
    rows = []
    with open(path, newline="") as f:
        for rec in csv.DictReader(f):
            rows.append((int(rec["year"]), int(rec["month"]), float(rec[col])))
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

out = {}

# ---- GLDAS Tair ----
print("GLDAS 2.1", flush=True)
def gldas_series(folder, ua_csv):
    files = {}
    for p in Path(folder).glob("*"):
        m = re.search(r"A(\d{6})", p.name)
        if m:
            files[m.group(1)] = p
    comp = []
    n0 = None
    for yyyymm, p in sorted(files.items()):
        ds = Dataset(str(p))
        try:
            lat = np.array(find_var(ds, ["lat"])[:], dtype=float)
            lon = np.array(find_var(ds, ["lon"])[:], dtype=float)
            var = find_var(ds, ["Tair_f_inst"])
            mean, n = weighted_mean(lat, lon, var[:], fill=getattr(var, "_FillValue", None))
            if n0 is None:
                n0 = n
            comp.append((int(yyyymm[:4]), int(yyyymm[4:6]), mean))
        finally:
            ds.close()
    ua = gesdisc_csv(ua_csv, "Tair_f_inst")
    return pack(comp, ua, {"n_cells_first": n0})

out["gldas21_Tair"] = gldas_series("$GLOBAL_DATA/gldas21_slim",
    "$UKRAINE_SAMPLES/gldas/gldas21_ukraine_monthly.csv")
print(" ", out["gldas21_Tair"]["monthly"], out["gldas21_Tair"]["annual_12of12"], flush=True)

print("GLDAS 2.0", flush=True)
out["gldas20_Tair"] = gldas_series("$GLOBAL_DATA/gldas20_slim",
    "$UKRAINE_SAMPLES/gldas/gldas20_ukraine_monthly.csv")
print(" ", out["gldas20_Tair"]["monthly"], out["gldas20_Tair"]["annual_12of12"], flush=True)

# confirm Rainf absent
ds = Dataset(next(Path("$GLOBAL_DATA/gldas21_slim").glob("*200001*")))
out["gldas21_vars"] = list(ds.variables)
ds.close()

# ---- IMERG ----
print("IMERG", flush=True)
files = {}
for p in Path("$GLOBAL_DATA/gpm_imerg_slim").glob("*"):
    m = re.search(r"3IMERG\.(\d{8})", p.name)
    if m:
        files[m.group(1)[:6]] = p
comp = []
n0 = units = None
for yyyymm, p in sorted(files.items()):
    ds = Dataset(str(p))
    try:
        lat = np.array(find_var(ds, ["lat"])[:], dtype=float)
        lon = np.array(find_var(ds, ["lon"])[:], dtype=float)
        var = find_var(ds, ["precipitation"])
        mean, n = weighted_mean(lat, lon, var[:], fill=getattr(var, "_FillValue", None))
        if n0 is None:
            n0 = n
            units = str(getattr(var, "units", ""))
        comp.append((int(yyyymm[:4]), int(yyyymm[4:6]), mean))
    finally:
        ds.close()
ua = gesdisc_csv("$UKRAINE_SAMPLES/gpm_imerg/imerg_ukraine_monthly.csv", "precipitation")
out["imerg_precip"] = pack(comp, ua, {"n_cells_first": n0, "units": units})
print(" ", out["imerg_precip"]["monthly"], out["imerg_precip"]["annual_12of12"], flush=True)

# ---- CHIRPS ----
print("CHIRPS", flush=True)
ds = Dataset("$GLOBAL_DATA/chirps_v3/chirps-v3.0.monthly.nc")
try:
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
    comp = [(t.year, t.month, float(means[i])) for i, t in enumerate(times)]
    extra = {
        "units": str(var.units),
        "nlat": int(lat_sub.size), "nlon": int(lon_sub.size),
        "lat_range": [float(lat_sub.min()), float(lat_sub.max())],
        "lon_range": [float(lon_sub.min()), float(lon_sub.max())],
        "n_valid_min": int(nvalid.min()), "n_valid_max": int(nvalid.max()),
        "global_first_last": [times[0].isoformat(), times[-1].isoformat(), len(times)],
    }
finally:
    ds.close()
ua = load_csv("$UKRAINE_SAMPLES/extra/chirps_v3/chirps_v3_ukraine_bbox_monthly.csv", "time", "precip_mm")
out["chirps"] = pack(comp, ua, extra)
# months in UA not in global
ua_m = {f"{y:04d}-{m:02d}" for y, m, v in ua}
gl_m = {f"{y:04d}-{m:02d}" for y, m, v in comp}
out["chirps"]["ua_only"] = sorted(ua_m - gl_m)
out["chirps"]["global_only"] = sorted(gl_m - ua_m)
print(" ", out["chirps"]["monthly"], out["chirps"]["annual_12of12"], "ua_only", out["chirps"]["ua_only"], flush=True)

# ---- GPCC ----
print("GPCC", flush=True)
comp = []
gauge_comp = []
varinfo = None
n0 = None
for fp in sorted(Path("$GLOBAL_DATA/gpcc_v2025_1deg").glob("*.nc.gz")):
    ds = open_nc(fp)
    try:
        lat = np.array(ds.variables["lat"][:], dtype=float)
        lon = np.array(ds.variables["lon"][:], dtype=float)
        pvar = ds.variables["precip"]
        gvar = ds.variables["gauge"] if "gauge" in ds.variables else None
        if varinfo is None:
            varinfo = {
                "precip_units": str(getattr(pvar, "units", "")),
                "gauge_units": str(getattr(gvar, "units", "")) if gvar is not None else None,
                "vars": list(ds.variables),
            }
        times = parse_times(ds.variables["time"])
        pdata = pvar[:]
        gdata = gvar[:] if gvar is not None else None
        for i, t in enumerate(times):
            mean, n = weighted_mean(lat, lon, pdata[i], fill=getattr(pvar, "_FillValue", None))
            if n0 is None:
                n0 = n
            comp.append((t.year, t.month, mean))
            if gdata is not None:
                gm, gn = weighted_mean(lat, lon, gdata[i], fill=getattr(gvar, "_FillValue", None))
                gauge_comp.append((t.year, t.month, gm, gn))
    finally:
        close_nc(ds)
ua = load_csv("$UKRAINE_SAMPLES/extra/gpcc/gpcc_v2025_1deg_ukraine_bbox_monthly.csv", "time", "precip_mm")
out["gpcc"] = pack(comp, ua, {"varinfo": varinfo, "n_cells_first": n0,
                               "gauge_first_last": [
                                   {"date": f"{gauge_comp[0][0]:04d}-{gauge_comp[0][1]:02d}", "mean": gauge_comp[0][2]},
                                   {"date": f"{gauge_comp[-1][0]:04d}-{gauge_comp[-1][1]:02d}", "mean": gauge_comp[-1][2]},
                               ] if gauge_comp else None})
print(" ", out["gpcc"]["monthly"], out["gpcc"]["annual_12of12"], varinfo, flush=True)

# ---- GRACE ----
print("GRACE", flush=True)
R = 6371000.0
ds = Dataset("$GLOBAL_DATA/grace/GRCTellus.JPL.200204_202609.GLO.RL06.3M.MSCNv04CRI.nc")
try:
    lon = np.array(ds.variables["lon"][:], dtype=float)
    lat = np.array(ds.variables["lat"][:], dtype=float)
    lon_b = np.array(ds.variables["lon_bounds"][:], dtype=float)
    lat_b = np.array(ds.variables["lat_bounds"][:], dtype=float)
    land = np.array(ds.variables["land_mask"][:], dtype=float)
    scale = np.array(ds.variables["scale_factor"][:], dtype=float)
    lon_ix = np.where((lon >= BBOX["lon_min"]) & (lon <= BBOX["lon_max"]))[0]
    lat_ix = np.where((lat >= BBOX["lat_min"]) & (lat <= BBOX["lat_max"]))[0]
    slat = slice(int(lat_ix[0]), int(lat_ix[-1]) + 1)
    slon = slice(int(lon_ix[0]), int(lon_ix[-1]) + 1)
    lat_b_sub = lat_b[slat]
    lon_b_sub = lon_b[slon]
    land_sub = land[slat, slon]
    scale_sub = scale[slat, slon]
    dsin = np.sin(np.radians(np.maximum(lat_b_sub[:, 0], lat_b_sub[:, 1]))) - np.sin(
        np.radians(np.minimum(lat_b_sub[:, 0], lat_b_sub[:, 1]))
    )
    dlon = np.radians(np.abs(lon_b_sub[:, 1] - lon_b_sub[:, 0]))
    area = (R ** 2) * dsin[:, None] * dlon[None, :]
    cell_ok = (land_sub == 1) & np.isfinite(scale_sub) & (scale_sub != -99999)
    lwe = np.array(ds.variables["lwe_thickness"][:, slat, slon], dtype=float)
    lwe = np.where((lwe == -99999.0) | ~np.isfinite(lwe), np.nan, lwe)
    tvar = ds.variables["time"]
    t_dates = num2date(np.array(tvar[:]), tvar.units, getattr(tvar, "calendar", "standard"))
    uns, scl = {}, {}
    for t, d in enumerate(t_dates):
        field = lwe[t]
        valid = cell_ok & np.isfinite(field)
        w = np.where(valid, area, 0.0)
        wsum = float(w.sum())
        key = date(int(d.year), int(d.month), int(d.day)).isoformat()
        uns[key] = float(np.nansum(field * w) / wsum) if wsum else float("nan")
        scl[key] = float(np.nansum(field * scale_sub * w) / wsum) if wsum else float("nan")
    # pixel vs subset
    sub = Dataset("$UKRAINE_SAMPLES/grace/GRCTellus.JPL.200204_202609.GLO.RL06.3M.MSCNv04CRI_ukraine_bbox.nc")
    lwe2 = np.array(sub.variables["lwe_thickness"][:], dtype=float)
    pix = {}
    for idx in [0, lwe.shape[0] // 2, lwe.shape[0] - 1]:
        a = np.where((lwe[idx] == -99999) | ~np.isfinite(lwe[idx]), np.nan, lwe[idx])
        b = np.where((lwe2[idx] == -99999) | ~np.isfinite(lwe2[idx]), np.nan, lwe2[idx])
        both = np.isfinite(a) & np.isfinite(b)
        pix[int(idx)] = {"max_abs": float(np.max(np.abs(a[both] - b[both]))) if both.any() else None,
                         "n": int(both.sum()), "shapes": [list(a.shape), list(b.shape)]}
    sub.close()
    doi = None
    for a in ds.ncattrs():
        if "doi" in a.lower():
            doi = {a: ds.getncattr(a)}
            break
finally:
    ds.close()
ua_rows = list(csv.DictReader(open("$UKRAINE_SAMPLES/grace/ukraine_tws_monthly.csv")))
ua_uns = {r["time_center"][:10]: float(r["lwe_thickness_unscaled_cm"]) for r in ua_rows}
ua_scl = {r["time_center"][:10]: float(r["lwe_thickness_cm"]) for r in ua_rows}
g_pairs = [(int(r["year"]), int(r["month"]), uns[r["time_center"][:10]]) for r in ua_rows if r["time_center"][:10] in uns]
ua_pairs = [(int(r["year"]), int(r["month"]), float(r["lwe_thickness_unscaled_cm"])) for r in ua_rows]
out["grace"] = {
    "monthly_unscaled": max_abs_diff(uns, ua_uns),
    "monthly_scaled": max_abs_diff(scl, ua_scl),
    "annual_unscaled_12of12": max_abs_diff(annual_from_monthly(g_pairs), annual_from_monthly(ua_pairs)),
    "n_global": len(uns), "n_ua": len(ua_uns),
    "pixel_vs_subset": pix,
    "doi_attr": doi,
    "n_land_ok": int(cell_ok.sum()),
}
print(" ", out["grace"], flush=True)

# ---- HadCRUT overlap-area ----
print("HadCRUT", flush=True)
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

ds = Dataset("$GLOBAL_DATA/hadcrut5/HadCRUT.5.2.0.0.analysis.anomalies.ensemble_mean.nc")
try:
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
finally:
    ds.close()
ua = load_csv("$UKRAINE_SAMPLES/extra/hadcrut5/hadcrut5_ukraine_bbox_monthly.csv", "time", "tas_anomaly_C")
out["hadcrut"] = pack(comp, ua, {"n_overlap_cells": len(cells)})
print(" ", out["hadcrut"]["monthly"], "cells", len(cells), flush=True)

# ---- GISTEMP ----
print("GISTEMP", flush=True)
ds = open_nc("$GLOBAL_DATA/gistemp/gistemp1200_GHCNv4_ERSSTv5.nc.gz")
try:
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
finally:
    close_nc(ds)
ua = load_csv("$UKRAINE_SAMPLES/extra/gistemp/gistemp_ukraine_bbox_monthly.csv", "time", "tas_anomaly_C")
out["gistemp"] = pack(comp, ua, {"n_overlap_cells": len(cells)})
print(" ", out["gistemp"]["monthly"], "cells", len(cells), flush=True)

# ---- Berkeley ----
print("Berkeley", flush=True)
ds = Dataset("$GLOBAL_DATA/berkeley_earth/Complete_TAVG_LatLong1.nc")
try:
    lat = np.array(ds.variables["latitude"][:], dtype=float)
    lon = np.array(ds.variables["longitude"][:], dtype=float)
    times = parse_times(ds.variables["time"])
    pvar = ds.variables["temperature"]
    data = np.array(pvar[:], dtype=float)
    if np.ma.isMaskedArray(pvar[:]):
        data = np.array(np.ma.filled(pvar[:], np.nan), dtype=float)
    fill = getattr(pvar, "_FillValue", None)
    comp = []
    n0 = None
    for t, d in enumerate(times):
        mean, n = weighted_mean(lat, lon, data[t], fill=fill)
        if n0 is None:
            n0 = n
        comp.append((d.year, d.month, mean))
finally:
    ds.close()
# discover value column
with open("$UKRAINE_SAMPLES/extra/berkeley_earth/berkeley_earth_ukraine_bbox_monthly.csv") as f:
    cols = [ln for ln in f if not ln.startswith("#")][0].strip().split(",")
print("  berkeley cols", cols, "time", times[0], times[-1], "n", len(times), flush=True)
# prefer anomaly / temperature column
bcol = None
for c in cols:
    if re.search(r"temp|anom|tas|tavg|value", c, re.I) and c not in ("time",):
        bcol = c
        break
if bcol is None:
    bcol = [c for c in cols if c != "time"][0]
ua = load_csv("$UKRAINE_SAMPLES/extra/berkeley_earth/berkeley_earth_ukraine_bbox_monthly.csv", "time", bcol)
out["berkeley"] = pack(comp, ua, {"n_cells": n0, "col": bcol, "time_span": [times[0].isoformat(), times[-1].isoformat(), len(times)]})
print(" ", out["berkeley"]["monthly"], flush=True)

# ---- AIRS sample ----
print("AIRS sample", flush=True)
files = {}
for p in Path("$GLOBAL_DATA/airs3stm_slim").glob("AIRS.*"):
    m = re.search(r"AIRS\.(\d{4})\.(\d{2})", p.name)
    if m:
        files[m.group(1) + m.group(2)] = p

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
        return comb, ma, md, na, nd
    finally:
        ds.close()

ua_airs = {}
with open("$UKRAINE_SAMPLES/airs/airs_ukraine_monthly.csv", newline="") as f:
    for rec in csv.DictReader(f):
        ua_airs[rec["date"]] = float(rec["SurfAirTemp"])
sample = {}
for ym in ["200209", "201007", "202007", "202610"]:
    if ym in airs_files:
        comb, ma, md, na, nd = airs_mean(airs_files[ym])
        key = f"{ym[:4]}-{ym[4:]}"
        sample[key] = {"combined": comb, "A": ma, "D": md, "nA": na, "nD": nd,
                       "ua": ua_airs.get(key),
                       "abs_diff": abs(comb - ua_airs[key]) if key in ua_airs else None}
out["airs_sample"] = sample
print(" ", sample, flush=True)

(OUT / "spotcheck2_results.json").write_text(json.dumps(out, default=str, indent=2))
print("WROTE spotcheck2_results.json")
