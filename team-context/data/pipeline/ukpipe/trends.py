"""Trend table.

PRIMARY significance (v1.4, team lead via Thinker 14 Nov 2026): repo Mann-Kendall + Yue-Wang AR(1) correction with Theil-Sen
slope and verdict, imported unchanged from the repo trend_stats.py (see ukpipe/repo_yw.py). The approved
trend_methods.py (OLS + HAC lag-1/3 + Hamed-Rao lag-3) is kept as SENSITIVITY columns; OLS slopes (lin_*) are unchanged.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .paths import load_module, trend_methods_py

tm = load_module(trend_methods_py(), "trend_methods")

from .core import LAST_FULL_YEAR, SHORT_RECORD_YEARS, TREND_EXCLUDE_FLAGS  # noqa: E402
from .grace_method import METHOD_LABEL as GRACE_METHOD_LABEL, grace_headline_trend  # noqa: E402
from . import repo_yw  # noqa: E402

WINDOWS = [(1981, 2025), (2001, 2025)]
STATION_SOURCES = {"ghcn", "gsom"}
# monthly flags whose YEARS are dropped from every trend until the issue is checked
EXCLUDE_FROM_TRENDS = TREND_EXCLUDE_FLAGS
# rows that are computed and kept in the test family but are NOT climate findings / headlines
FORCING_DIAGNOSTIC = {("gldas21", "snowfall"), ("gldas21", "SWE_inst")}
FORCING_DIAG_REASON = ("FORCING DIAGNOSTIC (not a finding): GLDAS-2.1 snow disagrees with GLDAS-2.0 over 2000-2014 "
                       "(annual means 78 vs 131 mm/yr, overlap slopes of opposite sign), the 2000-2025 window spans the "
                       "2.1 forcing breaks (Mar 2001, AGRMET after 2011, GALWEM from Jun 2025), dropping 2000/2025 gives "
                       "~-16 mm/yr per decade n.s., the HAC p fails Bonferroni in the annual family, and no non-GLDAS-2.1 "
                       "snow source exists in the pipeline to confirm it")
SAMPLING_DIAGNOSTIC = {("modis", "LST_Day_clear_days"), ("modis", "LST_Night_clear_days")}
VI_VARS = {("modis", "NDVI"), ("modis", "EVI")}
VI_SEASONS = [("JJA", "seasonal_JJA_3of3_peak_season", "peak season (JJA)"),
              ("AMJJAS", "seasonal_AprSep_6of6_growing_season", "growing season (Apr-Sep)")]
VI_SEASON_NOTE = ("season-sensitive: compare the JJA (peak season) and Apr-Sep (growing season) rows side by side; "
                  "neither is preferred")


def pettitt(x):
    """Pettitt (1979) change-point test. EXPLORATORY ONLY: anti-conservative under autocorrelation."""
    x = np.asarray(x, float); n = len(x)
    if n < 8:
        return np.nan, np.nan
    s = np.sign(x[:, None] - x[None, :])
    U = np.array([s[:k + 1, k + 1:].sum() for k in range(n - 1)])
    K = np.abs(U).max(); k = int(np.abs(U).argmax())
    p = min(1.0, 2 * np.exp(-6 * K ** 2 / (n ** 3 + n ** 2)))
    return k, p


def _span(years):
    """[2007, 2008, 2009, 2015] -> '2007-2009, 2015'"""
    out, i = [], 0
    while i < len(years):
        j = i
        while j + 1 < len(years) and years[j + 1] == years[j] + 1:
            j += 1
        out.append(str(years[i]) if i == j else f"{years[i]}-{years[j]}")
        i = j + 1
    return ", ".join(out)


def _row(meta, tr, monthly, short, yw):
    r = dict(meta)
    r["short_record"] = short
    r["robust_call"] = tm.robust_call(tr, monthly=monthly, short_record=short)
    r["_raw_sens"] = r["robust_call"]
    r["_raw_yw"] = ("too short for climate inference" if short else repo_yw.yw_raw_call(yw))
    if tr:
        r.update(tr)
    r.update(yw)
    return r


def _slope_unit(unit):
    return f"{str(unit).replace('mm/year', 'mm/yr')} per decade"


def trend_table(tidy: pd.DataFrame, annual: pd.DataFrame) -> pd.DataFrame:
    rows_a, rows_m = [], []
    annual_all = annual
    ann = annual[(annual["period"] == "ANN") & (annual["year"] <= LAST_FULL_YEAR)]
    for (src, var, reg), g in ann.groupby(["source", "variable", "region"], sort=False):
        mon = tidy[(tidy.source == src) & (tidy.variable == var) & (tidy.region == reg)]
        exf = mon["flags"].str.split(";").apply(lambda f: bool(EXCLUDE_FROM_TRENDS & set(f)))
        excl_years = sorted(set(mon.date[exf].dt.year))
        g = g[~g.year.isin(excl_years)].sort_values("year")
        if g.empty:
            continue
        y0, y1 = int(g.year.min()), int(g.year.max())
        wins = [("full", y0, y1)] + [(f"{a}-{b}", a, b) for a, b in WINDOWS if y0 <= a and y1 >= b and (a, b) != (y0, y1)]
        if src in STATION_SOURCES and y0 <= 1981:
            wins.append(("1981-2019_station_window", 1981, 2019))
        for wname, a, b in wins:
            s = g[g.year.between(a, b)]
            short = (b - a + 1) < SHORT_RECORD_YEARS
            missing = sorted(set(range(a, b + 1)) - set(s.year) - set(excl_years))
            gappy = src in STATION_SOURCES and bool(missing) and not wname.startswith("1981-2019")
            if src == "grace":  # generic 12/12 annual = different convention from the GRACE headline method
                gappy = True
                wname = f"{wname}_gappy_annual12of12_convention"
            elif gappy:
                wname = f"{wname}_gappy"
            tr = tm.trend_stats(s.year.to_numpy(float), s.value.to_numpy(float))
            k, pp = pettitt(s.value.to_numpy(float))
            meta = dict(source=src, variable=var, region=reg, unit=g.unit.iloc[0], series="annual_ANN_12of12",
                        window=wname, win_start=a, win_end=b,
                        pettitt_change_year=(int(s.year.iloc[int(k) + 1]) if np.isfinite(k) else np.nan),
                        pettitt_p_exploratory=pp, missing_years=",".join(map(str, missing)),
                        excluded_years=",".join(map(str, excl_years)),
                        headline=(wname.startswith("1981-2019") if src in STATION_SOURCES
                                  else (wname == "full" and src != "grace")))
            if src in STATION_SOURCES:
                mw = mon[mon.date.dt.year.between(a, b)]
                meta["stations_min"] = float(mw.n_valid.min()); meta["stations_median"] = float(mw.n_valid.median())
            row = _row(meta, tr, False, short, repo_yw.yw_annual(s.year, s.value))
            if src == "grace":
                row["robust_call"] = (f"DIFFERENT CONVENTION (12/12 annual means): gappy, n={row.get('n')}, missing years "
                                      f"{_span(missing) or 'none'}; not robust/headline - use the GRACE headline-method row")
            elif gappy:
                row["robust_call"] = (f"gappy window: {len(missing)} missing years ({_span(missing)}), n={row.get('n')}; "
                                      "not treated as robust - use 1981-2019 station window")
            elif src in STATION_SOURCES and missing:
                row["robust_call"] = f"{row['robust_call']} [headline window; note missing years {_span(missing)}, n={row.get('n')}]"
            row["role"] = "different_convention" if src == "grace" else "finding"
            if (src, var) in FORCING_DIAGNOSTIC:
                row["role"] = "forcing_diagnostic"; row["headline"] = False
                row["robust_call"] = f"{FORCING_DIAG_REASON}. [raw call: {row['robust_call']}]"
            elif (src, var) in SAMPLING_DIAGNOSTIC:
                row["role"] = "sampling_diagnostic"; row["headline"] = False
                row["robust_call"] = ("SAMPLING DIAGNOSTIC (clear-sky days per month behind the LST composite; not a climate "
                                      f"finding). [raw call: {row['robust_call']}]")
            elif (src, var) in VI_VARS:
                row["window"] = f"{wname}_annual_includes_low_coverage_winter_months"
                row["role"] = "annual_includes_low_coverage_winter_months"; row["headline"] = False
                lowf = mon["flags"].str.contains("qc_low_coverage_lt50pct")
                nlow = int(lowf[mon.date.dt.year.between(a, b)].sum()); nall = int(lowf.sum())
                row["robust_call"] = (f"ANNUAL 12/12 includes {nlow} Jan/Feb months with <50% QC coverage (snow) in this "
                                      f"window ({nall} over the whole record); not "
                                      f"headline - see peak-season (JJA) and growing-season (Apr-Sep) rows. "
                                      f"[raw call: {row['robust_call']}]")
            rows_a.append(row)
        if (src, var) in VI_VARS:  # official seasonal VI rows, same 2001-LAST_FULL_YEAR years as the annual row
            for per, series, label in VI_SEASONS:
                sg = annual_all[(annual_all.source == src) & (annual_all.variable == var) & (annual_all.region == reg)
                                & (annual_all.period == per) & annual_all.year.between(max(y0, 2001), LAST_FULL_YEAR)]
                sg = sg.sort_values("year")
                if len(sg) < 3:
                    continue
                tr = tm.trend_stats(sg.year.to_numpy(float), sg.value.to_numpy(float))
                a, b = int(sg.year.min()), int(sg.year.max())
                meta = dict(source=src, variable=var, region=reg, unit=sg.unit.iloc[0], series=series,
                            window=f"{a}-{b}_{per}", win_start=a, win_end=b, headline=True, role=f"finding_{label}",
                            missing_years=",".join(map(str, sorted(set(range(a, b + 1)) - set(sg.year)))),
                            excluded_years="")
                row = _row(meta, tr, False, (b - a + 1) < SHORT_RECORD_YEARS, repo_yw.yw_annual(sg.year, sg.value))
                row["robust_call"] = f"{row['robust_call']} [{label}; {VI_SEASON_NOTE}]"
                rows_a.append(row)
        # monthly deseasonalised, full record through LAST_FULL_YEAR
        m = mon[(mon.date.dt.year <= LAST_FULL_YEAR) & np.isfinite(mon.anomaly) & ~mon.date.dt.year.isin(excl_years)]
        if len(m) >= 24:
            t = m.date.dt.year + (m.date.dt.month - 0.5) / 12
            span = t.max() - t.min()
            tr = tm.trend_stats(t.to_numpy(float), m.anomaly.to_numpy(float))
            yrs_m = set(m.date.dt.year)
            miss_m = sorted(set(range(min(yrs_m), max(yrs_m) + 1)) - yrs_m - set(excl_years))
            gappy_m = src in STATION_SOURCES and bool(miss_m)
            wm = "full_gappy" if gappy_m else "full"
            if src == "grace":
                wm = "full_generic_convention"
            meta = dict(source=src, variable=var, region=reg, unit=g.unit.iloc[0],
                        series=f"monthly_deseasonalised_{m.baseline.iloc[0]}", window=wm,
                        missing_years=",".join(map(str, miss_m)),
                        win_start=float(t.min()), win_end=float(t.max()), excluded_years=",".join(map(str, excl_years)),
                        headline=False)
            row = _row(meta, tr, True, span < SHORT_RECORD_YEARS, repo_yw.yw_monthly(m.date, m.anomaly))
            if gappy_m:
                row["robust_call"] = (f"gappy record: missing years {_span(miss_m)}; not treated as robust - "
                                      "use annual 1981-2019 station window")
            if src == "grace":
                row["robust_call"] = ("DIFFERENT CONVENTION (generic: record-mean climatology, month-start time, keeps "
                                      f"2002/2017/2018/2025 months), n={row.get('n')}; not headline - use the GRACE "
                                      "headline-method row")
            row["role"] = "different_convention" if src == "grace" else "finding"
            if (src, var) in FORCING_DIAGNOSTIC:
                row["role"] = "forcing_diagnostic"
            elif (src, var) in SAMPLING_DIAGNOSTIC:
                row["role"] = "sampling_diagnostic"
            rows_m.append(row)
        if src == "grace":  # GRACE HEADLINE: same code path as the blocking smoke test
            tr = grace_headline_trend(mon)
            yw = repo_yw.yw_on_anomalies(tr.pop("_t"), tr.pop("_y"), g.unit.iloc[0])
            meta = dict(source=src, variable=var, region=reg, unit=g.unit.iloc[0],
                        series="monthly_deseasonalised_grace_headline_method", window="headline_grace_method",
                        win_start=tr.pop("_t0"), win_end=tr.pop("_t1"), excluded_years="2002,2017,2018,2026",
                        missing_years="", headline=True, method=GRACE_METHOD_LABEL, role="finding")
            rows_m.append(_row(meta, tr, True, False, yw))
    # SENSITIVITY multiple testing (old v1.3 columns, renamed sens_*), then PRIMARY repo-YW (same families)
    tm.add_multiple_testing(rows_a, "hac1_p", "sens_hac1")
    tm.add_multiple_testing(rows_a, "mk_hr_p", "sens_mk_hr")
    tm.add_multiple_testing(rows_m, "hac3_p", "sens_hac3")
    tm.add_multiple_testing(rows_a, "yw_p", "yw")
    tm.add_multiple_testing(rows_m, "yw_p", "yw")
    df = pd.DataFrame(rows_a + rows_m)
    df["slope_unit"] = df["unit"].map(_slope_unit)
    ann_rows = ~df["series"].str.startswith("monthly")
    df["test_family"] = np.where(ann_rows, "annual", "monthly")
    # labels: the context text (diagnostic / gappy / convention / VI notes) is kept; only the raw call is swapped
    sens_call = df["robust_call"].astype(str)
    df["sensitivity_call_hac_hr"] = sens_call
    df["robust_call"] = [c.replace(o, n, 1) if o in c else c
                         for c, o, n in zip(sens_call, df["_raw_sens"].astype(str), df["_raw_yw"].astype(str))]
    df["yw_raw_call"] = df.pop("_raw_yw"); df["sensitivity_raw_call_hac_hr"] = df.pop("_raw_sens")
    df["yw_significant_raw"] = df["yw_p"] < repo_yw.ALPHA
    for kind in ("bonferroni", "bh"):
        df[f"mt_{kind}_pass"] = df.get(f"yw_{kind}_reject", False).fillna(False).astype(bool)
        a_pass = (df.get(f"sens_hac1_{kind}_reject", False).fillna(False).astype(bool)
                  & df.get(f"sens_mk_hr_{kind}_reject", False).fillna(False).astype(bool))
        m_pass = df.get(f"sens_hac3_{kind}_reject", False).fillna(False).astype(bool)
        df[f"sens_mt_{kind}_pass"] = np.where(ann_rows, a_pass, m_pass)
    df["yw_ols_neff_agree"] = (df["yw_p"] < 0.05) == (df["yw_ols_neff_p"] < 0.05)
    df["repo_trend_stats_md5"] = repo_yw.REPO_TS_MD5
    df["notes"] = ("Pettitt is exploratory and anti-conservative under autocorrelation; "
                   "same independence_group = not independent confirmation")
    return df
