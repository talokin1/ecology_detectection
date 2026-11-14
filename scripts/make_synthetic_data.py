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
FDR_INSIGHT_Q = 0.05  # same q as the maps (review P0-5: filter and 95% whiskers must agree)
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
        "units": "°C", "rate_units": "°C per decade", "axis_label": "Difference from normal (°C)",
        "total_unit": "°C", "anomaly_units": "°C",
        "units_long": "in °C, about 2 m above the ground",
        "map_title": "Where is the air getting warmer or cooler?",
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
        "units": "mm/day", "rate_units": "mm/day per decade", "axis_label": "Difference from normal (mm/day)",
        "total_unit": "mm/day", "anomaly_units": "mm/day",
        "units_long": "rain and snow, in millimetres of water per day",
        "map_title": "Where is it getting wetter or drier?",
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
        "units": "%", "rate_units": "percentage points per decade",
        "axis_label": "Difference from normal (percentage points)",
        "total_unit": "percentage points", "anomaly_units": "percentage points",
        "units_long": "in percent of saturation (0% = bone dry, 100% = soaked)",
        "map_title": "Where is the soil getting drier or wetter?",
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
    # Pre-registered null case (review P1-7): question fixed before computing; shown whatever comes out.
    {"id": "04", "slug": "only-the-south", "title": "Only the south?",
     "question": "Is all of Ukraine drying out, or only the south?",
     "teaser": "We chose this question before running the numbers, and we show the answer whatever it is.",
     "variable_id": "soil", "region_id": "ukraine"},
]
NAME_IN_SENTENCE = {"sahel": "the Sahel", "great_plains": "the Great Plains (USA)"}

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
    d = spec["rate_decimals"] + 1
    bins = 11
    edges = [-limit + 2 * limit * i / bins for i in range(bins + 1)]
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
        "bins": bins,
        "value_decimals": d,
        "legend": {
            "title": f"Trend · {spec['rate_units']}",
            "edges_text": [fmt(e, d) for e in edges],
            "ticks": [{"value": v, "text": "0" if v == 0 else fmt(v, d - 1)} for v in (-limit, -limit / 2, 0, limit / 2, limit)],
            "min_text": f"≤ {fmt(-limit, d - 1)}", "max_text": f"≥ {fmt(limit, d - 1)}",
        },
        "units_label": spec["rate_units"],
        "words": spec["words"],
        "fdr_q": FDR_MAP_Q,
        "caption": (f"SYNTHETIC demo field shaped like NASA POWER {spec['parameter']} · {Y0}–{Y1} · "
                    "Sen's slope of yearly means in each 1° square. Strong colour: passes the map-wide "
                    f"test for false alarms (Mann-Kendall with memory correction, q = {FDR_MAP_Q}). "
                    "This map enlarges areas near the poles."),
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
        "caveat": ("Data: model-based reanalysis, about 50 km squares (the map is regridded to 1°). "
                   f"The trend is a straight line through {Y0}–{Y1}; it shows what changed, not why."),
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


LEVEL_WORD = {"strong": "Strong evidence", "moderate": "Evidence", "weak": "A hint",
              "none": "No clear trend yet", "insufficient": "Not enough data"}
SEASON_VERB = {"warming": ("warming", "warm fastest"), "cooling": ("cooling", "cool fastest"),
               "drying": ("drying out", "dry out fastest"), "wetting": ("getting wetter", "get wetter fastest")}


def range_text(lo: float, hi: float, d: int, prefix: str = "95% range ", suffix: str = "") -> str:
    """Interval rounded outwards; adds decimals until neither bound prints as a signless zero."""
    for dd in range(d, d + 4):
        f = 10 ** dd
        lo_r, hi_r = math.floor(lo * f) / f, math.ceil(hi * f) / f
        # outward rounding must not move a bound onto or across zero
        if not ((hi < 0 <= hi_r) or (lo > 0 >= lo_r)):
            break
    return f"{prefix}{fmt(lo_r, dd)}{suffix} to {fmt(hi_r, dd)}{suffix}"


def sentence_name(region: dict) -> str:
    return NAME_IN_SENTENCE.get(region["id"], region["name"])


