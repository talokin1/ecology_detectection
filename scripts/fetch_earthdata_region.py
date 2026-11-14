r"""Fetch a regional monthly series from an Earthdata Login dataset and cache it (offline precompute).

Datasets:
    ndvi   MODIS Terra MOD13C2 v061 vegetation greenness (LP DAAC, OPeNDAP subset per month)
    grace  JPL GRACE/GRACE-FO mascon RL06.3Mv04 CRI total water storage (PO.DAAC, one file)

Needs EARTHDATA_TOKEN in the environment or in .env (see .env.example). The token is never
printed or written to the cache. Idempotent: cached series are reused unless --refresh is given;
an interrupted NDVI run resumes where it stopped.

Writes ``<CACHE_DIR>/earthdata/<dataset>_<hash>.csv`` plus a ``.provenance.json`` sidecar.

Examples (PowerShell or bash):
    python scripts/fetch_earthdata_region.py --dataset grace --name "NW India" --bbox 72 26 78 32
    python scripts/fetch_earthdata_region.py --dataset ndvi --name Ukraine --bbox 22 44 40.5 52.5

SI-assisted (Claude, Anthropic); reviewed by the team (see docs/08-si-usage-log.md).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from trend_detective import grace, modis_ndvi  # noqa: E402
from trend_detective.power_zarr import Region  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--dataset", required=True, choices=["ndvi", "grace"])
    p.add_argument("--name", default="region", help="label for the region (stored in provenance)")
    p.add_argument(
        "--bbox", nargs=4, type=float, required=True,
        metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX"), help="west south east north, degrees",
    )
    p.add_argument("--refresh", action="store_true", help="download again even if cached")
    p.add_argument("--min-valid-fraction", type=float, default=modis_ndvi.MIN_VALID_FRACTION,
                   help="ndvi: share of land area that must pass quality checks for a month to count")
    p.add_argument("--workers", type=int, default=4, help="ndvi: parallel OPeNDAP requests")
    p.add_argument("--scale-factor", action="store_true",
                   help="grace: apply JPL's CLM gain factors (for regions smaller than ~3°)")
    args = p.parse_args(argv)

    lon_min, lat_min, lon_max, lat_max = args.bbox
    region = Region(args.name, lat_min, lat_max, lon_min, lon_max)
    t0 = time.time()
    if args.dataset == "ndvi":
        s = modis_ndvi.region_series(region, min_valid_fraction=args.min_valid_fraction,
                                     refresh=args.refresh, workers=args.workers, progress=True)
    else:
        s = grace.region_series(region, apply_scale_factor=args.scale_factor, refresh=args.refresh)

    prov = s.attrs["provenance"]
    state = "from cache" if s.attrs.get("from_cache") else f"fetched in {time.time() - t0:.0f} s"
    print(f"{prov['short_name']} {prov['version']} over {args.name}: {len(s)} months "
          f"{prov['time_range']['start']} to {prov['time_range']['end']} [{s.attrs['units']}] ({state})")
    dropped = prov.get("months_dropped_low_coverage") or prov.get("missing_months") or []
    if dropped:
        print(f"  months without a value: {len(dropped)}")
    for caveat in prov.get("caveats", []):
        print(f"  note: {caveat}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
