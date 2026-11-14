"""Aligned, detrended associations, regional contrasts and optional external controls."""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats

from .contracts import Config, InputSeries
from .core import (
    ar1_inflation,
    calendar_r1,
    climatology,
    describe,
    detrend,
    observation_support,
    positions,
    skipped,
    trend,
)


def correlations(items: list[InputSeries], anomalies: dict[str, pd.Series], cfg: Config) -> list[dict]:
    out = []
    residuals = {
        item.id: detrend(anomalies[item.id], 1 if item.frequency == "annual" else 12) for item in items
    }
    for left, right in combinations(items, 2):
        if left.region_id != right.region_id and left.variable_id != right.variable_id:
            continue
        if (left.frequency == "annual") != (right.frequency == "annual"):
            continue
        frequency = 1 if left.frequency == "annual" else 12
        for lag in cfg.correlation_lags:
            a = residuals[left.id].shift(lag)
            b = residuals[right.id]
            aligned = pd.concat([a.rename("x"), b.rename("y")], axis=1)
            # Evaluate coverage over the common observation window, including its gaps.
            aligned = aligned.loc[max(a.index.min(), b.index.min()) : min(a.index.max(), b.index.max())]
            paired_x = aligned.x.where(aligned.y.notna())
            pair = aligned.dropna()
            result = {
                "left_series_id": left.id,
                "right_series_id": right.id,
                "lag": lag,
                "lag_unit": "year" if frequency == 1 else "month",
                "lag_definition": "left at t-lag correlated with right at t",
                "n": len(pair),
                "preprocessing": "remove_calendar_month_climatology_then_each_series_Sen_trend",
            }
            failure = observation_support(paired_x, cfg, frequency)
            if failure:
                out.append({**result, **failure})
                continue
            x, y = pair.x.to_numpy(), pair.y.to_numpy()
            if min(np.std(x), np.std(y)) < 1e-12:
                out.append({**result, **skipped("constant_detrended_series")})
                continue
            pos = positions(pair.index, frequency)
            coefficients = {}
            for name, v1, v2 in (("pearson", x, y), ("spearman", stats.rankdata(x), stats.rankdata(y))):
                r = float(np.clip(np.corrcoef(v1, v2)[0, 1], -1, 1))
                phi1, pairs1 = calendar_r1(v1, pos)
                phi2, pairs2 = calendar_r1(v2, pos)
                infer = min(pairs1, pairs2) >= 4
                n_eff = max(4.0, len(x) / ar1_inflation(pos, max(0.0, phi1 * phi2)))
                dof = n_eff - 3  # Time was fitted/removed before measuring association.
                statistic = abs(r) * np.sqrt(dof / max(1e-15, 1 - r * r))
                z_width = stats.norm.ppf(1 - cfg.alpha / 2) / np.sqrt(max(1, n_eff - 3))
                fisher = np.arctanh(np.clip(r, -1 + 1e-12, 1 - 1e-12))
                coefficients[name] = {
                    "coefficient": r,
                    "n_eff": n_eff,
                    "test": f"{name}_AR1_effective_n_t_approximation",
                    "p_value": float(2 * stats.t.sf(statistic, dof)) if infer else None,
                    "ci_fisher_approximate": np.tanh([fisher - z_width, fisher + z_width]) if infer else None,
                    "inference_available": infer,
                    "adjacent_pairs": min(pairs1, pairs2),
                }
            out.append(
                {
                    **result,
                    "status": "ok",
                    **coefficients,
                    "caveat": "Association after detrending; approximate AR(1) inference, not causation or source independence.",
                }
            )
    return out


def region_contrasts(items: list[InputSeries], monthly: dict[str, pd.Series], cfg: Config) -> list[dict]:
    output = []
    for left, right in combinations(items, 2):
        if left.variable_id != right.variable_id or left.region_id == right.region_id:
            continue
        if (left.frequency == "annual") != (right.frequency == "annual"):
            continue
        paired = pd.concat([monthly[left.id].rename("left"), monthly[right.id].rename("right")], axis=1)
        difference = paired.left - paired.right
        if left.frequency != "annual":
            difference, _ = climatology(difference, cfg)
        output.append(
            {
                "left_series_id": left.id,
                "right_series_id": right.id,
                "definition": "left minus right, matched timestamps; trend tests divergence between regions",
                "paired_difference": describe(paired.left - paired.right),
                "trend": trend(
                    difference, cfg, frequency=1 if left.frequency == "annual" else 12, units=left.units
                ),
            }
        )
    return output


def _hac_covariance(design: np.ndarray, residual: np.ndarray, pos: np.ndarray, lags: int) -> np.ndarray:
    """Newey-West sandwich with Bartlett weights and actual calendar lags."""
    scores = design * residual[:, None]
    meat = scores.T @ scores
    for lag in range(1, lags + 1):
        right = np.searchsorted(pos, pos + lag)
        left = np.flatnonzero(right < len(pos))
        left = left[pos[right[left]] == pos[left] + lag]
        cross = scores[left].T @ scores[right[left]]
        meat += (1 - lag / (lags + 1)) * (cross + cross.T)
    bread = np.linalg.inv(design.T @ design)
    n, k = design.shape
    return (n / (n - k)) * bread @ meat @ bread