def analyse(world, var, region, cells, rng):
    spec = VARIABLES[var]
    name_s = sentence_name(region)
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
    decided_by = "both" if not disagree else ("mk" if weaker(mk_level, ols_level) == mk_level else "ols")
    direction = "up" if per_dec > 0 else "down" if per_dec < 0 else "flat"

    rd, td, sd_ = spec["rate_decimals"], spec["total_decimals"], spec["series_decimals"]
    unit = spec["total_unit"]
    total = sen["slope"] * span
    total_ci = [ci95[0] / 10 * span, ci95[1] / 10 * span]
    mean_level = float(np.nanmean(raw))
    pct_total = 100 * total / mean_level if spec["percent"] else None
    pct_ci = [100 * c / mean_level for c in total_ci] if spec["percent"] else None

    # --- headline, sentence, answer (templates; the app shows them verbatim)
    words = spec["up"] if direction == "up" else spec["down"]
    headline = {
        "strong": f"Strong evidence: {words}", "moderate": f"Evidence: {words}",
        "weak": "A hint, not proof", "none": "No clear trend yet", "insufficient": "Not enough data to judge",
    }[level]
    moved = "rose" if total > 0 else "dropped"
    total_abs = f"{fmt(abs(total), td, sign=False)} {unit}"
    if level == "strong":
        sentence = (f"Since {Y0}, {spec['long_name'].lower()} in {name_s} {moved} by about {total_abs}. "
                    f"A drift this large would be very rare if nothing were really changing ({p_text(mk['p'])}).")
    elif level == "moderate":
        sentence = (f"Since {Y0}, {spec['long_name'].lower()} in {name_s} {moved} by about {total_abs}. "
                    f"This would be rare if nothing were changing ({p_text(mk['p'])}).")
    elif level == "weak":
        sentence = (f"{spec['long_name']} in {name_s} may be {words}, but the evidence is not "
                    "strong enough to rule out ordinary ups and downs.")
    else:
        sentence = (f"{spec['long_name']} in {name_s} moves up and down from year to year, "
                    "and so far there is no steady drift we can tell apart from those swings.")
    rate_txt = f"{fmt(per_dec, rd)} {spec['rate_units']}"
    if level in ("strong", "moderate"):
        answer = f"{region['name']} is {words}: about {rate_txt} since {Y0}, {fmt(total, td)} {unit} in total."
    elif level == "weak":
        answer = f"Maybe, but not proven: {name_s} shows {rate_txt}, and the evidence is still weak."
    elif level == "none":
        answer = f"No clear trend yet in {name_s}: the change so far is within normal year-to-year swings."
    else:
        answer = "The record is too short or too patchy to judge a trend."
    how_sure = (f"Mann-Kendall test with a correction for month-to-month memory: {p_text(mk['p'])} · "
                f"{res['n']} months · second test (regression): {p_text(res['ols']['p'])}")
    disagree_text = (f"Mann-Kendall: {LEVEL_WORD[mk_level].lower()} ({p_text(mk['p'])}). Regression: "
                     f"{LEVEL_WORD[ols_level].lower()} ({p_text(res['ols']['p'])}). We report the weaker."
                     if disagree else None)

    # --- trend line and 95% fan in anomaly space
    x0, x1 = str(dates[0])[:7], str(dates[-1])[:7]
    tm = float(np.median(t))
    pivot = sen["intercept"] + sen["slope"] * tm
    lo, hi = ci95[0] / 10, ci95[1] / 10
    xs = [t.min(), tm, t.max()]
    lower = [min(pivot + lo * (x - tm), pivot + hi * (x - tm)) for x in xs]
    upper = [max(pivot + lo * (x - tm), pivot + hi * (x - tm)) for x in xs]
    mid_month = np.datetime64(f"{int(tm)}-01") + np.timedelta64(int(round((tm % 1) * 12)), "M")

    # --- years to detection (shown for none and weak)
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

    # --- seasons (S6) and months (M1): 95% ranges, filtered at the same q
    family = []
    seasons = []
    for code, label, ms in SEASONS:
        sy, sv = seasonal_series(dates, anom, ms)
        r = annual_trend(sy, sv)
        p = r["mk"]["p"]
        c95 = r["sen_ci95_per_decade"]
        seasons.append({"season": code, "label": label,
                        "sen_per_decade": round(r["sen_slope_per_decade"], rd + 1),
                        "ci95": [round(c, rd + 2) for c in c95], "ci_text": range_text(c95[0], c95[1], rd),
                        "p": round(p, 4), "display": fmt(r["sen_slope_per_decade"], rd)})
        family.append(("season", code, p))
    monthly = []
    for m in range(1, 13):
        sy, sv = seasonal_series(dates, anom, [m])
        r = annual_trend(sy, sv)
        c95 = r["sen_ci95_per_decade"]
        monthly.append({"month": m, "label": MONTH_NAMES[m - 1][:3], "name": MONTH_NAMES[m - 1],
                        "sen_per_decade": round(r["sen_slope_per_decade"], rd + 1),
                        "ci95": [round(c, rd + 2) for c in c95], "ci_text": range_text(c95[0], c95[1], rd),
                        "display": fmt(r["sen_slope_per_decade"], rd), "p": round(r["mk"]["p"], 4)})
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
                "early": {"label": f"{Y0}–{Y0 + 9}", "mean_per_year": round(early, 1), "years": [Y0, Y0 + 9]},
                "late": {"label": f"{Y1 - 9}–{Y1}", "mean_per_year": round(late, 1), "years": [Y1 - 9, Y1]}}

    # --- FDR across the follow-up checks (M11)
    pv = np.array([p for _, _, p in family])
    sig, qv = ts.fdr_bh(pv, q=FDR_INSIGHT_Q)
    qmap = {(k, key): float(q) for (k, key, _), q in zip(family, qv)}
    for s_ in seasons:
        s_["q"] = round(qmap[("season", s_["season"])], 4)
        s_["passes_fdr"] = s_["q"] <= FDR_INSIGHT_Q
    for m in monthly:
        m["q"] = round(qmap[("month", m["month"])], 4)
        m["passes_fdr"] = m["q"] <= FDR_INSIGHT_Q
    extremes["q"] = round(qmap[("extremes", ex["kind"])], 4)
    extremes["passes_fdr"] = extremes["q"] <= FDR_INSIGHT_Q
    extremes["display"] = {
        "subtitle": f"Months per year that were {ex['threshold_text']}.",
        "trend_text": (f"From about {extremes['early']['mean_per_year']:g} a year in {extremes['early']['label']} "
                       f"to about {extremes['late']['mean_per_year']:g} a year in {extremes['late']['label']}."
                       if extremes["passes_fdr"] else "The change in this count could still be chance."),
    }

    # --- spatial sign split (S9)
    w = np.cos(np.deg2rad(world.LAT)) * region["mask"] * np.isfinite(cells["slope"])
    opp = (np.sign(cells["slope"]) == -np.sign(per_dec)) & cells["sig"]
    same = (np.sign(cells["slope"]) == np.sign(per_dec)) & cells["sig"]
    share_opp = float((w * opp).sum() / w.sum()) if w.sum() else 0.0
    share_same = float((w * same).sum() / w.sum()) if w.sum() else 0.0

    rng95 = range_text(ci95[0], ci95[1], rd)
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
                   "anomaly_units": spec["anomaly_units"],
                   "baseline": f"normal = the average of the same calendar month, {Y0}–{Y1}"},
        "trend": {
            "sen_per_decade": round(per_dec, rd + 2),
            "ci90": [round(c, rd + 2) for c in ci90], "ci95": [round(c, rd + 2) for c in ci95],
            "ci99": [round(c, rd + 2) for c in ci99],
            "total_change": round(total, td + 1), "total_change_ci95": [round(c, td + 1) for c in total_ci],
            "percent_change": None if pct_total is None else round(pct_total, 1),
            "percent_change_ci95": None if pct_ci is None else [round(c, 1) for c in pct_ci],
            "line": {"x": [x0, x1], "y": rnd([sen["intercept"] + sen["slope"] * t.min(),
                                              sen["intercept"] + sen["slope"] * t.max()], sd_ + 2)},
            "band95": {"x": [x0, str(mid_month), x1], "lower": rnd(lower, sd_ + 2), "upper": rnd(upper, sd_ + 2)},
            "display": {
                "rate": rate_txt,
                "rate_value": fmt(per_dec, rd), "rate_unit": spec["rate_units"],
                "total_value": fmt(total, td), "total_unit": unit,
                "range": rng95,
                "total": f"{fmt(total, td)} {unit}",
                "total_label": f"Total change {Y0}–{Y1}",
                "total_range": range_text(total_ci[0], total_ci[1], td),
                "percent": None if pct_total is None else f"{fmt(pct_total, 0)}% of the average",
                "percent_range": None if pct_ci is None else range_text(pct_ci[0], pct_ci[1], 0, suffix="%"),
                "annotation": f"{rate_txt} ({rng95})",
            },
        },
        "tests": {
            "mk": {"p": round(mk["p"], 6), "z": round(mk["z"], 3), "tau": round(mk["tau"], 3),
                   "variance_correction": round(mk["variance_correction"], 3), "level": mk_level},
            "ols": {"p": round(res["ols"]["p"], 6), "slope_per_decade": round(res["ols"]["slope_per_decade"], rd + 2),
                    "n_eff": round(res["ols"]["n_eff"], 1), "r1": round(res["ols"]["r1"], 3), "level": ols_level},
        },
        "verdict": {"level": level, "direction": direction, "headline": headline, "sentence": sentence,
                    "answer": answer, "how_sure": how_sure, "methods_disagree": disagree,
                    "decided_by": decided_by, "disagree_text": disagree_text},
        "years_to_detect": ytd,
        "emergence": {"year": emergence, "ratio_now": None if ratio_now is None else round(ratio_now, 2),
                      "swing": round(swing, sd_ + 1),
                      "label": (f"Around {emergence}, the change on the trend line became bigger than a normal "
                                "year-to-year swing." if emergence else None)},
        "seasons": seasons,
        "monthly_profile": monthly,
        "extremes": extremes,
        "spatial": {"share_opposite_significant": round(share_opp, 3),
                    "share_same_significant": round(share_same, 3), "warn": share_opp >= 0.15},
        "neighbour": None,
        "insights": [],
        "insights_audit": {"tested": len(family), "passed": int(sig.sum()), "shown": 0, "q": FDR_INSIGHT_Q, "text": ""},
        "provenance": provenance(spec, "region"),
        "_internal": {"family": family, "qmap": qmap, "spec": spec, "region": region,
                      "total": total, "pct": pct_total, "unit": unit},
    }


