r"""Field-team data loader: listed countries, Ukraine first (24/7 pipeline, see scripts/PIPELINE.md).

THIS IS THE FILE TO EDIT. Everything the field team is expected to change is in the
"EDIT HERE" block below: the COUNTRIES list, which variables are fetched, and the
preprocessing / classification hooks that run after the raw data has landed.

The loader only *orchestrates*: every download goes through the repo's own readers
(``acquire.get_series`` / ``acquire.get_input_series`` for regional series), so caching,
provenance sidecars and units are the same as in ``scripts/build_data.py``. Raw cache
files are never modified by the hooks; hooks write to ``<data-dir>/<country>/processed/``.

Stages (run in this order by ``--stage all``), one pair per entry in COUNTRIES:
    <country>        all no-login POWER catalog variables + daily method inputs + GRACE +
                     MODIS NDVI (and any other regional-only reader) over that country's
                     preset, into ``<data-dir>/<country>/``
    <country>_slow   slow Earthdata series for that country (OMI NO2: ~8,000 small
                     requests; resumable), after every country's fast stage

The worldwide (2-degree global grid) stage has been removed. Existing files under
``<data-dir>/world/`` are left in place and are no longer updated.

Idempotent and resumable: finished files are skipped; an interrupted MODIS/OMI fetch
resumes from its ``.partial.csv``. Failed items are retried with exponential backoff.
Every stage writes ``MANIFEST.json`` (same format as ``scripts/build_data.py --manifest-only``)
and a per-stage ``STAGE_STATUS.<stage>.json``; ``STAGE_STATUS.json`` is a combined rollup
that keeps every stage's results (the slow stage must not overwrite the fast one).

Earthdata (GRACE, MODIS NDVI, OMI NO2) needs ``EARTHDATA_TOKEN`` in the environment (or the
repo ``.env``, or a ``machine urs.earthdata.nasa.gov`` entry in ``~/.netrc``). Without one
these items are served from the repo's committed cache when possible and otherwise logged
as skipped. The token is never printed or written anywhere by this script.

Examples (bash):
    python scripts/pipeline_load.py --data-dir /srv/spaceapps/data            # all stages
    python scripts/pipeline_load.py --data-dir /tmp/d --stage ukraine
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

# Canonical Ukraine preset from data/catalog/regions.yaml: bbox [22.0, 44.0, 40.5, 52.5],
# land_only, always including Crimea (ADR-005). Do not add a no-Crimea variant.
UKRAINE_REGION = "ukraine"

# Countries to fetch, as region preset ids from acquire.list_regions() (data/catalog/regions.yaml
# and any files it includes). Adding a country is just appending its id here after the preset
# exists in the catalog — see "Adding a country" in scripts/PIPELINE.md. If an id is missing
# from the registry, that country fails clearly in STAGE_STATUS / status.json and the rest
# of the run continues.
COUNTRIES: list[str] = [UKRAINE_REGION]

# Catalog variable ids to fetch for each country, or "all" = every catalog variable that has a
# reader (POWER, GRACE, MODIS NDVI, OMI NO2). Login-only ones are fetched only when a token is
# available. Readers that have no world-grid job (MODIS NDVI, OMI NO2, and any future regional-only
# reader) are always included for every listed country unless they appear in COUNTRY_EXCLUDE.
COUNTRY_VARIABLES: list[str] | str = "all"
COUNTRY_EXCLUDE: list[str] = []
# Login variables that take hours; fetched in the `<country>_slow` stage after every fast stage.
COUNTRY_SLOW: list[str] = ["no2_tropospheric_omi"]

# Daily method inputs (catalog `internal_inputs`; Tmax/Tmin = mean of daily extremes, never the
# monthly store's single extreme hour). (parameter, store, how) as in data/catalog/build.yaml.
COUNTRY_INPUTS: list[tuple[str, str, str]] = [
    ("T2M_MAX", "merra2_daily", "mean"),
    ("T2M_MIN", "merra2_daily", "mean"),
    ("PRECTOTCORR", "merra2_daily", "sum"),
]

# Retries for one item (a series): wait RETRY_BASE_S * 2**attempt, capped.
RETRIES = 4
RETRY_BASE_S = 20
RETRY_MAX_S = 600


def preprocess_series(series, meta: dict):
    """Called for every country series after it is fetched (or read from the cache).

    ``series``: pandas Series indexed by month (or date, for daily inputs), source units;
    ``series.attrs`` holds the catalog entry, provenance and the fit-for-trend ``assessment``.
    ``meta``: {"kind": "variable"|"input", "id": ..., "region": ..., "units": ...}.
    Return a Series (written to ``<country>/processed/<id>.csv``) or None to write nothing.
    Default: unchanged (a flat, easy-to-load copy of the cached series).
    """
    return series


def classify_series(series, meta: dict) -> dict | None:
    """Optional per-series classification/labels, collected into ``<country>/processed/labels.json``.

    Default: the repo's own data-quality verdict (``acquire.assess``: ok / caution / too_short /
    no_variation). Replace with your classifier; NEVER hand-roll a trend test here, use
    .claude/skills/trend-stats/scripts/trend_stats.py (CLAUDE.md rule 3).
    """
    a = series.attrs.get("assessment") or {}
    return {"status": a.get("status"), "notes": a.get("notes", [])}


def postprocess_country(stage_dir: Path, results: list[dict], country: str) -> None:
    """Runs once after each country's fast or slow stage. Default: nothing."""


