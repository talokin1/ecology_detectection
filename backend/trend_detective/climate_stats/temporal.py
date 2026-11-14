"""Seasonal profiles, changing distributions, emergence and block uncertainty."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import optimize, sparse, special, stats

from .contracts import Config
from .core import (
    annual_aggregate,
    baseline_mask,
    block_indices,
    bootstrap_summary,
    describe,
    detrend,
    positions,
    records,
    reference,
    rng_for,
    skipped,
    trend,
)

SEASONS = {"DJF": (12, 1, 2), "MAM": (3, 4, 5), "JJA": (6, 7, 8), "SON": (9, 10, 11)}


def profiles(monthly: pd.Series, cfg: Config, units: str, *, total: bool = False) -> tuple[list, dict]:
    by_month = []
    for month in range(1, 13):
        subset = monthly[monthly.index.month == month]
        by_month.append(
            {
                "month": month,
                "descriptive": describe(subset),
                "trend": trend(subset, cfg, frequency=1, units=units),
            }
        )
    by_season = {}
    for name, months in SEASONS.items():
        aggregated = annual_aggregate(monthly, cfg, months=months, total=total)
        output = {
            "months": months,
            "year_label": "year_of_January" if name == "DJF" else "calendar_year",
            "descriptive": describe(aggregated),
            "units": "mm/season" if total else units,
            "trend": trend(aggregated, cfg, frequency=1, units="mm/season" if total else units),
        }
        if cfg.include_series:
            output["series"] = records(aggregated)
        by_season[name] = output
    return by_month, by_season


def emergence(annual: pd.Series, fitted: dict, cfg: Config) -> dict:
    if fitted.get("status") not in ("ok", "constant"):
        return skipped("annual_trend_unavailable")
    residual = detrend(annual).dropna()
    noise = float(residual.std())
    if not np.isfinite(noise) or noise < 1e-12:
        return skipped("zero_or_undefined_residual_noise")
    valid = annual.dropna()
    slope = fitted["sen"]["slope_per_year"]
    ratio = abs(slope) * (valid.index.year - valid.index.year[0]) / noise
    crossings = valid.index.year[ratio > 1]
    candidate = int(crossings[0]) if len(crossings) else None
    return {
        "status": "ok",
        "candidate_year": candidate,
        "year": None,
        "ratio_now": float(ratio[-1]),
        "threshold": 1.0,
        "noise_std": noise,
        "definition": "Absolute fitted change since first annual observation / detrended annual SD",
        "interpretation": "A typical-noise threshold, not a date of causation or statistical significance.",
        "visibility_rule": "year is populated only if the annual MK test passes document-wide FDR",
    }


def split_series(annual: pd.Series, cfg: Config) -> tuple[pd.Series, pd.Series, int]:
    split = cfg.split_year
    if split is None:
        split = (int(annual.index.year.min()) + int(annual.index.year.max())) // 2
    return annual[annual.index.year <= split], annual[annual.index.year > split], split


def _smooth(annual: pd.Series) -> list[dict]:
    valid = annual.dropna()
    if len(valid) < 6:
        return []
    x, y = valid.index.year.to_numpy(dtype=float), valid.to_numpy()
    k = max(4, int(np.ceil(len(y) * 0.35)))
    out = []
    for x0 in x:
        distance = np.abs(x - x0)
        radius = max(np.partition(distance, k - 1)[k - 1], 1.0) * 1.001
        weights = np.maximum(0, 1 - (distance / radius) ** 3) ** 3
        design = np.column_stack([np.ones(len(x)), x - x0])
        coef = np.linalg.lstsq(design * np.sqrt(weights[:, None]), y * np.sqrt(weights), rcond=None)[0]
        out.append({"year": int(x0), "value": float(coef[0])})
    return out


def acceleration(annual: pd.Series, cfg: Config, key: str, units: str) -> dict:
    if annual.empty:
        return skipped("no_annual_data")
    first, second, split = split_series(annual, cfg)
    fits = [trend(s, cfg, units=units) for s in (first, second)]
    if any(f.get("status") not in ("ok", "constant") for f in fits):
        return skipped("each_half_requires_min_years", split_year=split, halves=fits)
    difference = fits[1]["sen"]["slope_per_decade"] - fits[0]["sen"]["slope_per_decade"]
    inference = skipped("bootstrap_disabled_missing_values_or_fewer_than_two_blocks")
    if (
        cfg.bootstrap_samples
        and not first.isna().any()
        and not second.isna().any()
        and min(len(first), len(second)) >= 2 * cfg.block_years
    ):
        rng = rng_for(cfg, key)
        residuals, predicted, times = [], [], []
        for s in (first, second):
            t = np.arange(len(s), dtype=float)
            fit = reference().sens_slope(t, s)
            pred = fit["intercept"] + fit["slope"] * t
            r = s.to_numpy() - pred
            residuals.append(r - r.mean())
            predicted.append(pred)
            times.append(t)
        diffs = []
        for _ in range(cfg.bootstrap_samples):
            slopes = [
                reference().sens_slope(t, pred + r[block_indices(len(r), cfg.block_years, rng)])["slope"]
                for t, pred, r in zip(times, predicted, residuals)
            ]
            diffs.append(10 * (slopes[1] - slopes[0]))
        inference = bootstrap_summary(diffs, difference, cfg)
    return {
        "status": "ok",
        "split_year": split,
        "split_rule": "configured_or_calendar_midpoint",
        "first": fits[0],
        "second": fits[1],
        "difference_per_decade": difference,
        "difference_test": inference,
        "smooth": _smooth(annual),
        "smooth_label": "local linear tricube smoother; visualization, not a test",
    }


def variability(annual: pd.Series, cfg: Config, key: str) -> dict:
    if annual.empty:
        return skipped("no_annual_data")
    first, second, split = split_series(annual, cfg)
    if min(first.count(), second.count()) < cfg.min_years:
        return skipped("each_half_requires_min_years", split_year=split)
    a, b = detrend(first), detrend(second)
    sd1, sd2 = float(a.std()), float(b.std())
    if min(sd1, sd2) <= 1e-12 or not np.isfinite(sd1 + sd2):
        return skipped("zero_or_undefined_variance")
    bf = stats.levene(a.dropna(), b.dropna(), center="median")
    inference = skipped("bootstrap_disabled_missing_values_or_fewer_than_two_blocks")
    if (
        cfg.bootstrap_samples
        and not a.isna().any()
        and not b.isna().any()
        and min(len(a), len(b)) >= 2 * cfg.block_years
    ):
        rng = rng_for(cfg, key)
        estimates = []
        for _ in range(cfg.bootstrap_samples):
            s1 = np.std(a.to_numpy()[block_indices(len(a), cfg.block_years, rng)], ddof=1)
            s2 = np.std(b.to_numpy()[block_indices(len(b), cfg.block_years, rng)], ddof=1)
            if min(s1, s2) > 1e-12:
                estimates.append(np.log(s2 / s1))
        inference = bootstrap_summary(estimates, np.log(sd2 / sd1), cfg)
        if inference["status"] == "ok":
            inference["ratio_ci"] = np.exp(inference.pop("ci"))
            inference["null"] = "SD ratio = 1; tested on log scale"
    return {
        "status": "ok",
        "split_year": split,
        "sd_first": sd1,
        "sd_second": sd2,
        "ratio": sd2 / sd1,
        "detrending": "separate_Sen_trend_in_each_half",
        "brown_forsythe": {
            "statistic": float(bf.statistic),
            "p_value_iid": float(bf.pvalue),
            "note": "IID diagnostic only; block test is used for FDR",
        },
        "block_test": inference,
    }


def _logistic(t: np.ndarray, event: np.ndarray):
    if len(np.unique(event)) < 2 or np.ptp(t) == 0:
        return None
    design = np.column_stack([np.ones(len(t)), t])

    def objective(beta):
        logits = design @ beta
        return np.sum(np.logaddexp(0, logits) - event * logits)

    def jac(beta):
        return design.T @ (special.expit(design @ beta) - event)

    fit = optimize.minimize(objective, np.zeros(2), jac=jac, method="BFGS", options={"gtol": 1e-7})
    if (
        not np.isfinite(fit.x).all()
        or np.max(np.abs(fit.x)) > 30
        or (not fit.success and np.linalg.norm(jac(fit.x)) > 1e-4)
    ):
        return None
    return fit.x


def _empirical(events: np.ndarray, alpha: float) -> dict:
    n, k = len(events), int(np.sum(events))
    if not n:
        return skipped("no_observations")
    p, z = k / n, stats.norm.ppf(1 - alpha / 2)
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return {
        "events": k,
        "n": n,
        "probability": p,
        "return_period_years": 1 / p if p > 0 else None,
        "probability_ci_iid_wilson": [max(0, center - half), min(1, center + half)],
    }


def probability_change(annual: pd.Series, cfg: Config, key: str) -> dict:
    valid = annual.dropna()
    base = annual[baseline_mask(annual.index, cfg)].dropna()
    if len(valid) < 2 * cfg.min_years or len(base) < cfg.min_years:
        return skipped("insufficient_annual_or_baseline_years")
    years = valid.index.year.to_numpy(dtype=float)
    _first, _second, split = split_series(annual, cfg)
    t = (years - years.mean()) / 10
    endpoints = np.array([1, t[0]]), np.array([1, t[-1]])
    out = {}
    for tail, quantile in (("low", 0.1), ("high", 0.9)):
        threshold = float(np.quantile(base, quantile))
        events = (valid.to_numpy() < threshold if tail == "low" else valid.to_numpy() > threshold).astype(
            float
        )
        beta = _logistic(t, events)
        result = {
            "threshold": threshold,
            "baseline_count": len(base),
            "quantile": quantile,
            "comparison": "strictly_below" if tail == "low" else "strictly_above",
            "first_period": _empirical(events[years <= split], cfg.alpha),
            "second_period": _empirical(events[years > split], cfg.alpha),
            "split_year": split,
        }
        if beta is None:
            result["logistic"] = skipped("constant_events_or_complete_separation")
        else:
            p_then, p_now = [float(special.expit(x @ beta)) for x in endpoints]
            ratio = p_now / p_then
            inference = skipped("bootstrap_disabled_missing_values_or_fewer_than_two_blocks")
            if cfg.bootstrap_samples and not annual.isna().any() and len(annual) >= 2 * cfg.block_years:
                rng = rng_for(cfg, key + tail)
                slopes, ratios = [], []
                for _ in range(cfg.bootstrap_samples):
                    idx = block_indices(len(t), cfg.block_years, rng)
                    sample = _logistic(t[idx], events[idx])
                    if sample is not None:
                        slopes.append(sample[1])
                        probs = [special.expit(x @ sample) for x in endpoints]
                        ratios.append(probs[1] / probs[0])
                inference = bootstrap_summary(slopes, float(beta[1]), cfg)
                if inference["status"] == "ok":
                    inference["log_odds_slope_ci_per_decade"] = inference.pop("ci")
                    inference["probability_ratio_ci_percentile"] = np.quantile(
                        ratios, [cfg.alpha / 2, 1 - cfg.alpha / 2]
                    )
            result["logistic"] = {
                "status": "ok",
                "log_odds_slope_per_decade": beta[1],
                "first_year": int(years[0]),
                "last_year": int(years[-1]),
                "p_then": p_then,
                "p_now": p_now,
                "probability_ratio": ratio,
                "return_then_years": 1 / p_then,
                "return_now_years": 1 / p_now,
                "inference": inference,
            }
        out[tail] = result
    return {
        "status": "ok",
        "basis": "annual_aggregates",
        "tails": out,
        "caveat": "Descriptive recurrence under a changing probability, not stationary return levels or attribution.",
    }


def _quantile_fit(t: np.ndarray, y: np.ndarray, tau: float) -> np.ndarray | None:
    n = len(y)
    design = sparse.csr_matrix(np.column_stack([np.ones(n), t]))
    constraints = sparse.hstack([design, sparse.eye(n), -sparse.eye(n)], format="csr")
    objective = np.r_[np.zeros(2), np.full(n, tau), np.full(n, 1 - tau)]
    fit = optimize.linprog(
        objective, A_eq=constraints, b_eq=y, bounds=[(None, None)] * 2 + [(0, None)] * (2 * n), method="highs"
    )
    return fit.x[:2] if fit.success else None


def quantile_trends(data: pd.Series, cfg: Config, key: str, *, frequency: int = 12) -> dict:
    valid = data.dropna()
    if len(valid) < max(cfg.min_years * frequency * cfg.min_coverage, 20):
        return skipped("insufficient_observations_for_quantile_regression")
    if len(valid) > 3000:
        return skipped("quantile_point_limit_exceeded_use_monthly_or_annual")
    t = (positions(valid.index, frequency) - positions(valid.index, frequency)[0]) / frequency
    t = t - t.mean()
    y = valid.to_numpy()
    estimates = {tau: _quantile_fit(t, y, tau) for tau in cfg.quantiles}
    samples = {tau: [] for tau in cfg.quantiles}
    block = cfg.block_months if frequency == 12 else cfg.block_years
    complete = not data.isna().any()
    if cfg.bootstrap_samples and complete and len(data) >= 2 * block:
        rng = rng_for(cfg, key)
        for _ in range(cfg.bootstrap_samples):
            # Pairs block bootstrap keeps the sampled original time coordinate, not an invented chronology.
            idx = block_indices(len(y), block, rng)
            if np.ptp(t[idx]) == 0:
                continue
            for tau in cfg.quantiles:
                coef = _quantile_fit(t[idx], y[idx], tau)
                samples[tau].append(float(coef[1] * 10) if coef is not None else np.nan)
    result = []
    for tau, coef in estimates.items():
        if coef is None:
            result.append({"tau": tau, **skipped("quantile_solver_failed")})
        else:
            inference = (
                bootstrap_summary(samples[tau], float(coef[1] * 10), cfg)
                if samples[tau]
                else skipped("bootstrap_disabled_or_incomplete_series")
            )
            result.append(
                {"tau": tau, "status": "ok", "slope_per_decade": float(coef[1] * 10), "inference": inference}
            )
    contrast = skipped("requires_quantiles_0.5_and_0.9_and_bootstrap")
    if (
        0.5 in samples
        and 0.9 in samples
        and samples[0.5]
        and samples[0.9]
        and estimates[0.5] is not None
        and estimates[0.9] is not None
    ):
        delta = 10 * (estimates[0.9][1] - estimates[0.5][1])
        contrast = {
            "difference_per_decade": delta,
            **bootstrap_summary(np.array(samples[0.9]) - np.array(samples[0.5]), delta, cfg),
        }
    return {
        "status": "ok",
        "basis": "monthly_anomalies" if frequency == 12 else "annual_values",
        "method": "Koenker-Bassett linear programming; moving-block pairs bootstrap",
        "quantiles": result,
        "upper_tail_minus_median": contrast,
        "caveat": "Monthly quantiles do not measure daily heat extremes; use daily indices for those.",
    }


def _pettitt(values: np.ndarray) -> tuple[float, int]:
    ranks = stats.rankdata(values)
    u = 2 * np.cumsum(ranks) - np.arange(1, len(values) + 1) * (len(values) + 1)
    point = int(np.argmax(np.abs(u[:-1])))
    return float(abs(u[point])), point


def change_point(annual: pd.Series, cfg: Config, key: str) -> dict:
    if len(annual) < 2 * cfg.min_years or annual.count() < 2 * cfg.min_years:
        return skipped("insufficient_years_for_change_point")
    residual = detrend(annual)
    values = residual.dropna().to_numpy()
    if np.ptp(values) < 1e-12:
        return skipped("no_residual_variation")
    statistic, point = _pettitt(values)
    inference = skipped("bootstrap_disabled_missing_values_or_fewer_than_two_blocks")
    if cfg.bootstrap_samples and not residual.isna().any() and len(residual) >= 2 * cfg.block_years:
        rng = rng_for(cfg, key)
        simulated = [
            _pettitt(values[block_indices(len(values), cfg.block_years, rng)])[0]
            for _ in range(cfg.bootstrap_samples)
        ]
        p = (1 + np.count_nonzero(np.asarray(simulated) >= statistic)) / (cfg.bootstrap_samples + 1)
        inference = {
            "status": "ok",
            "test": "pettitt_max_rank_statistic_block_bootstrap",
            "p_value": p,
            "replicates": cfg.bootstrap_samples,
            "block_years": cfg.block_years,
        }
    return {
        "status": "ok",
        "last_year_before_candidate_break": int(residual.dropna().index.year[point]),
        "statistic": statistic,
        "basis": "Sen_detrended_annual_values",
        "inference": inference,
        "caveat": "Exploratory level-shift diagnostic; cannot identify an instrument change or physical cause.",
    }
