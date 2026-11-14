"""Run catalog-aware regional climate statistics without downloading anything."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections import defaultdict
from importlib.metadata import version
from pathlib import Path

from .contracts import ROOT, parse_payload
from .core import (
    annual_aggregate,
    apply_fdr,
    bootstrap_trend,
    climatology,
    describe,
    json_safe,
    quality,
    records,
    skipped,
    to_monthly,
    trend,
)
from .indices import daily_indices, drought_indices, temperature_combinations
from .relationships import adjusted_drivers, correlations, region_contrasts
from .temporal import (
    acceleration,
    change_point,
    emergence,
    probability_change,
    profiles,
    quantile_trends,
    variability,
)


def analyze(payload: dict) -> dict:
    """Analyze a version-1.0 JSON-compatible payload and return strict-JSON-compatible results.

    Values are decoded physical observations (not satellite packed integers). Every series
    represents one regional mean or point. No fetching, interpolation or causal attribution.
    Invalid input raises ValueError; inapplicable methods return an explicit skipped reason.
    """
    cfg, items, covariates, controls = parse_payload(payload)
    methods = set(cfg.methods)
    monthly, anomalies, results, regions = {}, {}, {}, defaultdict(list)
    for item in items:
        regions[item.region_id].append(item)
    for region, members in regions.items():
        latitudes = {s.latitude for s in members if s.latitude is not None}
        if len(latitudes) > 1:
            raise ValueError(
                f"Region {region!r} has conflicting latitudes; use a consistent region/point definition"
            )
    for item in items:
        series = to_monthly(item, cfg)
        monthly[item.id] = series
        annual_input = item.frequency == "annual"
        if annual_input and set(cfg.annual_months) != set(range(1, 13)):
            raise ValueError("annual_months cannot select months from annual input")
        total = item.variable_id == "PRECTOTCORR_SUM"
        ratio_scale = bool(item.entry.get("percent_change_meaningful", False))
        if annual_input:
            anomaly = series.copy()
            seasonal_cycle = skipped("annual_input_has_no_monthly_climatology")
            annual = series
        else:
            anomaly, seasonal_cycle = climatology(series, cfg)
            annual = annual_aggregate(series, cfg, total=total)
        anomalies[item.id] = anomaly
        annual_units = (
            ("mm/year" if len(cfg.annual_months) == 12 else "mm/selected_months") if total else item.units
        )
        output = {
            "variable_id": item.variable_id,
            "region_id": item.region_id,
            "name": item.entry["name"],
            "input_frequency": item.frequency,
            "analysis_frequency": "annual" if annual_input else "monthly",
            "input_units": item.input_units,
            "units": item.units,
            "conversion_applied": item.conversion,
            "input_values": "already_scale_decoded_physical_values",
            "provenance": item.provenance,
            "source": item.entry.get("source"),
            "how_measured": item.entry.get("how_measured"),
            "quality": quality(item),
            "catalog_status": item.entry.get("status"),
            "analysis_quality": {
                "valid_steps": int(series.count()),
                "calendar_steps": len(series),
                "coverage": float(series.count() / len(series)),
                "valid_annual_aggregates": int(annual.count()),
            },
            "descriptive": describe(item.data, ratio_scale=ratio_scale),
            "analysis_descriptive": describe(series, ratio_scale=ratio_scale),
            "climatology": seasonal_cycle,
            "annual": {
                "units": annual_units,
                "months": list(cfg.annual_months),
                "year_label": "year_of_January" if set(cfg.annual_months) == {12, 1, 2} else "calendar_year",
                "missing_policy": "strict" if total else cfg.annual_missing_policy,
                "minimum_month_coverage": 1.0
                if total or cfg.annual_missing_policy == "strict"
                else cfg.annual_min_coverage,
                "caveat": "Climatology-adjusted partial means assume observed monthly anomalies represent the missing months; totals always require complete months."
                if cfg.annual_missing_policy == "climatology_adjusted" and not total
                else None,
                "aggregation": "sum_of_complete_monthly_totals"
                if total
                else "input_annual"
                if annual_input
                else "climatology_adjusted_day_weighted_mean"
                if cfg.annual_missing_policy == "climatology_adjusted"
                else "day_weighted_mean_of_qualified_months",
                "descriptive": describe(annual, ratio_scale=ratio_scale),
            },
        }
        if cfg.include_series:
            output["analysis_series"] = records(series)
            output["annual"]["series"] = records(annual)
        if "trend" in methods or "emergence" in methods:
            output["annual"]["trend"] = trend(annual, cfg, units=annual_units, ratio_scale=ratio_scale)
        if "trend" in methods:
            output["trend"] = trend(anomaly, cfg, frequency=1 if annual_input else 12, units=item.units)
            output["trend"]["basis"] = "annual_values" if annual_input else "calendar_month_anomalies"
            # Relative change must use the physical mean, never the (near-zero) anomaly mean.
            if output["trend"].get("status") in ("ok", "constant"):
                mean = series.mean()
                if ratio_scale and series.dropna().ge(0).all() and mean > 1e-12:
                    output["trend"]["sen"]["percent_change_of_mean"] = (
                        100 * output["trend"]["sen"]["total_change"] / mean
                    )
        if "monthly_profile" in methods or "seasonal" in methods:
            if annual_input:
                monthly_profile, seasonal = skipped("monthly_data_required"), skipped("monthly_data_required")
            else:
                monthly_profile, seasonal = profiles(series, cfg, item.units, total=total)
            if "monthly_profile" in methods:
                output["monthly_profile"] = monthly_profile
            if "seasonal" in methods:
                output["seasonal"] = seasonal
        if "emergence" in methods:
            output["emergence"] = emergence(annual, output["annual"]["trend"], cfg)
            output["emergence"]["noise_units"] = annual_units
        if "probability" in methods:
            output["probability_change"] = probability_change(annual, cfg, item.id + ":probability")
            output["probability_change"]["threshold_units"] = annual_units
        if "quantiles" in methods:
            output["quantile_trends"] = quantile_trends(
                anomaly, cfg, item.id + ":quantiles", frequency=1 if annual_input else 12
            )
        if "acceleration" in methods:
            output["acceleration"] = acceleration(annual, cfg, item.id + ":acceleration", annual_units)
        if "variability" in methods:
            output["variability"] = variability(annual, cfg, item.id + ":variability")
            output["variability"]["sd_units"] = annual_units
        if "bootstrap" in methods:
            output["bootstrap"] = bootstrap_trend(
                anomaly, cfg, item.id + ":bootstrap", frequency=1 if annual_input else 12
            )
        if "change_point" in methods:
            output["change_point"] = change_point(annual, cfg, item.id + ":change_point")
        if "indices" in methods:
            output["daily_indices"] = daily_indices(item, cfg)
        results[item.id] = output
    derived = {}
    for region, members in regions.items():
        derived[region] = {}
        if "indices" in methods:
            derived[region]["temperature"] = temperature_combinations(members, cfg)
        if "drought" in methods:
            derived[region]["drought"] = drought_indices(members, cfg)
    output = {
        "schema_version": "1.0",
        "pipeline_version": "1.1.0",
        "status": "ok",
        "config": cfg.json(),
        "metadata": payload.get("metadata", {}),
        "provenance": {
            "input_sha256": hashlib.sha256(
                json.dumps(payload, sort_keys=True, allow_nan=False, ensure_ascii=False).encode("utf-8")
            ).hexdigest(),
            "catalog_sha256": hashlib.sha256((ROOT / "data/catalog/variables.yaml").read_bytes()).hexdigest(),
            "reference_engine_sha256": hashlib.sha256(
                (ROOT / ".claude/skills/trend-stats/scripts/trend_stats.py").read_bytes()
            ).hexdigest(),
            "libraries": {name: version(name) for name in ("numpy", "scipy", "pandas", "PyYAML")},
            "random_seed": cfg.seed,
        },
        "assumptions": [
            "Each input series is an already spatially aggregated regional/point record.",
            "No interpolation; calendar gaps remain gaps. No automatic downloading.",
            "Baseline is explicit or the full input record; insufficient baseline months are not substituted.",
            "Trend inference uses an AR(1) approximation; arbitrary long-memory dependence is not guaranteed.",
            "Bootstrap requires complete regular series; event permutation refits its baseline threshold in every replicate.",
            "All computed p-values form one document-wide BH family, including secondary trend checks.",
            "Statistical associations and SPI/SPEI comparisons do not establish causal attribution.",
        ],
        "series": results,
        "derived": derived,
    }
    if "relationships" in methods:
        output["relationships"] = correlations(items, anomalies, cfg)
        output["region_contrasts"] = region_contrasts(items, monthly, cfg)
    if "drivers" in methods:
        for covariate in covariates:
            monthly[covariate.id] = to_monthly(covariate, cfg)
        output["drivers"] = (
            adjusted_drivers(controls, items, covariates, monthly, anomalies, cfg)
            if controls
            else skipped("supply_covariates_and_explicit_controls_for_NAO_or_other_driver_adjustment")
        )
    output["insights_audit"] = apply_fdr(output, cfg)
    for item in output["series"].values():
        toe = item.get("emergence", {})
        if toe.get("status") == "ok" and item["annual"].get("trend", {}).get("conservative_significant_fdr"):
            toe["year"] = toe["candidate_year"]
    return json_safe(output)


def _invalid_constant(value):
    raise ValueError(f"Invalid JSON numeric constant {value}; use null for missing values")


def analyze_file(input_path: str | Path, output_path: str | Path) -> dict:
    """Read UTF-8/BOM JSON, analyze and atomically write strict JSON. Never overwrite input."""
    source, destination = Path(input_path), Path(output_path)
    if source.resolve() == destination.resolve():
        raise ValueError("Input and output paths must differ")
    payload = json.loads(source.read_text(encoding="utf-8-sig"), parse_constant=_invalid_constant)
    result = analyze(payload)
    encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            delete=False,
            dir=destination.parent,
            prefix=destination.name + ".",
            suffix=".tmp",
        ) as handle:
            tmp = Path(handle.name)
            handle.write(encoded)
        os.replace(tmp, destination)
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()
    return result
