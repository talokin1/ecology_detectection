#!/usr/bin/env python3
from __future__ import annotations
import os, sys, json
from pathlib import Path
os.environ["OMP_NUM_THREADS"] = "1"
sys.path.insert(0, "$UKRAINE_SAMPLES/_staging")
sys.path.insert(0, "team-context/data/pipeline")

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests
import trend_methods as tm
from ukpipe.grace_method import grace_headline_trend

OUT = Path("team-context/team/reviews/pipeline_v13_checks_out.txt")
lines=[]
def p(*a):
    s=" ".join(str(x) for x in a)
    lines.append(s); print(s, flush=True)

def bh_manual(p):
    p=np.asarray(p, float)
    n=len(p)
    order=np.argsort(p)
    ranks=np.empty(n, int); ranks[order]=np.arange(1,n+1)
    # BH critical: reject largest k with p_(k) <= k*alpha/n; q-value: p*n/rank, then monotone
    q=np.minimum(1.0, p*n/ranks)
    # step-up: going from largest p, q_i = min(q_i, q_{i+1})
    q_ord=q[order]
    for i in range(n-2,-1,-1):
        q_ord[i]=min(q_ord[i], q_ord[i+1])
    qv=np.empty(n); qv[order]=q_ord
    return qv, qv<=0.05

def check_mt(df, pcol, prefix, family_expected=None):
    sub=df[np.isfinite(df[pcol])]
    pvals=sub[pcol].to_numpy(float)
    n=len(pvals)
    rej_b, p_b, _, _ = multipletests(pvals, alpha=0.05, method="bonferroni")
    rej_h, p_h, _, _ = multipletests(pvals, alpha=0.05, method="fdr_bh")
    q_man, rej_man = bh_manual(pvals)
    # compare to columns
    alpha=0.05/n if n else np.nan
    d_alpha=np.nanmax(np.abs(sub[f"{prefix}_bonferroni_alpha"].to_numpy(float)-alpha)) if n else 0
    d_pb=np.nanmax(np.abs(sub[f"{prefix}_bonferroni_p"].to_numpy(float)-p_b))
    d_ph=np.nanmax(np.abs(sub[f"{prefix}_bh_q"].to_numpy(float)-p_h))
    d_man=np.nanmax(np.abs(sub[f"{prefix}_bh_q"].to_numpy(float)-q_man))
    same_b=np.array_equal(sub[f"{prefix}_bonferroni_reject"].to_numpy(bool), rej_b)
    same_h=np.array_equal(sub[f"{prefix}_bh_reject"].to_numpy(bool), rej_h)
    same_man=np.array_equal(sub[f"{prefix}_bh_reject"].to_numpy(bool), rej_man)
    fam_col=sub["n_tests_in_family"].dropna().unique()
    p(f"  {pcol}/{prefix}: n_finite={n} family_col={fam_col.tolist()} expected={family_expected} "
      f"d_alpha={d_alpha:.2e} d_pbonf={d_pb:.2e} d_bh={d_ph:.2e} d_bh_manual={d_man:.2e} "
      f"reject_match_bonf={same_b} bh_sm={same_h} bh_manual={same_man} n_bonf_rej={int(rej_b.sum())} n_bh_rej={int(rej_h.sum())}")
    return n, rej_b, rej_h

