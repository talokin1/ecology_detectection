#!/usr/bin/env python3
"""Measure global native sizes for Space Apps datasets.

Never prints credentials. Reads EARTHDATA_TOKEN / username / password from env
only to set Authorization headers when a HEAD/GET needs them.
"""
from __future__ import annotations

import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from locate import FETCH_DIR

OUT = FETCH_DIR / "size_measurements.json"
UA = "SpaceAppsTrendDetective/1.0 (global size inventory; contact via Earthdata account)"
CTX = ssl.create_default_context()


def token() -> str:
    return os.environ.get("EARTHDATA_TOKEN") or ""


def auth_headers(need_auth: bool) -> dict:
    h = {"User-Agent": UA, "Accept": "*/*"}
    if need_auth:
        t = token()
        if t:
            h["Authorization"] = f"Bearer {t}"
    return h


def request(url: str, method="GET", need_auth=False, timeout=90, max_redir=8):
    """Return (status, headers_dict, body_or_None). Follows redirects, adding
    auth on earthdata hosts only. Never logs header values."""
    seen = 0
    current = url
    headers = auth_headers(need_auth)
    while seen <= max_redir:
        req = urllib.request.Request(current, method=method, headers=headers)
        try:
            resp = urllib.request.urlopen(req, timeout=timeout, context=CTX)
            body = None if method == "HEAD" else resp.read()
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            out = (resp.status, hdrs, body, str(resp.geturl()))
            resp.close()
            return out
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                loc = e.headers.get("Location")
                if not loc:
                    return (e.code, {k.lower(): v for k, v in e.headers.items()}, e.read() if method != "HEAD" else None, current)
                current = urllib.parse.urljoin(current, loc)
                host = urllib.parse.urlparse(current).hostname or ""
                # Only send the bearer to Earthdata / NASA hosts after redirects
                need = need_auth and (
                    "earthdata.nasa.gov" in host
                    or "earthdatacloud.nasa.gov" in host
                    or "nasa.gov" in host
                    or "gesdisc" in host
                    or "podaac" in host
                    or "lpdaac" in host
                )
                headers = auth_headers(need)
                seen += 1
                continue
            body = None
            try:
                body = e.read() if method != "HEAD" else None
            except Exception:
                body = None
            return (e.code, {k.lower(): v for k, v in e.headers.items()}, body, current)
        except Exception as e:
            return (0, {}, str(type(e).__name__), current)
    return (0, {}, "too many redirects", current)


def head_length(url: str, need_auth=False, timeout=90) -> dict:
    status, hdrs, body, final = request(url, method="HEAD", need_auth=need_auth, timeout=timeout)
    cl = hdrs.get("content-length")
    # Some servers refuse HEAD or omit length; try a GET range
    if status in (0, 403, 405, 501) or cl is None:
        # GET with Range: bytes=0-0 to read Content-Range
        # Implement a small GET if HEAD failed without length
        if status != 200 or cl is None:
            h = auth_headers(need_auth)
            h["Range"] = "bytes=0-0"
            req = urllib.request.Request(url, method="GET", headers=h)
            try:
                resp = urllib.request.urlopen(req, timeout=timeout, context=CTX)
                hdrs2 = {k.lower(): v for k, v in resp.headers.items()}
                resp.close()
                cr = hdrs2.get("content-range") or ""
                m = re.search(r"/(\d+)$", cr)
                if m:
                    return {"url": url, "final": str(resp.geturl()) if hasattr(resp, "geturl") else final,
                            "status": resp.status, "bytes": int(m.group(1)),
                            "method": "range", "content_type": hdrs2.get("content-type")}
                cl2 = hdrs2.get("content-length")
                if cl2 and resp.status == 200:
                    return {"url": url, "status": resp.status, "bytes": int(cl2),
                            "method": "get", "content_type": hdrs2.get("content-type")}
            except urllib.error.HTTPError as e:
                hdrs2 = {k.lower(): v for k, v in e.headers.items()}
                cr = hdrs2.get("content-range") or ""
                m = re.search(r"/(\d+)$", cr)
                if m:
                    return {"url": url, "status": e.code, "bytes": int(m.group(1)),
                            "method": "range", "content_type": hdrs2.get("content-type")}
            except Exception as e:
                if cl is None:
                    return {"url": url, "status": status, "bytes": None, "error": type(e).__name__, "method": "head"}
    return {
        "url": url,
        "final": final,
        "status": status,
        "bytes": int(cl) if cl and cl.isdigit() else None,
        "method": "head",
        "content_type": hdrs.get("content-type"),
    }


