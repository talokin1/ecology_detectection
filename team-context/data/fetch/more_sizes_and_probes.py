#!/usr/bin/env python3
"""Extra public listings, CHIRPS/CCI/SWOT sizes, POWER scale-up,
and one-month DAP4 slim-subset probes. Never prints credentials.
"""
from __future__ import annotations

import json
import os
import re
import ssl
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

from locate import FETCH_DIR, UKRAINE_SAMPLES

OUT = FETCH_DIR / "size_measurements_extra.json"
PROBE_DIR = Path("/tmp/slim_probes")
PROBE_DIR.mkdir(parents=True, exist_ok=True)
UA = "SpaceAppsTrendDetective/1.0"
CTX = ssl.create_default_context()


def log(msg):
    print(msg, flush=True)


def token():
    return os.environ.get("EARTHDATA_TOKEN") or ""


def urlopen(url, headers=None, timeout=180, method="GET"):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h, method=method)
    return urllib.request.urlopen(req, timeout=timeout, context=CTX)


def get_text(url, timeout=90):
    with urlopen(url, timeout=timeout) as r:
        return r.status, r.read(), {k.lower(): v for k, v in r.headers.items()}


def head_or_range_bytes(url, need_auth=False, timeout=90):
    headers = {"User-Agent": UA}
    if need_auth:
        headers["Authorization"] = f"Bearer {token()}"
    # HEAD first
    try:
        req = urllib.request.Request(url, headers=headers, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            cl = r.headers.get("Content-Length")
            if cl and cl.isdigit() and int(cl) > 0:
                return {"url": url, "status": r.status, "bytes": int(cl), "method": "head"}
    except Exception as e:
        head_err = type(e).__name__
    else:
        head_err = None
    headers2 = dict(headers)
    headers2["Range"] = "bytes=0-0"
    try:
        req = urllib.request.Request(url, headers=headers2, method="GET")
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            cr = r.headers.get("Content-Range") or ""
            m = re.search(r"/(\d+)$", cr)
            if m:
                return {"url": url, "status": r.status, "bytes": int(m.group(1)), "method": "range"}
            cl = r.headers.get("Content-Length")
            if cl and cl.isdigit():
                return {"url": url, "status": r.status, "bytes": int(cl), "method": "get"}
    except urllib.error.HTTPError as e:
        cr = e.headers.get("Content-Range") or ""
        m = re.search(r"/(\d+)$", cr)
        if m:
            return {"url": url, "status": e.code, "bytes": int(m.group(1)), "method": "range"}
        return {"url": url, "status": e.code, "bytes": None, "error": "HTTPError"}
    except Exception as e:
        return {"url": url, "status": 0, "bytes": None, "error": type(e).__name__, "head_err": head_err}
    return {"url": url, "status": 0, "bytes": None, "error": "no_length", "head_err": head_err}


def parse_pre_listing(url):
    status, body, _ = get_text(url)
    text = body.decode("utf-8", "replace")
    files = []
    # nginx/apache pre: href="file" ... date  SIZE
    for m in re.finditer(r'<a href="([^"]+)">([^<]+)</a>\s+([0-9A-Za-z:\- ]+?)\s+([0-9]+)\s*', text):
        href, name, date, sz = m.group(1), m.group(2), m.group(3).strip(), int(m.group(4))
        if href.endswith("/") or href in ("../",):
            continue
        files.append({"href": href, "name": href, "date": date, "bytes": sz})
    if not files:
        # table: href, date, size
        for m in re.finditer(
            r'<a href="([^"]+)">([^<]+)</a></td>\s*<td[^>]*>\s*([^<]*)</td>\s*<td[^>]*>\s*([0-9.]+(?:\s*[KMGT]i?B)?|[0-9]+|-)\s*<',
            text, re.I,
        ):
            href, name, date, sz = m.groups()
            if href.endswith("/"):
                continue
            files.append({"href": href, "name": href, "date": date.strip(), "bytes": parse_human(sz), "size_raw": sz.strip()})
    if not files:
        # CHIRPS style: class="size">8.3 GiB
        for m in re.finditer(
            r'<a href="([^"]+)"[^>]*>([^<]+)</a>.*?<td class="size">\s*([^<]+)\s*</td>.*?<td class="date">\s*([^<]+)\s*</td>',
            text, re.S | re.I,
        ):
            href, name, sz, date = m.groups()
            if href.endswith("/"):
                continue
            files.append({"href": href, "name": href, "date": date.strip(), "bytes": parse_human(sz), "size_raw": sz.strip()})
    return {"url": url, "status": status, "n": len(files), "bytes_sum": sum(f["bytes"] or 0 for f in files), "files": files}


def parse_human(s):
    s = (s or "").strip().replace(",", "")
    if not s or s == "-":
        return None
    m = re.match(r"^([0-9.]+)\s*([KMGT])i?B?$", s, re.I)
    if m:
        val = float(m.group(1))
        unit = m.group(2).upper()
        # GiB vs GB: if original had 'i' use 1024, else still 1024 for listing "8.3 GiB"
        mult = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}[unit]
        return int(val * mult)
    if re.fullmatch(r"[0-9]+", s):
        return int(s)
    return None


