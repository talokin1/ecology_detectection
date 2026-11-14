"""Aligned, detrended associations, regional contrasts and optional external controls."""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats

from .contracts import Config, InputSeries
from .core import ar1_inflation, calendar_r1, climatology, describe, detrend, positions, skipped, trend


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
            pair = pd.concat([a.rename("x"), b.rename("y")], axis=1).dropna()
            result = {
                "left_series_id": left.id,
                "right_series_id": right.id,
                "lag": lag,
                "lag_unit": "year" if frequency == 1 else "month",
                "lag_definition": "left at t-lag correlated with right at t",
                "n": len(pair),
                "preprocessing": "remove_calendar_month_climatology_then_each_series_Sen_trend",
            }
            if len(pair) < max(cfg.min_years * frequency * cfg.min_coverage, 8):
                out.append({**result, **skipped("insufficient_overlapping_data")})
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
            [anomalies[item.id].rename(item.id)] + [monthly[k].rename(k) for k in controls_ids], axis=1
        )
        if freq == 12:
            frame = frame[frame.index.month.isin(result["months"])]
        frame = frame.dropna()
        if len(frame) < max(cfg.min_years * (len(result["months"]) if freq == 12 else 1), 2 * len(names) + 4):
            outputs.append({**result, **skipped("insufficient_aligned_control_observations")})
            continue
        pos = positions(frame.index, freq)
        t = (pos - pos[0]) / freq
        t = t - t.mean()
        raw_cov = frame[controls_ids].to_numpy()
        scales = np.std(raw_cov, axis=0)
        if np.any(scales < 1e-12):
            outputs.append({**result, **skipped("constant_covariate")})
            continue
        standardized = (raw_cov - raw_cov.mean(axis=0)) / scales
        design = np.column_stack([np.ones(len(t)), t, standardized])
        if np.linalg.matrix_rank(design) < design.shape[1] or np.linalg.cond(design) > 1e6:
            outputs.append({**result, **skipped("collinear_time_and_covariates")})
            continue
        y = frame[item.id].to_numpy()
        coef = np.linalg.lstsq(design, y, rcond=None)[0]
        residual = y - design @ coef
        phi, adjacent = calendar_r1(residual, pos)
        if adjacent < 4 and np.std(residual) > 1e-10 * max(1, np.std(y)):
            outputs.append({**result, **skipped("insufficient_adjacent_residual_pairs_for_serial_inference")})
            continue
        n_eff = len(y) / ar1_inflation(pos, phi)
        dof = n_eff - design.shape[1]
        if dof <= 2:
            outputs.append({**result, **skipped("insufficient_effective_degrees_of_freedom")})
            continue
        covariance = np.sum(residual**2) / dof * np.linalg.inv(design.T @ design)
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
                "test": "multiple_OLS_t_effective_sample_size",
                "p_value": p,
                "ci": [(coef[i] - critical * se[i]) * multiplier, (coef[i] + critical * se[i]) * multiplier],
            }

        raw_design = design[:, :2]
        raw_slope = np.linalg.lstsq(raw_design, y, rcond=None)[0][1]
        total = np.sum((y - y.mean()) ** 2)
        outputs.append(
            {
                **result,
                "status": "ok",
                "n": len(y),
                "n_eff": n_eff,
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
                "caveat": "User-supplied covariates only; regional/seasonal relevance and confounding require interpretation.",
            }
        )
    return outputs
