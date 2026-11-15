"""Build the web app's data from REAL NASA data in the frozen cache (`data/cache/`).

Inputs (all committed, checked by `scripts/check_cache.py`; nothing is downloaded here):
  regional monthly series   NASA POWER (MERRA-2) via `acquire.get_series`, cos(lat)-weighted,
                            land cells only where the region preset says so
  daily inputs              POWER daily T2M_MAX, T2M_MIN, PRECTOTCORR for the case regions
  world map                 2-degree monthly grids (`data/cache/grids/`, built by `grids.py`)

Statistics:
  headline verdicts, seasons, months, extremes, map   `trend_stats.py` (Sen, Mann-Kendall
                            Yue-Wang, OLS n_eff, BH FDR, years to detection)
  deeper checks             the team's offline pipeline `trend_detective.climate_stats`
                            (ETCCDI-style daily indices, SPI/SPEI, acceleration, variability,
                            block bootstrap, change point); one BH family per region document

Period rule (fixed before any result was looked at): every series starts in 1981-01 and ends
with the last calendar year that is complete in every input, so yearly, seasonal and map
values all use whole years.

Outputs (frontend/public/data/):
  index.json                       cases, regions (with outlines), variables
  catalog.json                     all catalog variables with plain-language text and status
  map/<variable>.json              2-degree global trend grid + FDR significance
  analysis/<region>__<variable>.json
  compare/<regionA>__<regionB>__<variable>.json
  stats/<region>.json              full climate_stats output for that region (reproducibility)
  validation.json                  Monte-Carlo false-alarm table (from validate_type1.py)

Usage (from the repo root, with requirements.txt installed):
  python scripts/make_app_data.py [--runs 300] [--bootstrap 999]

SI-assisted (Claude, Anthropic).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pandas as pd
import shapely
import xarray as xr
import yaml
from scipy import stats
from shapely import contains_xy
from shapely.geometry import Polygon, mapping, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".claude" / "skills" / "trend-stats" / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))
import trend_stats as ts  # noqa: E402
from trend_detective import acquire, power_zarr  # noqa: E402
from trend_detective.climate_stats import analyze as climate_analyze  # noqa: E402


def _no_download(*_args, **_kwargs):
    raise RuntimeError("make_app_data.py reads the frozen cache only; a series was missing from "
                       "data/cache/ (ask the data engineer to add it, see HANDOFF.md)")


power_zarr.open_source = _no_download  # never fetch: every input must come from the frozen cache

OUT = ROOT / "frontend" / "public" / "data"
GRIDS = ROOT / "data" / "cache" / "grids"
SCHEMA_VERSION = "0.1.0"
Y0 = 1981
Y1 = 2025  # recomputed in main(): last calendar year complete in every input


def baseline_years() -> tuple[int, int]:
    """Years that define "normal" for extreme-month thresholds: 1981-2010 for the long records,
    the first 20 years for records that start later (satellite era)."""
    return (1981, 2010) if Y0 <= 1981 else (Y0, Y0 + 19)

DAILY = {"tmax": "T2M_MAX", "tmin": "T2M_MIN", "precip": "PRECTOTCORR"}
FDR_MAP_Q = 0.05
MAP_MIN_NONZERO_YEARS = 10  # a map square with fewer non-zero yearly means is not tested
FDR_INSIGHT_Q = 0.05  # same q as the maps (review P0-5: filter and 95% whiskers must agree)
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"]
SEASONS = [("DJF", "Winter", [12, 1, 2]), ("MAM", "Spring", [3, 4, 5]),
           ("JJA", "Summer", [6, 7, 8]), ("SON", "Autumn", [9, 10, 11])]
LEVEL_RANK = {"insufficient": -1, "none": 0, "weak": 1, "moderate": 2, "strong": 3}
MINUS = "−"

# --------------------------------------------------------------------------- variables
# One entry per variable the app shows. Texts are templates: "<region> is <up|down>",
# "Most of the <noun> happens in ...", "<subject> got about X <adj>".
#   scale      source units -> app units (fraction -> %, W/m2 -> MJ/m2/day)
#   start      first year of the record (later for satellite-era products)
#   mask       where the map is drawn: "land" (land-only product), "ocean" (sea ice), "all"
#   map_only   no regional analyses: sea ice (every region is land) and, for now, snow, whose
#              monthly anomalies are zero all summer, which pulls a median slope to zero (needs a
#              snow-season method first). The map uses yearly means and is not affected.
# Not offered: CERES cloud amount. Its 60S-60N mean steps down in 2006 and again in 2022
# (about -1.5 points each), the signature of changes in the observing system, not of climate.
#   extreme    which tail of monthly anomalies is counted as an "extreme month" (None = not counted)
def _v(catalog_id, name, long_name, parameter, grid, units, rate_units, *, palette, words, adj, up, down,
       noun, noun_down, subject, units_long, map_title, raw_label, decimals, percent, topic, mask="all",
       scale=1.0, start=1981, extreme=None, source="NASA POWER (MERRA-2)", map_only=False,
       zero_is_missing=False, season_verbs=None):
    rd, td, sd = decimals
    unit = rate_units.replace(" per decade", "")
    return {
        "catalog_id": catalog_id, "name": name, "long_name": long_name, "parameter": parameter,
        "units": units, "rate_units": rate_units, "axis_label": f"Difference from normal ({unit})",
        "total_unit": unit, "anomaly_units": unit, "units_long": units_long, "map_title": map_title,
        "raw_label": raw_label, "palette": palette, "words": words, "adj": adj, "up": up, "down": down,
        "noun": noun, "noun_down": noun_down, "subject": subject,
        "rate_decimals": rd, "total_decimals": td, "series_decimals": sd, "percent": percent,
        "topic": topic, "land_only": mask == "land", "mask": mask, "scale": scale, "start": start,
        "grid": grid, "grid_var": parameter, "extreme": extreme, "source": source, "map_only": map_only,
        "zero_is_missing": zero_is_missing, "season_verbs": season_verbs,
    }


def _ex(kind, tail, label, adj):
    return {"kind": kind, "tail": tail, "label": label, "adj": adj}


VARIABLES = {
    "t2m": _v(
        "air_temperature_power", "Air temperature", "Air temperature near the surface", "T2M",
        "merra2_T2M_2deg.nc", "°C", "°C per decade", palette="RdBu",
        words={"neg": "cooling", "pos": "warming"}, adj={"neg": "cooler", "pos": "warmer"},
        up="getting warmer", down="getting cooler", noun="warming", noun_down="cooling", subject="it",
        units_long="in °C, about 2 m above the ground", map_title="Where is the air getting warmer or cooler?",
        raw_label="Monthly mean temperature (°C)", decimals=(2, 1, 2), percent=False, topic="temperature",
        extreme=_ex("hot_months", "upper", "Very hot months", "hotter"),
        season_verbs={"warming": ("warming", "warm fastest"), "cooling": ("cooling", "cool fastest")}),
    "precip": _v(
        "precipitation_power", "Precipitation", "Precipitation (rain and snow)", "PRECTOTCORR",
        "merra2_PRECTOTCORR_2deg.nc", "mm/day", "mm/day per decade", palette="BrBG",
        words={"neg": "drier", "pos": "wetter"}, adj={"neg": "drier", "pos": "wetter"},
        up="getting wetter", down="getting drier", noun="wetting", noun_down="drying", subject="it",
        units_long="rain and snow, in millimetres of water per day",
        map_title="Where is it getting wetter or drier?", raw_label="Monthly precipitation (mm/day)",
        decimals=(2, 2, 2), percent=True, topic="water",
        extreme=_ex("dry_months", "lower", "Very dry months", "drier"),
        season_verbs={"wetting": ("getting wetter", "get wetter fastest"),
                      "drying": ("drying out", "dry out fastest")}),
    "soil": _v(
        "root_zone_soil_wetness_power", "Soil wetness", "Root-zone soil wetness", "GWETROOT",
        "merra2_GWETROOT_2deg.nc", "%", "percentage points per decade", palette="BrBG",
        words={"neg": "drier", "pos": "wetter"}, adj={"neg": "drier", "pos": "wetter"},
        up="getting wetter", down="getting drier", noun="wetting", noun_down="drying", subject="the soil",
        units_long="in percent of saturation (0% = bone dry, 100% = soaked)",
        map_title="Where is the soil getting drier or wetter?",
        raw_label="Root-zone soil wetness (% of saturation)", decimals=(1, 1, 1), percent=False,
        topic="water", mask="land", scale=100.0,  # fraction 0-1 -> %
        extreme=_ex("dry_months", "lower", "Very dry months", "drier"),
        season_verbs={"wetting": ("getting wetter", "get wetter fastest"),
                      "drying": ("drying out", "dry out fastest")}),
    "rain_sat": _v(
        "precipitation_imerg", "Rain from space", "Precipitation measured from space (GPM IMERG)",
        "IMERG_PRECTOT", "imerg_IMERG_PRECTOT_2deg.nc", "mm/day", "mm/day per decade", palette="BrBG",
        words={"neg": "drier", "pos": "wetter"}, adj={"neg": "drier", "pos": "wetter"},
        up="getting wetter", down="getting drier", noun="wetting", noun_down="drying", subject="it",
        units_long="rain and snow seen by satellites, in millimetres of water per day",
        map_title="Where do satellites see more or less rain?", raw_label="Monthly precipitation (mm/day)",
        decimals=(2, 2, 2), percent=True, topic="water", start=1998,
        source="NASA GPM IMERG (via POWER)",
        extreme=_ex("dry_months", "lower", "Very dry months", "drier"),
        season_verbs={"wetting": ("getting wetter", "get wetter fastest"),
                      "drying": ("drying out", "dry out fastest")}),
    "evap": _v(
        "evaporation_land_power", "Evaporation", "Evaporation from land", "EVLAND",
        "merra2_EVLAND_2deg.nc", "mm/day", "mm/day per decade", palette="BrBG",
        words={"neg": "less", "pos": "more"}, adj={"neg": "lower", "pos": "higher"},
        up="evaporating more water", down="evaporating less water",
        noun="rise in evaporation", noun_down="drop in evaporation", subject="evaporation",
        units_long="water leaving the land surface, in millimetres per day",
        map_title="Where does the land give up more or less water?",
        raw_label="Monthly evaporation from land (mm/day)", decimals=(2, 2, 2), percent=True,
        topic="water", mask="land"),
    "vapour": _v(
        "water_vapour_power", "Water vapour", "Water vapour in the air", "TQV",
        "merra2_TQV_2deg.nc", "kg/m²", "kg/m² per decade", palette="BrBG",
        words={"neg": "drier air", "pos": "moister air"}, adj={"neg": "lower", "pos": "higher"},
        up="holding more water vapour", down="holding less water vapour",
        noun="rise in water vapour", noun_down="drop in water vapour", subject="water vapour in the air",
        units_long="all the water vapour above a square metre of ground, in kilograms",
        map_title="Where does the air hold more or less water?",
        raw_label="Monthly water vapour (kg/m²)", decimals=(2, 2, 2), percent=True, topic="water",
        extreme=_ex("humid_months", "upper", "Very humid months", "more humid")),
    "snow_cover": _v(
        "snow_cover_fraction_power", "Snow cover", "Share of the land covered by snow", "FRSNO",
        "merra2_FRSNO_2deg.nc", "%", "percentage points per decade", palette="BrBG",
        words={"neg": "less snow", "pos": "more snow"}, adj={"neg": "smaller", "pos": "larger"},
        up="gaining snow cover", down="losing snow cover",
        noun="gain in snow cover", noun_down="loss of snow cover", subject="snow cover",
        units_long="in percent of the land covered by snow", map_title="Where is snow cover shrinking or growing?",
        raw_label="Monthly snow cover (% of land)", decimals=(1, 1, 1), percent=False, topic="snow_ice",
        mask="land", scale=100.0, map_only=True),
    "snow_depth": _v(
        "snow_depth_power", "Snow depth", "Depth of snow on the ground", "SNODP",
        "merra2_SNODP_2deg.nc", "cm", "cm per decade", palette="BrBG",
        words={"neg": "thinner snow", "pos": "deeper snow"}, adj={"neg": "thinner", "pos": "deeper"},
        up="seeing deeper snow", down="seeing thinner snow",
        noun="deepening of the snow", noun_down="thinning of the snow", subject="the snow",
        units_long="in centimetres, averaged over the whole year and the whole area",
        map_title="Where is the snow getting thinner or deeper?", raw_label="Monthly snow depth (cm)",
        decimals=(2, 1, 2), percent=False, topic="snow_ice", mask="land", map_only=True),
    "sea_ice": _v(
        "sea_ice_fraction_power", "Sea ice", "Share of the sea covered by ice", "FRSEAICE",
        "merra2_FRSEAICE_2deg.nc", "%", "percentage points per decade", palette="BrBG",
        words={"neg": "less ice", "pos": "more ice"}, adj={"neg": "smaller", "pos": "larger"},
        up="gaining sea ice", down="losing sea ice", noun="gain in sea ice", noun_down="loss of sea ice",
        subject="sea ice", units_long="in percent of the sea surface covered by ice",
        map_title="Where is sea ice shrinking or growing?", raw_label="Monthly sea-ice cover (%)",
        decimals=(1, 1, 1), percent=False, topic="snow_ice", mask="ocean", scale=100.0, map_only=True),
    "sunlight": _v(
        "solar_radiation_power", "Sunlight", "Sunlight reaching the ground", "ALLSKY_SFC_SW_DWN",
        "syn1deg_ALLSKY_SFC_SW_DWN_2deg.nc", "MJ/m²/day", "MJ/m²/day per decade", palette="PuOr",
        words={"neg": "dimmer", "pos": "brighter"}, adj={"neg": "weaker", "pos": "stronger"},
        up="getting more sunlight", down="getting less sunlight",
        noun="brightening", noun_down="dimming", subject="sunlight",
        units_long="energy from the Sun reaching the ground each day, after clouds and haze",
        map_title="Where is the ground getting more or less sunlight?",
        raw_label="Monthly sunlight at the ground (MJ/m²/day)", decimals=(2, 2, 2), percent=True,
        topic="sunlight", scale=0.0864, start=2001, source="NASA CERES SYN1deg (via POWER)",
        extreme=_ex("sunny_months", "upper", "Very sunny months", "sunnier")),
    "haze": _v(
        "aerosol_optical_depth_power", "Haze", "Haze in the air (aerosol optical depth)", "AOD_55_ADJ",
        "syn1deg_AOD_55_ADJ_2deg.nc", "AOD", "AOD per decade", palette="PuOr",
        words={"neg": "less haze", "pos": "more haze"}, adj={"neg": "thinner", "pos": "thicker"},
        up="getting hazier", down="getting less hazy",
        noun="increase in haze", noun_down="decrease in haze", subject="haze",
        units_long="how much dust, smoke and pollution particles dim the light (0 = perfectly clear)",
        map_title="Where is the air getting hazier or cleaner?", raw_label="Monthly haze (aerosol optical depth)",
        decimals=(3, 3, 3), percent=True, topic="air", start=2001,
        source="NASA CERES SYN1deg (via POWER)", zero_is_missing=True,
        extreme=_ex("hazy_months", "upper", "Very hazy months", "hazier")),
    "ozone": _v(
        "total_ozone_power", "Ozone layer", "Ozone layer (total ozone)", "TO3",
        "merra2_TO3_2deg.nc", "DU", "DU per decade", palette="PuOr",
        words={"neg": "thinner", "pos": "thicker"}, adj={"neg": "thinner", "pos": "thicker"},
        up="getting a thicker ozone layer", down="getting a thinner ozone layer",
        noun="thickening of the ozone layer", noun_down="thinning of the ozone layer",
        subject="the ozone layer", units_long="in Dobson units; about 300 is typical",
        map_title="Where is the ozone layer getting thinner or thicker?",
        raw_label="Monthly total ozone (Dobson units)", decimals=(1, 1, 1), percent=True, topic="air",
        extreme=_ex("thin_ozone_months", "lower", "Months with very thin ozone", "thinner")),
}
CORE = ("t2m", "precip", "soil")  # variables with daily inputs and the climate_stats deeper checks

CASES = [
    {"id": "01", "slug": "grandmas-drought", "title": "Grandma's drought",
     "question": "Is the soil in southern Ukraine drying out?",
     "teaser": "Grandma says her garden needs more watering every year. Is she right?",
     "variable_id": "soil", "region_id": "south_ukraine"},
    {"id": "02", "slug": "ukraine-warming", "title": "Is Ukraine getting warmer?",
     "question": "Is Ukraine getting warmer, and in which season the most?",
     "teaser": "Winters without snow, summers that do not end. What do {years} years of data say?",
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


# --------------------------------------------------------------------------- real inputs
def month_index(start_year: int, end_year: int) -> pd.DatetimeIndex:
    return pd.date_range(f"{start_year}-01-01", f"{end_year}-12-01", freq="MS")


def last_complete_year(index: pd.DatetimeIndex) -> int:
    """Last calendar year with all 12 months present in a monthly index."""
    counts = pd.Series(1, index=index).groupby(index.year).sum()
    full = counts[counts == 12]
    return int(full.index.max())


class Grid:
    """One 2-degree monthly grid from data/cache/grids/ (built by trend_detective.grids)."""

    def __init__(self, var: str):
        spec = VARIABLES[var]
        self.path = GRIDS / spec["grid"]
        ds = xr.open_dataset(self.path)
        name = spec["grid_var"] if spec["grid_var"] in ds.data_vars else next(
            v for v in ds.data_vars if v != "valid_fraction")
        da = ds[name]
        self.time = pd.DatetimeIndex(ds["time"].values)
        self.lat = ds["lat"].values.astype(float)
        self.lon = ds["lon"].values.astype(float)
        self.values = da.transpose("time", "lat", "lon").values.astype(float) * spec["scale"]
        if spec["zero_is_missing"]:  # aerosol optical depth 0.000 = no retrieval (low sun, snow or ice)
            self.values[self.values == 0] = np.nan
        ds.close()
        self.LON, self.LAT = np.meshgrid(self.lon, self.lat)
        sidecar = self.path.with_name(self.path.name + ".provenance.json")
        self.provenance = json.loads(sidecar.read_text(encoding="utf-8"))

    def annual_means(self) -> np.ndarray:
        """(years, lat, lon) mean of the 12 calendar months; NaN unless all 12 months exist."""
        out = np.full((Y1 - Y0 + 1,) + self.LAT.shape, np.nan)
        years = self.time.year
        for k, y in enumerate(range(Y0, Y1 + 1)):
            sel = years == y
            if sel.sum() != 12:
                continue
            block = self.values[sel]
            ok = np.isfinite(block).all(axis=0)
            out[k] = np.where(ok, block.mean(axis=0), np.nan)
        return out


def map_layer(grid: Grid, var: str) -> tuple[dict, dict]:
    """Per-cell Sen slope and Yue-Wang MK on annual means, then BH FDR across cells."""
    years = np.arange(Y0, Y1 + 1)
    n = years.size
    series = grid.annual_means()                                                 # (n, lat, lon)
    Y = series.reshape(n, -1).T                                                 # (cells, n)

    valid = np.isfinite(Y).all(axis=1)
    valid[valid] = np.std(Y[valid], axis=1) > 0
    valid[valid] = (Y[valid] != 0).sum(axis=1) >= MAP_MIN_NONZERO_YEARS
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
        ties = np.zeros(sel.size)  # tie term of Var(S), as in trend_stats.mann_kendall
        ys = np.sort(y, axis=1)
        for q in np.flatnonzero((np.diff(ys, axis=1) == 0).any(axis=1)):
            c = np.unique(ys[q], return_counts=True)[1]
            ties[q] = float((c * (c - 1) * (2 * c + 5)).sum()) / 18.0
        z = (s - np.sign(s)) / np.sqrt((var0 - ties) * eta)
        slope[sel] = sen * 10
        pval[sel] = 2 * stats.norm.sf(np.abs(z))
    sig = np.zeros(Y.shape[0], dtype=bool)
    ok = np.isfinite(pval)
    sig[ok], _ = ts.fdr_bh(pval[ok], q=FDR_MAP_Q)

    spec = VARIABLES[var]
    finite = np.abs(slope[np.isfinite(slope)])
    raw_lim = float(np.percentile(finite, 98))
    nice = [0.005, 0.01, 0.02, 0.03, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0,
            2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 15.0, 20.0, 30.0, 50.0, 100.0]
    limit = next((v for v in nice if v >= raw_lim), nice[-1])
    d = spec["rate_decimals"] + 1
    bins = 11
    edges = [-limit + 2 * limit * i / bins for i in range(bins + 1)]
    dlat = float(grid.lat[1] - grid.lat[0])
    dlon = float(grid.lon[1] - grid.lon[0])
    layer = {
        "schema_version": SCHEMA_VERSION,
        "variable_id": var,
        "period": {"start": f"{Y0}-01", "end": f"{Y1}-12"},
        "grid": {"lat0": float(grid.lat[0]), "lon0": float(grid.lon[0]), "dlat": dlat, "dlon": dlon,
                 "nlat": int(grid.lat.size), "nlon": int(grid.lon.size),
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
            "ticks": [{"value": v, "text": "0" if v == 0 else fmt(v, d - 1)}
                      for v in (-limit, -limit / 2, 0, limit / 2, limit)],
            "min_text": f"≤ {fmt(-limit, d - 1)}", "max_text": f"≥ {fmt(limit, d - 1)}",
        },
        "units_label": spec["rate_units"],
        "words": spec["words"],
        "fdr_q": FDR_MAP_Q,
        "mask": spec["mask"],
        "caption": (f"{spec['source']} {spec['parameter']} · {Y0}–{Y1} · Sen's slope of yearly means in "
                    f"each {dlat:g}° square. Strong colour: passes the map-wide test for false alarms "
                    f"(Mann-Kendall with memory correction, q = {FDR_MAP_Q}). This map enlarges areas near "
                    "the poles."),
        "provenance": provenance_from(grid.provenance, spec, "map"),
    }
    cells = {"slope": slope.reshape(grid.LAT.shape), "sig": sig.reshape(grid.LAT.shape),
             "LAT": grid.LAT, "LON": grid.LON}
    return layer, cells


def provenance_from(prov: dict, spec: dict, what: str) -> dict:
    """App provenance block built from the cache sidecar of the file actually used."""
    accessed = str(prov.get("accessed", ""))[:10] or None
    processing = [str(p) for p in prov.get("processing", [])][:3]
    if what == "map":
        processing += [f"yearly means of complete years {Y0}–{Y1} in each 2° square",
                       "per-square Sen's slope and Mann-Kendall (Yue-Wang), BH FDR across squares "
                       "(trend_stats.py)"]
    else:
        if what == "country":
            processing = processing[:2] + [
                "country value = mean of the 2° map squares that overlap the country, weighted by the "
                "overlapping area (mainland and islands within about 1,000 km)"]
        processing += [f"monthly series {Y0}-01 to {Y1}-12 (complete years)",
                       "anomalies from the calendar-month normal; Sen's slope, Mann-Kendall (Yue-Wang), "
                       "OLS with effective sample size (trend_stats.py)"]
    if "CERES" in spec["source"]:
        about = "Data: NASA CERES SYN1deg, built from satellite measurements, about 100 km squares"
    elif "IMERG" in spec["source"]:
        about = ("Data: NASA GPM IMERG, rainfall estimated from satellites, about 10 km squares; the "
                 "satellites changed in 2014 (TRMM to GPM)")
    else:
        about = "Data: MERRA-2 reanalysis, a weather model corrected by observations, about 50 km squares"
    if what == "map":
        about += " (the map averages them into 2° squares)"
    elif what == "country":
        about += " (averaged into 2° squares; coastal squares include some sea)"
    return {
        "dataset": f"{spec['source']} · {spec['parameter']}",
        "version": prov.get("version"),
        "doi": prov.get("doi"),
        "landing_page": prov.get("landing_page") or "https://power.larc.nasa.gov/",
        "accessed": accessed,
        "processing": processing,
        "synthetic": False,
        "caveat": (about + f". The trend is a straight line through {Y0}–{Y1}; it shows what changed, not why."
                   + (f" The record is {Y1 - Y0 + 1} years long, shorter than the 30 years usually used to "
                      "describe a climate." if Y1 - Y0 + 1 < 30 else "")
                   + (" " + prov["_caution"] if prov.get("_caution") else "")),
    }


# --------------------------------------------------------------------------- regional series
def region_mask(cells: dict, geom) -> np.ndarray:
    m = contains_xy(geom, cells["LON"], cells["LAT"])
    if m.sum() < 3:  # small region: take the squares whose centre is within about one square
        m = contains_xy(geom.buffer(1.5), cells["LON"], cells["LAT"])
    return m


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
GENERIC_SEASON_VERB = ("changing", "change fastest")


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


def monthly_level(dates, raw) -> str:
    """The app's verdict rule (weaker of MK-CI level and OLS-p level) for one monthly series."""
    anom, _ = ts.deseasonalize(dates, raw)
    t = ts.decimal_years(dates)
    mk = ts.mann_kendall(t, anom, method="yue_wang")
    cis = [[c * 10 for c in ts.sens_slope(t, anom, alpha=a, var_s=mk["var_s"])["ci"]] for a in (0.10, 0.05, 0.01)]
    res = ts.analyze_series(dates, raw)
    return weaker(level_from_cis(*cis), level_from_p(res["ols"]["p"]))


