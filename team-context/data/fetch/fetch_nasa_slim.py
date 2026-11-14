#!/usr/bin/env python3
"""Download global monthly slim (used variables only) via DAP4.

Never prints credentials. Uses EARTHDATA_TOKEN as a Bearer header only.
"""
from __future__ import annotations

import json
import os
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from locate import GLOBAL_DATA, LOG_DIR

ROOT = GLOBAL_DATA
LOG = LOG_DIR / "nasa_slim_fetch.log"
PROGRESS = LOG_DIR / "nasa_slim_progress.json"
UA = "SpaceAppsTrendDetective/1.0"
CTX = ssl.create_default_context()
LOCK = threading.Lock()

COLLECTIONS = {
    "merra2_slv": dict(
        concept_id="C1276812859-GES_DISC",
        short="M2TMNXSLV", version="5.12.4",
        style="gesdisc",
        ce="/T2M;/QV2M;/SLP;/lat;/lon;/time",
        outdir="merra2_slv_slim",
        min_bytes=200_000,
    ),
    "merra2_flx": dict(
        concept_id="C1276812868-GES_DISC",
        short="M2TMNXFLX", version="5.12.4",
        style="gesdisc",
        ce="/PRECTOT;/PRECTOTCORR;/lat;/lon;/time",
        outdir="merra2_flx_slim",
        min_bytes=200_000,
    ),
    "gldas20": dict(
        concept_id="C1233767569-GES_DISC",
        short="GLDAS_NOAH025_M", version="2.0",
        style="gesdisc",
        ce="/SoilMoi0_10cm_inst;/RootMoist_inst;/Evap_tavg;/Qs_acc;/Qsb_acc;/SWE_inst;/Tair_f_inst;/lat;/lon;/time",
        outdir="gldas20_slim",
        min_bytes=400_000,
    ),
    "gldas21": dict(
        concept_id="C1342986036-GES_DISC",
        short="GLDAS_NOAH025_M", version="2.1",
        style="gesdisc",
        ce="/SoilMoi0_10cm_inst;/RootMoist_inst;/Evap_tavg;/Qs_acc;/Qsb_acc;/SWE_inst;/Tair_f_inst;/lat;/lon;/time",
        outdir="gldas21_slim",
        min_bytes=400_000,
    ),
    "imerg": dict(
        concept_id="C2723754851-GES_DISC",
        short="GPM_3IMERGM", version="07",
        style="gesdisc",
        ce="/Grid/precipitation;/Grid/lon;/Grid/lat;/Grid/time",
        outdir="gpm_imerg_slim",
        min_bytes=400_000,
    ),
    "airs": dict(
        concept_id="C1701805662-GES_DISC",
        short="AIRS3STM", version="7.0",
        style="gesdisc",
        ce=("/ascending/Data_Fields/SurfAirTemp_A;/ascending/Data_Fields/TotH2OVap_A;"
            "/descending/Data_Fields/SurfAirTemp_D;/descending/Data_Fields/TotH2OVap_D;"
            "/location/Data_Fields/Latitude;/location/Data_Fields/Longitude"),
        outdir="airs3stm_slim",
        min_bytes=50_000,
    ),
    "mod13c2": dict(
        concept_id="C2565788914-LPCLOUD",
        short="MOD13C2", version="061",
        style="lpdaac",
        ce=("/MOD_Grid_monthly_CMG_VI/Data_Fields/CMG_0_05_Deg_Monthly_NDVI;"
            "/MOD_Grid_monthly_CMG_VI/Data_Fields/CMG_0_05_Deg_Monthly_EVI"),
        outdir="mod13c2_slim",
        min_bytes=200_000,
    ),
    "mod11c3": dict(
        concept_id="C2565788897-LPCLOUD",
        short="MOD11C3", version="061",
        style="lpdaac",
        ce=("/MODIS_MONTHLY_0_05DEG_CMG_LST/Data_Fields/LST_Day_CMG;"
            "/MODIS_MONTHLY_0_05DEG_CMG_LST/Data_Fields/LST_Night_CMG"),
        outdir="mod11c3_slim",
        min_bytes=200_000,
    ),
}


def log(msg: str) -> None:
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    with LOCK:
        with LOG.open("a") as f:
            f.write(line + "\n")


def token() -> str:
    t = os.environ.get("EARTHDATA_TOKEN") or ""
    if not t:
        raise SystemExit("EARTHDATA_TOKEN is not set")
    return t


