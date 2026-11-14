#!/usr/bin/env python3
"""Download official GPCC v2025 1° monthly global chunks."""
from __future__ import annotations
import re, ssl, time, urllib.request
from pathlib import Path

BASE = "https://opendata.dwd.de/climate_environment/GPCC/GPCC_Precipitation_Analysis_Monthly/Version_2025/100_degree/"
OUT = Path("/workspace/global_data/gpcc_v2025_1deg")
OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "SpaceAppsTrendDetective/1.0"}
CTX = ssl.create_default_context()
META = Path("/workspace/spaceapps/analysis/scripts/global_fetch/gpcc_listing.json")

def log(m):
    print(m, flush=True)

def main():
    req = urllib.request.Request(BASE, headers=UA)
    with urllib.request.urlopen(req, timeout=90, context=CTX) as r:
        text = r.read().decode("utf-8", "replace")
    files = []
    for m in re.finditer(r'<a href="(gpcc_precipitation_analysis_monthly_[^"]+\.nc\.gz)">.*?\s([0-9]+)\s*$', text, re.M):
        files.append((m.group(1), int(m.group(2))))
    log(f"listing n={len(files)} sum={sum(s for _,s in files)}")
    import json
    META.write_text(json.dumps({"n": len(files), "bytes_sum": sum(s for _,s in files),
                                "files": [{"name": n, "bytes": s} for n,s in files]}, indent=2))
    ok = err = 0
    for name, expected in files:
        dest = OUT / name
        if dest.exists() and dest.stat().st_size == expected:
            log(f"  exists {name} ({expected})")
            ok += 1
            continue
        url = BASE + name
        tmp = dest.with_suffix(dest.suffix + ".part")
        last = None
        for attempt in range(4):
            try:
                t0 = time.time()
                req = urllib.request.Request(url, headers=UA)
                with urllib.request.urlopen(req, timeout=180, context=CTX) as r, open(tmp, "wb") as f:
                    while True:
                        chunk = r.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                sz = tmp.stat().st_size
                if expected and sz != expected:
                    raise RuntimeError(f"size {sz} != {expected}")
                tmp.replace(dest)
                log(f"  got {name} {sz} in {time.time()-t0:.1f}s")
                ok += 1
                last = None
                break
            except Exception as e:
                last = e
                log(f"  retry {attempt+1} {name}: {type(e).__name__}")
                time.sleep(2 + attempt * 2)
                if tmp.exists():
                    tmp.unlink(missing_ok=True)
        if last is not None:
            log(f"  FAIL {name}: {last}")
            err += 1
    log(f"done ok={ok} err={err}")
    return 0 if err == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