def yearly_level(dates, raw) -> str:
    anom, _ = ts.deseasonalize(dates, raw)
    years = dates.astype("datetime64[Y]").astype(int) + 1970
    ys = np.arange(Y0, Y1 + 1)
    vals = np.array([anom[years == y].mean() for y in ys])
    r = annual_trend(ys, vals)
    t = ys.astype(float)
    mk = ts.mann_kendall(t, vals, method="yue_wang")
    cis = [[c * 10 for c in ts.sens_slope(t, vals, alpha=a, var_s=mk["var_s"])["ci"]] for a in (0.10, 0.05, 0.01)]
    return weaker(level_from_cis(*cis), level_from_p(r["ols"]["p"]))


def robustness(dates, raw, level: str) -> dict:
    """Pre-declared sensitivity checks, the same for every region and variable: the verdict rule
    repeated without the first two years, without the last two years, and on yearly means.
    The headline verdict is the most cautious of the full-record result and these three; when they
    differ, the line under the verdict says which calculation gave what."""
    if level == "insufficient":
        return {"checks": [], "text": None, "level": level}
    years = dates.astype("datetime64[Y]").astype(int) + 1970
    checks = []
    for label, sel in ((f"leaving out {Y0}–{Y0 + 1}", years >= Y0 + 2),
                       (f"leaving out {Y1 - 1}–{Y1}", years <= Y1 - 2)):
        checks.append((label, monthly_level(dates[sel], raw[sel])))
    checks.append(("using one average per year", yearly_level(dates, raw)))
    final = level
    for _, lv in checks:
        final = weaker(final, lv)
    differ = [(lbl, lv) for lbl, lv in checks if lv != level]
    if not differ:
        return {"checks": checks, "level": final,
                "text": "Same verdict without the first or last two years and with yearly averages."}
    parts = [f"{lbl}: {LEVEL_WORD[lv].lower()}" for lbl, lv in differ]
    return {"checks": checks, "level": final,
            "text": (f"Stability checks: full record: {LEVEL_WORD[level].lower()}; " + "; ".join(parts)
                     + ". We report the most cautious.")}