for region in ["ukraine_mask","ukraine_bbox","ukraine_mask_no_crimea"]:
    df=pd.read_csv(f"team-context/data/pipeline/data/tidy/{region}/trends.csv")
    p("\n"+"="*72)
    p(f"REGION {region} n={len(df)}")
    p("="*72)
    p("  unique region col:", df.region.unique().tolist())
    p("  roles:", df.role.value_counts().to_dict())
    p("  test_family:", df.test_family.value_counts().to_dict())
    p("  headline counts:", df.headline.value_counts().to_dict())
    p("  series:", df.series.value_counts().to_dict())
    p("  slope_unit unique:", sorted(df.slope_unit.dropna().unique().tolist()))

    # family sizes
    ann=df[df.test_family=="annual"]
    mon=df[df.test_family=="monthly"]
    p(f"  annual rows={len(ann)} finite hac1={ann.hac1_p.notna().sum()} finite hr={ann.mk_hr_p.notna().sum()} n_tests unique={sorted(ann.n_tests_in_family.dropna().unique().tolist())}")
    p(f"  monthly rows={len(mon)} finite hac3={mon.hac3_p.notna().sum()} finite hr={mon.mk_hr_p.notna().sum()} n_tests unique={sorted(mon.n_tests_in_family.dropna().unique().tolist())}")
    # monthly: is mk_hr MT filled?
    p(f"  monthly mk_hr_bonferroni_reject non-null={mon.mk_hr_bonferroni_reject.notna().sum()} hac3_bonf non-null={mon.hac3_bonferroni_reject.notna().sum()}")

    p("  -- recompute MT --")
    check_mt(ann, "hac1_p", "hac1")
    check_mt(ann, "mk_hr_p", "mk_hr")
    check_mt(mon, "hac3_p", "hac3")

    # mt_*_pass definition
    a=df[df.test_family=="annual"].copy()
    m=df[df.test_family=="monthly"].copy()
    a_exp_b=(a.hac1_bonferroni_reject.fillna(False).astype(bool) & a.mk_hr_bonferroni_reject.fillna(False).astype(bool))
    a_exp_h=(a.hac1_bh_reject.fillna(False).astype(bool) & a.mk_hr_bh_reject.fillna(False).astype(bool))
    m_exp_b=m.hac3_bonferroni_reject.fillna(False).astype(bool)
    m_exp_h=m.hac3_bh_reject.fillna(False).astype(bool)
    p(f"  mt_bonf annual match AND(hac1,hr)={(a.mt_bonferroni_pass.astype(bool)==a_exp_b).all()}  monthly match hac3-only={(m.mt_bonferroni_pass.astype(bool)==m_exp_b).all()}")
    p(f"  mt_bh annual match AND(hac1,hr)={(a.mt_bh_pass.astype(bool)==a_exp_h).all()}  monthly match hac3-only={(m.mt_bh_pass.astype(bool)==m_exp_h).all()}")

    # Alternative: BH/Bonf on max(hac,hr) for annual
    both=a[np.isfinite(a.hac1_p)&np.isfinite(a.mk_hr_p)]
    pstar=np.maximum(both.hac1_p, both.mk_hr_p)
    n=len(pstar)
    rej_b_max, _, _, _ = multipletests(pstar, alpha=0.05, method="bonferroni")
    rej_h_max, _, _, _ = multipletests(pstar, alpha=0.05, method="fdr_bh")
    and_b=both.mt_bonferroni_pass.astype(bool).to_numpy()
    and_h=both.mt_bh_pass.astype(bool).to_numpy()
    p(f"  annual Bonferroni on max(hac,hr) vs AND: agree={(rej_b_max==and_b).all()}  n_max={rej_b_max.sum()} n_and={and_b.sum()}")
    p(f"  annual BH on max(hac,hr) vs AND: agree={(rej_h_max==and_h).all()}  n_max={rej_h_max.sum()} n_and={and_h.sum()}")
    if not (rej_h_max==and_h).all():
        disag=both[rej_h_max!=and_h][["source","variable","series","window","hac1_p","mk_hr_p","hac1_bh_reject","mk_hr_bh_reject","mt_bh_pass"]]
        disag=disag.copy(); disag["bh_on_max"]=rej_h_max[rej_h_max!=and_h]
        p("  BH disagreements (AND vs max):")
        p(disag.to_string(index=False))

    # forcing / sampling / annual VI
    p("\n  -- role/headline checks --")
    for src,var,role in [("gldas21","snowfall","forcing_diagnostic"),("gldas21","SWE_inst","forcing_diagnostic"),
                         ("modis","LST_Day_clear_days","sampling_diagnostic"),("modis","LST_Night_clear_days","sampling_diagnostic")]:
        sub=df[(df.source==src)&(df.variable==var)]
        p(f"  {src}:{var} n={len(sub)} roles={sub.role.unique().tolist()} headlines={sub.headline.unique().tolist()}")
        if len(sub):
            p("    windows/series:", sub[["series","window","headline","role","lin_slope_per_decade","slope_unit","robust_call"]].to_string(index=False)[:2000])

    vi=df[(df.source=="modis")&(df.variable.isin(["NDVI","EVI"]))]
    p("\n  VI rows:")
    cols=["variable","series","window","n","lin_slope_per_decade","hac1_p","mk_hr_p","robust_call","role","headline","mt_bonferroni_pass","mt_bh_pass","slope_unit"]
    with pd.option_context("display.max_colwidth", 90, "display.width", 240):
        p(vi[cols].to_string(index=False))

    # snow unit
    sn=df[(df.source=="gldas21")&(df.variable=="snowfall")&(df.series=="annual_ANN_12of12")&(df.window=="full")]
    if len(sn):
        p(f"  snowfall full slope={sn.lin_slope_per_decade.iloc[0]:.4f} unit={sn.unit.iloc[0]} slope_unit={sn.slope_unit.iloc[0]} headline={sn.headline.iloc[0]} role={sn.role.iloc[0]}")

    # GRACE
    g=df[(df.source=="grace")]
    p("\n  GRACE rows:")
    p(g[["region","series","window","n","lin_slope_per_decade","unit","slope_unit","headline","role","mt_bonferroni_pass","mt_bh_pass","hac3_p","mk_hr_p","robust_call"]].to_string(index=False)[:3000])

    # survivors
    p("\n  -- mt_bonferroni_pass=True --")
    surv=df[df.mt_bonferroni_pass.astype(bool)][["source","variable","series","window","region","n","lin_slope_per_decade","slope_unit","role","headline","robust_call","hac1_p","mk_hr_p","hac3_p","mt_bh_pass"]]
    with pd.option_context("display.max_colwidth", 70, "display.width", 240):
        p(surv.to_string(index=False))
        p(f"  n bonf survivors={len(surv)} of which headline={int(surv.headline.astype(bool).sum())}")

    p("\n  -- headline=True and mt_bonf False --")
    h=df[df.headline.astype(bool)]
    fail_both=h[(~h.mt_bonferroni_pass.astype(bool)) & (~h.mt_bh_pass.astype(bool))]
    fail_bonf_pass_bh=h[(~h.mt_bonferroni_pass.astype(bool)) & (h.mt_bh_pass.astype(bool))]
    robustish=h[h.robust_call.str.contains("robust at 0.05", na=False)]
    p(f"  headlines={len(h)}  robust_call contains 'robust at 0.05'={len(robustish)}")
    p(f"  headline fail both MT={len(fail_both)}; fail Bonf but pass BH={len(fail_bonf_pass_bh)}")
    show=["source","variable","series","window","lin_slope_per_decade","robust_call","mt_bonferroni_pass","mt_bh_pass","role","hac1_p","mk_hr_p","hac3_p"]
    p("  robust headlines:")
    with pd.option_context("display.max_colwidth", 100, "display.width", 240):
        p(robustish[show].to_string(index=False))
    p("  headline fail BOTH MT:")
    with pd.option_context("display.max_colwidth", 100, "display.width", 240):
        p(fail_both[show].to_string(index=False) if len(fail_both) else "  (none)")
    p("  headline fail Bonf, pass BH:")
    with pd.option_context("display.max_colwidth", 100, "display.width", 240):
        p(fail_bonf_pass_bh[show].to_string(index=False) if len(fail_bonf_pass_bh) else "  (none)")

    # any headline that fails both MT and whose robust_call/role doesn't mention MT, diagnostic, or not treated as robust?
    def says_so(r):
        t=(str(r.robust_call)+" "+str(r.role)).lower()
        return any(k in t for k in ["bonferroni","benjamini","bh ","not treated as robust","not significant","method-dependent","forcing","sampling","different convention","gappy","low_coverage","low coverage"])
    silent=fail_both[~fail_both.apply(says_so, axis=1)]
    p(f"  headline fail both MT with no mention in robust_call/role: {len(silent)}")
    if len(silent):
        p(silent[show].to_string(index=False))

    # also robust+fail both (the dangerous case)
    dang=robustish[(~robustish.mt_bonferroni_pass.astype(bool))&(~robustish.mt_bh_pass.astype(bool))]
    p(f"  'robust at 0.05' headlines that fail BOTH MT: {len(dang)}")
    if len(dang):
        with pd.option_context("display.max_colwidth", 120, "display.width", 240):
            p(dang[show].to_string(index=False))

