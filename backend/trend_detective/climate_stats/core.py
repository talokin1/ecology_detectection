"""Calendar-aware statistics and shared inference primitives.

Sen ranks, tie-corrected MK variance and BH reuse the repository reference engine.
The AR(1) adapter uses actual calendar distances, never compressing missing months.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from functools import lru_cache

import numpy as np
import pandas as pd
from scipy import stats

from .contracts import ROOT, Config, InputSeries


@lru_cache(maxsize=1)
def reference():
    name = "_climate_pipeline_reference_trend_stats"
    path = ROOT / ".claude/skills/trend-stats/scripts/trend_stats.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def skipped(reason: str, **details) -> dict:
    return {"status": "skipped", "reason": reason, **details}


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def rng_for(cfg: Config, key: str) -> np.random.Generator:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return np.random.default_rng(np.random.SeedSequence([cfg.seed, int.from_bytes(digest[:8], "little")]))


def records(data: pd.Series) -> list[dict]:
    return [
        {"date": d.strftime("%Y-%m-%d"), "value": float(v) if np.isfinite(v) else None}
        for d, v in data.items()
    ]


def baseline_mask(index: pd.DatetimeIndex, cfg: Config) -> np.ndarray:
    if cfg.baseline is None:
        return np.ones(len(index), dtype=bool)
    return (index.year >= cfg.baseline[0]) & (index.year <= cfg.baseline[1])


def positions(index: pd.DatetimeIndex, frequency: int) -> np.ndarray:
    if frequency == 12:
        return np.asarray(index.year * 12 + index.month - 1, dtype=int)
    if frequency == 1:
        return np.asarray(index.year, dtype=int)
    raise ValueError("Inferential trends require monthly or annual series")


def calendar_r1(values: np.ndarray, pos: np.ndarray) -> tuple[float, int]:
    """Correlation using only pairs one real calendar step apart."""
    good = np.isfinite(values)
    pair = good[:-1] & good[1:] & (np.diff(pos) == 1)
    a, b = values[:-1][pair], values[1:][pair]
    if len(a) < 4 or min(np.std(a), np.std(b)) < 1e-12:
        return 0.0, len(a)
    return float(np.clip(np.corrcoef(a, b)[0, 1], -0.99, 0.99)), len(a)


def ar1_inflation(pos: np.ndarray, rho: float) -> float:
    """1 + 2/n * sum_{i<j} rho**calendar_distance; O(n), agrees with regular-grid eta."""
    rho = float(np.clip(rho, 0, 0.99))
    if len(pos) < 2 or rho == 0:
        return 1.0
    running = total = 0.0
    for gap in np.diff(pos):
        running = rho ** int(gap) * (1 + running)
        total += running
    return float(1 + 2 * total / len(pos))


def describe(data: pd.Series, *, ratio_scale: bool = False) -> dict:
    valid = data.dropna()
    y = valid.to_numpy()
    if not len(y):
        return skipped("no_valid_values", count=0)
    qs = [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]
    quantiles = np.quantile(y, qs)
    mean, median = float(np.mean(y)), float(np.median(y))
    std = float(np.std(y, ddof=1)) if len(y) > 1 else None
    constant = np.ptp(y) <= 1e-12
    return {
        "status": "ok",
        "count": len(y),
        "mean": mean,
        "median": median,
        "std": std,
        "variance": std**2 if std is not None else None,
        "min": float(np.min(y)),
        "max": float(np.max(y)),
        "min_date": valid.idxmin().strftime("%Y-%m-%d"),
        "max_date": valid.idxmax().strftime("%Y-%m-%d"),
        "range": float(np.ptp(y)),
        "iqr": float(quantiles[5] - quantiles[3]),
        "median_absolute_deviation": float(np.median(np.abs(y - median))),
        "trimmed_mean_10pct": float(stats.trim_mean(y, 0.1)),
        "quantiles": {str(q): float(v) for q, v in zip(qs, quantiles)},
        "skewness": float(stats.skew(y, bias=False)) if len(y) >= 3 and not constant else None,
        "excess_kurtosis": float(stats.kurtosis(y, bias=False)) if len(y) >= 4 and not constant else None,
        "coefficient_of_variation": std / mean
        if ratio_scale and np.all(y >= 0) and mean > 1e-12 and std is not None
        else None,
        "zero_fraction": float(np.mean(y == 0)),
    }


def longest_run(mask) -> int:
    longest = current = 0
    for yes in mask:
        current = current + 1 if yes else 0
        longest = max(longest, current)
    return longest


def quality(item: InputSeries) -> dict:
    s = item.data
    n = int(s.count())
    notes = []
    if item.entry.get("caveats"):
        notes.append(item.entry["caveats"])
    if item.entry.get("status"):
        notes.append(item.entry["status"])
    if item.entry.get("variable_verified") is False:
        notes.append("Catalog variable metadata have not been verified against a source granule.")
    if s.isna().any():
        notes.append("Missing calendar steps are retained; no interpolation is applied.")
    if n and np.mean(s.dropna().to_numpy() == 0) >= 0.25:
        notes.append("At least 25% of valid values are zero; tied/seasonally flat values affect trend power.")
    return {
        "status": "no_data" if not n else "caution" if notes else "ok",
        "supplied_records": item.supplied_count,
        "calendar_steps": len(s),
        "valid": n,
        "missing": len(s) - n,
        "coverage": n / len(s),
        "longest_missing_run": longest_run(s.isna()),
        "step": item.frequency,
        "declared_fill_values_replaced": item.missing_sentinels,
        "start": s.index[0].strftime("%Y-%m-%d"),
        "end": s.index[-1].strftime("%Y-%m-%d"),
        "warnings": notes,
    }


def to_monthly(item: InputSeries, cfg: Config) -> pd.Series:
    if item.frequency != "daily":
        return item.data.copy()
    means = item.data.resample("MS").mean()
    counts = item.data.resample("MS").count()
    threshold = cfg.daily_min_coverage if cfg.daily_min_coverage is not None else cfg.min_coverage
    return means.where(counts / means.index.days_in_month >= threshold)


def climatology(data: pd.Series, cfg: Config) -> tuple[pd.Series, dict]:
    mask = baseline_mask(data.index, cfg)
    base = data[mask]
    anomalies = pd.Series(np.nan, index=data.index, dtype=float)
    standardized = anomalies.copy()
    months = []
    for month in range(1, 13):
        vals = base[base.index.month == month].dropna()
        sufficient = len(vals) >= cfg.min_climatology_years
        desc = describe(vals)
        mean = float(vals.mean()) if sufficient else None
        std = float(vals.std()) if sufficient else None
        select = data.index.month == month
        if sufficient:
            anomalies.loc[select] = data.loc[select] - mean
            if std > 1e-12:
                standardized.loc[select] = anomalies.loc[select] / std
        months.append(
            {
                "month": month,
                "baseline_count": len(vals),
                "usable": sufficient,
                "mean": mean,
                "std": std,
                "distribution": desc,
            }
        )
    usable = [m["mean"] for m in months if m["usable"]]
    output = {
        "status": "ok" if len(usable) == 12 else "partial" if usable else "insufficient_data",
        "baseline": list(cfg.baseline) if cfg.baseline else "full_input_record",
        "min_years_per_month": cfg.min_climatology_years,
        "months": months,
        "seasonal_amplitude": max(usable) - min(usable) if len(usable) == 12 else None,
        "peak_month": max(months, key=lambda m: m["mean"] if m["mean"] is not None else -np.inf)["month"]
        if usable
        else None,
    }
    if cfg.include_series:
        output["anomalies"] = records(anomalies)
        output["standardized_anomalies"] = records(standardized)
    return anomalies, output


def annual_aggregate(
    monthly: pd.Series, cfg: Config, *, total: bool = False, months: tuple[int, ...] | None = None
) -> pd.Series:
    """Day-weighted state/rate mean, or sum of monthly totals. DJF belongs to Jan/Feb's year."""
    months = months or cfg.annual_months
    if set(months) == {12, 1, 2}:
        months = (12, 1, 2)
    selected = monthly[monthly.index.month.isin(months)]
    if selected.empty:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    years = selected.index.year + ((selected.index.month == 12) if months == (12, 1, 2) else 0)
    base = monthly[baseline_mask(monthly.index, cfg)]
    normal = base.groupby(base.index.month).mean()
    normal = normal.where(base.groupby(base.index.month).count() >= cfg.min_climatology_years)
    result = {}
    for year in range(int(years.min()), int(years.max()) + 1):
        group = selected[years == year]
        valid = group.dropna()
        # A changing mix of months can manufacture annual/seasonal trends and extremes.
        # Daily -> monthly coverage is configurable, but all constituent months must exist.
        required = len(months)
        if len(valid) < required:
            value = np.nan
            if (
                not total
                and cfg.annual_missing_policy == "climatology_adjusted"
                and len(valid) >= np.ceil(required * cfg.annual_min_coverage)
                and normal.reindex(months).notna().all()
            ):
                dates = pd.DatetimeIndex(
                    [
                        pd.Timestamp(year=year - int(months == (12, 1, 2) and m == 12), month=m, day=1)
                        for m in months
                    ]
                )
                full_normal = np.average(normal.reindex(months), weights=dates.days_in_month)
                observed_anomaly = valid.to_numpy() - normal.reindex(valid.index.month).to_numpy()
                value = float(full_normal + np.average(observed_anomaly, weights=valid.index.days_in_month))
        elif total:
            value = float(valid.sum())
        else:
            value = float(np.average(valid.to_numpy(), weights=valid.index.days_in_month))
        result[pd.Timestamp(year=year, month=1, day=1)] = value
    return pd.Series(result, dtype=float)


