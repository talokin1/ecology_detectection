"""One entry point for challenge objectives 1 and 2 (R-01, R-02).

Objective 1 — *identify variables that can be investigated for trends*:
    ``list_variables()`` returns the curated catalog with, for each variable, whether we can
    actually deliver it; ``assess(series)`` checks whether a delivered series is long and complete
    enough for a trend analysis; ``inventory(region)`` does both for every variable in a region.

Objective 2 — *acquire the variable for a particular region*:
    ``get_series(variable_id, region)`` takes a catalog id and a named preset or any box, and calls
    the right reader (POWER Zarr, no login; MODIS NDVI and GRACE from the Earthdata cache). Used by
    the offline precompute (scripts/build_data.py, ADR-004), not per app request.

Variables come from ``data/catalog/variables.yaml`` (field ``access`` says how each is fetched);
presets from ``data/catalog/regions.yaml``. Trend statistics are not computed here.

SI-assisted (Claude, Anthropic); pending team review (see docs/08-si-usage-log.md).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from . import grace, modis_ndvi, power_zarr
from .earthdata import NotCachedError
from .power_zarr import REPO_ROOT, Region

CATALOG_DIR = REPO_ROOT / "data" / "catalog"
READERS = ("power_zarr", "grace", "modis_ndvi")

# Data-quality guards (R-03). Defaults pending science-lead review; see docs/10-methods.md.
MIN_YEARS = 10
MIN_MONTHS = 120
MIN_YEARS_PER_CALENDAR_MONTH = 5  # needed to estimate a month's climatology for deseasonalising
# Sen's slope is pulled toward 0 when some calendar months barely vary between years (their
# anomalies are near-ties): Ukraine snow, Sahel dry season (docs/planning/2026-11-14-stats-cross-check.md).
# A calendar month is "flat" if its year-to-year SD is < 5% of the most variable month's SD; the
# series is flagged if >= 25% of observations fall in flat months or are exactly zero.
# Chosen on 2026-11-14 from real series: Sahel rainfall Nov-Feb 1-5% (flagged), Ukraine
# rainfall min 69%, NW India snow min 20%.
FLAT_MONTH_RELATIVE_SD = 0.05
FLAT_FRACTION = 0.25
LONG_GAP_MONTHS = 12


@dataclass(frozen=True)
class Variable:
    id: str
    name: str
    definition: str
    why_it_trends: str
    units: str
    period: str
    access: dict
    entry: dict = field(repr=False, compare=False)

    @property
    def reader(self) -> str:
        return str(self.access.get("reader", "none"))

    @property
    def available(self) -> bool:
        return self.reader in READERS

    @property
    def needs_login(self) -> bool:
        return self.access.get("login") == "earthdata"

    def summary(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "definition": self.definition,
            "why_it_trends": self.why_it_trends,
            "units": self.units,
            "period": self.period,
            # "live" = no login needed to (re)fetch, i.e. the precompute can refresh it without a
            # token (ADR-004); the static app never reads per request (plan v2 decision 8).
            "available": self.available,
            "live": self.available and not self.needs_login,
            "reader": self.reader,
            "caveats": self.entry.get("caveats"),
            "topic": self.entry.get("topic"),
            "how_measured": self.entry.get("how_measured"),
            "percent_change_meaningful": self.entry.get("percent_change_meaningful"),
            "biomes": self.entry.get("biomes", []),
        }


@cache
def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def list_variables(path: Path | None = None, *, available_only: bool = False) -> dict[str, Variable]:
    """Catalog variables by id (objective 1: the curated menu)."""
    data = _load_yaml(Path(path) if path else CATALOG_DIR / "variables.yaml")
    out: dict[str, Variable] = {}
    for e in data["variables"]:
        units = str(e.get("units", "")).split("#")[0].strip()
        v = Variable(
            id=e["id"],
            name=e["name"],
            definition=e.get("definition", ""),
            why_it_trends=e.get("why_it_trends", ""),
            units=units,
            period=str(e.get("period", "")),
            access=dict(e.get("access") or {"reader": "none"}),
            entry=e,
        )
        if v.id in out:
            raise ValueError(f"duplicate variable id {v.id!r} in catalog")
        if not available_only or v.available:
            out[v.id] = v
    return out


def list_inputs(path: Path | None = None) -> dict[str, dict]:
    """Internal method inputs by id (``internal_inputs`` in the catalog: T2M_MAX, T2M_MIN,
    PRECTOTCORR_SUM). Not shown to users; each entry states its monthly semantics (Q3)."""
    data = _load_yaml(Path(path) if path else CATALOG_DIR / "variables.yaml")
    return {e["id"]: e for e in data.get("internal_inputs") or []}


def list_regions(path: Path | None = None) -> dict[str, dict]:
    """Region presets by id, each with a ``region`` (``Region``) and its catalog fields."""
    data = _load_yaml(Path(path) if path else CATALOG_DIR / "regions.yaml")
    out = {}
    for e in data["regions"]:
        west, south, east, north = e["bbox"]
        out[e["id"]] = e | {"region": Region(e["name"], south, north, west, east)}
    return out


def resolve_region(region: str | Region | Sequence[float], name: str = "custom box") -> Region:
    """A preset id, a ``Region``, or a ``[west, south, east, north]`` box."""
    if isinstance(region, Region):
        return region
    if isinstance(region, str):
        presets = list_regions()
        if region not in presets:
            raise KeyError(f"unknown region preset {region!r}; choose from {sorted(presets)}")
        return presets[region]["region"]
    west, south, east, north = (float(v) for v in region)
    return Region(name, south, north, west, east)


def get_series(
    variable_id: str,
    region: str | Region | Sequence[float],
    *,
    allow_login_fetch: bool = False,
    refresh: bool = False,
    land_only: bool | None = None,
) -> pd.Series:
    """Monthly regional series for a catalog variable (objective 2).

    POWER variables are fetched live (cached after the first read). Earthdata variables are
    served from the cache only, unless ``allow_login_fetch`` is set (offline precompute scripts):
    the deployed app never needs the Earthdata token.

    ``land_only``: average land cells only (POWER variables). ``None`` takes the preset's
    ``land_only`` field (default false). GRACE is land-only and NDVI land-only by construction.

    ``attrs`` carries the catalog entry summary, the reader's provenance and ``assessment``.
    """
    land_only = _preset_land_only(region, land_only)
    variables = list_variables()
    if variable_id not in variables:
        raise KeyError(f"unknown variable {variable_id!r}")
    v = variables[variable_id]
    if not v.available:
        raise LookupError(f"{variable_id!r} is in the catalog but has no reader yet")
    reg = resolve_region(region)
    offline = v.needs_login and not allow_login_fetch

    if v.reader == "power_zarr":
        s = power_zarr.region_series(
            v.access["variable"], reg, v.access.get("store", "merra2"), refresh=refresh, land_only=land_only
        )
    elif v.reader == "grace":
        s = grace.region_series(reg, refresh=refresh, offline=offline)
    elif v.reader == "modis_ndvi":
        s = modis_ndvi.region_series(reg, refresh=refresh, offline=offline)
    else:  # pragma: no cover - guarded by READERS
        raise LookupError(v.reader)

    reader_units = s.attrs.get("units", "")
    s.attrs.update(
        {
            "variable_id": v.id,
            "catalog": v.summary(),
            "region": reg.name,
            "land_only": land_only,
            "bbox": [reg.lon_min, reg.lat_min, reg.lon_max, reg.lat_max],
            # B2-11: ``units`` is the catalog unit (what the app labels); ``source_units`` is the
            # reader's own string (e.g. POWER "C" for degC). ``catalog_units`` kept for callers.
            "units": v.units or reader_units,
            "source_units": reader_units,
            "catalog_units": v.units,
            "assessment": assess(s),
        }
    )
    return s


def _preset_land_only(region, land_only: bool | None) -> bool:
    if land_only is not None:
        return land_only
    return bool(isinstance(region, str) and list_regions().get(region, {}).get("land_only"))


def get_input_series(
    parameter: str,
    region: str | Region | Sequence[float],
    *,
    store: str = "merra2",
    land_only: bool | None = None,
    refresh: bool = False,
) -> pd.Series:
    """A POWER parameter that is an *input* to a method, not a catalog variable shown to users
    (e.g. daily ``T2M_MAX`` for extreme indices). Same box, land-only rule and cache as
    ``get_series``. ``store="merra2_daily"`` returns a daily series indexed by date.
    """
    reg = resolve_region(region)
    lo = _preset_land_only(region, land_only)
    s = power_zarr.region_series(parameter, reg, store, refresh=refresh, land_only=lo)
    s.attrs.update(
        {"region": reg.name, "land_only": lo, "bbox": [reg.lon_min, reg.lat_min, reg.lon_max, reg.lat_max]}
    )
    return s


def get_monthly_from_daily(
    parameter: str,
    region: str | Region | Sequence[float],
    how: str,
    *,
    min_fraction: float = 0.8,
    land_only: bool | None = None,
    refresh: bool = False,
) -> pd.Series:
    """Monthly series aggregated from the daily store (plan v2, S2): ``how="mean"`` for states
    (mean daily Tmax/Tmin), ``how="sum"`` for per-day fluxes (precipitation, mm/month).

    Use this, not the monthly store, for mean daily T2M_MAX / T2M_MIN: the monthly store holds
    the month's single extreme hour instead.
    """
    daily = get_input_series(parameter, region, store="merra2_daily", land_only=land_only, refresh=refresh)
    s = power_zarr.monthly_from_daily(daily, how, min_fraction)
    s.attrs["assessment"] = assess(s)
    return s


def assess(s: pd.Series) -> dict:
    """Can this monthly series be investigated for a trend? (objective 1, per region)

    Returns counts, the checks passed, and plain-language notes. ``status`` is ``ok``,
    ``caution`` (usable, but read the notes), ``too_short`` or ``no_variation`` (constant series).
    """
    s = s.dropna()
    if s.empty:
        return {"status": "too_short", "n_months": 0, "notes": ["No data for this region."]}
    idx = pd.DatetimeIndex(s.index).to_period("M")
    span = pd.period_range(idx.min(), idx.max(), freq="M")
    present = np.isin(span, idx)
    gaps, run = [], 0
    for p in present:
        run = 0 if p else run + 1
        gaps.append(run)
    per_month = pd.Series(idx.month).value_counts().reindex(range(1, 13), fill_value=0)
    years = len(span) / 12
    zero_fraction = float((np.abs(s.to_numpy()) < 1e-12).mean())

    # Year-to-year spread of each calendar month, relative to the most variable month.
    month_sd = s.groupby(idx.month).std(ddof=0).reindex(range(1, 13))
    ref_sd = float(month_sd.max())
    if not ref_sd > 0:
        return {
            "status": "no_variation",
            "n_months": len(s),
            "start": str(idx.min()),
            "end": str(idx.max()),
            "record_years": round(years, 1),
            "zero_fraction": round(zero_fraction, 3),
            "notes": [
                (
                    "The value never changes in this region (for example no snow ever falls), "
                    "so there is nothing to measure a trend in."
                )
            ],
        }
    flat_months = [int(m) for m in month_sd.index if month_sd[m] < FLAT_MONTH_RELATIVE_SD * ref_sd]
    # Near-ties: observations in flat calendar months, or exactly zero (a few non-zero outliers can
    # give a calendar month enough spread to look non-flat, e.g. rare sea ice in the Sea of Azov).
    tied = np.isin(idx.month, flat_months) | (np.abs(s.to_numpy()) < 1e-12)
    flat_fraction = float(tied.mean())

    checks = {
        "long_enough": bool(years >= MIN_YEARS and len(s) >= MIN_MONTHS),
        "seasonal_cycle_estimable": bool(per_month.min() >= MIN_YEARS_PER_CALENDAR_MONTH),
        "few_flat_months": bool(flat_fraction < FLAT_FRACTION),
        "no_long_gaps": bool(max(gaps) <= LONG_GAP_MONTHS),
    }
    notes = []
    if not checks["long_enough"]:
        notes.append(
            f"Only {years:.1f} years / {len(s)} months: at least {MIN_YEARS} years are "
            "needed before a trend means much."
        )
    if not checks["seasonal_cycle_estimable"]:
        weak = [
            pd.Timestamp(2000, m, 1).strftime("%b")
            for m in range(1, 13)
            if per_month[m] < MIN_YEARS_PER_CALENDAR_MONTH
        ]
        notes.append(
            f"Few values for {', '.join(weak)} (e.g. snow or cloud), so the seasonal "
            "cycle is uncertain for those months."
        )
    if not checks["few_flat_months"]:
        if flat_months:
            names = ", ".join(pd.Timestamp(2000, m, 1).strftime("%b") for m in flat_months)
            what = f"{names} hardly change from year to year (e.g. dry season, or no snow in summer)."
        else:
            what = f"{zero_fraction:.0%} of months are exactly zero."
        notes.append(
            f"{what} The median-based slope (Sen) can then be pulled toward zero; "
            "compare it with the regression slope."
        )
    if not checks["no_long_gaps"]:
        notes.append(
            f"Contains a gap of {max(gaps)} months; the record before and after may "
            "come from different instruments."
        )

    status = "too_short" if not checks["long_enough"] else ("ok" if all(checks.values()) else "caution")
    return {
        "status": status,
        "n_months": len(s),
        "start": str(idx.min()),
        "end": str(idx.max()),
        "record_years": round(years, 1),
        "coverage": round(float(present.mean()), 3),
        "longest_gap_months": int(max(gaps)),
        "min_years_per_calendar_month": int(per_month.min()),
        "zero_fraction": round(zero_fraction, 3),
        "flat_months": flat_months,
        "flat_fraction": round(flat_fraction, 3),
        "checks": checks,
        "notes": notes,
    }


def inventory(region: str | Region | Sequence[float], *, allow_login_fetch: bool = False) -> pd.DataFrame:
    """For one region: every catalog variable, whether we can deliver it, and whether it is fit
    for a trend analysis there. Runs no trend tests (no ranking by significance)."""
    rows = []
    for v in list_variables().values():
        row = {
            "id": v.id,
            "name": v.name,
            "available": v.available,
            "live": v.available and not v.needs_login,
        }  # live = refresh needs no login
        if not v.available:
            rows.append(row | {"status": "no reader", "notes": ""})
            continue
        try:
            s = get_series(v.id, region, allow_login_fetch=allow_login_fetch)
        except NotCachedError:
            rows.append(row | {"status": "not cached", "notes": "needs offline Earthdata fetch"})
            continue
        except ValueError as exc:  # e.g. land-only variable over open ocean
            rows.append(row | {"status": "no data", "notes": str(exc)})
            continue
        a = s.attrs["assessment"]
        rows.append(
            row
            | {
                "status": a["status"],
                "period": f"{a['start']}..{a['end']}",
                "n_months": a["n_months"],
                "units": s.attrs["units"],
                "notes": " ".join(a["notes"]),
            }
        )
    return pd.DataFrame(rows)