def cmr_granules(concept_id: str, page_size=200, pages=1, temporal=None) -> dict:
    hits = None
    sizes_mb = []
    names = []
    sample_links = []
    for page in range(1, pages + 1):
        q = {
            "collection_concept_id": concept_id,
            "page_size": str(page_size),
            "page_num": str(page),
        }
        if temporal:
            q["temporal"] = temporal
        url = "https://cmr.earthdata.nasa.gov/search/granules.umm_json?" + urllib.parse.urlencode(q)
        status, hdrs, body, _ = request(url, method="GET", need_auth=False, timeout=120)
        if status != 200 or not body:
            return {"concept_id": concept_id, "status": status, "error": "cmr_failed",
                    "hits": hits, "sample_n": len(sizes_mb)}
        hits = int(hdrs.get("cmr-hits") or hits or 0)
        data = json.loads(body)
        for item in data.get("items", []):
            umm = item.get("umm", {})
            name = umm.get("GranuleUR") or umm.get("DataGranule", {}).get("ProducerGranuleId")
            names.append(name)
            info = (umm.get("DataGranule") or {}).get("ArchiveAndDistributionInformation") or []
            # sum Size of archive files, prefer SizeInBytes if present
            gbytes = 0
            got = False
            for d in info:
                if d.get("SizeInBytes"):
                    gbytes += d["SizeInBytes"]
                    got = True
                elif d.get("Size") is not None:
                    unit = (d.get("SizeUnit") or "MB").upper()
                    val = float(d["Size"])
                    if unit in ("KB", "KBYTE", "KBYTES"):
                        gbytes += int(val * 1000)
                    elif unit in ("MB", "MBYTE", "MBYTES"):
                        gbytes += int(val * 1_000_000)
                    elif unit in ("GB", "GBYTE", "GBYTES"):
                        gbytes += int(val * 1_000_000_000)
                    elif unit in ("TB", "TBYTE", "TBYTES"):
                        gbytes += int(val * 1_000_000_000_000)
                    elif unit in ("B", "BYTE", "BYTES"):
                        gbytes += int(val)
                    else:
                        gbytes += int(val * 1_000_000)
                    got = True
            if got:
                sizes_mb.append(gbytes)
            # links
            for url_item in umm.get("RelatedUrls") or []:
                ut = (url_item.get("Type") or "") + " " + (url_item.get("Subtype") or "")
                href = url_item.get("URL") or ""
                if href and ("GET DATA" in ut.upper() or "DOWNLOAD" in ut.upper() or "USE SERVICE API" in ut.upper()):
                    sample_links.append({"type": ut.strip(), "url": href, "name": name})
                    break
        if page * page_size >= (hits or 0):
            break
    n = len(sizes_mb)
    mean = sum(sizes_mb) / n if n else None
    med = sorted(sizes_mb)[n // 2] if n else None
    total_est = int(mean * hits) if mean and hits else None
    return {
        "concept_id": concept_id,
        "hits": hits,
        "sample_n": n,
        "sample_bytes_mean": mean,
        "sample_bytes_median": med,
        "sample_bytes_min": min(sizes_mb) if sizes_mb else None,
        "sample_bytes_max": max(sizes_mb) if sizes_mb else None,
        "total_bytes_from_sample_mean": total_est,
        "sum_sampled_bytes": sum(sizes_mb) if sizes_mb else None,
        "sample_names_head": names[:3],
        "sample_links_head": sample_links[:4],
    }


def cmr_search_collections(short_name: str, provider=None) -> list:
    q = {"short_name": short_name, "page_size": "15"}
    if provider:
        q["provider"] = provider
    url = "https://cmr.earthdata.nasa.gov/search/collections.umm_json?" + urllib.parse.urlencode(q)
    status, hdrs, body, _ = request(url, method="GET", timeout=60)
    if status != 200 or not body:
        return [{"error": status, "short_name": short_name}]
    data = json.loads(body)
    out = []
    for item in data.get("items", []):
        meta = item.get("meta", {})
        umm = item.get("umm", {})
        out.append({
            "concept_id": meta.get("concept-id"),
            "short_name": umm.get("ShortName"),
            "version": umm.get("VersionId") or umm.get("Version"),
            "title": (umm.get("EntryTitle") or "")[:160],
            "provider": meta.get("provider-id"),
        })
    return out


def list_index_sizes(url: str, pattern=r'href="([^"]+)"') -> dict:
    """Parse an Apache-style directory listing and sum Content-Length via
    listed sizes if present, else return file hrefs."""
    status, hdrs, body, final = request(url, method="GET", timeout=90)
    if status != 200 or not body:
        return {"url": url, "status": status, "error": "list_failed"}
    text = body.decode("utf-8", "replace")
    # Apache listing: <a href="file">file</a> ...  1234  or  12K  12M  12G
    files = []
    # Common pattern: href and later a size column
    row_re = re.compile(
        r'<a href="([^"]+)">([^<]+)</a>\s*</td><td[^>]*>\s*([^<]*)</td><td[^>]*>\s*([0-9.\s]+[KMGTkmgt]?)\s*<',
        re.I,
    )
    # Simpler preformatted: "href="file" ...  12-Nov-2026 10:00  12345678"
    pre_re = re.compile(
        r'<a href="([^"]+)">([^<]+)</a>\s+(\d{2}-[A-Za-z]{3}-\d{4}\s+\d{2}:\d{2})\s+([0-9.]+[KMG]?|-)\s*',
    )
    # nginx autoindex json not assumed
    for m in pre_re.finditer(text):
        href, name, date, sz = m.groups()
        if href.endswith("/") or href.startswith("?") or href.startswith("/"):
            continue
        files.append({"href": href, "name": name, "date": date, "size_raw": sz, "bytes": parse_ls_size(sz)})
    if not files:
        # fallback: just hrefs matching a data extension
        hrefs = re.findall(r'href="([^"?]+\.(?:nc|nc4|nc\.gz|tar\.gz|tgz|zip|hdf|he5|tif|cog|grb|grib2))"', text, re.I)
        files = [{"href": h, "name": h, "bytes": None} for h in hrefs]
    return {
        "url": url,
        "final": final,
        "status": status,
        "n_files": len(files),
        "bytes_sum_listed": sum(f["bytes"] or 0 for f in files) if any(f.get("bytes") for f in files) else None,
        "files": files,
    }


def parse_ls_size(s: str):
    if not s or s.strip() == "-":
        return None
    s = s.strip().replace(",", "")
    m = re.match(r"^([0-9.]+)\s*([KMGTkmgt]?)$", s)
    if not m:
        if s.isdigit():
            return int(s)
        return None
    val, unit = float(m.group(1)), m.group(2).upper()
    mult = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}[unit]
    # Apache -l uses human 1024 and also sometimes exact bytes
    return int(val * mult)


