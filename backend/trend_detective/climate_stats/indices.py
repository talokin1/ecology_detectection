"""Daily climate indices, Hargreaves reference ET, SPI and SPEI.

Daily counts/spells require complete years. Missing days never count as dry/frost-free.
TX90p is explicitly a fixed-baseline variant without ETCCDI in-base bootstrap.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from scipy import stats

from .contracts import Config, InputSeries
from .core import (
    annual_aggregate,
    baseline_mask,
    describe,
    longest_run,
    records,
    skipped,
    to_monthly,
    trend,
)

PRECIP = {"precipitation_power", "precipitation_imerg", "PRECTOTCORR_SUM"}
AIR_TEMP = {"air_temperature_power", "air_temperature_merra2", "surface_air_temperature_airs"}


def _annual_index(data: pd.Series, calc) -> pd.Series:
    output = {}
    for year in range(int(data.index.year.min()), int(data.index.year.max()) + 1):
        axis = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
        group = data.reindex(axis)
        output[pd.Timestamp(year=year, month=1, day=1)] = np.nan if group.isna().any() else calc(group)
    return pd.Series(output, dtype=float)


def _package(data: pd.Series, cfg: Config, units: str, definition: str, **extra) -> dict:
    output = {
        "status": "ok" if data.count() else "insufficient_data",
        "units": units,
        "definition": definition,
        "descriptive": describe(data),
        "trend": trend(data, cfg, units=units),
        **extra,
    }
    if cfg.include_series:
        output["series"] = records(data)
    return output


def _calendar_day(index: pd.DatetimeIndex) -> np.ndarray:
    # 365-day month/day calendar; leap day is handled separately, not allowed to shift March.
    doy = index.dayofyear.to_numpy().copy()
    doy -= (index.is_leap_year & (index.month > 2)).astype(int)
    doy[(index.month == 2) & (index.day == 29)] = 0
    return doy


def tx90p(data: pd.Series, cfg: Config) -> pd.Series:
    base = data[baseline_mask(data.index, cfg)].dropna()
    thresholds = np.full(366, np.nan)
    day = _calendar_day(base.index)
    for d in range(1, 366):
        distance = np.minimum(np.abs(day - d), 365 - np.abs(day - d))
        selection = (distance <= 2) & (day != 0)
        years = len(set(base.index.year[selection]))
        if years >= cfg.min_climatology_years:
            thresholds[d] = np.quantile(base.to_numpy()[selection], 0.9)
    thresholds[0] = np.mean(thresholds[[59, 60]])
    daily_threshold = pd.Series(thresholds[_calendar_day(data.index)], index=data.index)
    exceeds = (data > daily_threshold).astype(float).where(data.notna() & daily_threshold.notna())
    return _annual_index(exceeds, lambda s: float(s.mean() * 100))


def daily_indices(item: InputSeries, cfg: Config) -> dict:
    if item.frequency != "daily":
        return skipped("daily_data_required")
    data, vid = item.data, item.variable_id
    definitions = {}
    if vid == "T2M_MIN":
        definitions = {
            "fd": (lambda s: int((s < 0).sum()), "days", "Days with daily Tmin < 0 degC"),
            "tr": (lambda s: int((s > 20).sum()), "days", "Days with daily Tmin > 20 degC"),
            "tnn": (lambda s: float(s.min()), "degC", "Annual minimum of daily Tmin"),
        }
    elif vid == "T2M_MAX":
        definitions = {
            "su": (lambda s: int((s > 25).sum()), "days", "Days with daily Tmax > 25 degC"),
            "id": (lambda s: int((s < 0).sum()), "days", "Days with daily Tmax < 0 degC"),
            "txx": (lambda s: float(s.max()), "degC", "Annual maximum of daily Tmax"),
        }
    elif vid in PRECIP and item.units == "mm/day":
        definitions = {
            "cdd": (
                lambda s: longest_run(s < 1),
                "days",
                "Longest within-calendar-year run with P < 1 mm/day",
            ),
            "cwd": (
                lambda s: longest_run(s >= 1),
                "days",
                "Longest within-calendar-year run with P >= 1 mm/day",
            ),
            "rx1day": (lambda s: float(s.max()), "mm", "Maximum one-day precipitation amount"),
            "rx5day": (
                lambda s: float(s.rolling(5).sum().max()),
                "mm",
                "Maximum five-day total wholly within the year",
            ),
            "r10mm": (lambda s: int((s >= 10).sum()), "days", "Days with P >= 10 mm/day"),
            "r20mm": (lambda s: int((s >= 20).sum()), "days", "Days with P >= 20 mm/day"),
            "prcptot": (
                lambda s: float(s[s >= 1].sum()),
                "mm/year",
                "Annual total from wet days (P >= 1 mm/day)",
            ),
            "sdii": (
                lambda s: float(s[s >= 1].mean()) if (s >= 1).any() else np.nan,
                "mm/wet_day",
                "Mean precipitation on wet days",
            ),
        }
    else:
        return skipped("no_daily_threshold_indices_defined_for_this_variable")
    result = {
        name: _package(_annual_index(data, calc), cfg, units, definition)
        for name, (calc, units, definition) in definitions.items()
    }
    if vid == "T2M_MAX":
        result["tx90p"] = _package(
            tx90p(data, cfg),
            cfg,
            "%",
            "Days above calendar-day baseline 90th percentile using a centered five-day window",
            caveat="Fixed-baseline variant: ETCCDI in-base bootstrap is not implemented.",
        )
    if vid == "T2M_MIN":
        if item.latitude is None:
            result["last_frost_doy"] = skipped("latitude_required_for_spring_definition")
        elif item.latitude < 0:
            result["last_frost_doy"] = skipped(
                "this_last_spring_frost_DOY_definition_is_northern_hemisphere_only"
            )
        else:

            def last_frost(s):
                frost = s[(s.index.month < 7) & (s < 0)]
                return int(frost.index.dayofyear[-1]) if len(frost) else np.nan

            result["last_frost_doy"] = _package(
                _annual_index(data, last_frost),
                cfg,
                "day_of_year",
                "Last Tmin < 0 degC before July 1; null if there was no spring frost",
                caveat="Custom indicator, not ETCCDI; no-frost years are excluded from its trend.",
            )
    return {
        "status": "ok",
        "coverage_rule": "complete_calendar_year_required",
        "source_series_id": item.id,
        "indices": result,
    }


def _first_run(mask: np.ndarray, length: int = 6, start: int = 0) -> int | None:
    count = 0
    for i in range(start, len(mask)):
        count = count + 1 if mask[i] else 0
        if count >= length:
            return i - length + 1
    return None


def growing_season(data: pd.Series, latitude: float, cfg: Config) -> dict:
    southern = latitude < 0
    output, censored = {}, []
    for year in range(int(data.index.year.min()), int(data.index.year.max()) + 1):
        start = pd.Timestamp(year=year, month=7 if southern else 1, day=1)
        end = start + pd.DateOffset(years=1) - pd.Timedelta(days=1)
        axis = pd.date_range(start, end, freq="D")
        group = data.reindex(axis)
        value = np.nan
        if not group.isna().any():
            warm = _first_run(group.to_numpy() > 5)
            halfway = int(
                (pd.Timestamp(year=year + int(southern), month=1 if southern else 7, day=1) - start).days
            )
            cold = _first_run(group.to_numpy() < 5, start=max(halfway, warm or 0))
            if warm is None:
                value = 0
            elif cold is None:
                censored.append(year)
            else:
                value = max(0, cold - warm)
        output[pd.Timestamp(year=year, month=1, day=1)] = value
    return _package(
        pd.Series(output, dtype=float),
        cfg,
        "days",
        "First six TG > 5 degC days to first six TG < 5 degC days after midyear",
        year_definition="July-June labeled by starting year" if southern else "January-December",
        no_observed_end_years=censored,
        caveat="Years without an observed cold-season endpoint are censored (null), not assumed complete.",
    )


def temperature_combinations(items: list[InputSeries], cfg: Config) -> dict:
    maximum = [s for s in items if s.variable_id == "T2M_MAX"]
    minimum = [s for s in items if s.variable_id == "T2M_MIN"]
    means = [s for s in items if s.variable_id in AIR_TEMP and s.frequency == "daily"]
    output = {}
    if len(maximum) == len(minimum) == 1 and all(s.frequency != "annual" for s in maximum + minimum):
        high, low = to_monthly(maximum[0], cfg), to_monthly(minimum[0], cfg)
        paired = pd.concat([high.rename("hi"), low.rename("lo")], axis=1)
        difference = paired.hi - paired.lo
        if (difference.dropna() < 0).any():
            output["dtr"] = skipped("Tmax_is_below_Tmin_check_input_semantics")
        else:
            annual = annual_aggregate(difference, cfg)
            output["dtr"] = _package(
                annual,
                cfg,
                "degC",
                "Mean daily temperature range over the selected months: Tmax - Tmin",
                months=list(cfg.annual_months),
                missing_policy=cfg.annual_missing_policy,
                year_label="year_of_January" if set(cfg.annual_months) == {12, 1, 2} else "calendar_year",
            )
            if cfg.include_series:
                output["dtr"]["monthly"] = records(difference)
    else:
        output["dtr"] = skipped("requires_one_unambiguous_T2M_MAX_and_T2M_MIN_daily_or_mean_daily_monthly")
    if len(means) == 1:
        data, latitude = means[0].data, means[0].latitude
        sources = [means[0].id]
    elif (
        not means
        and len(maximum) == len(minimum) == 1
        and maximum[0].frequency == minimum[0].frequency == "daily"
    ):
        data = (maximum[0].data + minimum[0].data) / 2
        latitude = maximum[0].latitude if maximum[0].latitude is not None else minimum[0].latitude
        sources = [maximum[0].id, minimum[0].id]
    else:
        output["gsl"] = skipped("requires_one_daily_air_temperature_or_daily_Tmax_Tmin_pair")
        return output
    if latitude is None:
        output["gsl"] = skipped("latitude_required_for_hemisphere")
    else:
        output["gsl"] = {**growing_season(data, latitude, cfg), "source_series_ids": sources}
    return output


def extraterrestrial_radiation(index: pd.DatetimeIndex, latitude: float) -> np.ndarray:
    """FAO-56 daily Ra in MJ m-2 day-1, including polar day/night clipping."""
    day = index.dayofyear.to_numpy()
    phi = np.deg2rad(latitude)
    dr = 1 + 0.033 * np.cos(2 * np.pi * day / 365)
    delta = 0.409 * np.sin(2 * np.pi * day / 365 - 1.39)
    sunset = np.arccos(np.clip(-np.tan(phi) * np.tan(delta), -1, 1))
    return np.maximum(
        0,
        (24 * 60 / np.pi)
        * 0.0820
        * dr
        * (sunset * np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.sin(sunset)),
    )


def hargreaves_pet(high: pd.Series, low: pd.Series, latitude: float) -> pd.Series:
    pair = pd.concat([high.rename("hi"), low.rename("lo")], axis=1)
    if (pair.hi < pair.lo).any():
        raise ValueError("Tmax is below Tmin")
    result = []
    for date, row in pair.iterrows():
        days = pd.date_range(date, date + pd.offsets.MonthEnd(0), freq="D")
        ra = np.mean(extraterrestrial_radiation(days, latitude))
        # Ra must be converted from energy to equivalent evaporation (0.408); see FAO-56 eq. 52.
        mean = (row.hi + row.lo) / 2
        daily = 0.0023 * 0.408 * ra * max(0.0, mean + 17.8) * np.sqrt(row.hi - row.lo)
        result.append(daily * len(days))
    return pd.Series(result, index=pair.index, dtype=float)


def precipitation_totals(item: InputSeries, cfg: Config) -> pd.Series:
    if item.variable_id == "PRECTOTCORR_SUM":
        return item.data.copy()
    if item.frequency == "daily":
        total = item.data.resample("MS").sum(min_count=1)
        counts = item.data.resample("MS").count()
        return total.where(counts == total.index.days_in_month)
    if item.frequency == "monthly":
        return item.data * item.data.index.days_in_month
    return pd.Series(dtype=float, index=pd.DatetimeIndex([]))


def _glo_pwm(sample: np.ndarray) -> dict:
    """Unbiased PWM fit used by SPEI/lmomco, including reflected/logistic limits.

    See lmomco pwm, pwm2lmom, parglo and cdfglo; parameters are xi, alpha, kappa.
    """
    x = np.sort(np.asarray(sample, dtype=float))
    n = len(x)
    if n < 4 or not np.isfinite(x).all() or np.ptp(x) <= 1e-10:
        raise ValueError("insufficient or constant PWM calibration sample")
    center = float(np.median(x))
    x = x - center
    j = np.arange(n, dtype=float)
    b0 = np.mean(x)
    b1 = np.mean(j / (n - 1) * x)
    b2 = np.mean(j * (j - 1) / ((n - 1) * (n - 2)) * x)
    l2, l3 = 2 * b1 - b0, 6 * b2 - 6 * b1 + b0
    if l2 <= 0 or not np.isfinite([b0, l2, l3]).all() or abs(l3 / l2) >= 1:
        raise ValueError("invalid generalized-logistic L-moments")
    kappa = -l3 / l2
    if abs(kappa) <= 1e-6:
        xi, alpha, kappa = b0, l2, 0.0
    else:
        alpha = l2 * np.sinc(kappa)
        xi = b0 + l2 * (1 - np.sinc(kappa)) / kappa
    if alpha <= 0 or not np.isfinite([xi, alpha, kappa]).all():
        raise ValueError("invalid generalized-logistic PWM parameters")
    if np.any(1 - kappa * (x - xi) / alpha <= 0):
        raise ValueError("PWM fit excludes calibration observations from its support")
    return {"xi": float(xi + center), "alpha": float(alpha), "kappa": float(kappa)}


def _glo_cdf(values: np.ndarray, params: dict) -> np.ndarray:
    from scipy.special import expit

    u = (np.asarray(values, dtype=float) - params["xi"]) / params["alpha"]
    k = params["kappa"]
    if k == 0:
        return expit(u)
    support = 1 - k * u > 0
    out = np.full(u.shape, 0.0 if k < 0 else 1.0)
    out[support] = expit(-np.log1p(-k * u[support]) / k)
    out[~np.isfinite(u)] = np.nan
    return out


def standardized_drought(totals: pd.Series, scale: int, kind: str, cfg: Config) -> dict:
    accumulated = totals.rolling(scale, min_periods=scale).sum()
    output = pd.Series(np.nan, index=totals.index, dtype=float)
    calibration = []
    for month in range(1, 13):
        mask = accumulated.index.month == month
        sample = accumulated[mask & baseline_mask(accumulated.index, cfg)].dropna().to_numpy()
        details = {"month": month, "n_baseline": len(sample)}
        if len(sample) < cfg.min_drought_baseline_years or np.std(sample) < 1e-10:
            calibration.append({**details, **skipped("insufficient_or_constant_calibration_sample")})
            continue
        values = accumulated[mask].to_numpy()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                if kind == "spi":
                    positive = sample[sample > 0]
                    if len(positive) < 10 or np.std(positive) < 1e-10:
                        raise ValueError("too few varying positive precipitation totals")
                    shape, loc, spread = stats.gamma.fit(positive, floc=0)
                    pzero = float(np.mean(sample == 0))
                    probability = pzero + (1 - pzero) * stats.gamma.cdf(values, shape, loc=loc, scale=spread)
                    params = {"shape": shape, "loc": loc, "scale": spread, "probability_zero": pzero}
                else:
                    params = _glo_pwm(sample)
                    probability = _glo_cdf(values, params)
            if not np.isfinite(list(params.values())).all():
                raise ValueError("nonfinite fit parameters")
            valid = np.isfinite(values)
            if not np.isfinite(probability[valid]).all():
                raise ValueError("nonfinite fitted probabilities")
            z = stats.norm.ppf(np.clip(probability, 1e-7, 1 - 1e-7))
            output.loc[mask] = np.where(valid, z, np.nan)
            diagnostics = {
                "cdf_clipped_low": int(np.sum(probability[valid] < 1e-7)),
                "cdf_clipped_high": int(np.sum(probability[valid] > 1 - 1e-7)),
            }
            if kind == "spei":
                base_z = stats.norm.ppf(np.clip(_glo_cdf(sample, params), 1e-7, 1 - 1e-7))
                diagnostics.update(
                    calibration_z_median=float(np.median(base_z)),
                    calibration_z_std=float(np.std(base_z, ddof=1)),
                    outside_support=int(
                        np.sum(1 - params["kappa"] * (values[valid] - params["xi"]) / params["alpha"] <= 0)
                    ),
                )
            calibration.append({**details, "status": "ok", "parameters": params, "diagnostics": diagnostics})
        except (ValueError, FloatingPointError, RuntimeError) as exc:
            calibration.append({**details, **skipped("distribution_fit_failed", detail=str(exc))})
    annual = output[output.index.month == cfg.drought_end_month]
    by_decade = []
    for decade in sorted(set((output.index.year // 10) * 10)):
        values = output[(output.index.year // 10) * 10 == decade].dropna()
        by_decade.append(
            {
                "decade": int(decade),
                "valid_months": len(values),
                "dry_months": int((values < -1).sum()),
                "dry_fraction": float((values < -1).mean()) if len(values) else None,
            }
        )
    successes = sum(m["status"] == "ok" for m in calibration)
    result = {
        "status": "ok" if successes == 12 else "partial" if successes else "insufficient_data",
        "kind": kind,
        "scale_months": scale,
        "units": "standard_normal_index",
        "calibration_method": "zero_inflated_gamma_MLE"
        if kind == "spi"
        else "generalized_logistic_unbiased_PWM",
        "warnings": ["Some evaluation CDF values were clipped; inspect monthly calibration diagnostics."]
        if any(
            m.get("diagnostics", {}).get("cdf_clipped_low", 0)
            or m.get("diagnostics", {}).get("cdf_clipped_high", 0)
            for m in calibration
        )
        else [],
        "baseline": list(cfg.baseline) if cfg.baseline else "full_input_record",
        "calibration": calibration,
        "drought_threshold": -1,
        "frequency_by_decade": by_decade,
        "trend_end_month": cfg.drought_end_month,
        "trend": trend(annual, cfg, units="index"),
        "trend_rule": "One fixed calendar month per year; overlapping windows are not treated as independent.",
    }
    if cfg.include_series:
        result["series"] = records(output)
    return result


def drought_indices(items: list[InputSeries], cfg: Config) -> dict:
    rain = [s for s in items if s.variable_id in PRECIP and s.frequency != "annual"]
    if not rain:
        return skipped("monthly_or_daily_precipitation_required")
    maximum = [s for s in items if s.variable_id == "T2M_MAX" and s.frequency != "annual"]
    minimum = [s for s in items if s.variable_id == "T2M_MIN" and s.frequency != "annual"]
    latitude = next((s.latitude for s in items if s.latitude is not None), None)
    pet, pet_reason = None, "requires_one_Tmax_Tmin_pair_and_latitude"
    if len(maximum) == len(minimum) == 1 and latitude is not None:
        try:
            pet = hargreaves_pet(to_monthly(maximum[0], cfg), to_monthly(minimum[0], cfg), latitude)
        except ValueError as exc:
            pet_reason = str(exc)
    out = {}
    for source in rain:
        totals = precipitation_totals(source, cfg)
        details = {"precipitation_units": "mm/month", "indices": {}}
        for scale in cfg.drought_scales:
            details["indices"][f"spi{scale}"] = standardized_drought(totals, scale, "spi", cfg)
            if pet is None:
                details["indices"][f"spei{scale}"] = skipped(pet_reason)
            else:
                balance = totals - pet.reindex(totals.index)
                details["indices"][f"spei{scale}"] = standardized_drought(balance, scale, "spei", cfg)
        details["pet"] = (
            skipped(pet_reason)
            if pet is None
            else {
                "status": "ok",
                "method": "Hargreaves-Samani_monthly_temperature_approximation",
                "units": "mm/month",
                "latitude": latitude,
                "temperature_sources": [maximum[0].id, minimum[0].id],
                "formula": "0.0023 * 0.408 * Ra_MJ_m2_day * max(Tmean+17.8,0) * sqrt(Tmax-Tmin) * days",
                "caveat": "Reference evaporative demand, not measured actual evaporation; not causal attribution.",
            }
        )
        if cfg.include_series:
            details["precipitation_totals"] = records(totals)
            if pet is not None:
                details["pet"]["series"] = records(pet)
        out[source.id] = details
    return {"status": "ok", "sources": out}