# --------------------------------------------------------------------------- insights
def change_phrase(a: dict) -> str:
    """'about 19% drier' / 'about 4.4 percentage points drier' / 'about 2.6 °C warmer'."""
    i, spec = a["_internal"], a["_internal"]["spec"]
    adj = spec["words"]["pos"] if i["total"] > 0 else spec["words"]["neg"]
    adj = {"warming": "warmer", "cooling": "cooler"}.get(adj, adj)
    if i["pct"] is not None:
        return f"about {fmt(abs(i['pct']), 0, sign=False)}% {adj}"
    return f"about {fmt(abs(i['total']), spec['total_decimals'], sign=False)} {i['unit']} {adj}"


def build_insights(a: dict, regions: dict) -> None:
    spec = a["_internal"]["spec"]
    v, tr = a["verdict"], a["trend"]
    level = v["level"]
    ins = []
    noun = spec["noun"] if v["direction"] == "up" else spec["noun_down"]

    if LEVEL_RANK[level] >= 2:
        if spec["percent"] and tr["percent_change"] is not None:
            text = (f"Since {Y0} it got {change_phrase(a)} "
                    f"({tr['display']['total_value']} {tr['display']['total_unit']}; {tr['display']['percent_range']}).")
        else:
            subject = "it" if a["variable_id"] == "t2m" else "the soil"
            text = f"Since {Y0} {subject} got {change_phrase(a)} ({tr['display']['total_range']})."
        ins.append({"kind": "total_change", "text": text, "evidence_level": level, "tested": False,
                    "methods_anchor": "trend-test", "numbers": {"total": tr["total_change"]}})
    if a["emergence"]["year"]:
        ins.append({"kind": "signal_noise",
                    "text": (f"Since about {a['emergence']['year']} the change has been bigger than a normal "
                             "year-to-year swing."),
                    "evidence_level": "descriptive", "tested": False, "methods_anchor": "signal-noise",
                    "numbers": {"year": a["emergence"]["year"], "ratio_now": a["emergence"]["ratio_now"]}})

    # seasons: always answer "which season?" once the main trend is clear
    if LEVEL_RANK[level] >= 2:
        sgn = 1 if v["direction"] == "up" else -1
        ss = sorted(a["seasons"], key=lambda s_: s_["sen_per_decade"] * sgn, reverse=True)
        fast, slow = ss[0], ss[-1]
        apart = fast["ci95"][0] > slow["ci95"][1] or fast["ci95"][1] < slow["ci95"][0]
        verb, verb_fast = SEASON_VERB[noun]
        same_sign = np.sign(fast["sen_per_decade"]) == np.sign(slow["sen_per_decade"])
        units = spec["rate_units"]
        if fast["passes_fdr"] and apart and slow["passes_fdr"] and same_sign:
            r = abs(fast["sen_per_decade"]) / max(abs(slow["sen_per_decade"]), 1e-9)
            tw = times_word(r) or "faster than"
            ins.append({"kind": "season", "text": f"{fast['label']}s are {verb} {tw} {slow['label'].lower()}s.",
                        "evidence_level": "moderate", "tested": True, "methods_anchor": "seasons",
                        "numbers": {"fast": fast["sen_per_decade"], "slow": slow["sen_per_decade"]}, "q": fast["q"]})
        elif fast["passes_fdr"] and apart:
            ins.append({"kind": "season",
                        "text": (f"{fast['label']}s {verb_fast} ({fast['display']} {units}); "
                                 f"{slow['label'].lower()}s show no clear change."),
                        "evidence_level": "moderate", "tested": True, "methods_anchor": "seasons",
                        "numbers": {"fast": fast["sen_per_decade"], "slow": slow["sen_per_decade"]}, "q": fast["q"]})
        else:
            others = [s_["sen_per_decade"] for s_ in ss[1:]]
            o_lo, o_hi = min(others), max(others)
            ins.append({"kind": "season_unresolved",
                        "text": (f"{fast['label']} shows the fastest {noun} ({fast['display']} {units}; the other "
                                 f"seasons {fmt(o_lo, spec['rate_decimals'])} to {fmt(o_hi, spec['rate_decimals'])}), "
                                 f"but the ranges still overlap, so we cannot yet say {fast['label'].lower()} "
                                 "is truly different."),
                        "evidence_level": "descriptive", "tested": False, "methods_anchor": "seasons",
                        "numbers": {"fast": fast["sen_per_decade"]}})
    # months (M1)
    passing = [m for m in a["monthly_profile"]
               if m["passes_fdr"] and np.sign(m["sen_per_decade"]) == np.sign(tr["sen_per_decade"])]
    if LEVEL_RANK[level] >= 2 and 1 <= len(passing) <= 5:
        top = sorted(passing, key=lambda m: abs(m["sen_per_decade"]), reverse=True)[:2]
        top = sorted(top, key=lambda m: m["month"])
        names = " and ".join(MONTH_NAMES[m["month"] - 1] for m in top)
        ins.append({"kind": "months", "text": f"Most of the {noun} happens in {names}.",
                    "evidence_level": "moderate", "tested": True, "methods_anchor": "months",
                    "numbers": {"months": [m["month"] for m in top]}, "q": min(m["q"] for m in top)})
    # extremes (S7)
    ex = a["extremes"]
    if ex["passes_fdr"]:
        ins.append({"kind": "extremes",
                    "text": (f"{ex['label']}: about {ex['early']['mean_per_year']:g} a year in {ex['early']['label']}, "
                             f"about {ex['late']['mean_per_year']:g} a year in {ex['late']['label']}."),
                    "evidence_level": "moderate", "tested": True, "methods_anchor": "extremes",
                    "numbers": {"early": ex["early"]["mean_per_year"], "late": ex["late"]["mean_per_year"]},
                    "q": ex["q"]})
    # neighbour (S11)
    nb = a["neighbour"]
    if nb:
        ins.append({"kind": "neighbour",
                    "text": f"{nb['distance_text']} {nb['bearing']}, {nb['name_in_sentence']} is {nb['words']}.",
                    "evidence_level": "descriptive", "tested": False, "methods_anchor": "neighbour",
                    "numbers": {"distance_km": nb["distance_km"]}})
    # heterogeneity (S9)
    if a["spatial"]["warn"]:
        ins.append({"kind": "heterogeneity",
                    "text": (f"The regional average hides a contrast: about "
                             f"{round(100 * a['spatial']['share_opposite_significant'])}% of the area moves the other way."),
                    "evidence_level": "descriptive", "tested": False, "methods_anchor": "sign-split",
                    "numbers": {"share": a["spatial"]["share_opposite_significant"]}})
    # not visible yet: only for "No clear trend yet" (plan v2)
    if level == "none" and a["years_to_detect"]:
        ins.append({"kind": "not_yet", "text": "Too noisy to tell yet. " + a["years_to_detect"]["text"],
                    "evidence_level": "descriptive", "tested": False, "methods_anchor": "years-to-detect",
                    "numbers": {"years": a["years_to_detect"]["value"]}})
    a["insights"] = ins
    au = a["insights_audit"]
    au["shown"] = sum(1 for i in ins if i["tested"])
    if au["passed"] and au["shown"] == 0 and LEVEL_RANK[level] < 2:
        au["text"] = (f"Besides the main test, we ran {au['tested']} follow-up checks (12 months, 4 seasons, "
                      f"extreme months). {au['passed']} held up after correcting for running many tests at once "
                      f"(q = {au['q']}), but we do not report them as findings while the main trend itself is not "
                      "clear.")
    elif au["passed"]:
        au["text"] = (f"Besides the main test, we ran {au['tested']} follow-up checks (12 months, 4 seasons, "
                      f"extreme months). {au['passed']} held up after correcting for running many tests at once "
                      f"(false discovery rate q = {au['q']}); most of them repeat the main trend month by month. "
                      "Findings marked “follow-up check” come from these checks.")
    else:
        au["text"] = (f"Besides the main test, we ran {au['tested']} follow-up checks (12 months, 4 seasons, "
                      "extreme months). None held up after correcting for running many tests at once "
                      f"(q = {au['q']}). That is a result too: no month or season stands out.")


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
            a["neighbour"] = {"region_id": oid, "name": regions[oid]["name"],
                              "name_in_sentence": sentence_name(regions[oid]), "distance_km": rounded,
                              "distance_text": f"{rounded:,} km", "bearing": bearing, "words": words}


