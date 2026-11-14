#!/usr/bin/env python3
from __future__ import annotations
import sys, os, glob, calendar, json
from pathlib import Path
from collections import Counter

os.environ["OMP_NUM_THREADS"] = "1"
sys.path.insert(0, "team-context/data/pipeline")
sys.path.insert(0, "$UKRAINE_SAMPLES/_staging")

import numpy as np
import pandas as pd
import netCDF4
import trend_methods as tm
from ukpipe.core import LAST_FULL_YEAR, annual_table, make_tidy
from ukpipe.loaders.global_grids import _cmg_coords, _vi_good, _lst_good, VI_QC, LST_QC, _rawq

OUT = Path("team-context/team/reviews/pipeline_v12_checks2_out.txt")
lines=[]
def p(*a):
    s=" ".join(str(x) for x in a)
    lines.append(s)
    print(s, flush=True)

def cache(prefix, region):
    # exact region, not prefix-matching ukraine_mask_no_crimea
    files=list(Path("team-context/data/pipeline/data/cache/series").glob(f"{prefix}_{region}_*.parquet"))
    files=[f for f in files if f.name.startswith(f"{prefix}_{region}_") and "_no_crimea_" not in f.name]
    files=sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
    return pd.read_parquet(files[0]), files[0]

# ---------- old extract GPCC/CHIRPS means
p("="*72)
p("A. OLD EXTRACT vs TIDY GPCC/CHIRPS (ukraine_bbox)")
p("="*72)
gp=pd.read_csv("$UKRAINE_SAMPLES/extra/gpcc/gpcc_v2025_1deg_ukraine_bbox_monthly.csv", comment="#")
gp["date"]=pd.to_datetime(gp["time"].astype(str)+"-01")
gp["year"]=gp.date.dt.year
s=gp[gp.year.between(1981,2025)].groupby("year").precip_mm.sum()
p(f"  old GPCC extract 1981-2025 ANN mean={s.mean():.4f} n={s.size} months={gp.year.between(1981,2025).sum()}")

ch=pd.read_csv("$UKRAINE_SAMPLES/extra/chirps_v3/chirps_v3_ukraine_bbox_monthly.csv", comment="#")
print_cols=list(ch.columns)
p("  chirps csv cols", print_cols)
# if comment skipped wrong, try header
if "time" not in ch.columns and "date" not in ch.columns:
    ch=pd.read_csv("$UKRAINE_SAMPLES/extra/chirps_v3/chirps_v3_ukraine_bbox_monthly.csv")
    p("  retry cols", list(ch.columns), ch.head(2).to_dict())
# find
dcol = "time" if "time" in ch.columns else ("date" if "date" in ch.columns else ch.columns[0])
vcol = "precip_mm" if "precip_mm" in ch.columns else ("precip" if "precip" in ch.columns else [c for c in ch.columns if c!=dcol][0])
ch["date"]=pd.to_datetime(ch[dcol].astype(str).str[:7]+"-01")
ch["year"]=ch.date.dt.year
s2=ch[ch.year.between(1981,2025)].groupby("year")[vcol].sum()
p(f"  old CHIRPS extract 1981-2025 ANN mean={s2.mean():.4f} n={s2.size} months={ch.year.between(1981,2025).sum()} last={ch.date.max()} n_all={len(ch)}")

tidy_b=pd.read_parquet("team-context/data/pipeline/data/tidy/ukraine_bbox/all_monthly_long.parquet")
ann_b=pd.read_parquet("team-context/data/pipeline/data/tidy/ukraine_bbox/annual_seasonal.parquet")
for src, old in [("gpcc",s),("chirps",s2)]:
    mon=tidy_b[(tidy_b.source==src)&(tidy_b.variable=="precip")].copy()
    mon["year"]=mon.date.dt.year
    new=mon[mon.year.between(1981,2025)].groupby("year").value.sum()
    # align monthly
    oldm = (gp if src=="gpcc" else ch).copy()
    valn = "precip_mm" if src=="gpcc" else vcol
    oldm=oldm.set_index(oldm.date.dt.to_period("M"))[valn]
    newm=mon.set_index(mon.date.dt.to_period("M")).value
    both=oldm.index.intersection(newm.index)
    d=(newm.loc[both]-oldm.loc[both])
    p(f"  {src} tidy ANN 1981-2025={new.mean():.4f} old={old.mean():.4f} diff={new.mean()-old.mean():+.4f}")
    p(f"    monthly n_common={len(both)} corr={np.corrcoef(newm.loc[both], oldm.loc[both])[0,1]:.6f} mean_diff={d.mean():+.4f} maxabs={d.abs().max():.4f}")
    # 1981-2025 only monthly
    both2=both[(both.year>=1981)&(both.year<=2025)]
    d2=(newm.loc[both2]-oldm.loc[both2])
    p(f"    1981-2025 monthly mean_diff={d2.mean():+.4f} *12={d2.mean()*12:+.4f} maxabs={d2.abs().max():.4f}")

