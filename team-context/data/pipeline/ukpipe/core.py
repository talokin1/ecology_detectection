"""Common schema, unit conversion, spatial aggregation, temporal rules, flags."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .paths import global_data, ukraine_samples

PIPE = Path(__file__).resolve().parents[1]
SAMPLES = ukraine_samples()
GLOBAL = global_data()
VARS = yaml.safe_load((PIPE / "config" / "variables.yaml").read_text())

TIDY_COLS = ["source", "variable", "region", "date", "value", "unit", "n_valid", "n_effective_cells",
             "coverage_frac", "flags", "anomaly", "baseline", "independence_group"]

BASELINE = (1991, 2020)
MIN_BASELINE_YEARS = 20  # per calendar month, else record-mean climatology (labelled)
SHORT_RECORD_YEARS = 10
LAST_FULL_YEAR = 2025     # 2026 rows are partial for every source


def spec(source, variable):
    return VARS[source]["variables"][variable]


def days_in_month(dates: pd.Series | pd.DatetimeIndex) -> np.ndarray:
    return np.asarray(pd.DatetimeIndex(dates).days_in_month, dtype=float)


def convert(values, dates, sp: dict) -> np.ndarray:
    v = np.asarray(values, dtype=float)
    c = sp.get("conversion", "none")
    if c == "none":
        return v
    if c == "K_to_C":
        return v - 273.15
    if c == "scale":
        return v * float(sp["factor"])
    if c == "tenths":
        return v * 0.1
    d = days_in_month(dates)
    if c == "per_s_to_month":
        return v * 86400.0 * d
    if c == "per_day_to_month":
        return v * d
    if c == "per_hour_to_month":
        return v * 24.0 * d
    if c == "acc3h_to_month":
        return v * 8.0 * d
    raise ValueError(c)


def grid_aggregate(data: np.ndarray, frac: np.ndarray, area: np.ndarray, extra_w: np.ndarray | None = None,
                   region_area: float | None = None):
    """Area x fractional-overlap weighted mean over (t, y, x) with NaN for missing.

    Returns value, n_valid (cells with data and w>0), n_effective_cells (sum of overlap
    fractions of valid cells), coverage_frac = valid weighted area / TRUE region area (region_area,
    km²) so edge strips missing from centre-cut extracts and masked (sea/fill) cells count as
    uncovered; without region_area it falls back to valid weight / grid weight.
    """
    w = frac * area
    if extra_w is not None:
        w = w * extra_w
    sel = w > 0
    d = data[:, sel].astype(float)  # (t, k)
    ww = w[sel]
    fr = frac[sel]
    ok = np.isfinite(d)
    num = np.where(ok, d, 0.0) @ ww
    den = ok.astype(float) @ ww
    with np.errstate(invalid="ignore", divide="ignore"):
        val = np.where(den > 0, num / den, np.nan)
    tot = region_area if region_area else ww.sum()
    cov = np.clip(den / tot, 0, 1) if tot > 0 else np.zeros(len(val))
    return val, ok.sum(1), ok.astype(float) @ fr, cov


def make_tidy(source, variable, region, dates, raw_values, n_valid=None, n_eff=None, coverage=None,
              flags=None, unit=None, out_name=None, convert_units=True, sp=None, preaggregated=None):
    sp = sp or spec(source, variable)
    dates = pd.DatetimeIndex(pd.to_datetime(dates)).to_period("M").to_timestamp()
    vals = convert(raw_values, dates, sp) if convert_units else np.asarray(raw_values, float)
    n = len(vals)
    fl = [[] for _ in range(n)]
    lo, hi = (float(x) for x in sp.get("valid_range", [-np.inf, np.inf]))
    bad = np.isfinite(vals) & ((vals < lo) | (vals > hi))
    for i in np.where(bad)[0]:
        fl[i].append("out_of_range")
    vals = np.where(bad, np.nan, vals)
    if "start" in sp:
        early = dates < pd.Timestamp(sp["start"])
        vals = np.where(early, np.nan, vals)
    if flags is not None:
        for i, f in enumerate(flags):
            if f:
                fl[i].extend([x for x in str(f).split(";") if x])
    src = VARS[source]
    base_flags = [x for x in str(src.get("qc_flag", "")).split(";") if x]
    base_flags += [x for x in str(sp.get("qc_flag", "")).split(";") if x]
    if (src.get("preaggregated") if preaggregated is None else preaggregated):
        base_flags.append("preaggregated_bbox_mean_centre_weights")
    if src.get("coarse"):
        base_flags.append("coarse_cells_extend_beyond_region")
    for f in fl:
        f.extend(base_flags)
    df = pd.DataFrame({
        "source": source, "variable": out_name or sp.get("out_name", variable), "region": region,
        "date": dates, "value": vals, "unit": unit or sp["unit"],
        "n_valid": np.nan if n_valid is None else np.asarray(n_valid, float),
        "n_effective_cells": np.nan if n_eff is None else np.asarray(n_eff, float),
        "coverage_frac": np.nan if coverage is None else np.asarray(coverage, float),
        "flags": [";".join(dict.fromkeys(f)) for f in fl],
        "independence_group": sp.get("group", src.get("group", "")),
    })
    df = df.dropna(subset=["date"]).sort_values("date").drop_duplicates(["date"], keep="first")
    return finalize(df)


def _add_flag(df, mask, flag):
    mask = np.asarray(mask, bool)
    df.loc[mask, "flags"] = [(f + ";" + flag) if f else flag for f in df.loc[mask, "flags"]]


def finalize(df: pd.DataFrame) -> pd.DataFrame:
    """Deseasonalise, add partial-year / short-record / 5-sigma flags."""
    df = df.reset_index(drop=True)
    ok = np.isfinite(df["value"].to_numpy())
    yr = df["date"].dt.year.to_numpy(); mo = df["date"].dt.month.to_numpy()
    counts = pd.Series(ok).groupby(yr).sum()
    _add_flag(df, np.isin(yr, counts.index[counts < 12]), "partial_year")
    _add_flag(df, ~ok, "missing_value")
    if ok.any():
        span = (df["date"][ok].max() - df["date"][ok].min()).days / 365.25
        if span < SHORT_RECORD_YEARS:
            _add_flag(df, ok, "short_record")
    # climatology: 1991-2020 if every calendar month has >= MIN_BASELINE_YEARS values, else record mean
    inb = ok & (yr >= BASELINE[0]) & (yr <= BASELINE[1])
    nb = pd.Series(inb).groupby(mo).sum().reindex(range(1, 13), fill_value=0)
    v = df["value"]
    if (nb >= MIN_BASELINE_YEARS).all():
        clim = v[inb].groupby(mo[inb]).mean(); label = "1991-2020"
    else:
        clim = v[ok].groupby(mo[ok]).mean(); label = "record_mean"
    df["anomaly"] = v.to_numpy() - pd.Series(mo).map(clim).to_numpy()
    df["baseline"] = label
    a = df["anomaly"].to_numpy()
    fin = np.isfinite(a)
    if fin.sum() > 24:
        sd = np.nanstd(a[fin])
        if sd > 0:
            _add_flag(df, fin & (np.abs(a) > 5 * sd), "outlier_5sigma")
    return df[TIDY_COLS]


# monthly flags whose YEARS are dropped from every trend until the issue is checked; carried into annual/seasonal rows
TREND_EXCLUDE_FLAGS = {"airs_2025_bias_unverified"}


def annual_table(tidy: pd.DataFrame) -> pd.DataFrame:
    """Annual (12/12 months), seasonal (3/3, DJF year = Jan/Feb year) and Apr-Sep (AMJJAS, 6/6) aggregates."""
    out = []
    for (src, var, reg), g in tidy.groupby(["source", "variable", "region"], sort=False):
        sp_agg = "mean"
        try:
            sp_agg = _agg_for(src, var)
        except KeyError:
            pass
        unit = g["unit"].iloc[0]
        g = g[np.isfinite(g["value"])]
        if g.empty:
            continue
        yr = g["date"].dt.year.to_numpy(); mo = g["date"].dt.month.to_numpy()
        ex_year = {}
        has_ex = g["flags"].str.contains("|".join(TREND_EXCLUDE_FLAGS), regex=True).to_numpy()
        exf = np.full(len(g), "", dtype=object)
        if has_ex.any():
            exf[has_ex] = g["flags"][has_ex].str.split(";").apply(lambda f: ";".join(sorted(TREND_EXCLUDE_FLAGS & set(f)))).to_numpy()
        _sy = np.where(mo == 12, yr + 1, yr)  # seasonal (DJF) year
        _ss = np.select([np.isin(mo, [12, 1, 2]), np.isin(mo, [3, 4, 5]), np.isin(mo, [6, 7, 8])], ["DJF", "MAM", "JJA"], "SON")
        for y_, s_, f_ in zip(_sy, _ss, exf):
            if f_:
                ex_year.setdefault(("S", int(y_), str(s_)), set()).update(f_.split(";"))
        for y_, f_ in zip(yr, exf):
            if f_:
                ex_year.setdefault(("A", int(y_)), set()).update(f_.split(";"))
        f = (lambda x: x.sum()) if sp_agg == "sum" else (lambda x: x.mean())
        aunit = unit.replace("/month", "/year") if sp_agg == "sum" else unit
        ann = g.groupby(yr)["value"].agg(["count", "sum", "mean"])
        for y, r in ann.iterrows():
            if r["count"] == 12:
                out.append((src, var, reg, int(y), "ANN", r["sum"] if sp_agg == "sum" else r["mean"], aunit, 12,
                            ";".join(sorted(ex_year.get(("A", int(y)), set())))))
        seas_year = np.where(mo == 12, yr + 1, yr)
        seas = np.select([np.isin(mo, [12, 1, 2]), np.isin(mo, [3, 4, 5]), np.isin(mo, [6, 7, 8])], ["DJF", "MAM", "JJA"], "SON")
        sunit = unit.replace("/month", "/season") if sp_agg == "sum" else unit
        sg = g.assign(_sy=seas_year, _s=seas).groupby(["_sy", "_s"])["value"].agg(["count", "sum", "mean"])
        for (y, s), r in sg.iterrows():
            if r["count"] == 3:
                out.append((src, var, reg, int(y), s, r["sum"] if sp_agg == "sum" else r["mean"], sunit, 3,
                            ";".join(sorted(ex_year.get(("S", int(y), str(s)), set())))))
        # Apr-Sep "growing season" (6/6 months, calendar year) - added for growing-season VI (Critique v1.2)
        gu = unit.replace("/month", "/Apr-Sep") if sp_agg == "sum" else unit
        gs = g[(mo >= 4) & (mo <= 9)]
        if len(gs):
            gg = gs.groupby(gs["date"].dt.year)["value"].agg(["count", "sum", "mean"])
            for y, r in gg.iterrows():
                if r["count"] == 6:
                    out.append((src, var, reg, int(y), "AMJJAS", r["sum"] if sp_agg == "sum" else r["mean"], gu, 6,
                                ";".join(sorted(ex_year.get(("A", int(y)), set())))))
    cols = ["source", "variable", "region", "year", "period", "value", "unit", "n_months", "_ex"]
    df = pd.DataFrame(out, columns=cols)
    base = np.where(df["year"] > LAST_FULL_YEAR, "partial_year_check", "")
    df["flags"] = [";".join(x for x in (b, e) if x) for b, e in zip(base, df.pop("_ex"))]
    return df


_AGG_CACHE = {}


def _agg_for(src, var):
    if (src, var) in _AGG_CACHE:
        return _AGG_CACHE[(src, var)]
    vs = VARS[src]["variables"]
    for k, sp in vs.items():
        if sp.get("out_name", k) == var or k == var:
            _AGG_CACHE[(src, var)] = sp.get("agg", "mean")
            return _AGG_CACHE[(src, var)]
    if var.startswith("PRCP") or "precip" in var.lower():
        return "sum"
    raise KeyError(var)
