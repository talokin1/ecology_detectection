"""Cross-check of the web app's country method: Ukraine from the 2-degree map grid (area-weighted
squares) against its native-resolution cached series, same period. Prints Sen's slope per decade,
its 95% range, the Mann-Kendall p-value and the correlation of the two monthly anomaly series.
Results are quoted in docs/10-methods.md ("Countries"). Reads the frozen cache only.

Usage (repo root):  python scripts/crosscheck_country_grid.py

SI-assisted (Claude, Anthropic).
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_app_data as m  # noqa: E402

m.COUNTRY_SKIP = m.COUNTRY_SKIP - {"UKR"}
ts = m.ts
for var in ("t2m", "precip", "soil", "sunlight"):
    spec = m.VARIABLES[var]
    grid = m.Grid(var)
    m.Y0 = spec["start"]
    m.Y1 = m.last_complete_year(grid.time[np.isfinite(grid.values).any(axis=(1, 2))])
    countries = m.country_regions(grid.lat, grid.lon)
    ukr = countries["c_ukr"]
    g = m.series_from_grid(grid, ukr)
    n, _ = m.series_from_cache(var, "ukraine_border")
    dates = m.month_index(m.Y0, m.Y1).values.astype("datetime64[M]").astype("datetime64[D]")
    parts = []
    for label, raw in (("2-degree squares", g), ("native", n)):
        r = ts.analyze_series(dates, raw)
        lo, hi = r["sen_ci95_per_decade"]
        parts.append(f"{label}: Sen {r['sen_slope_per_decade']:+.4f} [{lo:+.4f}, {hi:+.4f}] "
                     f"p {r['mk']['p']:.3g} mean {float(np.mean(raw)):.3f}")
    # correlation of the anomalies: the shared seasonal cycle would otherwise dominate
    corr = float(np.corrcoef(ts.deseasonalize(dates, g)[0], ts.deseasonalize(dates, n)[0])[0, 1])
    print(f"{var} ({m.Y0}-{m.Y1}) | " + " | ".join(parts)
          + f" | anomaly r {corr:.4f} | squares {len(ukr['weights'][2])}")
