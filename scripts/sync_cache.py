r"""Sync the large cache files (world-map grids) with the project's data store on Google Cloud
Storage (ADR-010; supersedes "grids in git" from ADR-006).

What lives where:
- git: data/cache/MANIFEST.json (path, size, sha256 of every cached file), every provenance
  sidecar, and the small regional CSV series.
- the bucket: the large files (``REMOTE_GLOBS``, now the 2° grids), stored by content as
  ``gs://<bucket>/sha256/<sha256>``. Objects are immutable: a refreshed grid is a new object, so
  every git commit's MANIFEST still points at the exact bytes it was built from.

Downloads use plain HTTPS from a public-read bucket: no login, no token, works in CI and for
judges. Uploads need ``gcloud`` logged in with write access to the bucket. Every file is checked
against the MANIFEST sha256 before it is used or uploaded.

Usage (PowerShell or bash, from the repo root):
    python scripts/sync_cache.py status        # what is local, what is in the bucket
    python scripts/sync_cache.py pull          # download missing or changed large files
    python scripts/sync_cache.py push          # upload large files the bucket does not have yet
Options: --bucket NAME (default: env TD_DATA_BUCKET or trend-detective-data), --cache-dir PATH.

SI-assisted (Claude, Anthropic); pending team review (see docs/08-si-usage-log.md).
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = ROOT / "data" / "cache"
DEFAULT_BUCKET = os.environ.get("TD_DATA_BUCKET", "trend-detective-data")
# Manifest paths (relative to the cache root) kept in the bucket instead of git.
REMOTE_GLOBS = ("grids/*.nc",)
PUBLIC_URL = "https://storage.googleapis.com/{bucket}/sha256/{sha}"
CHUNK = 1 << 20


@dataclass
class Entry:
    path: str
    sha256: str
    bytes: int


def remote_entries(cache_root: Path) -> list[Entry]:
    """MANIFEST entries that belong in the bucket (large files)."""
    manifest = json.loads((cache_root / "MANIFEST.json").read_text(encoding="utf-8"))
    out = []
    for f in manifest["files"]:
        if any(fnmatch.fnmatch(f["path"], g) for g in REMOTE_GLOBS):
            out.append(Entry(f["path"], f["sha256"], int(f["bytes"])))
    return out


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def local_state(cache_root: Path, e: Entry) -> str:
    p = cache_root / e.path
    if not p.is_file():
        return "missing"
    if p.stat().st_size != e.bytes or sha256_file(p) != e.sha256:
        return "differs"
    return "ok"


def url(bucket: str, sha: str) -> str:
    return PUBLIC_URL.format(bucket=bucket, sha=sha)


def remote_has(bucket: str, e: Entry, session=requests) -> bool:
    r = session.head(url(bucket, e.sha256), timeout=30)
    if r.status_code == 200:
        return True
    if r.status_code == 404:
        return False
    raise RuntimeError(f"bucket check failed for {e.path}: HTTP {r.status_code}")


def download(bucket: str, e: Entry, dest: Path, session=requests) -> None:
    """Stream to a temp file, verify size and sha256, then move into place (never a half file)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    h = hashlib.sha256()
    n = 0
    with session.get(url(bucket, e.sha256), stream=True, timeout=60) as r:
        if r.status_code != 200:
            raise RuntimeError(f"download failed for {e.path}: HTTP {r.status_code}")
        with tmp.open("wb") as fh:
            for block in r.iter_content(CHUNK):
                fh.write(block)
                h.update(block)
                n += len(block)
    if n != e.bytes or h.hexdigest() != e.sha256:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"{e.path}: downloaded bytes do not match MANIFEST (size {n}, sha {h.hexdigest()[:12]})"
        )
    os.replace(tmp, dest)


def upload(bucket: str, e: Entry, src: Path) -> None:
    gcloud = shutil.which("gcloud")
    if not gcloud:
        raise RuntimeError("gcloud not found; install the Google Cloud CLI and log in to upload")
    subprocess.run(
        [
            gcloud,
            "storage",
            "cp",
            str(src),
            f"gs://{bucket}/sha256/{e.sha256}",
            "--content-type=application/x-netcdf",
            "--cache-control=public, max-age=31536000, immutable",
            f"--custom-metadata=path={e.path}",
        ],
        check=True,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["status", "pull", "push"])
    ap.add_argument("--bucket", default=DEFAULT_BUCKET)
    ap.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    args = ap.parse_args(argv)
    entries = remote_entries(args.cache_dir)
    failed = 0

    for e in entries:
        state = local_state(args.cache_dir, e)
        if args.command == "status":
            remote = "in bucket" if remote_has(args.bucket, e) else "NOT in bucket"
            print(f"{state:8s} {remote:13s} {e.bytes / 1e6:6.1f} MB  {e.path}")
        elif args.command == "pull":
            if state == "ok":
                continue
            print(f"pull {e.path} ({e.bytes / 1e6:.1f} MB, local: {state})")
            try:
                download(args.bucket, e, args.cache_dir / e.path)
            except RuntimeError as exc:
                print(f"  ERROR {exc}", file=sys.stderr)
                failed += 1
        else:  # push
            if state != "ok":
                print(
                    f"  ERROR {e.path}: local file is {state}; rebuild it or fix MANIFEST first",
                    file=sys.stderr,
                )
                failed += 1
                continue
            if remote_has(args.bucket, e):
                continue
            print(f"push {e.path} ({e.bytes / 1e6:.1f} MB)")
            upload(args.bucket, e, args.cache_dir / e.path)

    print(f"{args.command}: {len(entries)} large files in MANIFEST, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
