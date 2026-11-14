#!/usr/bin/env python3
"""Independent recomputation for Ukraine trend-methods review. Does not modify ukraine_samples/."""
from __future__ import annotations

import calendar
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pymannkendall as mk
from scipy import stats
import statsmodels.api as sm

ROOT = Path("$UKRAINE_SAMPLES")
OUT = Path("team-context/team/reviews")
OUT.mkdir(exist_ok=True)
MONTHS = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]


def lag1(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 4:
        return np.nan
    return float(np.corrcoef(x[1:], x[:-1])[0, 1])


def ols_with_ar1(years, values):
    years = np.asarray(years, dtype=float)
    values = np.asarray(values, dtype=float)
    mask = np.isfinite(years) & np.isfinite(values)
    years, values = years[mask], values[mask]
    n = len(values)
    if n < 8:
        return None
    lr = stats.linregress(years, values)
    fitted = lr.intercept + lr.slope * years
    resid = values - fitted
    r = lag1(resid)
    r_series = lag1(values)
    # inflation of slope variance under AR(1)
    if np.isfinite(r) and abs(r) < 0.99:
        infl = math.sqrt((1 + r) / (1 - r)) if r > -0.99 else np.nan
        n_eff = n * (1 - r) / (1 + r) if r > -0.99 else n
    else:
        infl, n_eff = np.nan, n
    se = lr.stderr
    se_adj = se * infl if np.isfinite(infl) else np.nan
    if np.isfinite(se_adj) and se_adj > 0 and n_eff > 3:
        t_adj = lr.slope / se_adj
        df = max(n_eff - 2, 1)
        p_adj = float(2 * stats.t.sf(abs(t_adj), df))
        # 95% CI per decade
        tcrit = float(stats.t.ppf(0.975, df))
        ci_lo = (lr.slope - tcrit * se_adj) * 10
        ci_hi = (lr.slope + tcrit * se_adj) * 10
    else:
        t_adj, p_adj, ci_lo, ci_hi = np.nan, np.nan, np.nan, np.nan
    # classical CI
    tcrit_n = float(stats.t.ppf(0.975, n - 2))
    ci_lo_ols = (lr.slope - tcrit_n * se) * 10
    ci_hi_ols = (lr.slope + tcrit_n * se) * 10
    # HAC Newey-West lag 1 and lag 3
    X = sm.add_constant(years)
    model = sm.OLS(values, X).fit()
    hac = {}
    for nl in (1, 3):
        h = model.get_robustcov_results(cov_type="HAC", maxlags=nl)
        hac[f"hac{nl}_slope_decade"] = float(h.params[1] * 10)
        hac[f"hac{nl}_se_decade"] = float(h.bse[1] * 10)
        hac[f"hac{nl}_p"] = float(h.pvalues[1])
    # Sen's slope with actual time (per year) vs mk unit-index
    sen_time = stats.theilslopes(values, years)
    mk_orig = mk.original_test(values)
    try:
        mk_hr = mk.hamed_rao_modification_test(values)
        hr_p, hr_h, hr_z = float(mk_hr.p), bool(mk_hr.h), float(mk_hr.z)
    except Exception as e:
        hr_p, hr_h, hr_z = np.nan, None, np.nan
    try:
        mk_yw = mk.yue_wang_modification_test(values)
        yw_p, yw_h, yw_z = float(mk_yw.p), bool(mk_yw.h), float(mk_yw.z)
    except Exception as e:
        yw_p, yw_h, yw_z = np.nan, None, np.nan
    try:
        mk_pw = mk.trend_free_pre_whitening_modification_test(values)
        pw_p, pw_h = float(mk_pw.p), bool(mk_pw.h)
    except Exception:
        pw_p, pw_h = np.nan, None
    return {
        "n": n,
        "start": float(years.min()),
        "end": float(years.max()),
        "ols_decade": float(lr.slope * 10),
        "ols_p": float(lr.pvalue),
        "ols_se_decade": float(se * 10),
        "ols_ci95_lo": ci_lo_ols,
        "ols_ci95_hi": ci_hi_ols,
        "r_resid_lag1": r,
        "r_series_lag1": r_series,
        "n_eff_ar1": float(n_eff),
        "ols_p_ar1adj": p_adj,
        "ols_se_ar1adj_decade": float(se_adj * 10) if np.isfinite(se_adj) else np.nan,
        "ols_ci95_ar1_lo": ci_lo,
        "ols_ci95_ar1_hi": ci_hi,
        **hac,
        "sen_time_decade": float(sen_time[0] * 10),  # slope per year * 10
        "mk_orig_p": float(mk_orig.p),
        "mk_orig_h": bool(mk_orig.h),
        "mk_orig_sen_unitindex_x10": float(mk_orig.slope * 10),  # their method
        "mk_hr_p": hr_p,
        "mk_hr_h": hr_h,
        "mk_yw_p": yw_p,
        "mk_yw_h": yw_h,
        "mk_tfpw_p": pw_p,
        "mk_tfpw_h": pw_h,
        "ols_vs_sen_time_absdiff": abs(float(lr.slope * 10) - float(sen_time[0] * 10)),
        "ols_vs_their_sen_absdiff": abs(float(lr.slope * 10) - float(mk_orig.slope * 10)),
    }


def load_power(param: str) -> pd.DataFrame:
    frames = []
    for tile in ("west", "east"):
        path = ROOT / "nasa_power" / f"POWER_monthly_{param}_{tile}_1981-2025.csv"
        raw = path.read_text()
        body = raw.split("-END HEADER-\n", 1)[1]
        df = pd.read_csv(pd.io.common.StringIO(body))
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["YEAR", "LAT", "LON"], keep="first")
    for c in MONTHS + ["ANN"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").replace(-999, np.nan)
    return df


rows = []

# ---- saved annual/seasonal series ----
series_files = {
    "POWER_T2M": (ROOT / "analysis/power_T2M_bbox_annual.csv", "year", "value"),
    "POWER_PRECTOTCORR": (ROOT / "analysis/power_PRECTOTCORR_bbox_annual_mm.csv", "year", "value"),
    "POWER_T2M_MAX": (ROOT / "analysis/power_T2M_MAX_bbox_annual.csv", "year", "value"),
    "POWER_T2M_MIN": (ROOT / "analysis/power_T2M_MIN_bbox_annual.csv", "year", "value"),
    "POWER_QV2M": (ROOT / "analysis/power_QV2M_bbox_annual.csv", "year", "value"),
    "POWER_WS10M": (ROOT / "analysis/power_WS10M_bbox_annual.csv", "year", "value"),
    "POWER_ALLSKY_SW": (ROOT / "analysis/power_ALLSKY_SFC_SW_DWN_bbox_annual.csv", "year", "value"),
    "GSOM_TAVG_1981": (ROOT / "analysis/gsom_TAVG_anomaly_1981-2025.csv", "year", "anomaly"),
    "GSOM_TAVG_1961": (ROOT / "analysis/gsom_TAVG_anomaly_1961-2025.csv", "year", "anomaly"),
    "GSOM_PRCP_1950": (ROOT / "analysis/gsom_PRCP_anomaly_1950-2000.csv", "year", "anomaly"),
    "GHCN_T_1981": (ROOT / "analysis/ghcn_daily_T_anomaly_1981-2025.csv", "year", "anomaly"),
    "GHCN_P_1981": (ROOT / "analysis/ghcn_daily_P_anomaly_1981-2025.csv", "year", "anomaly"),
    "MODIS_NDVI_ann": (ROOT / "analysis/modis_NDVI_annual.csv", "year", "value"),
    "MODIS_EVI_ann": (ROOT / "analysis/modis_EVI_annual.csv", "year", "value"),
    "MODIS_EVI_AMJJAS": (ROOT / "analysis/modis_EVI_AMJJAS.csv", "year", "value"),
    "MODIS_EVI_JJA": (ROOT / "analysis/modis_EVI_JJA.csv", "year", "value"),
    "MODIS_NDVI_AMJJAS": (ROOT / "analysis/modis_NDVI_AMJJAS.csv", "year", "value"),
    "MODIS_NDVI_JJA": (ROOT / "analysis/modis_NDVI_JJA.csv", "year", "value"),
    "MODIS_LST_Day_ann": (ROOT / "analysis/modis_LST_Day_annual_C.csv", "year", "value"),
    "MODIS_LST_Night_ann": (ROOT / "analysis/modis_LST_Night_annual_C.csv", "year", "value"),
    "MODIS_LST_Day_JJA": (ROOT / "analysis/modis_LST_Day_JJA_C.csv", "year", "value"),
    "MODIS_LST_Night_JJA": (ROOT / "analysis/modis_LST_Night_JJA_C.csv", "year", "value"),
    "MODIS_LST_Day_MAM": (ROOT / "analysis/modis_LST_Day_MAM_C.csv", "year", "value"),
    "MODIS_LST_Night_DJF": (ROOT / "analysis/modis_LST_Night_DJF_C.csv", "year", "value"),
}

seasons = pd.read_csv(ROOT / "analysis/power_T2M_bbox_seasons.csv")
for col in ["DJF", "MAM", "JJA", "SON"]:
    tr = ols_with_ar1(seasons["year"], seasons[col])
    rows.append({"series": f"POWER_T2M_{col}", **tr})

for name, (path, yc, vc) in series_files.items():
    df = pd.read_csv(path)
    tr = ols_with_ar1(df[yc], df[vc])
    extra = {}
    if "n" in df.columns:
        extra["n_members_min"] = int(df["n"].min())
        extra["n_members_max"] = int(df["n"].max())
        extra["n_members_end"] = int(df["n"].iloc[-1])
        years_present = set(df[yc].astype(int))
        y0, y1 = int(df[yc].min()), int(df[yc].max())
        missing = sorted(set(range(y0, y1 + 1)) - years_present)
        extra["missing_years"] = ",".join(map(str, missing)) if missing else ""
    rows.append({"series": name, **tr, **extra})

# ---- SWOT monthly medians and month-of-year anomalies ----
sw = pd.read_csv(ROOT / "analysis/swot_hydrocron_monthly_wse.csv")
sw["time"] = pd.to_datetime(sw["time"], utc=True)
sw["year_frac"] = sw["time"].dt.year + (sw["time"].dt.dayofyear - 1) / 365.25
sw["month"] = sw["time"].dt.month
swot_detail = []
for site, g in sw.groupby("site"):
    g = g.sort_values("time")
    # month-of-year anomaly (same method as findings)
    clim = g.groupby("month")["wse_monthly_median"].transform("mean")
    g = g.copy()
    g["anom"] = g["wse_monthly_median"] - clim
    for kind, col in [("monthly_median", "wse_monthly_median"), ("moy_anomaly", "anom")]:
        tr = ols_with_ar1(g["year_frac"], g[col])
        rec = {"series": f"SWOT_{site}_{kind}", **tr, "n_months": len(g),
               "span_years": float((g["time"].max() - g["time"].min()).days / 365.25)}
        rows.append(rec)
        swot_detail.append(rec)

# ---- POWER T2M_MAX: ANN vs mean of monthly ----
tmax = load_power("T2M_MAX")
tmin = load_power("T2M_MIN")
t2m = load_power("T2M")
saved_max = pd.read_csv(ROOT / "analysis/power_T2M_MAX_bbox_annual.csv")
saved_min = pd.read_csv(ROOT / "analysis/power_T2M_MIN_bbox_annual.csv")
saved_t2m = pd.read_csv(ROOT / "analysis/power_T2M_bbox_annual.csv")

ann_max, monmean_max, ann_min, monmean_min, ann_t2m = [], [], [], [], []
for year, g in tmax.groupby("YEAR"):
    ann_max.append({"year": int(year), "value": g["ANN"].mean(skipna=True)})
    monmean_max.append({"year": int(year), "value": g[MONTHS].mean(axis=1).mean(skipna=True)})
for year, g in tmin.groupby("YEAR"):
    ann_min.append({"year": int(year), "value": g["ANN"].mean(skipna=True)})
    monmean_min.append({"year": int(year), "value": g[MONTHS].mean(axis=1).mean(skipna=True)})
for year, g in t2m.groupby("YEAR"):
    ann_t2m.append({"year": int(year), "value": g["ANN"].mean(skipna=True)})
ann_max = pd.DataFrame(ann_max)
monmean_max = pd.DataFrame(monmean_max)
ann_min = pd.DataFrame(ann_min)
monmean_min = pd.DataFrame(monmean_min)
ann_t2m = pd.DataFrame(ann_t2m)
cmp_max = saved_max.merge(ann_max, on="year", suffixes=("_saved", "_ANN"))
cmp_max = cmp_max.merge(monmean_max.rename(columns={"value": "value_monmean"}), on="year")
cmp_min = saved_min.merge(ann_min, on="year", suffixes=("_saved", "_ANN"))
cmp_min = cmp_min.merge(monmean_min.rename(columns={"value": "value_monmean"}), on="year")
tmax_id = {
    "saved_mean_1981": float(saved_max.loc[saved_max.year == 1981, "value"].iloc[0]),
    "ANN_spatial_mean_1981": float(ann_max.loc[ann_max.year == 1981, "value"].iloc[0]),
    "monthly_mean_spatial_1981": float(monmean_max.loc[monmean_max.year == 1981, "value"].iloc[0]),
    "max_abs_saved_minus_ANN": float((cmp_max["value_saved"] - cmp_max["value_ANN"]).abs().max()),
    "max_abs_saved_minus_monmean": float((cmp_max["value_saved"] - cmp_max["value_monmean"]).abs().max()),
    "tmin_saved_1981": float(saved_min.loc[saved_min.year == 1981, "value"].iloc[0]),
    "tmin_ANN_1981": float(ann_min.loc[ann_min.year == 1981, "value"].iloc[0]),
    "tmin_monmean_1981": float(monmean_min.loc[monmean_min.year == 1981, "value"].iloc[0]),
    "tmin_max_abs_saved_minus_ANN": float((cmp_min["value_saved"] - cmp_min["value_ANN"]).abs().max()),
    "tmin_max_abs_saved_minus_monmean": float((cmp_min["value_saved"] - cmp_min["value_monmean"]).abs().max()),
    "t2m_saved_vs_ANN_maxabs": float((saved_t2m.merge(ann_t2m, on="year", suffixes=("_s","_a"))["value_s"] - saved_t2m.merge(ann_t2m, on="year", suffixes=("_s","_a"))["value_a"]).abs().max()),
}

# ---- POWER area weighting T2M ----
# unweighted vs cos(lat); also land-ish vs all (rough Black Sea box)
recs_uw, recs_w, recs_landish = [], [], []
for year, g in t2m.groupby("YEAR"):
    year = int(year)
    w = np.cos(np.deg2rad(g["LAT"].to_numpy()))
    v = g["ANN"].to_numpy()
    recs_uw.append({"year": year, "value": np.nanmean(v)})
    recs_w.append({"year": year, "value": np.nansum(v * w) / np.nansum(w)})
    # rough NW Black Sea: south of 46.0 and east of 29.5 (excludes most Crimea land? Crimea is ~44.4-46.2, 32-36)
    # Instead report two masks:
    # sea-ish: lat<=45.5 and lon>=30.0 (open NW Black Sea, still includes some coast)
    landish = ~((g["LAT"] <= 45.5) & (g["LON"] >= 30.0))
    recs_landish.append({"year": year, "value": g.loc[landish, "ANN"].mean(), "n": int(landish.sum()), "n_all": len(g)})
uw, ww, land = pd.DataFrame(recs_uw), pd.DataFrame(recs_w), pd.DataFrame(recs_landish)
tr_uw = ols_with_ar1(uw["year"], uw["value"])
tr_w = ols_with_ar1(ww["year"], ww["value"])
tr_land = ols_with_ar1(land["year"], land["value"])
# difference series
diff = (ww["value"] - uw["value"]).abs()
weighting = {
    "n_cells": int(t2m.groupby(["LAT","LON"]).ngroups),
    "lat_min": float(t2m["LAT"].min()),
    "lat_max": float(t2m["LAT"].max()),
    "lon_min": float(t2m["LON"].min()),
    "lon_max": float(t2m["LON"].max()),
    "coslat_south_over_north": float(math.cos(math.radians(t2m["LAT"].min())) / math.cos(math.radians(t2m["LAT"].max()))),
    "mean_abs_uw_minus_weighted_C": float(diff.mean()),
    "max_abs_uw_minus_weighted_C": float(diff.max()),
    "ols_uw_decade": tr_uw["ols_decade"],
    "ols_weighted_decade": tr_w["ols_decade"],
    "ols_landish_decade": tr_land["ols_decade"],
    "n_landish_cells": int(land["n"].iloc[0]),
    "n_all_cells": int(land["n_all"].iloc[0]),
    "bbox_area_km2_approx": float(18.1 * 8.0 * 111.132 * 111.132 * math.cos(math.radians(48.4))),
}

# ---- GSOM station composition ----
gsom = pd.read_csv(ROOT / "noaa_gsom/gsom_ukraine_UP_stations.csv", low_memory=False)
gsom["DATE"] = pd.to_datetime(gsom["DATE"] + "-01")
gsom["year"] = gsom["DATE"].dt.year
gsom["month"] = gsom["DATE"].dt.month
# reconstruct annual TAVG like the script (min 10 months)
rows_t = []
for (sid, year), g in gsom.groupby(["STATION", "year"]):
    v = g["TAVG"].dropna()
    if len(v) < 10:
        continue
    rows_t.append({"STATION": sid, "NAME": g["NAME"].iloc[0], "LATITUDE": g["LATITUDE"].iloc[0],
                   "LONGITUDE": g["LONGITUDE"].iloc[0], "year": year, "value": v.mean(), "n_months": len(v)})
ann_t = pd.DataFrame(rows_t)
# long-record 1981-2025 as in script
def long_ids(ann, period, clim=(1991,2020), min_years=30):
    y0,y1=period
    c0,c1=clim
    use=[]
    for sid,g in ann.groupby("STATION"):
        g=g[(g.year>=y0)&(g.year<=y1)]
        clim_g=g[(g.year>=c0)&(g.year<=c1)]
        if len(g)>=min_years and len(clim_g)>=15:
            use.append((sid, g["NAME"].iloc[0], float(g["LATITUDE"].iloc[0]) if "LATITUDE" in g.columns else None, float(g["LONGITUDE"].iloc[0]) if "LONGITUDE" in g.columns else None,
                        int(g.year.min()), int(g.year.max()), int(len(g)),
                        int((g.year>=2013).sum()), int((g.year>=2020).sum()), int((g.year==2025).sum())))
    return use
ids81 = long_ids(ann_t, (1981,2025), min_years=30)
# years present among these
used = [x[0] for x in ids81]
sub = ann_t[ann_t.STATION.isin(used) & ann_t.year.between(1981,2025)]
# which stations drop after 2012
after = sub[sub.year>=2013].groupby("STATION")["year"].nunique()
before_ids = set(used)
after_ids = set(after[after>0].index)
dropped = [x for x in ids81 if x[0] not in after_ids]
remaining = [x for x in ids81 if x[0] in after_ids]
# mean of remaining vs dropped over 1981-2012
pre = sub[sub.year.between(1981,2012)]
pre_rem = pre[pre.STATION.isin(after_ids)].groupby("year")["value"].mean()
pre_drp = pre[pre.STATION.isin(before_ids-after_ids)].groupby("year")["value"].mean()
overlap = pre_rem.index.intersection(pre_drp.index)
gsom_comp = {
    "n_long_record": len(ids81),
    "stations": [{"id":x[0],"name":x[1],"lat":x[2],"lon":x[3],"ymin":x[4],"ymax":x[5],"n_years":x[6],
                  "n_years_2013plus":x[7],"n_years_2020plus":x[8],"has_2025":x[9]} for x in ids81],
    "dropped_after_2012": [{"id":x[0],"name":x[1]} for x in dropped],
    "remaining_after_2012": [{"id":x[0],"name":x[1]} for x in remaining],
    "mean_1981_2012_remaining_C": float(pre_rem.loc[overlap].mean()) if len(overlap) else None,
    "mean_1981_2012_dropped_C": float(pre_drp.loc[overlap].mean()) if len(overlap) else None,
    "diff_dropped_minus_remaining_C": float((pre_drp.loc[overlap]-pre_rem.loc[overlap]).mean()) if len(overlap) else None,
    "missing_years_in_anomaly_series": [2020,2021,2022,2023,2024],
    "coverage_2025_all_TAVG_stations": int(((ann_t.year==2025)).sum()),
}

# GSOM PRCP 1981 reconstruct
rows_p=[]
for (sid, year), g in gsom.groupby(["STATION","year"]):
    v=g["PRCP"].dropna()
    if len(v)<12:
        continue
    rows_p.append({"STATION":sid,"NAME":g["NAME"].iloc[0],"year":year,"value":v.sum()})
ann_p=pd.DataFrame(rows_p)
ids_p = long_ids(ann_p, (1981,2025), min_years=20)
# anomaly series
frames=[]
for sid,g in ann_p.groupby("STATION"):
    g=g[(g.year>=1981)&(g.year<=2025)].copy()
    clim_g=g[(g.year>=1991)&(g.year<=2020)]
    if len(g)<20 or len(clim_g)<15:
        continue
    base=clim_g["value"].mean()
    g["anomaly"]=g["value"]-base
    frames.append(g)
p_ser = pd.concat(frames).groupby("year").agg(anomaly=("anomaly","mean"), n=("STATION","nunique"), raw=("value","mean")).reset_index() if frames else pd.DataFrame()
if len(p_ser):
    tr_p = ols_with_ar1(p_ser["year"], p_ser["anomaly"])
    rows.append({"series":"GSOM_PRCP_1981_reconstructed", **tr_p,
                 "n_members_min":int(p_ser.n.min()), "n_members_max":int(p_ser.n.max()),
                 "n_members_end":int(p_ser.n.iloc[-1]),
                 "missing_years":",".join(map(str, sorted(set(range(int(p_ser.year.min()), int(p_ser.year.max())+1))-set(p_ser.year.astype(int)))))})
    p_ser.to_csv(OUT/"gsom_PRCP_anomaly_1981-2025_reconstructed.csv", index=False)

# ---- MODIS pixel-count trend (possible aliasing) ----
vi = pd.read_csv(ROOT / "modis_lpdaac/MOD13C2_ukraine_monthly.csv")
lst = pd.read_csv(ROOT / "modis_lpdaac/MOD11C3_ukraine_monthly.csv")
for df in (vi, lst):
    df["month"] = pd.to_datetime(df["month"] + "-01")
    df["year"] = df["month"].dt.year
vi_y = vi[(vi.year>=2001)&(vi.year<=2025)].groupby("year")["NDVI_n"].mean()
lst_y = lst[(lst.year>=2001)&(lst.year<=2025)].groupby("year")["LST_Day_K_n"].mean()
# also min monthly counts (winter dropouts)
lst_min = lst[(lst.year>=2001)&(lst.year<=2025)].groupby("year")["LST_Day_K_n"].min()
modis_counts = {
    "window_pixels_nominal": 160 * 362,  # Y 752:912 (160), X 4042:4404 (362) if exclusive end
    "NDVI_n_mean": float(vi["NDVI_n"].mean()),
    "NDVI_n_min": int(vi["NDVI_n"].min()),
    "NDVI_n_max": int(vi["NDVI_n"].max()),
    "LST_Day_n_mean": float(lst["LST_Day_K_n"].mean()),
    "LST_Day_n_min": int(lst["LST_Day_K_n"].min()),
    "LST_Day_n_max": int(lst["LST_Day_K_n"].max()),
    "LST_Day_n_min_month": str(lst.loc[lst["LST_Day_K_n"].idxmin(), "month"]),
    "NDVI_n_annualmean_ols_per_decade": float(stats.linregress(vi_y.index, vi_y.values).slope * 10),
    "LST_Day_n_annualmean_ols_per_decade": float(stats.linregress(lst_y.index, lst_y.values).slope * 10),
    "VI_http_all_200": bool((vi["http_status"]==200).all()),
    "LST_http_all_200": bool((lst["http_status"]==200).all()),
    "VI_n_months": int(len(vi)),
    "LST_n_months": int(len(lst)),
    "expected_months_Feb2000_Oct2026": 321,
}

# ---- GHCN station counts / 2024-2025 leverage ----
gt = pd.read_csv(ROOT / "analysis/ghcn_daily_T_anomaly_1981-2025.csv")
# trend with/without 2024 and 2025
tr_all = ols_with_ar1(gt["year"], gt["anomaly"])
tr_no24 = ols_with_ar1(gt.loc[gt.year<=2023, "year"], gt.loc[gt.year<=2023, "anomaly"])
tr_no25 = ols_with_ar1(gt.loc[gt.year<=2024, "year"], gt.loc[gt.year<=2024, "anomaly"])
# GSOM without 2025 (gap already excludes 2020-24)
gs = pd.read_csv(ROOT / "analysis/gsom_TAVG_anomaly_1981-2025.csv")
tr_gs = ols_with_ar1(gs["year"], gs["anomaly"])
tr_gs_no25 = ols_with_ar1(gs.loc[gs.year<=2019, "year"], gs.loc[gs.year<=2019, "anomaly"])
pw = pd.read_csv(ROOT / "analysis/power_T2M_bbox_annual.csv")
base = pw[pw.year.between(1991,2020)]["value"].mean()
pw_anom = pw.assign(anomaly=pw["value"]-base)
tr_pw = ols_with_ar1(pw_anom["year"], pw_anom["anomaly"])
tr_pw_no2425 = ols_with_ar1(pw_anom.loc[pw_anom.year<=2023,"year"], pw_anom.loc[pw_anom.year<=2023,"anomaly"])

endpoint = {
    "GHCN_ols_1981_2025": tr_all["ols_decade"],
    "GHCN_ols_1981_2024": tr_no25["ols_decade"],
    "GHCN_ols_1981_2023": tr_no24["ols_decade"],
    "GHCN_2024_anomaly": float(gt.loc[gt.year==2024,"anomaly"].iloc[0]),
    "GHCN_2025_anomaly": float(gt.loc[gt.year==2025,"anomaly"].iloc[0]),
    "GHCN_n_2024": int(gt.loc[gt.year==2024,"n"].iloc[0]),
    "GHCN_n_2025": int(gt.loc[gt.year==2025,"n"].iloc[0]),
    "GSOM_ols_1981_2025_incl_gap_and_2025": tr_gs["ols_decade"],
    "GSOM_ols_1981_2019_before_gap": tr_gs_no25["ols_decade"],
    "POWER_ols_1981_2025": tr_pw["ols_decade"],
    "POWER_ols_1981_2023": tr_pw_no2425["ols_decade"],
}

# ---- Lviv mis-location distance ----
# Lviv city 24.0297, 49.8397 vs reach 29.593624, 46.813680
def dist_km(lon1,lat1,lon2,lat2):
    x=math.radians(lon1-lon2)*math.cos(math.radians((lat1+lat2)/2))
    y=math.radians(lat1-lat2)
    return 6371.0*math.sqrt(x*x+y*y)

sites_claimed = {
    "Lviv_Dniester": ((24.0297, 49.8397), (29.593624, 46.813680)),
    "Kherson_Dnieper": ((32.6169, 46.6354), (32.013394, 46.560153)),
    "Odesa_Dniester": ((30.70, 46.35), (30.224842, 46.355689)),
    "Vinnytsia_SouthernBug": ((28.4682, 49.2331), (28.432755, 49.375100)),
    "Kyiv_Desna": ((30.5234, 50.4501), (30.573431, 50.560879)),
}
site_dist = {k: {"claimed_to_reach_km": dist_km(a[0],a[1],b[0],b[1])} for k,(a,b) in sites_claimed.items()}

# ---- multiple testing from trend_summary ----
ts = pd.read_csv(ROOT / "analysis/trend_summary.csv")
n_tests = len(ts)
n_sig_mk = int((ts["mk_p"] < 0.05).sum())
n_sig_ols = int((ts["lin_p"] < 0.05).sum())
bonf = 0.05 / n_tests
n_sig_mk_bonf = int((ts["mk_p"] < bonf).sum())
# disagreement OLS vs MK at 0.05
disagree = ts[((ts["lin_p"]<0.05) != (ts["mk_p"]<0.05))][["source","variable","lin_p","mk_p","lin_slope_per_decade","theil_sen_per_decade"]]

# SWOT their sen vs time-based sen ratio
swot_rows = [r for r in rows if r["series"].startswith("SWOT_") and r["series"].endswith("_moy_anomaly")]

# POWER precip MK vs AR1
# Save
out_df = pd.DataFrame(rows)
# reorder
pref = ["series","n","start","end","ols_decade","ols_p","ols_p_ar1adj","hac1_p","hac3_p",
        "r_resid_lag1","r_series_lag1","n_eff_ar1","sen_time_decade","mk_orig_sen_unitindex_x10",
        "mk_orig_p","mk_hr_p","mk_yw_p","mk_tfpw_p","ols_ci95_lo","ols_ci95_hi","ols_ci95_ar1_lo","ols_ci95_ar1_hi",
        "missing_years","n_members_min","n_members_max","n_members_end"]
cols = [c for c in pref if c in out_df.columns] + [c for c in out_df.columns if c not in pref]
out_df[cols].to_csv(OUT / "recomputed_trends.csv", index=False)

meta = {
    "tmax_identification": tmax_id,
    "weighting": weighting,
    "gsom_composition": gsom_comp,
    "modis_counts": modis_counts,
    "endpoint": endpoint,
    "site_distances_km": site_dist,
    "multiple_testing": {
        "n_tests_in_trend_summary": n_tests,
        "n_mk_p_lt_0.05": n_sig_mk,
        "n_ols_p_lt_0.05": n_sig_ols,
        "bonferroni_alpha": bonf,
        "n_mk_p_lt_bonferroni": n_sig_mk_bonf,
        "ols_mk_disagreements": disagree.to_dict(orient="records"),
    },
}
# make json safe
def conv(o):
    if isinstance(o, (np.floating, float)):
        if not np.isfinite(o):
            return None
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, Path):
        return str(o)
    raise TypeError(type(o))

