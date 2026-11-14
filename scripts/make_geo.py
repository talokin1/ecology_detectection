"""Build the map basemap and the prepared-region outlines from Natural Earth.

Outputs (both committed, both small):
  frontend/public/basemap/land.geojson       coastlines (land polygons, simplified)
  frontend/public/basemap/countries.geojson  country borders, Ukrainian point of view
  data/regions/regions.geojson               outlines of the prepared regions (shared by stats and viz)

Natural Earth is public domain. The country file is the official "point of view" variant for
Ukraine (ne_10m_admin_0_countries_ukr), so Crimea is drawn as part of Ukraine.

Usage (from the repo root):
  python scripts/make_geo.py            # downloads into data/cache/naturalearth/ if missing

SI-assisted (Claude, Anthropic).
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "naturalearth"
BASEMAP = ROOT / "frontend" / "public" / "basemap"
REGIONS = ROOT / "data" / "regions"
NE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/{}"
FILES = {"countries": "ne_10m_admin_0_countries_ukr.geojson", "land": "ne_50m_land.geojson"}

# Prepared regions: (id, name, place type, how the outline is built)
REGION_SPECS = [
    ("ukraine", "Ukraine", "farmland", {"countries": ["UKR"]}),
    ("south_ukraine", "Southern Ukraine", "farmland",
     {"countries": ["UKR"], "clip": (28.0, 44.0, 40.5, 47.6)}),
    ("north_europe", "Northern Europe", "forest",
     {"countries": ["NOR", "SWE", "FIN", "DNK", "EST", "LVA", "LTU"], "clip": (-10.0, 53.0, 35.0, 71.5)}),
    ("south_europe", "Southern Europe", "coast",
     {"countries": ["ESP", "PRT", "ITA", "GRC"], "clip": (-10.0, 35.0, 30.0, 46.0)}),
    ("sahel", "Sahel", "desert", {"land": True, "clip": (-17.0, 12.0, 38.0, 18.0)}),
    ("great_plains", "Great Plains (USA)", "farmland",
     {"countries": ["USA"], "clip": (-104.0, 33.0, -94.0, 45.0)}),
]


def fetch(name: str) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    if not path.exists():
        print(f"downloading {name}")
        urllib.request.urlretrieve(NE_URL.format(name), path)
    return json.loads(path.read_text(encoding="utf-8"))


def rounded(geom, ndigits: int = 3) -> dict:
    """GeoJSON mapping with coordinates rounded (about 100 m) to keep files small."""
    def r(c):
        if isinstance(c, (list, tuple)) and c and isinstance(c[0], (int, float)):
            return [round(c[0], ndigits), round(c[1], ndigits)]
        return [r(x) for x in c]
    m = mapping(geom)
    return {"type": m["type"], "coordinates": r(m["coordinates"])}


def write(path: Path, features: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fc = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(fc, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size / 1024:.0f} KB)")


def main() -> None:
    countries = fetch(FILES["countries"])
    land = fetch(FILES["land"])

    by_iso: dict[str, object] = {}
    country_features = []
    for f in countries["features"]:
        p = f["properties"]
        iso = p.get("ADM0_A3_UA") or p["ADM0_A3"]
        geom = shape(f["geometry"])
        by_iso[iso] = geom
        simple = geom.simplify(0.07, preserve_topology=True)
        if simple.is_empty or simple.area < 0.02:
            continue
        country_features.append({"type": "Feature", "properties": {"iso": iso, "name": p["NAME"]},
                                 "geometry": rounded(simple, 2)})
    write(BASEMAP / "countries.geojson", country_features)

    land_geoms = [shape(f["geometry"]) for f in land["features"]]
    land_union = unary_union(land_geoms)
    land_features = [{"type": "Feature", "properties": {},
                      "geometry": rounded(g.simplify(0.05, preserve_topology=True), 2)}
                     for g in land_geoms if g.area > 0.05]
    write(BASEMAP / "land.geojson", land_features)

    region_features = []
    for rid, name, place, spec in REGION_SPECS:
        if "countries" in spec:
            geom = unary_union([by_iso[i] for i in spec["countries"]])
        else:
            geom = land_union
        if "clip" in spec:
            geom = geom.intersection(box(*spec["clip"]))
        geom = geom.simplify(0.05, preserve_topology=True)
        if geom.geom_type == "MultiPolygon":  # drop specks (small islands) from the outline
            geom = unary_union([g for g in geom.geoms if g.area > 0.3])
        c = geom.representative_point()
        w, s, e, n = geom.bounds
        region_features.append({
            "type": "Feature",
            "properties": {"id": rid, "name": name, "place_type": place,
                           "bbox": [round(w, 2), round(s, 2), round(e, 2), round(n, 2)],
                           "centroid": [round(c.x, 2), round(c.y, 2)]},
            "geometry": rounded(geom),
        })
    write(REGIONS / "regions.geojson", region_features)


if __name__ == "__main__":
    main()
