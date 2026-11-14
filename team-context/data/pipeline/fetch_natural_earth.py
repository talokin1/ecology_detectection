#!/usr/bin/env python3
"""Download Natural Earth 10m admin-0 shapefiles used by the Ukraine masks.

The zips are not committed (over the archive's preference to keep geometries
rebuildable). Expected SHA-256 values are the files used for the published
mask areas (ukraine_mask 597,211 km2 with Crimea; ukraine_mask_no_crimea
570,178 km2).
"""
from __future__ import annotations

import hashlib
import urllib.request
import zipfile
from pathlib import Path

PIPE = Path(__file__).resolve().parent
DEST = PIPE / "data" / "raw_aux" / "natural_earth"
BASE = "https://naciscdn.org/naturalearth/10m/cultural/"
FILES = {
    "ne_10m_admin_0_countries.zip": "ce1ac7036499a0edd641fbc093cd209a98f96a49d2eca8480aaacad35138a7f6",
    "ne_10m_admin_0_countries_ukr.zip": "6fcdaed26c8d551018fbd3b97185df863a4f15f489e602fceae1dee90d6a5ae8",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    for name, expect in FILES.items():
        dest = DEST / name
        if not dest.exists() or sha256(dest) != expect:
            url = BASE + name
            print("GET", url, flush=True)
            urllib.request.urlretrieve(url, dest)
        got = sha256(dest)
        if got != expect:
            raise SystemExit(f"{name} sha256 {got} != {expect}")
        with zipfile.ZipFile(dest) as zf:
            zf.extractall(DEST / name.replace(".zip", ""))
        print("ok", name)
    print("shapefiles in", DEST)


if __name__ == "__main__":
    main()
