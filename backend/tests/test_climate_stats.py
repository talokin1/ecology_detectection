"""Offline contract, mathematical and edge-case tests for the JSON climate pipeline."""

from __future__ import annotations

import json
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest
from jsonschema import Draft202012Validator
from trend_detective.climate_stats import analyze, analyze_file
from trend_detective.climate_stats.contracts import ROOT, Config, catalog, parse_series
from trend_detective.climate_stats.core import (
    annual_aggregate,
    apply_fdr,
    ar1_inflation,
    bootstrap_trend,
    calendar_r1,
    climatology,
    reference,
    trend,
)
from trend_detective.climate_stats.indices import (
    _calendar_day,
    daily_indices,
    extraterrestrial_radiation,
    growing_season,
    hargreaves_pet,
    precipitation_totals,
    standardized_drought,
)
from trend_detective.climate_stats.temporal import _quantile_fit, quantile_trends


def series(
    vid="air_temperature_power",
    values=None,
    *,
    n=360,
    sid="x",
    units="degC",
    frequency="monthly",
    start="1981-01-01",
    **extra,
):
    index = pd.date_range(start, periods=n, freq={"monthly": "MS", "annual": "YS", "daily": "D"}[frequency])
    values = np.full(n, 10.0) if values is None else values
    return {
        "id": sid,
        "variable_id": vid,
        "region_id": "test",
        "frequency": frequency,
        "units": units,
        "values": [
            {"date": d.strftime("%Y-%m-%d"), "value": None if not np.isfinite(v) else float(v)}
            for d, v in zip(index, values)
        ],
        **extra,
    }


def payload(*items, **config):
    return {
        "schema_version": "1.0",
        "config": {"bootstrap_samples": 0, "include_series": False, "methods": ["trend"], **config},
        "series": list(items),
    }


def sample_values(n=360, beta=0.08, seed=5):
    t = np.arange(n)
    return 10 + 8 * np.sin(t * 2 * np.pi / 12) + beta * t / 12 + np.random.default_rng(seed).normal(0, 0.3, n)


def test_known_trend_and_strict_json_output():
    out = analyze(payload(series(values=sample_values())))
    main = out["series"]["x"]["trend"]
    assert main["sen"]["slope_per_decade"] == pytest.approx(0.8, abs=0.05)
    assert main["mann_kendall"]["p_value"] < 0.001
    assert main["mann_kendall"]["significant_fdr"]
    assert main["sen"]["percent_change_of_mean"] is None
    assert "NaN" not in json.dumps(out, allow_nan=False)
    schema = json.loads((ROOT / "schema/climate-output.schema.json").read_text())
    Draft202012Validator(schema).validate(out)


def test_constant_series_has_no_significant_test():
    out = analyze(payload(series(), methods=["trend", "emergence", "quantiles", "change_point"]))
    main = out["series"]["x"]["trend"]
    assert main["status"] == "constant"
    assert main["sen"]["slope_per_decade"] == 0
    assert main["mann_kendall"]["p_value"] == 1
    assert main["ols"]["p_value"] == 1
    assert out["insights_audit"]["significant"] == 0
    json.dumps(out, allow_nan=False)


def test_empty_and_short_series_report_reasons():
    for values in (np.full(12, np.nan), np.arange(12, dtype=float)):
        out = analyze(payload(series(values=values, n=12), methods=list(Config().methods)))
        assert out["series"]["x"]["trend"]["status"] == "skipped"
        assert "reason" in out["series"]["x"]["trend"]
        json.dumps(out, allow_nan=False)


