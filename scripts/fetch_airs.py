r"""Download AIRS3STM v7.0 monthly subsets and build the 2° map grids (backend/trend_detective/airs.py).

Needs an Earthdata token in .env (EARTHDATA_TOKEN). Resumable: months already in
data/cache/raw/airs/months/ are skipped. After building, refresh MANIFEST and upload the grids:
    python scripts/build_data.py --manifest-only
    python scripts/sync_cache.py push

Usage (PowerShell or bash, from the repo root):
    python scripts/fetch_airs.py                    # download + build both grids at 2 deg
    python scripts/fetch_airs.py --end 2025-12      # stop at a month
    python scripts/fetch_airs.py --build-only

SI-assisted (Claude, Anthropic); pending team review (see docs/08-si-usage-log.md).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from trend_detective import airs, grids  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--end", help="last month to download, YYYY-MM")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--resolution", type=float, default=2.0)
    ap.add_argument("--build-only", action="store_true")
    args = ap.parse_args()
    if not args.build_only:
        paths = airs.download(workers=args.workers, end=args.end)
        print(f"AIRS month files: {len(paths)}")
    for field in airs.FIELDS:
        path = airs.build_grid(field, args.resolution)
        print(grids.grid_summary(path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