def analyse(var, region, cells, raw, prov):
    """Full analysis of one monthly series (already in app units, complete for Y0..Y1)."""
    spec = VARIABLES[var]
    name_s = sentence_name(region)
    dates = month_index(Y0, Y1).values.astype("datetime64[M]").astype("datetime64[D]")
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
    full_level = weaker(mk_level, ols_level) if record_years >= 10 else "insufficient"
    robust = robustness(dates, raw, full_level)
    level = robust["level"]  # the most cautious of: full record, without first/last two years, yearly means
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
    if robust["text"]:
        how_sure += " · " + robust["text"]
    # the same verdict in plain words; the statistics stay one click away
    sure_plain = {
        "strong": "Very sure. A drift this large would be very rare if nothing were really changing.",
        "moderate": "Fairly sure. A drift like this would be unusual if nothing were changing.",
        "weak": "Not sure. There is a hint, but it could still be ordinary ups and downs.",
        "none": "No clear signal. The change so far is within normal year-to-year swings.",
        "insufficient": "Cannot say. The record is too short or too patchy.",
    }[level]
    if level != full_level:
        sure_plain += (" The full record alone looks stronger, but that does not hold up in our stability "
                       "checks, so we stay cautious.")
    if disagree:
        sure_plain += " Our two tests disagree, so we report the more cautious verdict."
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
    extremes = None
    if ex:
        b0, b1 = baseline_years()
        threshold_text = f"{ex['adj']} than 9 in 10 months of {b0}–{b1}"
        base = (dates >= np.datetime64(f"{b0}-01-01")) & (dates <= np.datetime64(f"{b1}-12-31"))
        thr = np.percentile(anom[base], 90 if ex["tail"] == "upper" else 10)
        hit = anom > thr if ex["tail"] == "upper" else anom < thr
        counts = np.array([int(hit[(dates >= np.datetime64(f"{y}-01-01"))
                                   & (dates < np.datetime64(f"{y + 1}-01-01"))].sum()) for y in yrs])
        ex_r = annual_trend(yrs, counts.astype(float))
        family.append(("extremes", ex["kind"], ex_r["mk"]["p"]))
        early, late = float(counts[:10].mean()), float(counts[-10:].mean())
        extremes = {"kind": ex["kind"], "label": ex["label"], "threshold_text": threshold_text,
                    "years": yrs.tolist(), "counts": counts.tolist(),
                    "sen_per_decade": round(ex_r["sen_slope_per_decade"], 2), "p": round(ex_r["mk"]["p"], 4),
                    "early": {"label": f"{Y0}–{Y0 + 9}", "mean_per_year": round(early, 1), "years": [Y0, Y0 + 9]},
                    "late": {"label": f"{Y1 - 9}–{Y1}", "mean_per_year": round(late, 1),
                             "years": [Y1 - 9, Y1]}}

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
    if extremes:
        extremes["q"] = round(qmap[("extremes", ex["kind"])], 4)
        extremes["passes_fdr"] = extremes["q"] <= FDR_INSIGHT_Q
        extremes["display"] = {
            "subtitle": f"Months per year that were {extremes['threshold_text']}.",
            "trend_text": (f"From about {extremes['early']['mean_per_year']:g} a year in "
                           f"{extremes['early']['label']} to about {extremes['late']['mean_per_year']:g} a year "
                           f"in {extremes['late']['label']}."
                           if extremes["passes_fdr"] else "The change in this count could still be chance."),
        }

    # --- spatial sign split (S9)
    w = np.cos(np.deg2rad(cells["LAT"])) * region["mask"] * np.isfinite(cells["slope"])
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
                    "answer": answer, "how_sure": how_sure, "sure_plain": sure_plain, "methods_disagree": disagree,
                    "decided_by": decided_by, "disagree_text": disagree_text,
                    "full_record_level": full_level},
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
        "deeper_checks": None,
        "provenance": provenance_from(prov, spec, "country" if region.get("weights") is not None else "region"),
        "_internal": {"family": family, "qmap": qmap, "spec": spec, "prov": prov,
                      "region": {"id": region["id"], "name": region["name"], "kind": region["kind"]},
                      "what": "country" if region.get("weights") is not None else "region",
                      "total": total, "pct": pct_total, "unit": unit},
    }


