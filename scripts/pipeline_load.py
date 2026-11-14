r"""Field-team data loader: Ukraine first, then the whole world (24/7 pipeline, see scripts/PIPELINE.md).

THIS IS THE FILE TO EDIT. Everything the field team is expected to change is in the
"EDIT HERE" block below: which variables are fetched, the world grid resolution, and the
preprocessing / classification hooks that run after the raw data has landed.

The loader only *orchestrates*: every download goes through the repo's own readers
(``acquire.get_series`` / ``acquire.get_input_series`` for regional series, ``grids.build_grid``
and ``grace.build_grid`` for world grids), so caching, provenance sidecars and units are the
same as in ``scripts/build_data.py`` and ``scripts/fetch_grid.py``. Raw cache files are never
modified by the hooks; hooks write to ``<data-dir>/<stage>/processed/``.

Stages (run in this order by ``--stage all``):
    ukraine        all no-login POWER catalog variables + daily method inputs + GRACE + MODIS NDVI
                   over the canonical ``ukraine`` preset (bbox 22,44,40.5,52.5, land_only, Crimea
                   always included), into ``<data-dir>/ukraine/``
    world          2-degree global monthly grid of every POWER catalog variable (+ GRACE grid),
                   into ``<data-dir>/world/grids/``
    ukraine_slow   slow Earthdata series for Ukraine (OMI NO2: ~8,000 small requests; resumable),
                   run after the world so it never delays it

Idempotent and resumable: finished files are skipped; an interrupted grid is written to a ``.tmp``
file and rebuilt; an interrupted MODIS/OMI fetch resumes from its ``.partial.csv``. Failed items
are retried with exponential backoff. Every stage writes ``MANIFEST.json`` (same format as
``scripts/build_data.py --manifest-only``) and ``STAGE_STATUS.json`` in its data folder.

Earthdata (GRACE, MODIS NDVI, OMI NO2) needs ``EARTHDATA_TOKEN`` in the environment (or the repo
``.env``, or a ``machine urs.earthdata.nasa.gov`` entry in ``~/.netrc``). Without one these items are
served from the repo's committed cache when possible and otherwise logged as skipped.
The token is never printed or written anywhere by this script.

Examples (bash):
    python scripts/pipeline_load.py --data-dir /srv/spaceapps/data            # all stages
    python scripts/pipeline_load.py --data-dir /tmp/d --stage ukraine
    python scripts/pipeline_load.py --data-dir /tmp/d --stage world --world-variables T2M TQV
    python scripts/pipeline_load.py --dry-run

SI-assisted (GOD / Grok Bot, data-entry agent, 2026-11-14); pending team review (docs/08-si-usage-log.md).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

# =================================================================================================
# EDIT HERE ---------------------------------------------------------------------------------------
# =================================================================================================

# Region preset id from data/catalog/regions.yaml. `ukraine` = [22.0, 44.0, 40.5, 52.5], land_only,
# always including Crimea (ADR-005). Do not add a no-Crimea variant.
UKRAINE_REGION = "ukraine"

# Catalog variable ids to fetch for Ukraine, or "all" = every catalog variable that has a reader
# (POWER, GRACE, MODIS NDVI, OMI NO2). Login-only ones are fetched only when a token is available.
UKRAINE_VARIABLES: list[str] | str = "all"
UKRAINE_EXCLUDE: list[str] = []
# Login variables that take hours; fetched in the `ukraine_slow` stage AFTER the world.
UKRAINE_SLOW: list[str] = ["no2_tropospheric_omi"]

# Daily method inputs (catalog `internal_inputs`; Tmax/Tmin = mean of daily extremes, never the
# monthly store's single extreme hour). (parameter, store, how) as in data/catalog/build.yaml.
UKRAINE_INPUTS: list[tuple[str, str, str]] = [
    ("T2M_MAX", "merra2_daily", "mean"),
    ("T2M_MIN", "merra2_daily", "mean"),
    ("PRECTOTCORR", "merra2_daily", "sum"),
]

# World grid: cell size in degrees (must divide 180). 2 deg = ~26 MB and ~40 s per variable.
WORLD_RESOLUTION = 2.0
WORLD_METHOD = "overlap"  # grids.METHODS: "overlap" (default, area-conserving) or "centre"
WORLD_LAND_ONLY = False
# (source, POWER parameter) pairs, or "all" = every POWER variable in the catalog (monthly stores).
WORLD_VARIABLES: list[tuple[str, str]] | str = "all"
# GRACE 2-deg land water-storage grid (Earthdata; the repo ships a committed copy that is reused).
WORLD_GRACE = True

# Retries for one item (a series or a grid): wait RETRY_BASE_S * 2**attempt, capped.
RETRIES = 4
RETRY_BASE_S = 20
RETRY_MAX_S = 600


def preprocess_series(series, meta: dict):
    """Called for every Ukraine series after it is fetched (or read from the cache).

    ``series``: pandas Series indexed by month (or date, for daily inputs), source units;
    ``series.attrs`` holds the catalog entry, provenance and the fit-for-trend ``assessment``.
    ``meta``: {"kind": "variable"|"input", "id": ..., "region": ..., "units": ...}.
    Return a Series (written to ``ukraine/processed/<id>.csv``) or None to write nothing.
    Default: unchanged (a flat, easy-to-load copy of the cached series).
    """
    return series


def classify_series(series, meta: dict) -> dict | None:
    """Optional per-series classification/labels, collected into ``ukraine/processed/labels.json``.

    Default: the repo's own data-quality verdict (``acquire.assess``: ok / caution / too_short /
    no_variation). Replace with your classifier; NEVER hand-roll a trend test here, use
    .claude/skills/trend-stats/scripts/trend_stats.py (CLAUDE.md rule 3).
    """
    a = series.attrs.get("assessment") or {}
    return {"status": a.get("status"), "notes": a.get("notes", [])}


def postprocess_ukraine(stage_dir: Path, results: list[dict]) -> None:
    """Runs once after the Ukraine stage. Default: nothing."""


def postprocess_world(stage_dir: Path, results: list[dict]) -> None:
    """Runs once after the world stage (grids are in ``stage_dir / 'grids'``). Default: nothing."""


# =================================================================================================
# END OF EDIT BLOCK (below: orchestration; change only if you know why) ---------------------------
# =================================================================================================

log = logging.getLogger("pipeline_load")
STAGES = ("ukraine", "world", "ukraine_slow")
EARTHDATA_HOST = "urs.earthdata.nasa.gov"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_commit() -> str | None:
    import subprocess

    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=5, check=True
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


# --- Earthdata credentials (never logged) ------------------------------------------------------


def earthdata_available() -> bool:
    """True if a bearer token can be found. Order: $EARTHDATA_TOKEN, repo .env, ~/.netrc (via
    earthaccess, which turns the netrc login into a token for this process only)."""
    from trend_detective import earthdata

    if os.environ.get(earthdata.TOKEN_VAR) or earthdata._read_dotenv(REPO_ROOT / ".env").get(
        earthdata.TOKEN_VAR
    ):
        return True
    netrc = Path(os.environ.get("NETRC", Path.home() / ".netrc"))
    if netrc.exists() and EARTHDATA_HOST in netrc.read_text(encoding="utf-8", errors="ignore"):
        try:
            import earthaccess

            auth = earthaccess.login(strategy="netrc")
            tok = (getattr(auth, "token", None) or {}).get("access_token")
            if tok:
                os.environ[earthdata.TOKEN_VAR] = tok  # this process and its children only
                earthdata.token.cache_clear()
                return True
        except Exception as exc:  # noqa: BLE001
            log.warning("~/.netrc has an Earthdata entry but login failed: %s", type(exc).__name__)
    return False


# --- helpers -------------------------------------------------------------------------------------


def with_retries(label: str, fn, *, retries: int = RETRIES, is_failure=None):
    """Call ``fn()``; retry on exceptions (or when ``is_failure(result)``) with exponential backoff."""
    last = None
    for attempt in range(retries + 1):
        try:
            result = fn()
            if is_failure is None or not is_failure(result):
                return result
            last = result
            log.warning(
                "%s: attempt %d/%d failed: %s",
                label,
                attempt + 1,
                retries + 1,
                getattr(result, "message", result),
            )
        except KeyboardInterrupt:
            raise
        except Exception as exc:  # noqa: BLE001
            last = exc
            log.warning(
                "%s: attempt %d/%d raised %s: %s", label, attempt + 1, retries + 1, type(exc).__name__, exc
            )
        if attempt < retries:
            wait = min(RETRY_MAX_S, RETRY_BASE_S * 2**attempt)
            log.info("%s: retrying in %d s", label, wait)
            time.sleep(wait)
    if isinstance(last, Exception):
        raise last
    return last


def use_cache_root(stage_dir: Path) -> None:
    """Point every reader at ``stage_dir`` (readers read $CACHE_DIR at call time)."""
    stage_dir.mkdir(parents=True, exist_ok=True)
    os.environ["CACHE_DIR"] = str(stage_dir)


def remove_orphans(stage_dir: Path) -> int:
    """Delete POWER series CSVs whose provenance sidecar is missing (a crash between the two writes),
    so they are fetched again. MODIS/OMI ``.partial.csv`` resume files are left alone."""
    n = 0
    d = stage_dir / "power_zarr"
    for csv in d.glob("*.csv") if d.is_dir() else []:
        if not csv.with_name(csv.name + ".provenance.json").exists():
            log.warning("removing incomplete %s (no provenance sidecar)", csv.name)
            csv.unlink()
            n += 1
    for tmp in (stage_dir / "grids").glob("*.tmp") if (stage_dir / "grids").is_dir() else []:
        tmp.unlink()
        n += 1
    return n


def _sidecar_bbox(f: Path) -> list[float] | None:
    """[west, south, east, north] from a cache file's provenance/meta sidecar (None if absent)."""
    base = f.name
    for suffix in (".provenance.json", ".meta.json"):
        base = base.removesuffix(suffix)
    for suffix in (".provenance.json", ".meta.json"):
        side = f.with_name(base + suffix)
        if side.exists():
            b = json.loads(side.read_text(encoding="utf-8")).get("bbox") or {}
            if isinstance(b, dict) and "lon_min" in b:
                return [float(b[k]) for k in ("lon_min", "lat_min", "lon_max", "lat_max")]
    return None