# =================================================================================================
# END OF EDIT BLOCK (below: orchestration; change only if you know why) ---------------------------
# =================================================================================================

log = logging.getLogger("pipeline_load")
EARTHDATA_HOST = "urs.earthdata.nasa.gov"
# Readers that only have a regional (per-country) implementation — no world-grid builder exists
# in the repo. These are always fetched for every listed country (see country_plan).
REGIONAL_ONLY_READERS = frozenset({"modis_ndvi", "omi_no2"})


def stage_names(countries: list[str] | None = None) -> tuple[str, ...]:
    """Fast stages first (one per country), then the matching slow stages."""
    ids = list(countries if countries is not None else COUNTRIES)
    return tuple(ids + [f"{cid}_slow" for cid in ids])


def parse_stage(stage: str) -> tuple[str, bool]:
    """``('ukraine', False)`` or ``('ukraine', True)`` for ``ukraine_slow``."""
    if stage.endswith("_slow"):
        return stage[: -len("_slow")], True
    return stage, False


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_commit() -> str | None:
    import subprocess

    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
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
                "%s: attempt %d/%d raised %s: %s",
                label,
                attempt + 1,
                retries + 1,
                type(exc).__name__,
                exc,
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
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_stage_status(stage_dir: Path, stage: str, state: str, results: list[dict], started: str) -> None:
    """Write a per-stage file and merge it into STAGE_STATUS.json without dropping other stages."""
    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    payload = {
        "stage": stage,
        "state": state,
        "started": started,
        "updated": _now(),
        "git_commit": _git_commit(),
        "counts": counts,
        "items": results,
    }
    write_json(stage_dir / f"STAGE_STATUS.{stage}.json", payload)
    combined_path = stage_dir / "STAGE_STATUS.json"
    combined: dict = {}
    if combined_path.exists():
        try:
            combined = json.loads(combined_path.read_text(encoding="utf-8"))
        except ValueError:
            combined = {}
    stages = dict(combined.get("stages") or {})
    # Older files had a single top-level stage; keep that result under its stage name.
    if "stage" in combined and "stages" not in combined:
        old = combined["stage"]
        if old not in stages:
            stages[old] = {k: combined[k] for k in combined if k != "stages"}
    stages[stage] = payload
    overall = "done"
    if any(s.get("state") == "failed" for s in stages.values()):
        overall = "failed"
    elif any(s.get("state") == "running" for s in stages.values()):
        overall = "running"
    all_counts: dict[str, int] = {}
    for s in stages.values():
        for k, n in (s.get("counts") or {}).items():
            all_counts[k] = all_counts.get(k, 0) + n
    write_json(
        combined_path,
        {
            "country": stage_dir.name,
            "state": overall,
            "updated": _now(),
            "git_commit": _git_commit(),
            "counts": all_counts,
            "stages": stages,
        },
    )


def write_manifest(stage_dir: Path) -> None:
    import build_data

    m = build_data.write_manifest(stage_dir)
    log.info("MANIFEST.json: %d files, %.1f MB", m["n_files"], m["total_bytes"] / 1e6)


