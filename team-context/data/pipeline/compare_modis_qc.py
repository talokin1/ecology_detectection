"""MODIS QC impact: per-pixel QC'd (production) vs unQC'd series, from the SAME cached global pass.

For every region: share of valid area removed by QC (overall and by season), months/years lost, mean difference,
and annual 12/12 OLS trends (trend_methods) for QC'd vs unQC'd. Writes data/modis_qc_impact.csv (+ _seasonal.csv).
Run: OMP_NUM_THREADS=2 nice -n 10 python compare_modis_qc.py  (after run_pipeline.py; uses the series cache)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from ukpipe.core import LAST_FULL_YEAR, PIPE, annual_table, make_tidy  # noqa: E402
from ukpipe.loaders import global_grids as GG  # noqa: E402
from ukpipe.regions import load_region  # noqa: E402
from ukpipe.trends import tm  # noqa: E402

REGIONS = ["ukraine_bbox", "ukraine_mask"]
VARS = {"mod13c2_qc": ["NDVI", "EVI"], "mod11c3_qc": ["LST_Day_K", "LST_Night_K"]}
SEAS = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM", 6: "JJA", 7: "JJA", 8: "JJA", 9: "SON", 10: "SON", 11: "SON"}


def _trend(tidy, period="ANN"):
    a = annual_table(tidy)
    a = a[(a.period == period) & (a.year <= LAST_FULL_YEAR) & (a.year >= 2001)].sort_values("year")
    tr = tm.trend_stats(a.year.to_numpy(float), a.value.to_numpy(float))
    return tr, len(a), tm.robust_call(tr, monthly=False, short_record=False)


def main():
    rows, srows = [], []
    for reg in REGIONS:
        r = load_region(reg)
        for pk, keys in VARS.items():
            df, info = GG.regional_series(pk, r)
            if df is None:
                print(reg, pk, info); continue
            for k in keys:
                q = make_tidy("modis", k, reg, df["date"], df[k].to_numpy(float), preaggregated=False)
                u = make_tidy("modis", k, reg, df["date"], df[k + "__noqc"].to_numpy(float), preaggregated=False)
                (tq, nq, cq), (tu, nu, cu) = _trend(q), _trend(u)
                kept = df[k + "__qc_kept_area_frac"]
                d = (q["value"].to_numpy() - u["value"].to_numpy())
                lost_months = int((np.isfinite(u["value"]) & ~np.isfinite(q["value"])).sum())
                seas_tr = {}
                for per in ("DJF", "JJA"):
                    seas_tr[f"trend_{per}_qc"] = _trend(q, per)[0]["lin_slope_per_decade"]
                    seas_tr[f"trend_{per}_noqc"] = _trend(u, per)[0]["lin_slope_per_decade"]
                low = int((df[k + "__cov"] < 0.5).sum())
                rows.append(dict(**seas_tr, months_qc_coverage_lt50pct=low, region=reg, variable=q.variable.iloc[0], unit=q.unit.iloc[0], months=len(df),
                                 area_removed_by_qc_pct_mean=100 * (1 - kept.mean()),
                                 area_removed_by_qc_pct_max=100 * (1 - kept.min()),
                                 months_lost=lost_months, years_12of12_qc=nq, years_12of12_noqc=nu,
                                 mean_diff_qc_minus_noqc=np.nanmean(d), max_abs_diff=np.nanmax(np.abs(d)),
                                 trend_qc_per_decade=tq["lin_slope_per_decade"], trend_noqc_per_decade=tu["lin_slope_per_decade"],
                                 trend_diff=tq["lin_slope_per_decade"] - tu["lin_slope_per_decade"],
                                 hac1_p_qc=tq["hac1_p"], hac1_p_noqc=tu["hac1_p"], mk_hr_p_qc=tq["mk_hr_p"], mk_hr_p_noqc=tu["mk_hr_p"],
                                 robust_qc=cq, robust_noqc=cu))
                s = pd.DataFrame({"season": df["date"].dt.month.map(SEAS), "removed": 1 - kept, "d": d})
                for se, g in s.groupby("season"):
                    srows.append(dict(region=reg, variable=q.variable.iloc[0], season=se,
                                      area_removed_by_qc_pct_mean=100 * g.removed.mean(), mean_diff_qc_minus_noqc=np.nanmean(g.d)))
    out = pd.DataFrame(rows); so = pd.DataFrame(srows)
    out.to_csv(PIPE / "data" / "modis_qc_impact.csv", index=False)
    so.to_csv(PIPE / "data" / "modis_qc_impact_seasonal.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_colwidth", 40):
        print(out.round(4).to_string(index=False))
        print(so.pivot_table(index=["region", "variable"], columns="season", values="area_removed_by_qc_pct_mean").round(2))


if __name__ == "__main__":
    main()
