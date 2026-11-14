"""Loaders for pre-aggregated bbox tables, country series, stations, SWOT.

Pre-aggregated (merra2, gldas, imerg, airs, modis, omi, gpcc): the samples hold only the bbox
mean computed at download (cell centres, cos-lat), no grids. They are emitted ONLY for
region=ukraine_bbox and flagged; for any other region they are skipped (no fake masking).
Country series (CRU-CY, Berkeley country) are emitted ONLY for polygon regions named ukraine_*,
flagged with their own (different) country mask.
"""
from __future__ import annotations

import gzip
import io

import numpy as np
import pandas as pd

from ..core import SAMPLES, VARS, make_tidy
from ..regions import Region

BBOX_REGION = "ukraine_bbox"


def _read_commented(p):
    return pd.read_csv(p, comment="#")


def _bbox_only(region, src):
    if region.name != BBOX_REGION:
        return [], {"source": src, "status": "skipped",
                    "reason": "samples hold only a pre-computed Ukraine-bbox mean (no grid); not valid for this region"}
    return None


def _cols(df, var):
    n = f"{var}_n" if f"{var}_n" in df else None
    return df[var].to_numpy(float), (df[n].to_numpy(float) if n else None)


def _generic(region, src, path, date_col="date", n_max=None, extra_flags=None, date_fmt=None, rename=None):
    skip = _bbox_only(region, src)
    if skip:
        return skip
    df = pd.read_csv(path, comment="#")
    if rename:
        df = df.rename(columns=rename)
    dates = pd.DatetimeIndex(pd.to_datetime(df[date_col].astype(str).str[:7] + "-01"))
    out, notes = [], {"source": src, "status": "ok", "file": str(path), "variables": {}}
    for var in VARS[src]["variables"]:
        if var not in df:
            notes["variables"][var] = "column missing"; continue
        v, n = _cols(df, var)
        cov = n / (n_max or np.nanmax(n)) if n is not None else None
        fl = extra_flags(dates, var) if extra_flags else None
        out.append(make_tidy(src, var, region.name, dates, v, n, None, cov, flags=fl))
        notes["variables"][var] = "ok"
    return out, notes


def load_merra2(region):
    skip = _bbox_only(region, "merra2")
    if skip:
        return skip
    slv = pd.read_csv(SAMPLES / "merra2" / "merra2_slv_ukraine_monthly.csv")
    flx = pd.read_csv(SAMPLES / "merra2" / "merra2_flx_ukraine_monthly.csv")
    df = slv.merge(flx, on=["year", "month", "date"], how="outer", suffixes=("", "_flx"))
    dates = pd.to_datetime(df["date"] + "-01")
    out, notes = [], {"source": "merra2", "status": "ok", "checks": {}}
    for var in VARS["merra2"]["variables"]:
        if var not in df:  # add-on variables (wind, extremes) exist only in the global files
            notes.setdefault("not_in_extract", []).append(var); continue
        v, n = _cols(df, var)
        t = make_tidy("merra2", var, region.name, dates, v, n, None, n / 464.0)
        out.append(t)
    # conversion check vs extract's own mm/month column
    pr = out[[d["variable"].iloc[0] for d in out].index("PRECTOTCORR")]
    notes["checks"]["PRECTOTCORR_mm_vs_extract_maxabs"] = float(np.nanmax(np.abs(pr["value"].to_numpy() - df["PRECTOTCORR_mm"].to_numpy())))
    return out, notes


def _gldas(region, src, fname):
    skip = _bbox_only(region, src)
    if skip:
        return skip
    df = pd.read_csv(SAMPLES / "gldas" / fname)
    dates = pd.to_datetime(df["date"] + "-01")
    out, notes = [], {"source": src, "status": "ok", "checks": {}}
    for var in VARS[src]["variables"]:
        if var not in df:  # add-on variables (Rainf/Snowf) exist only in the global files
            notes.setdefault("not_in_extract", []).append(var); continue
        v, n = _cols(df, var)
        out.append(make_tidy(src, var, region.name, dates, v, n, None, n / np.nanmax(n)))
    byv = {d["variable"].iloc[0]: d for d in out}
    for ours, theirs in [("Qs_acc", "Qs_mm"), ("Qsb_acc", "Qsb_mm"), ("Evap_tavg", "Evap_mm")]:
        notes["checks"][f"{ours}_mm_vs_extract_maxabs"] = float(np.nanmax(np.abs(byv[ours]["value"].to_numpy() - df[theirs].to_numpy())))
    return out, notes


