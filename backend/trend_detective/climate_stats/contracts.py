"""Validate JSON, decode calendar axes and normalize physical (already scaled) values."""

# Public contract: malformed JSON values/types consistently raise ValueError.
# ruff: noqa: TRY004

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, fields
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[3]
METHODS = (
    "trend",
    "monthly_profile",
    "seasonal",
    "emergence",
    "probability",
    "quantiles",
    "acceleration",
    "variability",
    "bootstrap",
    "change_point",
    "indices",
    "drought",
    "relationships",
    "drivers",
)


@dataclass(frozen=True)
class Config:
    baseline: tuple[int, int] | None = None
    alpha: float = 0.05
    fdr_q: float = 0.05
    min_years: int = 10
    min_climatology_years: int = 5
    min_coverage: float = 0.9
    daily_min_coverage: float | None = None
    annual_months: tuple[int, ...] = tuple(range(1, 13))
    annual_missing_policy: str = "strict"
    annual_min_coverage: float = 0.8
    bootstrap_samples: int = 999
    block_months: int = 12
    block_years: int = 3
    seed: int = 1729
    split_year: int | None = None
    drought_scales: tuple[int, ...] = (3, 6)
    drought_end_month: int = 8
    min_drought_baseline_years: int = 20
    quantiles: tuple[float, ...] = (0.1, 0.5, 0.9)
    correlation_lags: tuple[int, ...] = (0,)
    include_series: bool = True
    methods: tuple[str, ...] = METHODS

    @classmethod
    def parse(cls, obj: dict | None) -> Config:
        obj = obj or {}
        if not isinstance(obj, dict):
            raise ValueError("config must be an object")
        unknown = set(obj) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"Unknown config fields: {sorted(unknown)}")
        data = dict(obj)
        for name in (
            "baseline",
            "drought_scales",
            "quantiles",
            "correlation_lags",
            "methods",
            "annual_months",
        ):
            if name in data and data[name] is not None:
                if not isinstance(data[name], (list, tuple)):
                    raise ValueError(f"config.{name} must be an array")
                data[name] = tuple(data[name])
        cfg = cls(**data)
        for name in ("alpha", "fdr_q", "min_coverage", "daily_min_coverage", "annual_min_coverage"):
            value = getattr(cfg, name)
            if name == "daily_min_coverage" and value is None:
                continue
            upper_ok = (
                value <= 1
                if isinstance(value, (int, float)) and name.endswith("coverage")
                else (value < 1 if isinstance(value, (int, float)) else False)
            )
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not 0 < value
                or not upper_ok
            ):
                raise ValueError(f"config.{name} must be in (0, 1), or (0, 1] for coverage")
        if cfg.annual_missing_policy not in ("strict", "climatology_adjusted"):
            raise ValueError("annual_missing_policy must be strict or climatology_adjusted")
        limits = {
            "min_years": (4, 200),
            "min_climatology_years": (2, 100),
            "bootstrap_samples": (0, 10000),
            "block_months": (1, 120),
            "block_years": (1, 30),
            "seed": (0, 2**32 - 1),
            "drought_end_month": (1, 12),
            "min_drought_baseline_years": (10, 100),
        }
        for name, (lo, hi) in limits.items():
            value = getattr(cfg, name)
            if type(value) is not int or not lo <= value <= hi:
                raise ValueError(f"config.{name} must be an integer in [{lo}, {hi}]")
        if cfg.bootstrap_samples and cfg.bootstrap_samples < 19:
            raise ValueError("bootstrap_samples must be 0 (disabled) or at least 19")
        if cfg.baseline is not None and (
            len(cfg.baseline) != 2
            or any(type(v) is not int for v in cfg.baseline)
            or not 1800 <= cfg.baseline[0] <= cfg.baseline[1] <= 2200
        ):
            raise ValueError("baseline must be [first_year, last_year] within 1800..2200")
        if cfg.split_year is not None and (
            type(cfg.split_year) is not int or not 1800 <= cfg.split_year <= 2200
        ):
            raise ValueError("split_year must be an integer within 1800..2200")
        for name, lo, hi in (
            ("drought_scales", 1, 24),
            ("correlation_lags", 0, 36),
            ("annual_months", 1, 12),
        ):
            values = getattr(cfg, name)
            if (
                not isinstance(values, tuple)
                or not values
                or any(type(v) is not int or not lo <= v <= hi for v in values)
                or len(set(values)) != len(values)
            ):
                raise ValueError(f"config.{name} requires unique integers in [{lo}, {hi}]")
        if (
            not isinstance(cfg.quantiles, tuple)
            or not cfg.quantiles
            or any(type(q) not in (int, float) or not 0 < q < 1 for q in cfg.quantiles)
            or len(set(cfg.quantiles)) != len(cfg.quantiles)
        ):
            raise ValueError("quantiles must contain unique probabilities between 0 and 1")
        if (
            not isinstance(cfg.methods, tuple)
            or any(m not in METHODS for m in cfg.methods)
            or len(set(cfg.methods)) != len(cfg.methods)
        ):
            raise ValueError(f"methods must be a unique subset of {METHODS}")
        if type(cfg.include_series) is not bool:
            raise ValueError("include_series must be boolean")
        return cfg

    def json(self) -> dict:
        return asdict(self)