# --------------------------------------------------------------------------- compare
def compare(a: dict, b: dict, var: str) -> dict:
    spec = VARIABLES[var]
    rd, sd_ = spec["rate_decimals"], spec["series_decimals"]
    ya = np.array([np.nan if v is None else v for v in a["series"]["anomaly"]])
    yb = np.array([np.nan if v is None else v for v in b["series"]["anomaly"]])
    dates = np.array([np.datetime64(d + "-01") for d in a["series"]["dates"]])
    diff = ya - yb
    r = ts.analyze_series(dates, diff, deseasonalize_monthly=False, obs_per_year=12)
    t = ts.decimal_years(dates)
    mk = ts.mann_kendall(t, diff)
    sen = ts.sens_slope(t, diff, var_s=mk["var_s"])
    lvl = level_from_p(r["mk"]["p"])
    differ = LEVEL_RANK[lvl] >= 2
    ra, rb = a["_internal"]["region"], b["_internal"]["region"]
    na, nb = ra["name"], rb["name"]
    va, vb = a["verdict"], b["verdict"]
    sa, sb = np.sign(a["trend"]["sen_per_decade"]), np.sign(b["trend"]["sen_per_decade"])
    wa = spec["up"] if va["direction"] == "up" else spec["down"]
    wb = spec["up"] if vb["direction"] == "up" else spec["down"]
    adj = lambda s_: spec["words"]["pos"] if s_ > 0 else spec["words"]["neg"]  # noqa: E731
    faster = na if abs(a["trend"]["sen_per_decade"]) > abs(b["trend"]["sen_per_decade"]) else nb
    if differ and sa != sb:
        headline = f"{na} {adj(sa)}, {nb} {adj(sb)}: the gap is growing"
        answer = f"They move in opposite directions: {sentence_name(ra)} is {wa}, {sentence_name(rb)} {wb}."
    elif differ:
        headline = f"Both {wa}, {faster} faster"
        answer = (f"Both are {wa}, but {faster} is changing faster, and the difference is bigger than chance "
                  "would usually produce.")
    else:
        headline = "No clear difference yet"
        answer = (f"Not clearly: we cannot yet tell the difference apart from natural swings ({p_text(r['mk']['p'])}).")
    c95 = r["sen_ci95_per_decade"]
    sentence = (f"The gap ({na} minus {nb}) changes by {fmt(r['sen_slope_per_decade'], rd)} {spec['rate_units']} "
                f"({p_text(r['mk']['p'])}).")
    summary = (f"{na}: {change_phrase(a)} ({LEVEL_WORD[va['level']].lower()}) · "
               f"{nb}: {change_phrase(b)} ({LEVEL_WORD[vb['level']].lower()})")
    x0, x1 = a["series"]["dates"][0], a["series"]["dates"][-1]
    tm = float(np.median(t))
    pivot = sen["intercept"] + sen["slope"] * tm
    lo, hi = c95[0] / 10, c95[1] / 10
    xs = [t.min(), tm, t.max()]
    mid_month = np.datetime64(f"{int(tm)}-01") + np.timedelta64(int(round((tm % 1) * 12)), "M")
    return {"schema_version": SCHEMA_VERSION, "variable_id": var,
            "region_a": a["region_id"], "region_b": b["region_id"],
            "diff_sen_per_decade": round(r["sen_slope_per_decade"], rd + 2),
            "ci95": [round(c, rd + 2) for c in c95],
            "p": round(r["mk"]["p"], 6), "level": lvl, "differ": differ,
            "headline": headline, "answer": answer, "sentence": sentence, "summary": summary,
            "gap_text": f"{na} minus {nb}",
            "display": {"rate": f"{fmt(r['sen_slope_per_decade'], rd)} {spec['rate_units']}",
                        "rate_value": fmt(r["sen_slope_per_decade"], rd), "rate_unit": spec["rate_units"],
                        "range": range_text(c95[0], c95[1], rd),
                        "gap_label": "How fast the gap grows"},
            "gap_series": {
                "dates": a["series"]["dates"], "diff": rnd(diff, sd_ + 1),
                "line": {"x": [x0, x1], "y": rnd([sen["intercept"] + sen["slope"] * t.min(),
                                                  sen["intercept"] + sen["slope"] * t.max()], sd_ + 2)},
                "band95": {"x": [x0, str(mid_month), x1],
                           "lower": rnd([min(pivot + lo * (x - tm), pivot + hi * (x - tm)) for x in xs], sd_ + 2),
                           "upper": rnd([max(pivot + lo * (x - tm), pivot + hi * (x - tm)) for x in xs], sd_ + 2)},
                "label": f"Gap: {na} minus {nb} ({spec['anomaly_units']})",
            },
            "provenance": provenance(spec, "region")}


