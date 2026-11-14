#!/usr/bin/env python3
"""Build app-ready series from the frozen data cache, applying the catalog `convert` field (skeleton).

SI-assisted (GOD / Grok Bot, 2026-11-14), pending team review.

Rules this script enforces:
- Units are converted in ONE place: the `convert` expression of each entry in
  data/catalog/variables.yaml (docs/06-conventions.md:32; merge plan v2 Q1). The cache stays in source
  units (e.g. solar W/m^2); the output is in `display_units` (e.g. MJ/m^2/day via "x * 0.0864").
- Gate MC-4: inputs come only from data/cache/MANIFEST.json. Nothing under team-context/ (the
  stats-archive) is read, so no archive number reaches the UI until it is rebuilt from data/cache and has
  passed the stats-validator subagent.
- Trend statistics are NOT computed here yet; they will come from
  .claude/skills/trend-stats/scripts/trend_stats.py (conservative verdict when MK Yue-Wang and OLS
  disagree). This skeleton writes the converted monthly series only.

Usage: python scripts/build_all.py [--out build/app-series] [--only CATALOG_ID ...] [--dry-run]
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import operator
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "catalog" / "variables.yaml"
CACHE = ROOT / "data" / "cache"
FORBIDDEN = ROOT / "team-context"
# catalog reader -> MANIFEST (source, variable) for readers whose catalog `access` names no store or
# parameter. Must match what each reader writes in its provenance sidecar ("variable" block).
READER_KEY = {
    "grace": ("grace", "lwe_thickness"),
    "modis_ndvi": ("mod13c2", "NDVI"),
    "omi_no2": ("omno2d", "NO2_trop"),
}

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}


def compile_convert(expr: str | None):
    """Compile a catalog `convert` string such as "x * 0.0864" or "x - 273.15" into a function.

    Only the name `x`, numbers, + - * / ** and parentheses are allowed (no eval)."""
    if expr is None or str(expr).strip() == "":
        return lambda x: x
    tree = ast.parse(str(expr), mode="eval")

    def ev(node, x):
        if isinstance(node, ast.Expression):
            return ev(node.body, x)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name) and node.id == "x":
            return x
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.left, x), ev(node.right, x))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand, x))
        raise ValueError(f"unsupported element in convert {expr!r}: {ast.dump(node)[:60]}")

    ev(tree, 1.0)  # validate once
    return lambda x: ev(tree, x)


def load_catalog(path: Path = CATALOG) -> list[dict]:
    import yaml
    return yaml.safe_load(path.read_text())["variables"]


def manifest_key(var: dict) -> tuple[str, str] | None:
    acc = var.get("access") or {}
    reader = acc.get("reader")
    if not reader or reader == "none":
        return None
    if acc.get("store"):  # POWER: store + parameter name
        return acc["store"], acc.get("variable") or var.get("parameter")
    if reader not in READER_KEY:
        raise KeyError(f"build_all: no MANIFEST key for reader {reader!r} ({var['id']}); "
                       "add it to READER_KEY")
    return READER_KEY[reader]


def read_series(path: Path) -> list[tuple[str, float | None]]:
    if FORBIDDEN in path.resolve().parents:
        raise PermissionError(f"MC-4: {path} is in the stats-archive; rebuild from data/cache instead")
    with path.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    tcol = next(c for c in ("month", "date", "time") if c in rows[0]) if rows else "month"
    out = []
    for r in rows:
        v = r.get("value", "")
        out.append((r[tcol], float(v) if v not in ("", "nan", "NaN") else None))
    return out


def build(out_dir: Path, only: set[str] | None = None, dry_run: bool = False) -> list[dict]:
    manifest = json.loads((CACHE / "MANIFEST.json").read_text())
    by_key: dict[tuple[str, str], list[dict]] = {}
    for f in manifest["files"]:
        # Regional CSV series only; map grids (kind "grid", .nc, ADR-006) are not app series.
        if f.get("kind", "series") != "series" or not f["path"].endswith(".csv"):
            continue
        by_key.setdefault((f["source"], f["variable"]), []).append(f)
    built = []
    for var in load_catalog():
        if only and var["id"] not in only:
            continue
        key = manifest_key(var)
        if key is None:
            continue
        if key not in by_key:  # deliverable in the catalog but nothing cached: say so, never skip silently
            print(f"warning: {var['id']} has no cached series in MANIFEST (key {key})", file=sys.stderr)
            continue
        conv = compile_convert(var.get("convert"))
        units = var.get("display_units") or var.get("units")
        for f in by_key[key]:
            series = [(t, None if v is None else conv(v)) for t, v in read_series(CACHE / f["path"])]
            rec = {"variable_id": var["id"], "region_id": f.get("region_id"), "region": f.get("region_name"),
                   "bbox": f.get("bbox"), "land_only": bool(f.get("land_only")),
                   "source_units": var.get("units"), "units": units, "convert": var.get("convert"),
                   "cache_file": f["path"], "cache_sha256": f.get("sha256"),
                   "data": [{"t": t, "v": v} for t, v in series]}
            built.append(rec)
            if not dry_run:
                slug = f.get("region_id") or (f.get("region_name") or "region").lower().replace(" ", "_")
                dest = out_dir / var["id"] / f"{slug}_{Path(f['path']).stem}.json"
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(json.dumps(rec, indent=1))
    return built


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "app-series")
    ap.add_argument("--only", nargs="*", help="catalog ids to build")
    ap.add_argument("--dry-run", action="store_true", help="convert and count, write nothing")
    a = ap.parse_args(argv)
    built = build(a.out, set(a.only) if a.only else None, a.dry_run)
    print(f"{len(built)} series from {len({b['variable_id'] for b in built})} catalog variables"
          f"{' (dry run)' if a.dry_run else f' -> {a.out}'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