# ---------- unit conversion
p("\n"+"="*72)
p("B. GLDAS unit conversion + overlap + forcing windows")
p("="*72)
import inspect
from ukpipe import core
src=inspect.getsource(core)
# find conversion
for line in src.splitlines():
    if "per_s_to_month" in line or "def convert" in line or "86400" in line or "days_in" in line:
        p("  CORE:", line)

# one-month raw check: Jan 2010 GLDAS 2.1 Snowf over a single cell vs converted
# Use cached series vs raw * 86400 * 31, area-weighted over ukraine_mask would need weights.
# Simpler: take the cache rainf values BEFORE conversion? Cache is still in kg m-2 s-1 then tidy converts.
# Check _to_tidy / make_tidy
rainf, path = cache("gldas21_rainf", "ukraine_mask")
p("  rainf cache", path.name, "cols", list(rainf.columns), "n", len(rainf))
p("  cache Snowf_tavg mean (raw units?)", rainf["Snowf_tavg"].mean() if "Snowf_tavg" in rainf.columns else "no col", rainf.head(2).to_dict())
# if cache is raw kg m-2 s-1, Jan mean * 86400 * 31 should match tidy snowfall
tidy_m=pd.read_parquet("team-context/data/pipeline/data/tidy/ukraine_mask/all_monthly_long.parquet")
ann_m=pd.read_parquet("team-context/data/pipeline/data/tidy/ukraine_mask/annual_seasonal.parquet")
sno=tidy_m[(tidy_m.source=="gldas21")&(tidy_m.variable=="snowfall")].copy()
# identify raw col
rawcol = "Snowf_tavg" if "Snowf_tavg" in rainf.columns else ("snowfall" if "snowfall" in rainf.columns else None)
p("  first row cache", rainf.iloc[0].to_dict())
# merge
rainf=rainf.copy()
rainf["date"]=pd.to_datetime(rainf["date"])
# guess: cache already converted or not
jan=rainf[rainf.date==pd.Timestamp("2010-01-01")]
if len(jan):
    raw=float(jan.iloc[0][rawcol] if rawcol in jan.columns else jan.iloc[0][[c for c in jan.columns if "Snow" in c or "snow" in c][0]])
    tidyv=float(sno[sno.date==pd.Timestamp("2010-01-01")].value.iloc[0])
    p(f"  Jan 2010 cache raw={raw} tidy={tidyv} raw*86400={raw*86400:.4f} raw*86400*31={raw*86400*31:.4f} match_days={np.isclose(raw*86400*31, tidyv)} match_daily={np.isclose(raw*86400, tidyv)}")
# all months: if cache is raw, check conversion
if rawcol and rawcol in rainf.columns and rainf[rawcol].mean()<0.01:
    m=rainf.merge(sno, on="date")
    days=m.date.dt.days_in_month
    conv=m[rawcol]*86400*days
    p(f"  all months raw*86400*days vs tidy: maxabs={(conv-m.value).abs().max():.6e} n={len(m)}")
else:
    p("  cache may already be in mm or unexpected magnitude", rainf[rawcol].describe().to_dict() if rawcol in rainf.columns else "")

