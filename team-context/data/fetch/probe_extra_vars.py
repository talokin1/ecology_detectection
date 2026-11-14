#!/usr/bin/env python3
"""Probe DAP4 DMR / one-month slim sizes for QC, Rainf, wind, max/min.
Never prints credentials.
"""
from __future__ import annotations
import json, os, ssl, urllib.parse, urllib.request, urllib.error, time
from pathlib import Path

UA = "SpaceAppsTrendDetective/1.0"
CTX = ssl.create_default_context()
OUT = Path("/workspace/spaceapps/analysis/scripts/global_fetch/extra_var_probes.json")

def token():
    t = os.environ.get("EARTHDATA_TOKEN") or ""
    if not t:
        raise SystemExit("EARTHDATA_TOKEN is not set")
    return t

def log(m):
    print(m, flush=True)

def get(url, timeout=180, dest=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Authorization": f"Bearer {token()}"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            data = r.read()
            status = r.status
        if dest:
            Path(dest).write_bytes(data)
        return {"ok": True, "status": status, "bytes": len(data), "seconds": round(time.time()-t0, 2), "dest": str(dest) if dest else None}
    except urllib.error.HTTPError as e:
        body = b""
        try:
            body = e.read()[:500]
        except Exception:
            pass
        return {"ok": False, "status": e.code, "error": "HTTPError", "body_head": body.decode("utf-8", "replace"), "seconds": round(time.time()-t0, 2)}
    except Exception as e:
        return {"ok": False, "error": type(e).__name__, "seconds": round(time.time()-t0, 2)}

def dmr_url(concept_id, gran):
    return (f"https://opendap.earthdata.nasa.gov/collections/{concept_id}"
            f"/granules/{urllib.parse.quote(gran, safe='')}.dmr.xml")

def dap4_url(concept_id, gran, ce):
    base = (f"https://opendap.earthdata.nasa.gov/collections/{concept_id}"
            f"/granules/{urllib.parse.quote(gran, safe='')}.dap.nc4")
    return base + "?" + urllib.parse.urlencode({"dap4.ce": ce})

def cmr_search(q):
    url = "https://cmr.earthdata.nasa.gov/search/collections.umm_json?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
        data = json.loads(r.read())
        hits = r.headers.get("CMR-Hits")
    rows = []
    for item in data.get("items", []):
        meta, umm = item.get("meta", {}), item.get("umm", {})
        rows.append({
            "concept_id": meta.get("concept-id"),
            "short_name": umm.get("ShortName"),
            "version": umm.get("VersionId") or umm.get("Version"),
            "title": (umm.get("EntryTitle") or "")[:180],
            "provider": meta.get("provider-id"),
        })
    return {"hits": hits, "rows": rows}

def main():
    results = {}
    # CMR for max/min monthly collections
    log("CMR searches for MERRA-2 max/min...")
    results["cmr"] = {}
    for key, q in {
        "T2MMAX": {"keyword": "T2MMAX MERRA-2", "page_size": "15"},
        "M2SMNXSLV": {"short_name": "M2SMNXSLV", "page_size": "10"},
        "M2SDNXSLV": {"short_name": "M2SDNXSLV", "page_size": "10"},
        "statM": {"keyword": "MERRA-2 statM slv", "page_size": "15"},
        "statD": {"keyword": "MERRA-2 daily statistics slv", "page_size": "10"},
        "M2IMNXSLV": {"short_name": "M2IMNXSLV", "page_size": "5"},
    }.items():
        rec = cmr_search(q)
        results["cmr"][key] = rec
        log(f"  {key}: hits={rec['hits']} {[(r['concept_id'], r['short_name'], r['version'], r['title'][:70]) for r in rec['rows'][:6]]}")

    probes = [
        dict(key="mod13c2_dmr", kind="dmr",
             concept_id="C2565788914-LPCLOUD",
             gran="MOD13C2.A2000032.061.2020042083108"),
        dict(key="mod11c3_dmr", kind="dmr",
             concept_id="C2565788897-LPCLOUD",
             gran="MOD11C3.A2000032.061.2020048181639"),
        dict(key="merra2_slv_dmr", kind="dmr",
             concept_id="C1276812859-GES_DISC",
             gran="M2TMNXSLV.5.12.4:MERRA2_100.tavgM_2d_slv_Nx.198001.nc4"),
        dict(key="gldas21_dmr", kind="dmr",
             concept_id="C1342986036-GES_DISC",
             gran="GLDAS_NOAH025_M.2.1:GLDAS_NOAH025_M.A200001.021.nc4"),
        dict(key="gldas20_dmr", kind="dmr",
             concept_id="C1233767569-GES_DISC",
             gran="GLDAS_NOAH025_M.2.0:GLDAS_NOAH025_M.A194801.020.nc4"),
    ]
    Path("/tmp/dmr_probes").mkdir(exist_ok=True)
    results["dmr"] = {}
    for p in probes:
        url = dmr_url(p["concept_id"], p["gran"])
        dest = f"/tmp/dmr_probes/{p['key']}.xml"
        log(f"DMR {p['key']} ...")
        rec = get(url, dest=dest)
        rec["url_no_query"] = f"opendap ... {p['key']}"
        results["dmr"][p["key"]] = rec
        log(f"  {rec.get('status')} {rec.get('bytes')} {rec.get('error')}")

    OUT.write_text(json.dumps(results, indent=2))
    log(f"wrote {OUT}")

if __name__ == "__main__":
    main()
