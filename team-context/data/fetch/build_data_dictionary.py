#!/usr/bin/env python3
"""Build Ukraine-sample data dictionary, station coverage, and overview extras."""
from __future__ import annotations
import io, json, gzip
from pathlib import Path
import netCDF4 as nc
import numpy as np
import pandas as pd
import shapefile
from scipy import stats

from locate import FETCH_DIR, UKRAINE_SAMPLES

ROOT = UKRAINE_SAMPLES
OUT = FETCH_DIR.parent / "docs"
BBOX = dict(lon_min=22.1, lon_max=40.2, lat_min=44.4, lat_max=52.4)
MONTHS = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
COLS = ["category","status","source_folder","product","variable","description","units",
        "spatial_unit","temporal_resolution","date_first","date_last","n_records",
        "n_spatial_units","n_spatial_reporting","n_missing","pct_missing","fill_values",
        "qc_notes","min","max","mean","median_record_length_years","caveats","files"]
rows, station_rows, read_errors = [], [], []

def blank(**kw):
    r = {c: "" for c in COLS}; r.update(kw); return r
def add(**kw): rows.append(blank(**kw))
def fnum(x, nd=4):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))): return ""
    if isinstance(x, (int, np.integer)): return int(x)
    x = float(x)
    if abs(x) >= 1e6 or (abs(x) < 1e-3 and x != 0): return float(f"{x:.6g}")
    return round(x, nd)
def pct(n, d, nd=2):
    return "" if not d else round(100.0 * float(n) / float(d), nd)
def rel(p: Path) -> str:
    try: return str(p.relative_to(ROOT))
    except ValueError: return str(p)
def folder_bytes(path: Path) -> int:
    if not path.exists(): return 0
    if path.is_file(): return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
def fmt_bytes(n: float) -> str:
    n = float(n)
    if n >= 1024**4: return f"{n/1024**4:.2f} TiB"
    if n >= 1024**3: return f"{n/1024**3:.2f} GiB"
    if n >= 1024**2: return f"{n/1024**2:.2f} MiB"
    if n >= 1024: return f"{n/1024:.1f} KiB"
    return f"{int(n)} B"
def fmt_si(n: float) -> str:
    n = float(n)
    if n >= 1e12: return f"{n/1e12:.2f} TB"
    if n >= 1e9: return f"{n/1e9:.2f} GB"
    if n >= 1e6: return f"{n/1e6:.0f} MB" if n >= 1e8 else f"{n/1e6:.1f} MB"
    return f"{n/1e3:.0f} KB" if n >= 1e3 else f"{n:.0f} B"
def swot_mask(s, also_abs_gt=1e11):
    x = pd.to_numeric(s, errors="coerce")
    bad = x.isin([-999, -9999, -999999999999.0])
    if also_abs_gt is not None: bad = bad | (x.abs() >= also_abs_gt)
    return x.where(~bad)
def read_power(path: Path) -> pd.DataFrame:
    text = path.read_text()
    return pd.read_csv(io.StringIO(text[text.index("PARAMETER,"):]))

DESC = {
    "T2M": ("Air temperature at 2 m", "°C", "NASA POWER / MERRA-2 monthly"),
    "T2M_MAX": ("Monthly maximum 2 m air temperature (ANN is the annual extreme, not the mean)", "°C", "NASA POWER / MERRA-2 monthly"),
    "T2M_MIN": ("Monthly minimum 2 m air temperature (ANN is the annual extreme, not the mean)", "°C", "NASA POWER / MERRA-2 monthly"),
    "PRECTOTCORR": ("Bias-corrected precipitation rate", "mm/day", "NASA POWER / MERRA-2 monthly"),
    "QV2M": ("Specific humidity at 2 m (g/kg, not kg/kg)", "g/kg", "NASA POWER / MERRA-2 monthly"),
    "WS10M": ("Wind speed at 10 m", "m/s", "NASA POWER / MERRA-2 monthly"),
    "ALLSKY_SFC_SW_DWN": ("All-sky surface shortwave downward irradiance. POWER splices GEWEX SRB (1984-2000) to CERES SYN1deg (2001-present).", "kWh/m²/day", "NASA POWER / CERES SYN1deg (SRB before 2001)"),
    "PRCP": ("Monthly total precipitation", "mm", "NOAA GSOM"),
    "TAVG": ("Monthly average air temperature", "°C", "NOAA GSOM"),
    "TMAX": ("Monthly average daily-maximum air temperature", "°C", "NOAA GSOM"),
    "TMIN": ("Monthly average daily-minimum air temperature", "°C", "NOAA GSOM"),
    "NDVI": ("Normalized Difference Vegetation Index, bbox mean of valid 0.05° CMG pixels", "index", "MOD13C2.061"),
    "EVI": ("Enhanced Vegetation Index, bbox mean of valid 0.05° CMG pixels", "index", "MOD13C2.061"),
    "LST_Day_K": ("Daytime land-surface temperature, bbox mean of valid 0.05° CMG pixels", "K", "MOD11C3.061"),
    "LST_Night_K": ("Night-time land-surface temperature, bbox mean of valid 0.05° CMG pixels", "K", "MOD11C3.061"),
    "wse": ("Water-surface elevation", "m", "SWOT Hydrocron RiverSP-D"),
    "wse_u": ("Uncertainty of water-surface elevation", "m", "SWOT Hydrocron RiverSP-D"),
    "width": ("Reach width", "m", "SWOT Hydrocron RiverSP-D"),
    "width_u": ("Uncertainty of reach width", "m", "SWOT Hydrocron RiverSP-D"),
    "area_total": ("Total water area", "m²", "SWOT Hydrocron RiverSP-D"),
    "slope": ("Water-surface slope", "m/m", "SWOT Hydrocron RiverSP-D"),
    "reach_q": ("Reach quality flag (0 good, 1 suspect, 2 degraded, 3 bad)", "flag", "SWOT Hydrocron RiverSP-D"),
    "dark_frac": ("Fraction of reach area in dark water", "fraction", "SWOT Hydrocron RiverSP-D"),
    "ice_clim_f": ("Climatological ice flag", "flag", "SWOT Hydrocron RiverSP-D"),
    "ice_dyn_f": ("Dynamic ice flag (fill in this extract)", "flag", "SWOT Hydrocron RiverSP-D"),
    "dschg_c": ("Constrained discharge estimate", "m³/s", "SWOT Hydrocron RiverSP-D"),
}
GHCN_SCALE = {"PRCP": 0.1, "TMAX": 0.1, "TMIN": 0.1, "TAVG": 0.1, "SNWD": 1.0}
GHCN_UNITS = {"PRCP": "mm", "TMAX": "°C", "TMIN": "°C", "TAVG": "°C", "SNWD": "mm"}
GHCN_DESC = {
    "PRCP": "Daily precipitation total (stored as tenths of mm)",
    "TMAX": "Daily maximum air temperature (stored as tenths of °C)",
    "TMIN": "Daily minimum air temperature (stored as tenths of °C)",
    "TAVG": "Daily average air temperature (stored as tenths of °C)",
    "SNWD": "Snow depth",
}
print("helpers ok")

def analyze_power():
    print("POWER...")
    folder = ROOT / "nasa_power"
    params = ["T2M","T2M_MAX","T2M_MIN","PRECTOTCORR","QV2M","WS10M","ALLSKY_SFC_SW_DWN"]
    common = ("Bbox 22.1-40.2E, 44.4-52.4N is about twice Ukraine and includes neighbours and the NW Black Sea; no country polygon. "
              "West/east tiles do not overlap. Do not use ANN for T2M_MAX/T2M_MIN (annual extreme). Files end Dec 2025.")
    for var in params:
        frames, files = [], []
        for tile in ("west", "east"):
            p = folder / f"POWER_monthly_{var}_{tile}_1981-2025.csv"
            files.append(rel(p)); frames.append(read_power(p))
        df = pd.concat(frames, ignore_index=True)
        n_cells = df.groupby(["LAT","LON"]).ngroups
        long = df.melt(id_vars=["PARAMETER","YEAR","LAT","LON"], value_vars=MONTHS, var_name="month", value_name="val")
        val = pd.to_numeric(long["val"], errors="coerce")
        is_fill = val.isna() | (val == -999)
        good = val.where(~is_fill)
        first_y, last_y = int(df["YEAR"].min()), int(df["YEAR"].max())
        extra = ""
        if var == "ALLSKY_SFC_SW_DWN":
            extra = (" Filename says 1981-2025 but data start in 1984. Coarser 1deg grid (144 vs 464 MERRA-2 cells). "
                     "SRB-to-CERES splice at 2001: prefer 2001+ for trends or treat the splice as a breakpoint.")
            spatial = "1deg grid-cell (CERES), bbox mean of 144 cells"
        else:
            spatial = "0.5 x 0.625 deg grid-cell (MERRA-2), bbox mean of 464 cells"
        desc, units, product = DESC[var]
        add(category="observational", status="available", source_folder="nasa_power", product=product,
            variable=var, description=desc, units=units, spatial_unit=spatial,
            temporal_resolution="monthly (plus ANN column)", date_first=f"{first_y}-01", date_last=f"{last_y}-12",
            n_records=int(val.shape[0]), n_spatial_units=n_cells, n_spatial_reporting=n_cells,
            n_missing=int(is_fill.sum()), pct_missing=pct(int(is_fill.sum()), int(val.shape[0])),
            fill_values="-999", qc_notes="POWER missing/out-of-range flag is -999. No additional QC flags in the CSV.",
            min=fnum(good.min()), max=fnum(good.max()), mean=fnum(good.mean()),
            median_record_length_years=last_y-first_y+1, caveats=common+extra, files="; ".join(files))

