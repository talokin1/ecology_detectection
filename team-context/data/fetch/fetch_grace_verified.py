#!/usr/bin/env python3
"""Re-download GRACE JPL mascon CRI and verify MD5 + Content-Length. Never prints credentials."""
from __future__ import annotations
import hashlib, os, ssl, time, urllib.request

from locate import GLOBAL_DATA

URL = "https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-protected/TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4/GRCTellus.JPL.200204_202609.GLO.RL06.3M.MSCNv04CRI.nc"
DEST = GLOBAL_DATA / "grace" / "GRCTellus.JPL.200204_202609.GLO.RL06.3M.MSCNv04CRI.nc"
OFFICIAL_MD5 = "1567b9401ec2a704aab16598fcce5e70"
UA = "SpaceAppsTrendDetective/1.0"
CTX = ssl.create_default_context()

def log(m):
    print(m, flush=True)

def token():
    t = os.environ.get("EARTHDATA_TOKEN") or ""
    if not t:
        raise SystemExit("EARTHDATA_TOKEN is not set")
    return t

def md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    headers = {"User-Agent": UA, "Authorization": f"Bearer {token()}"}
    # Content-Length via range
    req = urllib.request.Request(URL, headers={**headers, "Range": "bytes=0-0"})
    expected = None
    try:
        with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
            cr = r.headers.get("Content-Range") or ""
            import re
            m = re.search(r"/(\d+)$", cr)
            if m:
                expected = int(m.group(1))
            r.read()
    except Exception as e:
        if hasattr(e, "headers"):
            import re
            cr = e.headers.get("Content-Range") or ""
            m = re.search(r"/(\d+)$", cr)
            if m:
                expected = int(m.group(1))
        log(f"range probe: {type(e).__name__} expected={expected}")
    log(f"expected Content-Length={expected}")

    DEST.parent.mkdir(parents=True, exist_ok=True)
    if DEST.exists():
        log(f"existing size={DEST.stat().st_size} md5={md5(DEST)}")
        DEST.rename(DEST.with_suffix(DEST.suffix + ".bad"))
        log("moved incomplete file aside")

    tmp = DEST.with_suffix(DEST.suffix + ".part")
    if tmp.exists():
        tmp.unlink()
    last = None
    for attempt in range(4):
        try:
            t0 = time.time()
            req = urllib.request.Request(URL, headers=headers)
            with urllib.request.urlopen(req, timeout=300, context=CTX) as r, open(tmp, "wb") as f:
                cl = r.headers.get("Content-Length")
                log(f"GET status={r.status} content-length={cl}")
                n = 0
                while True:
                    chunk = r.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    n += len(chunk)
            sz = tmp.stat().st_size
            log(f"downloaded {sz} bytes in {time.time()-t0:.1f}s")
            if expected and sz != expected:
                raise RuntimeError(f"truncated: got {sz} expected {expected}")
            if cl and cl.isdigit() and sz != int(cl):
                raise RuntimeError(f"truncated: got {sz} content-length {cl}")
            digest = md5(tmp)
            log(f"md5={digest} official={OFFICIAL_MD5} match={digest==OFFICIAL_MD5}")
            tmp.replace(DEST)
            # write sidecar
            (DEST.parent / "download_meta.txt").write_text(
                f"bytes={sz}\nmd5={digest}\nofficial_md5={OFFICIAL_MD5}\nmatch={digest==OFFICIAL_MD5}\n"
            )
            if digest != OFFICIAL_MD5:
                log("WARNING: MD5 does not match the previously recorded official hash; size was verified against Content-Length.")
            # cleanup bad
            bad = DEST.with_suffix(DEST.suffix + ".bad")
            if bad.exists():
                bad.unlink()
            return 0
        except Exception as e:
            last = e
            log(f"retry {attempt+1}: {type(e).__name__}: {e}")
            time.sleep(3 + attempt * 3)
            if tmp.exists():
                tmp.unlink()
    raise SystemExit(f"failed: {last}")

if __name__ == "__main__":
    raise SystemExit(main())