def seed_from_repo(
    stage_dir: Path, subdir: str, names: list[str] | None = None, bbox: list[float] | None = None
) -> int:
    """Copy committed cache files (with their sidecars) from the repo's data/cache/<subdir> into the
    stage folder when missing, so data already downloaded by the team (e.g. the long MODIS NDVI
    record) is reused instead of fetched again. ``bbox``: only files whose sidecar has this box."""
    src = REPO_ROOT / "data" / "cache" / subdir
    if not src.is_dir():
        return 0
    n = 0
    for f in sorted(src.iterdir()):
        if not f.is_file() or (names is not None and not any(f.name.startswith(x) for x in names)):
            continue
        if bbox is not None and _sidecar_bbox(f) != [float(v) for v in bbox]:
            continue
        dest = stage_dir / subdir / f.name
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
            n += 1
    return n


def write_json(path: Path, obj) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_stage_status(stage_dir: Path, stage: str, state: str, results: list[dict], started: str) -> None:
    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    write_json(
        stage_dir / "STAGE_STATUS.json",
        {
            "stage": stage,
            "state": state,
            "started": started,
            "updated": _now(),
            "git_commit": _git_commit(),
            "counts": counts,
            "items": results,
        },
    )


def write_manifest(stage_dir: Path) -> None:
    import build_data

    m = build_data.write_manifest(stage_dir)
    log.info("MANIFEST.json: %d files, %.1f MB", m["n_files"], m["total_bytes"] / 1e6)