# identity and overlap already partially planned
s20=tidy_m[(tidy_m.source=="gldas20")&(tidy_m.variable=="snowfall")].sort_values("date")
s21=tidy_m[(tidy_m.source=="gldas21")&(tidy_m.variable=="snowfall")].sort_values("date")
p(f"  2.0 {s20.date.min()}..{s20.date.max()} n={len(s20)} mean mm/mo={s20.value.mean():.3f}")
p(f"  2.1 {s21.date.min()}..{s21.date.max()} n={len(s21)} mean mm/mo={s21.value.mean():.3f}")
a=s20.set_index(s20.date.dt.to_period("M")).value
b=s21.set_index(s21.date.dt.to_period("M")).value
both=a.index.intersection(b.index)
p(f"  overlap n={len(both)} {both.min()}..{both.max()} corr={np.corrcoef(a.loc[both],b.loc[both])[0,1]:.4f} mean20={a.loc[both].mean():.3f} mean21={b.loc[both].mean():.3f} diff21-20={(b.loc[both]-a.loc[both]).mean():.3f}")
a20=ann_m[(ann_m.period=="ANN")&(ann_m.source=="gldas20")&(ann_m.variable=="snowfall")]
a21=ann_m[(ann_m.period=="ANN")&(ann_m.source=="gldas21")&(ann_m.variable=="snowfall")]
o20=a20[a20.year.between(2000,2014)].sort_values("year")
o21=a21[a21.year.between(2000,2014)].sort_values("year")
tr20=tm.trend_stats(o20.year.to_numpy(float), o20.value.to_numpy(float))
tr21=tm.trend_stats(o21.year.to_numpy(float), o21.value.to_numpy(float))
p(f"  ANN 2000-2014 mean20={o20.value.mean():.2f} mean21={o21.value.mean():.2f}")
p(f"  slope20={tr20['lin_slope_per_decade']:.3f} hac={tr20['hac1_p']:.4g} hr={tr20['mk_hr_p']:.4g} {tm.robust_call(tr20,False,True)}")
p(f"  slope21={tr21['lin_slope_per_decade']:.3f} hac={tr21['hac1_p']:.4g} hr={tr21['mk_hr_p']:.4g} {tm.robust_call(tr21,False,True)}")
p("  2.1 annual mm/yr:", {int(y): round(v,1) for y,v in zip(a21.sort_values('year').year, a21.sort_values('year').value)})
p("  2.0 annual 2000-2014:", {int(y): round(v,1) for y,v in zip(o20.year, o20.value)})
# windows
for y0,y1,label in [(2001,2010,"2001-2010"),(2011,2025,"2011-2025 AGRMET"),(2000,2025,"2000-2025 full"),(2002,2024,"2002-2024"),(2000,2010,"2000-2010"),(2012,2024,"2012-2024")]:
    s=a21[a21.year.between(y0,y1)]
    if len(s)<8: 
        p(f"  2.1 {label} n={len(s)} skip"); continue
    tr=tm.trend_stats(s.year.to_numpy(float), s.value.to_numpy(float))
    short=(y1-y0+1)<20
    p(f"  2.1 {label} n={len(s)} slope={tr['lin_slope_per_decade']:.3f} hac={tr['hac1_p']:.4g} hr={tr['mk_hr_p']:.4g} {tm.robust_call(tr,False,short)}")

# identity
for src in ["gldas20","gldas21"]:
    tot=tidy_m[(tidy_m.source==src)&(tidy_m.variable=="precip_total")].set_index("date").value
    liq=tidy_m[(tidy_m.source==src)&(tidy_m.variable=="rainfall_liquid")].set_index("date").value
    sn=tidy_m[(tidy_m.source==src)&(tidy_m.variable=="snowfall")].set_index("date").value
    both=tot.index.intersection(liq.index).intersection(sn.index)
    resid=(tot.loc[both]-liq.loc[both]-sn.loc[both])
    p(f"  {src} identity maxabs={resid.abs().max():.6e} mean={resid.mean():.6e} n={len(both)}")
    # any negative liquid (clip)?
    p(f"    liquid min={liq.min():.4f} snow min={sn.min():.4f} total mean mm/mo={tot.mean():.3f}")

# no splice: confirm sources stay separate; no combined series
p("  unique sources with snowfall", tidy_m[tidy_m.variable=="snowfall"].source.unique().tolist())
# 2.1 includes 2026-07? annual drops 2026. Months after Jun 2025 GALWEM?
s21=s21.copy(); s21["ym"]=s21.date.dt.strftime("%Y-%m")
p("  2.1 months in 2025-26:", s21[s21.date>=pd.Timestamp("2025-01-01")][["date","value"]].to_string(index=False))

# SWE / PRECSNO absence
p("  merra2 variables:", sorted(tidy_m[tidy_m.source=="merra2"].variable.unique().tolist()))
p("  station snow vars?", [v for v in tidy_m.variable.unique() if "snow" in str(v).lower() or "SNOW" in str(v)])