def adjusted_drivers(
    controls: list[dict],
    items: list[InputSeries],
    covariates: list[InputSeries],
    monthly: dict[str, pd.Series],
    anomalies: dict[str, pd.Series],
    cfg: Config,
) -> list[dict]:
    catalog = {s.id: s for s in items + covariates}
    outputs = []
    for control in controls:
        item = catalog[control["series_id"]]
        controls_ids = control["covariate_ids"]
        freq = 1 if item.frequency == "annual" else 12
        names = [item.id, *controls_ids]
        result = {
            "series_id": item.id,
            "covariate_ids": controls_ids,
            "months": control.get("months", list(range(1, 13))),
        }
        if freq == 1 and set(result["months"]) != set(range(1, 13)):
            outputs.append({**result, **skipped("calendar_month_filter_requires_monthly_input")})
            continue
        if any((catalog[k].frequency == "annual") != (item.frequency == "annual") for k in controls_ids):
            outputs.append({**result, **skipped("target_and_covariate_frequencies_do_not_match")})
            continue
        frame = pd.concat(
            [monthly[item.id].rename(item.id)] + [monthly[k].rename(k) for k in controls_ids], axis=1
        )
        common_start = max(monthly[k].index.min() for k in names)
        common_end = min(monthly[k].index.max() for k in names)
        frame = frame.loc[common_start:common_end]
        if freq == 12:
            frame = frame[frame.index.month.isin(result["months"])]
        expected = len(frame)
        frame = frame.dropna()
        if not expected or len(frame) / expected < cfg.min_coverage:
            outputs.append(
                {
                    **result,
                    **skipped(
                        "insufficient_aligned_control_coverage",
                        coverage=len(frame) / expected if expected else 0,
                    ),
                }
            )
            continue
        if len(frame) < max(cfg.min_years * (len(result["months"]) if freq == 12 else 1), 2 * len(names) + 4):
            outputs.append({**result, **skipped("insufficient_aligned_control_observations")})
            continue
        inference_frequency = 1 if freq == 1 or len(result["months"]) == 1 else 12
        pos = positions(frame.index, inference_frequency)
        t = (pos - pos[0]) / inference_frequency
        t = t - t.mean()
        raw_cov = frame[controls_ids].to_numpy()
        scales = np.std(raw_cov, axis=0)
        if np.any(scales < 1e-12):
            outputs.append({**result, **skipped("constant_covariate")})
            continue
        standardized = (raw_cov - raw_cov.mean(axis=0)) / scales
        # Joint month fixed effects residualize y, time and controls consistently (FWL).
        month_design = (
            pd.get_dummies(frame.index.month, drop_first=True, dtype=float).to_numpy()
            if freq == 12
            else np.empty((len(t), 0))
        )
        design = np.column_stack([np.ones(len(t)), t, standardized, month_design])
        if np.linalg.matrix_rank(design) < design.shape[1] or np.linalg.cond(design) > 1e6:
            outputs.append({**result, **skipped("collinear_time_and_covariates")})
            continue
        y = frame[item.id].to_numpy()
        coef = np.linalg.lstsq(design, y, rcond=None)[0]
        residual = y - design @ coef
        phi, adjacent = calendar_r1(residual, pos)
        dof = len(y) - design.shape[1]
        if dof <= 2:
            outputs.append({**result, **skipped("insufficient_effective_degrees_of_freedom")})
            continue
        lags = cfg.block_months if inference_frequency == 12 else cfg.block_years
        covariance = _hac_covariance(design, residual, pos, lags)
        se = np.sqrt(np.maximum(0, np.diag(covariance)))
        critical = stats.t.ppf(1 - cfg.alpha / 2, dof)

        def term(i, multiplier=1.0, *, coef=coef, se=se, dof=dof, critical=critical):
            p = (
                float(2 * stats.t.sf(abs(coef[i] / se[i]), dof))
                if se[i] > 1e-14
                else (0.0 if abs(coef[i]) > 1e-12 else 1.0)
            )
            return {
                "estimate": float(coef[i] * multiplier),
                "test": "multiple_OLS_Newey_West_t_approximation",
                "p_value": p,
                "ci": [(coef[i] - critical * se[i]) * multiplier, (coef[i] + critical * se[i]) * multiplier],
            }

        raw_design = np.column_stack([design[:, :2], month_design])
        raw_slope = np.linalg.lstsq(raw_design, y, rcond=None)[0][1]
        total = np.sum((y - y.mean()) ** 2)
        outputs.append(
            {
                **result,
                "status": "ok",
                "n": len(y),
                "degrees_of_freedom": dof,
                "hac_calendar_lags": lags,
                "hac_lag_unit": "month" if inference_frequency == 12 else "year",
                "seasonality": "calendar_month_fixed_effects_on_common_sample"
                if freq == 12
                else "annual_input",
                "residual_r1": phi,
                "adjacent_pairs": adjacent,
                "raw_slope_per_decade": raw_slope * 10,
                "target_units": item.units,
                "adjusted_slope_per_decade": term(1, 10),
                "covariate_coefficients": {
                    name: term(i + 2, 1 / scales[i]) for i, name in enumerate(controls_ids)
                },
                "r_squared": 1 - np.sum(residual**2) / total if total > 0 else None,
                "design_condition_number": float(np.linalg.cond(design)),
                "caveat": "HAC is asymptotic and bandwidth-dependent; covariate relevance and confounding require interpretation.",
            }
        )
    return outputs