# --- Ukraine -------------------------------------------------------------------------------------


def ukraine_jobs(variables, exclude, slow: bool):
    import build_data
    from trend_detective import acquire

    catalog = acquire.list_variables(available_only=True)
    ids = list(catalog) if variables == "all" else list(variables)
    jobs = []
    for vid in ids:
        if vid in exclude or (vid in UKRAINE_SLOW) != slow:
            continue
        jobs.append(build_data.Job("variable", UKRAINE_REGION, vid, needs_login=catalog[vid].needs_login))
    if not slow:
        login = [j for j in jobs if j.needs_login]
        jobs = [j for j in jobs if not j.needs_login]
        jobs += [build_data.Job("input", UKRAINE_REGION, p, store=s, how=h) for p, s, h in UKRAINE_INPUTS]
        jobs += login  # POWER first (fast, no login), then GRACE / NDVI
    return jobs


def _write_processed(stage_dir: Path, job, labels: dict) -> None:
    """Re-read the (cached) series and pass it through the team's hooks."""
    from trend_detective import acquire

    if job.kind == "variable":
        s = acquire.get_series(job.name, job.region)
        pid = job.name
    else:
        s = acquire.get_input_series(job.name, job.region, store=job.store)
        pid = f"{job.name}_{job.store}"
    meta = {"kind": job.kind, "id": pid, "region": job.region, "units": s.attrs.get("units", "")}
    out = preprocess_series(s, meta)
    if out is not None:
        p = stage_dir / "processed" / f"{pid}.csv"
        p.parent.mkdir(parents=True, exist_ok=True)
        out.rename("value").to_csv(p, lineterminator="\n")
    label = classify_series(s, meta)
    if label is not None:
        labels[pid] = label


