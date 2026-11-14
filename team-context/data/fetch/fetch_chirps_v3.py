#!/usr/bin/env python3
"""Download official CHIRPS v3 monthly global NetCDF. No login."""
from __future__ import annotations
import time, ssl, urllib.request
from pathlib import Path

from locate import GLOBAL_DATA, LOG_DIR

URL = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/netcdf/chirps-v3.0.monthly.nc"
DEST = GLOBAL_DATA / "chirps_v3" / "chirps-v3.0.monthly.nc"
EXPECTED = 8960342547
UA = "SpaceAppsTrendDetective/1.0"
CTX = ssl.create_default_context()
LOG = LOG_DIR / "chirps_fetch.log"

def log(m):
    line = time.strftime("%H:%M:%S ") + m
    print(line, flush=True)
    with LOG.open("a") as f:
        f.write(line + "\n")

def main():
    DEST.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("")
    if DEST.exists() and DEST.stat().st_size == EXPECTED:
        log(f"already complete {DEST.stat().st_size}")
        return 0
    tmp = DEST.with_suffix(DEST.suffix + ".part")
    # resume if part exists
    existing = tmp.stat().st_size if tmp.exists() else 0
    headers = {"User-Agent": UA}
    if existing:
        headers["Range"] = f"bytes={existing}-"
        log(f"resuming from {existing}")
    t0 = time.time()
    req = urllib.request.Request(URL, headers=headers)
    with urllib.request.urlopen(req, timeout=300, context=CTX) as r, open(tmp, "ab" if existing else "wb") as f:
        log(f"HTTP {r.status} content-length={r.headers.get('Content-Length')} accept-ranges={r.headers.get('Accept-Ranges')}")
        n = existing
        last_log = t0
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            n += len(chunk)
            if time.time() - last_log >= 15:
                log(f"  {n:,} / {EXPECTED:,} ({100*n/EXPECTED:.1f}%) {n/(time.time()-t0)/1e6:.1f} MB/s")
                last_log = time.time()
    sz = tmp.stat().st_size
    log(f"finished raw size={sz} expected={EXPECTED} elapsed={time.time()-t0:.1f}s")
    if sz != EXPECTED:
        log("ERROR size mismatch; leaving .part in place")
        return 1
    tmp.replace(DEST)
    log(f"ok {DEST}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