def load_gldas20(region):
    return _gldas(region, "gldas20", "gldas20_ukraine_monthly.csv")


def load_gldas21(region):
    return _gldas(region, "gldas21", "gldas21_ukraine_monthly.csv")


def load_imerg(region):
    r = _generic(region, "gpm_imerg", SAMPLES / "gpm_imerg" / "imerg_ukraine_monthly.csv")
    if r[0]:
        df = pd.read_csv(SAMPLES / "gpm_imerg" / "imerg_ukraine_monthly.csv")
        r[1]["checks"] = {"precip_mm_vs_extract_maxabs": float(np.nanmax(np.abs(r[0][0]["value"].to_numpy() - df["precip_mm"].to_numpy())))}
    return r


def load_airs(region):
    def fl(dates, var):
        return np.where(dates.year == 2025, "airs_2025_bias_unverified", "")
    return _generic(region, "airs", SAMPLES / "airs" / "airs_ukraine_monthly.csv", extra_flags=fl)


def load_modis(region):
    skip = _bbox_only(region, "modis")
    if skip:
        return skip
    out = []
    for f in ("MOD11C3_ukraine_monthly.csv", "MOD13C2_ukraine_monthly.csv"):
        df = pd.read_csv(SAMPLES / "modis_lpdaac" / f)
        dates = pd.to_datetime(df["month"] + "-01")
        for var in VARS["modis"]["variables"]:
            if var in df:
                v, n = _cols(df, var)
                out.append(make_tidy("modis", var, region.name, dates, v, n, None, n / 58443.0))
    return out, {"source": "modis", "status": "ok", "qc": "NO QC applied (no QA bits in DAP4 extract); Terra only; LST clear-sky"}


def load_omi(region):
    def fl(dates, var):
        return np.where(dates >= pd.Timestamp("2007-01-01"), "omi_row_anomaly_period", "")
    skip = _bbox_only(region, "omi")
    if skip:
        return skip
    df = pd.read_csv(SAMPLES / "omi" / "omno2d_ukraine_monthly.csv")
    dates = pd.DatetimeIndex(pd.to_datetime(df["date"] + "-01"))
    out = []
    for var in VARS["omi"]["variables"]:
        nd = df[f"{var}_n_days"].to_numpy(float)
        out.append(make_tidy("omi", var, region.name, dates, df[var].to_numpy(float), nd, None,
                             nd / dates.days_in_month.to_numpy(), flags=fl(dates, var)))
    return out, {"source": "omi", "status": "ok", "note": "n_valid = days with data; coverage = days/days_in_month"}


def load_gpcc(region):
    skip = _bbox_only(region, "gpcc")
    if skip:
        return skip
    df = _read_commented(SAMPLES / "extra" / "gpcc" / "gpcc_v2025_1deg_ukraine_bbox_monthly.csv")
    dates = pd.to_datetime(df["time"] + "-01")
    return [make_tidy("gpcc", "precip", region.name, dates, df["precip_mm"].to_numpy(float))], {"source": "gpcc", "status": "ok"}


# ---------------------------------------------------------------- country series
def _country_ok(region, src):
    if region.type != "polygon" or not region.name.startswith("ukraine"):
        return [], {"source": src, "status": "skipped", "reason": "country (Ukraine) series; only used for ukraine_mask* regions"}
    return None


def load_cru_cy(region):
    skip = _country_ok(region, "cru_cy")
    if skip:
        return skip
    out = []
    cols = {"tmp": "tmp_C", "tmp_anom": "tmp_C_anom_1961_1990", "tmn": "tmn_C", "tmx": "tmx_C", "dtr": "dtr_C",
            "pre": "pre_mm", "pet": "pet", "vap": "vap", "wet": "wet_days"}
    for var, col in cols.items():
        f = "tmp" if var == "tmp_anom" else var
        df = _read_commented(SAMPLES / "extra" / "cru_cy" / f"cru_cy_ukraine_{f}_monthly.csv")
        dates = pd.to_datetime(df["date"] + "-01")
        fl = ["own_country_mask;crimea_undocumented"] * len(df)
        if var == "tmp":
            fl = [x + ";absolute_not_anomaly" for x in fl]
        out.append(make_tidy("cru_cy", var, region.name, dates, df[col].to_numpy(float), flags=fl))
    return out, {"source": "cru_cy", "status": "ok", "mask": "CRU-CY country mask; Crimea in/out undocumented -> mask mismatch vs region"}


