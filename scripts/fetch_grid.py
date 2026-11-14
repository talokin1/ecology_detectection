r"""Build a global monthly grid of one NASA POWER variable for the world trend map and cache it.

Idempotent: a grid already in the cache is not rebuilt unless --refresh is given.
Writes ``<CACHE_DIR>/grids/<source>_<variable>_<res>deg[_land].nc`` plus a ``.provenance.json``
sidecar. Reads the whole globe once (MERRA-2: about 140 MB compressed, about a minute). No login needed.

Examples (PowerShell or bash):
    python scripts/fetch_grid.py --variable T2M --source merra2 --resolution 1.0
    python scripts/fetch_grid.py --variable PRECTOTCORR --resolution 2.0 --land-only
    python scripts/fetch_grid.py --variable T2M --resolution 1.0 --method overlap --refresh

SI-assisted (Claude, Anthropic); pending team review (see docs/08-si-usage-log.md).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from trend_detective import grids, power_zarr


def main(argv: list[str] | None = None) -> int:
    monthly = sorted(k for k, v in power_zarr.SOURCES.items() if v.get("freq", "M") == "M")
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--variable", required=True, help="POWER parameter name, e.g. T2M")
    p.add_argument("--source", default="merra2", choices=monthly)
    p.add_argument("--resolution", type=float, default=1.0, help="cell size in degrees; must divide 180")
    p.add_argument(
        "--method",
        default="overlap",
        choices=grids.METHODS,
        help="centre: native cells assigned by centre; overlap: split by footprint overlap",
    )
    p.add_argument("--land-only", action="store_true", help="keep MERRA-2 land cells only")
    p.add_argument("--refresh", action="store_true", help="rebuild even if cached")
    args = p.parse_args(argv)

    t0 = time.perf_counter()
    ds = grids.build_grid(
        args.variable,
        args.source,
        args.resolution,
        land_only=args.land_only,
        method=args.method,
        refresh=args.refresh,
    )
    elapsed = time.perf_counter() - t0
    path = grids.grid_path(
        grids.default_cache_dir(), args.variable, args.source, args.resolution, args.land_only, args.method
    )
    summary = grids.grid_summary(path)
    state = "from cache" if ds.attrs.get("from_cache") else "built"
    print(f"{args.variable} {args.resolution:g} deg grid ({state} in {elapsed:.1f} s)")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