@lru_cache(maxsize=1)
def catalog() -> dict[str, dict]:
    source = yaml.safe_load((ROOT / "data/catalog/variables.yaml").read_text(encoding="utf-8"))
    return {e["id"]: e for e in source["variables"] + source["internal_inputs"]}


def _unit(value: str) -> str:
    aliases = {
        "°C": "degC",
        "C": "degC",
        "celsius": "degC",
        "kelvin": "K",
        "fraction": "1",
        "index": "1",
        "dimensionless": "1",
        "percent": "%",
        "cm (equivalent water height)": "cm",
        "kg/m^2 (per 3-h, monthly mean)": "kg/m^2/3h",
        "molec/cm2": "molecules/cm^2",
        "molecules/cm2": "molecules/cm^2",
        "Dobsons": "DU",
    }
    value = value.strip().replace("²", "^2").replace("³", "^3")
    return aliases.get(value, value)


def normalize_units(vid: str, units: str, values: np.ndarray) -> tuple[np.ndarray, str, str | None]:
    entry = catalog()[vid]
    source, supplied = _unit(str(entry["units"])), _unit(units)
    target = _unit(str(entry.get("display_units", source)))
    factor, offset = 1.0, 0.0
    if target == "degC" and supplied in ("degC", "K"):
        offset = -273.15 if supplied == "K" else 0.0
    elif (
        source == "1"
        and vid in {"root_zone_soil_wetness_power", "snow_cover_fraction_power", "sea_ice_fraction_power"}
        and supplied in ("1", "%")
    ):
        factor = 0.01 if supplied == "%" else 1.0
    elif source == "%" and supplied in ("1", "%"):
        factor = 100.0 if supplied == "1" else 1.0
    elif vid == "solar_radiation_power" and supplied in ("W/m^2", "MJ/m^2/day"):
        factor = 0.0864 if supplied == "W/m^2" else 1.0
    elif vid == "evapotranspiration_gldas" and supplied in ("kg/m^2/s", "mm/day"):
        factor = 86400.0 if supplied == "kg/m^2/s" else 1.0
    elif supplied != target:
        raise ValueError(f"{vid}: unsupported units {units!r}; expected {source!r} or {target!r}")
    with np.errstate(over="ignore", invalid="ignore"):
        result = values * factor + offset
    if np.any(np.isfinite(values) & ~np.isfinite(result)):
        raise ValueError(f"{vid}: numeric overflow during unit conversion")
    conversion = f"x * {factor} + {offset}" if (factor, offset) != (1.0, 0.0) else None
    return result, target, conversion


@dataclass
class InputSeries:
    id: str
    variable_id: str
    region_id: str
    frequency: str
    units: str
    data: pd.Series
    entry: dict
    latitude: float | None
    conversion: str | None
    input_units: str
    supplied_count: int
    missing_sentinels: int
    provenance: dict