def run_ukraine(
    data_dir: Path, *, slow: bool = False, has_token: bool = False, dry_run: bool = False
) -> list[dict]:
    import build_data

    stage = "ukraine_slow" if slow else "ukraine"
    stage_dir = data_dir / "ukraine"
    jobs = ukraine_jobs(UKRAINE_VARIABLES, UKRAINE_EXCLUDE, slow)
    if dry_run:
        for j in jobs:
            print(f"{stage:12} {j.kind:8} {j.name:32} {'login' if j.needs_login else ''}")
        return []
    use_cache_root(stage_dir)
    remove_orphans(stage_dir)
    if not slow:
        from trend_detective import acquire

        n = seed_from_repo(stage_dir, "earthdata", bbox=acquire.list_regions()[UKRAINE_REGION]["bbox"])
        if n:
            log.info("seeded %d committed Earthdata cache files from the repo", n)
    started, results, labels = _now(), [], {}
    labels_path = stage_dir / "processed" / "labels.json"
    if labels_path.exists():
        labels = json.loads(labels_path.read_text(encoding="utf-8"))
    write_stage_status(stage_dir, stage, "running", results, started)
    for i, job in enumerate(jobs, 1):
        label = f"[{stage} {i}/{len(jobs)}] {job.kind} {job.name}"
        log.info("%s: start", label)
        r = with_retries(
            label,
            lambda job=job: build_data.run_job(job, with_earthdata=has_token),
            is_failure=lambda r: r.is_error,
        )
        status = r.status
        if status == "not cached":
            status = "skipped"
            r.message = "Earthdata login needed and no EARTHDATA_TOKEN configured"
        log.info("%s: %s %s %s", label, status, r.origin or "", r.message or r.period)
        item = {
            "kind": job.kind,
            "id": job.name,
            "store": job.store,
            "status": status,
            "origin": r.origin,
            "period": r.period,
            "n": r.n,
            "seconds": round(r.seconds, 1),
            "message": r.message,
        }
        if not r.is_error and status not in ("skipped", "no data", "unsupported"):
            try:
                _write_processed(stage_dir, job, labels)
            except Exception as exc:  # noqa: BLE001 - a broken hook must not lose the raw data
                item["hook_error"] = f"{type(exc).__name__}: {exc}"
                log.error("%s: preprocessing hook failed: %s", label, item["hook_error"])
        results.append(item)
        write_stage_status(stage_dir, stage, "running", results, started)
    if labels:
        labels_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(labels_path, labels)
    write_manifest(stage_dir)
    try:
        postprocess_ukraine(stage_dir, results)
    except Exception as exc:  # noqa: BLE001
        log.error("postprocess_ukraine failed: %s: %s", type(exc).__name__, exc)
    failed = [r for r in results if r["status"] == "error"]
    write_stage_status(stage_dir, stage, "failed" if failed else "done", results, started)
    return results