def load_berkeley_country(region):
    skip = _country_ok(region, "berkeley_country")
    if skip:
        return skip
    rows = []
    for line in (SAMPLES / "extra" / "berkeley_earth" / "ukraine-TAVG-Trend.txt").read_text().splitlines():
        if line.startswith("%") or not line.strip():
            continue
        p = line.split()
        rows.append((int(p[0]), int(p[1]), float(p[2])))
    df = pd.DataFrame(rows, columns=["y", "m", "v"])
    dates = pd.to_datetime(dict(year=df.y, month=df.m, day=1))
    fl = "own_country_mask;crimea_excluded;mask_mismatch_vs_region"  # every Ukraine region includes Crimea
    return [make_tidy("berkeley_country", "TAVG", region.name, dates, df["v"].to_numpy(), flags=[fl] * len(df))], \
        {"source": "berkeley_country", "status": "ok", "mask": "Berkeley polygon 553,101 km², 45.21-52.37N: Crimea EXCLUDED"}


# ---------------------------------------------------------------- stations
STN_BASE = (1991, 2020)
STN_MIN_BASE_YEARS = 15  # per station and calendar month; stations without it are not in the regional anomaly


def _station_regional(src, var, region, st: pd.DataFrame):
    """st: station, date, value (target units). Regional mean of station anomalies (1991-2020)."""
    st = st.dropna(subset=["value"]).copy()
    st["mo"] = st["date"].dt.month; st["yr"] = st["date"].dt.year
    inb = st["yr"].between(*STN_BASE)
    cnt = st[inb].groupby(["station", "mo"])["value"].count()
    clim = st[inb].groupby(["station", "mo"])["value"].mean()[cnt >= STN_MIN_BASE_YEARS]
    nmon = clim.groupby(level=0).size()
    last = st.groupby("station")["yr"].max()
    stats = dict(stations_with_data=int(st["station"].nunique()),
                 stations_with_any_baseline_month=int(len(nmon)),
                 stations_with_full_12month_baseline=int((nmon == 12).sum()),
                 stations_dropped_no_baseline=int(st["station"].nunique() - len(nmon)),
                 stations_ending_before_2006=int((last < 2006).sum()))
    st = st.join(clim.rename("clim"), on=["station", "mo"])
    st = st.dropna(subset=["clim"])
    st["anom"] = st["value"] - st["clim"]
    g = st.groupby("date")
    reg = pd.DataFrame({"anom": g["anom"].mean(), "n": g["station"].nunique()})
    full = pd.date_range(reg.index.min(), reg.index.max(), freq="MS")
    reg = reg.reindex(full)
    nst = st["station"].nunique()
    sp = dict(VARS[src]["variables"][var])
    sp["unit"] = sp["unit"].replace("°C", "°C anomaly (1991-2020)") if "°C" in sp["unit"] else sp["unit"] + " anomaly (1991-2020)"
    sp["valid_range"] = [-1e9, 1e9]
    sp["conversion"] = "none"
    t = make_tidy(src, var, region.name, reg.index, reg["anom"].to_numpy(), reg["n"].to_numpy(), None,
                  reg["n"].to_numpy() / max(nst, 1), sp=sp, out_name=f"{var}_anom",
                  flags=["station_anomaly_mean;UP_stations_only" + (";few_stations_lt3" if (np.isfinite(x) and x < 3) else "")
                         for x in reg["n"].to_numpy(float)])
    return t, stats


def _station_select(region, lat, lon):
    return region.contains_points(lon, lat)