def _numeric(value, label: str) -> float:
    if value is None:
        return np.nan
    if type(value) not in (int, float):
        raise ValueError(f"{label}: use a finite number or null, not {value!r}")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError(f"{label}: numeric magnitude exceeds float64 range") from exc
    if not np.isfinite(number):
        raise ValueError(f"{label}: use a finite number or null, not {value!r}")
    return number


def parse_series(obj: dict, *, covariate: bool = False) -> InputSeries:
    if not isinstance(obj, dict):
        raise ValueError("Each series must be an object")
    allowed = {
        "id",
        "variable_id",
        "region_id",
        "frequency",
        "units",
        "values",
        "latitude",
        "fill_values",
        "semantics",
        "provenance",
    }
    if set(obj) - allowed:
        raise ValueError(f"Unknown series fields: {sorted(set(obj) - allowed)}")
    for key in ("id", "region_id", "frequency", "units"):
        if not isinstance(obj.get(key), str) or not obj[key].strip():
            raise ValueError(f"series.{key} must be a nonempty string")
    sid, freq = obj["id"], obj["frequency"]
    if freq not in ("daily", "monthly", "annual"):
        raise ValueError(f"{sid}: frequency must be daily, monthly or annual")
    vid = obj.get("variable_id", "")
    if not isinstance(vid, str) or (not covariate and vid not in catalog()):
        raise ValueError(f"{sid}: unknown variable_id {vid!r}; use a catalog id")
    if covariate and vid:
        raise ValueError("Covariates use their id, without a variable_id")
    entry = catalog()[vid] if not covariate else {"name": sid, "percent_change_meaningful": False}
    if vid in ("T2M_MAX", "T2M_MIN") and freq == "monthly":
        expected = "mean_daily_maximum" if vid == "T2M_MAX" else "mean_daily_minimum"
        if obj.get("semantics") != expected:
            raise ValueError(
                f"{sid}: monthly {vid} requires semantics={expected!r}; monthly-hour extremes differ"
            )
    if vid == "PRECTOTCORR_SUM" and freq != "monthly":
        raise ValueError("PRECTOTCORR_SUM is a monthly total; use precipitation_power for daily rates")
    vals = obj.get("values")
    if not isinstance(vals, list) or not 1 <= len(vals) <= 200000:
        raise ValueError(f"{sid}: values must contain 1..200000 date/value records")
    fills = obj.get("fill_values", [])
    if not isinstance(fills, list):
        raise ValueError(f"{sid}: fill_values must be an array")
    fills = [_numeric(v, "fill_values") for v in fills]
    dates, numbers = [], []
    sentinel_count = 0
    for item in vals:
        if not isinstance(item, dict) or set(item) != {"date", "value"}:
            raise ValueError(f"{sid}: each value must have exactly date and value")
        date = item["date"]
        pattern = {
            "daily": r"\d{4}-\d{2}-\d{2}",
            "monthly": r"\d{4}-\d{2}(?:-\d{2})?",
            "annual": r"\d{4}(?:-01-01)?",
        }[freq]
        if not isinstance(date, str) or not re.fullmatch(pattern, date):
            raise ValueError(f"{sid}: invalid {freq} date {date!r}")
        try:
            timestamp = pd.Timestamp(date)
        except (ValueError, OverflowError) as exc:
            raise ValueError(f"{sid}: invalid calendar date {date!r}") from exc
        if not 1800 <= timestamp.year <= 2200:
            raise ValueError(f"{sid}: dates must be within 1800..2200")
        if freq == "monthly":
            timestamp = timestamp.to_period("M").to_timestamp()
        value = _numeric(item["value"], sid)
        if value in fills:
            value = np.nan
            sentinel_count += 1
        dates.append(timestamp)
        numbers.append(value)
    if len(set(dates)) != len(dates):
        raise ValueError(f"{sid}: duplicate {freq} timestamps after calendar normalization")
    values = np.array(numbers, dtype=float)
    conversion = None
    units = obj["units"]
    if not covariate:
        values, units, conversion = normalize_units(vid, units, values)
    data = pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float).sort_index()
    axis = pd.date_range(
        data.index[0], data.index[-1], freq={"daily": "D", "monthly": "MS", "annual": "YS"}[freq]
    )
    if len(axis) > 200000:
        raise ValueError(f"{sid}: calendar span exceeds 200000 time steps")
    data = data.reindex(axis)
    latitude = obj.get("latitude")
    if latitude is not None and (type(latitude) not in (int, float) or not -90 <= latitude <= 90):
        raise ValueError(f"{sid}: latitude must be in [-90, 90]")
    provenance = obj.get("provenance", {})
    if not isinstance(provenance, dict):
        raise ValueError(f"{sid}: provenance must be an object")
    finite = data.dropna().to_numpy()
    # Reject likely undecoded fill/scaling mistakes instead of reporting extreme climate trends.
    bounds = None
    if units == "degC":
        bounds = (-150, 150)
    elif vid in {"root_zone_soil_wetness_power", "snow_cover_fraction_power", "sea_ice_fraction_power"}:
        bounds = (0, 1)
    elif vid == "ndvi_modis":
        bounds = (-1, 1)
    elif units == "%":
        bounds = (0, 100)
    elif vid in {
        "precipitation_power",
        "precipitation_imerg",
        "PRECTOTCORR_SUM",
        "snow_depth_power",
        "soil_moisture_gldas",
        "snow_water_equivalent_gldas",
        "water_vapour_power",
        "water_vapor_airs",
    }:
        bounds = (0, np.inf)
    if bounds and np.any((finite < bounds[0] - 1e-10) | (finite > bounds[1] + 1e-10)):
        raise ValueError(f"{sid}: values outside physical bounds {bounds}; decode scale/fill values first")
    return InputSeries(
        sid,
        vid,
        obj["region_id"],
        freq,
        units,
        data,
        entry,
        latitude,
        conversion,
        obj["units"],
        len(vals),
        sentinel_count,
        provenance,
    )