(OUT / "meta_checks.json").write_text(json.dumps(meta, indent=2, default=conv))

# print highlights
print("=== T2M_MAX identification ===")
print(json.dumps(tmax_id, indent=2, default=conv))
print("=== weighting ===")
print(json.dumps(weighting, indent=2, default=conv))
print("=== GSOM composition ===")
print("n long", gsom_comp["n_long_record"])
print("dropped", gsom_comp["dropped_after_2012"])
print("remaining", gsom_comp["remaining_after_2012"])
print("mean rem/drop", gsom_comp["mean_1981_2012_remaining_C"], gsom_comp["mean_1981_2012_dropped_C"], gsom_comp["diff_dropped_minus_remaining_C"])
print("=== endpoint ===")
print(json.dumps(endpoint, indent=2, default=conv))
print("=== multiple testing ===")
print(n_tests, "tests; MK sig", n_sig_mk, "OLS sig", n_sig_ols, "bonf", bonf, "MK bonf sig", n_sig_mk_bonf)
print("disagreements:\n", disagree.to_string(index=False))
print("=== key series AR1 / modified MK ===")
show = out_df[out_df.series.isin([
    "POWER_T2M","POWER_PRECTOTCORR","POWER_WS10M","POWER_ALLSKY_SW","POWER_T2M_JJA",
    "GSOM_TAVG_1981","GSOM_TAVG_1961","GSOM_PRCP_1950","GHCN_T_1981","GHCN_P_1981",
    "MODIS_EVI_ann","MODIS_EVI_AMJJAS","MODIS_LST_Day_ann","MODIS_LST_Night_ann","MODIS_LST_Night_DJF",
    "GSOM_PRCP_1981_reconstructed",
])]
print(show[["series","n","ols_decade","ols_p","ols_p_ar1adj","hac1_p","r_resid_lag1","n_eff_ar1",
            "sen_time_decade","mk_orig_sen_unitindex_x10","mk_orig_p","mk_hr_p","mk_yw_p"]].to_string(index=False))
print("=== SWOT moy anomaly ===")
swo = out_df[out_df.series.str.contains("SWOT_") & out_df.series.str.endswith("_moy_anomaly")]
print(swo[["series","n","span_years","ols_decade","ols_p","ols_p_ar1adj","hac1_p","r_resid_lag1","n_eff_ar1",
           "sen_time_decade","mk_orig_sen_unitindex_x10","mk_orig_p","mk_hr_p","mk_yw_p"]].to_string(index=False))
print("=== MODIS counts ===")
print(json.dumps(modis_counts, indent=2, default=conv))
print("=== site distances ===")
print(json.dumps(site_dist, indent=2, default=conv))
print("DONE")
