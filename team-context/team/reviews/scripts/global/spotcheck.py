#!/usr/bin/env python3
"""Inspect global_data slim fetch and spot-check Ukraine bbox cuts vs earlier extracts."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
from netCDF4 import Dataset, num2date

BBOX = dict(lon_min=22.1, lon_max=40.2, lat_min=44.4, lat_max=52.4)
OUT = Path("team-context/team/reviews/global")
OUT.mkdir(parents=True, exist_ok=True)
notes = {}

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_TMP_PATHS = {}


def open_nc(path, mode="r"):
    path = str(path)
    tmp_name = None
    if path.endswith(".gz"):
        # netCDF4 cannot seek a gzip stream; decompress to a temp file
        tmp = tempfile.NamedTemporaryFile(suffix=".nc", delete=False, dir=str(OUT))
        tmp.close()
        with gzip.open(path, "rb") as fsrc, open(tmp.name, "wb") as fdst:
            shutil.copyfileobj(fsrc, fdst, 8 * 1024 * 1024)
        tmp_name = tmp.name
        ds = Dataset(tmp_name, mode)
    else:
        ds = Dataset(path, mode)
    _TMP_PATHS[id(ds)] = tmp_name
    return ds


def close_nc(ds):
    tmp = _TMP_PATHS.pop(id(ds), None)
    ds.close()
    if tmp and os.path.exists(tmp):
        os.unlink(tmp)


def ncattrs(obj):
    out = {}
    for a in obj.ncattrs():
        try:
            v = obj.getncattr(a)
        except Exception:
            continue
        if isinstance(v, (bytes, np.bytes_)):
            v = v.decode("utf-8", "replace")
        if isinstance(v, str) and len(v) > 300:
            v = v[:300] + "..."
        elif isinstance(v, np.ndarray) and v.size > 20:
            v = f"ndarray{v.shape}"
        out[a] = v if not isinstance(v, np.generic) else v.item() if v.ndim == 0 else v.tolist()
    return out


def walk_vars(ds, prefix=""):
    rows = []
    for vn, v in ds.variables.items():
        units = ""
        longn = ""
        try:
            units = str(getattr(v, "units", "") or "")
        except Exception:
            pass
        try:
            longn = str(getattr(v, "long_name", "") or getattr(v, "standard_name", "") or "")
        except Exception:
            pass
        rows.append({
            "name": prefix + vn,
            "shape": tuple(int(x) for x in v.shape),
            "dims": tuple(v.dimensions),
            "dtype": str(v.dtype),
            "units": units,
            "long_name": longn[:120],
        })
    for gn, g in ds.groups.items():
        rows.extend(walk_vars(g, prefix + gn + "/"))
    return rows


def find_var(ds, names):
    if isinstance(names, str):
        names = [names]
    # top-level
    for n in names:
        if n in ds.variables:
            return ds.variables[n]
    # groups, recursive
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


def to_1d(a):
    a = np.array(a)
    if np.ma.isMaskedArray(a):
        a = np.array(a.filled(np.nan) if a.dtype.kind == "f" else a.filled(), dtype=float)
    else:
        a = np.array(a, dtype=float)
    return np.ravel(a)


def months_between(a, b):
    y, m = a.year, a.month
    out = []
    while (y, m) <= (b.year, b.month):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            m, y = 1, y + 1
    return out


def parse_time_vals(var):
    vals = np.array(var[:])
    if np.ma.isMaskedArray(vals):
        vals = np.array(vals.filled(np.nan))
    units = getattr(var, "units", None)
    calendar = getattr(var, "calendar", "standard")
    if units:
        try:
            dates = num2date(vals, units, calendar=calendar)
            out = []
            for d in np.atleast_1d(dates):
                if d is None or (isinstance(d, float) and not np.isfinite(d)):
                    out.append(None)
                else:
                    out.append(date(int(d.year), int(d.month), int(getattr(d, "day", 1))))
            return out
        except Exception as e:
            return f"time-parse-fail: {e} units={units}"
    return vals.tolist()


# ---------------------------------------------------------------------------
# size table
# ---------------------------------------------------------------------------

claimed_files = {
    "grace_data": 46365171,
    "gistemp_dir": 25934827,
    "hadcrut_dir": 33039776,
    "berkeley": 198958040,
    "gpcc": 443882757,
    "merra2_slv": 891108130,
    "merra2_flx": 773787005,
    "gldas20": 3929728082,
    "gldas21": 1581824378,
    "imerg": 2268586131,
    "airs": 241075185,
    "mod13c2": 5771738931,
    "mod11c3": 5238693688,
    "chirps": 8960342547,
}

du = {}
for p in Path("$GLOBAL_DATA").iterdir():
    if p.is_dir():
        r = subprocess.check_output(["du", "-sb", str(p)], text=True).split()[0]
        du[p.name] = int(r)
    else:
        du[p.name] = p.stat().st_size

# file-only sizes (not dir overhead) for claimed comparison
def sum_files(d):
    return sum(f.stat().st_size for f in Path(d).rglob("*") if f.is_file())

file_bytes = {name: sum_files(Path("$GLOBAL_DATA") / name)
              for name in du if (Path("$GLOBAL_DATA") / name).is_dir()}

notes["du_dirs"] = du
notes["file_bytes"] = file_bytes
notes["claimed_total_log"] = sum(claimed_files.values())
notes["on_disk_file_bytes_sum"] = sum(file_bytes.values()) + du.get("README.md", 0)
# df
df = subprocess.check_output(["df", "-B1", "/workspace"], text=True).strip().splitlines()
notes["df"] = df[-1]

# GRACE md5
grace_path = Path("$GLOBAL_DATA/grace/GRCTellus.JPL.200204_202609.GLO.RL06.3M.MSCNv04CRI.nc")
h = hashlib.md5()
with open(grace_path, "rb") as f:
    for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
        h.update(chunk)
grace_md5 = h.hexdigest()
notes["grace_md5"] = grace_md5
notes["grace_md5_ok"] = grace_md5 == "1567b9401ec2a704aab16598fcce5e70"
notes["grace_bytes"] = grace_path.stat().st_size

# inodes
def inode(p):
    st = os.stat(p)
    return {"ino": st.st_ino, "nlink": st.st_nlink, "size": st.st_size}

notes["inodes"] = {
    "gistemp_global": inode("$GLOBAL_DATA/gistemp/gistemp1200_GHCNv4_ERSSTv5.nc.gz"),
    "gistemp_ua": inode("$UKRAINE_SAMPLES/extra/gistemp/gistemp1200_GHCNv4_ERSSTv5.nc.gz"),
    "hadcrut_global": inode("$GLOBAL_DATA/hadcrut5/HadCRUT.5.2.0.0.analysis.anomalies.ensemble_mean.nc"),
    "hadcrut_ua": inode("$UKRAINE_SAMPLES/extra/hadcrut5/HadCRUT.5.2.0.0.analysis.anomalies.ensemble_mean.nc"),
}

print("SIZES done. claimed_sum", notes["claimed_total_log"], "file_sum", notes["on_disk_file_bytes_sum"],
      "grace_md5_ok", notes["grace_md5_ok"])

# ---------------------------------------------------------------------------
# inspect one file per source
# ---------------------------------------------------------------------------

inspect_targets = {
    "merra2_slv": "$GLOBAL_DATA/merra2_slv_slim/MERRA2_100.tavgM_2d_slv_Nx.198001.nc4.nc4",
    "merra2_flx": "$GLOBAL_DATA/merra2_flx_slim/MERRA2_100.tavgM_2d_flx_Nx.198001.nc4.nc4",
    "gldas20": "$GLOBAL_DATA/gldas20_slim/GLDAS_NOAH025_M.A194801.020.nc4.nc4",
    "gldas21": "$GLOBAL_DATA/gldas21_slim/GLDAS_NOAH025_M.A200001.021.nc4.nc4",
    "imerg": "$GLOBAL_DATA/gpm_imerg_slim/3B-MO.MS.MRG.3IMERG.19980101-S000000-E235959.01.V07B.HDF5.nc4",
    "airs": "$GLOBAL_DATA/airs3stm_slim/AIRS.2002.09.01.L3.RetStd_IR030.v7.0.3.0.G20175163230.hdf.nc4",
    "mod11": "$GLOBAL_DATA/mod11c3_slim/MOD11C3.A2000032.061.2020048181639.nc4",
    "mod13": "$GLOBAL_DATA/mod13c2_slim/MOD13C2.A2000032.061.2020042083108.nc4",
    "grace": str(grace_path),
    "hadcrut": "$GLOBAL_DATA/hadcrut5/HadCRUT.5.2.0.0.analysis.anomalies.ensemble_mean.nc",
    "berkeley": "$GLOBAL_DATA/berkeley_earth/Complete_TAVG_LatLong1.nc",
    "gpcc_1981": "$GLOBAL_DATA/gpcc_v2025_1deg/gpcc_precipitation_analysis_monthly_1981_1985_v2025_100.nc.gz",
    "gistemp": "$GLOBAL_DATA/gistemp/gistemp1200_GHCNv4_ERSSTv5.nc.gz",
    "chirps": "$GLOBAL_DATA/chirps_v3/chirps-v3.0.monthly.nc",
}

# also mid/late merra to confirm 2026 file exists and has same vars
inspect_targets["merra2_slv_202609"] = str(next(Path("$GLOBAL_DATA/merra2_slv_slim").glob("*202609*")))

inspections = {}
for name, path in inspect_targets.items():
    print("INSPECT", name, flush=True)
    info = {"path": path, "bytes": os.path.getsize(path)}
    try:
        ds = open_nc(path)
        info["format"] = getattr(ds, "file_format", "")
        info["groups"] = list(ds.groups)
        info["dims"] = {k: int(v.size) for k, v in ds.dimensions.items()}
        # group dims too
        def gdims(g, prefix=""):
            d = {prefix + k: int(v.size) for k, v in g.dimensions.items()}
            for gn, sg in g.groups.items():
                d.update(gdims(sg, prefix + gn + "/"))
            return d
        info["all_dims"] = gdims(ds)
        attrs = ncattrs(ds)
        keep_keys = []
        for k, v in attrs.items():
            kl = k.lower()
            if any(s in kl for s in [
                "doi", "version", "shortname", "title", "institution", "comment",
                "history", "references", "production", "identifier", "source",
                "conventions", "rangebegin", "rangeend", "time_coverage",
                "months_missing", "summary", "product", "data_source",
            ]):
                keep_keys.append(k)
        info["attrs"] = {k: attrs[k] for k in keep_keys}
        info["vars"] = walk_vars(ds)
        # time coverage if present
        tvar = find_var(ds, ["time", "Time", "T", "date"])
        if tvar is not None and tvar.size < 10000:
            parsed = parse_time_vals(tvar)
            if isinstance(parsed, list) and parsed and isinstance(parsed[0], date):
                info["time_n"] = len(parsed)
                info["time_first"] = parsed[0].isoformat()
                info["time_last"] = parsed[-1].isoformat()
                info["time_unique"] = len({p.isoformat()[:7] for p in parsed if p})
        close_nc(ds)
    except Exception as e:
        info["error"] = f"{type(e).__name__}: {e}"
    inspections[name] = info

notes["inspections"] = inspections
print("INSPECT done")

# CHIRPS time completeness
print("CHIRPS time scan", flush=True)
try:
    ds = open_nc("$GLOBAL_DATA/chirps_v3/chirps-v3.0.monthly.nc")
    # don't load precip
    tnames = [v["name"] for v in walk_vars(ds)]
    notes["chirps_varnames"] = tnames
    notes["chirps_dims"] = {k: int(v.size) for k, v in ds.dimensions.items()}
    notes["chirps_attrs_all_keys"] = list(ncattrs(ds))
    tvar = find_var(ds, ["time", "T"])
    lats = find_var(ds, ["lat", "latitude", "y"])
    lons = find_var(ds, ["lon", "longitude", "x"])
    if tvar is not None:
        parsed = parse_time_vals(tvar)
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], date):
            months = [f"{p.year:04d}-{p.month:02d}" for p in parsed]
            exp = months_between(parsed[0], parsed[-1])
            miss = [m for m in exp if m not in set(months)]
            dups = [m for m, c in Counter(months).items() if c > 1]
            notes["chirps_time"] = {
                "n": len(months), "first": months[0], "last": months[-1],
                "expected": len(exp), "missing": miss, "dups": dups,
            }
    if lats is not None:
        la = np.array(lats[:], dtype=float)
        lo = np.array(lons[:], dtype=float)
        notes["chirps_lat_range"] = [float(np.nanmin(la)), float(np.nanmax(la)), int(la.size)]
        notes["chirps_lon_range"] = [float(np.nanmin(lo)), float(np.nanmax(lo)), int(lo.size)]
        # resolution
        if la.size > 1:
            notes["chirps_dlat"] = float(np.median(np.abs(np.diff(la))))
        if lo.size > 1:
            notes["chirps_dlon"] = float(np.median(np.abs(np.diff(lo))))
    close_nc(ds)
except Exception as e:
    notes["chirps_time_error"] = f"{type(e).__name__}: {e}"

# GPCC time from all chunks (open each, record time, vars)
print("GPCC scan", flush=True)
gpcc_months = []
gpcc_vars_by_file = {}
gpcc_dir = Path("$GLOBAL_DATA/gpcc_v2025_1deg")
for fp in sorted(gpcc_dir.glob("*.nc.gz")):
    ds = open_nc(fp)
    vnames = [v["name"] for v in walk_vars(ds)]
    gpcc_vars_by_file[fp.name] = vnames
    tvar = find_var(ds, ["time", "Time"])
    parsed = parse_time_vals(tvar) if tvar is not None else []
    if isinstance(parsed, list) and parsed and isinstance(parsed[0], date):
        for p in parsed:
            gpcc_months.append(f"{p.year:04d}-{p.month:02d}")
    close_nc(ds)
exp = months_between(date(int(gpcc_months[0][:4]), int(gpcc_months[0][5:7]), 1),
                     date(int(gpcc_months[-1][:4]), int(gpcc_months[-1][5:7]), 1))
notes["gpcc_time"] = {
    "n": len(gpcc_months), "unique": len(set(gpcc_months)),
    "first": gpcc_months[0], "last": gpcc_months[-1],
    "expected": len(exp),
    "missing": [m for m in exp if m not in set(gpcc_months)],
    "dups": [m for m, c in Counter(gpcc_months).items() if c > 1],
    "vars_first": gpcc_vars_by_file[sorted(gpcc_vars_by_file)[0]],
    "vars_last": gpcc_vars_by_file[sorted(gpcc_vars_by_file)[-1]],
    "all_same_vars": len(set(tuple(v) for v in gpcc_vars_by_file.values())) == 1,
}

# GRACE / HadCRUT / Berkeley / GISTEMP time already in inspections; add coverage field names
def varnames(insp):
    return [v["name"] for v in insp.get("vars", [])]

notes["coverage_fields"] = {
    "grace": [n for n in varnames(inspections.get("grace", {})) if re.search(r"land|mask|scale|mascon", n, re.I)],
    "gistemp": varnames(inspections.get("gistemp", {})),
    "hadcrut": varnames(inspections.get("hadcrut", {})),
    "berkeley": varnames(inspections.get("berkeley", {})),
}

# save intermediate inspections so we don't lose them if spotcheck fails
(OUT / "inspect_partial.json").write_text(json.dumps(notes, default=str, indent=2))
print("Wrote inspect_partial.json", flush=True)

# ---------------------------------------------------------------------------
# weighting helpers (match earlier extracts)
# ---------------------------------------------------------------------------

FRLAND = None

def load_frland():
    global FRLAND
    if FRLAND is None:
        z = np.load("$UKRAINE_SAMPLES/merra2/frland.npz")
        fr = np.asarray(z["FRLAND"], float)
        if fr.ndim == 3:
            fr = fr[0]
        FRLAND = (np.asarray(z["lat"], float), np.asarray(z["lon"], float), fr)
    return FRLAND


def frland_on_grid(lat, lon, thresh=0.5):
    frat, fron, fr = load_frland()
    lat = np.asarray(lat, dtype=float).reshape(-1)
    lon = np.asarray(lon, dtype=float).reshape(-1)
    # handle 0-360 lon if needed
    lon_use = lon.copy()
    if lon_use.min() >= 0 and fron.min() < 0:
        lon_use = np.where(lon_use > 180, lon_use - 360, lon_use)
    i = np.abs(frat[:, None] - lat[None, :]).argmin(axis=0)
    j = np.abs(fron[:, None] - lon_use[None, :]).argmin(axis=0)
    return fr[np.ix_(i, j)] >= thresh


def wrap_lon(lon, want_min=-180):
    lon = np.asarray(lon, dtype=float)
    if want_min == -180:
        return np.where(lon > 180, lon - 360, lon)
    return np.where(lon < 0, lon + 360, lon)


def weighted_mean(lat, lon, field, land_mask=None, fill=None):
    """Cos-lat mean of cell centres inside bbox. Matches download_gesdisc_ukraine.py."""
    lat = np.asarray(lat, dtype=float).reshape(-1)
    lon = np.asarray(lon, dtype=float).reshape(-1)
    # prefer -180..180 for this bbox
    lon = wrap_lon(lon, -180)
    data = np.array(field, dtype=float)
    if np.ma.isMaskedArray(field):
        data = np.array(field.filled(np.nan), dtype=float)
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
    if land_mask is not None:
        lm = np.asarray(land_mask)
        if lm.shape == mask.shape:
            mask = mask & lm
        elif lm.T.shape == mask.shape:
            mask = mask & lm.T
    fills = [-9999.0, -999.0, -9.99e8, 9.99999987e14, 1e15]
    if fill is not None and np.isfinite(fill):
        fills.append(float(fill))
    for fv in fills:
        mask &= data != fv
    mask &= np.abs(data) < 1e12
    w = np.cos(np.deg2rad(lat2d))
    w = np.where(mask, w, 0.0)
    n = int(mask.sum())
    if n == 0 or float(w.sum()) == 0:
        return float("nan"), 0
    return float((data * w).sum() / w.sum()), n


def annual_from_monthly(pairs, value_key="value"):
    """pairs: list of (year, month, value). Return dict year -> mean for 12/12 years."""
    by = defaultdict(dict)
    for y, m, v in pairs:
        if v is not None and np.isfinite(v):
            by[int(y)][int(m)] = float(v)
    out = {}
    for y, md in by.items():
        if len(md) == 12:
            out[y] = float(np.mean([md[m] for m in range(1, 13)]))
    return out


def max_abs_diff(a, b):
    keys = sorted(set(a) & set(b))
    if not keys:
        return {"n": 0, "max_abs": None}
    diffs = [abs(a[k] - b[k]) for k in keys]
    i = int(np.argmax(diffs))
    return {"n": len(keys), "max_abs": float(max(diffs)), "at": keys[i],
            "a": a[keys[i]], "b": b[keys[i]]}


def load_csv_series(path, date_col, val_col, comment="#"):
    rows = []
    with open(path, newline="") as f:
        # skip comments
        pos = 0
        lines = []
        for line in f:
            if line.startswith(comment):
                continue
            lines.append(line)
        rdr = csv.DictReader(lines)
        for rec in rdr:
            d = rec[date_col]
            if re.fullmatch(r"\d{4}-\d{2}", d):
                y, m = int(d[:4]), int(d[5:7])
            elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
                y, m = int(d[:4]), int(d[5:7])
            else:
                continue
            try:
                v = float(rec[val_col])
            except (TypeError, ValueError):
                v = float("nan")
            rows.append((y, m, v, f"{y:04d}-{m:02d}"))
    return rows


comparisons = {}

# ======================== MERRA-2 T2M ========================
print("SPOT merra2 T2M", flush=True)

def merra_path(kind, yyyymm):
    folder = Path(f"$GLOBAL_DATA/merra2_{kind}_slim")
    hits = list(folder.glob(f"*{yyyymm}*"))
    if not hits:
        raise FileNotFoundError(f"{kind} {yyyymm}")
    return hits[0]


def series_from_gesdisc_csv(path, val_col):
    recs = []
    with open(path, newline="") as f:
        rdr = csv.DictReader(f)
        for rec in rdr:
            recs.append((int(rec["year"]), int(rec["month"]), float(rec[val_col])))
    return recs


def process_monthly_files(file_dates, opener_mean_fn):
    """file_dates: list of (yyyymm or date-str, path or key). opener_mean_fn(key)-> (val, n) or dict."""
    out = []
    for key in file_dates:
        y, m, val = opener_mean_fn(key)
        out.append((y, m, val))
    return out


# pre-index merra slv files
merra_slv = {}
for p in Path("$GLOBAL_DATA/merra2_slv_slim").glob("*"):
    m = re.search(r"(\d{6})", p.name)
    if m:
        merra_slv[m.group(1)] = p

def merra_t2m_mean(yyyymm, land=False):
    ds = Dataset(str(merra_slv[yyyymm]))
    try:
        lat = np.array(find_var(ds, ["lat", "latitude"])[:], dtype=float)
        lon = np.array(find_var(ds, ["lon", "longitude"])[:], dtype=float)
        var = find_var(ds, ["T2M"])
        fill = getattr(var, "_FillValue", None) or getattr(var, "missing_value", None)
        data = var[:]
        lm = frland_on_grid(lat, lon) if land else None
        mean, n = weighted_mean(lat, lon, data, land_mask=lm, fill=fill)
        return int(yyyymm[:4]), int(yyyymm[4:6]), mean, n
    finally:
        ds.close()

# compute all months (needed for annual); T2M unmasked (primary bbox)
merra_comp = []
merra_n_ref = None
for yyyymm in sorted(merra_slv):
    y, m, mean, n = merra_t2m_mean(yyyymm, land=False)
    merra_comp.append((y, m, mean))
    if merra_n_ref is None:
        merra_n_ref = n
ua_merra = series_from_gesdisc_csv("$UKRAINE_SAMPLES/merra2/merra2_slv_ukraine_monthly.csv", "T2M")
merra_a = {f"{y:04d}-{m:02d}": v for y, m, v in merra_comp}
merra_b = {f"{y:04d}-{m:02d}": v for y, m, v in ua_merra}
ann_a = annual_from_monthly(merra_comp)
ann_b = annual_from_monthly(ua_merra)
# also a few months land
land_sample = {}
for ym in ["198001", "200007", "202107", "202609"]:
    y, m, mean, n = merra_t2m_mean(ym, land=True)
    land_sample[f"{y:04d}-{m:02d}"] = {"global_land": mean, "n": n}
ua_land = {f"{y:04d}-{m:02d}": v for y, m, v in series_from_gesdisc_csv(
    "$UKRAINE_SAMPLES/merra2/merra2_slv_ukraine_monthly.csv", "T2M_land")}
for k in land_sample:
    land_sample[k]["ua_land"] = ua_land.get(k)
    land_sample[k]["abs_diff"] = abs(land_sample[k]["global_land"] - ua_land[k]) if k in ua_land else None

comparisons["merra2_T2M"] = {
    "monthly": max_abs_diff(merra_a, merra_b),
    "annual_12of12": max_abs_diff(ann_a, ann_b),
    "n_months_global": len(merra_a),
    "n_months_ua": len(merra_b),
    "n_cells_first": merra_n_ref,
    "sample_months": {ym: {"global": merra_a.get(f"{ym[:4]}-{ym[4:]}"), "ua": merra_b.get(f"{ym[:4]}-{ym[4:]}")}
                      for ym in ["1980-01", "2000-07", "2021-07", "2026-09"]},
    "land_sample": land_sample,
}
print("  merra monthly", comparisons["merra2_T2M"]["monthly"], "annual", comparisons["merra2_T2M"]["annual_12of12"], flush=True)

# ======================== GLDAS Tair 2.1 (and a few 2.0) ========================
print("SPOT gldas Tair", flush=True)

def index_gldas(folder):
    d = {}
    for p in Path(folder).glob("*"):
        m = re.search(r"A(\d{6})", p.name)
        if m:
            d[m.group(1)] = p
    return d

g21 = index_gldas("$GLOBAL_DATA/gldas21_slim")
g20 = index_gldas("$GLOBAL_DATA/gldas20_slim")

def gldas_tair(path, land=False):
    ds = Dataset(str(path))
    try:
        lat = np.array(find_var(ds, ["lat", "latitude"])[:], dtype=float)
        lon = np.array(find_var(ds, ["lon", "longitude"])[:], dtype=float)
        var = find_var(ds, ["Tair_f_inst", "Tair"])
        fill = getattr(var, "_FillValue", None) or getattr(var, "missing_value", None)
        lm = frland_on_grid(lat, lon) if land else None
        mean, n = weighted_mean(lat, lon, var[:], land_mask=lm, fill=fill)
        return mean, n
    finally:
        ds.close()

g21_comp = []
g21_n = None
for yyyymm, p in sorted(g21.items()):
    mean, n = gldas_tair(p, land=False)
    g21_comp.append((int(yyyymm[:4]), int(yyyymm[4:6]), mean))
    if g21_n is None:
        g21_n = n
ua_g21 = series_from_gesdisc_csv("$UKRAINE_SAMPLES/gldas/gldas21_ukraine_monthly.csv", "Tair_f_inst")
comparisons["gldas21_Tair"] = {
    "monthly": max_abs_diff({f"{y:04d}-{m:02d}": v for y, m, v in g21_comp},
                            {f"{y:04d}-{m:02d}": v for y, m, v in ua_g21}),
    "annual_12of12": max_abs_diff(annual_from_monthly(g21_comp), annual_from_monthly(ua_g21)),
    "n_months_global": len(g21_comp),
    "n_months_ua": len(ua_g21),
    "n_cells_first": g21_n,
}
print("  gldas21", comparisons["gldas21_Tair"]["monthly"], comparisons["gldas21_Tair"]["annual_12of12"], flush=True)

# GLDAS 2.0: a few months + annual would need 804 files; do all since they're similar size
g20_comp = []
for yyyymm, p in sorted(g20.items()):
    mean, n = gldas_tair(p, land=False)
    g20_comp.append((int(yyyymm[:4]), int(yyyymm[4:6]), mean))
ua_g20 = series_from_gesdisc_csv("$UKRAINE_SAMPLES/gldas/gldas20_ukraine_monthly.csv", "Tair_f_inst")
comparisons["gldas20_Tair"] = {
    "monthly": max_abs_diff({f"{y:04d}-{m:02d}": v for y, m, v in g20_comp},
                            {f"{y:04d}-{m:02d}": v for y, m, v in ua_g20}),
    "annual_12of12": max_abs_diff(annual_from_monthly(g20_comp), annual_from_monthly(ua_g20)),
    "n_months_global": len(g20_comp),
    "n_months_ua": len(ua_g20),
}
print("  gldas20", comparisons["gldas20_Tair"]["monthly"], comparisons["gldas20_Tair"]["annual_12of12"], flush=True)

# ======================== IMERG precipitation ========================
print("SPOT imerg", flush=True)
imerg_files = {}
for p in Path("$GLOBAL_DATA/gpm_imerg_slim").glob("*"):
    m = re.search(r"3IMERG\.(\d{8})", p.name)
    if m:
        imerg_files[m.group(1)[:6]] = p

def imerg_mean(path):
    ds = Dataset(str(path))
    try:
        lat = np.array(find_var(ds, ["lat", "latitude", "Grid/lat"])[:], dtype=float)
        lon = np.array(find_var(ds, ["lon", "longitude", "Grid/lon"])[:], dtype=float)
        # may be in group
        var = find_var(ds, ["precipitation"])
        fill = getattr(var, "_FillValue", None) or getattr(var, "missing_value", None)
        data = var[:]
        mean, n = weighted_mean(lat, lon, data, fill=fill)
        return mean, n, str(getattr(var, "units", ""))
    finally:
        ds.close()

imerg_comp = []
imerg_units = None
imerg_n = None
for yyyymm, p in sorted(imerg_files.items()):
    mean, n, units = imerg_mean(p)
    imerg_comp.append((int(yyyymm[:4]), int(yyyymm[4:6]), mean))
    imerg_units = units
    if imerg_n is None:
        imerg_n = n
ua_imerg = series_from_gesdisc_csv("$UKRAINE_SAMPLES/gpm_imerg/imerg_ukraine_monthly.csv", "precipitation")
# versions in filenames
imerg_vers = Counter()
for p in imerg_files.values():
    m = re.search(r"(V07[A-Z])", p.name)
    if m:
        imerg_vers[m.group(1)] += 1
ua_imerg_vers = Counter()
with open("$UKRAINE_SAMPLES/gpm_imerg/imerg_ukraine_monthly.csv") as f:
    for line in f:
        m = re.search(r"(V07[A-Z])", line)
        if m:
            ua_imerg_vers[m.group(1)] += 1
comparisons["imerg_precip"] = {
    "monthly": max_abs_diff({f"{y:04d}-{m:02d}": v for y, m, v in imerg_comp},
                            {f"{y:04d}-{m:02d}": v for y, m, v in ua_imerg}),
    "annual_12of12": max_abs_diff(annual_from_monthly(imerg_comp), annual_from_monthly(ua_imerg)),
    "n_months_global": len(imerg_comp),
    "n_months_ua": len(ua_imerg),
    "units": imerg_units,
    "n_cells_first": imerg_n,
    "global_versions": dict(imerg_vers),
    "ua_versions": dict(ua_imerg_vers),
    # overlap starts 2000 for UA
    "global_range": (f"{imerg_comp[0][0]:04d}-{imerg_comp[0][1]:02d}",
                     f"{imerg_comp[-1][0]:04d}-{imerg_comp[-1][1]:02d}"),
}
print("  imerg", comparisons["imerg_precip"]["monthly"], comparisons["imerg_precip"]["annual_12of12"],
      "units", imerg_units, "vers", imerg_vers, flush=True)

# ======================== MODIS LST Day ========================
print("SPOT modis LST_Day", flush=True)
# CMG indices used by the Ukraine extract
Y0, Y1, X0, X1 = 752, 912, 4042, 4404

def find_modis_var(ds, names):
    v = find_var(ds, names)
    return v

def modis_lst_day_mean(path):
    ds = Dataset(str(path))
    try:
        var = find_var(ds, ["LST_Day_CMG"])
        var.set_auto_maskandscale(False)
        raw = np.array(var[:])
        raw = np.squeeze(raw)
        # full CMG or already? should be 3600x7200
        if raw.ndim != 2:
            raise ValueError(f"unexpected LST shape {raw.shape}")
        if raw.shape == (3600, 7200):
            win = raw[Y0:Y1 + 1, X0:X1 + 1]
        elif raw.shape == (161, 363):
            win = raw
        else:
            # maybe (time, y, x)
            raise ValueError(f"unexpected LST shape {raw.shape}")
        valid = (win != 0) & (win >= 7500)
        n = int(valid.sum())
        if n == 0:
            return float("nan"), 0
        vals = win[valid].astype(np.float64) * 0.02
        return float(vals.mean()), n
    finally:
        ds.close()


def month_from_modis_name(name):
    m = re.search(r"\.A(\d{4})(\d{3})\.", name)
    d = date(int(m.group(1)), 1, 1) + timedelta(days=int(m.group(2)) - 1)
    return d.year, d.month

mod11_comp = []
mod11_n0 = None
for p in sorted(Path("$GLOBAL_DATA/mod11c3_slim").glob("MOD11C3.*")):
    y, m = month_from_modis_name(p.name)
    mean, n = modis_lst_day_mean(p)
    mod11_comp.append((y, m, mean))
    if mod11_n0 is None:
        mod11_n0 = n

ua_mod11 = []
with open("$UKRAINE_SAMPLES/modis_lpdaac/MOD11C3_ukraine_monthly.csv", newline="") as f:
    rdr = csv.DictReader(f)
    for rec in rdr:
        y, m = rec["month"].split("-")
        ua_mod11.append((int(y), int(m), float(rec["LST_Day_K"]) if rec["LST_Day_K"] else float("nan")))

# pixel compare sample months
pixel_diffs = {}
samples = {
    "2000-02": "$UKRAINE_SAMPLES/modis_lpdaac/samples/MOD11C3_2000-02_MOD11C3.A2000032.061.2020048181639.dap.nc4",
    "2012-07": "$UKRAINE_SAMPLES/modis_lpdaac/samples/MOD11C3_2012-07_MOD11C3.A2012183.061.2021226214145.dap.nc4",
    "2020-07": "$UKRAINE_SAMPLES/modis_lpdaac/samples/MOD11C3_2020-07_MOD11C3.A2020183.061.2021013113245.dap.nc4",
    "2025-07": "$UKRAINE_SAMPLES/modis_lpdaac/samples/MOD11C3_2025-07_MOD11C3.A2025182.061.2025213154157.dap.nc4",
}

def raw_window_from_sample(path):
    ds = Dataset(str(path))
    try:
        var = find_var(ds, ["LST_Day_CMG"])
        var.set_auto_maskandscale(False)
        raw = np.squeeze(np.array(var[:]))
        return raw
    finally:
        ds.close()

def raw_window_from_global(stem_month_doy):
    # stem like A2000032
    hits = list(Path("$GLOBAL_DATA/mod11c3_slim").glob(f"*{stem_month_doy}*"))
    ds = Dataset(str(hits[0]))
    try:
        var = find_var(ds, ["LST_Day_CMG"])
        var.set_auto_maskandscale(False)
        raw = np.squeeze(np.array(var[:]))
        if raw.shape == (3600, 7200):
            return raw[Y0:Y1 + 1, X0:X1 + 1]
        return raw
    finally:
        ds.close()

for label, spath in samples.items():
    if not os.path.exists(spath):
        pixel_diffs[label] = {"error": "sample missing"}
        continue
    a = raw_window_from_sample(spath)
    # extract Ayyyyddd from sample path
    m = re.search(r"\.(A\d{7})\.", Path(spath).name)
    b = raw_window_from_global(m.group(1))
    if a.shape != b.shape:
        pixel_diffs[label] = {"error": f"shape {a.shape} vs {b.shape}"}
        continue
    d = np.abs(a.astype(np.int64) - b.astype(np.int64))
    pixel_diffs[label] = {
        "shape": list(a.shape),
        "max_abs_raw": int(d.max()),
        "n_diff": int((d > 0).sum()),
        "n": int(d.size),
    }

comparisons["mod11c3_LST_Day"] = {
    "monthly": max_abs_diff({f"{y:04d}-{m:02d}": v for y, m, v in mod11_comp},
                            {f"{y:04d}-{m:02d}": v for y, m, v in ua_mod11}),
    "annual_12of12": max_abs_diff(annual_from_monthly(mod11_comp), annual_from_monthly(ua_mod11)),
    "n_months_global": len(mod11_comp),
    "n_months_ua": len(ua_mod11),
    "n_valid_first": mod11_n0,
    "pixel_sample": pixel_diffs,
    "note": "Ukraine extract uses unweighted mean of valid 0.05deg pixels in DAP4 window [752:912, 4042:4404], scale 0.02, fill 0 / min 7500; no QC.",
}
print("  modis", comparisons["mod11c3_LST_Day"]["monthly"], comparisons["mod11c3_LST_Day"]["annual_12of12"],
      "pixels", pixel_diffs, flush=True)

# ======================== CHIRPS ========================
print("SPOT chirps", flush=True)
ds = Dataset("$GLOBAL_DATA/chirps_v3/chirps-v3.0.monthly.nc")
try:
    latv = find_var(ds, ["lat", "latitude", "y"])
    lonv = find_var(ds, ["lon", "longitude", "x"])
    pv = find_var(ds, ["precip", "precipitation", "pr", "precip_mm", "chirps"])
    tvar = find_var(ds, ["time", "T"])
    lat = np.array(latv[:], dtype=float)
    lon = np.array(lonv[:], dtype=float)
    times = parse_time_vals(tvar)
    # centres in bbox
    lat_ix = np.where((lat >= BBOX["lat_min"]) & (lat <= BBOX["lat_max"]))[0]
    lon_ix = np.where((lon >= BBOX["lon_min"]) & (lon <= BBOX["lon_max"]))[0]
    slat = slice(int(lat_ix.min()), int(lat_ix.max()) + 1)
    slon = slice(int(lon_ix.min()), int(lon_ix.max()) + 1)
    lat_sub = lat[slat]
    lon_sub = lon[slon]
    # read only the window (all times)
    data = np.array(pv[:, slat, slon], dtype=np.float64)
    fill = getattr(pv, "_FillValue", None) or getattr(pv, "missing_value", None)
    units = str(getattr(pv, "units", ""))
    varname = pv.name
    if fill is not None and np.isfinite(fill):
        data = np.where(data == float(fill), np.nan, data)
    data = np.where(data < -9000, np.nan, data)
    wlat = np.cos(np.deg2rad(lat_sub)).reshape(1, -1, 1)
    w = np.broadcast_to(wlat, data.shape).copy()
    w[np.isnan(data)] = 0
    num = np.nansum(np.nan_to_num(data) * w, axis=(1, 2))
    den = w.sum(axis=(1, 2))
    nvalid = np.isfinite(data).sum(axis=(1, 2))
    means = np.where(den > 0, num / den, np.nan)
    chirps_comp = []
    for i, t in enumerate(times):
        chirps_comp.append((t.year, t.month, float(means[i]), int(nvalid[i])))
    notes["chirps_slice"] = {
        "var": varname, "units": units,
        "nlat": int(lat_sub.size), "nlon": int(lon_sub.size),
        "lat_min": float(lat_sub.min()), "lat_max": float(lat_sub.max()),
        "lon_min": float(lon_sub.min()), "lon_max": float(lon_sub.max()),
        "shape_window": list(data.shape),
        "n_valid_minmax": [int(nvalid.min()), int(nvalid.max())],
    }
finally:
    ds.close()

ua_chirps = load_csv_series("$UKRAINE_SAMPLES/extra/chirps_v3/chirps_v3_ukraine_bbox_monthly.csv", "time", "precip_mm")
# also n_valid from ua
ua_nv = {}
with open("$UKRAINE_SAMPLES/extra/chirps_v3/chirps_v3_ukraine_bbox_monthly.csv") as f:
    lines = [ln for ln in f if not ln.startswith("#")]
    rdr = csv.DictReader(lines)
    for rec in rdr:
        ua_nv[rec["time"]] = int(float(rec["n_valid_pixels"]))

comparisons["chirps"] = {
    "monthly": max_abs_diff({f"{y:04d}-{m:02d}": v for y, m, v, n in chirps_comp},
                            {f"{y:04d}-{m:02d}": v for y, m, v in ua_chirps}),
    "annual_12of12": max_abs_diff(annual_from_monthly([(y, m, v) for y, m, v, n in chirps_comp]),
                                  annual_from_monthly(ua_chirps)),
    "n_months_global": len(chirps_comp),
    "n_months_ua": len(ua_chirps),
    "units": notes["chirps_slice"]["units"],
    "var": notes["chirps_slice"]["var"],
    "grid": notes["chirps_slice"],
    "n_valid_global_first_last": [chirps_comp[0][3], chirps_comp[-1][3]],
    "n_valid_ua_first": ua_nv.get("1981-01"),
    "sample": {
        ym: {
            "global": next((v for y, m, v, n in chirps_comp if f"{y:04d}-{m:02d}" == ym), None),
            "ua": next((v for y, m, v in ua_chirps if f"{y:04d}-{m:02d}" == ym), None),
        }
        for ym in ["1981-01", "2000-07", "2020-07", "2026-10"]
    },
}
print("  chirps", comparisons["chirps"]["monthly"], comparisons["chirps"]["annual_12of12"],
      notes["chirps_slice"], flush=True)

# ======================== GPCC ========================
print("SPOT gpcc", flush=True)
gpcc_comp = []
gpcc_gauge = []
gpcc_varinfo = None
for fp in sorted(Path("$GLOBAL_DATA/gpcc_v2025_1deg").glob("*.nc.gz")):
    ds = open_nc(fp)
    try:
        lat = np.array(find_var(ds, ["lat", "latitude"])[:], dtype=float)
        lon = np.array(find_var(ds, ["lon", "longitude"])[:], dtype=float)
        # precip var
        pvar = None
        for cand in ["precip", "p", "pr", "precipitation", "precipitations_amount"]:
            pvar = find_var(ds, [cand])
            if pvar is not None:
                break
        if pvar is None:
            # first 3d var
            for vn, v in ds.variables.items():
                if v.ndim >= 3 and vn.lower() not in ("lat", "lon", "time"):
                    pvar = v
                    break
        gvar = None
        for cand in ["numgauge", "numgauges", "gauge", "gauges", "n_gauges", "number_of_gauges", "num_gauge"]:
            gvar = find_var(ds, [cand])
            if gvar is not None:
                break
        if gvar is None:
            for vn, v in ds.variables.items():
                if re.search(r"gauge", vn, re.I):
                    gvar = v
                    break
        if gpcc_varinfo is None:
            gpcc_varinfo = {
                "precip_name": pvar.name if pvar is not None else None,
                "precip_units": str(getattr(pvar, "units", "")) if pvar is not None else None,
                "gauge_name": gvar.name if gvar is not None else None,
                "gauge_units": str(getattr(gvar, "units", "")) if gvar is not None else None,
                "all_vars": [v["name"] for v in walk_vars(ds)],
            }
        times = parse_time_vals(find_var(ds, ["time", "Time"]))
        pdata = np.array(pvar[:], dtype=float)
        if np.ma.isMaskedArray(pvar[:]):
            pdata = np.array(np.ma.filled(pvar[:], np.nan), dtype=float)
        fill = getattr(pvar, "_FillValue", None) or getattr(pvar, "missing_value", None)
        gdata = None
        if gvar is not None:
            gdata = np.array(gvar[:], dtype=float)
        for i, t in enumerate(times):
            field = pdata[i]
            mean, n = weighted_mean(lat, lon, field, fill=fill)
            gpcc_comp.append((t.year, t.month, mean, n))
            if gdata is not None:
                gm, gn = weighted_mean(lat, lon, gdata[i], fill=getattr(gvar, "_FillValue", None))
                gpcc_gauge.append((t.year, t.month, gm, gn))
    finally:
        close_nc(ds)

ua_gpcc = load_csv_series("$UKRAINE_SAMPLES/extra/gpcc/gpcc_v2025_1deg_ukraine_bbox_monthly.csv", "time", "precip_mm")
comparisons["gpcc"] = {
    "monthly": max_abs_diff({f"{y:04d}-{m:02d}": v for y, m, v, n in gpcc_comp},
                            {f"{y:04d}-{m:02d}": v for y, m, v in ua_gpcc}),
    "annual_12of12": max_abs_diff(annual_from_monthly([(y, m, v) for y, m, v, n in gpcc_comp]),
                                  annual_from_monthly(ua_gpcc)),
    "n_months_global": len(gpcc_comp),
    "n_months_ua": len(ua_gpcc),
    "varinfo": gpcc_varinfo,
    "n_cells_first": gpcc_comp[0][3] if gpcc_comp else None,
    "has_gauge": gpcc_varinfo["gauge_name"] is not None if gpcc_varinfo else False,
    "sample": {
        ym: {
            "global": next((v for y, m, v, n in gpcc_comp if f"{y:04d}-{m:02d}" == ym), None),
            "ua": next((v for y, m, v in ua_gpcc if f"{y:04d}-{m:02d}" == ym), None),
        }
        for ym in ["1891-01", "1981-01", "2000-07", "2026-08"]
    },
}
print("  gpcc", comparisons["gpcc"]["monthly"], comparisons["gpcc"]["annual_12of12"], gpcc_varinfo, flush=True)

# ======================== GRACE ========================
print("SPOT grace", flush=True)
EXPECTED_MD5 = "1567b9401ec2a704aab16598fcce5e70"
R_EARTH_M = 6371000.0
ds = Dataset(str(grace_path))
try:
    lon = np.array(ds.variables["lon"][:], dtype=float)
    lat = np.array(ds.variables["lat"][:], dtype=float)
    lon_b = np.array(ds.variables["lon_bounds"][:], dtype=float)
    lat_b = np.array(ds.variables["lat_bounds"][:], dtype=float)
    land = np.array(ds.variables["land_mask"][:], dtype=float)
    scale = np.array(ds.variables["scale_factor"][:], dtype=float)
    mascon = np.array(ds.variables["mascon_ID"][:], dtype=float)
    time = np.array(ds.variables["time"][:], dtype=float)
    time_b = np.array(ds.variables["time_bounds"][:], dtype=float)
    lon_ix = np.where((lon >= BBOX["lon_min"]) & (lon <= BBOX["lon_max"]))[0]
    lat_ix = np.where((lat >= BBOX["lat_min"]) & (lat <= BBOX["lat_max"]))[0]
    slat = slice(int(lat_ix[0]), int(lat_ix[-1]) + 1)
    slon = slice(int(lon_ix[0]), int(lon_ix[-1]) + 1)
    lat_sub = lat[slat]
    lon_sub = lon[slon]
    lat_b_sub = lat_b[slat]
    lon_b_sub = lon_b[slon]
    land_sub = land[slat, slon]
    scale_sub = scale[slat, slon]
    dsin = np.sin(np.radians(np.maximum(lat_b_sub[:, 0], lat_b_sub[:, 1]))) - np.sin(
        np.radians(np.minimum(lat_b_sub[:, 0], lat_b_sub[:, 1]))
    )
    dlon = np.radians(np.abs(lon_b_sub[:, 1] - lon_b_sub[:, 0]))
    area = (R_EARTH_M ** 2) * dsin[:, None] * dlon[None, :]
    land_ok = land_sub == 1
    scale_ok = np.isfinite(scale_sub) & (scale_sub != -99999)
    cell_ok = land_ok & scale_ok
    lwe = np.array(ds.variables["lwe_thickness"][:, slat, slon], dtype=float)
    lwe = np.where((lwe == -99999.0) | ~np.isfinite(lwe), np.nan, lwe)
    # time units
    t_dates = parse_time_vals(ds.variables["time"])
    grace_unscaled = []
    grace_scaled = []
    for t, d in enumerate(t_dates):
        field = lwe[t]
        valid = cell_ok & np.isfinite(field)
        w = area.copy()
        w[~valid] = 0.0
        wsum = float(w.sum())
        mean_unscaled = float(np.nansum(field * w) / wsum) if wsum else float("nan")
        mean_scaled = float(np.nansum(field * scale_sub * w) / wsum) if wsum else float("nan")
        # month assignment later via CSV date alignment on time_center if needed
        grace_unscaled.append((d, mean_unscaled))
        grace_scaled.append((d, mean_scaled))
    # also compare bbox subset file pixel-wise for a few times
    subset_path = "$UKRAINE_SAMPLES/grace/GRCTellus.JPL.200204_202609.GLO.RL06.3M.MSCNv04CRI_ukraine_bbox.nc"
    grace_pixel = {}
    if os.path.exists(subset_path):
        ds2 = Dataset(subset_path)
        lwe2 = np.array(ds2.variables["lwe_thickness"][:], dtype=float)
        # compare first, mid, last
        for idx in [0, lwe.shape[0] // 2, lwe.shape[0] - 1]:
            a = lwe[idx]
            b = lwe2[idx]
            # both may have nan/fill
            a2 = np.where((a == -99999) | ~np.isfinite(a), np.nan, a)
            b2 = np.where((b == -99999) | ~np.isfinite(b), np.nan, b)
            both = np.isfinite(a2) & np.isfinite(b2)
            if both.any():
                mx = float(np.max(np.abs(a2[both] - b2[both])))
            else:
                mx = None
            grace_pixel[int(idx)] = {"max_abs": mx, "n": int(both.sum()), "shape_g": list(a.shape), "shape_u": list(b.shape)}
        ds2.close()
    notes["grace_bbox"] = {
        "nlat": int(lat_sub.size), "nlon": int(lon_sub.size),
        "n_land": int(land_ok.sum()), "n_cell_ok": int(cell_ok.sum()),
        "vars": [v["name"] for v in walk_vars(ds)],
        "months_missing_attr": str(ds.getncattr("months_missing"))[:500] if "months_missing" in ds.ncattrs() else None,
        "doi": ds.getncattr("identifier_product_doi") if "identifier_product_doi" in ds.ncattrs() else ncattrs(ds).get("DOI") or ncattrs(ds).get("doi"),
        "title": ncattrs(ds).get("title") or ncattrs(ds).get("Title"),
    }
finally:
    ds.close()

# align GRACE with CSV by time_center date (CSV has time_center)
ua_grace_rows = []
with open("$UKRAINE_SAMPLES/grace/ukraine_tws_monthly.csv", newline="") as f:
    rdr = csv.DictReader(f)
    for rec in rdr:
        ua_grace_rows.append(rec)

# map by time_center
def parse_iso_date(s):
    return date.fromisoformat(s[:10])

ua_uns = {rec["time_center"][:10]: float(rec["lwe_thickness_unscaled_cm"]) for rec in ua_grace_rows}
ua_scl = {rec["time_center"][:10]: float(rec["lwe_thickness_cm"]) for rec in ua_grace_rows}
g_uns = {d.isoformat(): v for d, v in grace_unscaled}
g_scl = {d.isoformat(): v for d, v in grace_scaled}
# annual on official assigned months from CSV (safer than midpoint)
ua_ann_pairs = [(int(r["year"]), int(r["month"]), float(r["lwe_thickness_unscaled_cm"])) for r in ua_grace_rows]
# rebuild assigned-month series from our unscaled using CSV year/month via time_center join
g_pairs_assigned = []
for rec in ua_grace_rows:
    key = rec["time_center"][:10]
    if key in g_uns:
        g_pairs_assigned.append((int(rec["year"]), int(rec["month"]), g_uns[key]))

comparisons["grace"] = {
    "monthly_unscaled": max_abs_diff(g_uns, ua_uns),
    "monthly_scaled": max_abs_diff(g_scl, ua_scl),
    "annual_unscaled_12of12": max_abs_diff(annual_from_monthly(g_pairs_assigned), annual_from_monthly(ua_ann_pairs)),
    "n_months_global": len(g_uns),
    "n_months_ua": len(ua_uns),
    "pixel_vs_subset_nc": grace_pixel,
    "md5_ok": notes["grace_md5_ok"],
}
print("  grace", comparisons["grace"], flush=True)

# ======================== HadCRUT / GISTEMP / Berkeley few months + annual ========================
print("SPOT hadcrut/gistemp/berkeley", flush=True)

# HadCRUT: overlap-area weights. Source file is hard-linked, so data are identical;
# still recompute the cut to confirm we can reproduce the extract from this path.
WEST, EAST, SOUTH, NORTH = 22.1, 40.2, 44.4, 52.4

def rect_overlap(a0, a1, b0, b1):
    lo = max(min(a0, a1), min(b0, b1))
    hi = min(max(a0, a1), max(b0, b1))
    if hi <= lo:
        return None
    return lo, hi

def overlap_area(lat0, lat1, lon0, lon1):
    la = rect_overlap(lat0, lat1, SOUTH, NORTH)
    lo = rect_overlap(lon0, lon1, WEST, EAST)
    if la is None or lo is None:
        return 0.0
    # Δlon × Δsin(lat)
    return abs(np.radians(lo[1] - lo[0])) * abs(np.sin(np.radians(la[1])) - np.sin(np.radians(la[0])))

# HadCRUT
ds = Dataset("$GLOBAL_DATA/hadcrut5/HadCRUT.5.2.0.0.analysis.anomalies.ensemble_mean.nc")
try:
    lat = np.array(ds.variables["latitude"][:], dtype=float)
    lon = np.array(ds.variables["longitude"][:], dtype=float)
    lat_b = np.array(ds.variables["latitude_bnds"][:], dtype=float)
    lon_b = np.array(ds.variables["longitude_bnds"][:], dtype=float)
    tas = ds.variables["tas"]
    times = parse_time_vals(ds.variables["time"])
    cells = []
    for i, la in enumerate(lat):
        for j, lo in enumerate(lon):
            area = overlap_area(lat_b[i, 0], lat_b[i, 1], lon_b[j, 0], lon_b[j, 1])
            if area > 0:
                cells.append((i, j, area))
    had_comp = []
    # read only needed i,j? easier read all time for unique i rows
    i_set = sorted({c[0] for c in cells})
    j_set = sorted({c[1] for c in cells})
    # tas shape time, lat, lon — read full is 32MB file already in memory-ish; 1760*36*72*4 ~ 18MB ok
    data = np.array(tas[:], dtype=float)
    if np.ma.isMaskedArray(tas[:]):
        data = np.array(np.ma.filled(tas[:], np.nan), dtype=float)
    fill = getattr(tas, "_FillValue", None)
    if fill is not None:
        data = np.where(data == float(fill), np.nan, data)
    for t, d in enumerate(times):
        num = den = 0.0
        n = 0
        for i, j, area in cells:
            v = data[t, i, j]
            if np.isfinite(v):
                num += v * area
                den += area
                n += 1
        had_comp.append((d.year, d.month, (num / den) if den else float("nan")))
    notes["hadcrut_n_overlap_cells"] = len(cells)
    notes["hadcrut_vars"] = [v["name"] for v in walk_vars(ds)]
    notes["hadcrut_time"] = (times[0].isoformat(), times[-1].isoformat(), len(times))
finally:
    ds.close()

ua_had = load_csv_series("$UKRAINE_SAMPLES/extra/hadcrut5/hadcrut5_ukraine_bbox_monthly.csv", "time", "tas_anomaly_C") if False else None
# discover columns
with open("$UKRAINE_SAMPLES/extra/hadcrut5/hadcrut5_ukraine_bbox_monthly.csv") as f:
    lines = [ln for ln in f if not ln.startswith("#")]
header = lines[0].strip().split(",")
notes["hadcrut_csv_cols"] = header
# primary is tas_anomaly_C
ua_had = load_csv_series("$UKRAINE_SAMPLES/extra/hadcrut5/hadcrut5_ukraine_bbox_monthly.csv", "time", "tas_anomaly_C")
comparisons["hadcrut"] = {
    "monthly": max_abs_diff({f"{y:04d}-{m:02d}": v for y, m, v in had_comp},
                            {f"{y:04d}-{m:02d}": v for y, m, v in ua_had}),
    "annual_12of12": max_abs_diff(annual_from_monthly(had_comp), annual_from_monthly(ua_had)),
    "n_overlap_cells": notes["hadcrut_n_overlap_cells"],
    "hardlinked_to_ua_extract": notes["inodes"]["hadcrut_global"]["ino"] == notes["inodes"]["hadcrut_ua"]["ino"],
}

# GISTEMP (gzip) — 2° cells, centre ± 1°, overlap weights
ds = open_nc("$GLOBAL_DATA/gistemp/gistemp1200_GHCNv4_ERSSTv5.nc.gz")
try:
    # variable names
    vns = [v["name"] for v in walk_vars(ds)]
    notes["gistemp_vars"] = vns
    lat = np.array(find_var(ds, ["lat", "latitude"])[:], dtype=float)
    lon = np.array(find_var(ds, ["lon", "longitude"])[:], dtype=float)
    lon = wrap_lon(lon, -180)
    tvar = find_var(ds, ["time", "T"])
    times = parse_time_vals(tvar)
    # tempanomaly typical
    pvar = find_var(ds, ["tempanomaly", "tas", "temperature", "anom"])
    notes["gistemp_temp_var"] = pvar.name if pvar is not None else None
    notes["gistemp_time"] = (times[0].isoformat(), times[-1].isoformat(), len(times)) if isinstance(times[0], date) else times
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
    # also huge fills
    data = np.where(np.abs(data) > 1e10, np.nan, data)
    gis_comp = []
    for t, d in enumerate(times):
        num = den = 0.0
        for i, j, area in cells:
            v = data[t, i, j]
            if np.isfinite(v):
                num += v * area
                den += area
        gis_comp.append((d.year, d.month, (num / den) if den else float("nan")))
    notes["gistemp_n_overlap_cells"] = len(cells)
finally:
    close_nc(ds)

with open("$UKRAINE_SAMPLES/extra/gistemp/gistemp_ukraine_bbox_monthly.csv") as f:
    lines = [ln for ln in f if not ln.startswith("#")]
notes["gistemp_csv_cols"] = lines[0].strip().split(",")
ua_gis = load_csv_series("$UKRAINE_SAMPLES/extra/gistemp/gistemp_ukraine_bbox_monthly.csv", "time", "tas_anomaly_C")
comparisons["gistemp"] = {
    "monthly": max_abs_diff({f"{y:04d}-{m:02d}": v for y, m, v in gis_comp},
                            {f"{y:04d}-{m:02d}": v for y, m, v in ua_gis}),
    "annual_12of12": max_abs_diff(annual_from_monthly(gis_comp), annual_from_monthly(ua_gis)),
    "n_overlap_cells": notes["gistemp_n_overlap_cells"],
    "hardlinked_to_ua_extract": notes["inodes"]["gistemp_global"]["ino"] == notes["inodes"]["gistemp_ua"]["ino"],
}

# Berkeley: cosine-lat mean of 1° land cells with centres in box
ds = Dataset("$GLOBAL_DATA/berkeley_earth/Complete_TAVG_LatLong1.nc")
try:
    notes["berkeley_vars"] = [v["name"] for v in walk_vars(ds)]
    notes["berkeley_attrs_keys"] = list(ncattrs(ds))
    lat = np.array(find_var(ds, ["lat", "latitude"])[:], dtype=float)
    lon = np.array(find_var(ds, ["lon", "longitude"])[:], dtype=float)
    # temperature / anomal
    pvar = find_var(ds, ["temperature", "temperatures", "tas", "anomaly"])
    notes["berkeley_temp_var"] = pvar.name
    notes["berkeley_temp_units"] = str(getattr(pvar, "units", ""))
    times = parse_time_vals(find_var(ds, ["time", "T"]))
    notes["berkeley_time"] = (times[0].isoformat(), times[-1].isoformat(), len(times))
    data = np.array(pvar[:], dtype=float)
    if np.ma.isMaskedArray(pvar[:]):
        data = np.array(np.ma.filled(pvar[:], np.nan), dtype=float)
    fill = getattr(pvar, "_FillValue", None)
    berk_comp = []
    n0 = None
    for t, d in enumerate(times):
        mean, n = weighted_mean(lat, lon, data[t], fill=fill)
        berk_comp.append((d.year, d.month, mean))
        if n0 is None:
            n0 = n
    notes["berkeley_n_cells"] = n0
finally:
    ds.close()

with open("$UKRAINE_SAMPLES/extra/berkeley_earth/berkeley_earth_ukraine_bbox_monthly.csv") as f:
    lines = [ln for ln in f if not ln.startswith("#")]
notes["berkeley_csv_cols"] = lines[0].strip().split(",")
# typical column
bcol = "temperature" if "temperature" in notes["berkeley_csv_cols"] else notes["berkeley_csv_cols"][1]
# try common
for c in notes["berkeley_csv_cols"]:
    if c not in ("time", "year", "month", "nlat", "nlon", "n_cells") and not c.startswith("n"):
        # first value-like
        if re.search(r"temp|anom|tas|tavg", c, re.I) or c in ("value", "tavg"):
            bcol = c
            break
# if header is time,precip-like... read first data
ua_berk = load_csv_series("$UKRAINE_SAMPLES/extra/berkeley_earth/berkeley_earth_ukraine_bbox_monthly.csv", "time", bcol)
comparisons["berkeley"] = {
    "monthly": max_abs_diff({f"{y:04d}-{m:02d}": v for y, m, v in berk_comp},
                            {f"{y:04d}-{m:02d}": v for y, m, v in ua_berk}),
    "annual_12of12": max_abs_diff(annual_from_monthly(berk_comp), annual_from_monthly(ua_berk)),
    "n_cells": n0,
    "col_used": bcol,
}

# ======================== AIRS few months (bonus) ========================
print("SPOT airs few months", flush=True)
airs_files = {}
for p in Path("$GLOBAL_DATA/airs3stm_slim").glob("AIRS.*"):
    m = re.search(r"AIRS\.(\d{4})\.(\d{2})\.(\d{2})", p.name)
    if m:
        airs_files[m.group(1) + m.group(2)] = p

def airs_surf(path):
    ds = Dataset(str(path))
    try:
        lat = np.array(find_var(ds, ["Latitude", "lat", "latitude"])[:], dtype=float)
        lon = np.array(find_var(ds, ["Longitude", "lon", "longitude"])[:], dtype=float)
        va = find_var(ds, ["SurfAirTemp_A"])
        vd = find_var(ds, ["SurfAirTemp_D"])
        fill = getattr(va, "_FillValue", None) or getattr(va, "missing_value", None)
        ma, na = weighted_mean(np.unique(lat) if lat.ndim > 1 else lat,
                               np.unique(lon) if lon.ndim > 1 else lon,
                               va[:], fill=fill)
        # lat/lon may be 2d 180x360
        if lat.ndim > 1:
            # use 1d axes
            lat1 = lat[:, 0] if lat.shape[1] > 1 else lat.ravel()
            lon1 = lon[0, :] if lon.shape[0] > 1 else lon.ravel()
            ma, na = weighted_mean(lat1, lon1, va[:], fill=fill)
            md, nd = weighted_mean(lat1, lon1, vd[:], fill=fill)
        else:
            md, nd = weighted_mean(lat, lon, vd[:], fill=fill)
        if np.isfinite(ma) and np.isfinite(md):
            comb = 0.5 * (ma + md)
        else:
            comb = ma if np.isfinite(ma) else md
        return comb, ma, md, na, nd
    finally:
        ds.close()

airs_sample = {}
for ym in ["200209", "201007", "202007", "202610"]:
    if ym in airs_files:
        comb, ma, md, na, nd = airs_surf(airs_files[ym])
        airs_sample[f"{ym[:4]}-{ym[4:]}"] = {"combined": comb, "A": ma, "D": md, "nA": na, "nD": nd}

ua_airs = {}
with open("$UKRAINE_SAMPLES/airs/airs_ukraine_monthly.csv", newline="") as f:
    rdr = csv.DictReader(f)
    for rec in rdr:
        ua_airs[rec["date"]] = float(rec["SurfAirTemp"])
comparisons["airs_sample"] = {
    "months": {k: {**v, "ua": ua_airs.get(k),
                   "abs_diff": abs(v["combined"] - ua_airs[k]) if k in ua_airs else None}
               for k, v in airs_sample.items()}
}
print("  airs", comparisons["airs_sample"], flush=True)

# done
notes["comparisons"] = comparisons
# strip heavy inspections vars for a compact results? keep them
(OUT / "spotcheck_results.json").write_text(json.dumps({
    "du_dirs": notes["du_dirs"],
    "file_bytes": notes["file_bytes"],
    "claimed_total_log": notes["claimed_total_log"],
    "on_disk_file_bytes_sum": notes["on_disk_file_bytes_sum"],
    "df": notes["df"],
    "grace_md5": notes["grace_md5"],
    "grace_md5_ok": notes["grace_md5_ok"],
    "grace_bytes": notes["grace_bytes"],
    "inodes": notes["inodes"],
    "chirps_time": notes.get("chirps_time"),
    "chirps_lat_range": notes.get("chirps_lat_range"),
    "chirps_lon_range": notes.get("chirps_lon_range"),
    "chirps_dlat": notes.get("chirps_dlat"),
    "chirps_dlon": notes.get("chirps_dlon"),
    "chirps_slice": notes.get("chirps_slice"),
    "gpcc_time": notes.get("gpcc_time"),
    "coverage_fields": notes.get("coverage_fields"),
    "hadcrut_n_overlap_cells": notes.get("hadcrut_n_overlap_cells"),
    "hadcrut_vars": notes.get("hadcrut_vars"),
    "hadcrut_time": notes.get("hadcrut_time"),
    "hadcrut_csv_cols": notes.get("hadcrut_csv_cols"),
    "gistemp_vars": notes.get("gistemp_vars"),
    "gistemp_temp_var": notes.get("gistemp_temp_var"),
    "gistemp_time": notes.get("gistemp_time"),
    "gistemp_n_overlap_cells": notes.get("gistemp_n_overlap_cells"),
    "gistemp_csv_cols": notes.get("gistemp_csv_cols"),
    "berkeley_vars": notes.get("berkeley_vars"),
    "berkeley_temp_var": notes.get("berkeley_temp_var"),
    "berkeley_temp_units": notes.get("berkeley_temp_units"),
    "berkeley_time": notes.get("berkeley_time"),
    "berkeley_n_cells": notes.get("berkeley_n_cells"),
    "berkeley_csv_cols": notes.get("berkeley_csv_cols"),
    "grace_bbox": notes.get("grace_bbox"),
    "comparisons": comparisons,
    "inspect_varnames": {k: [v["name"] for v in insp.get("vars", [])] for k, insp in inspections.items()},
    "inspect_attrs": {k: insp.get("attrs") for k, insp in inspections.items()},
    "inspect_dims": {k: insp.get("all_dims") or insp.get("dims") for k, insp in inspections.items()},
    "inspect_time": {k: {kk: insp[kk] for kk in ("time_n", "time_first", "time_last", "time_unique", "error") if kk in insp}
                     for k, insp in inspections.items()},
    "inspect_errors": {k: insp["error"] for k, insp in inspections.items() if "error" in insp},
}, default=str, indent=2))
print("WROTE spotcheck_results.json")