def parse_payload(payload: dict) -> tuple[Config, list[InputSeries], list[InputSeries], list[dict]]:
    import json

    from jsonschema import Draft202012Validator

    schema = json.loads((ROOT / "schema/climate-input.schema.json").read_text(encoding="utf-8"))
    error = next(iter(Draft202012Validator(schema).iter_errors(payload)), None)
    if error is not None:
        path = "/".join(str(p) for p in error.absolute_path) or "/"
        raise ValueError(f"Input schema error at {path}: {error.message}")
    if not isinstance(payload, dict):
        raise ValueError("Input JSON must be an object")
    if set(payload) - {"schema_version", "config", "series", "covariates", "controls", "metadata"}:
        raise ValueError("Unknown top-level input fields")
    if payload.get("schema_version") != "1.0":
        raise ValueError('schema_version must be "1.0"')
    if not isinstance(payload.get("series"), list) or not 1 <= len(payload["series"]) <= 200:
        raise ValueError("series must contain 1..200 series")
    if not isinstance(payload.get("covariates", []), list):
        raise ValueError("covariates must be an array")
    cfg = Config.parse(payload.get("config"))
    series = [parse_series(s) for s in payload["series"]]
    covariates = [parse_series(s, covariate=True) for s in payload.get("covariates", [])]
    ids = [s.id for s in series + covariates]
    if len(set(ids)) != len(ids):
        raise ValueError("Series and covariate ids must be globally unique")
    controls = payload.get("controls", [])
    if not isinstance(controls, list):
        raise ValueError("controls must be an array")
    for item in controls:
        if (
            not isinstance(item, dict)
            or set(item) - {"series_id", "covariate_ids", "months"}
            or item.get("series_id") not in {s.id for s in series}
            or not isinstance(item.get("covariate_ids"), list)
            or not item["covariate_ids"]
            or len(set(item["covariate_ids"])) != len(item["covariate_ids"])
            or not set(item["covariate_ids"]) <= {s.id for s in covariates}
        ):
            raise ValueError("controls require a known series_id and unique known covariate_ids")
        months = item.get("months", list(range(1, 13)))
        if (
            not isinstance(months, list)
            or not months
            or len(set(months)) != len(months)
            or any(type(m) is not int or not 1 <= m <= 12 for m in months)
        ):
            raise ValueError("controls.months requires unique calendar months 1..12")
    return cfg, series, covariates, controls