# ---------- MODIS impact from CORRECT cache
p("\n"+"="*72)
p("C. MODIS IMPACT from correct ukraine_mask cache + flags")
p("="*72)
imp=pd.read_csv("team-context/data/pipeline/data/modis_qc_impact.csv")
vi, vp = cache("mod13c2_qc","ukraine_mask")
lst, lp = cache("mod11c3_qc","ukraine_mask")
p("  VI cache", vp.name)
p("  LST cache", lp.name)
for df, keys in [(vi,["NDVI","EVI"]),(lst,["LST_Day_K","LST_Night_K"])]:
    df=df.copy(); df["date"]=pd.to_datetime(df["date"])
    for k in keys:
        q=make_tidy("modis",k,"ukraine_mask",df["date"],df[k].to_numpy(float), preaggregated=False)
        u=make_tidy("modis",k,"ukraine_mask",df["date"],df[k+"__noqc"].to_numpy(float), preaggregated=False)
        def trend(tidy, period="ANN"):
            a=annual_table(tidy)
            a=a[(a.period==period)&(a.year<=LAST_FULL_YEAR)&(a.year>=2001)].sort_values("year")
            tr=tm.trend_stats(a.year.to_numpy(float), a.value.to_numpy(float))
            return tr,len(a),tm.robust_call(tr, monthly=False, short_record=False)
        tq,nq,cq=trend(q); tu,nu,cu=trend(u)
        kept=df[k+"__qc_kept_area_frac"]; cov=df[k+"__cov"]
        outname=q.variable.iloc[0]
        row=imp[(imp.region=="ukraine_mask")&(imp.variable==outname)].iloc[0]
        p(f"  {outname}: area_removed_mean={100*(1-kept.mean()):.4f} csv={row.area_removed_by_qc_pct_mean:.4f}  max={100*(1-kept.min()):.4f} csv={row.area_removed_by_qc_pct_max:.4f}")
        p(f"    lt50 cov={int((cov<0.5).sum())} kept={int((kept<0.5).sum())} csv={int(row.months_qc_coverage_lt50pct)}")
        p(f"    trend_qc={tq['lin_slope_per_decade']:.6f} csv={row.trend_qc_per_decade:.6f} match={np.isclose(tq['lin_slope_per_decade'],row.trend_qc_per_decade,atol=1e-6)}")
        p(f"    trend_noqc={tu['lin_slope_per_decade']:.6f} csv={row.trend_noqc_per_decade:.6f} match={np.isclose(tu['lin_slope_per_decade'],row.trend_noqc_per_decade,atol=1e-6)}")
        p(f"    robust_qc={cq} | csv={row.robust_qc}")
        p(f"    robust_noqc={cu} | csv={row.robust_noqc}")
        for per in ("DJF","JJA"):
            tqs,_,_=trend(q,per); tus,_,_=trend(u,per)
            p(f"    {per} qc={tqs['lin_slope_per_decade']:.6f} noqc={tus['lin_slope_per_decade']:.6f}")
        p(f"    kept weighted: mean={kept.mean():.3f} DJF={kept[df.date.dt.month.isin([12,1,2])].mean():.3f} JJA={kept[df.date.dt.month.isin([6,7,8])].mean():.3f}")

# flags via bracket
mod=tidy_m[tidy_m.source=="modis"]
for var,g in mod.groupby("variable"):
    fl=g["flags"].fillna("")
    flags=Counter()
    for f in fl:
        for x in str(f).split(";"):
            if x: flags[x]+=1
    n50=int(fl.str.contains("qc_low_coverage_lt50pct").sum())
    nno=int(fl.str.contains("no_qc").sum())
    nqc=int(fl.str.contains("qc_pixel_masked").sum())
    p(f"  tidy {var}: n={len(g)} cov min/med={g.coverage_frac.min():.3f}/{g.coverage_frac.median():.3f} qc_pixel_masked={nqc} no_qc={nno} lt50={n50} flags={dict(flags)}")
    if n50:
        low=g[fl.str.contains("qc_low_coverage_lt50pct")].copy()
        p(f"    lt50 by month {low.date.dt.month.value_counts().sort_index().to_dict()} n_years={low.date.dt.year.nunique()}")