def observation_support(data: pd.Series, cfg: Config, frequency: int) -> dict | None:
    """Separate valid sample size, calendar duration and actual calendar coverage."""
    if data.empty or data.count() < cfg.min_years * frequency:
        return skipped(
            "insufficient_valid_observations", n=int(data.count()), required=cfg.min_years * frequency
        )
    pos = positions(data.index, frequency)
    expected = int(pos[-1] - pos[0] + 1)
    coverage = float(data.count() / expected)
    if coverage < cfg.min_coverage:
        return skipped(
            "insufficient_calendar_coverage",
            n=int(data.count()),
            calendar_steps=expected,
            coverage=coverage,
            required_coverage=cfg.min_coverage,
        )
    return None


def trend(
    data: pd.Series, cfg: Config, *, frequency: int = 1, units: str = "", ratio_scale: bool = False
) -> dict:
    valid = data.dropna()
    support_failure = observation_support(data, cfg, frequency)
    if support_failure:
        return support_failure
    pos = positions(valid.index, frequency)
    span = (pos[-1] - pos[0] + 1) / frequency
    if span < cfg.min_years:
        return skipped("record_shorter_than_min_years", record_years=span, min_years=cfg.min_years)
    if len(valid) > reference().MAX_PAIRWISE_N:
        return skipped("pairwise_point_limit_exceeded_use_annual_series", n=len(valid))
    t = (pos - pos[0]) / frequency
    y = valid.to_numpy()
    constant = np.ptp(y) < 1e-12
    engine = reference()
    mk = engine.mann_kendall(t, y, method="original", alpha=cfg.alpha)
    initial = engine.sens_slope(t, y, alpha=cfg.alpha)
    residual = y - (initial["intercept"] + initial["slope"] * t)
    phi, pairs = calendar_r1(residual, pos)
    if np.std(residual) <= 1e-10 * max(1.0, np.std(y)):
        phi = 0.0
    eta = ar1_inflation(pos, phi)
    var_s = mk["var_s"] * eta
    z = (mk["s"] - np.sign(mk["s"])) / np.sqrt(var_s) if var_s > 0 else 0.0
    p = float(2 * stats.norm.sf(abs(z)))
    sen = engine.sens_slope(t, y, alpha=cfg.alpha, var_s=var_s)
    design = np.column_stack([np.ones(len(t)), t - t.mean()])
    intercept, slope = np.linalg.lstsq(design, y, rcond=None)[0]
    ols_resid = y - design @ [intercept, slope]
    ols_phi, _ = calendar_r1(ols_resid, pos)
    if np.std(ols_resid) <= 1e-10 * max(1.0, np.std(y)):
        ols_phi = 0.0
    # Santer finite-sample df; regular data approach n*(1-rho)/(1+rho).
    n_eff = max(3.0, len(t) / ar1_inflation(pos, ols_phi))
    dof = n_eff - 2
    se = np.sqrt(np.sum(ols_resid**2) / dof / np.sum((t - t.mean()) ** 2))
    ols_p = 1.0 if constant else float(2 * stats.t.sf(abs(slope / se), dof)) if se > 0 else 0.0
    width = stats.t.ppf(1 - cfg.alpha / 2, dof) * se
    noise = float(np.std(residual, ddof=1))
    detectable = engine.years_to_detect(noise, max(0.0, phi), sen["slope"], frequency)
    total_change = sen["slope"] * (t[-1] - t[0])
    mean = float(np.mean(y))
    inference_available = pairs >= 4 or noise <= 1e-10 * max(1.0, np.std(y))
    if not inference_available:
        detectable = np.nan
    warnings = []
    if pairs < 4:
        warnings.append("Fewer than four adjacent residual pairs: serial dependence cannot be estimated.")
    if np.mean(y == 0) >= 0.25:
        warnings.append("At least 25% zeros: tied values can yield a zero Sen slope despite a rank trend.")
    if not constant and sen["slope"] == 0 and p < cfg.alpha:
        warnings.append(
            "Zero median pairwise slope with significant rank trend; inspect ties and distribution changes."
        )
    return {
        "status": "constant" if constant else "ok",
        "n": len(y),
        "record_years": span,
        "units": units,
        "time_unit": "year",
        "confidence_level": 1 - cfg.alpha,
        "inference_available": inference_available,
        "methods_disagree": bool((p <= cfg.alpha) != (ols_p <= cfg.alpha)) if inference_available else None,
        "conservative_significant_unadjusted": bool(p <= cfg.alpha and ols_p <= cfg.alpha)
        if inference_available
        else None,
        "sen": {
            "slope_per_year": sen["slope"],
            "slope_per_decade": 10 * sen["slope"],
            "ci_per_decade": [10 * c for c in sen["ci"]] if inference_available else None,
            "total_change": total_change,
            "percent_change_of_mean": 100 * total_change / mean
            if ratio_scale and np.all(y >= 0) and mean > 1e-12
            else None,
        },
        "mann_kendall": {
            "test": "mann_kendall_yue_wang_ar1_calendar",
            "p_value": p if inference_available else None,
            "z": z,
            "tau": mk["tau"],
            "s": mk["s"],
            "variance_correction": eta,
        },
        "ols": {
            "test": "ols_t_effective_sample_size",
            "p_value": ols_p if inference_available else None,
            "slope_per_decade": 10 * slope,
            "ci_per_decade": [10 * (slope - width), 10 * (slope + width)] if inference_available else None,
            "n_eff": n_eff,
            "residual_r1": ols_phi,
            "r_squared": 1 - np.sum(ols_resid**2) / np.sum((y - mean) ** 2) if not constant else None,
        },
        "noise": {"std": noise, "r1": phi, "adjacent_pairs": pairs},
        "detectability": {
            "years_needed": detectable if np.isfinite(detectable) else None,
            "additional_years": max(0.0, detectable - span) if np.isfinite(detectable) else None,
            "assumption": "AR(1), unchanged trend/noise; 90% power at alpha=0.05",
        },
        "warnings": warnings,
    }


