#!/usr/bin/env python3
"""Independent re-check of the revised Ukraine trend analysis. Does not write to ukraine_samples/."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pymannkendall as mk
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.multitest import multipletests

sys.path.insert(0, "$UKRAINE_SAMPLES/_staging")
from trend_methods import trend_stats, robust_call

ROOT = Path("$UKRAINE_SAMPLES")
OUT = Path("team-context/team/reviews")
MONTHS = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
KAKHOVKA = pd.Timestamp("2023-06-06", tz="UTC")
SITE_RENAME = {"Lviv_Dniester": "Lower_Dniester"}


def load_power(param):
    frames = []
    for tile in ("west", "east"):
        raw = (ROOT / "nasa_power" / f"POWER_monthly_{param}_{tile}_1981-2025.csv").read_text()
        body = raw.split("-END HEADER-\n", 1)[1]
        frames.append(pd.read_csv(io.StringIO(body)))
    df = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["YEAR","LAT","LON"], keep="first")
    for c in MONTHS + ["ANN"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").replace(-999, np.nan)
    return df


def parse_reach_raw(text: str) -> pd.DataFrame:
    t = text.strip()
    if t.startswith("{") or "Feature ID" in t:
        return pd.DataFrame()
    if t.startswith('"') and t.endswith('"'):
        t = t[1:-1]
    t = t.replace("\\n", "\n")
    return pd.read_csv(io.StringIO(t))


# ---------- POWER ANN vs monthly mean ----------
df = load_power("T2M")
print("=== POWER ANN vs month means ===")
for year, days_feb in [(1981, 28), (1984, 29)]:
    g = df[df.YEAR == year]
    days = np.array([31, days_feb, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31], dtype=float)
    cell_unw = g[MONTHS].mean(axis=1).to_numpy()
    cell_dw = (g[MONTHS].to_numpy() * days).sum(axis=1) / days.sum()
    ann = g.ANN.to_numpy()
    print(f"{year} ANN vs unweighted month mean: maxabs={np.nanmax(np.abs(ann-cell_unw)):.5f} meanabs={np.nanmean(np.abs(ann-cell_unw)):.5f}")
    print(f"{year} ANN vs day-weighted month mean: maxabs={np.nanmax(np.abs(ann-cell_dw)):.5f} meanabs={np.nanmean(np.abs(ann-cell_dw)):.5f}")

# ---------- Reproduce trend_summary from saved series ----------
ts = pd.read_csv(ROOT / "analysis/trend_summary.csv")
print("\n=== n tests", len(ts), "primary", int(ts.primary_test.sum()))

series_map = {
    ("NASA_POWER","T2M"): (ROOT/"analysis/power_T2M_bbox_annual.csv", "year", "value", None),
    ("NASA_POWER","T2M_2001-2025"): (ROOT/"analysis/power_T2M_bbox_annual.csv", "year", "value", (2001,2025)),
    ("NASA_POWER","T2M_1981-2023"): (ROOT/"analysis/power_T2M_bbox_annual.csv", "year", "value", (1981,2023)),
    ("NASA_POWER","PRECTOTCORR_annual_mm"): (ROOT/"analysis/power_PRECTOTCORR_bbox_annual_mm.csv", "year", "value", None),
    ("NASA_POWER","T2M_MAX"): (ROOT/"analysis/power_T2M_MAX_bbox_annual.csv", "year", "value", None),
    ("NASA_POWER","T2M_MIN"): (ROOT/"analysis/power_T2M_MIN_bbox_annual.csv", "year", "value", None),
    ("NASA_POWER","QV2M"): (ROOT/"analysis/power_QV2M_bbox_annual.csv", "year", "value", None),
    ("NASA_POWER","WS10M"): (ROOT/"analysis/power_WS10M_bbox_annual.csv", "year", "value", None),
    ("NASA_POWER","ALLSKY_SFC_SW_DWN"): (ROOT/"analysis/power_ALLSKY_SFC_SW_DWN_bbox_annual.csv", "year", "value", None),
    ("NOAA_GSOM","TAVG_1981"): (ROOT/"analysis/gsom_TAVG_anomaly_1981-2025.csv", "year", "anomaly", None),
    ("NOAA_GSOM","TAVG_1981-2019"): (ROOT/"analysis/gsom_TAVG_anomaly_1981-2025.csv", "year", "anomaly", (1981,2019)),
    ("NOAA_GSOM","TAVG_1961"): (ROOT/"analysis/gsom_TAVG_anomaly_1961-2025.csv", "year", "anomaly", None),
    ("NOAA_GSOM","PRCP_1981"): (ROOT/"analysis/gsom_PRCP_anomaly_1981-2025.csv", "year", "anomaly", None),
    ("NOAA_GSOM","PRCP_1950-2000"): (ROOT/"analysis/gsom_PRCP_anomaly_1950-2000.csv", "year", "anomaly", None),
    ("NOAA_GHCN_Daily","tmean_regional"): (ROOT/"analysis/ghcn_daily_T_anomaly_1981-2025.csv", "year", "anomaly", None),
    ("NOAA_GHCN_Daily","tmean_1981-2023"): (ROOT/"analysis/ghcn_daily_T_anomaly_1981-2025.csv", "year", "anomaly", (1981,2023)),
    ("NOAA_GHCN_Daily","PRCP_regional"): (ROOT/"analysis/ghcn_daily_P_anomaly_1981-2025.csv", "year", "anomaly", None),
}
# detect actual GSOM/GHCN variable names
print("GSOM variables:", ts.loc[ts.source=="NOAA_GSOM","variable"].tolist())
print("GHCN variables:", ts.loc[ts.source=="NOAA_GHCN_Daily","variable"].tolist())

seasons = pd.read_csv(ROOT/"analysis/power_T2M_bbox_seasons.csv")
mism = []

def cmp_row(src, var, tr, r, keys=None):
    keys = keys or ["n","lin_slope_per_decade","lin_p","hac1_p","hac3_p","lin_p_ar1","mk_p","mk_hr_p","theil_sen_per_decade","r_resid_lag1"]
    for k in keys:
        a, b = tr[k], r[k]
        if not (np.isfinite(a) and np.isfinite(b)):
            if np.isfinite(a) or np.isfinite(b):
                mism.append((src, var, k, a, b))
            continue
        if abs(a-b) > max(1e-8, 1e-6*abs(b)):
            mism.append((src, var, k, float(a), float(b)))

# map by matching what exists
name_fix = {}
for (src, var), spec in list(series_map.items()):
    if ((ts.source==src)&(ts.variable==var)).any():
        continue
    # try fuzzy
    cands = ts[ts.source==src]
    print(f"VAR NAME MISMATCH {src} {var}; candidates {cands.variable.tolist()}")

for (src, var), (path, yc, vc, yr) in series_map.items():
    row = ts[(ts.source==src) & (ts.variable==var)]
    if row.empty:
        continue
    df = pd.read_csv(path)
    if yr:
        df = df[(df[yc] >= yr[0]) & (df[yc] <= yr[1])]
    tr = trend_stats(df[yc], df[vc])
    cmp_row(src, var, tr, row.iloc[0])

for col in ["MAM","JJA","SON"]:
    tr = trend_stats(seasons.year, seasons[col])
    r = ts[(ts.source=="NASA_POWER")&(ts.variable==f"T2M_{col}")]
    if r.empty:
        print("missing season", col)
        continue
    cmp_row("NASA_POWER", f"T2M_{col}", tr, r.iloc[0])
tr = trend_stats(seasons.loc[seasons.year>=1982,"year"], seasons.loc[seasons.year>=1982,"DJF"])
r = ts[(ts.source=="NASA_POWER")&(ts.variable=="T2M_DJF")]
cmp_row("NASA_POWER", "T2M_DJF", tr, r.iloc[0])

for var in ["NDVI_annual","EVI_annual","NDVI_AMJJAS","EVI_AMJJAS","NDVI_JJA","EVI_JJA",
            "LST_Day_annual_C","LST_Night_annual_C","LST_Day_JJA_C","LST_Night_JJA_C",
            "LST_Day_MAM_C","LST_Night_DJF_C"]:
    df = pd.read_csv(ROOT/f"analysis/modis_{var}.csv")
    tr = trend_stats(df.year, df.value)
    r = ts[(ts.source=="MODIS_LPDAAC")&(ts.variable==var)]
    cmp_row("MODIS_LPDAAC", var, tr, r.iloc[0])

print("mismatches on climate/MODIS from saved series:", len(mism))
for m in mism:
    print(" ", m)

# GHCN cities
gh = pd.read_csv(ROOT/"analysis/ghcn_daily_derived_annual.csv")
# period labels in findings
print("\nGHCN derived years sample cols", gh.columns.tolist()[:8])

# ---------- Sen awareness ----------
print("\n=== Sen time-aware vs unit-index ===")
ts["sen_absdiff"] = (ts.theil_sen_per_decade - ts.theil_sen_unitindex_x10).abs()
print(ts.groupby("source")["sen_absdiff"].agg(["max","median"]).to_string())
print("Largest annual diffs (GSOM gaps expected):")
print(ts.loc[ts.source!="SWOT_Hydrocron"].nlargest(8, "sen_absdiff")[["source","variable","theil_sen_per_decade","theil_sen_unitindex_x10"]].to_string(index=False))
print("SWOT:")
print(ts.loc[ts.source=="SWOT_Hydrocron", ["domain","n","theil_sen_per_decade","theil_sen_unitindex_x10"]].to_string(index=False))

# ---------- Multiple testing ----------
print("\n=== Multiple testing recount ===")
n = len(ts)
p = ts.hac1_p.to_numpy()
rej_b, _, _, _ = multipletests(p, alpha=0.05, method="bonferroni")
rej_h, q, _, _ = multipletests(p, alpha=0.05, method="fdr_bh")
print(f"n={n} bon_alpha={0.05/n:.6g}")
print(f"HAC p<0.05: {int((ts.hac1_p<0.05).sum())}")
print(f"HR p<0.05: {int((ts.mk_hr_p<0.05).sum())}")
print(f"both: {int(((ts.hac1_p<0.05)&(ts.mk_hr_p<0.05)).sum())}")
print(f"HAC Bonferroni: recomputed {int(rej_b.sum())} CSV {int(ts.hac1_bonferroni_reject.sum())} disagree {int((ts.hac1_bonferroni_reject.to_numpy()!=rej_b).sum())}")
print(f"HAC BH: recomputed {int(rej_h.sum())} CSV {int(ts.hac1_bh_reject.sum())} disagree {int((ts.hac1_bh_reject.to_numpy()!=rej_h).sum())}")
prim = ts[ts.primary_test==True]
print("primary n", len(prim), "alpha", 0.05/max(len(prim),1))
print(prim[["source","variable","hac1_p","mk_hr_p","robust_call","primary_hac1_bonferroni_reject","primary_hac1_bh_reject"]].to_string(index=False))
if len(prim):
    rb,_,_,_ = multipletests(prim.hac1_p, 0.05, method="bonferroni")
    rh,_,_,_ = multipletests(prim.hac1_p, 0.05, method="fdr_bh")
    print("primary HAC bonferroni", int(rb.sum()), "CSV", int(prim.primary_hac1_bonferroni_reject.sum()), "disagree", int((prim.primary_hac1_bonferroni_reject.to_numpy()!=rb).sum()))
    print("primary HAC BH", int(rh.sum()), "CSV", int(prim.primary_hac1_bh_reject.sum()))
    print("primary both unadj", int(((prim.hac1_p<0.05)&(prim.mk_hr_p<0.05)).sum()))

calls_dis=[]
for _, r in ts.iterrows():
    tr={"hac1_p":r.hac1_p,"mk_hr_p":r.mk_hr_p,"mk_tfpw_p":r.mk_tfpw_p,"lin_p":r.lin_p,"mk_p":r.mk_p}
    c=robust_call(tr)
    if c!=r.robust_call:
        calls_dis.append((r.source,r.variable,c,r.robust_call,r.hac1_p,r.mk_hr_p,r.lin_p,r.mk_p))
print("robust_call disagreements:", len(calls_dis))
for x in calls_dis:
    print(" ", x)

# ---------- HAC lag flips ----------
print("\n=== HAC lag-1 vs lag-3 robust flips ===")
ts["robust_hac1"]=(ts.hac1_p<0.05)&(ts.mk_hr_p<0.05)
ts["robust_hac3"]=(ts.hac3_p<0.05)&(ts.mk_hr_p<0.05)
flip=ts[ts.robust_hac1!=ts.robust_hac3]
print("n flips", len(flip))
if len(flip):
    print(flip[["source","variable","hac1_p","hac3_p","mk_hr_p","robust_call"]].to_string(index=False))
# also list SWOT hac1 vs hac3
print("All SWOT HAC/HR:")
print(ts.loc[ts.source=="SWOT_Hydrocron",["domain","n","hac1_p","hac3_p","lin_p_ar1","r_resid_lag1","mk_hr_p","robust_call"]].to_string(index=False))

# ---------- Hamed-Rao lag=None vs lag=3 ----------
print("\n=== Hamed-Rao default (all lags) vs lag=3 ===")
hr_cmp=[]
for (src, var), (path, yc, vc, yr) in series_map.items():
    row=ts[(ts.source==src)&(ts.variable==var)]
    if row.empty:
        continue
    df=pd.read_csv(path)
    if yr:
        df=df[(df[yc]>=yr[0])&(df[yc]<=yr[1])]
    vals=df[vc].to_numpy(dtype=float)
    vals=vals[np.isfinite(vals)]
    try:
        hr_all=mk.hamed_rao_modification_test(vals)
        hr3=mk.hamed_rao_modification_test(vals, lag=3)
        hr_cmp.append((src,var,float(hr_all.p),float(hr3.p),float(row.iloc[0].mk_hr_p),int(hr_all.p<0.05),int(hr3.p<0.05)))
    except Exception as e:
        hr_cmp.append((src,var,"ERR",str(e),None,None,None))
for col in ["MAM","JJA","SON"]:
    vals=seasons[col].to_numpy(dtype=float)
    hr_all=mk.hamed_rao_modification_test(vals)
    hr3=mk.hamed_rao_modification_test(vals, lag=3)
    pub=float(ts[(ts.source=="NASA_POWER")&(ts.variable==f"T2M_{col}")].iloc[0].mk_hr_p)
    hr_cmp.append(("NASA_POWER",f"T2M_{col}",float(hr_all.p),float(hr3.p),pub,int(hr_all.p<0.05),int(hr3.p<0.05)))
vals=seasons.loc[seasons.year>=1982,"DJF"].to_numpy(dtype=float)
hr_all=mk.hamed_rao_modification_test(vals); hr3=mk.hamed_rao_modification_test(vals, lag=3)
pub=float(ts[(ts.source=="NASA_POWER")&(ts.variable=="T2M_DJF")].iloc[0].mk_hr_p)
hr_cmp.append(("NASA_POWER","T2M_DJF",float(hr_all.p),float(hr3.p),pub,int(hr_all.p<0.05),int(hr3.p<0.05)))
for var in ["EVI_annual","EVI_AMJJAS","EVI_JJA","NDVI_annual","LST_Day_annual_C","LST_Night_annual_C","LST_Night_DJF_C"]:
    df=pd.read_csv(ROOT/f"analysis/modis_{var}.csv")
    vals=df.value.to_numpy(dtype=float)
    hr_all=mk.hamed_rao_modification_test(vals); hr3=mk.hamed_rao_modification_test(vals, lag=3)
    pub=float(ts[(ts.source=="MODIS_LPDAAC")&(ts.variable==var)].iloc[0].mk_hr_p)
    hr_cmp.append(("MODIS",var,float(hr_all.p),float(hr3.p),pub,int(hr_all.p<0.05),int(hr3.p<0.05)))

print(f"{'series':40s} {'HR_all':>12s} {'HR_lag3':>12s} {'published':>12s} all<0.05 lag3<0.05")
flips_hr=[]
for rec in hr_cmp:
    src,var,pa,p3,pub,sa,s3=rec
    if sa!=s3:
        flips_hr.append(rec)
    if abs(pa-pub)>1e-8:
        mark=" PUB_MISMATCH"
    else:
        mark=""
    print(f"{src+':'+var:40s} {pa:12.4g} {p3:12.4g} {pub:12.4g} {sa} {s3}{mark}")
print("significance flips all-lags vs lag=3:", len(flips_hr))
for rec in flips_hr:
    print(" ", rec)

# ---------- SWOT reproduce + extra HAC lags + HR lag=3 ----------
print("\n=== SWOT re-filter, anomalies, HAC lags, Kherson ===")
frames=[]
flag_rows=[]
for f in sorted((ROOT/"swot_hydrocron").glob("reach_*.csv")):
    d=parse_reach_raw(f.read_text())
    parts=f.stem.split("_",2)
    rid=parts[1] if len(parts)>1 else ""
    site=parts[2] if len(parts)>2 else ""
    site=SITE_RENAME.get(site,site)
    if d.empty:
        continue
    d["site"]=site
    for col in ["wse","wse_u","width","dark_frac","ice_clim_f","ice_dyn_f","reach_q","p_lat","p_lon"]:
        if col in d.columns:
            d[col]=pd.to_numeric(d[col], errors="coerce")
            d.loc[d[col].abs()>1e6, col]=np.nan
    d["time"]=pd.to_datetime(d["time_str"], errors="coerce", utc=True)
    d=d[d["time"].notna()].copy()
    valid=d["wse"].notna()
    if "reach_q" in d:
        valid &= d["reach_q"].fillna(0).le(2)
    ice=(d["ice_clim_f"]>=1) if "ice_clim_f" in d else False
    if "ice_dyn_f" in d:
        ice = ice | (d["ice_dyn_f"].fillna(0)>=1)
    dark=(d["dark_frac"]>0.5) if "dark_frac" in d else False
    d["flag_ice"]=ice.astype(bool)
    d["flag_dark"]=dark.astype(bool)
    d["usable"]=valid & ~d["flag_ice"] & ~d["flag_dark"]
    d["year_frac"]=d["time"].dt.year + (d["time"].dt.day_of_year-1)/365.25
    n_valid=int(valid.sum())
    flag_rows.append({"site":site,"n_valid":n_valid,"n_ice":int((valid&d.flag_ice).sum()),
                      "n_dark":int((valid&d.flag_dark).sum()),"n_usable":int(d.usable.sum())})
    frames.append(d)
flags=pd.DataFrame(flag_rows)
print("recomputed flags:\n", flags.to_string(index=False))
pub_flags=pd.read_csv(ROOT/"analysis/swot_quality_flag_counts.csv")
print("published flags n_usable vs recomputed:")
m=pub_flags.merge(flags,on="site")
print(m[["site","n_usable_x","n_usable_y","n_ice_clim","n_ice"]].to_string(index=False) if "n_usable_x" in m.columns else m.to_string())

all_df=pd.concat(frames, ignore_index=True)
usable=all_df[all_df.usable].copy()

# month-of-year anomaly (their method: monthly median, clim=monthly median)
def monthly_anomaly(g):
    mon=g.set_index("time").resample("MS")["wse"].median().dropna().reset_index()
    mon["year_frac"]=mon["time"].dt.year+(mon["time"].dt.day_of_year-1)/365.25
    mon["month"]=mon["time"].dt.month
    clim=mon.groupby("month")["wse"].median()
    mon["anomaly"]=mon["wse"]-mon["month"].map(clim)
    return mon

swot_rows=[]
for site,g in usable.groupby("site"):
    mon=monthly_anomaly(g)
    tr=trend_stats(mon.year_frac, mon.anomaly)
    # extra HAC lags
    X=sm.add_constant(mon.year_frac.to_numpy())
    model=sm.OLS(mon.anomaly.to_numpy(), X).fit()
    extra={}
    for nl in (1,3,6,12):
        if nl < len(mon)-2:
            h=model.get_robustcov_results(cov_type="HAC", maxlags=nl)
            extra[f"hac{nl}_p"]=float(h.pvalues[1])
    # residual ACF 1-6
    resid=model.resid
    acf=[]
    for lag in range(1,7):
        if len(resid)>lag+2:
            acf.append(float(np.corrcoef(resid[lag:], resid[:-lag])[0,1]))
        else:
            acf.append(np.nan)
    extra["acf"]=acf
    # HR lag=3
    try:
        hr3=mk.hamed_rao_modification_test(mon.anomaly.to_numpy(), lag=3)
        extra["mk_hr_lag3"]=float(hr3.p)
    except Exception as e:
        extra["mk_hr_lag3"]=None
    # time spacing irregularity
    dts=np.diff(np.sort(mon.year_frac))*12  # months
    extra["n_months"]=len(mon)
    extra["month_gap_max"]=float(dts.max()) if len(dts) else np.nan
    extra["n_gaps_gt_1.5mo"]=int((dts>1.5).sum()) if len(dts) else 0
    swot_rows.append({"site":site, **{k:tr[k] for k in ["n","lin_slope_per_decade","lin_p","lin_p_ar1","hac1_p","hac3_p","mk_p","mk_hr_p","theil_sen_per_decade","r_resid_lag1","n_eff_ar1"]}, **extra})

# compare to published SWOT
print("\nSWOT anomaly recompute vs CSV:")
for rec in swot_rows:
    # match domain containing site label fragments
    # published domain uses labels like "Kyiv / Desna reach ..."
    site=rec["site"]
    # find by reach or name
    cands=ts[ts.source=="SWOT_Hydrocron"]
    # map site key to fragment
    frag={"Kyiv_Desna":"Desna","Chernihiv_Dnieper":"Chernihiv","Kherson_Dnieper":"Kherson",
          "Lower_Dniester":"Lower Dniester","Odesa_Dniester":"Odesa","Pripyat_border":"Pripyat",
          "Vinnytsia_SouthernBug":"Southern Bug","Chernivtsi_Prut":"Prut"}[site]
    row=cands[cands.domain.str.contains(frag, regex=False)]
    if row.empty:
        print(" NO CSV for", site)
        continue
    r=row.iloc[0]
    diffs=[]
    for k in ["n","lin_slope_per_decade","hac1_p","hac3_p","mk_hr_p","theil_sen_per_decade","lin_p_ar1"]:
        if abs(rec[k]-r[k])>max(1e-8,1e-5*abs(r[k]) if np.isfinite(r[k]) else 0):
            diffs.append((k,rec[k],r[k]))
    print(f"  {site}: n={rec['n']} (csv {int(r.n)}) hac1={rec['hac1_p']:.4g} hac3={rec['hac3_p']:.4g} hac6={rec.get('hac6_p')} hac12={rec.get('hac12_p')} HR={rec['mk_hr_p']:.4g} HR3={rec.get('mk_hr_lag3')} r={rec['r_resid_lag1']:.3f} acf={['%.2f'%x for x in rec['acf']]} maxgap_mo={rec['month_gap_max']:.2f} n_gaps={rec['n_gaps_gt_1.5mo']} diffs={diffs}")

# ---------- Kherson step + seasonality ----------
print("\n=== Kherson step seasonality ===")
kh=usable[usable.site=="Kherson_Dnieper"].copy()
pre=kh[kh.time<KAKHOVKA]
post=kh[kh.time>=KAKHOVKA]
print(f"usable pre n={len(pre)} {pre.time.min()} to {pre.time.max()}")
print(f"usable post n={len(post)} {post.time.min()} to {post.time.max()}")
print("pre months:", pre.time.dt.month.value_counts().sort_index().to_dict())
print("post months:", post.time.dt.month.value_counts().sort_index().to_dict())
# published JSON
pub=json.loads((ROOT/"analysis/swot_kherson_kakhovka_step.json").read_text())
print("published", json.dumps({k:pub[k] for k in pub}, default=float))
print("recomputed median pre/post", float(pre.wse.median()), float(post.wse.median()), "step", float(post.wse.median()-pre.wse.median()))
# seasonally matched: only Apr-Jun in post years
post_amj=post[post.time.dt.month.isin([4,5,6])]
print(f"post Apr-Jun n={len(post_amj)} median={float(post_amj.wse.median()) if len(post_amj) else None}")
if len(post_amj):
    print("  matched-season median step", float(post_amj.wse.median()-pre.wse.median()))
    mw=stats.mannwhitneyu(pre.wse.dropna(), post_amj.wse.dropna(), alternative="two-sided")
    print("  matched-season MW p", float(mw.pvalue))
# month-by-month post vs pre (pre only has Apr, May, early Jun)
for m in [4,5,6]:
    a=pre[pre.time.dt.month==m].wse
    b=post[post.time.dt.month==m].wse
    print(f"  month {m}: pre n={len(a)} med={float(a.median()) if len(a) else None}; post n={len(b)} med={float(b.median()) if len(b) else None}; diff={float(b.median()-a.median()) if len(a) and len(b) else None}")

# OLS dummy + time+step on usable obs (reproduce)
y=np.concatenate([pre.wse.to_numpy(), post.wse.to_numpy()])
post_d=np.concatenate([np.zeros(len(pre)), np.ones(len(post))])
X=sm.add_constant(post_d)
m=sm.OLS(y,X).fit()
h=m.get_robustcov_results(cov_type="HAC", maxlags=3)
print("OLS dummy step", float(m.params[1]), "p", float(m.pvalues[1]), "HAC3 p", float(h.pvalues[1]))
# time + step
g2=kh.dropna(subset=["wse"])
X2=sm.add_constant(np.column_stack([g2.year_frac.to_numpy(), (g2.time>=KAKHOVKA).astype(float).to_numpy()]))
m2=sm.OLS(g2.wse.to_numpy(), X2).fit()
h2=m2.get_robustcov_results(cov_type="HAC", maxlags=3)
print("time+step: time coef", float(m2.params[1]), "p_time", float(m2.pvalues[1]),
      "step coef", float(m2.params[2]), "p_step", float(m2.pvalues[2]),
      "HAC3 step p", float(h2.pvalues[2]))
# seasonally dummy: month fixed effects + step
month=g2.time.dt.month.to_numpy()
dummies=np.column_stack([(month==m).astype(float) for m in range(2,13)])  # drop Jan
X3=sm.add_constant(np.column_stack([dummies, (g2.time>=KAKHOVKA).astype(float).to_numpy()]))
m3=sm.OLS(g2.wse.to_numpy(), X3).fit()
h3=m3.get_robustcov_results(cov_type="HAC", maxlags=3)
print("month FE + step: step", float(m3.params[-1]), "OLS p", float(m3.pvalues[-1]), "HAC3 p", float(h3.pvalues[-1]))
# month FE + time + step
X4=sm.add_constant(np.column_stack([g2.year_frac.to_numpy(), dummies, (g2.time>=KAKHOVKA).astype(float).to_numpy()]))
m4=sm.OLS(g2.wse.to_numpy(), X4).fit()
h4=m4.get_robustcov_results(cov_type="HAC", maxlags=3)
print("month FE + time + step: time", float(m4.params[1]), "step", float(m4.params[-1]),
      "OLS p_step", float(m4.pvalues[-1]), "HAC3 p_step", float(h4.pvalues[-1]))

# pre window is only ~2 months: also compare same calendar window 2024 and 2025 Apr 5-Jun 6
for year in [2024,2025,2026]:
    w=post[(post.time>=pd.Timestamp(f"{year}-04-05", tz="UTC"))&(post.time<pd.Timestamp(f"{year}-06-06", tz="UTC"))]
    print(f"  post {year} Apr5-Jun6 n={len(w)} median={float(w.wse.median()) if len(w) else None}")

# ---------- leftover scripts ----------
print("\n=== note: analyze_and_plot still has old trend_stats (not imported) ===")

# QV2M units, periods
print("QV2M units", ts.loc[ts.variable=="QV2M","units"].tolist(), "period", ts.loc[ts.variable=="QV2M","period"].tolist())
print("ALLSKY period/n/start/end", ts.loc[ts.variable=="ALLSKY_SFC_SW_DWN",["period","n","start","end"]].to_string(index=False))
print("city periods:")
print(ts.loc[ts.source=="NOAA_GHCN_Daily",["variable","domain","period","n","start","end"]].to_string(index=False))

# EVI_AMJJAS details
print("\nEVI_AMJJAS row:")
print(ts.loc[ts.variable=="EVI_AMJJAS",["lin_p","hac1_p","hac3_p","mk_p","mk_hr_p","r_resid_lag1","n_eff_ar1","robust_call"]].to_string(index=False))

# Lower Dniester / Odesa robust on short record
print("\nSWOT labelled robust:")
print(ts.loc[(ts.source=="SWOT_Hydrocron")&(ts.robust_call.str.contains("robust")),["domain","n","start","end","hac1_p","hac3_p","mk_hr_p","lin_p_ar1"]].to_string(index=False))

# primary family EVI etc Bonferroni
print("\nWhich primary fail unadjusted or Bonferroni?")
for _,r in prim.iterrows():
    print(f"  {r.source} {r.variable}: hac1={r.hac1_p:.4g} HR={r.mk_hr_p:.4g} call={r.robust_call} bonf={r.primary_hac1_bonferroni_reject} bh={r.primary_hac1_bh_reject}")

print("DONE")