ndvi=tidy_m[(tidy_m.source=="modis")&(tidy_m.variable=="NDVI")].copy()
ndvi["year"]=ndvi.date.dt.year
ndvi["low"]=ndvi["flags"].fillna("").str.contains("qc_low_coverage_lt50pct")
years_low=set(ndvi.loc[ndvi.low,"year"])
ann_ndvi=set(ann_m[(ann_m.source=="modis")&(ann_m.variable=="NDVI")&(ann_m.period=="ANN")].year)
p(f"  NDVI years with lt50 month: {sorted(years_low)} n={len(years_low)}; of those in 12/12 ANN: {len(years_low & ann_ndvi)}")

# LST clear days
for var in ["LST_Day_clear_days","LST_Night_clear_days"]:
    g=tidy_m[(tidy_m.source=="modis")&(tidy_m.variable==var)].copy()
    g["month"]=g.date.dt.month
    p(f"  {var} mean={g.value.mean():.2f} by month {g.groupby('month').value.mean().round(1).to_dict()}")

# ---------- MERRA flags / Jul 1980 / DTR
p("\n"+"="*72)
p("D. MERRA-2 DTR/wind remainder")
p("="*72)
def ser(src,var,tidy=tidy_m):
    return tidy[(tidy.source==src)&(tidy.variable==var)].sort_values("date")
tmax,tmin,dtr,t2m=ser("merra2","T2MMAX"),ser("merra2","T2MMIN"),ser("merra2","DTR"),ser("merra2","T2M")
m=tmax.merge(tmin,on="date",suffixes=("_x","_n")).merge(dtr,on="date")
resid=m.value_x-m.value_n-m.value
p(f"  DTR identity maxabs={resid.abs().max():.6e}")
for tidy,reg in [(tidy_b,"bbox"),(tidy_m,"mask")]:
    j=pd.Timestamp("1980-07-01")
    vals={v: float(ser("merra2",v,tidy).set_index("date").value.loc[j]) for v in ["T2M","T2MMAX","T2MMIN","DTR"]}
    p(f"  Jul 1980 {reg}: {vals}")
ws,u,v=ser("merra2","WS10M_from_mean_UV"),ser("merra2","U10M"),ser("merra2","V10M")
m=u.merge(v,on="date",suffixes=("_u","_v")).merge(ws,on="date")
hyp=np.hypot(m.value_u,m.value_v)
p(f"  mean WS={m.value.mean():.3f} mean hypot(reg U,V)={hyp.mean():.3f} POWER WS={ser('nasa_power','WS10M').value.mean():.3f}")
p(f"  WS>=hypot always {(m.value+1e-9>=hyp).all()}")
for var in ["U10M","V10M","WS10M_from_mean_UV","T2MMAX","T2MMIN","DTR"]:
    g=tidy_m[(tidy_m.source=="merra2")&(tidy_m.variable==var)]
    p(f"  {var}: n={len(g)} unit={g.unit.iloc[0]} flags={g['flags'].value_counts().to_dict()}")

# ---------- multiple testing
p("\n"+"="*72)
p("E. MULTIPLE TESTING")
p("="*72)
for region,path in [("ukraine_mask","team-context/data/pipeline/data/tidy/ukraine_mask/trends.csv"),
                    ("ukraine_bbox","team-context/data/pipeline/data/tidy/ukraine_bbox/trends.csv")]:
    df=pd.read_csv(path)
    ann=df[df.series=="annual_ANN_12of12"]
    n_finite=int(ann.hac1_p.notna().sum())
    fam=int(ann.n_tests_in_family.dropna().iloc[0])
    p(f"  [{region}] rows={len(df)} annual={len(ann)} finite hac1={n_finite} family={fam} match={n_finite==fam}")
    # monthly family
    mon=df[df.series.str.contains("monthly")]
    p(f"    monthly n={len(mon)} family unique={sorted(mon.n_tests_in_family.dropna().unique().tolist())} finite hac3={int(mon.hac3_p.notna().sum()) if 'hac3_p' in mon.columns else 'na'}")
    new=["T2MMAX","T2MMIN","DTR","U10M","V10M","WS10M_from_mean_UV","precip_total","snowfall","rainfall_liquid","LST_Day_clear_days","LST_Night_clear_days"]
    in_ann=ann[ann.variable.isin(new)]
    p(f"    new-var annual rows={len(in_ann)} vars={sorted(in_ann.variable.unique())}")
    # if we dropped new vars, family would be smaller
    p(f"    family without new-var rows would be {n_finite-len(in_ann[in_ann.hac1_p.notna()])}")
    sub=df[(df.headline==True)&(df.variable.isin(new+["NDVI","EVI","LST_Day","LST_Night"]))]
    cols=["source","variable","n","lin_slope_per_decade","hac1_p","hac1_bonferroni_reject","hac1_bh_reject","mk_hr_p","mk_hr_bonferroni_reject","mk_hr_bh_reject","n_tests_in_family","robust_call"]
    with pd.option_context("display.max_colwidth",72,"display.width",240):
        p(sub[cols].to_string(index=False))

