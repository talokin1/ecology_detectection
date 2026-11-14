"""The approved GRACE headline trend method (grace_findings.py), shared by trends.py and smoke_test.py
so the published headline and the blocking smoke check cannot diverge.

Monthly TWS -> anomaly vs a monthly climatology from COMPLETE (12/12) years only -> drop 2002, 2017, 2018, 2026
(partial / GRACE-GRACE-FO gap years) -> time = decimal year of the solution centre date (`time_center` in the
Researcher CSV) -> trend_methods.trend_stats (OLS + HAC/Hamed-Rao). Production weights = fractional overlap
(decided by the team lead via Thinker, 14 Nov 2026).
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from .paths import load_module, trend_methods_py, ukraine_samples

trend_stats = load_module(trend_methods_py(), "trend_methods_grace").trend_stats


def grace_csv():
    return ukraine_samples() / "grace" / "ukraine_tws_monthly.csv"
DROP_YEARS = (2002, 2017, 2018, 2026)
METHOD_LABEL = ("GRACE headline method: complete-year climatology, drop 2002/2017/2018/2026, time_center, "
                "monthly deseasonalised OLS")


def decimal_year(d: dt.date) -> float:  # same convention as grace_findings.py
    s = dt.date(d.year, 1, 1); e = dt.date(d.year + 1, 1, 1)
    return d.year + (d.toordinal() - s.toordinal() + 0.5) / (e.toordinal() - s.toordinal())


def grace_headline_trend(g: pd.DataFrame) -> dict:
    """g: tidy GRACE rows (date, value) for ONE region. Returns trend_stats dict (+ start/end decimal years)."""
    csv = pd.read_csv(grace_csv())
    csv["date"] = pd.to_datetime(csv["date"] + "-01")
    g = g[["date", "value"]].dropna(subset=["value"]).merge(csv[["date", "time_center"]], on="date", how="left")
    g["year"] = g.date.dt.year; g["month"] = g.date.dt.month
    cnt = g.groupby("year").size(); complete = cnt.index[cnt == 12]
    clim = g[g.year.isin(complete)].groupby("month")["value"].mean()
    d = g[~g.year.isin(DROP_YEARS)]
    t = np.array([decimal_year(dt.date.fromisoformat(x)) for x in d.time_center])
    y = (d.value - d.month.map(clim)).to_numpy()
    tr = trend_stats(t, y)
    tr["_t0"], tr["_t1"] = float(t.min()), float(t.max())
    tr["_t"], tr["_y"] = t, y  # exact inputs, so the repo Yue-Wang test sees the same anomalies/times
    return tr
