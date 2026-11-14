r"""Write data/catalog/regions_ar6.yaml: the IPCC AR6 WGI land reference regions as region presets.

Input: data/catalog/sources/IPCC-WGI-reference-regions-v4_coordinates.csv, the official vertex
list (Iturbide et al., 2020, ESSD 12, 2959, doi:10.5194/essd-12-2959-2020; repository
https://github.com/SantanderMetGroup/ATLAS, CC BY 4.0). The outlines are not changed.

Which regions and how (rule fixed from geometry only, before any trend was computed; ADR-005
amendment):
- every region whose Surface is "Land" or "Land-Ocean" (46 regions; RAR and RAR* are one region
  split at the antimeridian);
- averages use land cells only (``land_only: true``), as in AR6 regional land analyses;
- ``land_fraction`` (information only): area share (cos-latitude weighted) of MERRA-2 cells inside
  the outline that are land in the MERRA-2 land mask (power_zarr.land_mask). AR6 outlines include
  sea on purpose, so a low share is normal for coasts and islands and is not a reason to drop one;
- ``build: false`` for the regions dominated by an ice sheet (GIC, EAN, WAN): the land mask
  excludes ice sheets, so their land-only mean would describe only the ice-free coastal fringe;
  and for any region with fewer than MIN_LAND_CELLS land cells.

Needs network access once (the MERRA-2 land mask from the public POWER archive, no login).

Usage (PowerShell or bash):
    python scripts/make_ar6_regions.py            # writes data/catalog/regions_ar6.yaml
    python scripts/make_ar6_regions.py --check    # exit 1 if the file is out of date

SI-assisted (Claude, Anthropic); pending team review (see docs/08-si-usage-log.md).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from trend_detective.power_zarr import Region, land_mask  # noqa: E402

SOURCE_CSV = ROOT / "data" / "catalog" / "sources" / "IPCC-WGI-reference-regions-v4_coordinates.csv"
OUT = ROOT / "data" / "catalog" / "regions_ar6.yaml"
SURFACES = ("Land", "Land-Ocean")
ICE_SHEET_REGIONS = ("GIC", "EAN", "WAN")
MIN_LAND_CELLS = 20  # MERRA-2 cells (0.5° x 0.625°)
OUTLINE_SOURCE = "IPCC AR6 WGI reference regions v4 (Iturbide et al. 2020, doi:10.5194/essd-12-2959-2020)"

# Plain-language names for students (the CSV names are abbreviations such as "N.W.North-America").
PLAIN_NAMES = {
    "GIC": "Greenland and Iceland",
    "NWN": "North-western North America",
    "NEN": "North-eastern North America",
    "WNA": "Western North America",
    "CNA": "Central North America",
    "ENA": "Eastern North America",
    "NCA": "Northern Central America",
    "SCA": "Southern Central America",
    "CAR": "Caribbean",
    "NWS": "North-western South America",
    "NSA": "Northern South America",
    "NES": "North-eastern South America",
    "SAM": "South American monsoon region",
    "SWS": "South-western South America",
    "SES": "South-eastern South America",
    "SSA": "Southern South America",
    "NEU": "Northern Europe",
    "WCE": "Western and Central Europe",
    "EEU": "Eastern Europe",
    "MED": "Mediterranean",
    "SAH": "Sahara",
    "WAF": "Western Africa",
    "CAF": "Central Africa",
    "NEAF": "North-eastern Africa",
    "SEAF": "South-eastern Africa",
    "WSAF": "Western southern Africa",
    "ESAF": "Eastern southern Africa",
    "MDG": "Madagascar",
    "RAR": "Russian Arctic",
    "WSB": "Western Siberia",
    "ESB": "Eastern Siberia",
    "RFE": "Russian Far East",
    "WCA": "West Central Asia",
    "ECA": "East Central Asia",
    "TIB": "Tibetan Plateau",
    "EAS": "East Asia",
    "ARP": "Arabian Peninsula",
    "SAS": "South Asia",
    "SEA": "South-east Asia",
    "NAU": "Northern Australia",
    "CAU": "Central Australia",
    "EAU": "Eastern Australia",
    "SAU": "Southern Australia",
    "NZ": "New Zealand",
    "EAN": "East Antarctica",
    "WAN": "West Antarctica",
}


def read_regions(path: Path = SOURCE_CSV) -> list[dict]:
    """AR6 land regions from the official CSV, parts with the same acronym (RAR, RAR*) merged."""
    by_acronym: dict[str, dict] = {}
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    for row in rows[1:]:
        if not row or row[1] not in SURFACES:
            continue
        continent, surface, csv_name, acronym = row[:4]
        ring = [[float(a) for a in v.split("|")] for v in row[4:] if v.strip()]
        key = acronym.rstrip("*")
        entry = by_acronym.setdefault(
            key,
            {
                "acronym": key,
                "csv_name": csv_name,
                "continent": continent,
                "surface": surface,
                "polygons": [],
            },
        )
        entry["polygons"].append(ring)
    return list(by_acronym.values())


def land_cells(region: Region) -> tuple[float, int]:
    """(cos(lat)-weighted land share, number of land cells) of MERRA-2 cells inside the outline."""
    mask = land_mask()
    lat, lon = mask.lat.values, mask.lon.values
    inside = region.outline_mask(lat, lon)
    land = inside & mask.values
    w = np.cos(np.deg2rad(lat))[:, None] * np.ones((1, lon.size))
    total = float((w * inside).sum())
    return (float((w * land).sum()) / total if total else 0.0), int(land.sum())


def build_doc(path: Path = SOURCE_CSV) -> dict:
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    entries = []
    for r in read_regions(path):
        acr = r["acronym"]
        name = f"{PLAIN_NAMES[acr]} (IPCC AR6 {acr})"
        reg = Region.from_polygons(name, r["polygons"], OUTLINE_SOURCE)
        frac, n_land = land_cells(reg)
        frac = round(frac, 3)
        reason = None
        if acr in ICE_SHEET_REGIONS:
            reason = (
                "dominated by an ice sheet, which the MERRA-2 land mask excludes: a land-only mean would "
                "describe only the ice-free coastal fringe"
            )
        elif n_land < MIN_LAND_CELLS:
            reason = f"only {n_land} MERRA-2 land cells (minimum {MIN_LAND_CELLS})"
        e = {
            "id": f"ar6_{acr.lower()}",
            "name": name,
            "set": "ar6",
            "acronym": acr,
            "continent": r["continent"],
            "ar6_surface": r["surface"],
            "land_only": True,
            "land_fraction": frac,
            "land_cells_merra2": n_land,
            "build": reason is None,
            "app": False,  # the app's region menu is a viz/team decision
            "polygons": r["polygons"],
        }
        if reason:
            e["note"] = f"Not built: {reason}."
        entries.append(e)
    return {
        "version": 0.1,
        "set": {
            "id": "ar6",
            "title": "IPCC AR6 WGI land reference regions (v4)",
            "source_file": path.relative_to(ROOT).as_posix(),
            "source_sha256": sha,
            "citation": (
                "Iturbide, M. et al. (2020) An update of IPCC climate reference regions for subcontinental "
                "analysis of climate model data. Earth Syst. Sci. Data 12, 2959-2970. "
                "doi:10.5194/essd-12-2959-2020"
            ),
            "repository": "https://github.com/SantanderMetGroup/ATLAS (reference-regions, CC BY 4.0)",
            "rule": (
                "All Land and Land-Ocean regions; land cells only; build: false for the ice-sheet regions "
                f"{', '.join(ICE_SHEET_REGIONS)} and for regions with fewer than {MIN_LAND_CELLS} MERRA-2 "
                "land cells. Fixed from geometry before any trend was computed."
            ),
            "generated_by": "scripts/make_ar6_regions.py",
        },
        "regions": entries,
    }


HEADER = (
    "# GENERATED by scripts/make_ar6_regions.py from the official IPCC AR6 vertex list. Do not edit by\n"
    "# hand: change the script and rerun it. Polygons are rings of [lon, lat] vertices with straight edges.\n"
)


class _FlowLists(yaml.SafeDumper):
    pass


def _represent_list(dumper, data):
    flow = all(isinstance(v, (int, float)) for v in data)  # vertex pairs on one line
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=flow)


_FlowLists.add_representer(list, _represent_list)


def render(doc: dict) -> str:
    return HEADER + yaml.dump(doc, Dumper=_FlowLists, sort_keys=False, width=110, allow_unicode=False)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--check", action="store_true", help="exit 1 if regions_ar6.yaml is out of date")
    args = p.parse_args(argv)
    text = render(build_doc())
    if args.check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("up to date" if same else f"{OUT.relative_to(ROOT)} is out of date; rerun the script")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    doc = yaml.safe_load(text)
    built = [r["acronym"] for r in doc["regions"] if r["build"]]
    skipped = [f"{r['acronym']}: {r['note']}" for r in doc["regions"] if not r["build"]]
    print(f"wrote {OUT.relative_to(ROOT)}: {len(doc['regions'])} regions, {len(built)} to build")
    for line in skipped:
        print("  " + line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