# --- Countries -----------------------------------------------------------------------------------


def regional_only_ids(catalog) -> list[str]:
    """Catalog ids whose reader has no world-grid job (currently MODIS NDVI and OMI NO2)."""
    return [vid for vid, v in catalog.items() if getattr(v, "reader", None) in REGIONAL_ONLY_READERS]


def country_plan(country: str, *, slow: bool) -> tuple[list, list[dict]]:
    """Jobs to run for one country stage, plus items already resolved (skipped / unsupported)."""
    import build_data
    from trend_detective import acquire

    catalog_all = acquire.list_variables(available_only=False)
    catalog = acquire.list_variables(available_only=True)
    exclude = set(COUNTRY_EXCLUDE)
    if COUNTRY_VARIABLES == "all":
        requested = list(catalog)
    else:
        requested = list(COUNTRY_VARIABLES)
    for vid in regional_only_ids(catalog):
        if vid not in requested and vid not in exclude:
            requested.append(vid)

    jobs: list = []
    items: list[dict] = []
    seen: set[str] = set()

    def record(vid: str, status: str, message: str, kind: str = "variable", store=None) -> None:
        items.append({"kind": kind, "id": vid, "store": store, "status": status, "message": message})

    # Catalog entries with no reader: list them explicitly on the fast stage when fetching "all".
    if not slow and COUNTRY_VARIABLES == "all":
        for vid, v in catalog_all.items():
            if not v.available:
                record(vid, "unsupported", "no reader in the repo yet")
                seen.add(vid)

    for vid in requested:
        if vid in seen:
            continue
        entry = catalog.get(vid) or catalog_all.get(vid)
        if entry is None:
            record(vid, "unsupported", f"{vid!r} is not in the variable catalog")
            seen.add(vid)
            continue
        if vid in exclude:
            record(vid, "skipped", "listed in COUNTRY_EXCLUDE")
            seen.add(vid)
            continue
        if not entry.available:
            record(vid, "unsupported", "no reader in the repo yet")
            seen.add(vid)
            continue
        is_slow = vid in COUNTRY_SLOW
        if is_slow != slow:
            continue
        jobs.append(build_data.Job("variable", country, vid, needs_login=entry.needs_login))
        seen.add(vid)

    if not slow:
        login = [j for j in jobs if j.needs_login]
        jobs = [j for j in jobs if not j.needs_login]
        jobs += [
            build_data.Job("input", country, p, store=s, how=h) for p, s, h in COUNTRY_INPUTS
        ]
        jobs += login  # POWER first (fast, no login), then GRACE / NDVI
    return jobs, items


def country_jobs(country: str, *, slow: bool = False):
    """Runnable jobs for one country stage (skipped / unsupported items are in country_plan)."""
    jobs, _ = country_plan(country, slow=slow)
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


def _unknown_country_item(country: str) -> dict:
    return {
        "kind": "country",
        "id": country,
        "status": "error",
        "message": (
            f"{country!r} is not in acquire.list_regions(); add a preset to "
            "data/catalog/regions.yaml before listing it in COUNTRIES"
        ),
    }


def run_country(
    data_dir: Path,
    country: str,
    *,
    slow: bool = False,
    has_token: bool = False,
    dry_run: bool = False,
    pre_items: list[dict] | None = None,
) -> list[dict]:
    import build_data
    from trend_detective import acquire

    stage = f"{country}_slow" if slow else country
    stage_dir = data_dir / country
    regions = acquire.list_regions()
    if country not in regions:
        item = _unknown_country_item(country)
        if dry_run:
            print(f"{stage:12} ERROR    {item['message']}")
            return [item]
        started = _now()
        write_stage_status(stage_dir, stage, "failed", [item], started)
        log.error("%s", item["message"])
        return [item]
    jobs, planned = country_plan(country, slow=slow)
    results = list(pre_items or []) + list(planned)
    if dry_run:
        for r in results:
            print(f"{stage:12} {r['status']:8} {r['id']:32} {r.get('message') or ''}")
        for j in jobs:
            print(f"{stage:12} {j.kind:8} {j.name:32} {'login' if j.needs_login else ''}")
            results.append(
                {
                    "kind": j.kind,
                    "id": j.name,
                    "store": j.store,
                    "status": "planned",
                    "message": "login" if j.needs_login else "",
                }
            )
        return results
    use_cache_root(stage_dir)
    remove_orphans(stage_dir)
    if not slow:
        bbox = regions[country].get("bbox")
        n = seed_from_repo(stage_dir, "earthdata", bbox=bbox)
        if n:
            log.info("seeded %d committed Earthdata cache files from the repo", n)
    started, labels = _now(), {}
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
        postprocess_country(stage_dir, results, country)
    except Exception as exc:  # noqa: BLE001
        log.error("postprocess_country failed: %s: %s", type(exc).__name__, exc)
    failed = [r for r in results if r["status"] == "error"]
    write_stage_status(stage_dir, stage, "failed" if failed else "done", results, started)
    return results