def test_all_31_catalog_ids_accept_supplied_data_even_without_a_reader():
    items = []
    for vid, entry in catalog().items():
        unit = entry["units"]
        value = 280 if unit == "K" else 0.5 if unit == "1" else 10
        kwargs = {}
        if vid in ("T2M_MAX", "T2M_MIN"):
            kwargs["semantics"] = "mean_daily_maximum" if vid == "T2M_MAX" else "mean_daily_minimum"
        items.append(series(vid, np.full(12, value), n=12, sid=vid, units=unit, **kwargs))
    out = analyze(payload(*items, methods=[]))
    assert len(out["series"]) == 31
    assert out["series"]["land_surface_temperature_modis"]["descriptive"]["mean"] == pytest.approx(6.85)
    assert out["insights_audit"]["tested"] == 0


@pytest.mark.parametrize("units,value,expected", [("K", 283.15, 10), ("degC", 10, 10), ("°C", 10, 10)])
def test_temperature_units_are_converted_once(units, value, expected):
    s = parse_series(series(values=[value], n=1, units=units))
    assert s.data.iloc[0] == pytest.approx(expected)


def test_solar_and_fraction_units_and_raw_scaling_rejection():
    for units, value in (("W/m^2", 100), ("MJ/m^2/day", 8.64)):
        s = parse_series(series("solar_radiation_power", [value], n=1, units=units))
        assert s.data.iloc[0] == pytest.approx(8.64)
    s = parse_series(series("root_zone_soil_wetness_power", [50], n=1, units="%"))
    assert s.data.iloc[0] == 0.5
    with pytest.raises(ValueError, match="decode scale"):
        parse_series(series("ndvi_modis", [8000], n=1, units="1"))


@pytest.mark.parametrize("bad", [True, "12", float("inf"), float("nan"), 10**500])
def test_non_numeric_or_nonfinite_values_rejected(bad):
    s = series(n=1)
    s["values"][0]["value"] = bad
    with pytest.raises(ValueError):
        analyze(payload(s))


def test_unknown_duplicate_invalid_dates_and_config_rejected():
    cases = []
    s = series(n=2)
    s["values"][1]["date"] = "1981-01-20"
    cases.append(payload(s))
    s = series(n=1)
    s["values"][0]["date"] = "1981-02-30"
    cases.append(payload(s))
    cases.extend(
        [
            payload(series("bogus", n=1)),
            payload(series(n=1), min_yeers=10),
            payload(series(n=1), baseline=[2000, 1990]),
            payload(series(n=1), alpha=True),
            payload(series(n=1), bootstrap_samples=2),
            payload(series(n=1), methods=["unknown"]),
        ]
    )
    for case in cases:
        with pytest.raises(ValueError):
            analyze(case)


def test_monthly_extreme_semantics_are_explicit():
    with pytest.raises(ValueError, match="semantics"):
        parse_series(series("T2M_MAX"))
    s = parse_series(series("T2M_MAX", semantics="mean_daily_maximum"))
    assert s.data.count() == 360


def test_missing_dates_and_declared_sentinels_keep_calendar_gaps():
    s = series(n=3)
    del s["values"][1]
    s["values"][1]["value"] = -999
    s["fill_values"] = [-999]
    parsed = parse_series(s)
    assert len(parsed.data) == 3
    assert parsed.data.isna().sum() == 2
    assert parsed.missing_sentinels == 1


def test_calendar_autocorrelation_never_connects_years_across_gaps():
    pos = np.array([0, 1, 2, 3, 4, 20, 21, 22, 23, 24])
    values = np.arange(10, dtype=float)
    _, pairs = calendar_r1(values, pos)
    assert pairs == 8
    regular = np.arange(10)
    rho = 0.7
    expected = 1 + 2 * np.sum((1 - np.arange(1, 10) / 10) * rho ** np.arange(1, 10))
    assert ar1_inflation(regular, rho) == pytest.approx(expected)
    assert ar1_inflation(pos, rho) < ar1_inflation(regular, rho)


