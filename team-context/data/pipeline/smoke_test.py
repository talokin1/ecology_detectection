#!/usr/bin/env python3
"""Blocking smoke test: region=ukraine_bbox must reproduce approved numbers within ±0.005.

  POWER T2M annual (12/12) 1981-2025 OLS slope      +0.553 °C/decade  (trend_summary.csv: 0.55271)
  GRACE monthly deseasonalised, production overlap weights  -11.242 cm/decade (14 Nov 2026, team lead via Thinker)
    [legacy, non-blocking: original cell-centre selection -11.222 (grace_trend_rows.csv: -11.22209)]
  HadCRUT5 15-cell overlap annual 1981-2025 OLS     +0.579 °C/decade  (Critique extra_sources_review)
Reference values are as stated in the plan; exact upstream values are also reported.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
PIPE = Path(__file__).resolve().parent
sys.path.insert(0, str(PIPE))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from ukpipe.paths import load_module, trend_methods_py  # noqa: E402

trend_stats = load_module(trend_methods_py(), "trend_methods_smoke").trend_stats  # noqa: E402

TOL = 0.005
D = PIPE / "data" / "tidy" / "ukraine_bbox"


def main():
    ann = pd.read_parquet(D / "annual_seasonal.parquet")
    res = []

    def annual_slope(src, var):
        a = ann[(ann.source == src) & (ann.variable == var) & (ann.period == "ANN") & ann.year.between(1981, 2025)]
        return trend_stats(a.year.to_numpy(float), a.value.to_numpy(float))["lin_slope_per_decade"], len(a)

    s, n = annual_slope("nasa_power", "T2M")
    res.append(dict(check="POWER T2M annual 1981-2025 OLS (°C/decade)", reference=0.553, upstream_exact=0.5527065, reproduced=s, n=n))
    s, n = annual_slope("hadcrut5", "tas_anomaly")
    res.append(dict(check="HadCRUT5 overlap annual 1981-2025 OLS (°C/decade)", reference=0.579, upstream_exact=None, reproduced=s, n=n))

    # GRACE headline method: SAME code path as the GRACE headline row in trends.csv (ukpipe/grace_method.py)
    from ukpipe.grace_method import grace_headline_trend as grace_slope

    # GRACE (decided by the team lead via Thinker, 14 Nov 2026): fractional-overlap weights are the PRODUCTION method.
    # (a) BLOCKING: production tidy series (overlap weights incl. 44.0-44.5N row, 40.0-40.5E column) vs -11.242
    tr = grace_slope(pd.read_parquet(D / "grace.parquet"))
    res.append(dict(check="GRACE production tidy series, overlap weights (cm/decade)",
                    reference=-11.242, upstream_exact=-11.24197, reproduced=tr["lin_slope_per_decade"], n=tr["n"]))
    for r in res:
        r["blocking"] = True
    # (b) NON-blocking LEGACY check: same loader with the original cell-centre selection vs the old -11.222
    from ukpipe.loaders.gridded import load_grace
    from ukpipe.regions import load_region
    tr = grace_slope(load_grace(load_region("ukraine_bbox"), weights="centre")[0][0])
    res.append(dict(check="GRACE legacy cell-centre selection (cm/decade) [legacy, non-blocking]", reference=-11.222,
                    upstream_exact=-11.222087, reproduced=tr["lin_slope_per_decade"], n=tr["n"], blocking=False))
    for r in res:
        r["diff"] = r["reproduced"] - r["reference"]
        r["pass"] = bool(abs(r["diff"]) <= TOL)
    ok = all(r["pass"] for r in res if r["blocking"])
    out = dict(tolerance=TOL, all_pass=ok, results=res, run_at=dt.datetime.now().isoformat(timespec="seconds"))
    (PIPE / "data" / "smoke_test_results.json").write_text(json.dumps(out, indent=1))
    for r in res:
        print(f"{'PASS' if r['pass'] else 'FAIL'}{'' if r['blocking'] else ' (non-blocking)'}  {r['check']}: ref {r['reference']:+.3f}  got {r['reproduced']:+.4f}  diff {r['diff']:+.4f}  n={r['n']}")
    from ukpipe.report import write_report
    write_report()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
