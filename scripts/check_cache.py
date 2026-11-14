r"""Check that the frozen data cache is complete, unchanged and documented (data freeze gate).

Offline: no network and no token needed, so it runs in CI on every push. Checks:
1. MANIFEST.json lists exactly the series and grids on disk, with matching size and sha256
   (catches a refetch or a hand edit that was not followed by a manifest rebuild).
2. Every listed file has a provenance sidecar with the required fields, and every sidecar
   belongs to a data file.
3. No sidecar or manifest contains anything that looks like a credential.
4. Every POWER job in data/catalog/build.yaml has its cached series (the app never fetches live).
5. data/catalog/regions_ar6.yaml still matches the vendored official AR6 vertex list.
6. No file tracked by git is over 50 MB (CLAUDE.md), and raw downloads are not tracked.

Exit code 1 if any check fails. Rebuild the manifest with ``python scripts/build_data.py
--manifest-only`` after a deliberate data refresh.

Usage (PowerShell or bash):
    python scripts/check_cache.py
    python scripts/check_cache.py --cache-dir D:\nasa-cache

SI-assisted (Claude, Anthropic); pending team review (see docs/08-si-usage-log.md).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]

import build_data  # noqa: E402
import make_ar6_regions  # noqa: E402
import yaml  # noqa: E402

REQUIRED_SIDECAR = ("source", "variable", "accessed", "processing", "script")
# Intermediates documented by another file's sidecar: OMI NO2 daily box means are described by the
# monthly series' sidecar (omi_no2.py docstring); one must exist next to them.
INTERMEDIATES = {"omno2d_daily_": "omno2d_"}
MAX_TRACKED_BYTES = 50 * 1024 * 1024
# Credential patterns: JWT (Earthdata tokens are JWTs), bearer headers, .netrc lines, key names.
SECRET_PATTERNS = [
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(r"(?i)bearer\s+[a-z0-9._-]{20,}"),
    re.compile(r"(?i)machine\s+urs\.earthdata\.nasa\.gov"),
    re.compile(r"(?i)EARTHDATA_(TOKEN|PASSWORD)\s*[=:]"),
]


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def check(self, name: str, problems: list[str]) -> None:
        if problems:
            self.failures += [f"{name}: {p}" for p in problems]
            print(f"FAIL {name} ({len(problems)})")
            for p in problems[:20]:
                print(f"     {p}")
            if len(problems) > 20:
                print(f"     ... and {len(problems) - 20} more")
        else:
            print(f"ok   {name}")


def data_files(cache_root: Path) -> list[Path]:
    """The files the manifest must list (same rule as build_data.build_manifest)."""
    return sorted(
        p
        for d in build_data.MANIFEST_DIRS
        if (cache_root / d).is_dir()
        for p in (cache_root / d).rglob("*")
        if p.is_file()
        and p.suffix in (".csv", *build_data.GRID_SUFFIXES)
        and not p.name.endswith(".partial.csv")
    )


def check_manifest(cache_root: Path) -> list[str]:
    path = cache_root / build_data.MANIFEST_NAME
    if not path.exists():
        return [f"{path} is missing"]
    manifest = json.loads(path.read_text(encoding="utf-8"))
    listed = {e["path"]: e for e in manifest["files"]}
    on_disk = {p.relative_to(cache_root).as_posix(): p for p in data_files(cache_root)}
    problems = [f"on disk but not in MANIFEST: {p}" for p in sorted(set(on_disk) - set(listed))]
    problems += [f"in MANIFEST but missing on disk: {p}" for p in sorted(set(listed) - set(on_disk))]
    for rel in sorted(set(on_disk) & set(listed)):
        e, p = listed[rel], on_disk[rel]
        if p.stat().st_size != e["bytes"]:
            problems.append(f"size changed: {rel} ({e['bytes']} -> {p.stat().st_size} bytes)")
        elif build_data._sha256(p) != e["sha256"]:
            problems.append(f"content changed: {rel} (sha256 differs from MANIFEST)")
    if manifest.get("n_files") != len(manifest["files"]):
        problems.append("n_files does not match the number of entries")
    return problems


def check_sidecars(cache_root: Path) -> list[str]:
    problems = []
    files = data_files(cache_root)
    for p in files:
        side = p.with_name(p.name + ".provenance.json")
        parent = next((v for k, v in INTERMEDIATES.items() if p.name.startswith(k)), None)
        if parent and not side.exists():
            documented = [
                s
                for s in p.parent.glob(f"{parent}*.csv.provenance.json")
                if not s.name.startswith(p.name[:13])
            ]
            if not documented:
                problems.append(
                    f"intermediate without its monthly sidecar: {p.relative_to(cache_root).as_posix()}"
                )
            continue
        if not side.exists():
            problems.append(f"no provenance sidecar: {p.relative_to(cache_root).as_posix()}")
            continue
        try:
            prov = json.loads(side.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"sidecar is not JSON: {side.name} ({exc})")
            continue
        missing = [k for k in REQUIRED_SIDECAR if not prov.get(k)]
        if missing:
            problems.append(f"{side.relative_to(cache_root).as_posix()} lacks {', '.join(missing)}")
    names = {p.name for p in files}
    for d in build_data.MANIFEST_DIRS:
        for side in (cache_root / d).rglob("*.provenance.json") if (cache_root / d).is_dir() else []:
            data_name = side.name[: -len(".provenance.json")]
            if data_name not in names and not data_name.endswith(".partial.csv"):
                problems.append(f"orphan sidecar (no data file): {side.relative_to(cache_root).as_posix()}")
    return problems


def check_secrets(cache_root: Path) -> list[str]:
    problems = []
    candidates = [cache_root / build_data.MANIFEST_NAME]
    for d in build_data.MANIFEST_DIRS:
        if (cache_root / d).is_dir():
            candidates += sorted((cache_root / d).rglob("*.provenance.json"))
    for f in candidates:
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        for pat in SECRET_PATTERNS:
            if pat.search(text):
                problems.append(
                    f"possible credential in {f.relative_to(cache_root).as_posix()} ({pat.pattern[:24]}...)"
                )
    return problems


def check_build_jobs() -> list[str]:
    """Every POWER job of the job list is cached (Earthdata jobs may be absent: login needed)."""
    from trend_detective import acquire

    spec = build_data.load_jobs(build_data.DEFAULT_JOBS)
    catalog = acquire.list_variables()
    problems = []
    for job in build_data.expand_jobs(spec):
        if job.excluded or job.needs_login:
            continue
        ocean = job.kind == "variable" and catalog[job.name].entry.get("surface") == "ocean"
        if ocean and acquire._preset_land_only(job.region, None):
            continue  # refused by design: an ocean variable over a land-only region (ADR-005)
        if not build_data._power_cache_path(job).exists():
            problems.append(f"not cached: {job.region} {job.name}")
    return problems


def check_ar6() -> list[str]:
    """Generated region file matches the vendored CSV (no network: land fractions not recomputed)."""
    doc = yaml.safe_load(make_ar6_regions.OUT.read_text(encoding="utf-8"))
    problems = []
    sha = __import__("hashlib").sha256(make_ar6_regions.SOURCE_CSV.read_bytes()).hexdigest()
    if doc["set"]["source_sha256"] != sha:
        problems.append(
            "vendored AR6 CSV changed since regions_ar6.yaml was generated; rerun make_ar6_regions.py"
        )
    want = {r["acronym"]: r["polygons"] for r in make_ar6_regions.read_regions()}
    have = {r["acronym"]: r["polygons"] for r in doc["regions"]}
    if set(want) != set(have):
        problems.append(f"region list differs from the CSV: {sorted(set(want) ^ set(have))}")
    problems += [
        f"{a}: outline differs from the official vertices" for a in sorted(want) if have.get(a) != want[a]
    ]
    return problems


def check_git_sizes() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True, timeout=30
        ).stdout.decode()
    except (OSError, subprocess.SubprocessError):
        return []  # not a git checkout (e.g. an unpacked archive): nothing to check
    problems = []
    for rel in filter(None, out.split("\0")):
        p = ROOT / rel
        if rel.startswith("data/cache/raw/"):
            problems.append(f"raw download tracked by git: {rel}")
        elif p.is_file() and p.stat().st_size > MAX_TRACKED_BYTES:
            problems.append(f"tracked file over 50 MB: {rel} ({p.stat().st_size / 1e6:.0f} MB)")
        if Path(rel).name in (".env", ".netrc", "_netrc"):
            problems.append(f"secret file tracked by git: {rel}")
    return problems


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument(
        "--cache-dir", type=Path, default=None, help="cache root (default: $CACHE_DIR or data/cache)"
    )
    args = p.parse_args(argv)
    cache_root = args.cache_dir or build_data.default_cache_root()
    r = Report()
    r.check("manifest matches files", check_manifest(cache_root))
    r.check("provenance sidecars", check_sidecars(cache_root))
    r.check("no credentials in cache metadata", check_secrets(cache_root))
    r.check("build jobs cached", check_build_jobs())
    r.check("AR6 regions match official vertices", check_ar6())
    r.check("git: no large, raw or secret files", check_git_sizes())
    print(f"\n{'FAILED' if r.failures else 'passed'}: {len(r.failures)} problem(s) in {cache_root}")
    return 1 if r.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
