"""QC summary per variable + Crimea verification."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .core import PIPE, VARS
from .regions import load_polygon


def _gaps(valid: np.ndarray):
    runs, cur = [], 0
    for v in valid:
        if not v:
            cur += 1
        elif cur:
            runs.append(cur); cur = 0
    if cur:
        runs.append(cur)
    return len(runs), (max(runs) if runs else 0)


def qc_table(tidy: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (src, var, reg), g in tidy.groupby(["source", "variable", "region"], sort=False):
        g = g.sort_values("date")
        ok = np.isfinite(g["value"].to_numpy())
        if not ok.any():
            rows.append(dict(source=src, variable=var, region=reg, n_months_valid=0, issues="no valid data")); continue
        first, last = g["date"][ok].min(), g["date"][ok].max()
        span = g[(g.date >= first) & (g.date <= last)]
        sok = np.isfinite(span["value"].to_numpy())
        n_exp = (last.year - first.year) * 12 + last.month - first.month + 1
        official_gap = span["flags"].str.contains("missing_month_official|grace_gracefo_gap").to_numpy() & ~sok
        ngap, maxgap = _gaps(sok) if len(span) == n_exp else _gaps(np.r_[sok, np.zeros(n_exp - len(span), bool)])
        fl = pd.Series(";".join(g["flags"]).split(";"))
        fl = fl[fl != ""].value_counts()
        sp = {}
        for k, v in VARS.get(src, {}).get("variables", {}).items():
            if v.get("out_name", k) == var or k == var or var.startswith(k):
                sp = v; break
        gv = g[ok]
        yrs = gv.date.dt.year.value_counts()
        rows.append(dict(
            source=src, variable=var, region=reg, unit=g["unit"].iloc[0],
            raw_unit=sp.get("raw_unit", ""), conversion=sp.get("conversion", ""),
            first=first.strftime("%Y-%m"), last=last.strftime("%Y-%m"),
            n_months_expected=int(n_exp), n_months_valid=int(sok.sum()),
            pct_valid_raw=round(100 * sok.sum() / n_exp, 2),
            pct_valid_gap_excluded=round(100 * sok.sum() / max(n_exp - official_gap.sum(), 1), 2),
            n_gaps=int(ngap), longest_gap_months=int(maxgap),
            complete_years=int((yrs == 12).sum()), partial_years=int((yrs < 12).sum()),
            min_coverage_frac=float(np.nanmin(gv["coverage_frac"])) if gv["coverage_frac"].notna().any() else np.nan,
            median_coverage_frac=float(np.nanmedian(gv["coverage_frac"])) if gv["coverage_frac"].notna().any() else np.nan,
            min_n_valid=float(np.nanmin(gv["n_valid"])) if gv["n_valid"].notna().any() else np.nan,
            median_n_effective_cells=float(np.nanmedian(gv["n_effective_cells"])) if gv["n_effective_cells"].notna().any() else np.nan,
            baseline=g["baseline"].iloc[0], independence_group=g["independence_group"].iloc[0],
            flag_counts="; ".join(f"{k}={v}" for k, v in fl.items()),
        ))
    return pd.DataFrame(rows)


def crimea_check() -> dict:
    """Verify how the Natural Earth files assign Crimea (do not assume)."""
    import shapely
    from shapely.geometry import Point
    nd = PIPE / "data" / "raw_aux" / "natural_earth"
    de_facto = load_polygon(nd / "ne_10m_admin_0_countries" / "ne_10m_admin_0_countries.shp", "UKR")
    ukr_pov = load_polygon(nd / "ne_10m_admin_0_countries_ukr" / "ne_10m_admin_0_countries_ukr.shp", "UKR")
    rus_def = load_polygon(nd / "ne_10m_admin_0_countries" / "ne_10m_admin_0_countries.shp", "RUS")
    pts = {"Simferopol": (34.10, 44.95), "Sevastopol": (33.52, 44.60), "Kerch": (36.47, 45.36),
           "Kyiv": (30.52, 50.45), "Donetsk": (37.80, 48.00), "Luhansk": (39.31, 48.57)}
    memb = {k: dict(default_UKR=bool(de_facto.contains(Point(*v))), default_RUS=bool(rus_def.contains(Point(*v))),
                    ukr_pov_UKR=bool(ukr_pov.contains(Point(*v)))) for k, v in pts.items()}
    diff = shapely.difference(ukr_pov, de_facto)
    lat0 = np.deg2rad(45.3)
    km2 = lambda g: shapely.area(g) * (111.32 ** 2) * np.cos(lat0)  # rough, for reporting only
    def eq_area(g):
        # better area: equal-area via sin(lat) scaling of coordinates
        def tf(c):
            c = np.asarray(c, float)
            return np.c_[np.deg2rad(c[:, 0]) * 6371.0, np.sin(np.deg2rad(c[:, 1])) * 6371.0]
        return float(shapely.area(shapely.transform(g, tf)))
    return dict(
        ne_version=(nd / "ne_10m_admin_0_countries" / "ne_10m_admin_0_countries.VERSION.txt").read_text().strip(),
        membership=memb,
        area_km2_default_UKR=round(eq_area(de_facto)), area_km2_ukr_pov_UKR=round(eq_area(ukr_pov)),
        area_km2_difference=round(eq_area(diff)), difference_bounds=[round(x, 3) for x in diff.bounds],
        default_bounds=[round(x, 3) for x in de_facto.bounds], ukr_pov_bounds=[round(x, 3) for x in ukr_pov.bounds],
        area_km2_rough_difference=round(float(km2(diff))),
    )
