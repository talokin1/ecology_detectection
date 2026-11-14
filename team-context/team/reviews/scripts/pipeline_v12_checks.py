#!/usr/bin/env python3
"""Spot-checks for pipeline v1.2. Read-only. Writes team-context/team/reviews/pipeline_v12_checks_out.txt"""
from __future__ import annotations
import sys, os, json, glob
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
from ukpipe.grace_method import grace_headline_trend

OUT = Path("team-context/team/reviews/pipeline_v12_checks_out.txt")
lines = []
def p(*a):
    s = " ".join(str(x) for x in a)
    lines.append(s)
    print(s, flush=True)

# ---------------------------------------------------------------------------
# 1. File attributes
# ---------------------------------------------------------------------------
p("=" * 72)
p("1. FILE ATTRIBUTES")
p("=" * 72)

f = sorted(glob.glob("$GLOBAL_DATA/merra2_statm_extremes/*.nc4"))[0]
p("\n--- MERRA-2 extremes ---", f)
with netCDF4.Dataset(f) as ds:
    for a in ds.ncattrs():
        if any(k in a.lower() for k in ("title", "comment", "history", "source", "institution", "shortname", "longname", "product", "collection", "conventions")):
            val = str(getattr(ds, a))
            p(f"  global {a}: {val[:500]}")
    for v in ["T2MMAX", "T2MMIN", "T2M"]:
        if v in ds.variables:
            vv = ds[v]
            p(f"  -- {v} dtype={vv.dtype} shape={vv.shape}")
            for a in vv.ncattrs():
                p(f"     {a}: {str(getattr(vv, a))[:400]}")

f = sorted(glob.glob("$GLOBAL_DATA/merra2_flx_slim/*.nc4"))[0]
p("\n--- MERRA-2 flx vars ---", list(netCDF4.Dataset(f).variables))
# close properly
with netCDF4.Dataset(f) as ds:
    p("  flx vars:", list(ds.variables))

f = sorted(glob.glob("$GLOBAL_DATA/gldas21_rainf/*.nc4"))[0]
p("\n--- GLDAS 2.1 rainf ---", f)
with netCDF4.Dataset(f) as ds:
    p("  vars:", list(ds.variables))
    for a in ds.ncattrs():
        if any(k in a.lower() for k in ("title", "comment", "history", "source", "references", "institution", "comment")):
            p(f"  global {a}: {str(getattr(ds, a))[:500]}")
    for v in ["Rainf_f_tavg", "Rainf_tavg", "Snowf_tavg"]:
        if v in ds.variables:
            vv = ds[v]
            p(f"  -- {v}")
            for a in vv.ncattrs():
                p(f"     {a}: {str(getattr(vv, a))[:400]}")

f = sorted(glob.glob("$GLOBAL_DATA/gldas20_rainf/*.nc4"))[0]
p("\n--- GLDAS 2.0 rainf ---", f)
with netCDF4.Dataset(f) as ds:
    p("  vars:", list(ds.variables))
    for v in ["Rainf_f_tavg", "Rainf_tavg", "Snowf_tavg"]:
        if v in ds.variables:
            vv = ds[v]
            p(f"  -- {v}")
            for a in vv.ncattrs():
                p(f"     {a}: {str(getattr(vv, a))[:400]}")

# MODIS QC attrs for one January and one July file
for tag, pat, want_month in [
    ("MOD13C2 Jan", "$GLOBAL_DATA/mod13c2_qc/MOD13C2.A2000032.061*.nc4", 1),
    ("MOD11C3 Jan", "$GLOBAL_DATA/mod11c3_qc/MOD11C3.A2000032.061*.nc4", 1),
]:
    fs = glob.glob(pat)
    if not fs:
        p("MISSING", tag, pat)
        continue
    f = fs[0]
    p(f"\n--- {tag} --- {f}")
    with netCDF4.Dataset(f) as ds:
        def walk(g, prefix=""):
            for v in g.variables:
                path = f"{prefix}{v}"
                if any(k in v.lower() for k in ("quality", "reliab", "qc_", "clear_sky", "lst_", "ndvi", "evi")):
                    vv = g[v]
                    p(f"  {path} dtype={vv.dtype} shape={vv.shape}")
                    for a in vv.ncattrs():
                        s = str(getattr(vv, a))
                        if a.lower() in ("_fillvalue", "missing_value", "valid_range", "long_name", "units", "scale_factor", "legend", "description", "flag_values", "flag_meanings") or "bit" in a.lower() or "qa" in a.lower() or "comment" in a.lower():
                            p(f"     {a}: {s[:600]}")
            for name in g.groups:
                walk(g.groups[name], prefix + name + "/")
        walk(ds)

# ---------------------------------------------------------------------------
# 2. Smoke + GPCC/CHIRPS from tidy
# ---------------------------------------------------------------------------
p("\n" + "=" * 72)
p("2. SMOKE / GPCC / CHIRPS from tidy (ukraine_bbox)")
p("=" * 72)

ann_b = pd.read_parquet("team-context/data/pipeline/data/tidy/ukraine_bbox/annual_seasonal.parquet")
tidy_b = pd.read_parquet("team-context/data/pipeline/data/tidy/ukraine_bbox/all_monthly_long.parquet")
ann_m = pd.read_parquet("team-context/data/pipeline/data/tidy/ukraine_mask/annual_seasonal.parquet")
tidy_m = pd.read_parquet("team-context/data/pipeline/data/tidy/ukraine_mask/all_monthly_long.parquet")