def test_serial_correlation_widens_ci_against_iid():
    rng = np.random.default_rng(36)
    noise = np.zeros(360)
    for i in range(1, len(noise)):
        noise[i] = 0.8 * noise[i - 1] + rng.normal()
    values = 0.03 * np.arange(360) / 12 + noise
    data = pd.Series(values, index=pd.date_range("1981-01-01", periods=360, freq="MS"))
    fitted = trend(data, Config(), frequency=12)
    iid = reference().sens_slope(np.arange(360) / 12, values)
    ci = fitted["sen"]["ci_per_decade"]
    assert fitted["mann_kendall"]["variance_correction"] > 2
    assert ci[1] - ci[0] > 10 * (iid["ci"][1] - iid["ci"][0])


def test_baseline_is_not_silently_replaced():
    data = pd.Series(sample_values(), index=pd.date_range("1981-01-01", periods=360, freq="MS"))
    anomaly, info = climatology(data, Config(baseline=(2050, 2060)))
    assert anomaly.isna().all()
    assert info["status"] == "insufficient_data"


def test_annual_and_djf_coverage_and_year_label():
    idx = pd.date_range("2000-01-01", "2002-12-01", freq="MS")
    data = pd.Series(idx.month.astype(float), index=idx)
    annual = annual_aggregate(data, Config())
    assert annual.notna().all()
    data.loc["2001-05-01"] = np.nan
    assert np.isnan(annual_aggregate(data, Config()).loc["2001-01-01"])
    winter = annual_aggregate(data, Config(), months=(12, 1, 2))
    assert np.isnan(winter.loc["2000-01-01"])
    assert winter.loc["2001-01-01"] == pytest.approx((12 * 31 + 1 * 31 + 2 * 28) / 90)


def test_bh_matches_known_adjusted_probabilities_and_covers_all_tests():
    result = {
        "a": {"p_value": 0.01},
        "b": [{"p_value": 0.04}, {"p_value": 0.03}],
        "missing": {"p_value": None},
    }
    audit = apply_fdr(result, Config())
    assert audit["tested"] == 3
    assert result["a"]["q_value"] == pytest.approx(0.03)
    assert result["b"][0]["q_value"] == pytest.approx(0.04)
    assert audit["significant"] == 3


def test_bootstrap_reproducible_and_gaps_not_compressed():
    idx = pd.date_range("1981-01-01", periods=15, freq="YS")
    data = pd.Series(0.2 * np.arange(15) + np.sin(np.arange(15)), index=idx)
    cfg = Config(bootstrap_samples=19)
    assert bootstrap_trend(data, cfg, "same", frequency=1) == bootstrap_trend(data, cfg, "same", frequency=1)
    data.iloc[4] = np.nan
    assert bootstrap_trend(data, cfg, "same", frequency=1)["status"] == "skipped"


def test_daily_frost_counts_leap_days_and_missing_year_is_not_zero():
    item = parse_series(
        series("T2M_MIN", -np.ones(366), n=366, frequency="daily", start="2000-01-01", latitude=49)
    )
    result = daily_indices(item, Config(include_series=True))
    assert result["indices"]["fd"]["series"][0]["value"] == 366
    item.data.iloc[10] = np.nan
    result = daily_indices(item, Config(include_series=True))
    assert result["indices"]["fd"]["series"][0]["value"] is None


def test_dry_spell_and_monthly_total_need_actual_daily_values():
    values = np.full(365, 2.0)
    values[20:35] = 0
    item = parse_series(series("precipitation_power", values, n=365, frequency="daily", units="mm/day"))
    result = daily_indices(item, Config())
    assert result["indices"]["cdd"]["series"][0]["value"] == 15
    totals = precipitation_totals(item, Config())
    assert totals.iloc[0] == 40
    item.data.iloc[0] = np.nan
    assert np.isnan(precipitation_totals(item, Config()).iloc[0])


