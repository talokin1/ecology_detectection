"""Build the map basemap and the prepared-region outlines from Natural Earth.

Outputs (both committed, both small):
  frontend/public/basemap/land.geojson       coastlines (land polygons, simplified)
  frontend/public/basemap/countries.geojson  country borders, Ukrainian point of view
  data/regions/regions.geojson               outlines of the prepared regions (shared by stats and viz):
                                             the regions.yaml box, clipped to land when land_only

Country outlines are a visual layer only; region outlines follow data/catalog/regions.yaml.
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

import yaml
from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "naturalearth"
BASEMAP = ROOT / "frontend" / "public" / "basemap"
REGIONS = ROOT / "data" / "regions"
NE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/{}"
FILES = {"countries": "ne_10m_admin_0_countries_ukr.geojson", "land": "ne_50m_land.geojson"}

CATALOG_REGIONS = ROOT / "data" / "catalog" / "regions.yaml"  # read-only here (owned by data)

# Prepared regions the app offers, in display order. Geometry and bbox come from regions.yaml
# (merge plan v2, M3): outline = box(bbox) ∩ Natural Earth land if land_only, else box(bbox), and
# the geojson `bbox` property is the yaml bbox verbatim. `place_type` is a viz-only field.
# Presets in regions.yaml that are not listed here (test presets such as arctic_cap/nw_india,
# named alternates such as ukraine_sa_bbox) or that carry `app: false` are skipped.
APP_REGIONS = {
    "ukraine": "farmland",
    "south_ukraine": "farmland",
    "north_europe": "forest",
    "south_europe": "coast",
    "sahel": "desert",
}
# OPEN USER DECISION: great_plains has no preset in regions.yaml (data/ADR-005). Until the team
# either drops it or adds a preset via an ADR-005 addendum, it keeps its old country-clip outline
# so the app does not lose a region. Its numbers do NOT follow the data pipeline's box.
LEGACY_REGIONS = [
    ("great_plains", "Great Plains (USA)", "farmland",
     {"countries": ["USA"], "clip": (-104.0, 33.0, -94.0, 45.0)}),
]


def load_presets() -> dict[str, dict]:
    doc = yaml.safe_load(CATALOG_REGIONS.read_text(encoding="utf-8"))
    return {r["id"]: r for r in doc["regions"]}


def short_name(name: str) -> str:
    """'Sahel (West and Central Africa)' -> 'Sahel': the map label stays short."""
    return name.split(" (")[0].strip()


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

    def feature(rid, name, place, geom, bbox):
        geom = geom.simplify(0.05, preserve_topology=True)
        if geom.geom_type == "MultiPolygon":  # drop specks (small islands) from the outline
            geom = unary_union([g for g in geom.geoms if g.area > 0.3])
        c = geom.representative_point()
        return {
            "type": "Feature",
            "properties": {"id": rid, "name": name, "place_type": place,
                           "bbox": [float(x) for x in bbox],
                           "centroid": [round(c.x, 2), round(c.y, 2)]},
            "geometry": rounded(geom),
        }

    presets = load_presets()
    for rid, place in APP_REGIONS.items():
        r = presets.get(rid)
        if r is None:
            raise SystemExit(f"region {rid!r} is missing from {CATALOG_REGIONS.relative_to(ROOT)}")
        if r.get("app") is False:
            print(f"skip {rid}: app: false in regions.yaml")
            continue
        w, s_, e, n = r["bbox"]
        if w > e:
            raise SystemExit(f"region {rid!r} crosses the antimeridian; not supported by the map")
        geom = box(w, s_, e, n)
        if r.get("land_only"):
            geom = geom.intersection(land_union)
        region_features.append(feature(rid, short_name(r["name"]), place, geom, r["bbox"]))
    skipped = sorted(set(presets) - set(APP_REGIONS))
    if skipped:
        print(f"not in the app (regions.yaml only): {', '.join(skipped)}")

    for rid, name, place, spec in LEGACY_REGIONS:
        if rid in presets:
            print(f"WARNING {rid} now has a preset in regions.yaml; move it to APP_REGIONS")
            continue
        print(f"WARNING {rid}: no preset in regions.yaml, legacy country-clip outline kept (open decision)")
        geom = unary_union([by_iso[i] for i in spec["countries"]]).intersection(box(*spec["clip"]))
        b = geom.bounds
        region_features.append(feature(rid, name, place, geom, [round(x, 2) for x in b]))
    write(REGIONS / "regions.geojson", region_features)


if __name__ == "__main__":
    main()