def get_ann(ann, src, var, y0=1981, y1=2025):
    s = ann[(ann.period == "ANN") & (ann.source == src) & (ann.variable == var) & (ann.year >= y0) & (ann.year <= y1)].sort_values("year")
    return s

# POWER, HadCRUT
for src, var, ref in [("nasa_power", "T2M", 0.5526), ("hadcrut5", "tas_anomaly", 0.5793)]:
    s = get_ann(ann_b, src, var)
    tr = tm.trend_stats(s.year.to_numpy(float), s.value.to_numpy(float))
    p(f"  {src} {var} n={len(s)} {int(s.year.min())}-{int(s.year.max())} slope={tr['lin_slope_per_decade']:.6f} ref={ref} diff={tr['lin_slope_per_decade']-ref:+.6f} PASS={abs(tr['lin_slope_per_decade']-ref)<=0.005}")

# GRACE production
g = tidy_b[(tidy_b.source == "grace") & (tidy_b.variable == "TWS")].copy()
tr = grace_headline_trend(g)
p(f"  GRACE headline n={tr.get('n')} slope={tr['lin_slope_per_decade']:.6f} ref=-11.242 diff={tr['lin_slope_per_decade']+11.242:+.6f} PASS={abs(tr['lin_slope_per_decade']+11.242)<=0.005}")
p("    keys", {k: tr[k] for k in tr if k in ('n','lin_slope_per_decade','hac3_p','mk_hr_p') or k.startswith('_')})

# GPCC / CHIRPS means 1981-2025 ANN
for src, var, ref in [("gpcc", "precip", 586.39), ("chirps", "precip", 686.69)]:
    s = get_ann(ann_b, src, var, 1981, 2025)
    mu = float(s.value.mean())
    p(f"  {src} ANN 1981-2025 n={len(s)} mean={mu:.4f} ref={ref} diff={mu-ref:+.4f}")

# CHIRPS month count global
ch = tidy_b[(tidy_b.source == "chirps") & (tidy_b.variable == "precip")].sort_values("date")
p(f"  CHIRPS months={len(ch)} start={ch.date.min()} end={ch.date.max()} expected 549, 1981-01..2026-09")

gp = tidy_b[(tidy_b.source == "gpcc") & (tidy_b.variable == "precip")].sort_values("date")
p(f"  GPCC months={len(gp)} start={gp.date.min()} end={gp.date.max()}")

# verify file
ver = pd.read_csv("team-context/data/pipeline/data/verify_global_vs_bbox.csv")
p("\n  verify_global_vs_bbox: n=", len(ver))
if "n_months_new" in ver.columns or "months_new" in ver.columns:
    p("  cols", list(ver.columns))
p(ver.to_string(index=False)[:4000])

# ---------------------------------------------------------------------------
# 3. Recompute ukraine_mask headlines for new vars
# ---------------------------------------------------------------------------
p("\n" + "=" * 72)
p("3. RECOMPUTE ukraine_mask HEADLINES (annual 12/12, full window, last full year)")
p("=" * 72)

def recompute_full(ann, src, var):
    s = ann[(ann.period == "ANN") & (ann.source == src) & (ann.variable == var) & (ann.year <= LAST_FULL_YEAR)].sort_values("year")
    if s.empty:
        return None
    tr = tm.trend_stats(s.year.to_numpy(float), s.value.to_numpy(float))
    call = tm.robust_call(tr, monthly=False, short_record=(int(s.year.max())-int(s.year.min())+1) < 20)
    return s, tr, call

wanted = [
    ("merra2", "T2MMAX", 0.636),
    ("merra2", "T2MMIN", 0.578),
    ("merra2", "DTR", None),
    ("merra2", "U10M", None),
    ("merra2", "V10M", None),
    ("merra2", "WS10M_from_mean_UV", None),
    ("gldas21", "snowfall", -22.7),
    ("gldas21", "precip_total", None),
    ("gldas21", "rainfall_liquid", None),
    ("gldas20", "snowfall", None),
    ("gldas20", "precip_total", None),
    ("modis", "NDVI", 0.0021),
    ("modis", "EVI", 0.0052),
    ("modis", "LST_Day", None),
    ("modis", "LST_Night", None),
]
tr_mask = pd.read_csv("team-context/data/pipeline/data/tidy/ukraine_mask/trends.csv")
for src, var, ref in wanted:
    out = recompute_full(ann_m, src, var)
    if out is None:
        p(f"  MISSING {src}:{var}")
        continue
    s, tr, call = out
    csvrow = tr_mask[(tr_mask.source == src) & (tr_mask.variable == var) & (tr_mask.series == "annual_ANN_12of12") & (tr_mask.window == "full")]
    csv_slope = float(csvrow.lin_slope_per_decade.iloc[0]) if len(csvrow) else np.nan
    p(f"  {src}:{var} n={len(s)} {int(s.year.min())}-{int(s.year.max())} mean={s.value.mean():.4f} slope={tr['lin_slope_per_decade']:.6f} csv={csv_slope:.6f} match={np.isclose(tr['lin_slope_per_decade'], csv_slope, atol=1e-8)} hac1_p={tr['hac1_p']:.4g} hr_p={tr['mk_hr_p']:.4g} call={call}")
    if ref is not None:
        p(f"     vs claimed {ref}: diff={tr['lin_slope_per_decade']-ref:+.6f}")

