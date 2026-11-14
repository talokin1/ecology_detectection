#!/usr/bin/env python3
"""CCI SM v09.2 Ukraine-bbox review recomputes. Writes only under team-context/team/reviews/."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, "$UKRAINE_SAMPLES/_staging")
from trend_methods import fmt_trend, trend_stats, robust_call

CSV = Path("$UKRAINE_SAMPLES/extra/cci_sm/cci_sm_combined_v09_2_ukraine_bbox_monthly.csv")
OUT = Path("team-context/team/reviews/cci_sm_recompute_results.json")

MIN_COV, MIN_DAYS = 0.50, 5.0

# Official CCI SM sensor-transition dates used for break adjustment
# (PVIR v08.1 §5.1.7; also typical constellation changes).
BREAKS = [
    ("1987-07 SMMR→SSM/I", 1987, 7),
    ("1991-08 SSM/I constellation", 1991, 8),
    ("1998-01 TMI", 1998, 1),
    ("2002-06 AMSR-E", 2002, 6),
    ("2007-01 ASCAT", 2007, 1),
    ("2010-01 SMOS", 2010, 1),
    ("2012-07 AMSR2 (after AMSR-E gap)", 2012, 7),
    ("2015-03/04 SMAP", 2015, 4),
]

ERAS = [
    ("1978-11–1987-06 SMMR", 1978, 11, 1987, 6),
    ("1987-07–1991-07 SSM/I early", 1987, 7, 1991, 7),
    ("1991-08–2002-05 SSM/I+TMI (passive)", 1991, 8, 2002, 5),
    ("2002-06–2006-12 +AMSR-E still passive-led", 2002, 6, 2006, 12),
    ("2007-01–2011-09 +ASCAT (active enters)", 2007, 1, 2011, 9),
    ("2011-10–2012-06 AMSR-E gap", 2011, 10, 2012, 6),
    ("2012-07–2015-03 +AMSR2", 2012, 7, 2015, 3),
    ("2015-04–2024-12 +SMAP multi-sensor", 2015, 4, 2024, 12),
]


def ym_key(y, m):
    return y * 12 + m


def in_span(df, y0, m0, y1, m1):
    a = ym_key(df.year, df.month)
    return df[(a >= ym_key(y0, m0)) & (a <= ym_key(y1, m1))].copy()


def decyear(y, m):
    return y + (m - 0.5) / 12.0


def load():
    df = pd.read_csv(CSV, comment="#")
    for c in ["sm_m3m3", "weight_coverage", "mean_n_valid_days", "median_n_valid_days",
              "n_cells_valid", "n_cells"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["t"] = decyear(df["year"], df["month"])
    return df


def filt(df, min_cov=MIN_COV, min_days=MIN_DAYS, day_col="mean_n_valid_days"):
    return df[(df.weight_coverage >= min_cov) & (df[day_col] >= min_days) & df.sm_m3m3.notna()].copy()


def deseasonalize(df, col="sm_m3m3"):
    clim = df.groupby("month")[col].mean()
    out = df.copy()
    out["anom"] = out[col] - out["month"].map(clim)
    return out, clim.to_dict()


def pack_tr(tr):
    if tr is None:
        return None
    keys = [
        "n", "start", "end",
        "lin_slope_per_decade", "lin_p", "lin_p_ar1",
        "hac1_p", "hac3_p", "n_eff_ar1", "r_resid_lag1",
        "theil_sen_per_decade", "mk_p", "mk_hr_p", "mk_tfpw_p", "mk_yw_p",
        "hr_unequal_spacing", "hr_anti_conservative",
    ]
    return {k: (None if (isinstance(tr[k], float) and not np.isfinite(tr[k])) else
                (bool(tr[k]) if isinstance(tr[k], (bool, np.bool_)) else
                 (int(tr[k]) if k == "n" else (float(tr[k]) if isinstance(tr[k], (float, np.floating, int, np.integer)) else tr[k]))))
            for k in keys}


def run_trend(df, value_col, monthly):
    if len(df) < 8:
        return None, "insufficient data"
    tr = trend_stats(df["t"].values, df[value_col].values)
    return tr, fmt_trend(tr, "m3 m-3 / decade", monthly=monthly)


def main():
    df = load()
    out = {
        "n_file": int(len(df)),
        "range": f"{df.date.iloc[0]} to {df.date.iloc[-1]}",
        "sm_min": float(df.sm_m3m3.min()),
        "sm_max": float(df.sm_m3m3.max()),
        "sm_mean": float(df.sm_m3m3.mean()),
    }

    # Coverage by calendar month (unfiltered) — reproduce their table
    month_cov = []
    for m, g in df.groupby("month"):
        month_cov.append({
            "month": int(m),
            "mean_coverage": float(g.weight_coverage.mean()),
            "mean_n_valid_days": float(g.mean_n_valid_days.mean()),
            "median_n_valid_days": float(g.median_n_valid_days.mean()),
            "n": int(len(g)),
            "frac_pass_filter": float(((g.weight_coverage >= MIN_COV) & (g.mean_n_valid_days >= MIN_DAYS)).mean()),
        })
    out["coverage_by_month"] = month_cov

    # Coverage by era
    eras = []
    for name, y0, m0, y1, m1 in ERAS:
        sub = in_span(df, y0, m0, y1, m1)
        kept = filt(sub)
        warm = sub[sub.month.isin([4, 5, 6, 7, 8, 9, 10])]
        warm_kept = filt(warm)
        djf = sub[sub.month.isin([12, 1, 2])]
        djf_kept = filt(djf)
        eras.append({
            "era": name,
            "n_months": int(len(sub)),
            "mean_n_valid_days": float(sub.mean_n_valid_days.mean()),
            "median_of_mean_n_valid_days": float(sub.mean_n_valid_days.median()),
            "p25_n_valid_days": float(sub.mean_n_valid_days.quantile(0.25)),
            "p75_n_valid_days": float(sub.mean_n_valid_days.quantile(0.75)),
            "mean_median_n_valid_days": float(sub.median_n_valid_days.mean()),
            "mean_weight_coverage": float(sub.weight_coverage.mean()),
            "frac_pass_filter": float(len(kept) / len(sub)) if len(sub) else None,
            "n_kept": int(len(kept)),
            "n_dropped": int(len(sub) - len(kept)),
            "apr_oct_mean_days": float(warm.mean_n_valid_days.mean()) if len(warm) else None,
            "apr_oct_frac_pass": float(len(warm_kept) / len(warm)) if len(warm) else None,
            "djf_mean_days": float(djf.mean_n_valid_days.mean()) if len(djf) else None,
            "djf_frac_pass": float(len(djf_kept) / len(djf)) if len(djf) else None,
            "mean_sm": float(sub.sm_m3m3.mean()),
            "mean_sm_kept": float(kept.sm_m3m3.mean()) if len(kept) else None,
        })
    out["coverage_by_era"] = eras

    # Yearly coverage (for sparse early years)
    yearly = []
    for y, g in df.groupby("year"):
        kept = filt(g)
        yearly.append({
            "year": int(y),
            "n": int(len(g)),
            "mean_days": float(g.mean_n_valid_days.mean()),
            "apr_oct_mean_days": float(g[g.month.isin(range(4, 11))].mean_n_valid_days.mean()),
            "djf_mean_days": float(g[g.month.isin([12, 1, 2])].mean_n_valid_days.mean()) if (g.month.isin([12, 1, 2])).any() else None,
            "mean_cov": float(g.weight_coverage.mean()),
            "n_kept": int(len(kept)),
            "djf_kept": int(len(filt(g[g.month.isin([12, 1, 2])]))),
            "apr_oct_kept": int(len(filt(g[g.month.isin(range(4, 11))]))),
        })
    out["coverage_by_year"] = yearly

    # Headline windows, exact reproduction + sensitivities
    windows = [
        ("1991-01 to 2024-12", 1991, 1, 2024, 12),
        ("full 1978-11 to 2024-12", 1978, 11, 2024, 12),
        ("1992-01 to 2024-12 (after official 1991-08 break)", 1992, 1, 2024, 12),
        ("2002-06 to 2024-12 (AMSR-E onward)", 2002, 6, 2024, 12),
        ("2007-01 to 2024-12 (ASCAT onward)", 2007, 1, 2024, 12),
    ]

    headlines = []
    filter_sens = []
    for wname, y0, m0, y1, m1 in windows:
        sub = in_span(df, y0, m0, y1, m1)
        kept = filt(sub)
        rec = {
            "window": wname,
            "raw": int(len(sub)),
            "kept": int(len(kept)),
            "dropped": int(len(sub) - len(kept)),
            "djf_kept": int(len(kept[kept.month.isin([12, 1, 2])])),
            "djf_raw": int(len(sub[sub.month.isin([12, 1, 2])])),
        }
        if kept.empty:
            headlines.append(rec)
            continue
        des, _ = deseasonalize(kept)
        tr, text = run_trend(des, "anom", monthly=True)
        rec["monthly"] = {"text": text, "stats": pack_tr(tr), "call": robust_call(tr, monthly=True)}

        warm = des[des.month.isin([4, 5, 6, 7, 8, 9, 10])].copy()
        warm, _ = deseasonalize(warm)
        trw, textw = run_trend(warm, "anom", monthly=True)
        rec["apr_oct_monthly"] = {
            "text": textw, "stats": pack_tr(trw), "call": robust_call(trw, monthly=True),
            "n": int(len(warm)),
            "unique_year_gaps": None,
        }
        # spacing of Apr-Oct monthly series
        if len(warm) >= 3:
            dts = np.diff(np.sort(warm.t.values))
            rec["apr_oct_monthly"]["median_dt_years"] = float(np.median(dts))
            rec["apr_oct_monthly"]["max_dt_years"] = float(dts.max())
            rec["apr_oct_monthly"]["n_gaps_gt_1.5med"] = int((dts > 1.5 * np.median(dts) + 1e-12).sum())

        # Annual mean of coverage-filtered months, n>=6 (their rule)
        ann = des.groupby("year").agg(anom=("anom", "mean"), n=("anom", "size")).reset_index()
        ann6 = ann[ann.n >= 6].copy()
        ann6["t"] = ann6["year"] + 0.5
        tra, texta = run_trend(ann6, "anom", monthly=False)
        rec["annual_nmonths_ge6"] = {
            "text": texta, "stats": pack_tr(tra), "call": robust_call(tra, monthly=False),
            "n_years": int(len(ann6)),
            "years_below_10_months": int((ann6.n < 10).sum()),
            "years_below_12_months": int((ann6.n < 12).sum()),
            "mean_n_months": float(ann6.n.mean()),
        }
        # Team rule: deseasonalized annual only if >=10 months
        ann10 = ann[ann.n >= 10].copy()
        ann10["t"] = ann10["year"] + 0.5
        if len(ann10) >= 8:
            tr10, text10 = run_trend(ann10, "anom", monthly=False)
            rec["annual_nmonths_ge10"] = {
                "text": text10, "stats": pack_tr(tr10), "call": robust_call(tr10, monthly=False),
                "n_years": int(len(ann10)),
            }

        # Apr-Oct seasonal mean per year (recommended)
        for min_m, label in [(6, "ge6of7"), (7, "7of7")]:
            ao = kept[kept.month.isin(range(4, 11))]
            # deseasonalize within Apr-Oct then average? Or average raw then... 
            # Prefer: mean of the 7 calendar months (raw SM), one value per year, then trend.
            # Also: mean of month-anomalies (equivalent if all 7 present; not if some missing).
            g = ao.groupby("year").agg(sm=("sm_m3m3", "mean"), n=("sm_m3m3", "size")).reset_index()
            g = g[g.n >= min_m].copy()
            g["t"] = g["year"] + (7.0 - 0.5) / 12.0  # mid Apr-Oct ≈ mid-July
            if len(g) >= 8:
                # raw seasonal mean (seasonal cycle is constant if 7/7; residual seasonality if incomplete)
                trs, texts = run_trend(g, "sm", monthly=False)
                rec[f"apr_oct_seasonal_mean_{label}"] = {
                    "text": texts, "stats": pack_tr(trs), "call": robust_call(trs, monthly=False),
                    "n_years": int(len(g)),
                    "mean_n_months": float(g.n.mean()),
                }
            # anomaly-mean version (month clim of this window's Apr-Oct kept months)
            ao2, _ = deseasonalize(ao)
            g2 = ao2.groupby("year").agg(anom=("anom", "mean"), n=("anom", "size")).reset_index()
            g2 = g2[g2.n >= min_m].copy()
            g2["t"] = g2["year"] + (7.0 - 0.5) / 12.0
            if len(g2) >= 8:
                trs2, texts2 = run_trend(g2, "anom", monthly=False)
                rec[f"apr_oct_seasonal_anom_{label}"] = {
                    "text": texts2, "stats": pack_tr(trs2), "call": robust_call(trs2, monthly=False),
                    "n_years": int(len(g2)),
                }

        headlines.append(rec)

        # Filter sensitivity only for the two main windows
        if "1991-01" in wname or wname.startswith("full"):
            for min_days in (5, 10, 15, 20):
                for min_cov in (0.50, 0.70, 0.80):
                    k2 = filt(sub, min_cov=min_cov, min_days=min_days)
                    if len(k2) < 8:
                        filter_sens.append({"window": wname, "min_cov": min_cov, "min_days": min_days, "n": int(len(k2))})
                        continue
                    d2, _ = deseasonalize(k2)
                    tr2, _ = run_trend(d2, "anom", monthly=True)
                    # also Apr-Oct seasonal 7/7 under this filter
                    ao = k2[k2.month.isin(range(4, 11))]
                    g = ao.groupby("year").agg(sm=("sm_m3m3", "mean"), n=("sm_m3m3", "size")).reset_index()
                    g = g[g.n >= 7].copy()
                    g["t"] = g["year"] + 6.5 / 12.0
                    trs = None
                    if len(g) >= 8:
                        trs, _ = run_trend(g, "sm", monthly=False)
                    filter_sens.append({
                        "window": wname,
                        "min_cov": min_cov,
                        "min_days": min_days,
                        "n_kept": int(len(k2)),
                        "n_dropped": int(len(sub) - len(k2)),
                        "djf_kept": int(len(k2[k2.month.isin([12, 1, 2])])),
                        "monthly_ols": float(tr2["lin_slope_per_decade"]) if tr2 else None,
                        "monthly_sen": float(tr2["theil_sen_per_decade"]) if tr2 else None,
                        "monthly_hac3_p": float(tr2["hac3_p"]) if tr2 else None,
                        "monthly_hr_p": float(tr2["mk_hr_p"]) if tr2 else None,
                        "monthly_yw_p": float(tr2["mk_yw_p"]) if tr2 else None,
                        "monthly_call": robust_call(tr2, monthly=True) if tr2 else None,
                        "monthly_hr_unequal": bool(tr2["hr_unequal_spacing"]) if tr2 else None,
                        "ao7_n": int(len(g)),
                        "ao7_ols": float(trs["lin_slope_per_decade"]) if trs else None,
                        "ao7_sen": float(trs["theil_sen_per_decade"]) if trs else None,
                        "ao7_hac1_p": float(trs["hac1_p"]) if trs else None,
                        "ao7_hr_p": float(trs["mk_hr_p"]) if trs else None,
                        "ao7_call": robust_call(trs, monthly=False) if trs else None,
                    })
            # also median_n_valid_days >= 10 / 15
            for med_days in (10, 15):
                k2 = sub[(sub.weight_coverage >= 0.5) & (sub.median_n_valid_days >= med_days) & sub.sm_m3m3.notna()].copy()
                if len(k2) < 8:
                    continue
                d2, _ = deseasonalize(k2)
                tr2, _ = run_trend(d2, "anom", monthly=True)
                filter_sens.append({
                    "window": wname,
                    "min_cov": 0.5,
                    "min_days": f"median>={med_days}",
                    "n_kept": int(len(k2)),
                    "djf_kept": int(len(k2[k2.month.isin([12, 1, 2])])),
                    "monthly_ols": float(tr2["lin_slope_per_decade"]),
                    "monthly_sen": float(tr2["theil_sen_per_decade"]),
                    "monthly_hac3_p": float(tr2["hac3_p"]),
                    "monthly_hr_p": float(tr2["mk_hr_p"]),
                    "monthly_call": robust_call(tr2, monthly=True),
                })

    out["headlines"] = headlines
    out["filter_sensitivity"] = filter_sens

    # Break / mean-variance shift checks on deseasonalized filtered series
    # Use climatology from the analysis window so shifts aren't seasonal.
    def shift_tests(series_df, window_months=24, buffer_months=1):
        results = []
        for name, yb, mb in BREAKS:
            t_break = ym_key(yb, mb)
            pre = series_df[(series_df._k < t_break - buffer_months) & (series_df._k >= t_break - buffer_months - window_months)]
            post = series_df[(series_df._k >= t_break + buffer_months) & (series_df._k < t_break + buffer_months + window_months)]
            if len(pre) < 8 or len(post) < 8:
                results.append({
                    "break": name, "window_months": window_months,
                    "n_pre": int(len(pre)), "n_post": int(len(post)),
                    "note": "too few samples in ± window after coverage filter",
                })
                continue
            a, b = pre.anom.values, post.anom.values
            ttest = stats.ttest_ind(a, b, equal_var=False)
            lev = stats.levene(a, b)
            results.append({
                "break": name,
                "window_months": window_months,
                "n_pre": int(len(pre)),
                "n_post": int(len(post)),
                "mean_pre": float(a.mean()),
                "mean_post": float(b.mean()),
                "delta_mean": float(b.mean() - a.mean()),
                "sd_pre": float(a.std(ddof=1)),
                "sd_post": float(b.std(ddof=1)),
                "var_ratio": float((b.var(ddof=1) / a.var(ddof=1)) if a.var(ddof=1) > 0 else np.nan),
                "welch_t_p": float(ttest.pvalue),
                "levene_p": float(lev.pvalue),
                "delta_over_pooled_sd": float((b.mean() - a.mean()) / np.sqrt(((len(a)-1)*a.var(ddof=1)+(len(b)-1)*b.var(ddof=1))/(len(a)+len(b)-2))),
            })
        return results

    # Full-record deseasonalized (coverage-filtered) for breaks across 1987 etc.
    kept_full = filt(df)
    des_full, _ = deseasonalize(kept_full)
    des_full["_k"] = ym_key(des_full.year, des_full.month)
    out["breaks_full_24m"] = shift_tests(des_full, 24)
    out["breaks_full_36m"] = shift_tests(des_full, 36)

    # 1991-2024 window climatology
    sub91 = in_span(df, 1991, 1, 2024, 12)
    kept91 = filt(sub91)
    des91, _ = deseasonalize(kept91)
    des91["_k"] = ym_key(des91.year, des91.month)
    out["breaks_1991_24m"] = shift_tests(des91, 24)
    out["breaks_1991_36m"] = shift_tests(des91, 36)

    # Apr-Oct only shifts (better sampled)
    ao91 = des91[des91.month.isin(range(4, 11))].copy()
    ao91, _ = deseasonalize(ao91)
    ao91["_k"] = ym_key(ao91.year, ao91.month)
    out["breaks_1991_aprest_24m"] = shift_tests(ao91, 24)

    # Winter-coverage bias: which DJF months are kept, and does kept-DJF SM differ
    djf = df[df.month.isin([12, 1, 2])].copy()
    djf["kept"] = (djf.weight_coverage >= MIN_COV) & (djf.mean_n_valid_days >= MIN_DAYS)
    # early vs late fraction kept
    winter_bias = {
        "djf_n": int(len(djf)),
        "djf_kept": int(djf.kept.sum()),
        "mean_days_kept": float(djf.loc[djf.kept, "mean_n_valid_days"].mean()),
        "mean_days_dropped": float(djf.loc[~djf.kept, "mean_n_valid_days"].mean()) if (~djf.kept).any() else None,
        "mean_sm_kept": float(djf.loc[djf.kept, "sm_m3m3"].mean()),
        "mean_sm_dropped": float(djf.loc[~djf.kept, "sm_m3m3"].mean()) if (~djf.kept).any() else None,
        "frac_kept_1978_1990": float(djf[djf.year <= 1990].kept.mean()) if (djf.year <= 1990).any() else None,
        "frac_kept_1991_2001": float(djf[(djf.year >= 1991) & (djf.year <= 2001)].kept.mean()),
        "frac_kept_2002_2014": float(djf[(djf.year >= 2002) & (djf.year <= 2014)].kept.mean()),
        "frac_kept_2015_2024": float(djf[djf.year >= 2015].kept.mean()),
        "mean_days_1991_2001": float(djf[(djf.year >= 1991) & (djf.year <= 2001)].mean_n_valid_days.mean()),
        "mean_days_2015_2024": float(djf[djf.year >= 2015].mean_n_valid_days.mean()),
    }
    # correlation of year with DJF n_valid_days (sampling trend)
    d91 = djf[(djf.year >= 1991) & (djf.year <= 2024)]
    if len(d91) >= 8:
        lr = stats.linregress(d91.t, d91.mean_n_valid_days)
        winter_bias["djf_days_trend_per_decade_1991_2024"] = float(lr.slope * 10)
        winter_bias["djf_days_trend_p"] = float(lr.pvalue)
    out["winter_bias"] = winter_bias

    # months dropped in 1991-2024
    dropped91 = sub91.loc[~sub91.index.isin(kept91.index), ["year", "month", "date", "weight_coverage", "mean_n_valid_days", "sm_m3m3"]]
    out["dropped_1991_2024"] = dropped91.to_dict(orient="records")
    out["dropped_1991_by_month"] = {int(m): int(n) for m, n in dropped91.month.value_counts().sort_index().items()}

    # Compare reported numbers (rounded as in their text)
    def close(a, b, tol=5.5e-4):  # ±0.0005 on a .3f slope
        return abs(a - b) <= tol

    OUT.write_text(json.dumps(out, indent=2, default=str))
    print(f"wrote {OUT}")

    # stdout summary for the notes
    print("\n===== HEADLINES =====")
    for rec in headlines:
        print(f"\n== {rec['window']} raw={rec.get('raw')} kept={rec.get('kept')} dropped={rec.get('dropped')} DJF kept={rec.get('djf_kept')}/{rec.get('djf_raw')}")
        for k in ["monthly", "apr_oct_monthly", "annual_nmonths_ge6", "annual_nmonths_ge10",
                  "apr_oct_seasonal_mean_ge6of7", "apr_oct_seasonal_mean_7of7",
                  "apr_oct_seasonal_anom_7of7"]:
            if k in rec:
                st = rec[k].get("stats") or {}
                print(f"  [{k}] n={st.get('n')} OLS={st.get('lin_slope_per_decade')} Sen={st.get('theil_sen_per_decade')} "
                      f"HAC3p={st.get('hac3_p')} HAC1p={st.get('hac1_p')} HRp={st.get('mk_hr_p')} YWp={st.get('mk_yw_p')} "
                      f"uneq={st.get('hr_unequal_spacing')} call={rec[k].get('call')}")
                if k == "apr_oct_monthly":
                    print(f"       spacing median_dt={rec[k].get('median_dt_years')} max_dt={rec[k].get('max_dt_years')} n_gaps={rec[k].get('n_gaps_gt_1.5med')}")
                if k == "annual_nmonths_ge6":
                    print(f"       years_below_10={rec[k].get('years_below_10_months')} below_12={rec[k].get('years_below_12_months')} mean_n={rec[k].get('mean_n_months')}")

    print("\n===== ERAS =====")
    for e in eras:
        print(f"{e['era']}: n={e['n_months']} days={e['mean_n_valid_days']:.1f} (p25={e['p25_n_valid_days']:.1f}) "
              f"cov={e['mean_weight_coverage']:.3f} pass={e['frac_pass_filter']:.2f} "
              f"AO days={e['apr_oct_mean_days']:.1f} pass={e['apr_oct_frac_pass']:.2f} "
              f"DJF days={e['djf_mean_days']:.1f} pass={e['djf_frac_pass']:.2f}  sm={e['mean_sm']:.3f}")

    print("\n===== BREAKS full 36m (welch p, levene p, d) =====")
    for r in out["breaks_full_36m"]:
        if "welch_t_p" in r:
            print(f"  {r['break']}: Δ={r['delta_mean']:+.4f} d={r['delta_over_pooled_sd']:+.2f} "
                  f"welch_p={r['welch_t_p']:.3g} levene_p={r['levene_p']:.3g} var_ratio={r['var_ratio']:.2f} "
                  f"n={r['n_pre']}/{r['n_post']}")
        else:
            print(f"  {r['break']}: {r.get('note')} n={r['n_pre']}/{r['n_post']}")

    print("\n===== BREAKS 1991 Apr-Oct 24m =====")
    for r in out["breaks_1991_aprest_24m"]:
        if "welch_t_p" in r:
            print(f"  {r['break']}: Δ={r['delta_mean']:+.4f} d={r['delta_over_pooled_sd']:+.2f} "
                  f"welch_p={r['welch_t_p']:.3g} levene_p={r['levene_p']:.3g} n={r['n_pre']}/{r['n_post']}")
        else:
            print(f"  {r['break']}: {r.get('note')} n={r['n_pre']}/{r['n_post']}")

    print("\n===== WINTER BIAS =====")
    print(json.dumps(winter_bias, indent=2))
    print("dropped 1991-2024 by month:", out["dropped_1991_by_month"])

    print("\n===== FILTER SENS (1991 window, selected) =====")
    for r in filter_sens:
        if "1991" in r["window"] and r.get("monthly_ols") is not None:
            print(f"  cov>={r['min_cov']} days>={r['min_days']}: kept={r.get('n_kept')} djf={r.get('djf_kept')} "
                  f"OLS={r['monthly_ols']:+.4f} Sen={r.get('monthly_sen', float('nan')):+.4f} "
                  f"HAC3p={r.get('monthly_hac3_p')} HRp={r.get('monthly_hr_p')} call={r.get('monthly_call')}")
            if r.get("ao7_ols") is not None:
                print(f"      AO 7/7 n={r['ao7_n']} OLS={r['ao7_ols']:+.4f} Sen={r['ao7_sen']:+.4f} "
                      f"HAC1p={r['ao7_hac1_p']:.3g} HRp={r['ao7_hr_p']:.3g} call={r['ao7_call']}")


if __name__ == "__main__":
    main()
