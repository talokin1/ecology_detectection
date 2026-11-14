#!/usr/bin/env python3
"""Preprocessing pipeline v1.4 (analysis-ready tidy tables).

    cd team-context/data/pipeline
    export OMP_NUM_THREADS=2 UKRAINE_SAMPLES=... GLOBAL_DATA=...
    nice -n 10 python run_pipeline.py --region ukraine_bbox ukraine_mask ukraine_mask_no_crimea
    python smoke_test.py            # blocking check (needs ukraine_bbox run)

Outputs per region in data/tidy/<region>/ ; QC report in qc_report.md (all regions run so far).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(k, "2")

PIPE = Path(__file__).resolve().parent
sys.path.insert(0, str(PIPE))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ukpipe.core import GLOBAL, SAMPLES, annual_table  # noqa: E402
from ukpipe.loaders import dispatch as D, gridded as G, tables as T  # noqa: E402
from ukpipe.qc import qc_table  # noqa: E402
from ukpipe.regions import load_region  # noqa: E402

LOADERS = {
    "nasa_power": G.load_power, "grace": G.load_grace, "hadcrut5": G.load_hadcrut5, "gistemp": G.load_gistemp,
    "berkeley": G.load_berkeley, "chirps": D.load_chirps, "cci_sm": G.load_cci_sm,
    "merra2": D.load_merra2, "gldas20": D.load_gldas20, "gldas21": D.load_gldas21, "gpm_imerg": D.load_imerg,
    "airs": D.load_airs, "modis": D.load_modis, "omi": T.load_omi, "gpcc": D.load_gpcc,
    "cru_cy": T.load_cru_cy, "berkeley_country": T.load_berkeley_country,
    "ghcn": T.load_ghcn, "gsom": T.load_gsom, "swot": T.load_swot,
}


def run(region_name: str, sources: list[str], do_trends: bool = True):
    t0 = time.time()
    region = load_region(region_name)
    outdir = PIPE / "data" / "tidy" / region_name
    outdir.mkdir(parents=True, exist_ok=True)
    frames, notes = [], {}
    for src in sources:
        ts = time.time()
        try:
            dfs, nt = LOADERS[src](region)
        except Exception as e:  # keep going; report failure
            dfs, nt = [], {"source": src, "status": "FAILED", "error": f"{type(e).__name__}: {e}"}
        st = nt.pop("station_table", None)
        if st is not None and len(st):
            st.to_parquet(outdir / f"stations_{src}.parquet", index=False)
        nt.pop("time_center", None)
        if dfs:
            df = pd.concat(dfs, ignore_index=True)
            for s_name, d in df.groupby("source"):
                d.to_parquet(outdir / f"{s_name}.parquet", index=False)
            frames.append(df)
        nt["seconds"] = round(time.time() - ts, 1)
        notes[src] = nt
        print(f"[{region_name}] {src:17s} {nt.get('status'):8s} {len(dfs):3d} series  {nt['seconds']}s", flush=True)
    tidy = pd.concat(frames, ignore_index=True)
    tidy.to_parquet(outdir / "all_monthly_long.parquet", index=False)
    wide = tidy.assign(key=tidy.source + ":" + tidy.variable).pivot_table(index="date", columns="key", values="value")
    wide.to_parquet(outdir / "monthly_wide.parquet"); wide.to_csv(outdir / "monthly_wide.csv")
    ann = annual_table(tidy)
    ann.to_parquet(outdir / "annual_seasonal.parquet", index=False); ann.to_csv(outdir / "annual_seasonal.csv", index=False)
    qc = qc_table(tidy)
    qc.to_csv(outdir / "qc_variables.csv", index=False)
    if do_trends:
        from ukpipe.trends import trend_table
        tr = trend_table(tidy, ann)
        tr.to_csv(outdir / "trends.csv", index=False)
    meta = dict(region=region_name, region_cfg=region.cfg if region.is_bbox else {k: v for k, v in region.cfg.items()},
                bounds=region.bounds, sources=notes, n_series=int(tidy.groupby(["source", "variable"]).ngroups),
                seconds=round(time.time() - t0, 1))
    raw = json.dumps(meta, indent=1, default=str)
    raw = raw.replace(str(GLOBAL), "$GLOBAL_DATA").replace(str(SAMPLES), "$UKRAINE_SAMPLES")
    (outdir / "run_meta.json").write_text(raw)
    print(f"[{region_name}] done in {meta['seconds']}s -> {outdir}")
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", nargs="+", default=["ukraine_bbox"])
    ap.add_argument("--sources", nargs="+", default=list(LOADERS))
    ap.add_argument("--no-trends", action="store_true")
    a = ap.parse_args()
    for r in a.region:
        run(r, a.sources, not a.no_trends)
    from ukpipe.report import write_report
    write_report()


if __name__ == "__main__":
    main()
