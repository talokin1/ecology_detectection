r"""Fetch a regional monthly series from the public NASA POWER Zarr archive and cache it.

Idempotent: a series already in the cache is not downloaded again unless --refresh is given.
Writes ``<CACHE_DIR>/power_zarr/<source>_<variable>_<hash>.csv`` plus a
``.provenance.json`` sidecar. No login needed.

Examples (PowerShell or bash):
    python scripts/fetch_power_region.py --variable T2M --name Ukraine --bbox 22 44 40.5 52.5
    python scripts/fetch_power_region.py --source imerg --variable IMERG_PRECTOT --name Sahel \
        --bbox -15 10 35 18
    python scripts/fetch_power_region.py --list --source syn1deg

SI-assisted (Claude, Anthropic); reviewed by the team (see docs/08-si-usage-log.md).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from trend_detective import power_zarr  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--source", default="merra2", choices=sorted(power_zarr.SOURCES))
    p.add_argument("--variable", help="POWER parameter name, e.g. T2M")
    p.add_argument("--name", default="region", help="label for the region (stored in provenance)")
    p.add_argument(
        "--bbox", nargs=4, type=float, metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX"),
        help="west south east north, degrees; LON_MIN > LON_MAX crosses the antimeridian",
    )
    p.add_argument("--refresh", action="store_true", help="download again even if cached")
    p.add_argument("--list", action="store_true", help="list variables of --source and exit")
    args = p.parse_args(argv)

    if args.list:
        for name in power_zarr.list_variables(args.source):
            info = power_zarr.variable_info(name, args.source)
            print(f"{name:24} {info['long_name']} [{info['units']}]")
        return 0
    if not args.variable or not args.bbox:
        p.error("--variable and --bbox are required unless --list is given")

    lon_min, lat_min, lon_max, lat_max = args.bbox
    region = power_zarr.Region(args.name, lat_min, lat_max, lon_min, lon_max)
    s = power_zarr.region_series(args.variable, region, args.source, refresh=args.refresh)
    prov = s.attrs.get("provenance", {})
    state = "from cache" if s.attrs.get("from_cache") else "downloaded"
    print(
        f"{args.variable} over {args.name}: {len(s)} months "
        f"{s.index[0]:%Y-%m} to {s.index[-1]:%Y-%m} [{s.attrs.get('units', '')}] ({state}; "
        f"accessed {prov.get('accessed', 'unknown')})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