# --------------------------------------------------------------------------- case answers
def case_answer(c: dict, results: dict, compares: dict) -> tuple[str, str, str]:
    """(answer, headline, level) for one case. Conditional templates: safe for any data."""
    a = results[(c["region_id"], c["variable_id"])]
    v = a["verdict"]
    if c.get("compare_region_id"):
        cmp_ = compares[frozenset((c["region_id"], c["compare_region_id"], c["variable_id"]))]
        b = results[(c["compare_region_id"], c["variable_id"])]
        sa, sb = np.sign(a["trend"]["sen_per_decade"]), np.sign(b["trend"]["sen_per_decade"])
        if cmp_["differ"] and sa != sb:
            ans = (f"Yes, in opposite directions: {b['_internal']['region']['name']} got {change_phrase(b)}, "
                   f"{a['_internal']['region']['name']} {change_phrase(a)}, and the gap between them is growing.")
        else:
            ans = cmp_["answer"]
        return ans, cmp_["headline"], cmp_["level"]
    if c["id"] == "01":
        if LEVEL_RANK[v["level"]] >= 2 and v["direction"] == "down":
            ans = f"Yes, the record backs Grandma: since {Y0} the soil has become {change_phrase(a)}"
            ex = a["extremes"]
            if ex and ex["passes_fdr"]:
                ans += (f", and very dry months went from about {ex['early']['mean_per_year']:g} "
                        f"to about {ex['late']['mean_per_year']:g} a year")
            return ans + ".", v["headline"], v["level"]
        if v["direction"] == "up" and LEVEL_RANK[v["level"]] >= 2:
            return "No: the record shows the soil getting wetter, not drier.", v["headline"], v["level"]
        return "Not proven: " + v["answer"][0].lower() + v["answer"][1:], v["headline"], v["level"]
    if c["id"] == "02":
        if LEVEL_RANK[v["level"]] >= 2:
            ans = f"Yes. {a['_internal']['region']['name']} is {change_phrase(a)} than in {Y0}."
            season = next((i for i in a["insights"] if i["kind"] in ("season", "season_unresolved")), None)
            if season and season["kind"] == "season":
                ans += " " + season["text"]
            elif season:
                fast = sorted(a["seasons"], key=lambda s_: abs(s_["sen_per_decade"]), reverse=True)[0]
                ans += f" {fast['label']} looks fastest, but we cannot yet tell it apart from the other seasons."
            return ans, v["headline"], v["level"]
        return v["answer"], v["headline"], v["level"]
    if c["id"] == "04":
        south = results[("south_ukraine", c["variable_id"])]
        sv = south["verdict"]
        if LEVEL_RANK[sv["level"]] >= 2 and LEVEL_RANK[v["level"]] < 2:
            ans = (f"Only the south is clear. Across all of Ukraine the soil may be drying "
                   f"({a['trend']['display']['rate']}), but the evidence is still weak")
            if a["years_to_detect"] and a["years_to_detect"]["value"]:
                ans += f"; about {a['years_to_detect']['value']} more years of data would settle it"
            return ans + ".", v["headline"], v["level"]
        if LEVEL_RANK[sv["level"]] >= 2 and LEVEL_RANK[v["level"]] >= 2:
            return "Both: the whole country and the south show a clear trend.", v["headline"], v["level"]
        return v["answer"], v["headline"], v["level"]
    return v["answer"], v["headline"], v["level"]


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
            fa, pw = float(parts[3]), float(parts[4])
            rows.append({"n_months": int(parts[0]), "phi": float(parts[1]), "test": parts[2],
                         "false_alarm_rate": fa, "power": pw,
                         "false_alarm_text": f"{100 * fa:.1f}%", "power_text": f"{100 * pw:.0f}%"})
    orig = [r_["false_alarm_rate"] for r_ in rows if r_["test"] == "MK original"]
    ours = [r_["false_alarm_rate"] for r_ in rows if r_["test"].startswith("MK Yue-Wang")]
    summary = (f"The classic test raised false alarms in up to {100 * max(orig):.0f}% of trend-free series; "
               f"ours stayed between {100 * min(ours):.0f}% and {100 * max(ours):.0f}%.")
    return {"schema_version": SCHEMA_VERSION, "runs": runs, "alpha": 0.05,
            "source": "validate_type1.py (Monte-Carlo, AR(1) noise); real simulation, not synthetic data",
            "summary": summary, "rows": rows}