# JJA not in official trends
tr=pd.read_csv("team-context/data/pipeline/data/tidy/ukraine_mask/trends.csv")
p("  official series types:", tr.series.unique().tolist())
p("  any JJA/growing in window or series?", tr.series.str.contains("JJA|growing|DJF|seasonal_JJA",case=False).any())

# ---------- MODIS bit decode
p("\n"+"="*72)
p("F. MODIS BIT SPOT-DECODE")
p("="*72)
lat,lon=_cmg_coords()
p(f"  CMG lat {lat[0]:.4f}..{lat[-1]:.4f} n={len(lat)} lon {lon[0]:.4f}..{lon[-1]:.4f} n={len(lon)}")
lo0,la0,lo1,la1=22.1,44.4,40.2,52.4
iy=np.where((lat>=la0)&(lat<=la1))[0]
ix=np.where((lon>=lo0)&(lon<=lo1))[0]
ys,xs=slice(int(iy.min()),int(iy.max())+1), slice(int(ix.min()),int(ix.max())+1)
p(f"  window {iy.size}x{ix.size}")

def find_modis(d, year, month):
    import datetime
    doy=datetime.date(year,month,1).timetuple().tm_yday
    files=sorted(Path(d).glob(f"*.A{year}{doy:03d}.*.nc4"))
    if files: return files[0]
    files=sorted(Path(d).glob(f"*.A{year}*.nc4"))
    def doy_of(p):
        name=p.name; i=name.index(".A")+2; return int(name[i+4:i+7])
    files=sorted(files, key=lambda p: abs(doy_of(p)-doy))
    return files[0] if files else None

