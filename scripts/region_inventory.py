r"""List every catalog variable for a region: can we deliver it, and is it fit for a trend analysis?

Answers challenge objectives 1 and 2 for one region (R-01, R-02). Runs no trend tests.
POWER variables are read live (and cached); Earthdata variables come from the cache unless
--fetch is given (needs EARTHDATA_TOKEN; see scripts/fetch_earthdata_region.py).

Examples (PowerShell or bash):
    python scripts/region_inventory.py --region ukraine
    python scripts/region_inventory.py --bbox 72 26 78 32 --name "NW India"
    python scripts/region_inventory.py --list-regions

SI-assisted (Claude, Anthropic); pending team review (see docs/08-si-usage-log.md).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import pandas as pd
from trend_detective import acquire


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--region", help="preset id from data/catalog/regions.yaml")
    g.add_argument("--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    g.add_argument("--list-regions", action="store_true")
    p.add_argument("--name", default="custom box", help="label for --bbox")
    p.add_argument("--fetch", action="store_true", help="also fetch Earthdata variables (token needed)")
    args = p.parse_args(argv)

    if args.list_regions:
        for rid, e in acquire.list_regions().items():
            print(f"{rid:14} {e['name']:45} bbox={e['bbox']}")
        return 0
    region = args.region or acquire.resolve_region(args.bbox, args.name)
    df = acquire.inventory(region, allow_login_fetch=args.fetch)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 80)
    df = df.drop(columns=["available"])
    if "n_months" in df:
        df["n_months"] = df["n_months"].astype("Int64")
    print(df.astype(object).where(df.notna(), "").to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