@pytest.mark.parametrize("latitude,start", [(49, "2001-01-01"), (-30, "2001-07-01")])
def test_growing_season_handles_both_hemispheres(latitude, start):
    idx = pd.date_range(start, periods=365, freq="D")
    values = np.zeros(365)
    values[90:281] = 10
    result = growing_season(pd.Series(values, index=idx), latitude, Config())
    vals = [r["value"] for r in result["series"] if r["value"] is not None]
    assert vals == [191]


def test_tx90p_calendar_does_not_shift_after_leap_day():
    idx = pd.to_datetime(["2000-02-28", "2000-02-29", "2000-03-01", "2001-03-01"])
    np.testing.assert_array_equal(_calendar_day(idx), [59, 0, 60, 60])


def test_pet_has_radiation_to_water_conversion_and_polar_night():
    idx = pd.to_datetime(["2001-06-01"])
    hi, lo = pd.Series([25.0], index=idx), pd.Series([15.0], index=idx)
    pet = hargreaves_pet(hi, lo, 45).iloc[0]
    ra = extraterrestrial_radiation(pd.date_range("2001-06-01", "2001-06-30"), 45).mean()
    expected = 0.0023 * 0.408 * ra * 37.8 * np.sqrt(10) * 30
    assert pet == pytest.approx(expected)
    assert 120 < pet < 160
    assert extraterrestrial_radiation(pd.to_datetime(["2001-12-21"]), 89)[0] == pytest.approx(0)


def test_spi_calibration_and_missing_accumulation_window():
    idx = pd.date_range("1981-01-01", periods=480, freq="MS")
    rain = pd.Series(np.random.default_rng(2).gamma(2, 30, len(idx)), index=idx)
    rain.iloc[400] = np.nan
    result = standardized_drought(rain, 3, "spi", Config(baseline=(1981, 2010)))
    assert result["status"] == "ok"
    assert all(result["series"][i]["value"] is None for i in (0, 1, 400, 401, 402))
    assert result["trend"]["n"] <= 40
    z = np.array([r["value"] for r in result["series"][:360] if r["value"] is not None])
    assert abs(np.mean(z)) < 0.15
    assert 0.8 < np.std(z) < 1.2


def test_all_zero_precipitation_does_not_invent_spi():
    idx = pd.date_range("1981-01-01", periods=480, freq="MS")
    result = standardized_drought(pd.Series(0.0, index=idx), 3, "spi", Config())
    assert result["status"] == "insufficient_data"
    assert all(r["value"] is None for r in result["series"])


def test_quantile_regression_known_line_and_bootstrap():
    t = np.arange(20, dtype=float)
    for q in (0.1, 0.5, 0.9):
        fit = _quantile_fit(t, 2 + 0.4 * t, q)
        np.testing.assert_allclose(fit, [2, 0.4], atol=1e-8)
    data = pd.Series(2 + 0.4 * t + np.sin(t), index=pd.date_range("1981-01-01", periods=20, freq="YS"))
    result = quantile_trends(data, Config(bootstrap_samples=19), "q", frequency=1)
    assert all(q["inference"]["status"] == "ok" for q in result["quantiles"])
    assert result["upper_tail_minus_median"]["status"] == "ok"


def test_common_trends_removed_before_correlations():
    n = 360
    rng = np.random.default_rng(19)
    a = series(values=20 + 0.1 * np.arange(n) + rng.normal(size=n), sid="a")
    b = series(values=80 - 0.1 * np.arange(n) + rng.normal(size=n), sid="b")
    result = analyze(payload(a, b, methods=["relationships"]))
    corr = result["relationships"][0]
    assert corr["status"] == "ok"
    assert abs(corr["pearson"]["coefficient"]) < 0.15