# --- World ---------------------------------------------------------------------------------------


def world_variables(selected=None) -> list[tuple[str, str]]:
    from trend_detective import acquire, power_zarr

    if selected:
        out = []
        for item in selected:
            src, _, var = item.rpartition(":")
            out.append((src or None, var))
        catalog = {
            v.access["variable"]: v.access.get("store", "merra2")
            for v in acquire.list_variables().values()
            if v.reader == "power_zarr"
        }
        return [(src or catalog.get(var, "merra2"), var) for src, var in out]
    if WORLD_VARIABLES != "all":
        return list(WORLD_VARIABLES)
    pairs = []
    for v in acquire.list_variables(available_only=True).values():
        if v.reader != "power_zarr":
            continue
        store = v.access.get("store", "merra2")
        if power_zarr.SOURCES[store].get("freq", "M") == "M" and (store, v.access["variable"]) not in pairs:
            pairs.append((store, v.access["variable"]))
    return pairs


def run_world(data_dir: Path, *, has_token: bool = False, selected=None, dry_run: bool = False) -> list[dict]:
    from trend_detective import earthdata, grace, grids

    stage_dir = data_dir / "world"
    pairs = world_variables(selected)
    if dry_run:
        for src, var in pairs:
            print(f"world        grid     {src}:{var} {WORLD_RESOLUTION:g} deg")
        if WORLD_GRACE:
            print(f"world        grid     grace:lwe_thickness {WORLD_RESOLUTION:g} deg (login)")
        return []
    use_cache_root(stage_dir)
    remove_orphans(stage_dir)
    grid_dir = stage_dir / "grids"
    if WORLD_GRACE:
        seed_from_repo(stage_dir, "grids", ["grace_lwe_thickness"])
    started, results = _now(), []
    write_stage_status(stage_dir, "world", "running", results, started)
    total = len(pairs) + int(WORLD_GRACE)
    for i, (src, var) in enumerate(pairs, 1):
        label = f"[world {i}/{total}] {src}:{var}"
        path = grids.grid_path(grid_dir, var, src, WORLD_RESOLUTION, WORLD_LAND_ONLY, WORLD_METHOD)
        item = {"kind": "grid", "id": var, "store": src, "path": str(path)}
        t0 = time.perf_counter()
        log.info("%s: start", label)
        try:
            ds = with_retries(
                label,
                lambda src=src, var=var: grids.build_grid(
                    var,
                    src,
                    WORLD_RESOLUTION,
                    land_only=WORLD_LAND_ONLY,
                    method=WORLD_METHOD,
                    cache_dir=grid_dir,
                ),
            )
            item |= {
                "status": "done",
                "origin": "cached" if ds.attrs.get("from_cache") else "fetched",
                "mb": round(path.stat().st_size / 1e6, 1),
            }
            ds.close()
        except Exception as exc:  # noqa: BLE001
            item |= {"status": "error", "message": f"{type(exc).__name__}: {exc}"}
        item["seconds"] = round(time.perf_counter() - t0, 1)
        log.info("%s: %s %s", label, item["status"], item.get("mb", item.get("message", "")))
        results.append(item)
        write_stage_status(stage_dir, "world", "running", results, started)
    if WORLD_GRACE:
        label = f"[world {total}/{total}] grace:lwe_thickness"
        path = grids.grid_path(grid_dir, "lwe_thickness", "grace", WORLD_RESOLUTION, land_only=True)
        item = {"kind": "grid", "id": "lwe_thickness", "store": "grace", "path": str(path)}
        t0 = time.perf_counter()
        try:
            ds = with_retries(
                label,
                lambda: grace.build_grid(WORLD_RESOLUTION, cache_dir=grid_dir, offline=not has_token),
            )
            item |= {
                "status": "done",
                "origin": "cached" if ds.attrs.get("from_cache") else "fetched",
                "mb": round(path.stat().st_size / 1e6, 1),
            }
        except earthdata.NotCachedError:
            item |= {
                "status": "skipped",
                "message": "Earthdata login needed and no EARTHDATA_TOKEN configured",
            }
        except Exception as exc:  # noqa: BLE001
            item |= {"status": "error", "message": f"{type(exc).__name__}: {exc}"}
        item["seconds"] = round(time.perf_counter() - t0, 1)
        log.info("%s: %s %s", label, item["status"], item.get("mb", item.get("message", "")))
        results.append(item)
    log.info(
        "world: MODIS NDVI has no global-grid reader in the repo (MOD13C2 world = ~45 GB raw); not built"
    )
    write_manifest(stage_dir)
    try:
        postprocess_world(stage_dir, results)
    except Exception as exc:  # noqa: BLE001
        log.error("postprocess_world failed: %s: %s", type(exc).__name__, exc)
    failed = [r for r in results if r["status"] == "error"]
    write_stage_status(stage_dir, "world", "failed" if failed else "done", results, started)
    return results


