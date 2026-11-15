"""Validate every JSON file the web app reads against the shared contract in schema/.

Run before committing frontend/public/data (synthetic or real):
  python scripts/check_data.py [--data frontend/public/data]

Exit code 1 if any file is invalid. SI-assisted (Claude, Anthropic).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schema"
RULES = [("index.json", "index"), ("catalog.json", "catalog"), ("validation.json", "validation"),
         ("map/*.json", "map"), ("frames/*.json", "frames"), ("analysis/*.json", "analysis"),
         ("compare/*.json", "compare"),
         ("stats/*.json", "climate-output"), ("series/index.json", "series-index")]
SEASON_VIEWS = [""] + [f"__{s}" for s in ("djf", "mam", "jja", "son")]


def main(data: Path) -> int:
    schemas = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in SCHEMA.glob("*.schema.json")}
    registry = Registry().with_resources(
        (name, Resource.from_contents(s)) for name, s in schemas.items())
    bad = checked = 0
    for pattern, name in RULES:
        validator = Draft202012Validator(schemas[f"{name}.schema.json"], registry=registry)
        files = sorted(data.glob(pattern))
        if not files:
            print(f"MISSING {pattern}")
            bad += 1
        for f in files:
            checked += 1
            errors = sorted(validator.iter_errors(json.loads(f.read_text(encoding="utf-8"))), key=str)
            if errors:
                bad += 1
                e = errors[0]
                print(f"INVALID {f.relative_to(data)}: {'/'.join(map(str, e.path))}: {e.message[:200]}")
    # cross-file references: every case points at an existing analysis file
    index = json.loads((data / "index.json").read_text(encoding="utf-8"))
    for c in index["cases"]:
        for rid in [c["region_id"]] + ([c["compare_region_id"]] if "compare_region_id" in c else []):
            if not (data / "analysis" / f"{rid}__{c['variable_id']}.json").exists():
                print(f"BROKEN case {c['id']}: no analysis for {rid}__{c['variable_id']}")
                bad += 1
    # every variable has its map views (ten, or five without a world reference),
    # and every yearly-series binary has the promised size
    for v in index["variables"]:
        for view in SEASON_VIEWS:
            for rel in ("", "__rel"):
                there = (data / "map" / f"{v['id']}{view}{rel}.json").exists()
                wanted = not rel or v["world_reference"]
                if there != wanted:
                    print(f"{'MISSING' if wanted else 'UNEXPECTED'} map/{v['id']}{view}{rel}.json")
                    bad += 1
    for f in sorted((data / "analysis").glob("*.json")):  # no world comparison where there is no reference
        var = f.stem.split("__")[1]
        ref = next(v["world_reference"] for v in index["variables"] if v["id"] == var)
        if (json.loads(f.read_text(encoding="utf-8"))["vs_world"] is not None) != ref:
            print(f"BROKEN analysis/{f.name}: vs_world does not match world_reference of {var}")
            bad += 1
    series = json.loads((data / "series" / "index.json").read_text(encoding="utf-8"))
    cells = series["grid"]["nlat"] * series["grid"]["nlon"]
    for var, views in series["variables"].items():
        for view in views.values():
            f = data / "series" / view["file"]
            want = cells * 8 + (view["last_year"] - view["first_year"] + 1) * cells * 2
            checked += 1
            if not f.exists() or f.stat().st_size != want:
                print(f"BROKEN series/{view['file']}: expected {want} bytes")
                bad += 1
    print(f"checked {checked} files, {bad} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "frontend" / "public" / "data")
    sys.exit(main(ap.parse_args().data))
