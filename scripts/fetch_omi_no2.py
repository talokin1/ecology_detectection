r"""Fetch a regional monthly tropospheric NO2 series from OMI/Aura OMNO2d and cache it (offline precompute).

One Earthdata OPeNDAP request per daily granule (~8,000 since 2004-10; ~40-60 min for a city box).
Needs EARTHDATA_TOKEN in the environment or in .env (see .env.example). The token is never
printed or written to the cache. Idempotent: cached series are reused unless --refresh is given;
an interrupted run resumes where it stopped. Changing --min-valid-days or
--min-valid-area-fraction reuses the cached daily means (no new download).

Writes ``<CACHE_DIR>/earthdata/omno2d_<hash>.csv`` (month,value,n_days) plus a
``.provenance.json`` sidecar, and the daily box means in ``omno2d_daily_<hash>.csv``.
The box must contain at least one 0.25° cell centre (cells are centred at .125, .375, ...).

Examples (PowerShell or bash):
    python scripts/fetch_omi_no2.py --name Kyiv --bbox 30.2 50.2 30.9 50.7
    python scripts/fetch_omi_no2.py --name Kyiv --bbox 30.2 50.2 30.9 50.7 --min-valid-days 8

SI-assisted (Claude, Anthropic); reviewed by the team (see docs/08-si-usage-log.md).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from trend_detective import omi_no2  # noqa: E402
from trend_detective.power_zarr import Region  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--name", default="region", help="label for the region (stored in provenance)")
    p.add_argument(
        "--bbox", nargs=4, type=float, required=True,
        metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX"), help="west south east north, degrees",
    )
    p.add_argument("--version", default=omi_no2.VERSION, choices=sorted(omi_no2.DOIS))
    p.add_argument("--refresh", action="store_true", help="download again even if cached")
    p.add_argument("--min-valid-area-fraction", type=float, default=omi_no2.MIN_VALID_AREA_FRACTION,
                   help="share of the box area that must be valid for a day to count")
    p.add_argument("--min-valid-days", type=int, default=omi_no2.MIN_VALID_DAYS,
                   help="valid days needed for a month to count")
    p.add_argument("--workers", type=int, default=4, help="parallel OPeNDAP requests")
    args = p.parse_args(argv)

    lon_min, lat_min, lon_max, lat_max = args.bbox
    region = Region(args.name, lat_min, lat_max, lon_min, lon_max)
    t0 = time.time()
    s = omi_no2.region_series(region, version=args.version,
                              min_valid_area_fraction=args.min_valid_area_fraction,
                              min_valid_days=args.min_valid_days, refresh=args.refresh,
                              workers=args.workers, progress=True)

    prov = s.attrs["provenance"]
    state = "from cache" if s.attrs.get("from_cache") else f"done in {time.time() - t0:.0f} s"
    n_cells = prov["cell_centres"]["n_cells"]
    print(f"{prov['short_name']} {prov['version']} over {args.name} ({n_cells} cells): "
          f"{len(s)} of {prov['n_months_total']} months kept, {prov['time_range']['start']} to "
          f"{prov['time_range']['end']} [{s.attrs['units']}] ({state})")
    if len(s):
        print(f"  monthly values {s.min() / 1e15:.2f} to {s.max() / 1e15:.2f} x 1e15 molecules/cm^2; "
              f"median days per kept month {int(_median(s.attrs['n_days']))}")
    for caveat in prov.get("caveats", []):
        print(f"  note: {caveat}")
    return 0


def _median(values: list[int]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


if __name__ == "__main__":
    raise SystemExit(main())
