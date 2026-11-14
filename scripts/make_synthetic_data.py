"""Generate SYNTHETIC demo data for the web app, in the exact JSON format of the real pipeline.

The input series are invented (trend fields + autocorrelated noise, shaped like NASA POWER
monthly data). Everything computed FROM them uses the project's reference module
`trend_stats.py` (Sen, Mann-Kendall Yue-Wang, OLS n_eff, BH FDR, years to detection), so the
numbers on screen are internally consistent. Every file carries `provenance.synthetic = true`
and the app shows a "synthetic data" banner. Synthetic numbers must never be quoted as results.

Outputs (frontend/public/data/):
  index.json                       cases, regions (with outlines), variables
  catalog.json                     all catalog variables with plain-language text and status
  map/<variable>.json              1-degree global trend grid + FDR significance
  analysis/<region>__<variable>.json
  compare/<regionA>__<regionB>__<variable>.json
  validation.json                  Monte-Carlo false-alarm table (real, from validate_type1.py)

Usage (from the repo root):
  python scripts/make_synthetic_data.py [--seed 7] [--runs 300]

SI-assisted (Claude, Anthropic).
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import math
import sys
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy import ndimage, stats
from shapely import contains_xy
from shapely.geometry import shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".claude" / "skills" / "trend-stats" / "scripts"))
import trend_stats as ts  # noqa: E402

OUT = ROOT / "frontend" / "public" / "data"
SCHEMA_VERSION = "0.1.0"
Y0, Y1 = 1981, 2024
BASELINE = ("1981-01-01", "2010-12-31")
FDR_MAP_Q = 0.05
FDR_INSIGHT_Q = 0.10
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"]
SEASONS = [("DJF", "Winter", [12, 1, 2]), ("MAM", "Spring", [3, 4, 5]),
           ("JJA", "Summer", [6, 7, 8]), ("SON", "Autumn", [9, 10, 11])]
LEVEL_RANK = {"insufficient": -1, "none": 0, "weak": 1, "moderate": 2, "strong": 3}
MINUS = "−"

# --------------------------------------------------------------------------- variables
VARIABLES = {
    "t2m": {
        "catalog_id": "air_temperature_power", "name": "Air temperature",
        "long_name": "Air temperature near the surface", "parameter": "T2M",
        "units": "°C", "rate_units": "°C per decade", "axis_label": "Temperature anomaly (°C)",
        "raw_label": "Monthly mean temperature (°C)", "palette": "RdBu",
        "words": {"neg": "cooling", "pos": "warming"},
        "up": "getting warmer", "down": "getting cooler", "noun": "warming", "noun_down": "cooling",
        "rate_decimals": 2, "total_decimals": 1, "series_decimals": 2, "percent": False,
        "topic": "temperature", "land_only": False,
        "extreme": {"kind": "hot_months", "tail": "upper", "label": "Very hot months",
                    "threshold_text": "hotter than 9 in 10 months of 1981–2010"},
        "month_profile": np.array([1.45, 1.35, 1.2, 1.0, 0.85, 0.8, 0.85, 0.9, 0.9, 1.0, 1.15, 1.4]),
        "phi": 0.35,
    },
    "precip": {
        "catalog_id": "precipitation_power", "name": "Precipitation",
        "long_name": "Precipitation (rain and snow)", "parameter": "PRECTOTCORR",
        "units": "mm/day", "rate_units": "mm/day per decade", "axis_label": "Precipitation anomaly (mm/day)",
        "raw_label": "Monthly precipitation (mm/day)", "palette": "BrBG",
        "words": {"neg": "drier", "pos": "wetter"},
        "up": "getting wetter", "down": "getting drier", "noun": "wetting", "noun_down": "drying",
        "rate_decimals": 2, "total_decimals": 2, "series_decimals": 2, "percent": True,
        "topic": "water", "land_only": False,
        "extreme": {"kind": "dry_months", "tail": "lower", "label": "Very dry months",
                    "threshold_text": "drier than 9 in 10 months of 1981–2010"},
        "month_profile": np.array([1.3, 1.25, 1.1, 0.95, 0.85, 0.8, 0.8, 0.85, 0.95, 1.05, 1.2, 1.3]),
        "phi": 0.1,
    },
    "soil": {
        "catalog_id": "root_zone_soil_wetness_power", "name": "Soil wetness",
        "long_name": "Root-zone soil wetness", "parameter": "GWETROOT",
        "units": "%", "rate_units": "points per decade", "axis_label": "Soil wetness anomaly (points)",
        "raw_label": "Root-zone soil wetness (% of saturation)", "palette": "BrBG",
        "words": {"neg": "drier", "pos": "wetter"},
        "up": "getting wetter", "down": "getting drier", "noun": "wetting", "noun_down": "drying",
        "rate_decimals": 1, "total_decimals": 1, "series_decimals": 1, "percent": False,
        "topic": "water", "land_only": True,
        "extreme": {"kind": "dry_months", "tail": "lower", "label": "Very dry months",
                    "threshold_text": "drier than 9 in 10 months of 1981–2010"},
        "month_profile": np.array([0.4, 0.4, 0.55, 0.75, 0.95, 1.3, 1.7, 1.85, 1.55, 1.05, 0.6, 0.4]),
        "phi": 0.8,
    },
}

CASES = [
    {"id": "01", "slug": "grandmas-drought", "title": "Grandma's drought",
     "question": "Is the soil in southern Ukraine drying out?",
     "teaser": "Grandma says her garden needs more watering every year. Is she right?",
     "variable_id": "soil", "region_id": "south_ukraine"},
    {"id": "02", "slug": "ukraine-warming", "title": "Is Ukraine getting warmer?",
     "question": "Is Ukraine getting warmer, and in which season the most?",
     "teaser": "Winters without snow, summers that do not end. What do 44 years of data say?",
     "variable_id": "t2m", "region_id": "ukraine"},
    {"id": "03", "slug": "same-rain-opposite-ways", "title": "Same rain, opposite ways",
     "question": "Is the north of Europe getting wetter while the south dries out?",
     "teaser": "One continent, two directions. Do the trends really differ?",
     "variable_id": "precip", "region_id": "south_europe", "compare_region_id": "north_europe"},
]

# Topic ids are the viz filter ids; the topic of each variable is read from
# data/catalog/variables.yaml (merge plan v2, M2). The catalog may still carry the data branch's
# older labels, so they are mapped here; anything unknown falls into `other`.
TOPIC_LABELS = {"temperature": "Temperature", "water": "Water", "snow_ice": "Snow and ice",
                "air": "Air quality", "vegetation": "Vegetation", "sunlight": "Sunlight",
                "other": "Ocean"}
TOPIC_ALIASES = {"snow and ice": "snow_ice", "sunlight and clouds": "sunlight", "ocean": "other"}


def viz_topic(label) -> str:
    t = str(label or "").strip().lower()
    t = TOPIC_ALIASES.get(t, t)
    return t if t in TOPIC_LABELS else "other"


PLACE_TYPES = {
    "farmland": ("Farmland and steppe", {"agriculture", "steppe", "aquifer"}),
    "city": ("Cities", {"city", "industrial"}),
    "desert": ("Deserts", {"desert"}),
    "forest": ("Forests", {"forest", "rainforest", "boreal"}),
    "cold": ("Cold places", {"arctic", "polar", "glacier"}),
    "mountain": ("Mountains", {"mountain"}),
    "coast": ("Coasts and ocean", {"ocean", "estuary", "coast", "river_basin", "mediterranean"}),
    "tropics": ("Tropics", {"tropics", "monsoon", "rainforest"}),
}


# --------------------------------------------------------------------------- helpers
def fmt(x: float, d: int, sign: bool = True) -> str:
    """Display string with a real minus sign; rounding happens here, never in the browser."""
    if x is None or not np.isfinite(x):
        return "n/a"
    r = round(float(x), d)
    if r == 0:
        r = 0.0
    s = f"{abs(r):,.{d}f}"
    if r < 0:
        return MINUS + s
    return ("+" + s) if sign and r > 0 else s


def rnd(a, d: int):
    """Round an array for JSON; NaN -> None."""
    a = np.asarray(a, dtype=float)
    return [None if not np.isfinite(v) else round(float(v), d) for v in a]


def gauss(lat, lon, lat0, lon0, slat, slon):
    dlon = (lon - lon0 + 180) % 360 - 180
    return np.exp(-(((lat - lat0) / slat) ** 2) - ((dlon / slon) ** 2))


def smooth_noise(rng, shape_, sigma):
    f = ndimage.gaussian_filter(rng.normal(size=shape_), sigma=sigma, mode=("nearest", "wrap"))
    return (f - f.mean()) / f.std()


def ar1(n, phi, rng):
    e = rng.normal(0, 1, n)
    x = np.empty(n)
    x[0] = e[0] / math.sqrt(1 - phi ** 2)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x * math.sqrt(1 - phi ** 2)


def excludes_zero(ci) -> bool:
    return (ci[0] > 0 and ci[1] > 0) or (ci[0] < 0 and ci[1] < 0)


def level_from_cis(ci90, ci95, ci99) -> str:
    if excludes_zero(ci99):
        return "strong"
    if excludes_zero(ci95):
        return "moderate"
    if excludes_zero(ci90):
        return "weak"
    return "none"


def level_from_p(p: float) -> str:
    return "strong" if p < 0.01 else "moderate" if p < 0.05 else "weak" if p < 0.10 else "none"


def weaker(a: str, b: str) -> str:
    return a if LEVEL_RANK[a] <= LEVEL_RANK[b] else b


def p_text(p: float) -> str:
    if p < 0.001:
        return "p < 0.001"
    if p < 0.01:
        return f"p = {p:.3f}"
    return f"p = {p:.2f}"


def times_word(r: float) -> str | None:
    if r >= 3.5:
        return "more than three times as fast as"
    if r >= 2.5:
        return "about three times as fast as"
    if r >= 1.6:
        return "about twice as fast as"
    if r >= 1.3:
        return "noticeably faster than"
    return None


def compass(lon1, lat1, lon2, lat2) -> str:
    y = math.sin(math.radians(lon2 - lon1)) * math.cos(math.radians(lat2))
    x = (math.cos(math.radians(lat1)) * math.sin(math.radians(lat2))
         - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(math.radians(lon2 - lon1)))
    b = (math.degrees(math.atan2(y, x)) + 360) % 360
    return ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"][
        int((b + 22.5) // 45) % 8]


def haversine_km(lon1, lat1, lon2, lat2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(a))


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


# --------------------------------------------------------------------------- synthetic fields
class World:
    def __init__(self, rng):
        self.lat = np.arange(-89.5, 90, 1.0)
        self.lon = np.arange(-179.5, 180, 1.0)
        self.LON, self.LAT = np.meshgrid(self.lon, self.lat)
        land = json.loads((ROOT / "frontend/public/basemap/land.geojson").read_text(encoding="utf-8"))
        land_geom = unary_union([shape(f["geometry"]) for f in land["features"]])
        self.land = contains_xy(land_geom, self.LON, self.LAT)
        self.rng = rng
        self.fields = {v: self._field(v) for v in VARIABLES}

    def _field(self, var):
        """True trend per decade, annual noise std and climatology for each grid cell."""
        lat, lon, land, rng = self.LAT, self.LON, self.land, self.rng
        rough = smooth_noise(rng, lat.shape, 6)
        if var == "t2m":
            trend = np.where(land, 0.29, 0.14)
            trend = trend + 0.55 * np.clip((lat - 55) / 30, 0, 1) ** 1.3
            trend = trend + 0.16 * gauss(lat, lon, 50, 32, 9, 22)          # eastern Europe
            trend = trend - 0.38 * gauss(lat, lon, 55, -35, 7, 14)         # North Atlantic cold blob
            trend = trend - 0.10 * gauss(lat, lon, -60, 0, 8, 400)         # Southern Ocean
            trend = trend + 0.06 * rough
            sd = np.where(land, 0.42, 0.2) + 0.5 * np.clip((np.abs(lat) - 40) / 40, 0, 1)
            clim = 28 - 0.55 * np.clip(np.abs(lat) - 12, 0, None)
        elif var == "precip":
            clim = (0.7 + 6.5 * np.exp(-(((lat - 6) / 9) ** 2))
                    + 2.4 * np.exp(-(((np.abs(lat) - 50) / 14) ** 2)))
            clim = np.where(land & (np.abs(lat) > 14) & (np.abs(lat) < 33), clim * 0.35, clim)
            pct = (5.0 * np.clip((lat - 50) / 14, 0, 1)
                   - 7.0 * gauss(lat, lon, 40, 6, 7, 26)                   # Mediterranean
                   - 4.0 * gauss(lat, lon, 34, -112, 7, 12)                # US south-west
                   + 6.0 * gauss(lat, lon, 14, 5, 4, 30)                   # Sahel recovery
                   - 3.5 * gauss(lat, lon, -24, 25, 7, 14)                 # southern Africa
                   - 2.5 * gauss(lat, lon, 47, 33, 4, 9)                   # Black Sea steppe
                   + 1.6 * rough)
            trend = clim * pct / 100
            sd = clim * np.where(land, 0.11, 0.07)
        else:  # soil wetness, %
            pc = (0.7 + 6.5 * np.exp(-(((lat - 6) / 9) ** 2)) + 2.4 * np.exp(-(((np.abs(lat) - 50) / 14) ** 2)))
            pc = np.where((np.abs(lat) > 14) & (np.abs(lat) < 33), pc * 0.35, pc)
            clim = 20 + 60 * pc / (pc + 2.5)
            trend = (-1.7 * gauss(lat, lon, 40, 10, 7, 20)                 # Mediterranean
                     - 1.55 * gauss(lat, lon, 46.6, 33, 3.2, 8)            # southern Ukraine steppe
                     + 0.9 * np.clip((lat - 55) / 12, 0, 1) * gauss(lat, lon, 62, 20, 12, 40)
                     + 1.1 * gauss(lat, lon, 14, 5, 4, 30)                 # Sahel
                     - 0.45 * gauss(lat, lon, 38, -99, 6, 10)              # Great Plains
                     - 0.7 * gauss(lat, lon, -25, 135, 10, 20)             # Australia
                     + 0.32 * rough)
            sd = np.full(lat.shape, 2.0)
            greenland = (lat > 59.5) & (lon > -74) & (lon < -11) & ~((lat < 67) & (lon > -25))  # not Iceland
            ice = (lat < -60) | greenland  # ice sheets have no meaningful soil wetness
            land = land & ~ice
            trend = np.where(land, trend, np.nan)
            sd = np.where(land, sd, np.nan)
            clim = np.where(land, clim, np.nan)
        return {"trend": trend, "sd": sd, "clim": clim}


def map_layer(world: World, var: str, rng) -> tuple[dict, dict]:
    """Per-cell Sen slope and Yue-Wang MK on annual means, then BH FDR across cells."""
    f = world.fields[var]
    years = np.arange(Y0, Y1 + 1)
    n = years.size
    tc = (years - years.mean()) / 10.0
    k_modes = 16
    modes = np.stack([smooth_noise(rng, world.LAT.shape, 7) for _ in range(k_modes)])
    amps = np.stack([ar1(n, 0.3, rng) for _ in range(k_modes)])
    coherent = np.tensordot(amps.T, modes, axes=1) / math.sqrt(k_modes)       # (n, lat, lon)
    local = rng.normal(size=(n,) + world.LAT.shape)
    noise = (math.sqrt(0.88) * coherent + math.sqrt(0.12) * local) * f["sd"][None]
    series = f["trend"][None] * tc[:, None, None] + noise                      # (n, lat, lon)
    Y = series.reshape(n, -1).T                                                 # (cells, n)

    valid = np.isfinite(Y).all(axis=1)
    slope = np.full(Y.shape[0], np.nan)
    pval = np.full(Y.shape[0], np.nan)
    i, j = np.triu_indices(n, 1)
    dt_ = (j - i).astype(float)
    var0 = n * (n - 1) * (2 * n + 5) / 18.0
    kk = np.arange(1, n)
    idx = np.flatnonzero(valid)
    for c0 in range(0, idx.size, 4000):
        sel = idx[c0:c0 + 4000]
        y = Y[sel]
        d = y[:, j] - y[:, i]
        s = np.sign(d).sum(axis=1)
        sen = np.median(d / dt_, axis=1)                                        # per year
        detr = y - sen[:, None] * np.arange(n)[None]
        a = detr - detr.mean(axis=1, keepdims=True)
        r1 = np.clip((a[:, :-1] * a[:, 1:]).sum(1) / (a * a).sum(1), 0, None)
        eta = 1 + 2 * ((1 - kk / n)[None] * r1[:, None] ** kk[None]).sum(1)
        z = (s - np.sign(s)) / np.sqrt(var0 * eta)
        slope[sel] = sen * 10
        pval[sel] = 2 * stats.norm.sf(np.abs(z))
    sig, _ = ts.fdr_bh(pval, q=FDR_MAP_Q)

    spec = VARIABLES[var]
    finite = np.abs(slope[np.isfinite(slope)])
    raw_lim = float(np.percentile(finite, 98))
    nice = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0]
    limit = next(v for v in nice if v >= raw_lim)
    d = spec["rate_decimals"] + (1 if var == "precip" else 0)
    layer = {
        "schema_version": SCHEMA_VERSION,
        "variable_id": var,
        "period": {"start": f"{Y0}-01", "end": f"{Y1}-12"},
        "grid": {"lat0": -89.5, "lon0": -179.5, "dlat": 1.0, "dlon": 1.0, "nlat": 180, "nlon": 360,
                 "order": "row-major from south to north, west to east"},
        "slope_per_decade": rnd(slope, d),
        "significant": [int(v) for v in sig],
        "palette": spec["palette"],
        "limit": limit,
        "bins": 10,
        "units_label": spec["rate_units"],
        "words": spec["words"],
        "fdr_q": FDR_MAP_Q,
        "caption": (f"SYNTHETIC demo field shaped like NASA POWER {spec['parameter']} · {Y0}–{Y1} · "
                    "Sen's slope of annual means per 1° cell; full colour = trend unlikely to be chance "
                    f"(Mann-Kendall with autocorrelation correction, false discovery rate q = {FDR_MAP_Q})."),
        "provenance": provenance(spec, "map"),
    }
    cells = {"slope": slope.reshape(world.LAT.shape), "sig": sig.reshape(world.LAT.shape)}
    return layer, cells


def provenance(spec: dict, what: str) -> dict:
    return {
        "dataset": f"SYNTHETIC — shaped like NASA POWER monthly {spec['parameter']}",
        "version": None, "doi": None,
        "landing_page": "https://power.larc.nasa.gov/",
        "accessed": dt.date.today().isoformat(),
        "processing": [
            "synthetic trend field + autocorrelated noise (scripts/make_synthetic_data.py)",
            "statistics: trend_stats.py (Sen, Mann-Kendall Yue-Wang, OLS n_eff, BH FDR)",
        ] + (["per-cell annual means, BH FDR across cells"] if what == "map" else
             ["cos(latitude)-weighted regional mean, monthly anomalies"]),
        "synthetic": True,
    }


# --------------------------------------------------------------------------- regional series
def region_mask(world: World, geom) -> np.ndarray:
    m = contains_xy(geom, world.LON, world.LAT)
    if m.sum() < 3:  # tiny region: take the cells whose centre is within 1 degree
        m = contains_xy(geom.buffer(0.75), world.LON, world.LAT)
    return m


def regional_series(world: World, var: str, mask: np.ndarray, centroid, rng):
    spec, f = VARIABLES[var], world.fields[var]
    w = np.cos(np.deg2rad(world.LAT)) * mask
    if spec["land_only"]:
        w = w * world.land
    w = w / w.sum()
    trend_dec = float(np.nansum(f["trend"] * w))
    sd_ann = 0.85 * float(np.nansum(f["sd"] * w))  # a regional mean is less noisy than one cell
    clim_mean = float(np.nansum(f["clim"] * w))

    dates = np.arange(np.datetime64(f"{Y0}-01"), np.datetime64(f"{Y1 + 1}-01"), dtype="datetime64[M]")
    months = dates.astype(int) % 12
    t = (dates.astype(int) / 12.0) + 1970
    tc = (t - t.mean()) / 10.0
    profile = spec["month_profile"] / spec["month_profile"].mean()
    phi = spec["phi"]
    # monthly noise std chosen so that annual means have roughly sd_ann
    sd_m = sd_ann * math.sqrt(12 / ((1 + phi) / (1 - phi)))
    noise = ar1(dates.size, phi, rng) * sd_m
    anom_true = trend_dec * profile[months] * tc + noise

    lat = centroid[1]
    if var == "t2m":
        mean = float(np.nansum(f["clim"] * w))
        amp = 1.5 + 0.32 * max(0.0, abs(lat) - 8)
        phase = 6 if lat >= 0 else 0
        cycle = mean + amp * np.cos(2 * np.pi * (months - phase) / 12)
        raw = cycle + anom_true
    elif var == "precip":
        peak = 11 if 34 < lat < 46 and centroid[0] < 30 else 7 if lat > 0 else 0
        amp = 0.9 if abs(lat) < 20 else 0.35
        cycle = clim_mean * (1 + amp * np.cos(2 * np.pi * (months - peak) / 12))
        raw = np.maximum(0.0, cycle + anom_true)
    else:
        cycle = clim_mean + 9 * np.cos(2 * np.pi * (months - 3) / 12)
        raw = np.clip(cycle + anom_true, 2, 98)
    day_dates = dates.astype("datetime64[D]")
    return day_dates, raw


def seasonal_series(dates, anom, months_wanted):
    """One mean per year for the given calendar months; December counts towards the next winter."""
    d = dates.astype("datetime64[M]").astype(int)
    years = d // 12 + 1970
    months = d % 12 + 1
    wraps = 12 in months_wanted and 1 in months_wanted
    season_year = np.where((months == 12) & wraps, years + 1, years)
    out_y, out_v = [], []
    for y in range(Y0, Y1 + 1):
        sel = (season_year == y) & np.isin(months, months_wanted)
        if sel.sum() == len(months_wanted) and np.isfinite(anom[sel]).all():
            out_y.append(y)
            out_v.append(float(np.mean(anom[sel])))
    return np.array(out_y), np.array(out_v)


def annual_trend(years, values):
    """Sen + MK Yue-Wang for one value per year (no deseasonalising)."""
    dates = np.array([np.datetime64(f"{y}-07-01") for y in years])
    return ts.analyze_series(dates, values, obs_per_year=1, deseasonalize_monthly=False)


def analyse(world, var, region, cells, rng):
    spec = VARIABLES[var]
    dates, raw = regional_series(world, var, region["mask"], region["centroid"], rng)
    res = ts.analyze_series(dates, raw, units=spec["rate_units"], variable_name=spec["long_name"])
    anom, _ = ts.deseasonalize(dates, raw)
    t = ts.decimal_years(dates)
    mk = ts.mann_kendall(t, anom, method="yue_wang")
    ci = {a: ts.sens_slope(t, anom, alpha=a, var_s=mk["var_s"]) for a in (0.10, 0.05, 0.01)}
    sen = ci[0.05]
    per_dec = sen["slope"] * 10
    ci90, ci95, ci99 = ([c * 10 for c in ci[a]["ci"]] for a in (0.10, 0.05, 0.01))
    span = float(t.max() - t.min())
    record_years = res["record_years"]

    mk_level = level_from_cis(ci90, ci95, ci99)
    ols_level = level_from_p(res["ols"]["p"])
    level = weaker(mk_level, ols_level) if record_years >= 10 else "insufficient"
    disagree = mk_level != ols_level
    direction = "up" if per_dec > 0 else "down" if per_dec < 0 else "flat"

    rd, td, sd_ = spec["rate_decimals"], spec["total_decimals"], spec["series_decimals"]
    total = sen["slope"] * span
    total_ci = [ci95[0] / 10 * span, ci95[1] / 10 * span]
    mean_level = float(np.nanmean(raw))
    pct_total = 100 * total / mean_level if spec["percent"] else None

    # --- headline and sentence (templates; the app shows them verbatim)
    words = spec["up"] if direction == "up" else spec["down"]
    headline = {
        "strong": f"Strong evidence: {words}", "moderate": f"Evidence: {words}",
        "weak": "A hint, not proof", "none": "No clear trend yet", "insufficient": "Not enough data to judge",
    }[level]
    unit_word_ = spec["units"] if spec["units"] != "%" else "points"
    if level in ("strong", "moderate"):
        moved = "rose" if total > 0 else "dropped"
        sure = "very unlikely" if level == "strong" else "unlikely"
        sentence = (f"Since {Y0}, {spec['long_name'].lower()} in {region['name']} {moved} by about "
                    f"{fmt(abs(total), td, sign=False)} {unit_word_}, and the change is {sure} to be chance.")
    elif level == "weak":
        sentence = (f"{spec['long_name']} in {region['name']} may be {words}, but the evidence is not "
                    "strong enough to rule out chance.")
    else:
        sentence = (f"{spec['long_name']} in {region['name']} moves up and down from year to year, "
                    "and so far there is no steady drift we can tell apart from those swings.")
    how_sure = (f"Mann-Kendall test with a correction for month-to-month memory: {p_text(mk['p'])} · "
                f"{res['n']} months · second test (regression): {p_text(res['ols']['p'])}")

    # --- trend line and 95% fan in anomaly space
    x0, x1 = str(dates[0])[:7], str(dates[-1])[:7]
    tm = float(np.median(t))
    pivot = sen["intercept"] + sen["slope"] * tm
    lo, hi = ci95[0] / 10, ci95[1] / 10
    xs = [t.min(), tm, t.max()]
    lower = [min(pivot + lo * (x - tm), pivot + hi * (x - tm)) for x in xs]
    upper = [max(pivot + lo * (x - tm), pivot + hi * (x - tm)) for x in xs]
    mid_month = np.datetime64(f"{int(tm)}-01") + np.timedelta64(int(round((tm % 1) * 12)), "M")

    # --- years to detection
    ytd = None
    if level in ("none", "weak"):
        more = res["years_to_detect"] - record_years
        if not np.isfinite(more) or abs(total) < 0.05 * res["noise"]["std"]:
            ytd = {"value": None, "text": "The change is so small that we cannot say when it would become clear."}
        elif more > 50:
            ytd = {"value": None, "text": "The change is small next to natural swings."}
        else:
            v = max(5, int(5 * round(max(more, 0) / 5)))
            ytd = {"value": v, "text": f"If the current rate held, about {v} more years of data would be needed to tell."}

    # --- annual means and signal vs noise (M4)
    yrs = np.arange(Y0, Y1 + 1)
    ann = np.array([np.nanmean(anom[(dates >= np.datetime64(f"{y}-01-01")) & (dates < np.datetime64(f"{y + 1}-01-01"))])
                    for y in yrs])
    ann_detr = ann - (sen["intercept"] + sen["slope"] * (yrs + 0.5))
    swing = float(np.std(ann_detr, ddof=1))
    ratio_now = abs(total) / swing if swing > 0 else None
    emergence = None
    if level in ("strong", "moderate") and ratio_now and ratio_now > 1:
        emergence = int(math.ceil(Y0 + swing / abs(sen["slope"])))

    # --- seasons (S6) and months (M1)
    family = []
    seasons = []
    for code, label, ms in SEASONS:
        sy, sv = seasonal_series(dates, anom, ms)
        r = annual_trend(sy, sv)
        p = r["mk"]["p"]
        seasons.append({"season": code, "label": label,
                        "sen_per_decade": round(r["sen_slope_per_decade"], rd + 1),
                        "ci95": [round(c, rd + 1) for c in r["sen_ci95_per_decade"]],
                        "p": round(p, 4), "display": fmt(r["sen_slope_per_decade"], rd)})
        family.append(("season", code, p))
    monthly = []
    for m in range(1, 13):
        sy, sv = seasonal_series(dates, anom, [m])
        r = annual_trend(sy, sv)
        monthly.append({"month": m, "label": MONTH_NAMES[m - 1][:3],
                        "sen_per_decade": round(r["sen_slope_per_decade"], rd + 1),
                        "ci95": [round(c, rd + 1) for c in r["sen_ci95_per_decade"]],
                        "p": round(r["mk"]["p"], 4)})
        family.append(("month", m, r["mk"]["p"]))

    # --- extremes (S7)
    ex = spec["extreme"]
    base = (dates >= np.datetime64(BASELINE[0])) & (dates <= np.datetime64(BASELINE[1]))
    thr = np.percentile(anom[base], 90 if ex["tail"] == "upper" else 10)
    hit = anom > thr if ex["tail"] == "upper" else anom < thr
    counts = np.array([int(hit[(dates >= np.datetime64(f"{y}-01-01")) & (dates < np.datetime64(f"{y + 1}-01-01"))].sum())
                       for y in yrs])
    ex_r = annual_trend(yrs, counts.astype(float))
    family.append(("extremes", ex["kind"], ex_r["mk"]["p"]))
    early, late = float(counts[:10].mean()), float(counts[-10:].mean())
    extremes = {"kind": ex["kind"], "label": ex["label"], "threshold_text": ex["threshold_text"],
                "years": yrs.tolist(), "counts": counts.tolist(),
                "sen_per_decade": round(ex_r["sen_slope_per_decade"], 2), "p": round(ex_r["mk"]["p"], 4),
                "early": {"label": f"{Y0}–{Y0 + 9}", "mean_per_year": round(early, 1)},
                "late": {"label": f"{Y1 - 9}–{Y1}", "mean_per_year": round(late, 1)}}

    # --- FDR across the insight family (M11)
    pv = np.array([p for _, _, p in family])
    sig, qv = ts.fdr_bh(pv, q=FDR_INSIGHT_Q)
    qmap = {(k, key): float(q) for (k, key, _), q in zip(family, qv)}
    for s in seasons:
        s["q"] = round(qmap[("season", s["season"])], 4)
        s["passes_fdr"] = s["q"] <= FDR_INSIGHT_Q
    for m in monthly:
        m["q"] = round(qmap[("month", m["month"])], 4)
        m["passes_fdr"] = m["q"] <= FDR_INSIGHT_Q
    extremes["q"] = round(qmap[("extremes", ex["kind"])], 4)
    extremes["passes_fdr"] = extremes["q"] <= FDR_INSIGHT_Q

    # --- spatial sign split (S9)
    w = np.cos(np.deg2rad(world.LAT)) * region["mask"] * np.isfinite(cells["slope"])
    opp = (np.sign(cells["slope"]) == -np.sign(per_dec)) & cells["sig"]
    same = (np.sign(cells["slope"]) == np.sign(per_dec)) & cells["sig"]
    share_opp = float((w * opp).sum() / w.sum()) if w.sum() else 0.0
    share_same = float((w * same).sum() / w.sum()) if w.sum() else 0.0

    unit_word = spec["units"] if spec["units"] != "%" else "points"
    return {
        "schema_version": SCHEMA_VERSION,
        "variable_id": var,
        "region_id": region["id"],
        "period": {"start": x0, "end": x1},
        "record_years": round(record_years, 1),
        "n": res["n"],
        "series": {"dates": [str(d)[:7] for d in dates],
                   "raw": rnd(raw, sd_ + 1), "anomaly": rnd(anom, sd_ + 1),
                   "smooth12": rnd(pd.Series(anom).rolling(12, center=True).mean().to_numpy(), sd_ + 1),
                   "annual": {"years": yrs.tolist(), "anomaly": rnd(ann, sd_ + 1)},
                   "raw_label": spec["raw_label"], "anomaly_label": spec["axis_label"],
                   "baseline": "anomaly = value minus the average of the same calendar month over the whole record"},
        "trend": {
            "sen_per_decade": round(per_dec, rd + 2),
            "ci90": [round(c, rd + 2) for c in ci90], "ci95": [round(c, rd + 2) for c in ci95],
            "ci99": [round(c, rd + 2) for c in ci99],
            "total_change": round(total, td + 1), "total_change_ci95": [round(c, td + 1) for c in total_ci],
            "percent_change": None if pct_total is None else round(pct_total, 1),
            "line": {"x": [x0, x1], "y": rnd([sen["intercept"] + sen["slope"] * t.min(),
                                              sen["intercept"] + sen["slope"] * t.max()], sd_ + 2)},
            "band95": {"x": [x0, str(mid_month), x1], "lower": rnd(lower, sd_ + 2), "upper": rnd(upper, sd_ + 2)},
            "display": {
                "rate": f"{fmt(per_dec, rd)} {spec['rate_units']}",
                "rate_value": fmt(per_dec, rd), "rate_unit": spec["rate_units"],
                "total_value": fmt(total, td), "total_unit": unit_word,
                "range": f"likely {fmt(ci95[0], rd)} to {fmt(ci95[1], rd)}",
                "total": f"{fmt(total, td)} {unit_word}",
                "total_label": f"Total change {Y0}–{Y1}",
                "total_range": f"likely {fmt(total_ci[0], td)} to {fmt(total_ci[1], td)}",
                "percent": None if pct_total is None else f"{fmt(pct_total, 0)}% of the average",
                "annotation": f"{fmt(per_dec, rd)} {spec['rate_units']} (likely {fmt(ci95[0], rd)} to {fmt(ci95[1], rd)})",
            },
        },
        "tests": {
            "mk": {"p": round(mk["p"], 6), "z": round(mk["z"], 3), "tau": round(mk["tau"], 3),
                   "variance_correction": round(mk["variance_correction"], 3), "level": mk_level},
            "ols": {"p": round(res["ols"]["p"], 6), "slope_per_decade": round(res["ols"]["slope_per_decade"], rd + 2),
                    "n_eff": round(res["ols"]["n_eff"], 1), "r1": round(res["ols"]["r1"], 3), "level": ols_level},
        },
        "verdict": {"level": level, "direction": direction, "headline": headline, "sentence": sentence,
                    "how_sure": how_sure, "methods_disagree": disagree},
        "years_to_detect": ytd,
        "emergence": {"year": emergence, "ratio_now": None if ratio_now is None else round(ratio_now, 2),
                      "swing": round(swing, sd_ + 1)},
        "seasons": seasons,
        "monthly_profile": monthly,
        "extremes": extremes,
        "spatial": {"share_opposite_significant": round(share_opp, 3),
                    "share_same_significant": round(share_same, 3), "warn": share_opp >= 0.15},
        "neighbour": None,
        "insights": [],
        "insights_audit": {"tested": len(family), "passed": int(sig.sum()), "shown": 0, "q": FDR_INSIGHT_Q},
        "provenance": provenance(spec, "region"),
        "_internal": {"family": family, "qmap": qmap, "spec": spec, "region": region},
    }


# --------------------------------------------------------------------------- insights
def build_insights(a: dict, regions: dict) -> None:
    spec, region = a["_internal"]["spec"], a["_internal"]["region"]
    v, tr = a["verdict"], a["trend"]
    level = v["level"]
    rd = spec["rate_decimals"]
    ins = []
    unit_word = spec["units"] if spec["units"] != "%" else "points"
    noun = spec["noun"] if v["direction"] == "up" else spec["noun_down"]

    if LEVEL_RANK[level] >= 2:
        if spec["percent"] and tr["percent_change"] is not None:
            text = (f"Since {Y0} it got about {fmt(abs(tr['percent_change']), 0, sign=False)}% "
                    f"{'wetter' if tr['total_change'] > 0 else 'drier'} "
                    f"({fmt(tr['total_change'], spec['total_decimals'])} {unit_word}).")
        else:
            lo, hi = sorted(abs(c) for c in tr["total_change_ci95"])
            d = spec["total_decimals"]
            adj = {"t2m": ("warmer", "cooler"), "soil": ("wetter", "drier")}[a["variable_id"]]
            subject = "it" if a["variable_id"] == "t2m" else "the soil"
            text = (f"Since {Y0} {subject} got about {fmt(abs(tr['total_change']), d, sign=False)} {unit_word} "
                    f"{adj[0] if tr['total_change'] > 0 else adj[1]} "
                    f"(likely {fmt(lo, d, sign=False)} to {fmt(hi, d, sign=False)}).")
        ins.append({"kind": "total_change", "text": text, "evidence_level": level,
                    "methods_anchor": "trend-test", "numbers": {"total": tr["total_change"]}})
    if a["emergence"]["year"]:
        ins.append({"kind": "signal_noise",
                    "text": (f"Since about {a['emergence']['year']} the change has been bigger than a normal "
                             "year-to-year swing."),
                    "evidence_level": "descriptive", "methods_anchor": "signal-noise",
                    "numbers": {"year": a["emergence"]["year"], "ratio_now": a["emergence"]["ratio_now"]}})

    # season: fastest significant season vs slowest, CIs must not overlap
    ss = sorted(a["seasons"], key=lambda s: s["sen_per_decade"] * (1 if v["direction"] == "up" else -1), reverse=True)
    fast, slow = ss[0], ss[-1]
    if (LEVEL_RANK[level] >= 2 and fast["passes_fdr"]
            and (fast["ci95"][0] > slow["ci95"][1] or fast["ci95"][1] < slow["ci95"][0])):
        r = abs(fast["sen_per_decade"]) / max(abs(slow["sen_per_decade"]), 1e-9)
        tw = times_word(r) if np.sign(fast["sen_per_decade"]) == np.sign(slow["sen_per_decade"]) else None
        verb = {"warming": "warming", "cooling": "cooling", "drying": "drying out", "wetting": "getting wetter"}[noun]
        if tw:
            text = f"{fast['label']}s are {verb} {tw} {slow['label'].lower()}s."
        else:
            text = f"{fast['label']}s change the most; {slow['label'].lower()}s show no clear change."
        ins.append({"kind": "season", "text": text, "evidence_level": "moderate", "methods_anchor": "seasons",
                    "numbers": {"fast": fast["sen_per_decade"], "slow": slow["sen_per_decade"]},
                    "q": fast["q"]})
    # months (M1)
    passing = [m for m in a["monthly_profile"]
               if m["passes_fdr"] and np.sign(m["sen_per_decade"]) == np.sign(tr["sen_per_decade"])]
    if LEVEL_RANK[level] >= 2 and 1 <= len(passing) <= 5:
        top = sorted(passing, key=lambda m: abs(m["sen_per_decade"]), reverse=True)[:2]
        top = sorted(top, key=lambda m: m["month"])
        names = " and ".join(MONTH_NAMES[m["month"] - 1] for m in top)
        ins.append({"kind": "months", "text": f"Most of the {noun} happens in {names}.",
                    "evidence_level": "moderate", "methods_anchor": "months",
                    "numbers": {"months": [m["month"] for m in top]}, "q": min(m["q"] for m in top)})
    # extremes (S7)
    ex = a["extremes"]
    if ex["passes_fdr"]:
        ins.append({"kind": "extremes",
                    "text": (f"{ex['label']}: about {ex['early']['mean_per_year']:g} a year in {ex['early']['label']}, "
                             f"about {ex['late']['mean_per_year']:g} a year in {ex['late']['label']}."),
                    "evidence_level": "moderate", "methods_anchor": "extremes",
                    "numbers": {"early": ex["early"]["mean_per_year"], "late": ex["late"]["mean_per_year"]},
                    "q": ex["q"]})
    # neighbour (S11)
    nb = a["neighbour"]
    if nb:
        ins.append({"kind": "neighbour",
                    "text": f"{nb['distance_text']} {nb['bearing']}, {nb['name']} is {nb['words']}.",
                    "evidence_level": "descriptive", "methods_anchor": "neighbour",
                    "numbers": {"distance_km": nb["distance_km"]}})
    # heterogeneity (S9)
    if a["spatial"]["warn"]:
        ins.append({"kind": "heterogeneity",
                    "text": (f"The regional average hides a contrast: about "
                             f"{round(100 * a['spatial']['share_opposite_significant'])}% of the area moves the other way."),
                    "evidence_level": "descriptive", "methods_anchor": "sign-split",
                    "numbers": {"share": a["spatial"]["share_opposite_significant"]}})
    # not visible yet
    if level in ("none", "weak") and a["years_to_detect"]:
        ins.append({"kind": "not_yet", "text": "Too noisy to tell yet. " + a["years_to_detect"]["text"],
                    "evidence_level": "descriptive", "methods_anchor": "years-to-detect",
                    "numbers": {"years": a["years_to_detect"]["value"]}})
    # caveat
    if v["methods_disagree"]:
        ins.append({"kind": "caveat",
                    "text": "Our two tests disagree on how sure we can be, so we report the weaker verdict.",
                    "evidence_level": "descriptive", "methods_anchor": "two-tests", "numbers": {}})
    a["insights"] = ins
    a["insights_audit"]["shown"] = sum(1 for i in ins if "q" in i)


def attach_neighbours(results: dict, regions: dict) -> None:
    for (rid, var), a in results.items():
        if a["verdict"]["direction"] == "flat":
            continue
        best = None
        for (oid, ovar), o in results.items():
            if ovar != var or oid == rid:
                continue
            if LEVEL_RANK[o["verdict"]["level"]] < 2 or o["verdict"]["direction"] == a["verdict"]["direction"]:
                continue
            c1, c2 = regions[rid]["centroid"], regions[oid]["centroid"]
            km = haversine_km(c1[0], c1[1], c2[0], c2[1])
            if km <= 3000 and (best is None or km < best[0]):
                best = (km, oid, compass(c1[0], c1[1], c2[0], c2[1]))
        if best:
            km, oid, bearing = best
            spec = VARIABLES[var]
            words = spec["up"] if results[(oid, var)]["verdict"]["direction"] == "up" else spec["down"]
            rounded = int(round(km, -2))
            a["neighbour"] = {"region_id": oid, "name": regions[oid]["name"], "distance_km": rounded,
                              "distance_text": f"{rounded:,} km", "bearing": bearing, "words": words}


# --------------------------------------------------------------------------- compare
def compare(a: dict, b: dict, var: str) -> dict:
    spec = VARIABLES[var]
    ya = np.array([np.nan if v is None else v for v in a["series"]["anomaly"]])
    yb = np.array([np.nan if v is None else v for v in b["series"]["anomaly"]])
    dates = np.array([np.datetime64(d + "-01") for d in a["series"]["dates"]])
    r = ts.analyze_series(dates, ya - yb, deseasonalize_monthly=False, obs_per_year=12)
    lvl = level_from_p(r["mk"]["p"])
    differ = LEVEL_RANK[lvl] >= 2
    rd = spec["rate_decimals"]
    na, nb = a["_internal"]["region"]["name"], b["_internal"]["region"]["name"]
    if differ:
        answer = "Yes, the two trends really differ."
        sentence = (f"The gap between {na} and {nb} changes by {fmt(r['sen_slope_per_decade'], rd)} "
                    f"{spec['rate_units']} ({p_text(r['mk']['p'])}), more than chance would explain.")
    else:
        answer = "Not clearly. The difference could still be chance."
        sentence = (f"The gap between {na} and {nb} changes by {fmt(r['sen_slope_per_decade'], rd)} "
                    f"{spec['rate_units']}, but that is within what natural swings produce ({p_text(r['mk']['p'])}).")
    return {"schema_version": SCHEMA_VERSION, "variable_id": var,
            "region_a": a["region_id"], "region_b": b["region_id"],
            "diff_sen_per_decade": round(r["sen_slope_per_decade"], rd + 2),
            "ci95": [round(c, rd + 2) for c in r["sen_ci95_per_decade"]],
            "p": round(r["mk"]["p"], 6), "level": lvl, "differ": differ,
            "answer": answer, "sentence": sentence,
            "display": {"rate": f"{fmt(r['sen_slope_per_decade'], rd)} {spec['rate_units']}",
                        "range": f"likely {fmt(r['sen_ci95_per_decade'][0], rd)} to {fmt(r['sen_ci95_per_decade'][1], rd)}"},
            "provenance": provenance(spec, "region")}


# --------------------------------------------------------------------------- validation (Methods page)
def validation_table(runs: int) -> dict:
    sys.path.insert(0, str(ROOT / ".claude" / "skills" / "trend-stats" / "scripts"))
    import validate_type1  # noqa: E402
    buf = io.StringIO()
    with redirect_stdout(buf):
        validate_type1.main(runs)
    rows = []
    for line in buf.getvalue().splitlines():
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) == 5 and parts[0].isdigit():
            rows.append({"n_months": int(parts[0]), "phi": float(parts[1]), "test": parts[2],
                         "false_alarm_rate": float(parts[3]), "power": float(parts[4])})
    return {"schema_version": SCHEMA_VERSION, "runs": runs, "alpha": 0.05,
            "source": "validate_type1.py (Monte-Carlo, AR(1) noise); real simulation, not synthetic data",
            "rows": rows}


# --------------------------------------------------------------------------- catalog
def catalog(variables_ready: dict) -> dict:
    cat = yaml.safe_load((ROOT / "data/catalog/variables.yaml").read_text(encoding="utf-8"))
    src = cat["sources"]
    ready = {v["catalog_id"]: k for k, v in variables_ready.items()}
    out = []
    for v in cat["variables"]:
        biomes = set(v.get("biomes", []))
        places = sorted(k for k, (_, tags) in PLACE_TYPES.items() if biomes & tags)
        out.append({"id": v["id"], "name": v["name"], "definition": v["definition"],
                    "why_it_trends": v.get("why_it_trends", ""),
                    "source": src.get(v.get("source"), {}).get("name", v.get("source")),
                    "period": str(v.get("period", "")), "resolution": str(v.get("resolution", "")),
                    "topic": viz_topic(v.get("topic")),
                    "place_types": places, "anywhere": "any" in biomes,
                    "app_variable_id": ready.get(v["id"]),
                    "status": "ready" if v["id"] in ready else "planned"})
    return {"schema_version": SCHEMA_VERSION,
            "topics": [{"id": k, "label": lbl} for k, lbl in TOPIC_LABELS.items()],
            "place_types": [{"id": k, "label": lbl} for k, (lbl, _) in PLACE_TYPES.items()],
            "variables": out, "synthetic": True}


# --------------------------------------------------------------------------- main
def main(seed: int, runs: int) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    rng = np.random.default_rng(seed)
    world = World(rng)
    regions_fc = json.loads((ROOT / "data/regions/regions.geojson").read_text(encoding="utf-8"))
    regions = {}
    for f in regions_fc["features"]:
        p = f["properties"]
        g = shape(f["geometry"])
        regions[p["id"]] = {**p, "geometry": f["geometry"], "mask": region_mask(world, g)}

    cells = {}
    for var in VARIABLES:
        layer, cells[var] = map_layer(world, var, rng)
        write_json(OUT / "map" / f"{var}.json", layer)
        print(f"map {var}: limit {layer['limit']}, significant cells {sum(layer['significant'])}")

    results = {}
    for rid, region in regions.items():
        for var in VARIABLES:
            results[(rid, var)] = analyse(world, var, region, cells[var], rng)
    attach_neighbours(results, regions)
    for a in results.values():
        build_insights(a, regions)

    for (rid, var), a in results.items():
        internal = a.pop("_internal")
        print(f"{rid:13s} {var:6s} {a['verdict']['level']:9s} {a['trend']['display']['rate']:28s} "
              f"insights={len(a['insights'])} tested={a['insights_audit']['tested']} passed={a['insights_audit']['passed']}")
        write_json(OUT / "analysis" / f"{rid}__{var}.json", a)
        a["_internal"] = internal

    ids = list(regions)
    for var in VARIABLES:
        for i, ra in enumerate(ids):
            for rb in ids[i + 1:]:
                c = compare(results[(ra, var)], results[(rb, var)], var)
                write_json(OUT / "compare" / f"{ra}__{rb}__{var}.json", c)

    index = {
        "schema_version": SCHEMA_VERSION, "synthetic": True,
        "generated": dt.date.today().isoformat(),
        "default_case": "01",
        "cases": CASES,
        "regions": [{k: r[k] for k in ("id", "name", "place_type", "bbox", "centroid", "geometry")}
                    for r in regions.values()],
        "variables": [{"id": k, "catalog_id": v["catalog_id"], "name": v["name"], "long_name": v["long_name"],
                       "units": v["units"], "rate_units": v["rate_units"], "palette": v["palette"],
                       "words": v["words"], "topic": v["topic"], "land_only": v["land_only"],
                       "source": "NASA POWER (MERRA-2)", "parameter": v["parameter"],
                       "period": f"{Y0}–{Y1}"} for k, v in VARIABLES.items()],
        "verdicts": {f"{rid}__{var}": {"level": a["verdict"]["level"], "direction": a["verdict"]["direction"],
                                        "headline": a["verdict"]["headline"], "rate": a["trend"]["display"]["rate"]}
                     for (rid, var), a in results.items()},
    }
    write_json(OUT / "index.json", index)
    write_json(OUT / "catalog.json", catalog(VARIABLES))
    write_json(OUT / "validation.json", validation_table(runs))
    print("done")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--runs", type=int, default=300, help="Monte-Carlo runs for validation.json")
    args = ap.parse_args()
    main(args.seed, args.runs)
