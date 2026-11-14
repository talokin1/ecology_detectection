"""Create reproducible synthetic input for analyze_climate.py, optionally with daily data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def make_payload(*, daily: bool = False, bootstrap_samples: int = 999) -> dict:
    rng = np.random.default_rng(42)
    index = pd.date_range("1981-01-01", "2024-12-31" if daily else "2024-12-01", freq="D" if daily else "MS")
    t = (index - index[0]).days.to_numpy() / 365.2425
    phase = (index.dayofyear.to_numpy() - 110) * 2 * np.pi / 365.2425
    mean = 10 + 12 * np.sin(phase) + 0.045 * t + rng.normal(0, 2 if daily else 0.8, len(index))
    maximum = mean + rng.uniform(3.5, 6, len(index))
    minimum = mean - rng.uniform(3.5, 6, len(index))
    rain = rng.gamma(1.2 if daily else 4.0, 2.0 if daily else 0.55, len(index))
    rain *= np.clip(1.1 + 0.25 * np.sin(phase) - 0.004 * t, 0.1, None)
    if daily:
        rain[rng.random(len(index)) < 0.45] = 0
    series = []
    frequency = "daily" if daily else "monthly"
    for sid, vid, units, values in (
        ("ukraine_t2m", "air_temperature_power", "degC", mean),
        ("ukraine_tmax", "T2M_MAX", "degC", maximum),
        ("ukraine_tmin", "T2M_MIN", "degC", minimum),
        ("ukraine_precip", "precipitation_power", "mm/day", rain),
    ):
        item = {
            "id": sid,
            "variable_id": vid,
            "region_id": "ukraine",
            "latitude": 49.0,
            "units": units,
            "frequency": frequency,
            "provenance": {"synthetic": True, "generator_seed": 42},
            "values": [
                {"date": d.strftime("%Y-%m-%d" if daily else "%Y-%m"), "value": round(float(v), 6)}
                for d, v in zip(index, values)
            ],
        }
        if not daily and vid in ("T2M_MAX", "T2M_MIN"):
            item["semantics"] = "mean_daily_maximum" if vid == "T2M_MAX" else "mean_daily_minimum"
        series.append(item)
    monthly_rain = pd.Series(rain, index=index).resample("MS").mean()
    soil = np.clip(
        0.55
        + 0.03 * monthly_rain.to_numpy()
        - 0.0015 * np.arange(len(monthly_rain)) / 12
        + rng.normal(0, 0.025, len(monthly_rain)),
        0,
        1,
    )
    series.append(
        {
            "id": "ukraine_soil",
            "variable_id": "root_zone_soil_wetness_power",
            "region_id": "ukraine",
            "latitude": 49.0,
            "units": "1",
            "frequency": "monthly",
            "provenance": {"synthetic": True, "generator_seed": 42},
            "values": [
                {"date": d.strftime("%Y-%m"), "value": round(float(v), 6)}
                for d, v in zip(monthly_rain.index, soil)
            ],
        }
    )
    return {
        "schema_version": "1.0",
        "metadata": {"synthetic": True, "purpose": "Pipeline demonstration only"},
        "config": {
            "baseline": [1981, 2010],
            "bootstrap_samples": bootstrap_samples,
            "seed": 1729,
            "include_series": True,
        },
        "series": series,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("examples/climate/input.json"))
    parser.add_argument("--daily", action="store_true")
    parser.add_argument(
        "--bootstrap-samples",
        type=int,
        default=999,
        help="999 by default; 39 is available for a quick smoke check with coarse p-values",
    )
    args = parser.parse_args()
    payload = make_payload(daily=args.daily, bootstrap_samples=args.bootstrap_samples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote synthetic input: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
