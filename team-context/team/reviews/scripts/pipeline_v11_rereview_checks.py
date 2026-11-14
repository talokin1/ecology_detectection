#!/usr/bin/env python3
"""Spot checks for pipeline v1.1. Does not rerun the pipeline.
Imports official trend_methods. Run with: nice -n 19, OMP_NUM_THREADS=1.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import numpy as np
import pandas as pd

sys.path.insert(0, "$UKRAINE_SAMPLES/_staging")
from trend_methods import trend_stats

PIPE = Path("team-context/data/pipeline")
TIDY = PIPE / "data" / "tidy"
OUT = Path("team-context/team/reviews/pipeline_v11_rereview_checks.json")

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def annual_ols(years, values, unit=""):
    years = np.asarray(years, float)
    values = np.asarray(values, float)
    ok = np.isfinite(years) & np.isfinite(values)
    r = trend_stats(years[ok], values[ok])
    if r is None:
        return {"n": int(ok.sum()), "start": None, "end": None, "ols_per_decade": None,
                "hac3_p": None, "mk_hr_p": None, "robust": False, "sig_hac": False, "sig_hr": False, "error": "n<min_n"}
    return {
        "n": int(r.get("n", ok.sum())),
        "start": int(years[ok].min()) if ok.any() else None,
        "end": int(years[ok].max()) if ok.any() else None,
        "ols_per_decade": float(r["lin_slope_per_decade"]),
        "hac3_p": float(r["hac3_p"]) if r.get("hac3_p") is not None else None,
        "mk_hr_p": float(r["mk_hr_p"]) if r.get("mk_hr_p") is not None else None,
        "robust": bool(
            (r.get("hac3_p") is not None and r["hac3_p"] < 0.05)
            and (r.get("mk_hr_p") is not None and r["mk_hr_p"] < 0.05)
        ),
        "sig_hac": bool(r.get("hac3_p") is not None and r["hac3_p"] < 0.05),
        "sig_hr": bool(r.get("mk_hr_p") is not None and r["mk_hr_p"] < 0.05),
    }


def load_ann(region, source, variable):
    df = pd.read_parquet(TIDY / region / "annual_seasonal.parquet")
    sub = df[(df["source"] == source) & (df["variable"] == variable) & (df["period"] == "ANN")].copy()
    sub["year"] = pd.to_datetime(sub["date"]).dt.year if "date" in sub.columns else sub.get("year")
    if "year" not in sub.columns or sub["year"].isna().all():
        # try 'year' already or parse from index
        for c in sub.columns:
            if c.lower() in {"year", "yr"}:
                sub["year"] = sub[c]
    return sub


def main():
    report = {}

    # ------------------------------------------------------------------
    # 0. schema / available files
    # ------------------------------------------------------------------
    regions = sorted(p.name for p in TIDY.iterdir() if p.is_dir())
    report["regions_in_tidy"] = regions

    # annual_seasonal schema
    ann0 = pd.read_parquet(TIDY / "ukraine_bbox" / "annual_seasonal.parquet")
    report["annual_seasonal_cols"] = list(ann0.columns)
    report["annual_seasonal_seasons"] = sorted(ann0["period"].unique().tolist()) if "period" in ann0.columns else None

    # ------------------------------------------------------------------
    # 1. GSOM TAVG baseline counts on ukraine_bbox
    # ------------------------------------------------------------------
    st = pd.read_parquet(TIDY / "ukraine_bbox" / "stations_gsom.parquet")
    tavg = st[st["variable"] == "TAVG"].dropna(subset=["value"]).copy()
    tavg["date"] = pd.to_datetime(tavg["date"])
    tavg["yr"] = tavg["date"].dt.year
    tavg["mo"] = tavg["date"].dt.month
    n_data = tavg["station"].nunique()
    inb = tavg["yr"].between(1991, 2020)
    cnt = tavg[inb].groupby(["station", "mo"])["value"].count()
    clim_idx = cnt[cnt >= 15].index
    nmon = clim_idx.to_frame(index=False).groupby("station").size() if len(clim_idx) else pd.Series(dtype=int)
    # nmon index is station
    any_base = set(nmon.index)
    full12 = set(nmon[nmon == 12].index)
    all_st = set(tavg["station"].unique())
    dropped = all_st - any_base
    last = tavg.groupby("station")["yr"].max()
    end_before_2006 = set(last[last < 2006].index)
    end_in_2005 = set(last[last == 2005].index)
    end_by_2004 = set(last[last <= 2004].index)
    # can any end-before-2006 station still have a baseline month?
    end_before_2006_with_baseline = end_before_2006 & any_base
    # among dropped, how many extend past 2005?
    dropped_after_2005 = dropped - end_before_2006

    # also confirm 1991-2004 max 14 years
    years_in_base = tavg[inb].groupby("station")["yr"].nunique()

    report["gsom_tavg_bbox"] = {
        "stations_with_data": int(n_data),
        "stations_with_any_baseline_month": int(len(any_base)),
        "stations_with_full_12month_baseline": int(len(full12)),
        "stations_dropped_no_baseline": int(len(dropped)),
        "stations_ending_before_2006": int(len(end_before_2006)),
        "stations_ending_in_2005": int(len(end_in_2005)),
        "stations_ending_by_2004": int(len(end_by_2004)),
        "end_before_2006_that_still_have_a_baseline_month": int(len(end_before_2006_with_baseline)),
        "dropped_but_extend_to_2006_or_later": int(len(dropped_after_2005)),
        "max_baseline_years_among_end_before_2006": int(years_in_base.reindex(list(end_before_2006)).max()) if end_before_2006 else None,
        "worker_claimed": {"data": 183, "any_base": 36, "full12": 9, "dropped": 147, "end_before_2006": 49},
        "matches_worker": bool(n_data == 183 and len(any_base) == 36 and len(full12) == 9 and len(dropped) == 147 and len(end_before_2006) == 49),
    }

    # ------------------------------------------------------------------
    # 2. AIRS 2025 exclusion + slope recompute
    # ------------------------------------------------------------------
    # tidy monthly
    airs_m = pd.read_parquet(TIDY / "ukraine_bbox" / "airs.parquet")
    airs_ann = pd.read_parquet(TIDY / "ukraine_bbox" / "annual_seasonal.parquet")
    airs_ann = airs_ann[(airs_ann["source"] == "airs") & (airs_ann["period"] == "ANN")].copy()
    # detect year column
    if "year" not in airs_ann.columns:
        if "date" in airs_ann.columns:
            airs_ann["year"] = pd.to_datetime(airs_ann["date"]).dt.year
        else:
            raise SystemExit(f"no year/date in annual: {airs_ann.columns}")
    sat = airs_ann[airs_ann["variable"] == "SurfAirTemp"].sort_values("year")
    thv = airs_ann[airs_ann["variable"] == "TotH2OVap"].sort_values("year")
    report["airs_annual_years_SurfAirTemp"] = [int(x) for x in sat["year"].tolist()]
    report["airs_annual_n_SurfAirTemp"] = int(len(sat))
    report["airs_2025_in_annual"] = bool((sat["year"] == 2025).any())

    # monthly 2025 flags
    airs_m["date"] = pd.to_datetime(airs_m["date"])
    m2025 = airs_m[(airs_m["variable"] == "SurfAirTemp") & (airs_m["date"].dt.year == 2025)]
    flags_2025 = m2025["flags"].tolist()
    report["airs_monthly_2025"] = {
        "n_months": int(len(m2025)),
        "all_flagged_airs_2025_bias_unverified": all("airs_2025_bias_unverified" in str(f) for f in flags_2025),
        "values_head": [None if pd.isna(v) else float(v) for v in m2025["value"].head(3)],
    }

    # recompute 2003-2024 from tidy annual (production / global cut)
    def rec(sub, y0, y1, unit):
        s = sub[(sub["year"] >= y0) & (sub["year"] <= y1)]
        return annual_ols(s["year"], s["value"], unit=unit)

    report["airs_SurfAirTemp_2003_2024_from_tidy_annual"] = rec(sat, 2003, 2024, "°C")
    # if 2025 somehow in annual, also compute including it
    if (sat["year"] == 2025).any() or (sat["year"] == 2026).any():
        report["airs_SurfAirTemp_including_later"] = rec(sat, 2003, 2026, "°C")

    # old extract slope 2003-2024
    old = pd.read_csv("$UKRAINE_SAMPLES/airs/airs_ukraine_monthly.csv")
    report["old_airs_cols"] = list(old.columns)
    # we'll fill after inspecting if needed; try common names
    old["date"] = pd.to_datetime(old[ [c for c in old.columns if "date" in c.lower()][0] ])
    # find temp column
    tcols = [c for c in old.columns if "surf" in c.lower() or "temp" in c.lower() or c.lower() in {"t", "tas", "sat"}]
    report["old_airs_tcols"] = tcols
    # old extract: SurfAirTemp_C is already C; also mean of A/D bbox means
    # build 12/12 annual 2003-2024
    old_airs = old  # already loaded
    old_airs["year"] = old_airs["date"].dt.year
    old_airs["month"] = old_airs["date"].dt.month
    def airs_ann(col):
        g = old_airs.groupby("year")[col].agg(["mean","count"])
        g = g[g["count"]==12]["mean"]
        return g
    oa = airs_ann("SurfAirTemp_C")
    oa = oa.loc[(oa.index>=2003)&(oa.index<=2024)]
    report["airs_old_extract_2003_2024"] = {
        "n": int(len(oa)),
        "years": [int(x) for x in oa.index],
        "stats": annual_ols(oa.index, oa.values),
        "col": "SurfAirTemp_C",
    }
    if "TotH2OVap" in old_airs.columns:
        ov = airs_ann("TotH2OVap")
        ov = ov.loc[(ov.index>=2003)&(ov.index<=2024)]
        report["airs_old_TotH2OVap_2003_2024"] = {"n": int(len(ov)), "stats": annual_ols(ov.index, ov.values)}

    # trends.csv AIRS rows
    tr = pd.read_csv(TIDY / "ukraine_bbox" / "trends.csv")
    airs_tr = tr[tr["source"] == "airs"][
        ["variable", "series", "window", "win_start", "win_end", "excluded_years",
         "missing_years", "headline", "n", "start", "end", "lin_slope_per_decade",
         "robust_call", "hac3_p", "mk_hr_p"]
    ]
    report["airs_trends_csv"] = airs_tr.to_dict(orient="records")

    # ------------------------------------------------------------------
    # 3. Station windows in trends.csv
    # ------------------------------------------------------------------
    stn = tr[tr["source"].isin(["gsom", "ghcn"])].copy()
    win_summary = []
    for _, r in stn.iterrows():
        win_summary.append({
            "source": r["source"], "variable": r["variable"], "series": r["series"],
            "window": r["window"], "headline": bool(r["headline"]),
            "n": int(r["n"]) if pd.notna(r["n"]) else None,
            "start": r["start"], "end": r["end"],
            "missing_years": r["missing_years"] if pd.notna(r["missing_years"]) else "",
            "excluded_years": r["excluded_years"] if pd.notna(r["excluded_years"]) else "",
            "robust_call": r["robust_call"],
            "slope": float(r["lin_slope_per_decade"]) if pd.notna(r["lin_slope_per_decade"]) else None,
        })
    report["station_trend_rows"] = win_summary
    # checks
    headlines = [x for x in win_summary if x["headline"]]
    gappy = [x for x in win_summary if "gappy" in str(x["window"])]
    robust_gappy = [x for x in gappy if x["robust_call"] and "not treated as robust" not in str(x["robust_call"]).lower() and str(x["robust_call"]).startswith("robust")]
    headline_windows = set(x["window"] for x in headlines)
    report["station_window_checks"] = {
        "headline_windows": sorted(headline_windows),
        "n_headlines": len(headlines),
        "all_headlines_are_1981_2019": all(x["window"] == "1981-2019_station_window" for x in headlines),
        "gappy_called_robust_anyway": robust_gappy,
        "ghcn_TAVG_headline_missing_years": [
            x for x in headlines if x["source"] == "ghcn" and x["variable"] == "TAVG_anom" and x.get("missing_years")
        ],
    }

    # ------------------------------------------------------------------
    # 4. GRACE production slope
    # ------------------------------------------------------------------
    grace_ann_or_month = pd.read_parquet(TIDY / "ukraine_bbox" / "grace.parquet")
    grace_ann_or_month["date"] = pd.to_datetime(grace_ann_or_month["date"])
    # monthly deseasonalised: use anomaly column if present
    g = grace_ann_or_month[grace_ann_or_month["variable"] == "TWS"].copy()
    # build decimal year
    def decyear(d):
        d = pd.Timestamp(d)
        return d.year + (d.dayofyear - 0.5) / (366 if (d.year % 4 == 0 and (d.year % 100 != 0 or d.year % 400 == 0)) else 365)

    # prefer anomaly (deseasonalised)
    ycol = "anomaly" if "anomaly" in g.columns and g["anomaly"].notna().any() else "value"
    gg = g.dropna(subset=[ycol])
    t = np.array([decyear(d) for d in gg["date"]])
    grace_res = annual_ols(t, gg[ycol].to_numpy(float), unit="cm")  # function name misleading but OK
    # also from trends.csv
    gr_tr = tr[(tr["source"] == "grace") & (tr["variable"] == "TWS")]
    report["grace"] = {
        "tidy_n_months_used": int(len(gg)),
        "ycol": ycol,
        "recomputed_deseason_slope": grace_res,
        "trends_csv": gr_tr[["series", "window", "n", "start", "end", "lin_slope_per_decade", "robust_call", "headline"]].to_dict(orient="records"),
    }

    # smoke json
    smoke = json.loads((PIPE / "data" / "smoke_test_results.json").read_text())
    report["smoke"] = smoke

    # ------------------------------------------------------------------
    # 5. coverage_frac POWER
    # ------------------------------------------------------------------
    pw = pd.read_parquet(TIDY / "ukraine_bbox" / "nasa_power.parquet")
    pw_t2m = pw[pw["variable"] == "T2M"]
    report["power_coverage_frac"] = {
        "min": float(pw_t2m["coverage_frac"].min()),
        "median": float(pw_t2m["coverage_frac"].median()),
        "max": float(pw_t2m["coverage_frac"].max()),
        "unique_rounded": sorted(set(np.round(pw_t2m["coverage_frac"], 6))),
        "n_effective_cells_median": float(pw_t2m["n_effective_cells"].median()) if "n_effective_cells" in pw_t2m else None,
        "is_honest_not_1_0": bool(pw_t2m["coverage_frac"].min() < 0.999),
    }
    # merra2 / chirps / gldas / gpcc / imerg coverage on bbox vs mask
    cov = {}
    for region in regions:
        cov[region] = {}
        for src, var in [
            ("nasa_power", "T2M"), ("merra2", "T2M"), ("merra2", "PRECTOTCORR"),
            ("chirps", "precip"), ("gldas20", "Tair_f_inst"), ("gldas21", "Tair_f_inst"),
            ("gpm_imerg", "precipitation"), ("gpcc", "precip"), ("airs", "SurfAirTemp"),
            ("modis", "NDVI"), ("modis", "LST_Day"),
        ]:
            p = TIDY / region / f"{src}.parquet"
            if not p.exists():
                continue
            d = pd.read_parquet(p)
            if "variable" in d.columns:
                d = d[d["variable"] == var]
            if d.empty or "coverage_frac" not in d.columns:
                continue
            cov[region][f"{src}:{var}"] = {
                "min": float(np.nanmin(d["coverage_frac"])),
                "median": float(np.nanmedian(d["coverage_frac"])),
                "max": float(np.nanmax(d["coverage_frac"])),
            }
    report["coverage_frac_by_region"] = cov

    # ------------------------------------------------------------------
    # 6. GSOM March 2026 flag + all 2026 flags
    # ------------------------------------------------------------------
    gsom = pd.read_parquet(TIDY / "ukraine_bbox" / "gsom.parquet")
    gsom["date"] = pd.to_datetime(gsom["date"])
    m26 = gsom[(gsom["variable"] == "TAVG_anom") & (gsom["date"] == "2026-03-01")]
    y26 = gsom[gsom["date"].dt.year == 2026]
    report["gsom_2026"] = {
        "march_rows": m26[["date", "value", "flags", "n_valid"]].to_dict(orient="records"),
        "march_flagged_missing_or_partial": bool(
            len(m26) and (
                "missing_value" in str(m26.iloc[0]["flags"]) or "partial_year" in str(m26.iloc[0]["flags"])
            )
        ),
        "all_2026_TAVG_flags": y26[y26["variable"] == "TAVG_anom"][["date", "value", "flags"]].astype(str).to_dict(orient="records"),
        "any_2026_unflagged": bool(
            any(
                ("partial_year" not in str(f) and "missing_value" not in str(f))
                for f in y26["flags"].tolist()
            )
        ),
    }

    # MODIS flags: lst only on LST, no_qc on all
    mod = pd.read_parquet(TIDY / "ukraine_bbox" / "modis.parquet")
    flag_by_var = {}
    for var, gv in mod.groupby("variable"):
        flags = set()
        for f in gv["flags"].dropna().astype(str):
            for part in f.split(";"):
                flags.add(part.strip())
        flag_by_var[var] = sorted(flags)
    report["modis_flags_by_var"] = flag_by_var
    report["modis_lst_flag_only_on_LST"] = all(
        ("lst_clear_sky_winter_bias" in flag_by_var[v]) == (v.startswith("LST"))
        for v in flag_by_var
    )
    report["modis_all_no_qc"] = all("no_qc" in flag_by_var[v] for v in flag_by_var)

    # ------------------------------------------------------------------
    # 7. verify_global_vs_bbox: material trend diffs + significance flip
    # ------------------------------------------------------------------
    ver = pd.read_csv(PIPE / "data" / "verify_global_vs_bbox.csv")
    # Recompute both slopes with trend_stats where we can, from tidy (new) vs explanation.
    # We already have trend_new / trend_old in the table. Recheck a few from tidy annual.
    material = []
    for _, r in ver.iterrows():
        old, new, diff = r["trend_old"], r["trend_new"], r["trend_diff"]
        denom = abs(old) if abs(old) > 1e-12 else np.nan
        rel = abs(diff) / denom * 100 if np.isfinite(denom) else np.nan
        # practical magnitude: for precip, compare to typical annual total later
        material.append({
            "source": r["source"], "variable": r["variable"],
            "corr": float(r["corr"]),
            "mean_diff": float(r["mean_diff"]),
            "max_abs_diff": float(r["max_abs_diff"]),
            "rel_mean_diff_pct": float(r["rel_mean_diff_pct"]),
            "trend_years": r["trend_years"],
            "trend_unit": r["trend_unit"],
            "trend_new": float(new), "trend_old": float(old), "trend_diff": float(diff),
            "rel_trend_diff_pct": None if not np.isfinite(rel) else float(rel),
            "gt_5pct_of_old_slope": bool(np.isfinite(rel) and rel > 5),
            "n_common": int(r["n_common"]),
            "new_only": int(r["new_only"]), "old_only": int(r["old_only"]),
            "explanation": r["explanation"],
        })
    report["verify_rows"] = material
    report["verify_gt_5pct_slope"] = [x for x in material if x["gt_5pct_of_old_slope"]]

    # Recompute new slopes from tidy annual and compare to verify table
    # Map source/variable and year windows
    def tidy_trend(source, variable, y0, y1, how="mean"):
        ann = pd.read_parquet(TIDY / "ukraine_bbox" / "annual_seasonal.parquet")
        if "year" not in ann.columns:
            ann["year"] = pd.to_datetime(ann["date"]).dt.year
        s = ann[(ann["source"] == source) & (ann["variable"] == variable) & (ann["period"] == "ANN")]
        s = s[(s["year"] >= y0) & (s["year"] <= y1)].dropna(subset=["value"])
        return annual_ols(s["year"], s["value"]), int(len(s)), float(s["value"].mean()) if len(s) else None

    recompute_new = {}
    for row in material:
        y0, y1 = [int(x) for x in row["trend_years"].split("-")]
        try:
            stt, n, mean_ann = tidy_trend(row["source"], row["variable"], y0, y1)
            recompute_new[f"{row['source']}:{row['variable']}"] = {
                **stt, "n_annual": n, "mean_annual": mean_ann,
                "table_trend_new": row["trend_new"],
                "abs_diff_vs_table": abs(stt["ols_per_decade"] - row["trend_new"]) if stt["ols_per_decade"] is not None else None,
                "rel_to_mean_pct": abs(row["trend_diff"]) / abs(mean_ann) * 100 if mean_ann not in (None, 0) else None,
            }
        except Exception as e:
            recompute_new[f"{row['source']}:{row['variable']}"] = {"error": str(e)}
    report["recompute_new_from_tidy"] = recompute_new

    # old extract recomputes for key series
    old_re = {}
    # AIRS old
    old_airs = pd.read_csv("$UKRAINE_SAMPLES/airs/airs_ukraine_monthly.csv")
    old_re["airs_cols"] = list(old_airs.columns)

    # merra2 PRECTOT / PRECTOTCORR / T2M - find extract
    merra_files = list(Path("$UKRAINE_SAMPLES/merra2").glob("*.csv"))
    old_re["merra_files"] = [str(p) for p in merra_files]
    # merra2 flx extract
    try:
        flx = pd.read_csv("$UKRAINE_SAMPLES/merra2/merra2_flx_ukraine_monthly.csv")
        old_re["merra_flx_cols"] = list(flx.columns)
        flx["date"] = pd.to_datetime(flx[[c for c in flx.columns if "date" in c.lower()][0]])
        flx["year"] = flx["date"].dt.year
        # pick PRECTOT / PRECTOTCORR mm columns
        for key, candidates in {
            "PRECTOT": [c for c in flx.columns if "PRECTOT" in c and "CORR" not in c],
            "PRECTOTCORR": [c for c in flx.columns if "PRECTOTCORR" in c],
        }.items():
            old_re[f"merra_{key}_candidate_cols"] = candidates
            # prefer *mm* monthly
            col = None
            for c in candidates:
                if c.endswith("_mm") or c == key or "mm" in c.lower():
                    col = c
                    break
            if col is None and candidates:
                col = candidates[0]
            if col:
                g = flx.groupby("year")[col].agg(["sum","count","mean"])
                # if values look like mm/month, annual = sum; if already rate, mean
                use = "sum" if g["mean"].abs().mean() > 5 else "mean"
                gg = g[g["count"]==12][use]
                gg = gg.loc[(gg.index>=1980)&(gg.index<=2025)]
                old_re[f"merra_old_{key}"] = {"col": col, "agg": use, "n": int(len(gg)),
                                              "mean_annual": float(gg.mean()) if len(gg) else None,
                                              "stats": annual_ols(gg.index, gg.values)}
    except Exception as e:
        old_re["merra_flx_error"] = str(e)

    report["old_extract_probe"] = old_re

    # ------------------------------------------------------------------
    # 8. CHIRPS monthly diffs timing (if both series accessible)
    # ------------------------------------------------------------------
    new_ch = pd.read_parquet(TIDY / "ukraine_bbox" / "chirps.parquet")
    new_ch = new_ch[new_ch["variable"] == "precip"].copy()
    new_ch["date"] = pd.to_datetime(new_ch["date"])
    old_ch = pd.read_csv("$UKRAINE_SAMPLES/extra/chirps_v3/chirps_v3_ukraine_bbox_monthly.csv", comment="#")
    old_ch.columns = [c.strip() for c in old_ch.columns]
    report["old_chirps_cols"] = list(old_ch.columns)
    old_ch["time"] = pd.to_datetime(old_ch["time"])
    m = pd.merge(new_ch[["date", "value"]].rename(columns={"value": "new"}),
                 old_ch.rename(columns={"time": "date", "precip_mm": "old"})[["date", "old"]],
                 on="date", how="outer")
    m["diff"] = m["new"] - m["old"]
    m["abs"] = m["diff"].abs()
    big = m[m["abs"] > 0.33].copy()
    report["chirps_diff_timing"] = {
        "n_common": int(m.dropna(subset=["new","old"]).shape[0]),
        "n_new_only": int(m["old"].isna().sum()),
        "n_old_only": int(m["new"].isna().sum()),
        "max_abs_diff": float(m["abs"].max()) if m["abs"].notna().any() else None,
        "max_abs_date": str(m.loc[m["abs"].idxmax(), "date"].date()) if m["abs"].notna().any() else None,
        "n_abs_gt_0_33": int((m["abs"] > 0.33).sum()),
        "first_abs_gt_0_33": str(big["date"].min().date()) if len(big) else None,
        "last_abs_gt_0_33": str(big["date"].max().date()) if len(big) else None,
        "max_abs_before_2025_10": float(m[m["date"] < "2025-10-01"]["abs"].max()) if (m["date"] < "2025-10-01").any() else None,
        "diffs_2025_10_to_2025_12": m[m["date"].between("2025-10-01","2025-12-01")][["date","old","new","diff"]].astype(str).to_dict(orient="records"),
    }
    # annual 1981-2025 both ways
    def ann_sum(df, valcol, datecol="date"):
        d = df.dropna(subset=[valcol]).copy()
        d["year"] = pd.to_datetime(d[datecol]).dt.year
        # 12/12
        c = d.groupby("year")[valcol].agg(["sum","count"])
        c = c[c["count"]==12]["sum"]
        return c
    an = ann_sum(m, "new").rename("new")
    ao = ann_sum(m, "old").rename("old")
    both = pd.concat([an, ao], axis=1).dropna()
    both = both.loc[1981:2025]
    report["chirps_annual_1981_2025"] = {
        "n": int(len(both)),
        "new": annual_ols(both.index, both["new"]),
        "old": annual_ols(both.index, both["old"]),
        "year_2025_new": float(both.loc[2025, "new"]) if 2025 in both.index else None,
        "year_2025_old": float(both.loc[2025, "old"]) if 2025 in both.index else None,
        "year_2025_diff": float(both.loc[2025, "new"]-both.loc[2025, "old"]) if 2025 in both.index else None,
    }

    # ------------------------------------------------------------------
    # 9. Trend table sanity across regions
    # ------------------------------------------------------------------
    sanity = {}
    for region in regions:
        t = pd.read_csv(TIDY / region / "trends.csv")
        issues = []
        # n vs start/end
        for _, r in t.iterrows():
            if pd.isna(r["n"]) or pd.isna(r["start"]) or pd.isna(r["end"]):
                continue
            span = int(r["end"]) - int(r["start"]) + 1
            # annual series should have n <= span; monthly more
            series = str(r["series"])
            if "monthly" not in series.lower() and "deseas" not in series.lower():
                if int(r["n"]) > span:
                    issues.append(f"{r['source']}:{r['variable']}:{r['window']} n={r['n']} > span={span}")
                # 12/12 annual: n should be span minus missing
                miss = []
                if pd.notna(r.get("missing_years")) and str(r["missing_years"]).strip():
                    # may be comma-separated years or ranges
                    miss = [x.strip() for x in str(r["missing_years"]).split(",") if x.strip()]
                excl = []
                if pd.notna(r.get("excluded_years")) and str(r["excluded_years"]).strip():
                    excl = [x.strip() for x in str(r["excluded_years"]).split(",") if x.strip()]
                expected = span - len(miss)  # excluded may already be outside win?
                # don't fail hard; just record large gaps
                if "gappy" not in str(r["window"]) and len(miss) and r["source"] not in {"gsom", "ghcn"}:
                    issues.append(f"non-gappy window has missing_years: {r['source']}:{r['variable']}:{r['window']} {r['missing_years']}")
            if r["n"] < 8 and not r.get("short_record", False) and "short" not in str(r.get("robust_call", "")).lower():
                issues.append(f"short n={r['n']} without short_record label: {r['source']}:{r['variable']}:{r['window']}")
        sanity[region] = {
            "n_rows": int(len(t)),
            "n_sources": int(t["source"].nunique()),
            "windows": t["window"].value_counts().to_dict(),
            "n_min": int(t["n"].min()),
            "n_max": int(t["n"].max()),
            "any_null_slope": int(t["lin_slope_per_decade"].isna().sum()),
            "issues": issues[:30],
            "n_issues": len(issues),
            "airs_full_end": t[(t["source"]=="airs") & (t["variable"]=="SurfAirTemp") & (t["window"]=="full")][["end","n","lin_slope_per_decade","excluded_years","robust_call"]].to_dict(orient="records"),
        }
    report["region_trend_sanity"] = sanity

    # ------------------------------------------------------------------
    # 10. Units spot check on tidy monthly vs days
    # ------------------------------------------------------------------
    # IMERG: compare one month to expected range; also vs old extract if present
    imerg = pd.read_parquet(TIDY / "ukraine_bbox" / "gpm_imerg.parquet")
    imerg = imerg[imerg["variable"] == "precipitation"].copy()
    imerg["date"] = pd.to_datetime(imerg["date"])
    report["imerg_units_sanity"] = {
        "unit": imerg["unit"].iloc[0] if len(imerg) else None,
        "min": float(imerg["value"].min()),
        "max": float(imerg["value"].max()),
        "mean": float(imerg["value"].mean()),
        "looks_like_mm_per_month_not_mm_per_hr": bool(imerg["value"].mean() > 10),  # mm/hr mean would be <<1
    }
    # merra2 PRECTOTCORR
    mer = pd.read_parquet(TIDY / "ukraine_bbox" / "merra2.parquet")
    mer_p = mer[mer["variable"] == "PRECTOTCORR"]
    report["merra2_PRECTOTCORR_units"] = {
        "unit": mer_p["unit"].iloc[0],
        "min": float(mer_p["value"].min()), "max": float(mer_p["value"].max()),
        "mean": float(mer_p["value"].mean()),
        "looks_like_mm_per_month": bool(10 < mer_p["value"].mean() < 200),
    }
    g20 = pd.read_parquet(TIDY / "ukraine_bbox" / "gldas20.parquet")
    qs = g20[g20["variable"] == "Qs_acc"]
    ev = g20[g20["variable"] == "Evap_tavg"]
    report["gldas20_units"] = {
        "Qs_unit": qs["unit"].iloc[0], "Qs_mean": float(qs["value"].mean()),
        "Evap_unit": ev["unit"].iloc[0], "Evap_mean": float(ev["value"].mean()),
        "Qs_looks_mm_month": bool(0.1 < qs["value"].mean() < 80),
        "Evap_looks_mm_month": bool(10 < ev["value"].mean() < 200),
    }
    gp = pd.read_parquet(TIDY / "ukraine_bbox" / "gpcc.parquet")
    gp = gp[gp["variable"] == "precip"]
    report["gpcc_units"] = {
        "unit": gp["unit"].iloc[0], "mean": float(gp["value"].mean()),
        "looks_mm_month": bool(20 < gp["value"].mean() < 150),
    }

    # ------------------------------------------------------------------
    # 11. ukraine_mask primary stated? already in docs; record POWER T2M trends by region
    # ------------------------------------------------------------------
    region_t2m = {}
    for region in regions:
        t = pd.read_csv(TIDY / region / "trends.csv")
        for src, var, win in [
            ("nasa_power", "T2M", "1981-2025"),
            ("airs", "SurfAirTemp", "full"),
            ("grace", "TWS", "full"),
            ("gsom", "TAVG_anom", "1981-2019_station_window"),
        ]:
            rows = t[(t["source"]==src) & (t["variable"]==var) & (t["window"]==win)]
            # grace may be monthly
            if rows.empty:
                rows = t[(t["source"]==src) & (t["variable"]==var)]
            region_t2m[f"{region}:{src}:{var}:{win}"] = rows[
                ["series","window","n","start","end","lin_slope_per_decade","robust_call","headline","excluded_years"]
            ].to_dict(orient="records")
    report["key_trends_by_region"] = region_t2m

    OUT.write_text(json.dumps(report, indent=2, default=str))
    print("WROTE", OUT)
    print("GSOM match", report["gsom_tavg_bbox"]["matches_worker"], report["gsom_tavg_bbox"])
    print("AIRS years", report["airs_annual_years_SurfAirTemp"])
    print("AIRS 2025 in annual", report["airs_2025_in_annual"])
    print("AIRS recompute", report["airs_SurfAirTemp_2003_2024_from_tidy_annual"])
    print("POWER coverage", report["power_coverage_frac"])
    print("MODIS lst only LST", report["modis_lst_flag_only_on_LST"], report["modis_flags_by_var"])
    print("GSOM 2026", report["gsom_2026"]["march_rows"])
    print(">5% slope diffs:")
    for x in report["verify_gt_5pct_slope"]:
        print(" ", x["source"], x["variable"], "rel", round(x["rel_trend_diff_pct"], 2),
              "new", x["trend_new"], "old", x["trend_old"])
    print("regions", regions)
    print("station headline windows", report["station_window_checks"])


if __name__ == "__main__":
    main()
