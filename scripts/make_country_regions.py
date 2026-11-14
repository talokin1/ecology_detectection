r"""Generate data/catalog/regions_countries.yaml: the web app's regions as real borders.

The app's prepared regions were latitude/longitude boxes (ADR-005). For the map and the numbers to
show the same area, each European region is redefined as a set of real borders from Natural Earth
1:10m (Ukrainian point of view for admin-0, so Crimea is part of Ukraine):

  ukraine_border          Ukraine (UKR), with Crimea
  south_ukraine_oblasts   Odesa, Mykolaiv, Kherson, Zaporizhzhia oblasts, Autonomous Republic of
                          Crimea and Sevastopol (ISO 3166-2 UA-51, UA-48, UA-65, UA-23, UA-43, UA-40)
  north_europe_countries  Norway, Sweden, Finland, Denmark, Estonia, Latvia, Lithuania; parts north of
                          72°N (Svalbard), west of 0° (Jan Mayen) and south of 50°N (Bouvet) are left out
  south_europe_countries  Portugal, Spain, Italy, Malta, Greece, Slovenia, Croatia, Bosnia and
                          Herzegovina, Montenegro, Albania, North Macedonia, Serbia, Bulgaria (Kosovo is
                          part of Serbia in the Ukrainian-POV admin-0 file);
                          Atlantic islands (west of 10°W) and Ceuta/Melilla (south of 36°N, west of
                          0°) are left out

These membership lists follow the plain-language descriptions already in regions.yaml and were
fixed before any trend was computed for the new outlines. The Sahel stays a box: it is a climate
belt, not a country. Outlines are simplified to 0.02° (about 2 km), far below the 0.5° x 0.625°
MERRA-2 cells the readers select by cell centre.

Usage (repo root; downloads Natural Earth into data/cache/naturalearth/ if missing):
    python scripts/make_country_regions.py

SI-assisted (Claude, Anthropic).
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import yaml
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
NE = ROOT / "data" / "cache" / "naturalearth"
NE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/{}"
ADM0 = "ne_10m_admin_0_countries_ukr.geojson"
ADM1 = "ne_10m_admin_1_states_provinces.geojson"
OUT = ROOT / "data" / "catalog" / "regions_countries.yaml"
TOLERANCE = 0.02
MIN_AREA = 0.002  # deg²; islets this small hold no MERRA-2 cell centre (cells are 0.31 deg²)

REGIONS = [
    {"id": "ukraine_border", "name": "Ukraine", "adm0": ["UKR"], "biomes": ["steppe", "agriculture"],
     "description": "Ukraine within its internationally recognised borders, Crimea included."},
    {"id": "south_ukraine_oblasts", "name": "Southern Ukraine (steppe)",
     "adm1": ["UA-51", "UA-48", "UA-65", "UA-23", "UA-43", "UA-40"], "biomes": ["steppe", "agriculture"],
     "description": "Odesa, Mykolaiv, Kherson and Zaporizhzhia oblasts, Crimea and Sevastopol."},
    {"id": "north_europe_countries", "name": "Northern Europe (Fennoscandia and the Baltic states)",
     "adm0": ["NOR", "SWE", "FIN", "DNK", "EST", "LVA", "LTU"],
     "drop": {"north_of": 72.0, "south_of": 50.0, "west_of": 0.0},
     "biomes": ["boreal", "mountain"],
     "description": ("Norway, Sweden, Finland, Denmark, Estonia, Latvia and Lithuania "
                     "(mainland and coastal islands; Åland is a separate unit and not included).")},
    {"id": "south_europe_countries", "name": "Southern Europe (Mediterranean)",
     "adm0": ["PRT", "ESP", "ITA", "MLT", "GRC", "SVN", "HRV", "BIH", "MNE", "ALB", "MKD", "SRB", "BGR"],
     "drop": {"west_of": -10.0, "africa": True}, "biomes": ["mediterranean", "agriculture"],
     "description": "Portugal, Spain, Italy, Malta, Greece, the western Balkans and Bulgaria."},
]


def load(name: str) -> dict:
    path = NE / name
    if not path.exists():
        NE.mkdir(parents=True, exist_ok=True)
        print(f"downloading {name}")
        urllib.request.urlretrieve(NE_URL.format(name), path)
    return json.loads(path.read_text(encoding="utf-8"))


def parts(geom) -> list[Polygon]:
    return list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]


def keep(p: Polygon, drop: dict) -> bool:
    pt = p.representative_point()
    if "north_of" in drop and pt.y > drop["north_of"]:
        return False
    if "south_of" in drop and pt.y < drop["south_of"]:
        return False
    if "west_of" in drop and pt.x < drop["west_of"]:
        return False
    if drop.get("africa") and pt.y < 36.0 and pt.x < 0.0:
        return False
    return True


def rings(geom) -> list[list[list[float]]]:
    out = []
    for p in parts(geom):
        for ring in [p.exterior, *p.interiors]:
            out.append([[round(x, 3), round(y, 3)] for x, y in ring.coords])
    return out


def main() -> None:
    adm0 = load(ADM0)["features"]
    adm1 = load(ADM1)["features"]
    by_a3 = {}
    for f in adm0:
        p = f["properties"]
        by_a3[p.get("ADM0_A3_UA") or p["ADM0_A3"]] = shape(f["geometry"])
    by_iso2 = {f["properties"].get("iso_3166_2"): shape(f["geometry"]) for f in adm1}

    regions = []
    for spec in REGIONS:
        if "adm0" in spec:
            missing = [a for a in spec["adm0"] if a not in by_a3]
            if missing:
                raise SystemExit(f"{spec['id']}: not in {ADM0}: {missing}")
            geom = unary_union([by_a3[a] for a in spec["adm0"]])
        else:
            missing = [c for c in spec["adm1"] if c not in by_iso2]
            if missing:
                raise SystemExit(f"{spec['id']}: not in {ADM1}: {missing}")
            geom = unary_union([by_iso2[c] for c in spec["adm1"]])
        drop = spec.get("drop", {})
        geom = unary_union([p for p in parts(geom) if keep(p, drop) and p.area > MIN_AREA])
        geom = geom.buffer(0).simplify(TOLERANCE, preserve_topology=True)
        w, s, e, n = geom.bounds
        print(f"{spec['id']}: {len(parts(geom))} parts, bounds {w:.2f} {s:.2f} {e:.2f} {n:.2f}")
        regions.append({
            "id": spec["id"], "name": spec["name"], "set": "countries", "land_only": True,
            "biomes": spec["biomes"], "description": spec["description"],
            "members": spec.get("adm0") or spec.get("adm1"),
            "polygons": rings(geom),
        })

    doc = {
        "version": 0.1,
        "set": {
            "id": "countries",
            "title": "Natural Earth 1:10m borders (admin-0 Ukrainian point of view; admin-1 for oblasts)",
            "source": ("https://www.naturalearthdata.com/ (public domain), "
                       "via github.com/nvkelso/natural-earth-vector"),
            "rule": ("Web-app regions as real borders; membership from the regions.yaml descriptions, fixed "
                     "before any trend was computed for these outlines; land cells only; MERRA-2 cells "
                     "selected by centre inside the outline. See scripts/make_country_regions.py."),
            "generated_by": "scripts/make_country_regions.py",
        },
        "regions": regions,
    }
    header = ("# GENERATED by scripts/make_country_regions.py from Natural Earth. Do not edit by hand:\n"
              "# change the script and rerun it. Polygons are rings of [lon, lat]; holes are extra\n"
              "# rings (even-odd).\n")
    OUT.write_text(header + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=110,
                                           default_flow_style=None), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