# --------------------------------------------------------------------------- catalog
SOURCE_SHORT = {"power": "NASA POWER", "ges_disc": "NASA GES DISC", "lp_daac": "NASA LP DAAC",
                "nsidc": "NSIDC DAAC", "podaac": "NASA PO.DAAC"}


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
                    "source_short": SOURCE_SHORT.get(v.get("source"), v.get("source")),
                    "period": str(v.get("period", "")), "resolution": str(v.get("resolution", "")),
                    "topic": viz_topic(v.get("topic")),
                    "place_types": places, "anywhere": "any" in biomes,
                    "app_variable_id": ready.get(v["id"]),
                    "status": "ready" if v["id"] in ready else "planned"})
    labels = {**TOPIC_LABELS, "other": "Other"}
    return {"schema_version": SCHEMA_VERSION,
            "topics": [{"id": k, "label": lbl} for k, lbl in labels.items()],
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

    compares = {}
    ids = list(regions)
    for var in VARIABLES:
        for i, ra in enumerate(ids):
            for rb in ids[i + 1:]:
                c = compare(results[(ra, var)], results[(rb, var)], var)
                compares[frozenset((ra, rb, var))] = c
                write_json(OUT / "compare" / f"{ra}__{rb}__{var}.json", c)

    cases = []
    for c in CASES:
        ans, head, lvl = case_answer(c, results, compares)
        cases.append({**c, "answer": ans, "headline": head, "level": lvl})

    for (rid, var), a in results.items():
        internal = a.pop("_internal")
        print(f"{rid:13s} {var:6s} {a['verdict']['level']:9s} {a['trend']['display']['rate']:36s} "
              f"insights={len(a['insights'])} passed={a['insights_audit']['passed']} shown={a['insights_audit']['shown']}")
        write_json(OUT / "analysis" / f"{rid}__{var}.json", a)
        a["_internal"] = internal

    index = {
        "schema_version": SCHEMA_VERSION, "synthetic": True,
        "generated": dt.date.today().isoformat(),
        "default_case": "02",  # D7: air temperature reads fastest on a bare map
        "cases": cases,
        "regions": [{**{k: r[k] for k in ("id", "name", "place_type", "bbox", "centroid", "geometry")},
                     "name_in_sentence": sentence_name(r)} for r in regions.values()],
        "variables": [{"id": k, "catalog_id": v["catalog_id"], "name": v["name"], "long_name": v["long_name"],
                       "units": v["units"], "units_long": v["units_long"], "rate_units": v["rate_units"],
                       "anomaly_units": v["anomaly_units"], "map_title": v["map_title"], "palette": v["palette"],
                       "words": v["words"], "topic": v["topic"], "land_only": v["land_only"],
                       "source": "NASA POWER (MERRA-2)", "parameter": v["parameter"],
                       "period": f"{Y0}–{Y1}"} for k, v in VARIABLES.items()],
        "verdicts": {f"{rid}__{var}": {
            "level": a["verdict"]["level"], "level_word": LEVEL_WORD[a["verdict"]["level"]],
            "direction": a["verdict"]["direction"], "headline": a["verdict"]["headline"],
            "rate": a["trend"]["display"]["rate"], "rate_text": a["trend"]["display"]["rate_value"],
            "rate_value": a["trend"]["sen_per_decade"], "ci95": a["trend"]["ci95"],
            "range_text": a["trend"]["display"]["range"]}
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