def main():
    results = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "items": {}}

    collections = {
        "merra2_slv": "C1276812859-GES_DISC",
        "merra2_flx": "C1276812868-GES_DISC",
        "gldas20": "C1233767569-GES_DISC",
        "gldas21": "C1342986036-GES_DISC",
        "imerg_monthly": "C2723754851-GES_DISC",
        "airs3stm": "C1701805662-GES_DISC",
        "omno2d": "C3333493715-GES_DISC",
        "omto3e": "C1266136071-GES_DISC",
        "grace_jpl_cri": "C3195527175-POCLOUD",
        "mod13c2": "C2565788914-LPCLOUD",
        "mod11c3": "C2565788897-LPCLOUD",
    }

    # Search a few short names for concept IDs first
    short_searches = {
        "mod11a2": ("MOD11A2", "LPCLOUD"),
        "mcd12q1": ("MCD12Q1", "LPCLOUD"),
        "swot_riversp": ("SWOT_L2_HR_RiverSP_2.0", None),
        "swot_riversp_reach": ("SWOT_L2_HR_RiverSP_reach_2.0", None),
        "hydrocron": ("HYDROCRON", None),
    }

    print("Searching CMR collections...", flush=True)
    results["collection_searches"] = {}
    for key, (short, prov) in short_searches.items():
        found = cmr_search_collections(short, prov)
        results["collection_searches"][key] = found
        print(f"  {key}: {len(found)} hits, first={(found[0].get('concept_id') if found else None)} {found[0].get('title') if found else ''}", flush=True)
        # Also try without version suffix
    # broader SWOT and Hydrocron searches
    for key, short in [
        ("swot_riversp_any", "SWOT_L2_HR_RiverSP_D"),
        ("swot_riversp_v2", "SWOT_L2_HR_RiverSP_2.0"),
    ]:
        found = cmr_search_collections(short)
        results["collection_searches"][key] = found
        print(f"  {key}: {[(x.get('concept_id'), x.get('short_name'), x.get('version')) for x in found[:5]]}", flush=True)

    # keyword search
    for label, q in [
        ("swot_keyword", "https://cmr.earthdata.nasa.gov/search/collections.umm_json?keyword=SWOT%20RiverSP&page_size=20"),
        ("hydrocron_keyword", "https://cmr.earthdata.nasa.gov/search/collections.umm_json?keyword=Hydrocron&page_size=10"),
        ("mcd12q1", "https://cmr.earthdata.nasa.gov/search/collections.umm_json?short_name=MCD12Q1&page_size=10"),
        ("mod11a2", "https://cmr.earthdata.nasa.gov/search/collections.umm_json?short_name=MOD11A2&page_size=10"),
    ]:
        status, hdrs, body, _ = request(q, timeout=60)
        if status == 200 and body:
            data = json.loads(body)
            rows = []
            for item in data.get("items", []):
                meta, umm = item.get("meta", {}), item.get("umm", {})
                rows.append({
                    "concept_id": meta.get("concept-id"),
                    "short_name": umm.get("ShortName"),
                    "version": umm.get("VersionId") or umm.get("Version"),
                    "title": (umm.get("EntryTitle") or "")[:160],
                    "provider": meta.get("provider-id"),
                    "hits_header": hdrs.get("cmr-hits"),
                })
            results["collection_searches"][label] = rows
            print(f"  {label}: {[(r['concept_id'], r['short_name'], r['version'], r['provider']) for r in rows[:8]]}", flush=True)

    # Add latest MCD12Q1 / MOD11A2 / SWOT if found
    def pick(rows, prefer_provider=None, prefer_version=None):
        if not rows:
            return None
        scored = []
        for r in rows:
            if r.get("error"):
                continue
            s = 0
            if prefer_provider and r.get("provider") == prefer_provider:
                s += 5
            if prefer_version and str(r.get("version")) == str(prefer_version):
                s += 5
            if r.get("provider") in ("LPCLOUD", "POCLOUD", "GES_DISC"):
                s += 2
            scored.append((s, r))
        scored.sort(key=lambda x: -x[0])
        return scored[0][1]["concept_id"] if scored else None

    mcd = pick(results["collection_searches"].get("mcd12q1") or results["collection_searches"].get("mcd12q1", []), "LPCLOUD", "061")
    m11 = pick(results["collection_searches"].get("mod11a2") or [], "LPCLOUD", "061")
    if mcd:
        collections["mcd12q1"] = mcd
    if m11:
        collections["mod11a2"] = m11
    # SWOT: prefer POCLOUD / Version D or 2.0
    for label in ("swot_keyword", "swot_riversp_any", "swot_riversp_v2", "swot_riversp"):
        rows = results["collection_searches"].get(label) or []
        for r in rows:
            sn = (r.get("short_name") or "")
            if "RiverSP" in sn and r.get("concept_id") and "POCLOUD" in (r.get("provider") or r.get("concept_id", "")):
                collections.setdefault("swot_riversp", r["concept_id"])
                print(f"  using SWOT {r}", flush=True)
                break

    print("CMR granule size samples...", flush=True)
    results["cmr"] = {}
    # Large collections: small sample; small ones: more pages
    page_plan = {
        "omno2d": (200, 2),
        "omto3e": (200, 2),
        "mod11a2": (200, 2),
        "mcd12q1": (200, 2),
        "swot_riversp": (200, 2),
        "grace_jpl_cri": (10, 1),
        "imerg_monthly": (200, 2),
        "airs3stm": (200, 2),
        "merra2_slv": (200, 3),
        "merra2_flx": (200, 3),
        "gldas20": (200, 4),  # 804 granules, try to get a solid sample
        "gldas21": (200, 2),
        "mod13c2": (200, 2),
        "mod11c3": (200, 2),
    }
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {}
        for name, cid in collections.items():
            ps, pg = page_plan.get(name, (200, 1))
            # For collections under ~400, grab all
            futs[ex.submit(cmr_granules, cid, ps, pg)] = name
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                rec = fut.result()
            except Exception as e:
                rec = {"error": type(e).__name__}
            results["cmr"][name] = rec
            tb = rec.get("total_bytes_from_sample_mean")
            gb = f"{tb/1e9:.3f} GB" if tb else "?"
            print(f"  {name}: hits={rec.get('hits')} sample={rec.get('sample_n')} mean={rec.get('sample_bytes_mean')} total~{gb}", flush=True)

    # Public HEAD / directory listings
    print("Public HEAD and directory listings...", flush=True)
    public_urls = {
        "gistemp_1200_nc_gz": "https://data.giss.nasa.gov/pub/gistemp/gistemp1200_GHCNv4_ERSSTv5.nc.gz",
        "gistemp_250_nc_gz": "https://data.giss.nasa.gov/pub/gistemp/gistemp250_GHCNv4_ERSSTv5.nc.gz",
        "gistemp_lnd_ocn": "https://data.giss.nasa.gov/pub/gistemp/gistemp1200_GHCNv4_ERSSTv5.nc",
        "hadcrut5_analysis_mean_metoffice": "https://www.metoffice.gov.uk/hadobs/hadcrut5/data/current/analysis/HadCRUT.5.2.0.0.analysis.anomalies.ensemble_mean.nc",
        "hadcrut5_analysis_mean_uea": "https://crudata.uea.ac.uk/cru/data/temperature/HadCRUT.5.2.0.0.analysis.anomalies.ensemble_mean.nc",
        "hadcrut5_noninfilled": "https://www.metoffice.gov.uk/hadobs/hadcrut5/data/current/analysis/HadCRUT.5.2.0.0.anomalies.ensemble_mean.nc",
        "berkeley_tavg_land_1deg": "https://berkeley-earth-temperature.s3.us-west-1.amazonaws.com/Global/Gridded/Complete_TAVG_LatLong1.nc",
        "berkeley_tmax_land_1deg": "https://berkeley-earth-temperature.s3.us-west-1.amazonaws.com/Global/Gridded/Complete_TMAX_LatLong1.nc",
        "berkeley_tmin_land_1deg": "https://berkeley-earth-temperature.s3.us-west-1.amazonaws.com/Global/Gridded/Complete_TMIN_LatLong1.nc",
        "berkeley_landocean_1deg": "https://berkeley-earth-temperature.s3.us-west-1.amazonaws.com/Global/Gridded/Land_and_Ocean_LatLong1.nc",
        "berkeley_landocean_eqarea": "https://berkeley-earth-temperature.s3.us-west-1.amazonaws.com/Global/Gridded/Land_and_Ocean_EqualArea.nc",
        "cru_ts_410_tmp": "https://crudata.uea.ac.uk/cru/data/hrg/cru_ts_4.10/cruts.2604091129.v4.10/tmp/cru_ts4.10.1901.2025.tmp.dat.nc.gz",
        "cru_ts_410_pre": "https://crudata.uea.ac.uk/cru/data/hrg/cru_ts_4.10/cruts.2604091129.v4.10/pre/cru_ts4.10.1901.2025.pre.dat.nc.gz",
        "cru_ts_410_tmn": "https://crudata.uea.ac.uk/cru/data/hrg/cru_ts_4.10/cruts.2604091129.v4.10/tmn/cru_ts4.10.1901.2025.tmn.dat.nc.gz",
        "cru_ts_410_tmx": "https://crudata.uea.ac.uk/cru/data/hrg/cru_ts_4.10/cruts.2604091129.v4.10/tmx/cru_ts4.10.1901.2025.tmx.dat.nc.gz",
        "cru_ts_410_pet": "https://crudata.uea.ac.uk/cru/data/hrg/cru_ts_4.10/cruts.2604091129.v4.10/pet/cru_ts4.10.1901.2025.pet.dat.nc.gz",
        "cru_ts_410_dtr": "https://crudata.uea.ac.uk/cru/data/hrg/cru_ts_4.10/cruts.2604091129.v4.10/dtr/cru_ts4.10.1901.2025.dtr.dat.nc.gz",
        "cru_ts_410_vap": "https://crudata.uea.ac.uk/cru/data/hrg/cru_ts_4.10/cruts.2604091129.v4.10/vap/cru_ts4.10.1901.2025.vap.dat.nc.gz",
        "cru_ts_410_wet": "https://crudata.uea.ac.uk/cru/data/hrg/cru_ts_4.10/cruts.2604091129.v4.10/wet/cru_ts4.10.1901.2025.wet.dat.nc.gz",
        "cru_ts_410_cld": "https://crudata.uea.ac.uk/cru/data/hrg/cru_ts_4.10/cruts.2604091129.v4.10/cld/cru_ts4.10.1901.2025.cld.dat.nc.gz",
        "cru_ts_410_frs": "https://crudata.uea.ac.uk/cru/data/hrg/cru_ts_4.10/cruts.2604091129.v4.10/frs/cru_ts4.10.1901.2025.frs.dat.nc.gz",
        "ghcnd_all_tar_gz": "https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd_all.tar.gz",
        "ghcnd_by_year_tar_gz": "https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_year.tar.gz",
        "ghcnd_superghcnd": "https://www.ncei.noaa.gov/pub/data/ghcn/daily/superghcnd/",
        "chirps_v3_monthly_nc": "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/netcdf/",
        "grace_jpl_https": "https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-protected/TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4/GRCTellus.JPL.200204_202609.GLO.RL06.3M.MSCNv04CRI.nc",
    }

    results["heads"] = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {}
        for name, url in public_urls.items():
            need = name.startswith("grace")
            futs[ex.submit(head_length, url, need)] = name
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                rec = fut.result()
            except Exception as e:
                rec = {"error": type(e).__name__}
            results["heads"][name] = rec
            print(f"  HEAD {name}: status={rec.get('status')} bytes={rec.get('bytes')} method={rec.get('method')}", flush=True)

    # Directory listings
    print("Directory listings...", flush=True)
    results["listings"] = {}
    listing_urls = {
        "gpcc_v2025_1deg": "https://opendata.dwd.de/climate_environment/GPCC/GPCC_Precipitation_Analysis_Monthly/Version_2025/100_degree/",
        "gpcc_v2025_025deg": "https://opendata.dwd.de/climate_environment/GPCC/GPCC_Precipitation_Analysis_Monthly/Version_2025/025_degree/",
        "gpcc_v2025_05deg": "https://opendata.dwd.de/climate_environment/GPCC/GPCC_Precipitation_Analysis_Monthly/Version_2025/050_degree/",
        "ghcn_daily": "https://www.ncei.noaa.gov/pub/data/ghcn/daily/",
        "giss_gistemp": "https://data.giss.nasa.gov/pub/gistemp/",
        "chirps_v3_monthly_nc": "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/netcdf/",
        "chirps_v3_monthly_cogs": "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/cogs/",
        "gsom_ncei_data": "https://www.ncei.noaa.gov/data/global-summary-of-the-month/access/",
        "gsom_pub": "https://www.ncei.noaa.gov/pub/data/noaa/gsom/",
        "cru_ts_410": "https://crudata.uea.ac.uk/cru/data/hrg/cru_ts_4.10/",
        "cru_cy_410": "https://crudata.uea.ac.uk/cru/data/hrg/cru_ts_4.10/crucy.2606161920.v4.10/countries/",
    }
    for name, url in listing_urls.items():
        rec = list_index_sizes(url)
        # Don't dump huge file lists into the summary print; keep in JSON but cap stored files
        files = rec.get("files") or []
        rec_store = dict(rec)
        if len(files) > 40:
            rec_store["files_head"] = files[:20]
            rec_store["files_tail"] = files[-5:]
            rec_store.pop("files", None)
            rec_store["n_files_with_size"] = sum(1 for f in files if f.get("bytes"))
            rec_store["bytes_sum_listed"] = sum(f["bytes"] or 0 for f in files)
            rec_store["n_files"] = len(files)
        results["listings"][name] = rec_store
        print(f"  LIST {name}: status={rec.get('status')} n={rec.get('n_files')} sum={rec.get('bytes_sum_listed')}", flush=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2, default=str))
    print(f"Wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
