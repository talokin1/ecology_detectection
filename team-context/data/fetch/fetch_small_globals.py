#!/usr/bin/env python3
"""Fetch small official global products into /workspace/global_data/.

Never prints credentials. Uses EARTHDATA_TOKEN only as a Bearer header for GRACE.
"""
from __future__ import annotations

import os
import ssl
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path("/workspace/global_data")
UA = "SpaceAppsTrendDetective/1.0 (global monthly archive)"
CTX = ssl.create_default_context()


def log(msg: str) -> None:
    print(msg, flush=True)


def token() -> str:
    t = os.environ.get("EARTHDATA_TOKEN") or ""
    if not t:
        raise SystemExit("EARTHDATA_TOKEN is not set")
    return t


def download(url: str, dest: Path, need_auth=False, timeout=300, max_tries=4) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        log(f"  exists {dest} ({dest.stat().st_size} bytes)")
        return dest.stat().st_size
    tmp = dest.with_suffix(dest.suffix + ".part")
    headers = {"User-Agent": UA}
    if need_auth:
        headers["Authorization"] = f"Bearer {token()}"
    last = None
    for i in range(max_tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r, open(tmp, "wb") as f:
                while True:
                    chunk = r.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            tmp.replace(dest)
            sz = dest.stat().st_size
            log(f"  got {dest.name} {sz} bytes in {time.time()-t0:.1f}s")
            return sz
        except Exception as e:
            last = e
            log(f"  retry {i+1} {dest.name}: {type(e).__name__}")
            time.sleep(2 + i * 3)
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
    raise RuntimeError(f"failed {url}: {type(last).__name__}")


def main():
    jobs = [
        ("gistemp", "https://data.giss.nasa.gov/pub/gistemp/gistemp1200_GHCNv4_ERSSTv5.nc.gz",
         ROOT / "gistemp/gistemp1200_GHCNv4_ERSSTv5.nc.gz", False),
        ("gistemp", "https://data.giss.nasa.gov/pub/gistemp/GLB.Ts+dSST.csv",
         ROOT / "gistemp/GLB.Ts+dSST.csv", False),
        ("gistemp", "https://data.giss.nasa.gov/pub/gistemp/NH.Ts+dSST.csv",
         ROOT / "gistemp/NH.Ts+dSST.csv", False),
        ("gistemp", "https://data.giss.nasa.gov/pub/gistemp/SH.Ts+dSST.csv",
         ROOT / "gistemp/SH.Ts+dSST.csv", False),
        ("gistemp", "https://data.giss.nasa.gov/pub/gistemp/ZonAnn.Ts+dSST.csv",
         ROOT / "gistemp/ZonAnn.Ts+dSST.csv", False),
        ("hadcrut5", "https://www.metoffice.gov.uk/hadobs/hadcrut5/data/current/analysis/HadCRUT.5.2.0.0.analysis.anomalies.ensemble_mean.nc",
         ROOT / "hadcrut5/HadCRUT.5.2.0.0.analysis.anomalies.ensemble_mean.nc", False),
        ("hadcrut5", "https://www.metoffice.gov.uk/hadobs/hadcrut5/data/current/analysis/HadCRUT.5.2.0.0.analysis.summary_series.global.monthly.csv",
         ROOT / "hadcrut5/HadCRUT.5.2.0.0.analysis.summary_series.global.monthly.csv", False),
        ("hadcrut5", "https://www.metoffice.gov.uk/hadobs/hadcrut5/data/current/analysis/HadCRUT.5.2.0.0.analysis.summary_series.northern_hemisphere.monthly.csv",
         ROOT / "hadcrut5/HadCRUT.5.2.0.0.analysis.summary_series.northern_hemisphere.monthly.csv", False),
        ("berkeley_earth", "https://berkeley-earth-temperature.s3.us-west-1.amazonaws.com/Global/Gridded/Complete_TAVG_LatLong1.nc",
         ROOT / "berkeley_earth/Complete_TAVG_LatLong1.nc", False),
        ("grace", "https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-protected/TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4/GRCTellus.JPL.200204_202609.GLO.RL06.3M.MSCNv04CRI.nc",
         ROOT / "grace/GRCTellus.JPL.200204_202609.GLO.RL06.3M.MSCNv04CRI.nc", True),
        ("grace", "https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-docs/gracefo/open/docs/GRACE_GRACE-FO_ReleaseNotes_JPL_MASCON.txt",
         ROOT / "grace/GRACE_GRACE-FO_ReleaseNotes_JPL_MASCON.txt", True),
    ]
    # Prefer local copies when already present (faster, same official files)
    local_aliases = {
        str(ROOT / "gistemp/gistemp1200_GHCNv4_ERSSTv5.nc.gz"):
            Path("/workspace/ukraine_samples/extra/gistemp/gistemp1200_GHCNv4_ERSSTv5.nc.gz"),
        str(ROOT / "hadcrut5/HadCRUT.5.2.0.0.analysis.anomalies.ensemble_mean.nc"):
            Path("/workspace/ukraine_samples/extra/hadcrut5/HadCRUT.5.2.0.0.analysis.anomalies.ensemble_mean.nc"),
    }

    ok, err = 0, 0
    for group, url, dest, auth in jobs:
        log(f"{group}: {dest.name}")
        try:
            alias = local_aliases.get(str(dest))
            if alias and alias.exists() and not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                # hardlink if same filesystem, else copy
                try:
                    os.link(alias, dest)
                    log(f"  hardlinked from existing {alias} ({dest.stat().st_size} bytes)")
                except OSError:
                    import shutil
                    shutil.copy2(alias, dest)
                    log(f"  copied from existing {alias} ({dest.stat().st_size} bytes)")
                ok += 1
                continue
            download(url, dest, need_auth=auth, timeout=600)
            ok += 1
        except Exception as e:
            log(f"  FAIL {dest.name}: {type(e).__name__}: {e}")
            err += 1
    log(f"done ok={ok} err={err}")
    return 0 if err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