# seasonal JJA VI
p("\n  --- seasonal / growing-season VI in annual_seasonal and trends.csv ---")
p("  periods in annual_seasonal ukraine_mask:", sorted(ann_m.period.unique()))
p("  series in trends:", tr_mask.series.unique().tolist())
for var in ["NDVI", "EVI"]:
    for per in ["DJF", "MAM", "JJA", "SON", "AMJJAS", "growing", "Apr-Sep"]:
        s = ann_m[(ann_m.period == per) & (ann_m.source == "modis") & (ann_m.variable == var) & (ann_m.year <= LAST_FULL_YEAR)].sort_values("year")
        if s.empty:
            continue
        tr = tm.trend_stats(s.year.to_numpy(float), s.value.to_numpy(float))
        call = tm.robust_call(tr, monthly=False, short_record=False)
        p(f"  {var} period={per} n={len(s)} {int(s.year.min())}-{int(s.year.max())} slope={tr['lin_slope_per_decade']:.6f} hac1_p={tr['hac1_p']:.4g} hr_p={tr['mk_hr_p']:.4g} call={call}")

# is JJA in trends.csv?
jja_rows = tr_mask[tr_mask.series.str.contains("JJA|growing|AMJJA|season", case=False, na=False)]
p("  trends.csv rows with seasonal series:", len(jja_rows))

# ---------------------------------------------------------------------------
# 4. MODIS QC impact recompute from cache
# ---------------------------------------------------------------------------
p("\n" + "=" * 72)
p("4. MODIS QC IMPACT RECOMPUTE from series cache (ukraine_mask)")
p("=" * 72)

imp = pd.read_csv("team-context/data/pipeline/data/modis_qc_impact.csv")
imps = pd.read_csv("team-context/data/pipeline/data/modis_qc_impact_seasonal.csv")

def load_cache(prefix, region):
    files = sorted(Path("team-context/data/pipeline/data/cache/series").glob(f"{prefix}_{region}_*.parquet"))
    # prefer most recently modified
    files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
    return pd.read_parquet(files[0]) if files else None, files

for region in ["ukraine_mask"]:
    vi, vi_files = load_cache("mod13c2_qc", region)
    lst, lst_files = load_cache("mod11c3_qc", region)
    p("  VI cache", vi_files[0].name if vi_files else None, "cols", list(vi.columns) if vi is not None else None)
    p("  LST cache", lst_files[0].name if lst_files else None, "cols", list(lst.columns) if lst is not None else None)
    for label, df, keys in [
        ("VI", vi, ["NDVI", "EVI"]),
        ("LST", lst, ["LST_Day_K", "LST_Night_K"]),
    ]:
        if df is None:
            p("  missing cache", label)
            continue
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        for k in keys:
            # scale LST already in K in cache? compare_modis_qc uses make_tidy which does K_to_C
            q = make_tidy("modis", k, region, df["date"], df[k].to_numpy(float), preaggregated=False)
            u = make_tidy("modis", k, region, df["date"], df[k + "__noqc"].to_numpy(float), preaggregated=False)
            def trend(tidy, period="ANN"):
                a = annual_table(tidy)
                a = a[(a.period == period) & (a.year <= LAST_FULL_YEAR) & (a.year >= 2001)].sort_values("year")
                tr = tm.trend_stats(a.year.to_numpy(float), a.value.to_numpy(float))
                return tr, len(a), tm.robust_call(tr, monthly=False, short_record=False)
            tq, nq, cq = trend(q)
            tu, nu, cu = trend(u)
            kept = df[k + "__qc_kept_area_frac"]
            cov = df[k + "__cov"]
            area_removed = 100 * (1 - kept.mean())
            area_removed_max = 100 * (1 - kept.min())
            low = int((cov < 0.5).sum())
            outname = q.variable.iloc[0]
            row = imp[(imp.region == region) & (imp.variable == outname)].iloc[0]
            p(f"  {region} {outname}:")
            p(f"    n months={len(df)} area_removed_mean={area_removed:.4f} (csv {row.area_removed_by_qc_pct_mean:.4f}) max={area_removed_max:.4f} (csv {row.area_removed_by_qc_pct_max:.4f})")
            p(f"    months_lt50={low} (csv {int(row.months_qc_coverage_lt50pct)}) trend_qc={tq['lin_slope_per_decade']:.6f} (csv {row.trend_qc_per_decade:.6f}) trend_noqc={tu['lin_slope_per_decade']:.6f} (csv {row.trend_noqc_per_decade:.6f})")
            p(f"    robust_qc={cq} | {row.robust_qc}")
            p(f"    robust_noqc={cu} | {row.robust_noqc}")
            for per in ("DJF", "JJA"):
                tqs, _, _ = trend(q, per)
                tus, _, _ = trend(u, per)
                p(f"    {per} qc={tqs['lin_slope_per_decade']:.6f} noqc={tus['lin_slope_per_decade']:.6f}")