def analyze_gsom():
    print("GSOM...")
    path = ROOT / "noaa_gsom" / "gsom_ukraine_UP_stations.csv"
    df = pd.read_csv(path)
    df["DATE"] = df["DATE"].astype(str)
    df["year"] = df["DATE"].str[:4].astype(int)
    n_sta, n_rows = df["STATION"].nunique(), len(df)
    d0, d1 = df["DATE"].min(), df["DATE"].max()
    prcp_by_dec = []
    for dec, sub in df.assign(decade=(df["year"]//10)*10).groupby("decade"):
        prcp_by_dec.append(f"{int(dec)}s: {sub.loc[sub['PRCP'].notna(),'STATION'].nunique()} sta")
    for var in ["PRCP","TAVG","TMAX","TMIN"]:
        s = pd.to_numeric(df[var], errors="coerce")
        n_miss = int(s.isna().sum()); good = s.dropna()
        reporting = df.loc[s.notna(), "STATION"].nunique()
        spans = []
        for sta, g in df.groupby("STATION"):
            v = pd.to_numeric(g[var], errors="coerce")
            ok = g.loc[v.notna(), "DATE"]
            n_valid = int(v.notna().sum())
            name, lat, lon, elev = g["NAME"].iloc[0], g["LATITUDE"].iloc[0], g["LONGITUDE"].iloc[0], g["ELEVATION"].iloc[0]
            if n_valid == 0:
                first = last = span = ""
            else:
                first, last = ok.min(), ok.max()
                span = round(int(last[:4]) - int(first[:4]) + (int(last[5:7]) - int(first[5:7])) / 12.0, 2)
                spans.append(span)
            station_rows.append(dict(source="noaa_gsom", station_id=sta, name=name, latitude=lat, longitude=lon,
                elevation=elev, country="UP", variable=var, date_first=first, date_last=last, n_valid=n_valid,
                n_rows_in_archive=int(len(g)), n_missing_in_archive_rows=int(v.isna().sum()),
                pct_missing_in_archive_rows=pct(int(v.isna().sum()), len(g)), n_qc_removed=0, record_length_years=span))
        add(category="observational", status="available", source_folder="noaa_gsom",
            product="NOAA NCEI GSOM (GHCN monthly), all 204 UP stations",
            variable=var, description=DESC[var][0], units=DESC[var][1],
            spatial_unit="station (UP / Ukraine)", temporal_resolution="monthly",
            date_first=d0, date_last=d1, n_records=n_rows, n_spatial_units=n_sta, n_spatial_reporting=reporting,
            n_missing=n_miss, pct_missing=pct(n_miss, n_rows),
            fill_values="empty / NaN (no -999 or -9999 in this extract)",
            qc_notes="This extract has no quality-flag columns; NOAA GSOM flags were not downloaded.",
            min=fnum(good.min()), max=fnum(good.max()), mean=fnum(good.mean()),
            median_record_length_years=fnum(float(np.median(spans)), 2) if spans else "",
            caveats=("204 UP stations, 1900-01 to 2026-10, one combined CSV. "
                     f"GSOM precipitation reporting collapses after ~2000 ({', '.join(prcp_by_dec)}). "
                     "Long-record TAVG (9 stations in the revised analysis) has no data in 2020-2024 "
                     "(9 stations through 2012, 4 in 2013-2019 and 2025, 0 in the gap). "
                     "2026 is incomplete (through October). Stations are Ukraine only, not the full bbox."),
            files=rel(path))

def analyze_ghcn():
    print("GHCN...")
    folder = ROOT / "noaa_ghcn" / "daily_by_station"
    bbox = pd.read_csv(ROOT / "noaa_ghcn" / "ukraine_bbox_stations.csv")
    meta = bbox.set_index("id")
    files = sorted(folder.glob("*.csv.gz"))
    parts = [pd.read_csv(f, header=None, names=["ID","DATE","ELEMENT","VALUE","MFLAG","QFLAG","SFLAG","OBS_TIME"],
                         dtype={"ID":str,"DATE":str,"ELEMENT":str,"VALUE":"float64","MFLAG":str,"QFLAG":str,"SFLAG":str,"OBS_TIME":str},
                         keep_default_na=False) for f in files]
    all_df = pd.concat(parts, ignore_index=True)
    n_sta = all_df["ID"].nunique()
    n_bbox, n_up = len(bbox), int((bbox["country"]=="UP").sum())
    for elem, group in all_df.groupby("ELEMENT"):
        scale = GHCN_SCALE.get(elem, 1.0)
        units = GHCN_UNITS.get(elem, "")
        qflag = group["QFLAG"].fillna("").astype(str).str.strip()
        n_qc = int((qflag != "").sum())
        val = pd.to_numeric(group["VALUE"], errors="coerce") * scale
        good = val.where(qflag == "")
        spans, reporting = [], 0
        for sta, g in group.groupby("ID"):
            q = g["QFLAG"].fillna("").astype(str).str.strip()
            v = pd.to_numeric(g["VALUE"], errors="coerce") * scale
            valid = v.where(q == "").dropna()
            dates = g["DATE"].astype(str)
            if len(valid):
                reporting += 1
                dfirst, dlast = dates.loc[valid.index].min(), dates.loc[valid.index].max()
                span = round(int(dlast[:4]) - int(dfirst[:4]) + 1 + (int(dlast[4:6]) - int(dfirst[4:6])) / 12.0, 2)
                spans.append(int(dlast[:4]) - int(dfirst[:4]) + 1)
            else:
                dfirst = dlast = span = ""
            info = meta.loc[sta] if sta in meta.index else None
            station_rows.append(dict(source="noaa_ghcn", station_id=sta,
                name=("" if info is None else info["name"]),
                latitude=("" if info is None else info["lat"]),
                longitude=("" if info is None else info["lon"]),
                elevation=("" if info is None else info["elev"]),
                country=("UP" if info is None else info["country"]),
                variable=elem,
                date_first=(f"{dfirst[:4]}-{dfirst[4:6]}-{dfirst[6:8]}" if dfirst else ""),
                date_last=(f"{dlast[:4]}-{dlast[4:6]}-{dlast[6:8]}" if dlast else ""),
                n_valid=int(len(valid)), n_rows_in_archive=int(len(g)),
                n_missing_in_archive_rows=int(len(g)-len(valid)),
                pct_missing_in_archive_rows=pct(len(g)-len(valid), len(g)),
                n_qc_removed=int((q!="").sum()), record_length_years=span))
        dates = group["DATE"].astype(str); d0, d1 = dates.min(), dates.max()
        qcounts = qflag[qflag!=""].value_counts().to_dict()
        add(category="observational", status="available", source_folder="noaa_ghcn",
            product="GHCN-Daily, 28 selected UP city stations",
            variable=elem, description=GHCN_DESC.get(elem, f"GHCN-Daily element {elem}"), units=units,
            spatial_unit="station (28 selected UP cities)", temporal_resolution="daily",
            date_first=f"{d0[:4]}-{d0[4:6]}-{d0[6:8]}", date_last=f"{d1[:4]}-{d1[4:6]}-{d1[6:8]}",
            n_records=len(group), n_spatial_units=n_sta, n_spatial_reporting=reporting,
            n_missing=int(good.isna().sum()), pct_missing=pct(int(good.isna().sum()), len(group)),
            fill_values="none in raw integer values; missing = element not reported that day",
            qc_notes=f"QFLAG non-blank failed QC and was removed from min/max/mean ({n_qc} rows, {qcounts}). Scale {scale}. MFLAG/SFLAG are not failures.",
            min=fnum(good.min()), max=fnum(good.max()), mean=fnum(good.mean()),
            median_record_length_years=fnum(float(np.median(spans)), 2) if spans else "",
            caveats=(f"Only 28 of {n_bbox} bbox-inventory stations were downloaded ({n_up} UP + neighbours). "
                     "2025 temperature uses fewer long-record stations; precip in 2020-2024 rests on two stations. "
                     "Record through 2026-11-06 (partial 2026). Drop 2026 from climate annual trends."),
            files=f"{rel(folder)} ({len(files)} files); {rel(ROOT/'noaa_ghcn'/'ukraine_bbox_stations.csv')}")

def analyze_modis():
    print("MODIS...")
    folder = ROOT / "modis_lpdaac"
    specs = [
        ("MOD13C2_ukraine_monthly.csv","NDVI","NDVI","NDVI_n","MOD13C2.061"),
        ("MOD13C2_ukraine_monthly.csv","EVI","EVI","EVI_n","MOD13C2.061"),
        ("MOD11C3_ukraine_monthly.csv","LST_Day_K","LST_Day_K","LST_Day_K_n","MOD11C3.061"),
        ("MOD11C3_ukraine_monthly.csv","LST_Night_K","LST_Night_K","LST_Night_K_n","MOD11C3.061"),
    ]
    for fname, var, col, ncol, product in specs:
        path = folder / fname
        df = pd.read_csv(path)
        desc, units, prod = DESC[var]
        s = pd.to_numeric(df[col], errors="coerce")
        n_pix = pd.to_numeric(df[ncol], errors="coerce")
        add(category="observational", status="available", source_folder="modis_lpdaac", product=prod,
            variable=var, description=desc, units=units,
            spatial_unit="bbox mean of valid 0.05deg CMG pixels (window 161 x 363 = 58443; no Ukraine polygon, no QA-bit filter)",
            temporal_resolution="monthly", date_first=str(df["month"].min()), date_last=str(df["month"].max()),
            n_records=len(df), n_spatial_units=58443, n_spatial_reporting=int(round(n_pix.mean())) if n_pix.notna().any() else "",
            n_missing=int(s.isna().sum()), pct_missing=pct(int(s.isna().sum()), len(df)),
            fill_values="already removed in the monthly CSV (fill/range only; see sample NetCDF rows)",
            qc_notes=(f"Mean valid-pixel count/month: {fnum(n_pix.mean(),1)} (min {int(n_pix.min())}, max {int(n_pix.max())}). "
                      f"All {len(df)} months HTTP 200, no missing months 2000-02 to 2026-10. No QA-bit filtering."),
            min=fnum(s.min()), max=fnum(s.max()), mean=fnum(s.mean()),
            median_record_length_years=round((2026+10/12)-(2000+2/12), 2),
            caveats=("Year 2000 starts in February — drop 2000 from annual climate trends. 2026 incomplete (through Oct). "
                     "Use 2001-2025. Compare LST with POWER T2M over the same 2001-2025 window, not 1981-2025 air temperature. Terra-only."),
            files=rel(path))
    def walk_vars(ds):
        out = []
        def rec(g):
            for v in g.variables.values(): out.append((g, v))
            for sg in g.groups.values(): rec(sg)
        rec(ds); return out
    def describe_sample(pattern, label):
        files = sorted((folder/"samples").glob(pattern))
        if not files:
            read_errors.append(f"No MODIS sample matching {pattern}"); return
        p = files[0]
        try:
            ds = nc.Dataset(p)
        except Exception as e:
            read_errors.append(f"Could not read {p}: {e}")
            add(category="observational", status="read_error", source_folder="modis_lpdaac", product=label,
                variable="(unreadable sample)", description=str(e), files=rel(p), caveats="File could not be read.")
            return
        for grp, var in walk_vars(ds):
            var.set_auto_maskandscale(False)
            raw = np.array(var[:])
            fill = var.getncattr("_FillValue") if "_FillValue" in var.ncattrs() else None
            scale = var.getncattr("scale_factor") if "scale_factor" in var.ncattrs() else 1
            vr = var.getncattr("valid_range") if "valid_range" in var.ncattrs() else None
            units = var.getncattr("units") if "units" in var.ncattrs() else ""
            long_name = var.getncattr("long_name") if "long_name" in var.ncattrs() else var.name
            if vr is not None:
                vmin, vmax = int(vr[0]), int(vr[1])
                valid = (raw != fill) & (raw >= vmin) & (raw <= vmax) if fill is not None else (raw >= vmin) & (raw <= vmax)
            else:
                valid = raw != fill if fill is not None else np.ones(raw.shape, bool)
            n_pix, n_valid = raw.size, int(valid.sum())
            is_vi = var.name.startswith("CMG_0_05") or "NDVI" in var.name or "EVI" in var.name
            if is_vi:
                scaled = raw[valid].astype(np.float64) / 10000.0
                scale_note = "raw/10000 (file scale_factor attr is 10000; do not auto-scale)"
                units_out = "index"
            else:
                scaled = raw[valid].astype(np.float64) * float(scale)
                scale_note = f"raw x {scale}"
                units_out = units or "K"
            add(category="observational", status="available", source_folder="modis_lpdaac",
                product=f"{label} sample NetCDF (DAP4 Ukraine subset)",
                variable=var.name, description=f"{long_name} (pixel-level sample, not the full time series)",
                units=units_out, spatial_unit=f"0.05deg pixel in {raw.shape[0]} x {raw.shape[1]} window",
                temporal_resolution="single monthly granule (sample)",
                date_first=p.name.split("_")[1] if "_" in p.name else "", date_last="",
                n_records=int(n_pix), n_spatial_units=int(n_pix), n_spatial_reporting=n_valid,
                n_missing=n_pix-n_valid, pct_missing=pct(n_pix-n_valid, n_pix),
                fill_values=f"_FillValue={fill}; valid_range={list(vr) if vr is not None else 'n/a'}; {scale_note}",
                qc_notes="QA layers were not in the DAP4 subset. Valid = fill/range only. Stats from the first sample file; 8 samples exist (4 VI, 4 LST).",
                min=fnum(scaled.min()) if n_valid else "", max=fnum(scaled.max()) if n_valid else "",
                mean=fnum(scaled.mean()) if n_valid else "",
                caveats=f"{len(files)} sample files in modis_lpdaac/samples/. Pixel window is the bbox, not a Ukraine polygon.",
                files="; ".join(rel(f) for f in files))
        ds.close()
    describe_sample("MOD13C2_*.dap.nc4", "MOD13C2.061")
    describe_sample("MOD11C3_*.dap.nc4", "MOD11C3.061")

def analyze_hydrocron():
    print("Hydrocron...")
    folder = ROOT / "swot_hydrocron"
    path = folder / "hydrocron_ukraine_reaches.csv"
    df = pd.read_csv(path)
    n_reach = df["reach_id"].nunique()
    d0, d1 = str(df["time_str"].min()), str(df["time_str"].max())
    empty = [f.name for f in sorted(folder.glob("reach_*.csv")) if f.stat().st_size <= 200]
    nonempty = [f.name for f in sorted(folder.glob("reach_*.csv")) if f.stat().st_size > 200]
    n_usable = int(df["usable"].sum()) if "usable" in df.columns else ""
    for var, abs_gt in [("wse",1e11),("wse_u",1e11),("width",1e11),("width_u",1e6),
                        ("area_total",1e11),("slope",1e11),("reach_q",None),
                        ("dark_frac",1e11),("ice_clim_f",None),("ice_dyn_f",None),("dschg_c",1e11)]:
        desc, units, product = DESC.get(var, (var, "", "SWOT Hydrocron"))
        masked = swot_mask(df[var], also_abs_gt=abs_gt if abs_gt else None)
        n_total = len(df); n_miss = int(masked.isna().sum()); good = masked.dropna()
        add(category="observational", status="available", source_folder="swot_hydrocron", product=product,
            variable=var, description=desc, units=units,
            spatial_unit=f"SWOT RiverSP reach ({n_reach} with data; {len(empty)} requested IDs returned no series)",
            temporal_resolution="irregular (each SWOT overpass)", date_first=d0, date_last=d1,
            n_records=n_total, n_spatial_units=n_reach+len(empty), n_spatial_reporting=n_reach,
            n_missing=n_miss, pct_missing=pct(n_miss, n_total),
            fill_values="-999, -999999999999; |x|>=1e11 treated as fill" + ("; |x|>=1e6 also fill-like for width_u" if var=="width_u" else ""),
            qc_notes=(f"Analysis drops fill, reach_q>2, ice_clim_f>=1, dark_frac>0.5. {n_usable} usable of {n_total} obs. "
                      "ice_dyn_f and dschg_c are fill in every row of this extract."),
            min=fnum(good.min()) if len(good) else "", max=fnum(good.max()) if len(good) else "",
            mean=fnum(good.mean()) if len(good) else "", median_record_length_years=3.3,
            caveats=("Operational record is only ~3.3 years (2023-2026) — too short for a climate trend. "
                     "2026 runs through mid-November. Kherson / lower Dnipro may include the Kakhovka dam breach (a step, not a trend). "
                     "The reach once labelled Lviv_Dniester is the lower Dniester (29.59E, 46.81N). "
                     f"Empty reach files: {', '.join(empty) if empty else 'none'}."),
            files=f"{rel(path)}; plus {len(nonempty)} per-reach CSVs and {len(empty)} empty reach CSVs")

def shp_to_df(path: Path) -> pd.DataFrame:
    r = shapefile.Reader(str(path))
    names = [f[0] for f in r.fields if f[0] != "DeletionFlag"]
    recs = [list(rec) for rec in r.records()]
    r.close()
    return pd.DataFrame(recs, columns=names)

def shp_desc(name: str):
    known = {
        "reach_id": ("SWORD reach identifier",""), "time": ("Time of observation, seconds since 2000-01-01","s"),
        "time_tai": ("Time in TAI","s"), "time_str": ("UTC timestamp",""),
        "p_lat": ("Prior reach-center latitude","degrees_north"), "p_lon": ("Prior reach-center longitude","degrees_east"),
        "river_name": ("River name from SWORD (often no_data)",""), "wse": ("Water-surface elevation","m"),
        "wse_u": ("WSE uncertainty","m"), "width": ("Reach width","m"), "width_u": ("Width uncertainty","m"),
        "slope": ("Water-surface slope","m/m"), "area_total": ("Total water area","m2"),
        "reach_q": ("Reach quality flag 0-3","flag"), "dark_frac": ("Dark-water fraction","fraction"),
        "ice_clim_f": ("Climatological ice flag","flag"), "ice_dyn_f": ("Dynamic ice flag","flag"),
        "dschg_c": ("Constrained discharge","m3/s"), "obs_frac_n": ("Fraction of nodes observed","fraction"),
    }
    if name in known: return known[name]
    if name.startswith("dschg_"): return (f"SWOT discharge-related field {name}", "")
    return (f"SWOT RiverSP reach attribute {name}", "")

def analyze_swot_sample():
    print("SWOT sample...")
    folder = ROOT / "swot_sample"
    p012 = next((folder/"extract").glob("*.shp"))
    p540 = next((folder/"extract_540").glob("*.shp"))
    try:
        df012, df540 = shp_to_df(p012), shp_to_df(p540)
    except Exception as e:
        read_errors.append(f"Shapefile read failed: {e}")
        add(category="observational", status="read_error", source_folder="swot_sample",
            product="SWOT RiverSP Reach shapefile", variable="(unreadable)", description=str(e),
            files=f"{rel(p012)}; {rel(p540)}", caveats="Shapefile could not be read.")
        return
    def in_bbox(df):
        lat, lon = pd.to_numeric(df["p_lat"], errors="coerce"), pd.to_numeric(df["p_lon"], errors="coerce")
        return (lon>=BBOX["lon_min"])&(lon<=BBOX["lon_max"])&(lat>=BBOX["lat_min"])&(lat<=BBOX["lat_max"])
    n012_bbox = int(in_bbox(df012).sum())
    sub = df540.loc[in_bbox(df540)].copy()
    n540 = len(sub)
    for col in sub.columns:
        desc, units = shp_desc(col)
        if col in ("reach_id","time_str","river_name","rch_id_up","rch_id_dn"):
            n_miss = int((sub[col].isna() | (sub[col].astype(str).isin(["","no_data"]))).sum())
            mn = mx = me = ""
        else:
            masked = swot_mask(sub[col], also_abs_gt=1e11)
            if col.endswith("_u"):
                masked = masked.where(masked.abs() < 1e6)
            n_miss = int(masked.isna().sum()); good = masked.dropna()
            mn, mx, me = (fnum(good.min()), fnum(good.max()), fnum(good.mean())) if len(good) else ("","","")
        add(category="observational", status="available", source_folder="swot_sample",
            product="SWOT L2 HR RiverSP Reach, Version D — single-pass shapefiles",
            variable=col, description=desc, units=units,
            spatial_unit=f"RiverSP reach, pass 540 (2023-08-09), centroid in Ukraine bbox ({n540} of {len(df540)})",
            temporal_resolution="single overpass (not a time series)", date_first="2023-08-09", date_last="2023-08-09",
            n_records=n540, n_spatial_units=n540, n_spatial_reporting=n540,
            n_missing=n_miss, pct_missing=pct(n_miss, n540) if n540 else "",
            fill_values="-999, -999999999999; many discharge/constrained fields are entirely fill",
            qc_notes="Stats for pass 540 reaches whose SWORD centroid is in the bbox. QA fields present but not filtered here.",
            min=mn, max=mx, mean=me,
            caveats=(f"Pass 012 (2023-03-29) has {len(df012)} Europe-swath reaches and {n012_bbox} in the Ukraine bbox — it does not intersect Ukraine. "
                     "These are one-day snapshots, not climate records. Use Hydrocron for time series."),
            files=f"{rel(p540)}; also {rel(p012)}; zips and {rel(folder/'ukraine_bbox_reaches_pass540_20230809.csv')}")

def analyze_cmr():
    print("CMR...")
    path = ROOT / "swot_cmr_metadata" / "swot_ukraine_bbox_cmr_summary.json"
    try:
        data = json.loads(path.read_text())
    except Exception as e:
        read_errors.append(f"CMR JSON: {e}"); return
    q = data.get("query", {})
    for c in data.get("collections", []):
        add(category="metadata", status="metadata_only", source_folder="swot_cmr_metadata",
            product=c.get("short_name",""), variable="(granule inventory, no data files)",
            description=c.get("note") or c.get("sample_main_file") or "CMR granule count for the Ukraine bbox intersection",
            spatial_unit="CMR bbox intersection (not a Ukraine clip)", temporal_resolution="granule / pass",
            date_first=str(c.get("first_start","")), date_last=str(c.get("last_end","")),
            n_records=c.get("hits",""), qc_notes="Metadata only. Data files were not downloaded.",
            caveats=str(data.get("size_guidance","")) + " Checked " + str(q.get("checked_at","")), files=rel(path))

def analyze_appeears():
    print("AppEEARS...")
    folder = ROOT / "appeears_metadata"
    avail = pd.read_csv(folder / "appeears_available_products.csv")
    relv = pd.read_csv(folder / "appeears_products_relevant_for_trends.csv")
    add(category="metadata", status="metadata_only", source_folder="appeears_metadata",
        product="AppEEARS product catalog (open API)", variable="(catalog only — no rasters)",
        description=f"Full catalog: {len(avail)} products. Curated 'relevant for trends' list: {len(relv)} products. Task API with the bearer was rejected (HTTP 403).",
        spatial_unit="n/a (no data downloaded)", temporal_resolution="n/a", n_records=len(avail),
        qc_notes="GET /api/product without auth returned HTTP 200. Authenticated task API returned 403.",
        caveats="MODIS monthly NDVI/LST was fetched via LP DAAC DAP4 instead. 1 km MOD11A2 and MCD12Q1 remain blocked until an AppEEARS username/password login works.",
        files=f"{rel(folder/'appeears_available_products.csv')}; {rel(folder/'appeears_products_relevant_for_trends.csv')}")

def analyze_derived():
    print("Derived...")
    folder = ROOT / "analysis"
    series_files = {
        "power_T2M_bbox_annual.csv": ("POWER T2M annual bbox mean", "°C", "value"),
        "power_T2M_MAX_bbox_annual.csv": ("POWER T2M_MAX annual (mean of monthly maxima, not ANN extreme)", "°C", "value"),
        "power_T2M_MIN_bbox_annual.csv": ("POWER T2M_MIN annual (mean of monthly minima, not ANN extreme)", "°C", "value"),
        "power_PRECTOTCORR_bbox_annual_mm.csv": ("POWER PRECTOTCORR annual total (mm/day x days, summed)", "mm/year", "value"),
        "power_QV2M_bbox_annual.csv": ("POWER QV2M annual bbox mean", "g/kg", "value"),
        "power_WS10M_bbox_annual.csv": ("POWER WS10M annual bbox mean", "m/s", "value"),
        "power_ALLSKY_SFC_SW_DWN_bbox_annual.csv": ("POWER all-sky SW annual bbox mean (starts 1984)", "kWh/m2/day", "value"),
        "gsom_TAVG_anomaly_1981-2025.csv": ("GSOM long-record TAVG annual anomaly vs 1991-2020 (gap 2020-2024)", "°C", "anomaly"),
        "gsom_TAVG_anomaly_1961-2025.csv": ("GSOM TAVG annual anomaly 1961-2025", "°C", "anomaly"),
        "gsom_PRCP_anomaly_1981-2025.csv": ("GSOM long-record PRCP annual anomaly 1981-2025 (thin in the 2020s)", "mm", "anomaly"),
        "gsom_PRCP_anomaly_1950-2000.csv": ("GSOM PRCP annual anomaly 1950-2000 (better coverage)", "mm", "anomaly"),
        "ghcn_daily_T_anomaly_1981-2025.csv": ("GHCN-Daily long-record annual temperature anomaly vs 1991-2020", "°C", "anomaly"),
        "ghcn_daily_P_anomaly_1981-2025.csv": ("GHCN-Daily annual precipitation anomaly (few stations in the 2020s)", "mm", "anomaly"),
        "modis_NDVI_annual.csv": ("MODIS NDVI annual bbox mean, 2001-2025", "index", "value"),
        "modis_EVI_annual.csv": ("MODIS EVI annual bbox mean, 2001-2025", "index", "value"),
        "modis_EVI_AMJJAS.csv": ("MODIS EVI Apr-Sep mean, 2001-2025", "index", "value"),
        "modis_EVI_JJA.csv": ("MODIS EVI JJA mean, 2001-2025", "index", "value"),
        "modis_NDVI_AMJJAS.csv": ("MODIS NDVI Apr-Sep mean, 2001-2025", "index", "value"),
        "modis_NDVI_JJA.csv": ("MODIS NDVI JJA mean, 2001-2025", "index", "value"),
        "modis_LST_Day_annual_C.csv": ("MODIS daytime LST annual bbox mean, 2001-2025", "°C", "value"),
        "modis_LST_Night_annual_C.csv": ("MODIS night-time LST annual bbox mean, 2001-2025", "°C", "value"),
        "modis_LST_Day_JJA_C.csv": ("MODIS daytime LST JJA, 2001-2025", "°C", "value"),
        "modis_LST_Day_MAM_C.csv": ("MODIS daytime LST MAM, 2001-2025", "°C", "value"),
        "modis_LST_Night_JJA_C.csv": ("MODIS night-time LST JJA, 2001-2025", "°C", "value"),
        "modis_LST_Night_DJF_C.csv": ("MODIS night-time LST DJF, 2001-2025", "°C", "value"),
    }
    for fname, (desc, units, valcol_pref) in series_files.items():
        p = folder / fname
        if not p.exists():
            read_errors.append(f"Missing derived file {p}"); continue
        df = pd.read_csv(p)
        valcol = valcol_pref if valcol_pref in df.columns else ("value" if "value" in df.columns else df.columns[-1])
        nums = pd.to_numeric(df[valcol], errors="coerce")
        years = pd.to_numeric(df["year"], errors="coerce") if "year" in df.columns else pd.Series(dtype=float)
        add(category="derived", status="derived", source_folder="analysis",
            product="Revised analysis tables (14 Nov 2026 methods)", variable=fname.replace(".csv",""),
            description=desc, units=units, spatial_unit="bbox mean or long-record station mean",
            temporal_resolution="annual",
            date_first=str(int(years.min())) if len(years.dropna()) else "",
            date_last=str(int(years.max())) if len(years.dropna()) else "",
            n_records=int(nums.notna().sum()), n_missing=int(nums.isna().sum()),
            pct_missing=pct(int(nums.isna().sum()), len(nums)),
            qc_notes="Derived from the observational extracts with the revised methods (drop incomplete 2026; drop MODIS year 2000).",
            min=fnum(nums.min()), max=fnum(nums.max()), mean=fnum(nums.mean()), files=rel(p))
    extra_docs = {
        "trend_summary.csv": "Revised trend tests for 46 series (OLS, AR(1), HAC, Theil-Sen, MK, Hamed-Rao lag-3, TFPW, Bonferroni/BH). Use this, not earlier notes.",
        "headline_findings.txt": "Plain-language headline findings after the methods revision.",
        "modis_findings.txt": "MODIS-specific findings and caveats.",
        "swot_findings.txt": "SWOT Hydrocron findings and caveats.",
        "swot_kherson_kakhovka_step.json": "Seasonally matched and dummy-variable tests of a Kakhovka step at Kherson; not a linear trend.",
        "swot_quality_flag_counts.csv": "Per-reach counts of ice, dark water, and usable observations.",
        "swot_hydrocron_site_summary.csv": "Per-site usable-record summary.",
        "swot_hydrocron_monthly_wse.csv": "Monthly WSE series (usable observations) by site.",
        "gsom_longrecord_TAVG_counts_by_year.csv": "Long-record GSOM TAVG station counts by year (shows the 2020-2024 hole).",
        "gsom_TAVG_station_trends_1981-2025.csv": "Per-station TAVG trends for the 9 long-record stations.",
        "gsom_station_counts_TAVG.csv": "GSOM stations reporting TAVG by year.",
        "gsom_station_counts_PRCP.csv": "GSOM stations reporting PRCP by year.",
        "power_T2M_gridcell_trends.csv": "Per-grid-cell POWER T2M trends (464 MERRA-2 cells).",
        "ghcn_daily_derived_annual.csv": "Per-station annual tmean and precip for the 28 GHCN stations.",
        "power_T2M_bbox_seasons.csv": "POWER T2M seasonal bbox means (DJF, MAM, JJA, SON).",
        "modis_lst_monthly_climatology_2001-2025.csv": "MODIS LST day/night monthly climatology 2001-2025.",
        "modis_ndvi_evi_monthly_climatology_2001-2025.csv": "MODIS NDVI/EVI monthly climatology 2001-2025.",
    }
    already = {k.replace(".csv","") for k in series_files}
    for fname, desc in extra_docs.items():
        p = folder / fname
        if not p.exists() or p.stem in already: continue
        n, cols = "", ""
        if p.suffix == ".csv":
            df = pd.read_csv(p); n = len(df)
            cols = ", ".join(df.columns.tolist()[:12]) + ("..." if len(df.columns)>12 else "")
        add(category="derived", status="derived", source_folder="analysis",
            product="Revised analysis tables (14 Nov 2026 methods)", variable=p.stem,
            description=desc, n_records=n, qc_notes=(f"Columns: {cols}" if cols else ""),
            caveats="Not raw observations. Prefer headline_findings.txt and trend_summary.csv over earlier notes.",
            files=rel(p))

def analyze_not_pulled():
    print("Not-yet-pulled / still blocked...")
    # GES DISC is now approved and verified (MERRA-2 monthly and GLDAS NOAH 0.25 monthly download with EARTHDATA_TOKEN).
    accessible = [
        dict(variable="MERRA-2 M2TMNXSLV (monthly 2-D single-level diagnostics)",
             product="M2TMNXSLV.5.12.4", units="various",
             description="Native GES DISC monthly MERRA-2 meteorology. POWER already supplies T2M and PRECTOTCORR for this bbox without GES DISC; this collection is the native archive (more fields, global files).",
             caveats="GES DISC app is now approved and verified; MERRA-2 monthly downloads work with the EARTHDATA_TOKEN bearer. Not yet pulled into $UKRAINE_SAMPLES/."),
        dict(variable="MERRA-2 M2TMNXFLX (monthly surface flux / precip)",
             product="M2TMNXFLX.5.12.4", units="various",
             description="Native GES DISC monthly MERRA-2 flux collection, including precipitation. Overlaps POWER PRECTOTCORR.",
             caveats="GES DISC now accessible; not yet pulled."),
        dict(variable="GLDAS_NOAH025_M 2.1 soil moisture and other Noah LSM fields",
             product="GLDAS_NOAH025_M.2.1", units="kg/m2 (soil moisture) and others",
             description="Monthly 0.25deg Noah land-surface model: soil moisture layers, evapotranspiration, runoff. Needed for a farmer-relevant moisture story.",
             caveats="GES DISC is now approved and verified; GLDAS NOAH 0.25 monthly downloads work with the EARTHDATA_TOKEN bearer. Not yet pulled."),
        dict(variable="GPM IMERG monthly precipitation (3IMERGM)",
             product="GPM_3IMERGM V07", units="mm",
             description="Satellite precipitation, 0.1deg, monthly. Independent check on POWER/station precip.",
             caveats="GES DISC app is now approved. This collection was previously blocked by the same EULA; it has not yet been pulled, and was not in the MERRA-2/GLDAS verification note."),
        dict(variable="AIRS3STM 7.0 monthly atmospheric temperature/humidity",
             product="AIRS3STM 7.0", units="K, mixing ratio, etc.",
             description="AIRS monthly standard retrievals.",
             caveats="GES DISC app is now approved. Not yet pulled; not in the MERRA-2/GLDAS verification note."),
        dict(variable="OMI OMNO2d tropospheric NO2",
             product="OMNO2d 004", units="molecules/cm2",
             description="Daily OMI nitrogen dioxide. Atmosphere / air-quality variable from the challenge list.",
             caveats="GES DISC app is now approved. Not yet pulled; not in the MERRA-2/GLDAS verification note."),
    ]
    for b in accessible:
        add(category="not_yet_pulled", status="now accessible, not yet pulled",
            source_folder="login_required", product=b["product"], variable=b["variable"],
            description=b["description"], units=b["units"], spatial_unit="not yet downloaded",
            temporal_resolution="n/a",
            qc_notes="GES DISC EULA was approved and verified on 14 Nov 2026 (Europe/Kiev). MERRA-2 monthly and GLDAS NOAH 0.25 monthly download with the EARTHDATA_TOKEN bearer.",
            caveats=b["caveats"], files="login_required.md (status superseded for GES DISC archive access)")
    still = [
        dict(variable="GRACE / GRACE-FO mascon terrestrial water storage",
             product="TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4", units="cm water equivalent",
             description="Monthly equivalent water height, 2002-present. The honest long-record hydrology complement to short SWOT reaches.",
             status="not_downloaded",
             caveats="Not a GES DISC EULA product (PO.DAAC). Not downloaded. The whole record is one ~44 MB NetCDF."),
        dict(variable="AppEEARS 1 km rasters (MOD11A2 LST, MCD12Q1 land cover, etc.)",
             product="AppEEARS task API", units="various",
             description="1 km 8-day LST and land-cover masks needed for a true urban-vs-rural heat contrast. Catalog is present; rasters are not.",
             status="blocked",
             caveats="Still blocked: bearer token rejected (HTTP 403). Login endpoint expects username/password, not a bearer. 0.05deg CMG LST is too coarse to separate a district from a park."),
        dict(variable="KNMI Climate Explorer series",
             product="KNMI Climate Explorer", units="various",
             description="Station and gridded climate series from climexp.knmi.nl.",
             status="blocked",
             caveats="Still requires a one-time human check. Folder knmi_climexp/ is empty."),
        dict(variable="Hydrology data rods (Giovanni / hydro1 timeseries.cgi)",
             product="GES DISC Hydrology Time Series", units="various",
             description="Point time series of land-surface variables for Ukrainian cities.",
             status="blocked",
             caveats="Separate from the archive EULA: timeseries.cgi returned SPA HTML, /data/timeseries/ returned HTTP 500, OPeNDAP 410 Gone. Not verified after the GES DISC approval. Use GLDAS monthly files once pulled, or Hydrocron for rivers."),
        dict(variable="RADARSAT Constellation Mission / Geo.ca",
             product="RCM / EODMS", units="",
             description="SAR imagery, not used.",
             status="blocked",
             caveats="EODMS account/licence required; no relevant open Ukraine extract. Out of scope."),
    ]
    for b in still:
        add(category="blocked" if b["status"]=="blocked" else "not_yet_pulled",
            status=b["status"] if b["status"]!="not_downloaded" else "not downloaded",
            source_folder="login_required", product=b["product"], variable=b["variable"],
            description=b["description"], units=b["units"], spatial_unit="not downloaded",
            temporal_resolution="n/a", qc_notes="See login_required.md for earlier HTTP statuses.",
            caveats=b["caveats"], files="login_required.md")

def _ann(path, val="value"):
    df = pd.read_csv(path)
    out = df[["year", val]].copy(); out.columns = ["year","value"]
    out["year"] = out["year"].astype(int)
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    return out.dropna()

def agree(a, b, name_a, name_b, units_per_decade):
    m = a.merge(b, on="year", suffixes=("_a","_b")).dropna()
    n = len(m)
    if n < 5:
        return {"pair": f"{name_a} vs {name_b}", "n": n, "years": "", "r": "", "note": "too few overlapping years"}
    r, p = stats.pearsonr(m["value_a"], m["value_b"])
    sa, _, _, pa, _ = stats.linregress(m["year"], m["value_a"])
    sb, _, _, pb, _ = stats.linregress(m["year"], m["value_b"])
    tsa = stats.theilslopes(m["value_a"], m["year"])[0]
    tsb = stats.theilslopes(m["value_b"], m["year"])[0]
    return {"pair": f"{name_a} vs {name_b}", "n": n,
            "years": f"{int(m.year.min())}-{int(m.year.max())}", "r": round(float(r), 3), "r_p": float(f"{p:.3g}"),
            "ols_a_per_dec": round(sa*10, 3), "ols_b_per_dec": round(sb*10, 3), "ols_diff": round((sa-sb)*10, 3),
            "sen_a_per_dec": round(tsa*10, 3), "sen_b_per_dec": round(tsb*10, 3), "units": units_per_decade}

def compute_overlaps():
    print("Overlaps...")
    A = ROOT / "analysis"
    power_t = _ann(A/"power_T2M_bbox_annual.csv")
    gsom_t = _ann(A/"gsom_TAVG_anomaly_1981-2025.csv", "raw")
    ghcn_t = _ann(A/"ghcn_daily_T_anomaly_1981-2025.csv", "raw")
    gsom_ta = _ann(A/"gsom_TAVG_anomaly_1981-2025.csv", "anomaly")
    ghcn_ta = _ann(A/"ghcn_daily_T_anomaly_1981-2025.csv", "anomaly")
    lst_d = _ann(A/"modis_LST_Day_annual_C.csv")
    lst_n = _ann(A/"modis_LST_Night_annual_C.csv")
    power_p = _ann(A/"power_PRECTOTCORR_bbox_annual_mm.csv")
    gsom_p = _ann(A/"gsom_PRCP_anomaly_1981-2025.csv", "anomaly")
    ghcn_p = _ann(A/"ghcn_daily_P_anomaly_1981-2025.csv", "anomaly")
    pairs = []
    pairs.append(agree(power_t, gsom_t, "POWER T2M (bbox, C)", "GSOM TAVG raw (UP long-record, C)", "C/decade"))
    pairs.append(agree(power_t, ghcn_t, "POWER T2M (bbox, C)", "GHCN-Daily tmean raw (UP long-record, C)", "C/decade"))
    pairs.append(agree(gsom_t, ghcn_t, "GSOM TAVG raw", "GHCN-Daily tmean raw", "C/decade"))
    pairs.append(agree(gsom_ta, ghcn_ta, "GSOM TAVG anomaly (1991-2020)", "GHCN-Daily T anomaly (1991-2020)", "C/decade"))
    p01 = power_t[(power_t.year>=2001)&(power_t.year<=2025)]
    pairs.append(agree(p01, lst_d, "POWER T2M 2001-2025", "MODIS LST Day 2001-2025", "C/decade"))
    pairs.append(agree(p01, lst_n, "POWER T2M 2001-2025", "MODIS LST Night 2001-2025", "C/decade"))
    pairs.append(agree(lst_d, lst_n, "MODIS LST Day", "MODIS LST Night", "C/decade"))
    pairs.append(agree(gsom_p, ghcn_p, "GSOM PRCP anomaly", "GHCN-Daily P anomaly", "mm/decade"))
    pairs.append(agree(gsom_p[gsom_p.year<=2000], ghcn_p[ghcn_p.year<=2000],
                       "GSOM PRCP anomaly 1981-2000", "GHCN-Daily P anomaly 1981-2000", "mm/decade"))
    base = power_p[(power_p.year>=1991)&(power_p.year<=2020)]["value"].mean()
    power_pa = power_p.copy(); power_pa["value"] = power_pa["value"] - base
    pairs.append(agree(power_pa, gsom_p, "POWER PRECTOTCORR anomaly vs 1991-2020", "GSOM PRCP anomaly", "mm/decade"))
    pairs.append(agree(power_pa, ghcn_p, "POWER PRECTOTCORR anomaly vs 1991-2020", "GHCN-Daily P anomaly", "mm/decade"))
    return pairs

def write_csv():
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "data_dictionary.csv"
    pd.DataFrame(rows).reindex(columns=COLS).to_csv(path, index=False)
    cov = OUT / "station_coverage.csv"
    cov_cols = ["source","station_id","name","latitude","longitude","elevation","country",
                "variable","date_first","date_last","n_valid","n_rows_in_archive",
                "n_missing_in_archive_rows","pct_missing_in_archive_rows","n_qc_removed","record_length_years"]
    pd.DataFrame(station_rows).reindex(columns=cov_cols).to_csv(cov, index=False)
    return path, cov

def md_esc(s):
    return str(s).replace("|", "\\|").replace("\n", " ")

def write_markdown(sizes, overlaps):
    path = OUT / "data_dictionary.md"
    n_obs = sum(1 for r in rows if r["category"]=="observational")
    n_der = sum(1 for r in rows if r["category"]=="derived")
    n_meta = sum(1 for r in rows if r["category"]=="metadata")
    n_blk = sum(1 for r in rows if r["category"]=="blocked")
    n_ntp = sum(1 for r in rows if r["category"]=="not_yet_pulled")
    L = []
    L.append("# Ukraine sample data dictionary")
    L.append("")
    L.append("NASA Space Apps 2026, *Be An Earth System Trend Detective!*  ")
    L.append("Computed from files in `$UKRAINE_SAMPLES/` on 14 November 2026 (Europe/Kiev). Numbers are not invented.")
    L.append("")
    L.append("## Overview")
    L.append("")
    L.append("- **Bounding box:** 22.1-40.2 E, 44.4-52.4 N — about twice Ukraine's area (~1.19 vs ~0.60 million km2). No country polygon or land mask.")
    L.append(f"- **Extract size on disk:** {fmt_bytes(sizes['total'])} ({sizes['total']:,} bytes).")
    L.append(f"- **Dictionary rows:** {len(rows)} ({n_obs} observational, {n_der} derived, {n_meta} metadata, {n_ntp} now accessible but not yet pulled, {n_blk} still blocked).")
    L.append("- **Usable now for trend analysis:** NASA POWER (1981-2025 meteorology; 1984-2025 solar), NOAA GSOM (204 UP stations, 1900-Oct 2026, with coverage caveats), GHCN-Daily (28 UP cities, 1879-Nov 2026), MODIS Terra monthly CMG NDVI/EVI and LST day/night (Feb 2000-Oct 2026).")
    L.append("- **Usable only as a short-record methods demo:** SWOT Hydrocron WSE (2023-2026, 8 reaches).")
    L.append("- **Now accessible, not yet pulled:** GES DISC is approved and verified (MERRA-2 monthly and GLDAS NOAH 0.25 monthly download with the EARTHDATA_TOKEN bearer). Native MERRA-2, GLDAS, and other GES DISC collections (GPM IMERG, AIRS, OMI) are not in the sample folder yet. GRACE mascons (PO.DAAC) were not downloaded.")
    L.append("- **Still blocked:** AppEEARS rasters (1 km LST, land cover), KNMI Climate Explorer, hydrology data-rod endpoints, RADARSAT.")
    L.append("")
    L.append("### Local folder sizes")
    L.append("")
    L.append("| Folder | Size | Role |")
    L.append("|---|---:|---|")
    for name, note in sizes["folders"]:
        L.append(f"| `{name}` | {fmt_bytes(sizes['folder_bytes'][name])} | {note} |")
    L.append("")
    if read_errors:
        L.append("### Read errors")
        for e in read_errors: L.append(f"- {e}")
        L.append("")
    L.append("## How to read the tables")
    L.append("")
    L.append("For station archives (GSOM 204 stations, GHCN 28 stations) the rows below are **per-variable aggregates**. Per-station coverage is in `station_coverage.csv`. Min / max / mean are after fill-value and QC-flag removal.")
    L.append("")
    groups = [
        ("nasa_power","NASA POWER"), ("noaa_gsom","NOAA GSOM"), ("noaa_ghcn","GHCN-Daily"),
        ("modis_lpdaac","MODIS LP DAAC"), ("swot_hydrocron","SWOT Hydrocron"),
        ("swot_sample","SWOT RiverSP sample shapefiles"), ("swot_cmr_metadata","SWOT CMR metadata"),
        ("appeears_metadata","AppEEARS catalog"), ("analysis","Derived analysis files"),
        ("login_required","Not yet pulled or still blocked"),
    ]
    main_cols = ["variable","description","units","spatial_unit","temporal_resolution","date_first","date_last",
                 "n_records","n_spatial_units","n_spatial_reporting","n_missing","pct_missing","fill_values",
                 "min","max","mean","status","caveats"]
    for folder, title in groups:
        subset = [r for r in rows if r["source_folder"]==folder]
        if not subset: continue
        L.append(f"## {title}")
        L.append("")
        if folder=="swot_sample" and len(subset)>20:
            L.append(f"{len(subset)} shapefile attributes for pass 540 reaches in the Ukraine bbox. Pass 012 has **no** Ukraine intersections. Full per-field stats are in `data_dictionary.csv`. Highlights:")
            L.append("")
            show = [r for r in subset if r["variable"] in {
                "wse","wse_u","width","slope","area_total","reach_q","dark_frac","ice_clim_f","ice_dyn_f",
                "dschg_c","obs_frac_n","p_lat","p_lon","river_name"}] or subset[:15]
        else:
            show = subset
        L.append("| " + " | ".join(main_cols) + " |")
        L.append("|" + "|".join(["---"]*len(main_cols)) + "|")
        for r in show:
            L.append("| " + " | ".join(md_esc(r.get(c,"")) for c in main_cols) + " |")
        L.append("")
        if folder=="swot_sample" and len(subset)>20:
            L.append(f"The CSV has all {len(subset)} fields, including discharge columns that are almost entirely fill.")
            L.append("")
    L.append("## Notable data-quality findings")
    L.append("")
    L.append("1. **GSOM precipitation coverage collapses after about 2000**, and long-record TAVG has **no data in 2020-2024**. Those holes dominate any station-based trend after the 1990s.")
    L.append("2. **POWER all-sky solar starts in 1984**, not 1981, and is spliced from SRB to CERES at **2001**. Treating 1984-2025 as one homogeneous series is unsafe.")
    L.append("3. **MODIS LST is not “warming faster than air temperature.”** The steeper LST slopes come from the shorter 2001-2025 window; POWER T2M over that same window is similar.")
    L.append("4. **SWOT is a 3.3-year operational record**, not a climate baseline. `ice_dyn_f` and `dschg_c` are fill in every Hydrocron row. Kherson includes the Kakhovka breach (a step, not a trend).")
    L.append("5. **SWOT fill-value traps:** official sentinels are `-999` and `-999999999999`. Some uncertainty fields also contain implausible values with `|x| > 1e6` (for example `width_u`). Pass 012 of the sample shapefile does not intersect Ukraine.")
    L.append("6. **The bbox is about twice Ukraine** and includes sea and neighbouring countries. POWER and MODIS means are bbox means, while GSOM/GHCN are Ukraine (UP) stations.")
    L.append("7. **GHCN-Daily precipitation in 2020-2024 rests on two stations**; 2025 temperature uses only 9 of 24 long-record stations. Partial **2026** must be dropped from climate annual trends.")
    L.append("8. **GES DISC is now approved**, so native MERRA-2, GLDAS soil moisture, and (likely) GPM/AIRS/OMI can be pulled. They are **not in the extract yet**. AppEEARS 1 km rasters and KNMI are still blocked. “Any variable” is not true of the files on disk today.")
    L.append("")
    L.append("Related files: `station_coverage.csv`, `data_overview_extras.md` (overlaps, global size, what we don’t need, preprocessing plan).")
    L.append("")
    path.write_text("\n".join(L))
    return path

def write_extras(sizes, overlaps):
    path = OUT / "data_overview_extras.md"
    power_dir = ROOT / "nasa_power"
    met_bytes = sum((power_dir/f"POWER_monthly_{v}_{t}_1981-2025.csv").stat().st_size
                    for v in ["T2M","T2M_MAX","T2M_MIN","PRECTOTCORR","QV2M","WS10M"] for t in ("west","east"))
    sol_bytes = sum((power_dir/f"POWER_monthly_ALLSKY_SFC_SW_DWN_{t}_1981-2025.csv").stat().st_size for t in ("west","east"))
    merra_global, merra_local = 576*360, 464
    ceres_global, ceres_local = 360*180, 144
    power_global = met_bytes*(merra_global/merra_local) + sol_bytes*(ceres_global/ceres_local)
    L = []
    L.append("# Ukraine sample data — overview extras")
    L.append("")
    L.append("14 November 2026, Europe/Kiev. Companion to `data_dictionary.md`. Overlap statistics are computed from the revised annual series in `$UKRAINE_SAMPLES/analysis/`. Global sizes use cited CMR / catalog / directory figures. GES DISC is now approved and verified (MERRA-2 monthly and GLDAS NOAH 0.25 monthly download with the EARTHDATA_TOKEN bearer); those sources are accessible but not yet pulled.")
    L.append("")
    L.append("## 1. Overlaps")
    L.append("")
    L.append("Several sources measure the same (or closely related) quantities. They do **not** share the same spatial support: POWER and MODIS are means over the wide bbox (land + some Black Sea + neighbours), while GSOM and GHCN-Daily are Ukraine (UP) stations, and the daily network is only 28 selected cities. Treat correlations as a consistency check, not a validation of a Ukraine-only average.")
    L.append("")
    L.append("### What overlaps")
    L.append("")
    L.append("| Theme | Sources | Spatial support | Overlapping period (complete years) |")
    L.append("|---|---|---|---|")
    L.append("| Air temperature | POWER T2M; GSOM TAVG; GHCN-Daily TAVG/TMAX/TMIN | 464 MERRA-2 cells in the bbox vs 204 UP monthly stations vs 28 UP daily stations (trends use long-record subsets) | 1981-2025, but GSOM long-record TAVG is **missing 2020-2024** |")
    L.append("| Land-surface vs air temperature | MODIS LST day/night (CMG 0.05deg) vs POWER T2M | Same bbox, different quantity (skin vs 2 m air) | **2001-2025** (drop MODIS 2000 and all 2026) |")
    L.append("| Precipitation | POWER PRECTOTCORR; GSOM PRCP; GHCN-Daily PRCP | Bbox reanalysis vs thinning UP stations | 1981-2025 on paper; GSOM PRCP coverage collapses after ~2000 and both station series are down to n=2 in several 2020s years |")
    L.append("| Vegetation | MODIS NDVI and EVI only (no second independent source in the extract) | Bbox CMG | 2001-2025 |")
    L.append("| Surface solar / wind | POWER only | CERES 1deg (solar, 1984-2025) and MERRA-2 (wind) | n/a (single source) |")
    L.append("| River water-surface elevation | SWOT Hydrocron only (too short to overlap a climate series) | 8 reaches, 2023-2026 | n/a |")
    L.append("")
    L.append("### Agreement over the common period")
    L.append("")
    L.append("Pearson *r* is on the overlapping annual values (equivalent to annual anomalies about the common-period mean). OLS and Theil-Sen slopes are per decade on those same years. GSOM temperature *raw* is the long-record network annual mean; GSOM 1981-2025 precipitation is stored as an anomaly only.")
    L.append("")
    L.append("| Pair | Overlap | n years | r | OLS slopes (A, B) | OLS difference (A-B) | Theil-Sen (A, B) | Units |")
    L.append("|---|---|---:|---:|---|---|---|---|")
    for p in overlaps:
        if p.get("r")=="":
            L.append(f"| {p['pair']} | {p.get('years','')} | {p['n']} | — | — | — | — | {p.get('note','')} |")
            continue
        L.append(f"| {p['pair']} | {p['years']} | {p['n']} | {p['r']} | {p['ols_a_per_dec']}, {p['ols_b_per_dec']} | {p['ols_diff']} | {p['sen_a_per_dec']}, {p['sen_b_per_dec']} | {p['units']} |")
    L.append("")
    L.append("**How to read this.** Air-temperature sources should agree closely on year-to-year anomalies; a high *r* with a slightly different slope is expected because the bbox includes sea and neighbours and because GSOM thins after 2012 and skips 2020-2024. LST is a different physical quantity: daytime LST is warmer than 2 m air, but the *trend* over 2001-2025 should be compared with POWER T2M over **that same window**. Precipitation agreement is weaker and is further limited by the post-2000 station-coverage collapse — the 1981-2000 subset is the fairer station-vs-station check.")
    L.append("")
    L.append("## 2. Global size estimate")
    L.append("")
    L.append("Rough storage if we pulled each dataset **globally**. Figures are documented catalog, directory, or CMR sizes, or a stated scale-up of our real POWER files. CMR queries were run on 14 November 2026. MB in CMR UMM are treated as 10^6-byte megabytes when converting to GB.")
    L.append("")
    L.append("| Dataset | Basis (cited) | Assumption | Global estimate | Ukraine extract we have |")
    L.append("|---|---|---|---:|---|")
    L.append(f"| MOD13C2.061 monthly VI CMG, Feb 2000-Oct 2026 | Earthdata catalog Dataset Size **98.1 MB**/granule; CMR hits **321** (matches our 321 months). README Harmony test: unsubsetted global HDF **101.30 MiB**. | 321 x 98.1 MB | {fmt_si(321*98.1*1e6)} (or {fmt_bytes(321*101.30*1024**2)} using the measured HDF) | DAP4 bbox subsets + 4 sample nc4 ({fmt_bytes(sizes['folder_bytes']['modis_lpdaac'])}) |")
    L.append(f"| MOD11C3.061 monthly LST CMG, same period | Earthdata catalog **70 MB**/granule; CMR hits **321**. | 321 x 70 MB | {fmt_si(321*70*1e6)} | included in the same folder |")
    L.append(f"| MOD11A2.061 8-day 1 km LST (not yet downloaded) | Earthdata catalog typical granule **3.6 MB**; live CMR hits **388,853**. A 400-granule CMR UMM sample had median **1.78 MB**, mean **2.53 MB**, max 9.59 MB. | Prefer sample mean; also show catalog typical. | **{fmt_si(388853*2.53*1e6)}** at 2.53 MB mean, or {fmt_si(388853*3.6*1e6)} at 3.6 MB | none (still blocked at AppEEARS) |")
    L.append(f"| NASA POWER monthly (the 7 parameters we have, 1981/1984-2025, global grid) | Our real CSV sizes ({fmt_bytes(met_bytes)} meteorology, {fmt_bytes(sol_bytes)} solar) scaled by cell count. MERRA-2 0.5x0.625 deg = {merra_global:,} cells vs our {merra_local}; CERES 1deg = {ceres_global:,} vs our {ceres_local}. | Same CSV layout, no extra parameters. | **{fmt_bytes(power_global)}** | {fmt_bytes(sizes['folder_bytes']['nasa_power'])} |")
    L.append(f"| GHCN-Daily, all stations | NCEI directory https://www.ncei.noaa.gov/pub/data/ghcn/daily/ : `ghcnd_all.tar.gz` is **3,826,010,800 bytes** (dated 2026-11-12). | Use the official tarball, not the old ~5 TB climate-mirror figure (that included a duplicated superghcnd tree). | **{fmt_bytes(3826010800)}** | 28 station files + inventories ({fmt_bytes(sizes['folder_bytes']['noaa_ghcn'])}) |")
    L.append(f"| NOAA GSOM (global monthly station summaries) | No single published archive size was found. Our extract is {fmt_bytes(sizes['folder_bytes']['noaa_gsom'])} for 204 UP stations (111,281 station-months). | A global figure is **not estimated** rather than inventing a station count. | unknown (not invented) | {fmt_bytes(sizes['folder_bytes']['noaa_gsom'])} |")
    L.append(f"| SWOT L2 HR RiverSP Reach, Version D, global | Live CMR hits **73,308**. UMM sizes on a 200-granule sample: min 0.23 MB, median **2.25 MB**, mean **3.05 MB**, max 17.6 MB. Our two sample zips are 2.0 MB and 4.08 MB. | 73,308 x sample mean (continent files vary a lot). | **{fmt_si(73308*3.05*1e6)}** (median would be {fmt_si(73308*2.25*1e6)}) | two sample granules + Hydrocron ({fmt_bytes(sizes['folder_bytes']['swot_sample']+sizes['folder_bytes']['swot_hydrocron'])}) |")
    L.append(f"| MERRA-2 M2TMNXSLV monthly (now accessible, not yet pulled) | CMR hits **561**; UMM sizes on 20 granules ~**51.7 MB** each (range 51.6-51.9 MB). | 561 x 51.75 MB (native GES DISC files, 1980-present). | **{fmt_si(561*51.75*1e6)}** | none yet |")
    L.append(f"| GLDAS_NOAH025_M 2.1 monthly (now accessible, not yet pulled) | CMR hits **319**; UMM and the GES DISC directory listing for 2024 both show **~24 MB**/month. | 319 x 24 MB, Jan 2000-present. | **{fmt_si(319*24*1e6)}** | none yet |")
    L.append(f"| GPM IMERG monthly 3IMERGM V07 (GES DISC approved, not yet pulled) | CMR hits **333**; UMM sample mean **17.3 MB** (median 17.5). The 2023 IMERG technical documentation said “about 30 MB”; we use live CMR sizes. | 333 x 17.3 MB. | **{fmt_si(333*17.3*1e6)}** | none yet |")
    L.append("| GRACE/GRACE-FO JPL mascon CRI RL06.3 v04 (not downloaded) | CMR: **1** granule, UMM size **44.22 MB** for `GRCTellus.JPL.200204_202609.GLO.RL06.3M.MSCNv04CRI.nc` (Apr 2002-Sep 2026). Non-CRI sibling is 38.98 MB. | The whole record is one NetCDF. | **44 MB** | none |")
    L.append(f"| AIRS3STM 7.0 monthly (GES DISC approved, not yet pulled) | CMR version 7.0 hits **290**; UMM mean ~**200 MB**. | 290 x 200 MB. | {fmt_si(290*200*1e6)} | none yet |")
    L.append(f"| OMI OMNO2d 004 daily (GES DISC approved, not yet pulled) | CMR version 004 hits **8,028**; UMM median ~**14.4 MB**. | Daily product; 8028 x 14.4 MB. Prefer a monthly composite for trends. | {fmt_si(8028*14.4*1e6)} | none yet |")
    L.append("")
    L.append("**Practical reading.** A global analysis-ready kit is still modest if we stick to monthly CMG MODIS (~54 GB for VI+LST), POWER-like monthly meteorology (a few GB as CSV), GHCN-Daily (3.8 GB compressed), GLDAS monthly (~7.7 GB), MERRA-2 SLV monthly (~29 GB), and GRACE (44 MB). The things that blow up are **1 km MOD11A2** (~1 TB) and **global SWOT RiverSP** (order 200 GB). Prefer Hydrocron or a subsetted RiverSP extract over a global shapefile haul.")
    L.append("")
    L.append("## 3. What we don’t need")
    L.append("")
    L.append("Out of scope for data analysis of climate trends, or redundant with something we already have. This is not a request to delete files from the shared disk.")
    L.append("")
    L.append("| Item | Why we don’t need it for the analysis |")
    L.append("|---|---|")
    L.append("| `swot_sample/` shapefiles, zips, and pass-540 preview PNG | Single-pass snapshots. Pass 012 has **zero** Ukraine-bbox reaches. Hydrocron is the SWOT time series. |")
    L.append("| Duplicate RiverSP zips once `extract/` and `extract_540/` exist | The unzipped shapefiles are enough; the zips only duplicate those bytes (~6 MB). |")
    L.append("| SWOT Hydrocron as a *climate-trend* input | 3.3-year record, ice/dark filters, Kakhovka step at Kherson, fill-only discharge. Keep it only as a “record too short / step vs trend” methods demo. |")
    L.append("| Empty Hydrocron reach CSVs (7 files, header only) | Those SWORD IDs are not in the default RiverSP-D collection. |")
    L.append("| Most SWOT RiverSP discharge columns (`dschg_*`) and `ice_dyn_f` | Entirely fill in the Hydrocron extract; mostly fill in the sample shapefile. |")
    L.append("| AppEEARS catalog JSON/CSV (193 products) | Metadata only. The CMG variables we needed were fetched via LP DAAC. |")
    L.append("| SWOT CMR granule-count JSON, once size guidance is recorded | Metadata for planning downloads, not a variable to analyse. |")
    L.append("| POWER `ANN` column for T2M_MAX and T2M_MIN | Annual extreme, not the annual mean. |")
    L.append("| Unused POWER parameters we never downloaded | Out of scope until a new science question needs them. |")
    L.append("| `knmi_climexp/` (empty) and `login_required/` (empty) | Placeholders. The useful content is `login_required.md`. |")
    L.append("| `_staging/legacy/` scripts | Retired; they used unit-index Sen slopes and would overwrite revised results. Do not run. |")
    L.append("| `charts/` | Visualization belongs to the other team. |")
    L.append("| `ghcnd-stations.txt` as a data series | It is the global station inventory (useful metadata), not a climate time series. |")
    L.append("| GSOM PRCP after ~2000 as a regional precipitation trend | Coverage collapse; a naive all-station series is not a climate signal. |")
    L.append("| Partial year 2026 in GSOM, GHCN, MODIS, SWOT | Incomplete year; already excluded from climate annual trends. |")
    L.append("| Native MERRA-2 T2M / PRECTOTCORR as a *replacement* for POWER | POWER already provides those for this bbox. Pull native MERRA-2 only if we need fields POWER does not have. GLDAS soil moisture *is* new and worth pulling. |")
    L.append("| RADARSAT / Geo.ca | Not downloaded; not needed for this trend analysis. |")
    L.append("")
    L.append("## 4. Preprocessing plan")
    L.append("")
    L.append("Ordered checklist for anyone computing trends from these extracts. It follows the revised methods in the sample README, plus the spatial and splice issues the review already flagged.")
    L.append("")
    L.append("1. **Decide the domain.** Replace the rectangular bbox with a Ukraine polygon (and a land mask for MODIS/POWER) before recomputing area means. Until then, disclose that the box is ~2x the country and includes sea and neighbours. If the bbox is retained, area-weight grid cells by `cos(latitude)` (a check on unweighted POWER T2M changed the 1981-2025 OLS rate only from +0.553 to +0.554 C/decade, but the polygon still matters for interpretation).")
    L.append("2. **Drop incomplete years** from climate annual trends: all of **2026**, and MODIS **2000** (starts in February). Hydrocron may keep 2026 only in the short-record methods demo.")
    L.append("3. **Apply fill values and scale factors before any statistic.** POWER: treat `-999` as missing. MODIS VI: `_FillValue=-3000`, valid range -2000 to 10000, then `raw/10000` (do not trust auto-scale: the file’s `scale_factor` attr is 10000). MODIS LST: `_FillValue=0`, valid range 7500-65535, then `raw x 0.02` (Kelvin). SWOT: mask `-999`, `-999999999999`, and implausible `|x|` (use >=1e11 for sentinels; also inspect uncertainty fields for `|x|>1e6`). GSOM: empty cells are missing (no sentinels in this extract). GHCN-Daily: convert tenths (TMAX/TMIN/TAVG/PRCP) and drop rows with a non-blank **QFLAG**.")
    L.append("4. **QC beyond fills.** MODIS: current series are fill/range only — if 1 km LST arrives, use QC bits and treat cloud gaps as missing, not zeros. SWOT: drop `reach_q>2`, `ice_clim_f>=1`, `dark_frac>0.5`; do not use `ice_dyn_f` (all fill). GHCN: do not treat MFLAG/SFLAG as failures. GSOM: no flag columns were downloaded.")
    L.append("5. **Units.** QV2M is **g/kg**, not kg/kg. PRECTOTCORR is mm/day — multiply by days in the month and sum to mm/year. LST comparisons with air temperature should be in C over the **same years**. Never use POWER `ANN` for T2M_MAX/T2M_MIN.")
    L.append("6. **Temporal aggregation.** Prefer **annual** or meteorological-season series so the seasonal cycle does not dominate the test. Build DJF from complete Dec-Feb winters only. For SWOT, monthly means are for the methods demo, not a 30-year trend.")
    L.append("7. **Anomalies.** For station temperature (and precip where used), take anomalies versus each station’s **1991-2020** mean, then average **long-record stations only**. For MODIS and POWER-vs-LST, use a common 2001-2025 window rather than mixing with 1981-2025 air-temperature anomalies.")
    L.append("8. **Station selection.** Declare the long-record rule up front. Disclose GSOM TAVG thinning (9 stations to 2012, 4 in 2013-2019 and 2025, **none in 2020-2024**) and that GSOM/GHCN PRCP in the 2020s can fall to n=2. Do not treat those years as a regional mean.")
    L.append("9. **Solar splice.** For `ALLSKY_SFC_SW_DWN`, either restrict trends to **2001-2025** (CERES only) or test a breakpoint at 2001 (SRB to CERES). Do not headline a 1984-2025 slope without that check. Data do not begin in 1981.")
    L.append("10. **Homogenization / breakpoints.** GSOM/GHCN are not homogenized in this extract. At least flag known network changes (post-2012 thinning, 2020-2024 hole, war-related 2022 gaps) and the Kakhovka **step** at Kherson (do not fit a linear trend there). A formal breakpoint test is desirable if time allows; it is not already in the tables.")
    L.append("11. **Trend tests.** Use time-aware Theil-Sen (against calendar year, not unit index). Report OLS with AR(1)-inflated errors and Newey-West HAC (lag 1 annual, lag 3 monthly), plus Hamed-Rao MK at **lag=3** (not the all-lag default) and TFPW. Call a result **robust** only if both HAC and Hamed-Rao p < 0.05. Watch negative lag-1 residual autocorrelation (Hamed-Rao can be anti-conservative). Do not use Yue-Wang for wording.")
    L.append("12. **Multiple testing.** Use the pre-declared primary family and the full family sizes already stored on `trend_summary.csv`, with Bonferroni and Benjamini-Hochberg flags. Do not call borderline seasonal tests “significant” in the headline.")
    L.append("13. **Cross-source check.** For any headline (especially temperature), show POWER, GSOM (with the gap disclosed), and GHCN together; for 2001-2025 also show MODIS LST. If they disagree, do not average them silently.")
    L.append("14. **New GES DISC / AppEEARS variables when pulled.** Apply the same fill, scale, QC, annual-aggregation, anomaly, and autocorrelation-aware tests. Priority pull: GLDAS soil moisture (new science). Native MERRA-2 is optional where POWER already covers T2M/PRECTOTCORR. For 1 km urban heat (still AppEEARS-blocked), define urban vs rural pixels from MCD12Q1, prefer night LST, and test the **urban-rural difference series** before claiming an intensifying UHI.")
    L.append("")
    path.write_text("\n".join(L))
    return path

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    analyze_power(); analyze_gsom(); analyze_ghcn(); analyze_modis()
    analyze_hydrocron(); analyze_swot_sample(); analyze_cmr(); analyze_appeears()
    analyze_derived(); analyze_not_pulled()
    folder_notes = [
        ("nasa_power","NASA POWER monthly CSVs"),
        ("noaa_gsom","GSOM 204 UP stations"),
        ("noaa_ghcn","GHCN inventories + 28 daily stations"),
        ("modis_lpdaac","MODIS monthly means + 8 sample NetCDFs"),
        ("swot_hydrocron","Hydrocron reach time series"),
        ("swot_sample","Two RiverSP shapefile granules"),
        ("swot_cmr_metadata","CMR granule counts (metadata)"),
        ("appeears_metadata","AppEEARS catalog (no rasters)"),
        ("analysis","Derived annual series and trend tables"),
        ("charts","PNG charts (other team's visualisation)"),
        ("_staging","Download and analysis scripts"),
        ("knmi_climexp","Empty — KNMI blocked"),
        ("login_required","Empty folder; see login_required.md"),
    ]
    fb = {name: folder_bytes(ROOT/name) for name,_ in folder_notes}
    sizes = {"total": folder_bytes(ROOT), "folders": folder_notes, "folder_bytes": fb}
    overlaps = compute_overlaps()
    csv_path, cov_path = write_csv()
    md_path = write_markdown(sizes, overlaps)
    extras_path = write_extras(sizes, overlaps)
    json_path = OUT / "data_dictionary_page.json"
    json_path.write_text(json.dumps({
        "n_rows": len(rows),
        "n_observational": sum(1 for r in rows if r["category"]=="observational"),
        "n_derived": sum(1 for r in rows if r["category"]=="derived"),
        "n_metadata": sum(1 for r in rows if r["category"]=="metadata"),
        "n_blocked": sum(1 for r in rows if r["category"]=="blocked"),
        "n_not_yet_pulled": sum(1 for r in rows if r["category"]=="not_yet_pulled"),
        "total_bytes": sizes["total"],
        "folder_bytes": fb,
        "overlaps": overlaps,
        "read_errors": read_errors,
        "rows": [{k: r.get(k,"") for k in COLS} for r in rows],
    }, default=str))
    print("Wrote", csv_path, "rows", len(rows))
    print("Wrote", cov_path, "rows", len(station_rows))
    print("Wrote", md_path)
    print("Wrote", extras_path)
    print("Wrote", json_path)
    if read_errors:
        print("READ ERRORS:", read_errors)
    # category counts
    from collections import Counter
    print("categories", Counter(r["category"] for r in rows))

if __name__ == "__main__":
    main()