def detrend(data: pd.Series, frequency: int = 1) -> pd.Series:
    out = data.copy()
    valid = data.dropna()
    if len(valid) < 4 or len(valid) > reference().MAX_PAIRWISE_N:
        return out * np.nan
    t = positions(valid.index, frequency).astype(float)
    t -= t[0]
    fit = reference().sens_slope(t, valid.to_numpy())
    out.loc[valid.index] = valid - (fit["intercept"] + fit["slope"] * t)
    return out


def block_indices(n: int, block: int, rng: np.random.Generator) -> np.ndarray:
    block = min(block, n)
    starts = rng.integers(0, n - block + 1, size=int(np.ceil(n / block)))
    return np.concatenate([np.arange(start, start + block) for start in starts])[:n]


def bootstrap_summary(estimates, estimate: float, cfg: Config) -> dict:
    samples = np.asarray(estimates, dtype=float)
    samples = samples[np.isfinite(samples)]
    counts = {
        "attempted": cfg.bootstrap_samples,
        "successful": len(samples),
        "failed": cfg.bootstrap_samples - len(samples),
    }
    if len(samples) != cfg.bootstrap_samples:
        return skipped("failed_bootstrap_replicates_no_conditional_inference", **counts)
    if len(samples) < max(19, cfg.bootstrap_samples // 2):
        return skipped("too_few_successful_bootstrap_replicates", **counts)
    lo, hi = np.quantile(samples, [cfg.alpha / 2, 1 - cfg.alpha / 2])
    p = (1 + np.count_nonzero(np.abs(samples - estimate) >= abs(estimate))) / (len(samples) + 1)
    return {
        "status": "ok",
        "ci": [float(2 * estimate - hi), float(2 * estimate - lo)],
        "p_value": float(p),
        "test": "centered_block_bootstrap",
        **counts,
        "confidence_level": 1 - cfg.alpha,
        "p_value_resolution": 1 / (len(samples) + 1),
    }


def bootstrap_trend(data: pd.Series, cfg: Config, key: str, *, frequency: int = 12) -> dict:
    if not cfg.bootstrap_samples:
        return skipped("bootstrap_disabled")
    if data.isna().any():
        return skipped("bootstrap_requires_a_complete_regular_series_no_gap_compression")
    block = cfg.block_months if frequency == 12 else cfg.block_years
    if len(data) < max(cfg.min_years * frequency, 2 * block, 4):
        return skipped("insufficient_data_for_blocks")
    if len(data) > reference().MAX_PAIRWISE_N:
        return skipped("pairwise_point_limit_exceeded")
    t = np.arange(len(data), dtype=float) / frequency
    y = data.to_numpy()
    fit = reference().sens_slope(t, y)
    fitted = fit["intercept"] + fit["slope"] * t
    residual = y - fitted
    residual -= residual.mean()
    rng = rng_for(cfg, key)
    estimates = [
        reference().sens_slope(t, fitted + residual[block_indices(len(y), block, rng)])["slope"] * 10
        for _ in range(cfg.bootstrap_samples)
    ]
    return {
        **bootstrap_summary(estimates, fit["slope"] * 10, cfg),
        "estimate_per_decade": fit["slope"] * 10,
        "block_length": block,
        "step": "month" if frequency == 12 else "year",
        "resampling": "moving_blocks_of_detrended_residuals",
    }


def apply_fdr(result: dict, cfg: Config) -> dict:
    tests = []

    def walk(node, path):
        if isinstance(node, dict):
            p = node.get("p_value")
            if isinstance(p, (float, int)) and np.isfinite(p) and 0 <= p <= 1:
                tests.append((path, node))
            for key, child in node.items():
                if key in {"metadata", "provenance", "config", "insights_audit"}:
                    continue
                escaped = str(key).replace("~", "~0").replace("/", "~1")
                walk(child, f"{path}/{escaped}")
        elif isinstance(node, list):
            for i, child in enumerate(node):
                walk(child, f"{path}/{i}")

    walk(result, "")
    flags, qvals = reference().fdr_bh([node["p_value"] for _, node in tests], q=cfg.fdr_q)
    audit = []
    for (path, node), flag, q in zip(tests, flags, qvals):
        node.update(
            q_value=float(q),
            significant_unadjusted=bool(node["p_value"] <= cfg.alpha),
            significant_fdr=bool(flag),
        )
        audit.append(
            {
                "path": path,
                "test": node.get("test"),
                "p_value": node["p_value"],
                "q_value": float(q),
                "significant_fdr": bool(flag),
            }
        )

    def agreement(node):
        if isinstance(node, dict):
            if isinstance(node.get("mann_kendall"), dict) and isinstance(node.get("ols"), dict):
                a, b = node["mann_kendall"], node["ols"]
                node["conservative_significant_fdr"] = bool(
                    a.get("significant_fdr") and b.get("significant_fdr")
                )
            for key, child in node.items():
                if key in {"metadata", "provenance", "config", "insights_audit"}:
                    continue
                agreement(child)
        elif isinstance(node, list):
            for child in node:
                agreement(child)

    agreement(result)
    resolution = [
        {"path": path, "minimum_p": node["p_value_resolution"]}
        for path, node in tests
        if "p_value_resolution" in node
    ]
    return {
        "method": "Benjamini-Hochberg",
        "family": "all_computed_tests_in_this_input_document",
        "q_threshold": cfg.fdr_q,
        "tested": len(tests),
        "significant": int(np.sum(flags)),
        "assumption": "Independent or positively dependent tests; exploratory, not causal attribution.",
        "resampling_resolution": resolution,
        "replicates_for_rank_one_resolution": max(0, int(np.ceil(len(tests) / cfg.fdr_q)) - 1),
        "warnings": [
            "Finite resampling resolution may limit BH power; a single global family is retained and not selected after seeing significance."
        ]
        if resolution
        else [],
        "tests": audit,
    }