# tidy flags
p("\n  --- tidy MODIS flags (ukraine_mask) ---")
mod = tidy_m[tidy_m.source == "modis"]
for var, g in mod.groupby("variable"):
    flags = Counter()
    for f in g.flags.fillna(""):
        for x in str(f).split(";"):
            if x:
                flags[x] += 1
    n50 = int(g.flags.fillna("").str.contains("qc_low_coverage_lt50pct").sum())
    nno = int(g.flags.fillna("").str.contains("no_qc").sum())
    nqc = int(g.flags.fillna("").str.contains("qc_pixel_masked").sum())
    p(f"  {var}: months={len(g)} coverage min/median={g.coverage_frac.min():.3f}/{g.coverage_frac.median():.3f} qc_pixel_masked={nqc} no_qc={nno} lt50={n50} flags={dict(flags)}")
    # do low-coverage months enter annual 12/12?
    if n50:
        lowm = g[g.flags.fillna("").str.contains("qc_low_coverage_lt50pct")].copy()
        p(f"    lt50 months by month: {lowm.date.dt.month.value_counts().sort_index().to_dict()} years {sorted(lowm.date.dt.year.unique())[:15]}... n_years={lowm.date.dt.year.nunique()}")

# ---------------------------------------------------------------------------
# 5. GLDAS overlap 2.0 vs 2.1 snowfall, units, no splice
# ---------------------------------------------------------------------------
p("\n" + "=" * 72)
p("5. GLDAS snowfall overlap / units / splice")
p("=" * 72)

def series(tidy, src, var):
    return tidy[(tidy.source == src) & (tidy.variable == var)].sort_values("date").copy()

for region, tidy, ann in [("ukraine_mask", tidy_m, ann_m), ("ukraine_bbox", tidy_b, ann_b)]:
    s20 = series(tidy, "gldas20", "snowfall")
    s21 = series(tidy, "gldas21", "snowfall")
    p(f"\n  [{region}]")
    p(f"    2.0 snowfall months={len(s20)} {s20.date.min()}..{s20.date.max()} mean mm/month={s20.value.mean():.3f}")
    p(f"    2.1 snowfall months={len(s21)} {s21.date.min()}..{s21.date.max()} mean mm/month={s21.value.mean():.3f}")
    # overlap months
    m20 = s20.set_index(s20.date.dt.to_period("M")).value
    m21 = s21.set_index(s21.date.dt.to_period("M")).value
    both = m20.index.intersection(m21.index)
    if len(both):
        a, b = m20.loc[both], m21.loc[both]
        p(f"    overlap months={len(both)} {both.min()}..{both.max()} corr={np.corrcoef(a,b)[0,1]:.4f} mean20={a.mean():.3f} mean21={b.mean():.3f} mean_diff21-20={ (b-a).mean():.3f}")
        # annual overlap 2000-2014 12/12
        a20 = ann[(ann.period=="ANN")&(ann.source=="gldas20")&(ann.variable=="snowfall")&(ann.year.between(2000,2014))]
        a21 = ann[(ann.period=="ANN")&(ann.source=="gldas21")&(ann.variable=="snowfall")&(ann.year.between(2000,2014))]
        if len(a20) and len(a21):
            tr20 = tm.trend_stats(a20.year.to_numpy(float), a20.value.to_numpy(float))
            tr21 = tm.trend_stats(a21.year.to_numpy(float), a21.value.to_numpy(float))
            p(f"    ANN 2000-2014 n20={len(a20)} n21={len(a21)} mean20={a20.value.mean():.2f} mean21={a21.value.mean():.2f} mm/yr")
            p(f"    slope20={tr20['lin_slope_per_decade']:.3f} hac={tr20['hac1_p']:.4g} hr={tr20['mk_hr_p']:.4g} {tm.robust_call(tr20,False,True)}")
            p(f"    slope21={tr21['lin_slope_per_decade']:.3f} hac={tr21['hac1_p']:.4g} hr={tr21['mk_hr_p']:.4g} {tm.robust_call(tr21,False,True)}")
    # check no splice: 2.0 should end 2014-12, 2.1 start 2000-01, separate sources
    p(f"    sources unique snowfall: {tidy[tidy.variable=='snowfall'].source.unique().tolist()}")

# unit check: one month, kg m-2 s-1 * 86400 * days vs tidy
# Use a mid-month from cache (already converted). Cross-check conversion in core.
from ukpipe.core import convert as _convert
# peek convert function
import inspect
try:
    from ukpipe import core as C
    p("\n  conversion functions:")
    p("   ", [n for n in dir(C) if "conv" in n.lower() or "per_s" in n.lower() or "unit" in n.lower()])
except Exception as e:
    p("  conv inspect err", e)

# monthly totals vs daily rate: typical snowfall ~ few mm/month to tens. If they forgot *days, values would be ~0.00x mm
# If they forgot *86400, tiny. If they did *86400 but not *days, ~ daily mm. Report range.
s21 = series(tidy_m, "gldas21", "snowfall")
p(f"  2.1 snowfall mm/month range {s21.value.min():.3f} .. {s21.value.max():.3f}  winter means by month:")
s21 = s21.copy()
s21["month"] = s21.date.dt.month
p("   ", s21.groupby("month").value.mean().round(2).to_dict())
# annual mean ~ 
a21 = ann_m[(ann_m.period=="ANN")&(ann_m.source=="gldas21")&(ann_m.variable=="snowfall")]
p(f"  2.1 ANN snowfall mm/year range {a21.value.min():.1f} .. {a21.value.max():.1f} mean={a21.value.mean():.1f}")
a20 = ann_m[(ann_m.period=="ANN")&(ann_m.source=="gldas20")&(ann_m.variable=="snowfall")]
p(f"  2.0 ANN snowfall mm/year range {a20.value.min():.1f} .. {a20.value.max():.1f} mean={a20.value.mean():.1f}")