def http_json(url: str, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.status, json.loads(r.read()), {k.lower(): v for k, v in r.headers.items()}


def list_granules(concept_id: str) -> list[dict]:
    cache = Path(f"/tmp/cmr_granules_{concept_id}.json")
    if cache.exists() and time.time() - cache.stat().st_mtime < 6 * 3600:
        return json.loads(cache.read_text())
    rows = []
    page = 1
    while True:
        q = urllib.parse.urlencode({
            "collection_concept_id": concept_id,
            "page_size": 2000,
            "page_num": page,
            "sort_key": "start_date",
        })
        url = "https://cmr.earthdata.nasa.gov/search/granules.json?" + q
        status, js, headers = http_json(url)
        entries = js.get("feed", {}).get("entry", [])
        for e in entries:
            rows.append({
                "producer": e.get("producer_granule_id") or e.get("title"),
                "title": e.get("title"),
                "start": e.get("time_start"),
                "end": e.get("time_end"),
                "id": e.get("id"),
            })
        hits = int(headers.get("cmr-hits") or len(rows))
        log(f"  CMR {concept_id} page {page} got {len(entries)} total {len(rows)}/{hits}")
        if len(entries) < 2000 or len(rows) >= hits:
            break
        page += 1
        if page > 80:
            break
    cache.write_text(json.dumps(rows))
    return rows


def dap4_url(cfg: dict, producer: str) -> str:
    if cfg["style"] == "gesdisc":
        gran = f"{cfg['short']}.{cfg['version']}:{producer}"
    else:
        gran = producer
    base = (
        f"https://opendap.earthdata.nasa.gov/collections/{cfg['concept_id']}"
        f"/granules/{urllib.parse.quote(gran, safe='')}.dap.nc4"
    )
    return base + "?" + urllib.parse.urlencode({"dap4.ce": cfg["ce"]})


def safe_name(producer: str) -> str:
    return producer.replace("/", "_").replace(":", "_") + ".nc4"


def download_one(key: str, cfg: dict, gran: dict) -> dict:
    outdir = ROOT / cfg["outdir"]
    outdir.mkdir(parents=True, exist_ok=True)
    dest = outdir / safe_name(gran["producer"])
    if dest.exists() and dest.stat().st_size >= cfg["min_bytes"]:
        return {"key": key, "producer": gran["producer"], "status": "exists", "bytes": dest.stat().st_size}
    url = dap4_url(cfg, gran["producer"])
    tmp = dest.with_suffix(dest.suffix + ".part")
    headers = {"User-Agent": UA, "Authorization": f"Bearer {token()}"}
    last = None
    for attempt in range(4):
        try:
            t0 = time.time()
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=300, context=CTX) as r, open(tmp, "wb") as f:
                status = r.status
                while True:
                    chunk = r.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            sz = tmp.stat().st_size
            # basic magic check
            magic = tmp.read_bytes()[:4]
            if sz < cfg["min_bytes"] or magic not in (b"\x89HDF", b"CDF\x01", b"CDF\x02"):
                raise RuntimeError(f"bad file status={status} size={sz} magic={magic!r}")
            tmp.replace(dest)
            return {"key": key, "producer": gran["producer"], "status": "ok",
                    "bytes": sz, "seconds": round(time.time()-t0, 2)}
        except Exception as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
    err = type(last).__name__
    code = getattr(last, "code", None)
    return {"key": key, "producer": gran["producer"], "status": "fail",
            "error": err, "http": code}


def probe_modis() -> bool:
    """Try one MOD13C2 month; skip both MODIS collections if it fails."""
    cfg = COLLECTIONS["mod13c2"]
    granules = list_granules(cfg["concept_id"])
    if not granules:
        log("MODIS CMR empty")
        return False
    rec = download_one("mod13c2_probe", cfg, granules[0])
    log(f"MODIS probe: {rec}")
    return rec.get("status") in ("ok", "exists")


def save_progress(state: dict) -> None:
    with LOCK:
        PROGRESS.write_text(json.dumps(state, indent=2, default=str))


def main():
    keys = sys.argv[1:] or list(COLLECTIONS)
    # optional: skip modis if first arg is --no-modis
    if keys and keys[0] == "--no-modis":
        keys = [k for k in COLLECTIONS if not k.startswith("mod")]
    LOG.write_text("")
    log(f"start keys={keys}")

    if "mod13c2" in keys or "mod11c3" in keys:
        if not probe_modis():
            log("MODIS DAP4 probe failed; skipping MODIS collections this run")
            keys = [k for k in keys if not k.startswith("mod")]

    state = {"started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "collections": {}}
    # list all first
    jobs = []
    for key in keys:
        cfg = COLLECTIONS[key]
        grans = list_granules(cfg["concept_id"])
        state["collections"][key] = {
            "n": len(grans),
            "ok": 0, "exists": 0, "fail": 0,
            "bytes": 0,
            "first": grans[0]["start"] if grans else None,
            "last": grans[-1]["start"] if grans else None,
        }
        for g in grans:
            jobs.append((key, cfg, g))
        log(f"{key}: {len(grans)} granules {state['collections'][key]['first']} -> {state['collections'][key]['last']}")
    save_progress(state)

    workers = 5
    log(f"downloading {len(jobs)} files with {workers} workers")
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(download_one, key, cfg, g) for key, cfg, g in jobs]
        for fut in as_completed(futs):
            rec = fut.result()
            key = rec["key"]
            if key.endswith("_probe"):
                key = "mod13c2"
            st = state["collections"].setdefault(key, {"ok": 0, "exists": 0, "fail": 0, "bytes": 0})
            st[rec["status"]] = st.get(rec["status"], 0) + 1
            st["bytes"] = st.get("bytes", 0) + (rec.get("bytes") or 0)
            done += 1
            if rec["status"] == "fail":
                log(f"FAIL {key} {rec.get('producer')} {rec.get('error')} http={rec.get('http')}")
            if done % 25 == 0 or rec["status"] == "fail":
                state["done"] = done
                state["total"] = len(jobs)
                save_progress(state)
                log(f"progress {done}/{len(jobs)} { {k: {s: v.get(s,0) for s in ('ok','exists','fail','bytes')} for k,v in state['collections'].items()} }")
    state["done"] = done
    state["total"] = len(jobs)
    state["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    save_progress(state)
    log(f"finished {json.dumps(state['collections'], default=str)}")
    fails = sum(v.get("fail", 0) for v in state["collections"].values())
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