# smoke + GRACE recompute + VI recompute
p("\n"+"="*72)
p("RECOMPUTES")
p("="*72)
from ukpipe.core import LAST_FULL_YEAR
ann_m=pd.read_parquet("team-context/data/pipeline/data/tidy/ukraine_mask/annual_seasonal.parquet")
ann_b=pd.read_parquet("team-context/data/pipeline/data/tidy/ukraine_bbox/annual_seasonal.parquet")
tidy_m=pd.read_parquet("team-context/data/pipeline/data/tidy/ukraine_mask/all_monthly_long.parquet")
tidy_b=pd.read_parquet("team-context/data/pipeline/data/tidy/ukraine_bbox/all_monthly_long.parquet")

def ann_trend(ann, src, var, period, y0, y1):
    s=ann[(ann.period==period)&(ann.source==src)&(ann.variable==var)&(ann.year.between(y0,y1))].sort_values("year")
    tr=tm.trend_stats(s.year.to_numpy(float), s.value.to_numpy(float))
    return s, tr, tm.robust_call(tr, monthly=False, short_record=False)

for period,y0,y1,label in [("JJA",2001,2025,"JJA"),("AMJJAS",2001,2025,"Apr-Sep")]:
    for var in ["NDVI","EVI"]:
        s,tr,call=ann_trend(ann_m,"modis",var,period,y0,y1)
        p(f"  mask {var} {label} n={len(s)} {int(s.year.min())}-{int(s.year.max())} slope={tr['lin_slope_per_decade']:.6f} hac={tr['hac1_p']:.6g} hr={tr['mk_hr_p']:.6g} {call}")