# year-by-year 2.1 snowfall to see forcing-break jumps
p("  2.1 annual snowfall by year:")
p("   ", {int(y): round(v,1) for y,v in zip(a21.sort_values('year').year, a21.sort_values('year').value)})
p("  2.0 annual snowfall 2000-2014:")
p("   ", {int(y): round(v,1) for y,v in zip(a20[a20.year.between(2000,2014)].sort_values('year').year, a20[a20.year.between(2000,2014)].sort_values('year').value)})

# precip_total vs rainfall_liquid + snowfall identity
for src in ["gldas20", "gldas21"]:
    tot = series(tidy_m, src, "precip_total")
    liq = series(tidy_m, src, "rainfall_liquid")
    sno = series(tidy_m, src, "snowfall")
    m = tot.merge(liq, on="date", suffixes=("_t","_l")).merge(sno, on="date")
    residual = m.value_t - m.value_l - m.value
    p(f"  {src} identity precip_total - liquid - snow: maxabs={residual.abs().max():.6e} mean={residual.mean():.6e} n={len(m)}")

# post-2011 / post-2001 windows for 2.1
for y0, y1, label in [(2001, 2010, "2001-2010 post-Mar2001 start"), (2011, 2025, "2011-2025 AGRMET era"), (2000, 2025, "full 2000-2025"), (2002, 2024, "2002-2024 drop 2000 and 2025")]:
    s = ann_m[(ann_m.period=="ANN")&(ann_m.source=="gldas21")&(ann_m.variable=="snowfall")&(ann_m.year.between(y0,y1))]
    if len(s) < 8:
        p(f"  2.1 snow {label}: too short n={len(s)}")
        continue
    tr = tm.trend_stats(s.year.to_numpy(float), s.value.to_numpy(float))
    p(f"  2.1 snow {label} n={len(s)} slope={tr['lin_slope_per_decade']:.3f} hac={tr['hac1_p']:.4g} hr={tr['mk_hr_p']:.4g} {tm.robust_call(tr,False,(y1-y0+1)<20)}")

# SWE for context
for src in ["gldas20", "gldas21"]:
    s = recompute_full(ann_m, src, "SWE_inst")
    if s:
        ss, tr, call = s
        p(f"  {src} SWE n={len(ss)} {int(ss.year.min())}-{int(ss.year.max())} slope={tr['lin_slope_per_decade']:.3f} {call}")

# ---------------------------------------------------------------------------
# 6. MERRA-2 DTR / wind labels / T2M vs T2MMAX
# ---------------------------------------------------------------------------
p("\n" + "=" * 72)
p("6. MERRA-2 DTR, wind, T2M vs max/min")
p("=" * 72)

t2m = series(tidy_m, "merra2", "T2M")
tmax = series(tidy_m, "merra2", "T2MMAX")
tmin = series(tidy_m, "merra2", "T2MMIN")
dtr = series(tidy_m, "merra2", "DTR")
# DTR identity at regional mean: tmax-tmin should equal dtr if derived per cell then averaged
# (equal because subtraction is linear — regional mean(DTR)=mean(max)-mean(min))
m = tmax.merge(tmin, on="date", suffixes=("_x","_n")).merge(dtr, on="date")
resid = m.value_x - m.value_n - m.value
p(f"  DTR identity T2MMAX-T2MMIN-DTR maxabs={resid.abs().max():.6e} (should be ~0)")
# Is T2M between min and max?
m2 = t2m.merge(tmax, on="date", suffixes=("_m","_x")).merge(tmin, on="date")
p(f"  T2M vs T2MMAX-T2MMIN: months T2M>T2MMAX={(m2.value_m>m2.value_x+1e-6).sum()} T2M<T2MMIN={(m2.value_m<m2.value+1e-6).sum()}")
# July 1980 check mentioned in report: bbox 24.2 / 14.5 vs T2M 19.6
ann_b_or_m = tidy_b
for tidy, reg in [(tidy_b, "bbox"), (tidy_m, "mask")]:
    row = lambda v: series(tidy, "merra2", v)
    j = pd.Timestamp("1980-07-01")
    vals = {v: float(row(v).set_index("date").loc[j, "value"]) if j in row(v).date.values else None
            for v in ["T2M", "T2MMAX", "T2MMIN", "DTR"]}
    p(f"  Jul 1980 {reg}: {vals}")