def cmr_granules(concept_id, page_size=200, pages=2):
    sizes = []
    names = []
    hits = None
    for page in range(1, pages + 1):
        q = urllib.parse.urlencode({
            "collection_concept_id": concept_id,
            "page_size": str(page_size),
            "page_num": str(page),
        })
        url = "https://cmr.earthdata.nasa.gov/search/granules.umm_json?" + q
        status, body, hdrs = get_text(url, timeout=120)
        hits = int(hdrs.get("cmr-hits") or 0)
        data = json.loads(body)
        for item in data.get("items", []):
            umm = item.get("umm", {})
            names.append(umm.get("GranuleUR"))
            info = (umm.get("DataGranule") or {}).get("ArchiveAndDistributionInformation") or []
            gbytes = 0
            got = False
            for d in info:
                if d.get("SizeInBytes"):
                    gbytes += d["SizeInBytes"]
                    got = True
                elif d.get("Size") is not None:
                    unit = (d.get("SizeUnit") or "MB").upper()
                    val = float(d["Size"])
                    factor = {"KB": 1e3, "KBYTE": 1e3, "KBYTES": 1e3,
                              "MB": 1e6, "MBYTE": 1e6, "MBYTES": 1e6,
                              "GB": 1e9, "GBYTE": 1e9, "GBYTES": 1e9,
                              "B": 1, "BYTE": 1, "BYTES": 1}.get(unit, 1e6)
                    gbytes += int(val * factor)
                    got = True
            if got:
                sizes.append(gbytes)
        if page * page_size >= (hits or 0):
            break
    n = len(sizes)
    mean = sum(sizes) / n if n else None
    return {
        "concept_id": concept_id, "hits": hits, "sample_n": n,
        "mean": mean, "median": sorted(sizes)[n//2] if n else None,
        "min": min(sizes) if sizes else None, "max": max(sizes) if sizes else None,
        "total_est": int(mean * hits) if mean and hits else None,
        "names_head": names[:3],
    }


def dap4_download(concept_id, short, version, producer, ce, dest, timeout=300):
    gran = f"{short}.{version}:{producer}"
    base = f"https://opendap.earthdata.nasa.gov/collections/{concept_id}/granules/{urllib.parse.quote(gran, safe='')}.dap.nc4"
    url = base + "?" + urllib.parse.urlencode({"dap4.ce": ce})
    headers = {"User-Agent": UA, "Authorization": f"Bearer {token()}"}
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r, open(dest, "wb") as f:
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
            status = r.status
        sz = dest.stat().st_size
        return {"ok": True, "status": status, "bytes": sz, "seconds": round(time.time()-t0, 2),
                "dest": str(dest), "producer": producer}
    except Exception as e:
        # don't include URL (has no token) but also don't include headers
        err_body = ""
        if isinstance(e, urllib.error.HTTPError):
            try:
                err_body = e.read()[:300].decode("utf-8", "replace")
            except Exception:
                err_body = ""
            return {"ok": False, "status": e.code, "error": "HTTPError",
                    "body_head": err_body, "seconds": round(time.time()-t0, 2), "producer": producer}
        return {"ok": False, "error": type(e).__name__, "seconds": round(time.time()-t0, 2), "producer": producer}


def power_scale():
    root = UKRAINE_SAMPLES / "nasa_power"
    files = sorted(root.glob("POWER_monthly_*.csv"))
    recs = []
    total = 0
    lats = set(); lons = set(); cells = set()
    solar_bytes = 0
    met_bytes = 0
    # count cells from T2M west+east
    for p in files:
        sz = p.stat().st_size
        total += sz
        recs.append({"name": p.name, "bytes": sz})
        if "ALLSKY" in p.name:
            solar_bytes += sz
        else:
            met_bytes += sz
        if "T2M_west" in p.name or "T2M_east" in p.name:
            # skip header, parse LAT,LON
            with p.open() as f:
                in_body = False
                for line in f:
                    if line.startswith("PARAMETER,"):
                        in_body = True
                        continue
                    if not in_body:
                        continue
                    parts = line.strip().split(",")
                    if len(parts) < 4:
                        continue
                    # PARAMETER,YEAR,LAT,LON,...
                    if parts[0] != "T2M":
                        continue
                    lat, lon = float(parts[2]), float(parts[3])
                    cells.add((lat, lon))
                    lats.add(lat); lons.add(lon)
    n_cells = len(cells)
    # MERRA-2 monthly grid: 0.5 lat x 0.625 lon, 361 x 576
    merra_cells = 361 * 576
    # CERES 1 deg: 180 x 360 (or 181 x 360?). POWER solar was 144 cells in bbox.
    ceres_cells = 180 * 360
    # count solar cells
    solar_cells = set()
    for p in files:
        if "ALLSKY" not in p.name:
            continue
        with p.open() as f:
            in_body = False
            for line in f:
                if line.startswith("PARAMETER,"):
                    in_body = True
                    continue
                if not in_body:
                    continue
                parts = line.strip().split(",")
                if len(parts) < 4:
                    continue
                solar_cells.add((float(parts[2]), float(parts[3])))
    n_solar = len(solar_cells)
    # 6 meteorology parameters (T2M, T2M_MAX, T2M_MIN, QV2M, PRECTOTCORR, WS10M)
    # scale each group's bytes by cell ratio
    met_global = met_bytes * (merra_cells / n_cells) if n_cells else None
    solar_global = solar_bytes * (ceres_cells / n_solar) if n_solar else None
    return {
        "local_total_bytes": total,
        "files": recs,
        "met_local_bytes": met_bytes,
        "solar_local_bytes": solar_bytes,
        "ukraine_met_cells": n_cells,
        "ukraine_met_nlats": len(lats),
        "ukraine_met_nlons": len(lons),
        "ukraine_solar_cells": n_solar,
        "merra_global_cells": merra_cells,
        "ceres_global_cells": ceres_cells,
        "slim_csv_global_bytes_est": (met_global or 0) + (solar_global or 0),
        "met_global_bytes_est": met_global,
        "solar_global_bytes_est": solar_global,
        "params_used": 7,
        "note": "Scale-up of the on-disk POWER CSVs (same layout, 7 parameters) by official grid cell counts.",
    }


def main():
    results = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S%z")}

    log("Listings...")
    results["listings"] = {}
    for name, url in {
        "gpcc_v2025_1deg": "https://opendata.dwd.de/climate_environment/GPCC/GPCC_Precipitation_Analysis_Monthly/Version_2025/100_degree/",
        "gpcc_v2025_05deg": "https://opendata.dwd.de/climate_environment/GPCC/GPCC_Precipitation_Analysis_Monthly/Version_2025/050_degree/",
        "gpcc_v2025_025deg": "https://opendata.dwd.de/climate_environment/GPCC/GPCC_Precipitation_Analysis_Monthly/Version_2025/025_degree/",
        "gpcc_v2025_25deg": "https://opendata.dwd.de/climate_environment/GPCC/GPCC_Precipitation_Analysis_Monthly/Version_2025/250_degree/",
        "ghcn_daily": "https://www.ncei.noaa.gov/pub/data/ghcn/daily/",
        "gsom_archive": "https://www.ncei.noaa.gov/data/global-summary-of-the-month/archive/",
        "chirps_v3_nc_dir": "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/netcdf/",
        "chirps_v3_cogs_dir": "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/cogs/",
        "giss_gistemp": "https://data.giss.nasa.gov/pub/gistemp/",
        "ghcnm_v4": "https://www.ncei.noaa.gov/pub/data/ghcn/v4/",
    }.items():
        try:
            rec = parse_pre_listing(url)
            # cap files stored
            store = dict(rec)
            if len(rec["files"]) > 30:
                store["files_head"] = rec["files"][:8]
                store["files_tail"] = rec["files"][-4:]
                store.pop("files")
            results["listings"][name] = store
            log(f"  {name}: n={rec['n']} sum={rec['bytes_sum']}")
        except Exception as e:
            results["listings"][name] = {"url": url, "error": type(e).__name__}
            log(f"  {name}: FAIL {type(e).__name__}: {e}")

    log("HEAD specific files...")
    results["heads"] = {}
    for name, url, auth in [
        ("chirps_v3_monthly_nc", "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/netcdf/chirps-v3.0.monthly.nc", False),
        ("chirps_v3_cog_sample", "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/cogs/chirps-v3.0.1981.01.cog", False),
        ("gsom_latest_tar_gz", "https://www.ncei.noaa.gov/data/global-summary-of-the-month/archive/gsom-latest.tar.gz", False),
        ("ghcnd_all_tar_gz", "https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd_all.tar.gz", False),
        ("cci_sm_sample_19781101", "https://dap.ceda.ac.uk/neodc/esacci/soil_moisture/data/daily_files/COMBINED/v09.2/1978/ESACCI-SOILMOISTURE-L3S-SSMV-COMBINED-19781101000000-fv09.2.nc", False),
        ("cci_sm_sample_20000101", "https://dap.ceda.ac.uk/neodc/esacci/soil_moisture/data/daily_files/COMBINED/v09.2/2000/ESACCI-SOILMOISTURE-L3S-SSMV-COMBINED-20000101000000-fv09.2.nc", False),
        ("cci_sm_sample_20241231", "https://dap.ceda.ac.uk/neodc/esacci/soil_moisture/data/daily_files/COMBINED/v09.2/2024/ESACCI-SOILMOISTURE-L3S-SSMV-COMBINED-20241231000000-fv09.2.nc", False),
    ]:
        rec = head_or_range_bytes(url, need_auth=auth)
        results["heads"][name] = rec
        log(f"  {name}: {rec}")

    log("CMR SWOT reach-only and node-only Version D...")
    results["cmr_extra"] = {
        "swot_riversp_reach_D": cmr_granules("C3233942283-POCLOUD", 200, 2),
        "swot_riversp_node_D": cmr_granules("C3233942282-POCLOUD", 200, 2),
        "swot_riversp_D_all": cmr_granules("C3233944997-POCLOUD", 200, 1),  # already have, refresh
    }
    for k, v in results["cmr_extra"].items():
        log(f"  {k}: hits={v.get('hits')} mean={v.get('mean')} total={v.get('total_est')}")

    log("POWER scale-up...")
    results["power"] = power_scale()
    log(f"  cells={results['power']['ukraine_met_cells']} slim_est={results['power']['slim_csv_global_bytes_est']}")

    # DAP4 slim probes (one month each, full global, used variables only)
    log("DAP4 slim probes...")
    results["slim_probes"] = {}
    probes = [
        dict(key="merra2_slv", concept_id="C1276812859-GES_DISC", short="M2TMNXSLV", version="5.12.4",
             producer="MERRA2_100.tavgM_2d_slv_Nx.198001.nc4",
             ce="/T2M;/QV2M;/SLP;/lat;/lon;/time",
             native_get="https://data.gesdisc.earthdata.nasa.gov/data/MERRA2_MONTHLY/M2TMNXSLV.5.12.4/1980/MERRA2_100.tavgM_2d_slv_Nx.198001.nc4"),
        dict(key="merra2_flx", concept_id="C1276812868-GES_DISC", short="M2TMNXFLX", version="5.12.4",
             producer="MERRA2_100.tavgM_2d_flx_Nx.198001.nc4",
             ce="/PRECTOT;/PRECTOTCORR;/lat;/lon;/time",
             native_get="https://data.gesdisc.earthdata.nasa.gov/data/MERRA2_MONTHLY/M2TMNXFLX.5.12.4/1980/MERRA2_100.tavgM_2d_flx_Nx.198001.nc4"),
        dict(key="gldas21", concept_id="C1342986036-GES_DISC", short="GLDAS_NOAH025_M", version="2.1",
             producer="GLDAS_NOAH025_M.A200001.021.nc4",
             ce="/SoilMoi0_10cm_inst;/RootMoist_inst;/Evap_tavg;/Qs_acc;/Qsb_acc;/SWE_inst;/Tair_f_inst;/lat;/lon;/time",
             native_get="https://data.gesdisc.earthdata.nasa.gov/data/GLDAS/GLDAS_NOAH025_M.2.1/2000/GLDAS_NOAH025_M.A200001.021.nc4"),
        dict(key="gldas20", concept_id="C1233767569-GES_DISC", short="GLDAS_NOAH025_M", version="2.0",
             producer="GLDAS_NOAH025_M.A194801.020.nc4",
             ce="/SoilMoi0_10cm_inst;/RootMoist_inst;/Evap_tavg;/Qs_acc;/Qsb_acc;/SWE_inst;/Tair_f_inst;/lat;/lon;/time",
             native_get="https://data.gesdisc.earthdata.nasa.gov/data/GLDAS/GLDAS_NOAH025_M.2.0/1948/GLDAS_NOAH025_M.A194801.020.nc4"),
        dict(key="imerg", concept_id="C2723754851-GES_DISC", short="GPM_3IMERGM", version="07",
             producer="3B-MO.MS.MRG.3IMERG.20000601-S000000-E235959.06.V07B.HDF5",
             ce="/Grid/precipitation;/Grid/lon;/Grid/lat;/Grid/time",
             native_get="https://data.gesdisc.earthdata.nasa.gov/data/GPM_L3/GPM_3IMERGM.07/2000/3B-MO.MS.MRG.3IMERG.20000601-S000000-E235959.06.V07B.HDF5"),
        dict(key="airs", concept_id="C1701805662-GES_DISC", short="AIRS3STM", version="7.0",
             producer="AIRS.2002.09.01.L3.RetStd_IR030.v7.0.3.0.G20175163230.hdf",
             ce=("/ascending/Data_Fields/SurfAirTemp_A;/ascending/Data_Fields/TotH2OVap_A;"
                 "/descending/Data_Fields/SurfAirTemp_D;/descending/Data_Fields/TotH2OVap_D;"
                 "/location/Data_Fields/Latitude;/location/Data_Fields/Longitude"),
             native_get="https://data.gesdisc.earthdata.nasa.gov/data/Aqua_AIRS_Level3/AIRS3STM.7.0/2002/AIRS.2002.09.01.L3.RetStd_IR030.v7.0.3.0.G20175163230.hdf"),
        dict(key="mod13c2", concept_id="C2565788914-LPCLOUD", short="MOD13C2", version="061",
             producer="MOD13C2.A2000032.061.2020042083108",
             ce=("/MOD_Grid_monthly_CMG_VI/Data_Fields/CMG_0_05_Deg_Monthly_NDVI;"
                 "/MOD_Grid_monthly_CMG_VI/Data_Fields/CMG_0_05_Deg_Monthly_EVI"),
             native_get="https://data.lpdaac.earthdatacloud.nasa.gov/lp-prod-protected/MOD13C2.061/MOD13C2.A2000032.061.2020042083108/MOD13C2.A2000032.061.2020042083108.hdf"),
        dict(key="mod11c3", concept_id="C2565788897-LPCLOUD", short="MOD11C3", version="061",
             producer="MOD11C3.A2000032.061.2020048181639",
             ce=("/MODIS_MONTHLY_0_05DEG_CMG_LST/Data_Fields/LST_Day_CMG;"
                 "/MODIS_MONTHLY_0_05DEG_CMG_LST/Data_Fields/LST_Night_CMG"),
             native_get="https://data.lpdaac.earthdatacloud.nasa.gov/lp-prod-protected/MOD11C3.061/MOD11C3.A2000032.061.2020048181639/MOD11C3.A2000032.061.2020048181639.hdf"),
    ]
    for p in probes:
        log(f"  probe {p['key']} ...")
        dest = PROBE_DIR / f"{p['key']}_slim_month.nc4"
        rec = dap4_download(p["concept_id"], p["short"], p["version"], p["producer"], p["ce"], dest)
        # native size from earlier CMR / a quick HEAD
        native = head_or_range_bytes(p["native_get"], need_auth=True)
        rec["native_head"] = native
        results["slim_probes"][p["key"]] = rec
        log(f"    slim={rec} native={native.get('bytes')}")

    # CCI day count * mean size
    # 1978-11-01 to 2024-12-31 inclusive
    import datetime
    d0 = datetime.date(1978, 11, 1)
    d1 = datetime.date(2024, 12, 31)
    ndays = (d1 - d0).days + 1
    sample_sizes = [results["heads"][k].get("bytes") for k in
                    ("cci_sm_sample_19781101", "cci_sm_sample_20000101", "cci_sm_sample_20241231")
                    if results["heads"].get(k, {}).get("bytes")]
    mean = sum(sample_sizes) / len(sample_sizes) if sample_sizes else 1.55 * 1e6
    results["cci_sm"] = {
        "ndays": ndays, "sample_bytes": sample_sizes,
        "mean_sample_bytes": mean, "total_est_bytes": int(mean * ndays),
        "period": "1978-11-01 to 2024-12-31", "version": "v09.2 COMBINED daily",
    }
    log(f"CCI SM days={ndays} mean={mean} total={results['cci_sm']['total_est_bytes']}")

    OUT.write_text(json.dumps(results, indent=2, default=str))
    log(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
