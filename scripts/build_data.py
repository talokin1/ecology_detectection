r"""Rebuild every cached data series the statistics team needs, then write the freeze manifest.

One idempotent command (data plan tasks T2, T11, T14). The job list in
``data/catalog/build.yaml`` names the regions, the catalog-variable matrix and the daily method
inputs. Series already in the cache are served from it unless --refresh is given. Variables that
need an Earthdata login (GRACE, MODIS NDVI) are only fetched with --with-earthdata; otherwise
they are read from the cache and reported as "not cached" if missing (not an error).

After a build, ``<CACHE_DIR>/MANIFEST.json`` lists every cached CSV under ``power_zarr/`` and
``earthdata/`` with its sha256, row count, first/last index value and provenance fields.
The exit code is 1 if any series failed with a real error ("no data" and "not cached" are not
errors), so the command can gate a data freeze.

Examples (PowerShell or bash):
    python scripts/build_data.py --dry-run
    python scripts/build_data.py
    python scripts/build_data.py --only ukraine --only south_europe --refresh
    python scripts/build_data.py --with-earthdata
    python scripts/build_data.py --manifest-only

SI-assisted (Claude, Anthropic); pending team review (see docs/08-si-usage-log.md).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from trend_detective import acquire, power_zarr  # noqa: E402
from trend_detective.earthdata import NotCachedError  # noqa: E402

DEFAULT_JOBS = REPO_ROOT / "data" / "catalog" / "build.yaml"
MANIFEST_NAME = "MANIFEST.json"
MANIFEST_DIRS = ("power_zarr", "earthdata", "grids")  # data/cache/raw is deliberately not frozen
GRID_SUFFIXES = (".nc",)  # committed map grids (ADR-006); listed with their sidecar time range
ASSESSMENT_STATUSES = ("ok", "caution", "too_short", "no_variation")
NOT_ERRORS = (*ASSESSMENT_STATUSES, "no data", "not cached", "skipped")


@dataclass(frozen=True)
class Job:
    """One series to build: a catalog variable (``kind="variable"``) or a method input."""

    kind: str  # "variable" or "input"
    region: str  # region preset id
    name: str  # catalog variable id, or POWER parameter for inputs
    store: str | None = None  # inputs only
    how: str = "mean"  # inputs only: daily -> monthly aggregation for the quality check
    needs_login: bool = False
    excluded: bool = False


@dataclass
class Result:
    job: Job
    status: str
    period: str = ""
    n: int | None = None
    n_unit: str = ""
    origin: str = ""  # "cached" or "fetched"
    seconds: float = 0.0
    message: str = ""

    @property
    def is_error(self) -> bool:
        return self.status not in NOT_ERRORS


# --- job list ---------------------------------------------------------------------------------


def load_jobs(path: Path) -> dict:
    """Read and validate the YAML job list."""
    spec = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    regions = spec.get("regions")
    if not regions or not isinstance(regions, list):
        raise ValueError(f"{path}: 'regions' must be a non-empty list of preset ids")
    matrix = spec.get("matrix") or {}
    variables = matrix.get("variables", "all")
    if variables != "all" and not isinstance(variables, list):
        raise ValueError(f"{path}: matrix.variables must be 'all' or a list of catalog ids")
    for i, item in enumerate(spec.get("inputs") or []):
        if "parameter" not in item or "store" not in item:
            raise ValueError(f"{path}: inputs[{i}] needs 'parameter' and 'store'")
        if item.get("how", "mean") not in ("mean", "sum"):
            raise ValueError(f"{path}: inputs[{i}].how must be 'mean' or 'sum'")
    return spec


def expand_jobs(
    spec: dict, catalog: dict[str, acquire.Variable] | None = None, only: Sequence[str] | None = None
) -> list[Job]:
    """Matrix (available catalog variables x regions) followed by the method inputs.

    ``catalog`` defaults to ``acquire.list_variables(available_only=True)``. ``only`` restricts
    the run to these region ids (they need not be in the job list, but must be presets).
    """
    catalog = acquire.list_variables(available_only=True) if catalog is None else catalog
    regions = list(spec["regions"])
    matrix = spec.get("matrix") or {}
    wanted = matrix.get("variables", "all")
    excluded = set(matrix.get("exclude_variables") or [])
    if wanted == "all":
        ids = list(catalog)
    else:
        unknown = [v for v in wanted if v not in catalog]
        if unknown:
            raise KeyError(f"matrix variables not available in the catalog: {unknown}")
        ids = list(wanted)

    jobs: list[Job] = []
    matrix_regions = list(only) if only else list(matrix.get("regions") or regions)
    for region in matrix_regions:
        for vid in ids:
            jobs.append(
                Job("variable", region, vid, needs_login=catalog[vid].needs_login, excluded=vid in excluded)
            )
    for item in spec.get("inputs") or []:
        item_regions = list(only) if only else list(item.get("regions") or regions)
        for region in item_regions:
            jobs.append(
                Job("input", region, item["parameter"], store=item["store"], how=item.get("how", "mean"))
            )
    return jobs


# --- running ----------------------------------------------------------------------------------


def _period_and_n(s, job: Job) -> tuple[str, str, int, str]:
    """(status, period, n, unit) for a fetched series."""
    if job.kind == "variable":
        a = s.attrs.get("assessment") or acquire.assess(s)
        period = f"{a['start']}..{a['end']}" if "start" in a else ""
        return a["status"], period, int(a.get("n_months", len(s))), "mo"
    clean = s.dropna()
    if clean.empty:
        return "no data", "", 0, "d"
    a = acquire.assess(power_zarr.monthly_from_daily(clean, job.how))
    period = f"{clean.index[0]:%Y-%m-%d}..{clean.index[-1]:%Y-%m-%d}"
    return a["status"], period, len(clean), "d"


def run_job(job: Job, *, refresh: bool = False, with_earthdata: bool = False) -> Result:
    """Build one series. Never raises (except KeyboardInterrupt): failures become a Result."""
    if job.excluded:
        return Result(job, "skipped", message="excluded in the job list")
    t0 = time.perf_counter()
    try:
        if job.kind == "variable":
            s = acquire.get_series(
                job.name,
                job.region,
                allow_login_fetch=with_earthdata,
                refresh=refresh and (with_earthdata or not job.needs_login),
            )
        else:
            s = acquire.get_input_series(job.name, job.region, store=job.store, refresh=refresh)
        status, period, n, unit = _period_and_n(s, job)
        origin = "cached" if s.attrs.get("from_cache") else "fetched"
        return Result(job, status, period, n, unit, origin, time.perf_counter() - t0)
    except NotCachedError as exc:
        status = "error" if with_earthdata else "not cached"
        msg = str(exc) if with_earthdata else "needs --with-earthdata (Earthdata login)"
        return Result(job, status, seconds=time.perf_counter() - t0, message=msg)
    except ValueError as exc:
        status = "no data" if "no data" in str(exc).lower() else "error"
        return Result(job, status, seconds=time.perf_counter() - t0, message=str(exc))
    except Exception as exc:  # noqa: BLE001 - one failing series must not stop the run
        return Result(job, "error", seconds=time.perf_counter() - t0, message=f"{type(exc).__name__}: {exc}")


def format_result(r: Result) -> str:
    n = f"n={r.n} {r.n_unit}" if r.n is not None else "n=-"
    origin = f"{r.origin} {r.seconds:.1f}s" if r.origin else f"{r.seconds:.1f}s"
    line = f"{r.job.region:14} {r.job.name:32} {r.status:12} {r.period or '-':23} {n:12} {origin}"
    if r.message and r.status not in ASSESSMENT_STATUSES:
        line += f"  ({r.message})"
    return line


def dry_run_line(job: Job) -> str:
    """What a build would do for this job, without any network access."""
    if job.excluded:
        state = "skipped (excluded)"
    elif job.needs_login:
        state = "Earthdata: cache only unless --with-earthdata"
    else:
        state = "cached" if _power_cache_path(job).exists() else "would fetch"
    label = f"{job.name} [{job.store}]" if job.kind == "input" else job.name
    return f"{job.region:14} {label:44} {state}"


def _power_cache_path(job: Job) -> Path:
    """Cache file a POWER job would read (mirrors acquire.get_series / get_input_series)."""
    region = acquire.resolve_region(job.region)
    land_only = acquire._preset_land_only(job.region, None)
    if job.kind == "variable":
        access = acquire.list_variables()[job.name].access
        variable, store = access["variable"], access.get("store", "merra2")
    else:
        variable, store = job.name, job.store
    return power_zarr._cache_path(power_zarr.default_cache_dir(), variable, region, store, land_only)


def run_jobs(
    jobs: Iterable[Job], *, refresh: bool = False, with_earthdata: bool = False, echo=print
) -> list[Result]:
    results = []
    for job in jobs:
        r = run_job(job, refresh=refresh, with_earthdata=with_earthdata)
        echo(format_result(r))
        results.append(r)
    return results


def summarise(results: Sequence[Result], echo=print) -> int:
    """Print the status counts and failures; return the exit code (1 if any real error)."""
    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    echo("")
    echo(f"{len(results)} series: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    errors = [r for r in results if r.is_error]
    for r in errors:
        echo(f"FAILED {r.job.region} {r.job.name}: {r.message}")
    return 1 if errors else 0


# --- manifest ---------------------------------------------------------------------------------


def default_cache_root() -> Path:
    """``$CACHE_DIR`` or ``data/cache`` (the parent of the reader cache folders)."""
    return power_zarr.default_cache_dir().parent


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _csv_summary(path: Path) -> tuple[int, str | None, str | None]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        rows, first, last = 0, None, None
        for row in reader:
            if not row:
                continue
            rows += 1
            if first is None:
                first = row[0]
            last = row[0]
    return rows, first, last


def _region_id(bbox: dict | None) -> str | None:
    """Preset id whose bbox equals the sidecar bbox (B1-03), else ``None`` (custom box or grid)."""
    if not bbox:
        return None
    key = (bbox.get("lon_min"), bbox.get("lat_min"), bbox.get("lon_max"), bbox.get("lat_max"))
    for pid, e in acquire.list_regions().items():
        if tuple(float(v) for v in e["bbox"]) == key:
            return pid
    return None


def manifest_entry(path: Path, cache_root: Path) -> dict:
    sidecar = path.with_name(path.name + ".provenance.json")
    prov = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.exists() else {}
    if path.suffix in GRID_SUFFIXES:
        tr = prov.get("time_range") or {}
        rows, first, last = prov.get("n_months"), tr.get("start"), tr.get("end")
    else:
        rows, first, last = _csv_summary(path)
    var = prov.get("variable")
    return {
        "kind": "grid" if path.suffix in GRID_SUFFIXES else "series",
        "region_id": _region_id(prov.get("bbox")) if path.suffix not in GRID_SUFFIXES else None,
        "path": path.relative_to(cache_root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "rows": rows,
        "first": first,
        "last": last,
        "variable": var.get("variable") if isinstance(var, dict) else var,
        "source": var.get("source") if isinstance(var, dict) else prov.get("source"),
        "region_name": prov.get("region_name"),
        "bbox": prov.get("bbox"),
        "land_only": prov.get("land_only"),
        "git_commit": prov.get("git_commit"),
        "accessed": prov.get("accessed"),
        "has_provenance": sidecar.exists(),
    }


def build_manifest(cache_root: Path, freeze_date: str | None = None) -> dict:
    cache_root = Path(cache_root)
    files = sorted(
        (
            p
            for d in MANIFEST_DIRS
            if (cache_root / d).is_dir()
            for p in (cache_root / d).rglob("*")
            if p.is_file() and p.suffix in (".csv", *GRID_SUFFIXES) and not p.name.endswith(".partial.csv")
        ),  # unfinished resumable fetches are not frozen data
        key=lambda p: p.relative_to(cache_root).as_posix(),
    )
    entries = [manifest_entry(p, cache_root) for p in files]
    return {
        "freeze_date": freeze_date or datetime.now(UTC).date().isoformat(),
        "n_files": len(entries),
        "total_bytes": sum(e["bytes"] for e in entries),
        "directories": list(MANIFEST_DIRS),
        "files": entries,
    }


def write_manifest(cache_root: Path, freeze_date: str | None = None) -> dict:
    """Write ``<cache_root>/MANIFEST.json`` (sorted, deterministic) and return its content."""
    manifest = build_manifest(cache_root, freeze_date)
    out = Path(cache_root) / MANIFEST_NAME
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return manifest


# --- CLI --------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--jobs", type=Path, default=DEFAULT_JOBS, help="YAML job list")
    p.add_argument("--refresh", action="store_true", help="download again even if cached")
    p.add_argument(
        "--with-earthdata",
        action="store_true",
        help="allow fetching login-only variables (needs EARTHDATA_TOKEN)",
    )
    p.add_argument(
        "--only", action="append", metavar="REGION_ID", help="build only this region preset (repeatable)"
    )
    p.add_argument("--dry-run", action="store_true", help="list what would be built and exit")
    p.add_argument("--manifest-only", action="store_true", help="only rewrite MANIFEST.json")
    args = p.parse_args(argv)

    cache_root = default_cache_root()
    if args.manifest_only:
        m = write_manifest(cache_root)
        print(f"wrote {cache_root / MANIFEST_NAME}: {m['n_files']} files, {m['total_bytes']} bytes")
        return 0

    spec = load_jobs(args.jobs)
    if args.only:
        unknown = sorted(set(args.only) - set(acquire.list_regions()))
        if unknown:
            p.error(f"unknown region preset(s) {unknown}; choose from {sorted(acquire.list_regions())}")
    jobs = expand_jobs(spec, only=args.only)

    if args.dry_run:
        for job in jobs:
            print(dry_run_line(job))
        print(f"\n{len(jobs)} series would be built (dry run: nothing fetched, manifest not written)")
        return 0

    results = run_jobs(jobs, refresh=args.refresh, with_earthdata=args.with_earthdata)
    code = summarise(results)
    m = write_manifest(cache_root)
    print(f"wrote {cache_root / MANIFEST_NAME}: {m['n_files']} files, {m['total_bytes']} bytes")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