def test_controlled_regression_recovers_trend_with_supplied_driver():
    n = 360
    t = np.arange(n) / 12
    cov = 0.04 * t + np.sin(t * 2 * np.pi / 7)
    y = 10 + 0.07 * t + 3 * cov + np.random.default_rng(8).normal(0, 0.05, n)
    control = series(values=cov, sid="nao", units="1")
    control.pop("variable_id")
    doc = payload(series(values=y), methods=["drivers"])
    doc["covariates"] = [control]
    doc["controls"] = [{"series_id": "x", "covariate_ids": ["nao"]}]
    result = analyze(doc)["drivers"][0]
    assert result["status"] == "ok"
    assert result["adjusted_slope_per_decade"]["estimate"] == pytest.approx(0.7, abs=0.1)
    assert result["covariate_coefficients"]["nao"]["estimate"] == pytest.approx(3, abs=0.1)


def test_relative_change_uses_physical_mean_and_temperature_is_excluded():
    values = 2 + 0.02 * np.arange(360) / 12
    result = analyze(payload(series("precipitation_power", values=values, units="mm/day")))
    fitted = result["series"]["x"]["trend"]["sen"]
    assert fitted["percent_change_of_mean"] == pytest.approx(100 * fitted["total_change"] / np.mean(values))


def test_json_file_atomic_write_and_cli_error(tmp_path):
    source, dest = tmp_path / "input.json", tmp_path / "result.json"
    doc = payload(series(n=12), methods=[])
    source.write_text(json.dumps(doc), encoding="utf-8-sig")
    result = analyze_file(source, dest)
    assert json.loads(dest.read_text(encoding="utf-8")) == result
    with pytest.raises(ValueError, match="paths must differ"):
        analyze_file(source, source)
    original = dest.read_bytes()
    source.write_text('{"bad": NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON"):
        analyze_file(source, dest)
    assert dest.read_bytes() == original
    cli = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/analyze_climate.py"),
            "--input",
            str(source),
            "--output",
            str(dest),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert cli.returncode == 2
    assert "Analysis failed" in cli.stderr


def test_schema_definitions_are_valid():
    for name in ("climate-input.schema.json", "climate-output.schema.json"):
        Draft202012Validator.check_schema(json.loads((ROOT / "schema" / name).read_text()))


def test_no_adjacent_years_suppresses_unestimable_serial_inference():
    index = pd.date_range("1981-01-01", periods=30, freq="YS")
    values = np.arange(30, dtype=float) + np.sin(np.arange(30))
    values[1::2] = np.nan
    result = trend(pd.Series(values, index=index), Config(min_coverage=0.4))
    assert result["status"] == "ok"
    assert not result["inference_available"]
    assert result["mann_kendall"]["p_value"] is None
    assert result["sen"]["ci_per_decade"] is None


def test_user_metadata_not_counted_as_hypotheses_and_paths_are_escaped():
    result = {
        "metadata": {"p_value": 0.00001},
        "series": {"a/b~c": {"provenance": {"p_value": 0.00001}, "test": {"p_value": 0.5}}},
    }
    audit = apply_fdr(result, Config())
    assert audit["tested"] == 1
    assert audit["tests"][0]["path"] == "/series/a~1b~0c/test"
    assert "q_value" not in result["metadata"]


def test_overflowing_physical_unit_conversion_fails_clearly():
    with pytest.raises(ValueError, match="overflow"):
        parse_series(series("evapotranspiration_gldas", [1e308], n=1, units="kg/m^2/s"))


def test_blocks_larger_than_half_period_do_not_produce_degenerate_inference():
    result = analyze(
        payload(
            series(values=sample_values()),
            bootstrap_samples=19,
            block_years=30,
            methods=["acceleration", "variability", "probability", "change_point"],
        )
    )
    output = result["series"]["x"]
    assert output["acceleration"]["difference_test"]["status"] == "skipped"
    assert output["variability"]["block_test"]["status"] == "skipped"
    assert output["change_point"]["inference"]["status"] == "skipped"


def test_annual_driver_cannot_claim_a_winter_only_adjustment():
    doc = payload(series(n=30, frequency="annual", values=np.arange(30)), methods=["drivers"])
    cov = series(n=30, frequency="annual", values=np.sin(np.arange(30)), sid="driver", units="1")
    cov.pop("variable_id")
    doc["covariates"] = [cov]
    doc["controls"] = [{"series_id": "x", "covariate_ids": ["driver"], "months": [12, 1, 2]}]
    out = analyze(doc)
    assert out["drivers"][0]["reason"] == "calendar_month_filter_requires_monthly_input"


def test_monthly_precipitation_totals_keep_aggregate_units():
    values = 50 + 0.02 * np.arange(360) + np.sin(np.arange(360))
    doc = payload(
        series("PRECTOTCORR_SUM", values=values, units="mm/month"),
        methods=["trend", "seasonal", "probability", "variability", "emergence"],
    )
    out = analyze(doc)["series"]["x"]
    assert out["annual"]["units"] == "mm/year"
    assert out["seasonal"]["DJF"]["units"] == "mm/season"
    assert out["probability_change"]["threshold_units"] == "mm/year"
    assert out["variability"]["sd_units"] == "mm/year"
    assert out["emergence"]["noise_units"] == "mm/year"


def test_spei_pwm_matches_independent_lmomco_formula_fixture():
    from scipy.stats import norm
    from trend_detective.climate_stats.indices import _glo_cdf, _glo_pwm

    # Exact unbiased PWM: b0=25/8, b1=29/8, b2=575/168; lmomco parglo mapping.
    sample = np.array([-4, -2, -1, 0, 1, 3, 8, 20], dtype=float)
    params = _glo_pwm(sample)
    assert params == pytest.approx(
        {"xi": 0.2984869231271787, "alpha": 2.8157493540026324, "kappa": -0.46320346320346323}
    )
    expected = [
        -1.5068708947,
        -0.6311655068,
        -0.3235519489,
        -0.0681015202,
        0.1476078595,
        0.4920320817,
        1.0540504439,
        1.7243245045,
    ]
    np.testing.assert_allclose(norm.ppf(_glo_cdf(sample, params)), expected, atol=1e-9)
    reflected = -sample[::-1]
    np.testing.assert_allclose(
        norm.ppf(_glo_cdf(reflected, _glo_pwm(reflected))), -np.array(expected)[::-1], atol=1e-9
    )
    symmetric = _glo_pwm(np.arange(-3, 4, dtype=float))
    assert symmetric == pytest.approx({"xi": 0, "alpha": 4 / 3, "kappa": 0})
    with pytest.raises(ValueError, match="L-moments"):
        _glo_pwm(np.array([0.0] * 7 + [1.0]))
    shifted = _glo_pwm(sample + 1e9)
    assert shifted["alpha"] == pytest.approx(params["alpha"])
    assert shifted["kappa"] == pytest.approx(params["kappa"])


def test_spei_example_calibration_no_longer_collapses():
    from trend_detective.climate_stats.indices import drought_indices

    doc = json.loads((ROOT / "examples/climate/input.json").read_text())
    items = [parse_series(s) for s in doc["series"]]
    out = drought_indices(items, Config(baseline=(1981, 2010), bootstrap_samples=0))
    indices = out["sources"]["ukraine_precip"]["indices"]
    for key in ("spei3", "spei6"):
        assert indices[key]["status"] == "ok"
        assert indices[key]["calibration_method"] == "generalized_logistic_unbiased_PWM"
        for month in indices[key]["calibration"]:
            d = month["diagnostics"]
            assert abs(d["calibration_z_median"]) < 0.3
            assert 0.85 < d["calibration_z_std"] < 1.15
    assert abs(indices["spei3"]["calibration"][7]["diagnostics"]["calibration_z_median"]) < 0.1


def test_firth_separation_matches_saturated_binomial_closed_form():
    from trend_detective.climate_stats.temporal import _logistic

    t = np.repeat([-0.5, 0.5], 20)
    events = np.repeat([0.0, 1.0], 20)
    # Two saturated groups: Jeffreys-adjusted odds are .5/20.5 and 20.5/.5.
    fit = _logistic(t, events)
    np.testing.assert_allclose(fit, [0.0, 2 * np.log(41)], atol=1e-5)
    fit = _logistic(t, np.zeros(40))
    np.testing.assert_allclose(fit, [-np.log(41), 0.0], atol=1e-5)


def test_probability_sparse_events_and_threshold_refit_in_permutations(monkeypatch):
    from trend_detective.climate_stats import temporal

    annual = pd.Series(np.arange(44, dtype=float), index=pd.date_range("1981", periods=44, freq="YS"))
    cfg = Config(baseline=(1981, 2010), bootstrap_samples=19)
    original = temporal._logistic
    calls = []

    def track(t, event):
        calls.append(event.copy())
        return original(t, event)

    monkeypatch.setattr(temporal, "_logistic", track)
    out = temporal.probability_change(annual, cfg, "test")
    assert out["tails"]["low"]["logistic"]["inference"]["reason"] == "fewer_than_10_events_or_non_events"
    high = out["tails"]["high"]["logistic"]
    assert high["inference"]["status"] == "ok"
    assert high["inference"]["attempted"] == high["inference"]["successful"] == 19
    assert high["inference"]["failed"] == 0
    assert "probability_ratio_ci_percentile" not in high["inference"]
    # Both original tails then 19 high-tail draws: each recalibrates its first 30 years.
    assert len(calls) == 21
    assert all(events[:30].sum() == 3 for events in calls[2:])


def test_failed_event_permutation_does_not_condition_on_success(monkeypatch):
    from trend_detective.climate_stats import temporal

    annual = pd.Series(np.arange(44, dtype=float), index=pd.date_range("1981", periods=44, freq="YS"))
    cfg = Config(baseline=(1981, 2010), bootstrap_samples=19)
    original = temporal._logistic
    call_count = 0

    def fail_once(t, event):
        nonlocal call_count
        call_count += 1
        return None if call_count == 3 else original(t, event)

    monkeypatch.setattr(temporal, "_logistic", fail_once)
    out = temporal.probability_change(annual, cfg, "test")["tails"]["high"]["logistic"]["inference"]
    assert out["status"] == "skipped"
    assert out["failed"] == 1
    assert "p_value" not in out


def test_seasonal_control_recovers_driver_and_zero_adjusted_trend():
    n = 528
    rng = np.random.default_rng(2026)
    t = np.arange(n) / 12
    season = 15 * np.sin(2 * np.pi * np.arange(n) / 12)
    anomaly = 0.2 * t + rng.normal(size=n)
    control = series(values=season + anomaly, n=n, sid="driver", units="1")
    control.pop("variable_id")
    doc = payload(series(values=season + 2 * anomaly, n=n), methods=["drivers"])
    doc["covariates"] = [control]
    doc["controls"] = [{"series_id": "x", "covariate_ids": ["driver"]}]
    out = analyze(doc)["drivers"][0]
    assert out["covariate_coefficients"]["driver"]["estimate"] == pytest.approx(2, abs=1e-9)
    assert out["adjusted_slope_per_decade"]["estimate"] == pytest.approx(0, abs=1e-9)
    assert out["adjusted_slope_per_decade"]["test"] == "multiple_OLS_Newey_West_t_approximation"


def test_actual_calendar_coverage_and_valid_year_count_gate_inference():
    idx = pd.date_range("1980", periods=540, freq="MS")
    values = np.arange(540, dtype=float)
    values[95:-95] = np.nan
    data = pd.Series(values, index=idx)
    for out in (trend(data, Config(), frequency=12), quantile_trends(data, Config(), "gaps")):
        assert out["reason"] == "insufficient_calendar_coverage"
        assert out["coverage"] == pytest.approx(190 / 540)
    short = pd.Series(np.arange(108.0), index=idx[:108])
    assert trend(short, Config(), frequency=12)["status"] == "skipped"


def test_fixed_season_and_opt_in_partial_annual_aggregation():
    idx = pd.date_range("1981", periods=360, freq="MS")
    values = 10 * np.sin(idx.month * 2 * np.pi / 12) + (idx.year - 1981) * 0.2
    complete = pd.Series(values, index=idx)
    missing = complete.copy()
    missing.loc[(idx.year > 1990) & (idx.month == 7)] = np.nan
    cfg = Config(baseline=(1981, 1990), annual_missing_policy="climatology_adjusted")
    np.testing.assert_allclose(
        annual_aggregate(missing, cfg), annual_aggregate(complete, Config()), atol=1e-10
    )
    assert annual_aggregate(missing, Config()).count() == 10
    # Incomplete precipitation totals are never reconstructed.
    assert annual_aggregate(missing, cfg, total=True).count() == 10
    missing = complete.where(idx.month.isin([4, 5, 6, 7, 8, 9]))
    assert annual_aggregate(missing, Config(annual_months=(4, 5, 6, 7, 8, 9))).count() == 30


def test_daily_coverage_is_independent_and_catalog_status_is_preserved():
    from trend_detective.climate_stats.core import to_monthly

    values = np.ones(365)
    values[::2] = np.nan
    parsed = parse_series(series(values=values, n=365, frequency="daily"))
    assert to_monthly(parsed, Config()).count() == 0
    assert to_monthly(parsed, Config(daily_min_coverage=0.4)).count() == 12
    doc = payload(
        series("no2_tropospheric_omi", values=[-1e14] * 12, n=12, units="molecules/cm^2"), methods=[]
    )
    out = analyze(doc)["series"]["x"]
    assert "under review" in out["catalog_status"]
    assert any("under review" in s for s in out["quality"]["warnings"])
    # Valid negative retrievals are not unconditionally clipped to zero.
    assert out["descriptive"]["mean"] == -1e14


def test_fdr_agreement_does_not_traverse_user_metadata():
    doc = payload(series(values=sample_values()))
    doc["metadata"] = {
        "mann_kendall": "description",
        "ols": "description",
        "nested": {"mann_kendall": {"p_value": 0.001}, "ols": {"p_value": 0.001}},
    }
    out = analyze(doc)
    assert out["metadata"] == doc["metadata"]
    assert out["series"]["x"]["trend"]["conservative_significant_fdr"]
    assert all(not t["path"].startswith("/metadata") for t in out["insights_audit"]["tests"])


def test_djf_month_order_does_not_change_year_assignment():
    data = pd.Series(np.arange(360.0), index=pd.date_range("1981", periods=360, freq="MS"))
    pd.testing.assert_series_equal(
        annual_aggregate(data, Config(annual_months=(12, 1, 2))),
        annual_aggregate(data, Config(annual_months=(1, 2, 12))),
    )


def test_driver_common_window_and_single_month_hac():
    rng = np.random.default_rng(9)
    cov = rng.normal(size=300)
    values = np.r_[rng.normal(size=228), 2 * cov + rng.normal(scale=0.1, size=300)]
    driver = series(values=cov, n=300, start="2000-01-01", sid="driver", units="1")
    driver.pop("variable_id")
    doc = payload(series(values=values, n=528), methods=["drivers"])
    doc["covariates"] = [driver]
    doc["controls"] = [{"series_id": "x", "covariate_ids": ["driver"]}]
    out = analyze(doc)["drivers"][0]
    assert out["status"] == "ok" and out["n"] == 300
    doc["controls"][0]["months"] = [1]
    out = analyze(doc)["drivers"][0]
    assert out["status"] == "ok" and out["n"] == 25
    assert out["hac_lag_unit"] == "year" and out["hac_calendar_lags"] == 3
    assert out["covariate_coefficients"]["driver"]["estimate"] == pytest.approx(2, abs=0.15)