def skip_slow_without_token(data_dir: Path, country: str, *, dry_run: bool = False) -> list[dict]:
    """Record every slow item as skipped instead of omitting the stage."""
    msg = "Earthdata login needed and no EARTHDATA_TOKEN configured"
    jobs, planned = country_plan(country, slow=True)
    results = list(planned) + [
        {
            "kind": j.kind,
            "id": j.name,
            "store": j.store,
            "status": "skipped",
            "message": msg,
        }
        for j in jobs
    ]
    if dry_run:
        for r in results:
            print(f"{country + '_slow':12} {r['status']:8} {r['id']:32} {r.get('message') or ''}")
        return results
    log.info("stage %s_slow: skipped (needs Earthdata token)", country)
    write_stage_status(data_dir / country, f"{country}_slow", "done", results, _now())
    return results


def run_world_removed(data_dir: Path, *, dry_run: bool = False) -> list[dict]:
    """Compatibility stub: older daemons may still invoke ``--stage world``."""
    msg = (
        "worldwide fetch removed; the loader no longer builds global grids. "
        f"Existing files in {data_dir / 'world'} were left in place and are not updated"
    )
    log.info("%s", msg)
    if dry_run:
        print(f"world        skipped  {msg}")
    return [{"kind": "stage", "id": "world", "status": "skipped", "message": msg}]


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
    p.add_argument("--stage", choices=[*stage_names(), "all", "world"], default="all")
    p.add_argument("--dry-run", action="store_true", help="list what would be fetched and exit")
    p.add_argument(
        "--lock",
        type=Path,
        default=os.environ.get("SPACEAPPS_RUN_LOCK") or None,
        help="lock file shared with the daemon so runs never overlap (default $SPACEAPPS_RUN_LOCK)",
    )
    args = p.parse_args(argv)
    logging.Formatter.converter = time.gmtime  # log times in UTC, marked with Z
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)sZ %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    data_dir = (args.data_dir or default_data_dir()).resolve()
    stages = stage_names() if args.stage == "all" else (args.stage,)

    lock_fh = None
    if args.lock and not args.dry_run:
        from file_lock import lock  # fcntl on Linux/macOS, msvcrt on Windows

        lock_fh = Path(args.lock).open("a")  # noqa: SIM115 - held until the process exits
        try:
            lock(lock_fh, blocking=False)
        except BlockingIOError:
            log.info("another loader run holds %s; waiting for it to finish", args.lock)
            lock(lock_fh)
    has_token = False if args.dry_run else earthdata_available()
    if not args.dry_run:
        log.info("data dir %s; repo %s at %s", data_dir, REPO_ROOT, (_git_commit() or "?")[:10])
        log.info(
            "Earthdata: %s",
            "token found (GRACE, NDVI, NO2 will be fetched)"
            if has_token
            else "no EARTHDATA_TOKEN / ~/.netrc entry: login-only items are skipped (cached copies kept)",
        )
        log.info("countries: %s", ", ".join(COUNTRIES) or "(none)")
    code = 0
    for stage in stages:
        t0 = time.perf_counter()
        log.info("=== stage %s: start", stage)
        if stage == "world":
            results = run_world_removed(data_dir, dry_run=args.dry_run)
        else:
            country, slow = parse_stage(stage)
            if slow and not has_token and not args.dry_run:
                results = skip_slow_without_token(data_dir, country)
            else:
                results = run_country(
                    data_dir, country, slow=slow, has_token=has_token, dry_run=args.dry_run
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
