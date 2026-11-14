"""Verify the global-file cuts against the old pre-aggregated bbox extracts (region ukraine_bbox).

For every series produced by both paths: monthly correlation, mean diff (global - old), max |diff|,
and the difference of annual OLS trends (per decade) over common complete (12/12) years.
Writes data/verify_global_vs_bbox.csv (read by the QC report).
Run: OMP_NUM_THREADS=2 nice -n 10 python verify_global_vs_bbox.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from ukpipe.core import PIPE, annual_table  # noqa: E402
from ukpipe.loaders import dispatch as D, gridded as G, tables as T  # noqa: E402
from ukpipe.regions import load_region  # noqa: E402

PAIRS = {"merra2": (D.load_merra2, T.load_merra2), "gldas20": (D.load_gldas20, T.load_gldas20),
         "gldas21": (D.load_gldas21, T.load_gldas21), "gpm_imerg": (D.load_imerg, T.load_imerg),
         "airs": (D.load_airs, T.load_airs), "modis": (D.load_modis, T.load_modis),
         "gpcc": (D.load_gpcc, T.load_gpcc), "chirps": (D.load_chirps, G.load_chirps)}
WHY = {"merra2": "overlap weights vs extract cell-centre selection (edge rows/cols at 0.5x0.625)",
       "gldas20": "overlap vs centre; land-only grid so coastal cells differ", "gldas21": "overlap vs centre; land-only coastal cells",
       "gpm_imerg": "overlap vs centre; global file starts 1998 (extract 2000)",
       "airs": "per-cell nanmean(A,D) vs mean of A and D bbox means; 1 deg overlap vs centre",
       "modis": "global = per-pixel QC'd + area-weighted; extract = unQC'd unweighted pixel mean (VI winter differs by QC)",
       "gpcc": "overlap vs centre at 1 deg; global = same v2025 product",
       "chirps": "global v3.0 file vs bbox nc; overlap vs centre at 0.05 deg"}


def ann_slope(df):
    a = annual_table(df)
    a = a[(a.period == "ANN") & np.isfinite(a.value)]
    return a.set_index("year")["value"], (a.unit.iloc[0] if len(a) else "")


def main():
    r = load_region("ukraine_bbox")
    rows = []
    for src, (fnew, fold) in PAIRS.items():
        new, nn = fnew(r)
        old, _ = fold(r)
        if nn.get("path") == "old_bbox_extract":
            print(f"{src}: global file missing, fallback used -> nothing to verify"); continue
        new = pd.concat(new); old = pd.concat(old)
        for var in sorted(set(new.variable) & set(old.variable)):
            a = new[new.variable == var].set_index("date")["value"]
            b = old[old.variable == var].set_index("date")["value"]
            j = pd.concat([a.rename("new"), b.rename("old")], axis=1).dropna()
            d = j.new - j.old
            (an, aunit), (ao, _) = ann_slope(new[new.variable == var]), ann_slope(old[old.variable == var])
            yrs = an.index.intersection(ao.index); yrs = yrs[yrs <= 2025]
            if src == "airs":
                yrs = yrs[yrs <= 2024]
            sl = lambda s: np.polyfit(yrs, s.loc[yrs].to_numpy(), 1)[0] * 10 if len(yrs) > 2 else np.nan
            sn, so = sl(an), sl(ao)
            rows.append(dict(source=src, variable=var, unit=new[new.variable == var].unit.iloc[0],
                             n_common=len(j), first=j.index.min().strftime("%Y-%m"), last=j.index.max().strftime("%Y-%m"),
                             new_only=len(a.dropna().index.difference(j.index)), old_only=len(b.dropna().index.difference(j.index)),
                             corr=j.new.corr(j.old), mean_diff=d.mean(), max_abs_diff=d.abs().max(),
                             rel_mean_diff_pct=100 * d.mean() / j.old.abs().mean(),
                             trend_unit=f"{aunit.replace('mm/year', 'mm/yr')} per decade", trend_new=sn, trend_old=so, trend_diff=sn - so, trend_years=f"{yrs.min()}-{yrs.max()}" if len(yrs) else "",
                             explanation=WHY[src]))
    out = pd.DataFrame(rows)
    out.to_csv(PIPE / "data" / "verify_global_vs_bbox.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_colwidth", 30):
        print(out.drop(columns="explanation").round(4).to_string(index=False))


if __name__ == "__main__":
    main()