# --------------------------------------------------------------------------- insights
def change_phrase(a: dict) -> str:
    """'about 19% drier' / 'about 4.4 percentage points drier' / 'about 2.6 °C warmer'."""
    i, spec = a["_internal"], a["_internal"]["spec"]
    adj = spec["adj"]["pos"] if i["total"] > 0 else spec["adj"]["neg"]
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
        text = f"Since {Y0} {spec['subject']} got {change_phrase(a)}."
        if spec["percent"] and tr["percent_change"] is not None:
            detail = (f"Total change {tr['display']['total_value']} {tr['display']['total_unit']} "
                      f"({tr['display']['total_range']}); as a share of the average: {tr['display']['percent_range']}.")
        else:
            detail = f"Total change {tr['display']['total_value']} {tr['display']['total_unit']} ({tr['display']['total_range']})."
        ins.append({"kind": "total_change", "text": text, "detail": detail, "evidence_level": level,
                    "tested": False, "methods_anchor": "trend-test", "numbers": {"total": tr["total_change"]}})
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
        verb, verb_fast = (spec["season_verbs"] or {}).get(noun, GENERIC_SEASON_VERB)
        same_sign = np.sign(fast["sen_per_decade"]) == np.sign(slow["sen_per_decade"])
        units = spec["rate_units"]
        if fast["passes_fdr"] and apart and slow["passes_fdr"] and same_sign:
            r = abs(fast["sen_per_decade"]) / max(abs(slow["sen_per_decade"]), 1e-9)
            tw = times_word(r) or "faster than"
            ins.append({"kind": "season", "text": f"{fast['label']}s are {verb} {tw} {slow['label'].lower()}s.",
                        "detail": (f"{fast['label']}: {fast['display']} {units} ({fast['ci_text']}). "
                                   f"{slow['label']}: {slow['display']} {units} ({slow['ci_text']})."),
                        "evidence_level": "moderate", "tested": True, "methods_anchor": "seasons",
                        "numbers": {"fast": fast["sen_per_decade"], "slow": slow["sen_per_decade"]}, "q": fast["q"]})
        elif fast["passes_fdr"] and apart:
            ins.append({"kind": "season",
                        "text": f"{fast['label']}s {verb_fast}; {slow['label'].lower()}s show no clear change.",
                        "detail": (f"{fast['label']}: {fast['display']} {units} ({fast['ci_text']}). "
                                   f"{slow['label']}: {slow['display']} {units} ({slow['ci_text']})."),
                        "evidence_level": "moderate", "tested": True, "methods_anchor": "seasons",
                        "numbers": {"fast": fast["sen_per_decade"], "slow": slow["sen_per_decade"]}, "q": fast["q"]})
        else:
            others = [s_["sen_per_decade"] for s_ in ss[1:]]
            o_lo, o_hi = min(others), max(others)
            ins.append({"kind": "season_unresolved",
                        "text": (f"{fast['label']} shows the fastest {noun}, but the seasons are still too "
                                 "close to tell apart."),
                        "detail": (f"{fast['label']}: {fast['display']} {units}; the other seasons "
                                   f"{fmt(o_lo, spec['rate_decimals'])} to {fmt(o_hi, spec['rate_decimals'])}. "
                                   "Their 95% ranges overlap."),
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
    if ex and ex["passes_fdr"]:
        more = ex["late"]["mean_per_year"] > ex["early"]["mean_per_year"]
        ins.append({"kind": "extremes",
                    "text": f"{ex['label']} have become {'more' if more else 'less'} common.",
                    "detail": (f"About {ex['early']['mean_per_year']:g} a year in {ex['early']['label']}, about "
                               f"{ex['late']['mean_per_year']:g} a year in {ex['late']['label']}. Counted: months "
                               f"{ex['threshold_text']}."),
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
    checks = "12 months, 4 seasons, extreme months" if a["extremes"] else "12 months and 4 seasons"
    lead = f"Besides the main test, we ran {au['tested']} follow-up checks ({checks})."
    if au["passed"] and au["shown"] == 0 and LEVEL_RANK[level] < 2:
        au["text"] = (f"{lead} {au['passed']} held up after correcting for running many tests at once "
                      f"(q = {au['q']}), but we do not report them as findings while the main trend itself is not "
                      "clear.")
    elif au["passed"]:
        au["text"] = (f"{lead} {au['passed']} held up after correcting for running many tests at once "
                      f"(false discovery rate q = {au['q']}); most of them repeat the main trend month by month. "
                      "Findings marked “follow-up check” come from these checks.")
    else:
        au["text"] = (f"{lead} None held up after correcting for running many tests at once "
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
            "provenance": provenance_from(a["_internal"]["prov"], spec, a["_internal"]["what"])}


# --------------------------------------------------------------------------- deeper checks (climate_stats)
# Which pipeline results each variable page shows. Fixed by what the variable is about, not by
# the results: every listed row is shown, clear or not (plan v2: non-significant results count).
# (kind, key, label, explain, unit_text, decimals)
CHECKS = {
    "t2m": [
        ("index", ("tmax", "su"), "Summer days", "Days a year when the region-average afternoon high is above 25 °C.", "days a year", 1),
        ("index", ("tmin", "fd"), "Frost nights", "Days a year when the region-average night-time low drops below 0 °C.", "days a year", 1),
        ("index", ("tmax", "txx"), "Hottest day of the year", "The highest region-average afternoon temperature of each year.", "°C", 2),
        ("index", ("tmin", "tnn"), "Coldest night of the year", "The lowest region-average night-time temperature of each year.", "°C", 2),
        ("index", ("tmax", "tx90p"), "Unusually hot days",
         "Share of days whose region-average high beats 9 in 10 days at the same time of year in 1981–2010.", "% of days", 2),
        ("gsl", None, "Growing season", "Days between the first warm spell (6 days above 5 °C) and the first "
         "cold spell after midsummer.", "days", 1),
        ("index", ("tmin", "last_frost_doy"), "Last spring frost",
         "The day of the year of the last night below 0 °C before July; a negative change means earlier.",
         "days", 1),
    ],
    "precip": [
        ("index", ("precip", "rx1day"), "Wettest day of the year", "The most region-average rain on a single day each year.", "mm", 2),
        ("index", ("precip", "rx5day"), "Wettest five days", "The most region-average rain in five days in a row each year.", "mm", 1),
        ("index", ("precip", "cdd"), "Longest dry spell", "The longest run of days a year with less than 1 mm of region-average rain.", "days", 1),
        ("index", ("precip", "sdii"), "Rain on a wet day", "Average rain (region average) on days with at least 1 mm.", "mm", 2),
        ("drought", "spi3", "Rain-only drought index (3 months)",
         "SPI: how unusual the rain of June to August was; below zero is drier than normal.", "index points", 2),
        ("drought", "spi6", "Rain-only drought index (6 months)",
         "SPI over March to August; below zero is drier than normal.", "index points", 2),
    ],
    "soil": [
        ("drought", "spei3", "Water-balance drought index (3 months)",
         "SPEI: rain minus the water that warm air can pull out of the ground, June to August; below zero "
         "is drier than normal.", "index points", 2),
        ("drought", "spei6", "Water-balance drought index (6 months)",
         "SPEI over March to August; below zero is drier than normal.", "index points", 2),
        ("drought", "spi6", "Rain-only drought index (6 months)",
         "SPI over March to August, rain only. If SPEI falls but SPI does not, heat rather than missing rain "
         "is drying the land.", "index points", 2),
    ],
}
METHOD_CHECKS = [
    ("bootstrap", "Rate checked another way",
     "Block bootstrap: we resample whole years of the record 999 times instead of relying on a formula."),
    ("acceleration", "Faster or slower lately?",
     "Compares the rate in the second half of the record with the first half (split fixed in advance)."),
    ("variability", "Years more uneven?",
     "Compares the size of year-to-year swings in the two halves of the record."),
    ("change_point", "A sudden jump?",
     "Pettitt test: looks for one year where the level shifts abruptly, e.g. after an instrument change."),
]
STATUS_TEXT = {"clear": "Clear change", "not_clear": "No clear change", "unavailable": "Not available here"}


def cs_values(s: pd.Series, daily: bool) -> list[dict]:
    fmt_ = "%Y-%m-%d" if daily else "%Y-%m"
    return [{"date": d.strftime(fmt_), "value": None if not np.isfinite(v) else float(v)} for d, v in s.items()]


def doc_hash(doc: dict) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def stats_document(region: dict, bootstrap: int) -> dict | None:
    """Input document for trend_detective.climate_stats for one region (real cached data)."""
    rid, lat = region["id"], float(region["centroid"][1])
    src = region["preset"]  # the area the numbers are averaged over (real borders for Europe)
    common = {"region_id": rid, "latitude": lat}
    series = []
    for var, cid, units in (("t2m", "air_temperature_power", "degC"), ("soil", "root_zone_soil_wetness_power", "1")):
        s = acquire.get_series(cid, src)
        s = s[(s.index.year >= Y0) & (s.index.year <= Y1)]
        series.append({"id": var, "variable_id": cid, "frequency": "monthly", "units": units,
                       "values": cs_values(s, False), **common})
    daily_ok = True
    daily = {}
    for key, param in DAILY.items():
        try:
            d = acquire.get_input_series(param, src, store="merra2_daily")
        except Exception:  # noqa: BLE001 - not every region has daily inputs in the cache
            daily_ok = False
            break
        if not d.attrs.get("from_cache", True):
            raise RuntimeError(f"daily {param} / {rid} did not come from the cache")
        daily[key] = d[(d.index.year >= Y0) & (d.index.year <= Y1)]
    if daily_ok:
        series += [
            {"id": "tmax", "variable_id": "T2M_MAX", "frequency": "daily", "units": "degC",
             "values": cs_values(daily["tmax"], True), **common},
            {"id": "tmin", "variable_id": "T2M_MIN", "frequency": "daily", "units": "degC",
             "values": cs_values(daily["tmin"], True), **common},
            # one precipitation source only, so drought indices are not tested twice
            {"id": "precip", "variable_id": "precipitation_power", "frequency": "daily", "units": "mm/day",
             "values": cs_values(daily["precip"], True), **common},
        ]
    else:
        s = acquire.get_series("precipitation_power", src)
        s = s[(s.index.year >= Y0) & (s.index.year <= Y1)]
        series.append({"id": "precip", "variable_id": "precipitation_power", "frequency": "monthly",
                       "units": "mm/day", "values": cs_values(s, False), **common})
    return {
        "schema_version": "1.0",
        "metadata": {"project": "Earth System Trend Detective web app", "region_id": rid, "region_preset": src,
                     "source": "data/cache (NASA POWER MERRA-2, frozen; see MANIFEST.json)",
                     "period": f"{Y0}-01 to {Y1}-12"},
        "config": {"baseline": [1981, 2010], "alpha": 0.05, "fdr_q": 0.05, "bootstrap_samples": bootstrap,
                   "seed": 1729, "include_series": False,
                   "methods": ["trend", "monthly_profile", "seasonal", "emergence", "probability",
                               "acceleration", "variability", "bootstrap", "change_point", "indices", "drought"]},
        "series": series,
    }


def _trend_row(t: dict | None, scale: float, d: int) -> dict:
    """Display fields from one climate_stats trend object."""
    if not isinstance(t, dict) or t.get("status") != "ok" or not t.get("inference_available", True):
        reason = (t or {}).get("reason") if isinstance(t, dict) else None
        return {"status": "unavailable", "reason": reason}
    sen = t["sen"]
    rate = sen["slope_per_decade"] * scale
    ci = [c * scale for c in sen["ci_per_decade"]] if sen.get("ci_per_decade") else None
    clear = bool(t.get("conservative_significant_fdr"))
    return {
        "status": "clear" if clear else "not_clear",
        "rate": round(rate, d + 2), "ci95": None if ci is None else [round(c, d + 2) for c in ci],
        "value_text": fmt(rate, d), "range_text": None if ci is None else range_text(ci[0], ci[1], d),
        "q": None if t["mann_kendall"].get("q_value") is None else round(t["mann_kendall"]["q_value"], 4),
        "methods_disagree": bool(t.get("methods_disagree")),
        "warnings": [str(w) for w in t.get("warnings", [])],
    }


def deeper_checks(var: str, out: dict, region_id: str) -> dict:
    """Compact, display-ready rows for one (region, variable) page from a climate_stats output."""
    spec = VARIABLES[var]
    S = out.get("series", {})
    der = out.get("derived", {}).get(region_id, {})
    rows = []
    for kind, key, label, explain, unit, d in CHECKS[var]:
        if kind == "index":
            sid, idx = key
            di = S.get(sid, {}).get("daily_indices", {})
            obj = (di.get("indices") or {}).get(idx) if isinstance(di, dict) else None
            t = obj.get("trend") if isinstance(obj, dict) else None
            path = f"/series/{sid}/daily_indices/indices/{idx}/trend"
            caveat = obj.get("caveat") if isinstance(obj, dict) else None
        elif kind == "gsl":
            obj = der.get("temperature", {}).get("gsl")
            t = obj.get("trend") if isinstance(obj, dict) else None
            path = "/derived/" + region_id + "/temperature/gsl/trend"
            caveat = obj.get("caveat") if isinstance(obj, dict) else None
        else:  # drought index, from the single precipitation source
            src = (der.get("drought", {}).get("sources") or {}).get("precip", {})
            obj = (src.get("indices") or {}).get(key)
            t = obj.get("trend") if isinstance(obj, dict) else None
            path = f"/derived/{region_id}/drought/sources/precip/indices/{key}/trend"
            caveat = None
        row = {"id": f"{kind}:{key if isinstance(key, str) else '/'.join(key) if key else kind}",
               "group": "events", "label": label, "explain": explain, "unit": f"{unit} per decade",
               "path": path, **_trend_row(t, 1.0, d)}
        if row["status"] == "unavailable" and not row.get("reason"):
            row["reason"] = "needs daily data, which we have only for the four European case regions"
        if caveat and isinstance(caveat, str):
            row["warnings"] = row.get("warnings", []) + [caveat]
        row["status_text"] = STATUS_TEXT[row["status"]]
        rows.append(row)

    main = S.get(var, {})
    scale = spec["scale"]
    rd = spec["rate_decimals"]
    for method, label, explain in METHOD_CHECKS:
        m = main.get(method)
        row = {"id": f"method:{method}", "group": "method", "label": label, "explain": explain,
               "unit": spec["rate_units"], "path": f"/series/{var}/{method}", "warnings": []}
        if not isinstance(m, dict) or m.get("status") != "ok":
            row.update({"status": "unavailable", "reason": (m or {}).get("reason") if isinstance(m, dict) else None})
        elif method == "bootstrap":
            ci = [c * scale for c in m["ci"]]
            row.update({"status": "clear" if m.get("significant_fdr") else "not_clear",
                        "rate": round(m["estimate_per_decade"] * scale, rd + 2), "ci95": [round(c, rd + 2) for c in ci],
                        "value_text": fmt(m["estimate_per_decade"] * scale, rd),
                        "range_text": range_text(ci[0], ci[1], rd), "q": round(m["q_value"], 4)})
        elif method == "acceleration":
            dt_ = m.get("difference_test") or {}
            diff = (m.get("difference_per_decade") or 0.0) * scale
            ci = dt_.get("ci")
            first, second = m.get("first", {}), m.get("second", {})
            r1 = first.get("sen", {}).get("slope_per_decade")
            r2 = second.get("sen", {}).get("slope_per_decade")
            sy = m.get("split_year")
            row.update({"status": "clear" if dt_.get("significant_fdr") else "not_clear",
                        "rate": round(diff, rd + 2), "value_text": fmt(diff, rd),
                        "ci95": None if not ci else [round(c * scale, rd + 2) for c in ci],
                        "range_text": None if not ci else range_text(ci[0] * scale, ci[1] * scale, rd),
                        "q": None if dt_.get("q_value") is None else round(dt_["q_value"], 4),
                        "detail": (None if r1 is None or r2 is None else
                                   f"{Y0}–{sy}: {fmt(r1 * scale, rd)} · {sy + 1}–{Y1}: {fmt(r2 * scale, rd)} "
                                   f"{spec['rate_units']}"),
                        "unit": (f"{spec['rate_units']}, {sy + 1}–{Y1} minus {Y0}–{sy}" if sy
                                 else spec["rate_units"])})
        elif method == "variability":
            bt = m.get("block_test") or {}
            ratio = m.get("ratio")
            sy = m.get("split_year")
            row.update({"status": "clear" if bt.get("significant_fdr") else "not_clear",
                        "rate": None if ratio is None else round(ratio, 3),
                        "value_text": None if ratio is None else f"×{ratio:.2f}",
                        "range_text": None, "q": None if bt.get("q_value") is None else round(bt["q_value"], 4),
                        "unit": f"size of swings in {sy + 1}–{Y1} compared with {Y0}–{sy}" if sy else "ratio"})
        else:  # change_point
            inf = m.get("inference") or {}
            yb = m.get("last_year_before_candidate_break")
            row.update({"status": "clear" if inf.get("significant_fdr") else "not_clear",
                        "rate": None, "value_text": None if yb is None else f"after {yb}",
                        "range_text": None, "q": None if inf.get("q_value") is None else round(inf["q_value"], 4),
                        "unit": "most likely year of a jump"})
        row["status_text"] = STATUS_TEXT[row["status"]]
        rows.append(row)

    audit = out.get("insights_audit", {})
    n_clear = sum(1 for r in rows if r["status"] == "clear")
    n_avail = sum(1 for r in rows if r["status"] != "unavailable")
    return {
        "rows": rows,
        "shown": len(rows), "available": n_avail, "clear": n_clear,
        "family_tests": int(audit.get("tested", 0)), "q": float(audit.get("q_threshold", 0.05)),
        "source_file": f"stats/{region_id}.json",
        "pipeline_version": out.get("pipeline_version"),
        "text": (f"{n_clear} of {n_avail} extra checks show a clear change. Day counts use the region's "
                 "average daily values; averaging smooths out extremes, so they differ from counts at one weather station. "
                 f"“Clear” means both of the "
                 f"pipeline's tests pass after correcting for all {int(audit.get('tested', 0))} tests run for this "
                 f"region (false discovery rate q = {audit.get('q_threshold', 0.05)}). Rows that are not clear are "
                 "shown too: no change is also a result."),
    }


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
        return "Not proven. " + v["answer"], v["headline"], v["level"]
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
            "variables": out, "synthetic": False}


# --------------------------------------------------------------------------- regions
# Three kinds of region, all with real data:
#   story    the five prepared regions (native ~50 km series from the cache, plus deeper checks)
#   country  countries of the world; value = area-weighted mean of the 2° map squares they overlap
#   world    the IPCC AR6 land reference regions (native series from the cache)
BASEMAP_COUNTRIES = ROOT / "frontend" / "public" / "basemap" / "countries.geojson"
COUNTRY_MIN_KM2 = 20_000          # smaller countries cover well under one 2° square
COUNTRY_CLUSTER_DEG = 9.0         # keep parts within about 1,000 km of the mainland (chain rule)
COUNTRY_SKIP = {"ATA", "UKR", "SOL", "CYN", "KAS"}  # Antarctica; Ukraine is a story region; disputed areas
COUNTRY_NAMES = {
    "United States of America": "United States", "Dem. Rep. Congo": "DR Congo",
    "Central African Rep.": "Central African Republic", "Dominican Rep.": "Dominican Republic",
    "Eq. Guinea": "Equatorial Guinea", "S. Sudan": "South Sudan", "W. Sahara": "Western Sahara",
    "Bosnia and Herz.": "Bosnia and Herzegovina", "Solomon Is.": "Solomon Islands",
    "Falkland Is.": "Falkland Islands", "Congo": "Republic of the Congo", "eSwatini": "Eswatini",
    "Czechia": "Czechia", "N. Cyprus": "Northern Cyprus", "Fr. S. Antarctic Lands": "French Southern Lands",
}
THE = {"United States", "United Kingdom", "Netherlands", "Philippines", "United Arab Emirates",
       "Central African Republic", "Dominican Republic", "Republic of the Congo", "Bahamas", "Gambia",
       "Solomon Islands", "Falkland Islands", "Maldives"}


def story_regions() -> dict:
    """The prepared regions in data/regions/regions.geojson that have a preset with cached data."""
    fc = json.loads((ROOT / "data/regions/regions.geojson").read_text(encoding="utf-8"))
    presets = acquire.list_regions()
    out = {}
    for f in fc["features"]:
        p = dict(f["properties"])
        p["preset"] = p.get("preset") or p["id"]
        if p["preset"] not in presets:
            print(f"skip region {p['id']}: no preset {p['preset']!r} in the region catalog")
            continue
        out[p["id"]] = {**p, "geometry": f["geometry"], "kind": "country" if p["id"] == "ukraine" else "story",
                        "story": True, "iso": "UKR" if p["id"] == "ukraine" else None, "weights": None,
                        "name_in_sentence": NAME_IN_SENTENCE.get(p["id"], p["name"])}
    return out


def world_regions() -> dict:
    """IPCC AR6 land reference regions that the data build covers (acquire.region_set)."""
    presets = acquire.list_regions()
    out = {}
    for rid in acquire.region_set("ar6"):
        e = presets[rid]
        geom = None
        for ring in e["polygons"]:
            poly = Polygon(ring).buffer(0)
            geom = poly if geom is None else geom.symmetric_difference(poly)
        if geom.bounds[2] - geom.bounds[0] > 300:  # crosses the antimeridian: not drawable as one outline
            print(f"skip world region {rid}: crosses the antimeridian")
            continue
        name = e["name"].split(" (IPCC")[0].strip()
        c = geom.representative_point()
        m = mapping(geom)
        out[rid] = {"id": rid, "preset": rid, "name": name, "place_type": "world region",
                    "bbox": [round(v, 2) for v in geom.bounds], "centroid": [round(c.x, 2), round(c.y, 2)],
                    "geometry": {"type": m["type"], "coordinates": json.loads(json.dumps(m["coordinates"]))},
                    "kind": "world", "story": False, "iso": None, "weights": None,
                    "name_in_sentence": f"the {name} region"}
    return out


def country_regions(lat: np.ndarray, lon: np.ndarray) -> dict:
    """Countries from the committed basemap, with the weights of the 2° squares they overlap."""
    fc = json.loads(BASEMAP_COUNTRIES.read_text(encoding="utf-8"))
    dlat, dlon = float(lat[1] - lat[0]), float(lon[1] - lon[0])
    out = {}
    for f in fc["features"]:
        iso, name = f["properties"]["iso"], f["properties"]["name"]
        if iso in COUNTRY_SKIP or not iso or iso.startswith("-"):
            continue
        geom = shape(f["geometry"]).buffer(0)
        parts = sorted(geom.geoms if geom.geom_type == "MultiPolygon" else [geom], key=lambda g: -g.area)
        if not parts:
            continue
        cluster, rest = [parts[0]], parts[1:]
        grew = True
        while grew and rest:
            grew = False
            hull = unary_union(cluster)
            for g in list(rest):
                if g.distance(hull) <= COUNTRY_CLUSTER_DEG:
                    cluster.append(g)
                    rest.remove(g)
                    grew = True
        main = unary_union(cluster)
        km2 = sum(g.area * math.cos(math.radians(g.representative_point().y)) * 111.32 ** 2 for g in cluster)
        if km2 < COUNTRY_MIN_KM2:
            continue
        w, s, e, n = main.bounds
        rows = np.flatnonzero((lat + dlat / 2 > s) & (lat - dlat / 2 < n))
        cols = np.flatnonzero((lon + dlon / 2 > w) & (lon - dlon / 2 < e))
        rr, cc = np.meshgrid(rows, cols, indexing="ij")
        rr, cc = rr.ravel(), cc.ravel()
        boxes = shapely.box(lon[cc] - dlon / 2, lat[rr] - dlat / 2, lon[cc] + dlon / 2, lat[rr] + dlat / 2)
        frac = shapely.area(shapely.intersection(main, boxes)) / (dlat * dlon)
        keep = frac > 1e-4
        weights = frac[keep] * np.cos(np.deg2rad(lat[rr[keep]]))
        if weights.sum() <= 0:
            continue
        name = COUNTRY_NAMES.get(name, name)
        c = cluster[0].representative_point()
        rid = f"c_{iso.lower()}"
        mask = np.zeros((lat.size, lon.size), dtype=bool)
        mask[rr[keep], cc[keep]] = True
        out[rid] = {"id": rid, "preset": None, "name": name, "place_type": "country",
                    "bbox": [round(w, 2), round(s, 2), round(e, 2), round(n, 2)],
                    "centroid": [round(c.x, 2), round(c.y, 2)], "geometry": None, "kind": "country",
                    "story": False, "iso": iso, "weights": (rr[keep], cc[keep], weights), "mask": mask,
                    "name_in_sentence": f"the {name}" if name in THE else name}
    return dict(sorted(out.items(), key=lambda kv: kv[1]["name"]))


def series_from_cache(var: str, preset: str) -> tuple[np.ndarray, dict]:
    spec = VARIABLES[var]
    s = acquire.get_series(spec["catalog_id"], preset)
    if not s.attrs.get("from_cache", True):
        raise RuntimeError(f"{spec['catalog_id']} / {preset} did not come from the cache")
    raw = s.reindex(month_index(Y0, Y1)).to_numpy(dtype=float) * spec["scale"]
    if spec["zero_is_missing"]:
        raw[raw == 0] = np.nan
    return raw, s.attrs.get("provenance", {})


def series_from_grid(grid: Grid, region: dict) -> np.ndarray:
    """Area-weighted monthly mean of the 2° squares a country overlaps; a month needs data in
    squares holding at least half of the country's weight."""
    rr, cc, w = region["weights"]
    sel = (grid.time.year >= Y0) & (grid.time.year <= Y1)
    block = grid.values[sel][:, rr, cc]
    ok = np.isfinite(block)
    num = np.where(ok, block, 0.0) @ w
    den = ok @ w
    return np.where(den >= 0.5 * w.sum(), num / np.where(den > 0, den, 1.0), np.nan)


def usable(raw: np.ndarray) -> str | None:
    """None if the series can carry a trend analysis, else the reason it is left out."""
    if raw.size != (Y1 - Y0 + 1) * 12 or not np.isfinite(raw).all():
        return "missing months"
    if np.std(raw) == 0:
        return "no variation"
    # e.g. snow: at least three calendar months must hold something in at least half of the years
    by_month = raw.reshape(-1, 12)
    if int(((by_month != 0).mean(axis=0) >= 0.5).sum()) < 3:
        return "too little of it here (zero in most months)"
    return None


def _analyse_task(task):
    global Y0, Y1
    var, y0, y1, region, cells, raw, prov = task
    Y0, Y1 = y0, y1
    return (region["id"], var), analyse(var, region, cells, raw, prov)


# --------------------------------------------------------------------------- main
def remove_stale(folder: Path, written: set[str]) -> None:
    n = 0
    for f in folder.glob("*.json"):
        if f.name not in written:
            f.unlink()
            n += 1
    if n:
        print(f"removed {n} stale file(s) from {folder.name}/")


def main(runs: int, bootstrap: int, workers: int) -> None:
    global Y0, Y1
    sys.stdout.reconfigure(encoding="utf-8")
    stories = story_regions()
    worlds = world_regions()
    first = Grid(next(iter(VARIABLES)))
    countries = country_regions(first.lat, first.lon)
    regions = {**stories, **countries, **worlds}
    print(f"regions: {len(stories)} story, {len(countries)} countries, {len(worlds)} world regions")

    periods, results, skipped = {}, {}, []
    written_maps = set()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for var, spec in VARIABLES.items():
            grid = first if var == next(iter(VARIABLES)) else Grid(var)
            Y0 = spec["start"]
            Y1 = last_complete_year(grid.time[np.isfinite(grid.values).any(axis=(1, 2))])
            periods[var] = (Y0, Y1)
            layer, cells = map_layer(grid, var)
            write_json(OUT / "map" / f"{var}.json", layer)
            written_maps.add(f"{var}.json")
            print(f"map {var}: {Y0}–{Y1}, limit {layer['limit']}, "
                  f"cells {sum(v is not None for v in layer['slope_per_decade'])}, significant {sum(layer['significant'])}")
            if spec["map_only"]:
                continue
            slim_cells = {"slope": cells["slope"], "sig": cells["sig"], "LAT": cells["LAT"]}
            tasks = []
            for r in regions.values():
                if "mask" not in r:
                    r["mask"] = region_mask(cells, shape(r["geometry"]))
                try:
                    if r["weights"] is not None:
                        raw, prov = series_from_grid(grid, r), grid.provenance
                    else:
                        raw, prov = series_from_cache(var, r["preset"])
                except Exception as exc:  # noqa: BLE001 - leave the pair out and say so; never invent data
                    skipped.append((r["id"], var, f"{type(exc).__name__}: {exc}"))
                    continue
                why = usable(raw)
                if why:
                    skipped.append((r["id"], var, why))
                    continue
                notes = acquire.assess(pd.Series(raw, index=month_index(Y0, Y1))).get("notes") or []
                if notes:
                    prov = {**prov, "_caution": " ".join(str(x) for x in notes)}
                slim = {"id": r["id"], "name": r["name"], "kind": r["kind"], "mask": r["mask"],
                        "weights": True if r["weights"] is not None else None}
                tasks.append((var, Y0, Y1, slim, slim_cells, raw, prov))
            for key, a in pool.map(_analyse_task, tasks, chunksize=4):
                results[key] = a
            print(f"  {var}: {len(tasks)} regional analyses")
            del grid
    print(f"left out {len(skipped)} region/variable pairs without usable data, e.g. "
          + "; ".join(f"{r}/{v}: {w}" for r, v, w in skipped[:6]))

    story_results = {k: a for k, a in results.items() if k[0] in stories}
    attach_neighbours(story_results, stories)
    for (rid, var), a in results.items():
        Y0, Y1 = periods[var]
        build_insights(a, regions)

    # deeper checks: the team's climate_stats pipeline, one document (one BH family) per story region
    Y0, Y1 = periods[CORE[0]]
    for rid, region in stories.items():
        doc = stats_document(region, bootstrap)
        digest = doc_hash(doc)
        path = OUT / "stats" / f"{rid}.json"
        out = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        if out and out.get("metadata", {}).get("input_sha256") == digest:
            note = "reused (same inputs and settings)"
        else:
            doc["metadata"]["input_sha256"] = digest
            out = climate_analyze(doc)
            write_json(path, out)
            note = "computed"
        for var in CORE:
            if (rid, var) in results:
                results[(rid, var)]["deeper_checks"] = deeper_checks(var, out, rid)
        print(f"stats {rid}: {out['insights_audit']['tested']} tests, "
              f"{out['insights_audit']['significant']} pass BH, {note}")

    compares, written_cmp = {}, set()
    ids = list(stories)
    for var, spec in VARIABLES.items():
        if spec["map_only"]:
            continue
        Y0, Y1 = periods[var]
        for i, ra in enumerate(ids):
            for rb in ids[i + 1:]:
                if (ra, var) not in results or (rb, var) not in results:
                    continue
                c = compare(results[(ra, var)], results[(rb, var)], var)
                compares[frozenset((ra, rb, var))] = c
                name = f"{ra}__{rb}__{var}.json"
                write_json(OUT / "compare" / name, c)
                written_cmp.add(name)

    cases = []
    for c in CASES:
        if c["region_id"] not in stories or c.get("compare_region_id", c["region_id"]) not in stories:
            print(f"skip case {c['id']}: region without data")
            continue
        Y0, Y1 = periods[c["variable_id"]]
        ans, head, lvl = case_answer(c, results, compares)
        teaser = c["teaser"].replace("{years}", str(Y1 - Y0 + 1))
        cases.append({**c, "teaser": teaser, "answer": ans, "headline": head, "level": lvl})

    written_an = set()
    for (rid, var), a in results.items():
        internal = a.pop("_internal")
        name = f"{rid}__{var}.json"
        write_json(OUT / "analysis" / name, a)
        written_an.add(name)
        a["_internal"] = internal
        if rid in stories:
            dc = a["deeper_checks"]
            print(f"{rid:13s} {var:10s} {a['verdict']['level']:9s} {a['trend']['display']['rate']:38s} "
                  f"insights={len(a['insights'])} deeper={'-' if not dc else str(dc['clear']) + '/' + str(dc['available'])}")
    for folder, names in ((OUT / "analysis", written_an), (OUT / "compare", written_cmp),
                          (OUT / "map", written_maps), (OUT / "stats", {f"{r}.json" for r in stories})):
        remove_stale(folder, names)

    index = {
        "schema_version": SCHEMA_VERSION, "synthetic": False,
        "generated": dt.date.today().isoformat(),
        "default_case": "02",  # D7: air temperature reads fastest on a bare map
        "cases": cases,
        "regions": [{k: r[k] for k in ("id", "name", "place_type", "bbox", "centroid", "geometry",
                                       "name_in_sentence", "kind", "story", "iso")} for r in regions.values()],
        "variables": [{"id": k, "catalog_id": v["catalog_id"], "name": v["name"], "long_name": v["long_name"],
                       "units": v["units"], "units_long": v["units_long"], "rate_units": v["rate_units"],
                       "anomaly_units": v["anomaly_units"], "map_title": v["map_title"], "palette": v["palette"],
                       "words": v["words"], "topic": v["topic"], "land_only": v["land_only"],
                       "source": v["source"], "parameter": v["parameter"], "map_only": v["map_only"],
                       "period": f"{periods[k][0]}–{periods[k][1]}"} for k, v in VARIABLES.items()],
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
    print(f"done: {len(written_maps)} maps, {len(written_an)} analyses, {len(written_cmp)} comparisons")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", type=int, default=300, help="Monte-Carlo runs for validation.json")
    ap.add_argument("--bootstrap", type=int, default=999,
                    help="resampling replicates for the climate_stats deeper checks (pipeline default 999)")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1),
                    help="processes for the regional analyses")
    args = ap.parse_args()
    main(args.runs, args.bootstrap, args.workers)
