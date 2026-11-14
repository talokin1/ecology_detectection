#!/usr/bin/env python3
"""Download extra global monthly slim layers via DAP4.

MODIS QC, GLDAS Rainf+Snowf, MERRA-2 U10M/V10M, MERRA-2 monthly T2MMAX/T2MMIN
(from M2SMNXSLV, not M2TMNXSLV). Never prints credentials.
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

from locate import GLOBAL_DATA, LOG_DIR, SCRATCH, data_root

ROOT = GLOBAL_DATA
LOG = LOG_DIR / "extra_vars_fetch.log"
PROGRESS = LOG_DIR / "extra_vars_progress.json"
PROBE_DIR = SCRATCH / "extra_var_month_probes"
UA = "SpaceAppsTrendDetective/1.0"
CTX = ssl.create_default_context()
LOCK = threading.Lock()

COLLECTIONS = {
    "mod13c2_qc": dict(
        concept_id="C2565788914-LPCLOUD",
        short="MOD13C2", version="061", style="lpdaac",
        ce=("/MOD_Grid_monthly_CMG_VI/Data_Fields/CMG_0_05_Deg_Monthly_VI_Quality;"
            "/MOD_Grid_monthly_CMG_VI/Data_Fields/CMG_0_05_Deg_Monthly_pixel_reliability"),
        outdir="mod13c2_qc", min_bytes=50_000,
        vars="VI_Quality + pixel_reliability",
    ),
    "mod11c3_qc": dict(
        concept_id="C2565788897-LPCLOUD",
        short="MOD11C3", version="061", style="lpdaac",
        ce=("/MODIS_MONTHLY_0_05DEG_CMG_LST/Data_Fields/QC_Day;"
            "/MODIS_MONTHLY_0_05DEG_CMG_LST/Data_Fields/QC_Night;"
            "/MODIS_MONTHLY_0_05DEG_CMG_LST/Data_Fields/Clear_sky_days;"
            "/MODIS_MONTHLY_0_05DEG_CMG_LST/Data_Fields/Clear_sky_nights"),
        outdir="mod11c3_qc", min_bytes=50_000,
        vars="QC_Day, QC_Night, Clear_sky_days, Clear_sky_nights",
    ),
    "gldas20_rainf": dict(
        concept_id="C1233767569-GES_DISC",
        short="GLDAS_NOAH025_M", version="2.0", style="gesdisc",
        ce="/Rainf_f_tavg;/Snowf_tavg;/lat;/lon;/time",
        outdir="gldas20_rainf", min_bytes=80_000,
        vars="Rainf_f_tavg + Snowf_tavg",
    ),
    "gldas21_rainf": dict(
        concept_id="C1342986036-GES_DISC",
        short="GLDAS_NOAH025_M", version="2.1", style="gesdisc",
        ce="/Rainf_f_tavg;/Snowf_tavg;/lat;/lon;/time",
        outdir="gldas21_rainf", min_bytes=80_000,
        vars="Rainf_f_tavg + Snowf_tavg",
    ),
    "merra2_slv_wind": dict(
        concept_id="C1276812859-GES_DISC",
        short="M2TMNXSLV", version="5.12.4", style="gesdisc",
        ce="/U10M;/V10M;/lat;/lon;/time",
        outdir="merra2_slv_wind", min_bytes=80_000,
        vars="U10M + V10M",
    ),
    "merra2_statm_extremes": dict(
        concept_id="C1276812828-GES_DISC",
        short="M2SMNXSLV", version="5.12.4", style="gesdisc",
        ce="/T2MMAX;/T2MMIN;/lat;/lon;/time",
        outdir="merra2_statm_extremes", min_bytes=80_000,
        vars="T2MMAX + T2MMIN (monthly statistics collection, not tavgM SLV)",
    ),
}

# Also probe MOD11C3 without clear-sky, in case that layer is huge
PROBE_ONLY = {
    "mod11c3_qc_only": dict(
        concept_id="C2565788897-LPCLOUD",
        short="MOD11C3", version="061", style="lpdaac",
        ce=("/MODIS_MONTHLY_0_05DEG_CMG_LST/Data_Fields/QC_Day;"
            "/MODIS_MONTHLY_0_05DEG_CMG_LST/Data_Fields/QC_Night"),
        vars="QC_Day + QC_Night only",
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
    SCRATCH.mkdir(parents=True, exist_ok=True)
    cache = SCRATCH / f"cmr_granules_{concept_id}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < 12 * 3600:
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
    name = producer.replace("/", "_").replace(":", "_")
    if not name.endswith(".nc4"):
        name += ".nc4"
    return name


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


def probe_month(key: str, cfg: dict, gran: dict, dest: Path) -> dict:
    url = dap4_url(cfg, gran["producer"])
    headers = {"User-Agent": UA, "Authorization": f"Bearer {token()}"}
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=300, context=CTX) as r, open(dest, "wb") as f:
            status = r.status
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        sz = dest.stat().st_size
        magic = dest.read_bytes()[:4]
        ok = magic in (b"\x89HDF", b"CDF\x01", b"CDF\x02")
        return {"key": key, "ok": ok, "status": status, "bytes": sz,
                "seconds": round(time.time()-t0, 2), "magic": magic.decode("latin1", "replace"),
                "producer": gran["producer"], "vars": cfg.get("vars")}
    except Exception as e:
        return {"key": key, "ok": False, "error": type(e).__name__,
                "http": getattr(e, "code", None), "seconds": round(time.time()-t0, 2)}


def save_progress(state: dict) -> None:
    with LOCK:
        PROGRESS.write_text(json.dumps(state, indent=2, default=str))


def free_bytes(path=None) -> int:
    import os
    st = os.statvfs(path or data_root())
    return st.f_bavail * st.f_frsize


def main():
    mode = sys.argv[1:] or ["probe", "fetch"]
    if "probe" in mode or mode == ["fetch"]:
        # always probe first if log empty / requested
        pass
    LOG.write_text("")
    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    log(f"start mode={mode} free={free_bytes()/1e9:.2f} GB")

    # list granules
    granules = {}
    for key, cfg in {**COLLECTIONS, **PROBE_ONLY}.items():
        cid = cfg["concept_id"]
        if cid not in granules:
            rows = list_granules(cid)
            granules[cid] = rows
            log(f"CMR {cid} n={len(rows)} {rows[0]['start'] if rows else None} -> {rows[-1]['start'] if rows else None}")

    probe_results = {}
    if "probe" in mode or "fetch" in mode:
        log("one-month probes...")
        jobs = []
        for key, cfg in COLLECTIONS.items():
            jobs.append((key, cfg, granules[cfg["concept_id"]][0]))
        for key, cfg in PROBE_ONLY.items():
            jobs.append((key, cfg, granules[cfg["concept_id"]][0]))
        for key, cfg, gran in jobs:
            dest = PROBE_DIR / f"{key}.nc4"
            rec = probe_month(key, cfg, gran, dest)
            n = len(granules[cfg["concept_id"]])
            rec["n_months"] = n
            rec["est_total"] = (rec.get("bytes") or 0) * n
            probe_results[key] = rec
            log(f"  probe {key}: ok={rec.get('ok')} bytes={rec.get('bytes')} est_total={rec.get('est_total')} s={rec.get('seconds')} err={rec.get('error')}")
        (LOG_DIR / "extra_var_month_probes.json").write_text(
            json.dumps(probe_results, indent=2)
        )

    if "fetch" not in mode:
        return 0

    # Drop clear-sky from MOD11C3 if the combined layer is not cheap
    # Threshold: if including clear-sky more than 3x QC-only and would exceed ~8 GB, keep it only if still modest.
    qc_plus = probe_results.get("mod11c3_qc", {})
    qc_only = probe_results.get("mod11c3_qc_only", {})
    if qc_plus.get("ok") and qc_only.get("ok"):
        log(f"MOD11C3 QC+clear {qc_plus['bytes']} vs QC-only {qc_only['bytes']}; "
            f"est {qc_plus['est_total']/1e9:.2f} vs {qc_only['est_total']/1e9:.2f} GB")
        # "if cheap": include if estimated total under 8 GB or not much larger than QC-only
        if qc_plus["est_total"] > 8e9 and qc_plus["bytes"] > 3 * qc_only["bytes"]:
            log("Clear-sky not cheap; fetching QC_Day/QC_Night only")
            COLLECTIONS["mod11c3_qc"]["ce"] = PROBE_ONLY["mod11c3_qc_only"]["ce"]
            COLLECTIONS["mod11c3_qc"]["vars"] = "QC_Day + QC_Night only (Clear_sky not cheap)"
        else:
            log("Clear-sky is cheap enough; including it")

    # Abort if any probe failed
    fetch_keys = list(COLLECTIONS)
    for key in list(fetch_keys):
        rec = probe_results.get(key, {})
        if not rec.get("ok"):
            log(f"SKIP {key}: probe failed {rec}")
            fetch_keys.remove(key)

    est = sum(probe_results[k]["est_total"] for k in fetch_keys if probe_results.get(k, {}).get("est_total"))
    free = free_bytes()
    # leave 20% of 128 GiB (~27.5e9? df size is 128G binary = 128*1024^3)
    # 20% of the filesystem: use statvfs
    import os as _os
    st = _os.statvfs(data_root())
    total = st.f_blocks * st.f_frsize
    must_leave = 0.20 * total
    log(f"estimated extra {est/1e9:.2f} GB SI; free {free/1e9:.2f} GB; must leave {must_leave/1e9:.2f} GB")
    if free - est < must_leave:
        log("ERROR: fetch would breach 20% free floor; aborting")
        return 2

    state = {"started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "collections": {},
             "probes": probe_results}
    jobs = []
    for key in fetch_keys:
        cfg = COLLECTIONS[key]
        grans = granules[cfg["concept_id"]]
        state["collections"][key] = {
            "n": len(grans), "ok": 0, "exists": 0, "fail": 0, "bytes": 0,
            "vars": cfg.get("vars"),
            "first": grans[0]["start"] if grans else None,
            "last": grans[-1]["start"] if grans else None,
        }
        for g in grans:
            jobs.append((key, cfg, g))
        log(f"{key}: {len(grans)} granules, vars={cfg.get('vars')}")
    save_progress(state)

    workers = 5
    log(f"downloading {len(jobs)} files with {workers} workers")
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(download_one, key, cfg, g) for key, cfg, g in jobs]
        for fut in as_completed(futs):
            rec = fut.result()
            key = rec["key"]
            stt = state["collections"].setdefault(key, {"ok": 0, "exists": 0, "fail": 0, "bytes": 0})
            stt[rec["status"]] = stt.get(rec["status"], 0) + 1
            stt["bytes"] = stt.get("bytes", 0) + (rec.get("bytes") or 0)
            done += 1
            if rec["status"] == "fail":
                log(f"FAIL {key} {rec.get('producer')} {rec.get('error')} http={rec.get('http')}")
            if done % 25 == 0 or rec["status"] == "fail":
                state["done"] = done
                state["total"] = len(jobs)
                save_progress(state)
                log(f"progress {done}/{len(jobs)}")
    state["done"] = done
    state["total"] = len(jobs)
    state["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    save_progress(state)
    log(f"finished {json.dumps(state['collections'], default=str)}")
    fails = sum(v.get("fail", 0) for v in state["collections"].values())
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