for year,month,tag in [(2003,1,"Jan 2003"),(2003,7,"Jul 2003"),(2010,1,"Jan 2010")]:
    fvi=find_modis("$GLOBAL_DATA/mod13c2_qc", year, month)
    dvi=Path("$GLOBAL_DATA/mod13c2_slim")/fvi.name
    fls=find_modis("$GLOBAL_DATA/mod11c3_qc", year, month)
    dls=Path("$GLOBAL_DATA/mod11c3_slim")/fls.name
    p(f"\n  === {tag} === VI={fvi.name} LST={fls.name}")
    with netCDF4.Dataset(fvi) as qds, netCDF4.Dataset(dvi) as ds:
        rel=_rawq(qds, VI_QC+"CMG_0_05_Deg_Monthly_pixel_reliability", ys, xs).astype(np.int16)
        viq=_rawq(qds, VI_QC+"CMG_0_05_Deg_Monthly_VI_Quality", ys, xs).astype(np.uint32)
        ndvi_v=ds[VI_QC+"CMG_0_05_Deg_Monthly_NDVI"]; ndvi_v.set_auto_maskandscale(False)
        ndvi=np.asarray(ndvi_v[ys,xs], dtype=np.float64)
        good=_vi_good(qds, ys, xs)
        mand=viq & 0b11
        p(f"    rel unique {dict(zip(*np.unique(rel, return_counts=True)))}")
        p(f"    mand unique {dict(zip(*np.unique(mand, return_counts=True)))}")
        p(f"    _vi_good {int(good.sum())}/{good.size}={good.mean():.3f}")
        for r in sorted(np.unique(rel)):
            sub=mand[rel==r]
            p(f"      rel={int(r)} n={sub.size} mand {dict(zip(*np.unique(sub, return_counts=True)))} good_frac={good[rel==r].mean():.3f}")
        inc1=int((((rel==0)|(rel==1)) & (mand>=2)).sum())
        inc2=int((((rel>=2)&(rel<=4)) & (mand<=1)).sum())
        p(f"    inconsistent rel 0/1 & mand 10/11={inc1}; rel 2-4 & mand 00/01={inc2}")
        for target,name in [((rel==0)&(mand==0),"good_rel0_mand00"),((rel==1),"marginal_rel1"),((rel==2),"snow_rel2"),((rel==3),"cloud_rel3"),((rel==4),"estimated_rel4")]:
            idx=np.argwhere(target)
            if len(idx)==0:
                p(f"      no pixel {name}"); continue
            i,j=idx[len(idx)//2]
            p(f"      ex {name}: lat={lat[ys][i]:.3f} lon={lon[xs][j]:.3f} rel={int(rel[i,j])} VIQ={int(viq[i,j])} bits0-1={int(mand[i,j]):02b} NDVI_raw={int(ndvi[i,j])} good={bool(good[i,j])}")
    with netCDF4.Dataset(fls) as qds, netCDF4.Dataset(dls) as ds:
        for which,lname in [("Day","LST_Day_CMG"),("Night","LST_Night_CMG")]:
            q=_rawq(qds, LST_QC+f"QC_{which}", ys, xs).astype(np.uint8)
            mand=q&0b11; err=(q>>6)&0b11
            good=_lst_good(which)(qds, ys, xs)
            lstv=ds[LST_QC+lname]; lstv.set_auto_maskandscale(False)
            lst=np.asarray(lstv[ys,xs], dtype=np.float64)
            p(f"    LST_{which}: mand {dict(zip(*np.unique(mand, return_counts=True)))} err {dict(zip(*np.unique(err, return_counts=True)))} good={good.mean():.3f} fill0={(lst==0).mean():.3f}")
            for mval in range(4):
                sub=(mand==mval)
                p(f"      mand={mval:02b} n={int(sub.sum())} fill0={(lst[sub]==0).mean() if sub.any() else np.nan:.3f} err={dict(zip(*np.unique(err[sub], return_counts=True))) if sub.any() else {}} good={good[sub].mean() if sub.any() else np.nan:.3f}")
            for target,name in [((mand==0)&(lst!=0),"mand00"),((mand==1)&(err<=1)&(lst!=0),"mand01_err<=2K"),((mand==1)&(err>=2)&(lst!=0),"mand01_err>2K"),((mand>=2),"mand10/11")]:
                idx=np.argwhere(target)
                if len(idx)==0:
                    p(f"      no pixel {name}"); continue
                i,j=idx[len(idx)//2]
                p(f"      ex {name}: lat={lat[ys][i]:.3f} lon={lon[xs][j]:.3f} QC={int(q[i,j])} mand={mand[i,j]:02b} err={err[i,j]:02b} LST_K={lst[i,j]*0.02:.2f} good={bool(good[i,j])}")
            p(f"      QC==0 n={(q==0).sum()} all_good={good[q==0].all() if (q==0).any() else 'n/a'}")
            qobj=qds[LST_QC+f"QC_{which}"]
            fills={a:getattr(qobj,a) for a in qobj.ncattrs() if a.lower() in ("_fillvalue","missing_value")}
            p(f"      fill attrs {fills}")

# popcount sanity: one January file, a pixel with known bit pattern
p("\n  popcount check vs Clear_sky_days (Jan 2003, few pixels)")
from ukpipe.loaders.global_grids import _popcount32
fls=find_modis("$GLOBAL_DATA/mod11c3_qc", 2003, 1)
with netCDF4.Dataset(fls) as qds:
    raw=_rawq(qds, LST_QC+"Clear_sky_days", ys, xs).astype(np.float64)
    pc=_popcount32(raw)
    # compare to python bin().count
    rawu=np.nan_to_num(raw,nan=0).astype(np.uint32)
    py=np.array([[bin(int(x)).count("1") for x in row] for row in rawu])
    p(f"    popcount vs bin().count maxabs={np.max(np.abs(pc-py)):.0f} mean pc={pc.mean():.2f} max={pc.max():.0f}")
    # mid pixel
    i,j=pc.shape[0]//2, pc.shape[1]//2
    p(f"    mid pixel raw={int(rawu[i,j])} bits={bin(int(rawu[i,j]))} pop={pc[i,j]} py={py[i,j]}")

OUT.write_text("\n".join(lines)+"\n")
p("Wrote", OUT)