# --- CLI -----------------------------------------------------------------------------------------


def default_data_dir() -> Path:
    if os.environ.get("SPACEAPPS_DATA_DIR"):
        return Path(os.environ["SPACEAPPS_DATA_DIR"])
    return Path("/srv/spaceapps/data")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument(
        "--data-dir", type=Path, default=None, help="default $SPACEAPPS_DATA_DIR or /srv/spaceapps/data"
    )
    p.add_argument("--stage", choices=[*STAGES, "all"], default="all")
    p.add_argument("--world-variables", nargs="*", metavar="[SOURCE:]VAR", help="override the world list")
    p.add_argument("--dry-run", action="store_true", help="list what would be fetched and exit")
    p.add_argument(
        "--lock",
        type=Path,
        default=os.environ.get("SPACEAPPS_RUN_LOCK") or None,
        help="flock file shared with the daemon so runs never overlap (default $SPACEAPPS_RUN_LOCK)",
    )
    args = p.parse_args(argv)
    logging.Formatter.converter = time.gmtime  # log times in UTC, marked with Z
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)sZ %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    data_dir = (args.data_dir or default_data_dir()).resolve()
    stages = STAGES if args.stage == "all" else (args.stage,)

    lock_fh = None
    if args.lock and not args.dry_run:
        import fcntl

        lock_fh = Path(args.lock).open("a")  # noqa: SIM115 - held until the process exits
        try:
            fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log.info("another loader run holds %s; waiting for it to finish", args.lock)
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
    has_token = False if args.dry_run else earthdata_available()
    if not args.dry_run:
        log.info("data dir %s; repo %s at %s", data_dir, REPO_ROOT, (_git_commit() or "?")[:10])
        log.info(
            "Earthdata: %s",
            "token found (GRACE, NDVI, NO2 will be fetched)"
            if has_token
            else "no EARTHDATA_TOKEN / ~/.netrc entry: login-only items are skipped (cached copies kept)",
        )
    code = 0
    for stage in stages:
        t0 = time.perf_counter()
        log.info("=== stage %s: start", stage)
        if stage == "world":
            results = run_world(
                data_dir, has_token=has_token, selected=args.world_variables, dry_run=args.dry_run
            )
        elif stage == "ukraine_slow" and not has_token and not args.dry_run:
            log.info("stage ukraine_slow: skipped (needs Earthdata token)")
            results = []
        else:
            results = run_ukraine(
                data_dir, slow=stage == "ukraine_slow", has_token=has_token, dry_run=args.dry_run
            )
        errors = [r for r in results if r["status"] == "error"]
        log.info(
            "=== stage %s: %s in %.0f s (%d items, %d errors)",
            stage,
            "failed" if errors else "done",
            time.perf_counter() - t0,
            len(results),
            len(errors),
        )
        code = code or (1 if errors else 0)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