# wind
ws = series(tidy_m, "merra2", "WS10M_from_mean_UV")
u = series(tidy_m, "merra2", "U10M")
v = series(tidy_m, "merra2", "V10M")
# hypot of regional mean U,V vs published WS (WS is hypot then average, so >= hypot of means)
m = u.merge(v, on="date", suffixes=("_u","_v")).merge(ws, on="date")
hyp = np.hypot(m.value_u, m.value_v)
p(f"  WS vs hypot(regional U,V): mean WS={m.value.mean():.3f} mean hypot(U,V)={hyp.mean():.3f} WS>=hypot always? {(m.value+1e-9>=hyp).all()} min(WS-hypot)={(m.value-hyp).min():.4f}")
# POWER WS10M
pw = series(tidy_m, "nasa_power", "WS10M")
p(f"  POWER WS10M mean={pw.value.mean():.3f}  MERRA-2 WS10M_from_mean_UV mean={ws.value.mean():.3f}")
# flags
p("  merra2 wind/DTR flags unique:")
for var in ["U10M","V10M","WS10M_from_mean_UV","T2MMAX","T2MMIN","DTR"]:
    g = tidy_m[(tidy_m.source=="merra2")&(tidy_m.variable==var)]
    p(f"    {var}: n={len(g)} flags={g.flags.value_counts().to_dict() if len(g) else 'MISSING'} unit={g.unit.iloc[0] if len(g) else None}")

# POWER derived DTR vs merra2 DTR
pdtr = series(tidy_m, "derived", "DTR")
p(f"  derived(POWER) DTR months={len(pdtr)} mean={pdtr.value.mean():.3f}  merra2 DTR mean={dtr.value.mean():.3f}")

# ---------------------------------------------------------------------------
# 7. Multiple testing family
# ---------------------------------------------------------------------------
p("\n" + "=" * 72)
p("7. MULTIPLE TESTING FAMILY")
p("=" * 72)

for region, path in [
    ("ukraine_mask", "team-context/data/pipeline/data/tidy/ukraine_mask/trends.csv"),
    ("ukraine_bbox", "team-context/data/pipeline/data/tidy/ukraine_bbox/trends.csv"),
]:
    df = pd.read_csv(path)
    ann = df[df.series == "annual_ANN_12of12"]
    p(f"\n  [{region}] total rows={len(df)} annual={len(ann)}")
    p(f"    n_tests_in_family unique (annual): {sorted(ann.n_tests_in_family.dropna().unique().tolist())}")
    p(f"    n_tests_in_family unique (all): {sorted(df.n_tests_in_family.dropna().unique().tolist())}")
    # new variables
    new_vars = ["T2MMAX","T2MMIN","DTR","U10M","V10M","WS10M_from_mean_UV","precip_total","snowfall","rainfall_liquid","LST_Day_clear_days","LST_Night_clear_days"]
    in_ann = ann[ann.variable.isin(new_vars)]
    p(f"    new-var annual rows={len(in_ann)} variables present: {sorted(in_ann.variable.unique().tolist())}")
    p(f"    sources for new vars: {in_ann.groupby(['source','variable']).size().to_dict()}")
    # family size should equal number of annual rows with finite hac1_p
    n_finite = int(ann.hac1_p.notna().sum())
    fam = int(ann.n_tests_in_family.dropna().iloc[0]) if ann.n_tests_in_family.notna().any() else None
    p(f"    annual finite hac1_p={n_finite} family={fam} match={n_finite==fam}")
    # BH/Bonferroni for claimed headlines
    sub = df[(df.headline==True) & (df.variable.isin(["T2MMAX","T2MMIN","DTR","snowfall","NDVI","EVI","LST_Day","U10M","WS10M_from_mean_UV"]))]
    cols = [c for c in ["source","variable","n","lin_slope_per_decade","hac1_p","hac1_bonferroni_reject","hac1_bh_reject","mk_hr_p","mk_hr_bonferroni_reject","mk_hr_bh_reject","n_tests_in_family","robust_call"] if c in df.columns]
    with pd.option_context("display.max_colwidth", 70, "display.width", 220):
        p(sub[cols].to_string(index=False))

# ---------------------------------------------------------------------------
# 8. MODIS bit spot-decode
# ---------------------------------------------------------------------------
p("\n" + "=" * 72)
p("8. MODIS BIT SPOT-DECODE (Ukraine window, Jan and Jul 2003)")
p("=" * 72)

# CMG 0.05 deg, 3600 x 7200, lat 89.975 .. -89.975, lon -179.975 .. 179.975
# Worker uses _cmg_coords — inspect it
from ukpipe.loaders.global_grids import _cmg_coords, _vi_good, _lst_good, VI_QC, LST_QC, _rawq

lat, lon = _cmg_coords()
p(f"  CMG coords: lat {lat[0]:.4f}..{lat[-1]:.4f} n={len(lat)} lon {lon[0]:.4f}..{lon[-1]:.4f} n={len(lon)}")

# Ukraine bbox slightly padded
lo0, la0, lo1, la1 = 22.1, 44.4, 40.2, 52.4
iy = np.where((lat >= la0) & (lat <= la1))[0]
ix = np.where((lon >= lo0) & (lon <= la1 + 0))  # typo guard
ix = np.where((lon >= lo0) & (lon <= lo1))[0]
ys, xs = slice(int(iy.min()), int(iy.max())+1), slice(int(ix.min()), int(ix.max())+1)
p(f"  window ys={ys} xs={xs} shape={(iy.size, ix.size)}")

def find_modis(d, year, month, doy_guess=None):
    # files named MOD13C2.A{YYYYDDD}.061....nc4
    import datetime
    d0 = datetime.date(year, month, 1)
    doy = d0.timetuple().tm_yday
    files = sorted(Path(d).glob(f"*.A{year}{doy:03d}.*.nc4"))
    if not files:
        files = sorted(Path(d).glob(f"*.A{year}*.nc4"))
        # pick closest doy
        def doy_of(p):
            # AYYYYDDD
            name = p.name
            i = name.index(".A") + 2
            return int(name[i+4:i+7])
        files = sorted(files, key=lambda p: abs(doy_of(p)-doy))
        files = [files[0]] if files else []
    return files[0] if files else None