def load_gsom(region):
    df = pd.read_csv(SAMPLES / "noaa_gsom" / "gsom_ukraine_UP_stations.csv")
    keep = _station_select(region, df["LATITUDE"].to_numpy(), df["LONGITUDE"].to_numpy())
    df = df[keep]
    dates = pd.to_datetime(df["DATE"] + "-01")
    out, notes = [], {"source": "gsom", "status": "ok", "n_stations_in_region": int(df["STATION"].nunique()), "variables": {}}
    stn_long = []
    for var in VARS["gsom"]["variables"]:
        st = pd.DataFrame({"station": df["STATION"].to_numpy(), "date": dates.to_numpy(), "value": df[var].to_numpy(float)})
        t, stats = _station_regional("gsom", var, region, st)
        out.append(t); notes["variables"][var] = stats
        stn_long.append(st.assign(variable=var))
    notes["station_table"] = pd.concat(stn_long).dropna(subset=["value"])
    return out, notes


def _ghcn_station_monthly(path: str) -> pd.DataFrame:
    d = pd.read_csv(path, header=None, usecols=[0, 1, 2, 3, 5], names=["id", "date", "el", "v", "q"],
                    dtype={"id": str, "date": str, "el": str, "v": float, "q": str})
    d = d[d["el"].isin(["TAVG", "TMAX", "TMIN", "PRCP"])]
    nq = int(d["q"].notna().sum())
    d = d[d["q"].isna()]  # QFLAG filter: drop any value with a quality flag
    d["month"] = pd.to_datetime(d["date"].str[:6] + "01", format="%Y%m%d")
    g = d.groupby(["el", "month"])["v"].agg(["count", "sum", "mean"]).reset_index()
    dim = g["month"].dt.days_in_month
    is_p = g["el"] == "PRCP"
    ok = np.where(is_p, (g["count"] >= 27) | (g["count"] == dim), g["count"] >= 20)
    g["value"] = np.where(is_p, g["sum"], g["mean"]) * 0.1  # tenths -> °C / mm
    g.loc[~ok, "value"] = np.nan
    g["station"] = d["id"].iloc[0] if len(d) else ""
    g.attrs["n_qflag_removed"] = nq
    return g.rename(columns={"count": "n_days"})[["station", "el", "month", "n_days", "value"]], nq


def load_ghcn(region):
    from concurrent.futures import ThreadPoolExecutor
    stations = pd.read_csv(SAMPLES / "noaa_ghcn" / "ukraine_bbox_stations.csv")
    files = sorted((SAMPLES / "noaa_ghcn" / "daily_by_station").glob("*.csv.gz"))
    ids = [f.name.split(".")[0] for f in files]
    meta = stations.set_index("id").reindex(ids)
    keep = _station_select(region, meta["lat"].to_numpy(), meta["lon"].to_numpy())
    files = [f for f, k in zip(files, keep) if k]
    with ThreadPoolExecutor(max_workers=2) as ex:
        res = list(ex.map(lambda f: _ghcn_station_monthly(str(f)), files))
    mon = pd.concat([r[0] for r in res], ignore_index=True)
    nq = int(sum(r[1] for r in res))
    out, notes = [], {"source": "ghcn", "status": "ok", "n_stations_in_region": len(files), "n_qflag_values_removed": nq, "variables": {}}
    for var in VARS["ghcn"]["variables"]:
        st = mon[mon["el"] == var].rename(columns={"month": "date"})[["station", "date", "value"]]
        if st.empty:
            continue
        t, stats = _station_regional("ghcn", var, region, st)
        stats["station_months_failing_day_rule"] = int(mon[(mon.el == var)]["value"].isna().sum())
        out.append(t); notes["variables"][var] = stats
    notes["station_table"] = mon.rename(columns={"el": "variable", "month": "date"})
    return out, notes


# ---------------------------------------------------------------- SWOT
def load_swot(region):
    skip = _bbox_only(region, "swot")
    if skip:
        return skip
    df = pd.read_csv(SAMPLES / "analysis" / "swot_hydrocron_monthly_wse.csv")
    out = []
    for site, g in df.groupby("site"):
        dates = pd.to_datetime(g["time"].str[:10])
        out.append(make_tidy("swot", "wse", region.name, dates, g["wse"].to_numpy(float), out_name=f"wse_{site}",
                             flags=["too_short_for_climate_inference;reach_not_regional"] * len(g)))
    return out, {"source": "swot", "status": "ok", "n_reaches": len(out)}