# AMJJAS present?
p("  periods in annual_seasonal mask:", sorted(ann_m.period.unique()))
# 6/6 check
mod=tidy_m[(tidy_m.source=="modis")&(tidy_m.variable=="EVI")].copy()
mod["year"]=mod.date.dt.year; mod["month"]=mod.date.dt.month
for y in range(2001,2026):
    sg=mod[(mod.year==y)&(mod.month.between(4,9))]
    if sg.month.nunique()!=6 or sg.value.notna().sum()!=6:
        p(f"  EVI Apr-Sep incomplete year {y}: months={sorted(sg.month)} nvalid={sg.value.notna().sum()}")

# means GPCC/CHIRPS
for src,ref in [("gpcc",585.35),("chirps",686.78)]:
    s=ann_b[(ann_b.period=="ANN")&(ann_b.source==src)&(ann_b.variable=="precip")&(ann_b.year.between(1981,2025))]
    p(f"  bbox {src} 1981-2025 ANN mean={s.value.mean():.4f} ref={ref} diff={s.value.mean()-ref:+.4f}")

# smoke
for src,var,ref in [("nasa_power","T2M",0.5526),("hadcrut5","tas_anomaly",0.5793)]:
    s=ann_b[(ann_b.period=="ANN")&(ann_b.source==src)&(ann_b.variable==var)&(ann_b.year.between(1981,2025))].sort_values("year")
    tr=tm.trend_stats(s.year.to_numpy(float), s.value.to_numpy(float))
    p(f"  smoke {src} slope={tr['lin_slope_per_decade']:.6f} ref={ref} pass={abs(tr['lin_slope_per_decade']-ref)<=0.005} n={len(s)}")
for lab,tidy,ref in [("bbox",tidy_b,-11.242),("mask",tidy_m,-12.12)]:
    g=tidy[(tidy.source=="grace")&(tidy.variable=="TWS")].copy()
    tr=grace_headline_trend(g)
    p(f"  GRACE {lab} n={tr['n']} slope={tr['lin_slope_per_decade']:.6f} vs {ref} region_in_tidy={g.region.unique().tolist()}")

# README / report notes already grepped; count low-coverage months in 2001-2025 vs record
ndvi=tidy_m[(tidy_m.source=="modis")&(tidy_m.variable=="NDVI")].copy()
# flags via bracket
low=ndvi["flags"].fillna("").str.contains("qc_low_coverage_lt50pct")
p(f"  mask NDVI lt50 months all={int(low.sum())} in 2001-2025={int(low[ndvi.date.dt.year.between(2001,2025)].sum())} by month all={ndvi.loc[low].date.dt.month.value_counts().sort_index().to_dict()}")
ndvi_b=tidy_b[(tidy_b.source=="modis")&(tidy_b.variable=="NDVI")].copy()
lowb=ndvi_b["flags"].fillna("").str.contains("qc_low_coverage_lt50pct")
p(f"  bbox NDVI lt50 months all={int(lowb.sum())} in 2001-2025={int(lowb[ndvi_b.date.dt.year.between(2001,2025)].sum())}")

# monthly headlines: would HR Bonferroni change anything?
p("\n  monthly headlines and HR p vs family")
for region in ["ukraine_mask","ukraine_bbox"]:
    df=pd.read_csv(f"team-context/data/pipeline/data/tidy/{region}/trends.csv")
    mon=df[df.test_family=="monthly"]
    n=int(mon.hac3_p.notna().sum())
    # would-be HR bonferroni
    sub=mon[np.isfinite(mon.mk_hr_p)]
    if len(sub):
        rej, padj, _, _ = multipletests(sub.mk_hr_p.to_numpy(float), alpha=0.05, method="bonferroni")
        sub=sub.copy(); sub["hr_bonf_would"]=rej
        h=sub[sub.headline.astype(bool)]
        p(f"  {region} monthly family n={n} (hr finite {len(sub)}) headline rows:")
        p(h[["source","variable","series","hac3_p","mk_hr_p","mt_bonferroni_pass","hr_bonf_would","lin_slope_per_decade"]].to_string(index=False))

OUT.write_text("\n".join(lines)+"\n")
p("Wrote", OUT)