for year, month, tag in [(2003, 1, "Jan 2003"), (2003, 7, "Jul 2003"), (2010, 1, "Jan 2010"), (2010, 7, "Jul 2010")]:
    fvi = find_modis("$GLOBAL_DATA/mod13c2_qc", year, month)
    # data file is in slim with same name
    dvi = Path("$GLOBAL_DATA/mod13c2_slim") / fvi.name if fvi else None
    fls = find_modis("$GLOBAL_DATA/mod11c3_qc", year, month)
    dls = Path("$GLOBAL_DATA/mod11c3_slim") / fls.name if fls else None
    p(f"\n  === {tag} ===")
    p(f"    VI qc={fvi.name if fvi else None} data exists={dvi.exists() if dvi else False}")
    p(f"    LST qc={fls.name if fls else None} data exists={dls.exists() if dls else False}")
    if fvi and dvi and dvi.exists():
        with netCDF4.Dataset(fvi) as qds, netCDF4.Dataset(dvi) as ds:
            rel = _rawq(qds, VI_QC + "CMG_0_05_Deg_Monthly_pixel_reliability", ys, xs).astype(np.int16)
            viq = _rawq(qds, VI_QC + "CMG_0_05_Deg_Monthly_VI_Quality", ys, xs).astype(np.uint32)
            ndvi_v = ds[VI_QC + "CMG_0_05_Deg_Monthly_NDVI"]
            ndvi_v.set_auto_maskandscale(False)
            ndvi = np.asarray(ndvi_v[ys, xs], dtype=np.float64)
            good = _vi_good(qds, ys, xs)
            mand = viq & 0b11
            p(f"    pixel_reliability unique (value:count): {dict(zip(*np.unique(rel, return_counts=True)))}")
            p(f"    VI_Quality bits0-1 unique: {dict(zip(*np.unique(mand, return_counts=True)))}")
            p(f"    _vi_good True={int(good.sum())} / {good.size} = {good.mean():.3f}")
            # cross tab reliability x mand
            for r in sorted(np.unique(rel)):
                sub = mand[rel == r]
                p(f"      rel={int(r)} n={sub.size} mand counts {dict(zip(*np.unique(sub, return_counts=True)))}  good_frac={good[rel==r].mean():.3f}")
            # pick example pixels: good (rel0), marginal (rel1), snow (rel2), cloud (rel3), estimated (rel4), fill
            flat = np.argwhere(np.ones(rel.shape, dtype=bool))
            examples = []
            for target, name in [((rel==0)&(mand==0), "good_rel0_mand00"), ((rel==1), "marginal_rel1"), ((rel==2), "snow_rel2"), ((rel==3), "cloud_rel3"), ((rel==4), "estimated_rel4"), ((rel<0)|(rel==255)|(rel==-1), "fill")]:
                idx = np.argwhere(target)
                if len(idx)==0:
                    p(f"      no pixel for {name}")
                    continue
                i,j = idx[len(idx)//2]
                latp, lonp = lat[ys][i], lon[xs][j]
                p(f"      ex {name}: lat={latp:.3f} lon={lonp:.3f} rel={int(rel[i,j])} VIQ={int(viq[i,j])} bits0-1={int(mand[i,j]):02b} NDVI_raw={int(ndvi[i,j])} good={bool(good[i,j])}")
            # inconsistency: rel in {0,1} but mand in {2,3} or vice versa
            inc1 = ((rel==0)|(rel==1)) & (mand>=2)
            inc2 = ((rel>=2)&(rel<=4)) & (mand<=1)
            p(f"    inconsistent rel good/marg but mand 10/11: {int(inc1.sum())}; rel snow/cloud/est but mand 00/01: {int(inc2.sum())}")

    if fls and dls and dls.exists():
        with netCDF4.Dataset(fls) as qds, netCDF4.Dataset(dls) as ds:
            for which, lname in [("Day", "LST_Day_CMG"), ("Night", "LST_Night_CMG")]:
                q = _rawq(qds, LST_QC + f"QC_{which}", ys, xs).astype(np.uint8)
                mand = q & 0b11
                err = (q >> 6) & 0b11
                good = _lst_good(which)(qds, ys, xs)
                lstv = ds[LST_QC + lname]
                lstv.set_auto_maskandscale(False)
                lst = np.asarray(lstv[ys, xs], dtype=np.float64)
                # fill 0
                p(f"    LST_{which}: QC unique-top {Counter(q.ravel()).most_common(8)}")
                p(f"      mand counts {dict(zip(*np.unique(mand, return_counts=True)))}  err counts {dict(zip(*np.unique(err, return_counts=True)))}")
                p(f"      _lst_good True={int(good.sum())}/{good.size}={good.mean():.3f}  LST fill0={(lst==0).mean():.3f} LST range nonfill {(lst[lst!=0].min()*0.02 if (lst!=0).any() else np.nan):.2f}..{(lst[lst!=0].max()*0.02 if (lst!=0).any() else np.nan):.2f} K")
                # mand 00 / 01 / 10 / 11 vs fill
                for mval in range(4):
                    sub = (mand==mval)
                    p(f"      mand={mval:02b} n={int(sub.sum())} fill0_frac={(lst[sub]==0).mean() if sub.any() else np.nan:.3f} err_counts={dict(zip(*np.unique(err[sub], return_counts=True))) if sub.any() else {}} good_frac={good[sub].mean() if sub.any() else np.nan:.3f}")
                # examples
                for target, name in [((mand==0)&(lst!=0), "mand00_good"), ((mand==1)&(err<=1)&(lst!=0), "mand01_err<=2K"), ((mand==1)&(err>=2)&(lst!=0), "mand01_err>2K_dropped"), ((mand>=2), "mand10/11_dropped")]:
                    idx = np.argwhere(target)
                    if len(idx)==0:
                        p(f"      no pixel for {name}")
                        continue
                    i,j = idx[len(idx)//2]
                    latp, lonp = lat[ys][i], lon[xs][j]
                    p(f"      ex {name}: lat={latp:.3f} lon={lonp:.3f} QC={int(q[i,j])} mand={mand[i,j]:02b} err={err[i,j]:02b} LST_raw={int(lst[i,j])} LST_K={lst[i,j]*0.02:.2f} good={bool(good[i,j])}")
                # QC==0 is good? 
                p(f"      QC value 0 count={(q==0).sum()} all good? {good[q==0].all() if (q==0).any() else 'n/a'}  fillvalue attr?")
                qobj = qds[LST_QC + f"QC_{which}"]
                p(f"      QC ncattrs: {qobj.ncattrs()}")
                for a in qobj.ncattrs():
                    p(f"        {a}={getattr(qobj,a)}")

# ---------------------------------------------------------------------------
# 9. coverage_frac vs kept_area_frac for 50% flag
# ---------------------------------------------------------------------------
p("\n" + "=" * 72)
p("9. 50% FLAG: coverage_frac (vs region) vs qc_kept_area_frac (vs valid)")
p("=" * 72)
vi, _ = load_cache("mod13c2_qc", "ukraine_mask")
if vi is not None:
    for k in ["NDVI"]:
        kept = vi[k+"__qc_kept_area_frac"]
        cov = vi[k+"__cov"]
        p(f"  {k}: kept_area mean={kept.mean():.3f} min={kept.min():.3f}  cov mean={cov.mean():.3f} min={cov.min():.3f}")
        p(f"    months kept<0.5={int((kept<0.5).sum())} cov<0.5={int((cov<0.5).sum())} disagreement={int(((kept<0.5)!=(cov<0.5)).sum())}")
        # winter
        vi2 = vi.copy()
        vi2["month"] = pd.to_datetime(vi2["date"]).dt.month
        p(f"    DJF kept mean={kept[vi2.month.isin([12,1,2])].mean():.3f} JJA={kept[vi2.month.isin([6,7,8])].mean():.3f}")

# tidy coverage vs 12/12: any year with a lt50 month still 12/12?
mod_ndvi = tidy_m[(tidy_m.source=="modis")&(tidy_m.variable=="NDVI")].copy()
mod_ndvi["year"]=mod_ndvi.date.dt.year
mod_ndvi["low"]=mod_ndvi.flags.fillna("").str.contains("qc_low_coverage_lt50pct")
ann_ndvi = ann_m[(ann_m.source=="modis")&(ann_m.variable=="NDVI")&(ann_m.period=="ANN")]
years_low = set(mod_ndvi.loc[mod_ndvi.low,"year"])
years_ann = set(ann_ndvi.year)
p(f"  NDVI years with >=1 lt50 month: {sorted(years_low)} n={len(years_low)}")
p(f"  of those in 12/12 ANN: {sorted(years_low & years_ann)} n={len(years_low & years_ann)}")

# LST clear-sky days seasonal
p("\n  LST clear days (ukraine_mask) by month (mean):")
for var in ["LST_Day_clear_days","LST_Night_clear_days"]:
    g = tidy_m[(tidy_m.source=="modis")&(tidy_m.variable==var)].copy()
    if g.empty:
        p("  missing", var)
        continue
    g["month"]=g.date.dt.month
    p(f"  {var}: overall mean={g.value.mean():.2f}  by month {g.groupby('month').value.mean().round(1).to_dict()}")

# ---------------------------------------------------------------------------
# 10. misc: no splice chirps, data_dictionary, README wind label
# ---------------------------------------------------------------------------
p("\n" + "=" * 72)
p("10. MISC")
p("=" * 72)
meta = json.loads(Path("team-context/data/pipeline/data/tidy/ukraine_mask/run_meta.json").read_text())
p("  run_meta keys", list(meta.keys())[:30])
p("  run_meta snippet:", json.dumps(meta, default=str)[:2500])

dd = pd.read_csv("team-context/data/pipeline/data_dictionary.csv")
p("\n  data_dictionary rows", len(dd), "cols", list(dd.columns))
# new vars present?
p(dd[dd.apply(lambda r: any(x in str(r).lower() for x in ["t2mmax","snowfall","ws10m","clear_days","dtr","qc_pixel"]), axis=1)].to_string(index=False)[:3000])

OUT.write_text("\n".join(lines) + "\n")
p("\nWrote", OUT)
