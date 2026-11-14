"""Locations for the fetch scripts. No machine-specific absolute prefix.

UKRAINE_SAMPLES and GLOBAL_DATA override discovery. Otherwise this walks
parent directories for a folder of that name. Logs go under data/fetch/logs/.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

FETCH_DIR = Path(__file__).resolve().parent


def _find(folder: str, env: str) -> Path:
    if os.environ.get(env):
        return Path(os.environ[env])
    seen = set()
    for parent in FETCH_DIR.parents:
        for cand in (parent / folder, parent.parent / folder):
            if cand in seen:
                continue
            seen.add(cand)
            if cand.is_dir():
                return cand
    return Path(folder)


GLOBAL_DATA = _find("global_data", "GLOBAL_DATA")
UKRAINE_SAMPLES = _find("ukraine_samples", "UKRAINE_SAMPLES")
LOG_DIR = FETCH_DIR / "logs"
# Scratch space for probe caches (A1-11): $TC_SCRATCH, else the OS temp dir. No hard-coded /tmp.
SCRATCH = Path(os.environ.get("TC_SCRATCH") or tempfile.gettempdir()) / "team-context-fetch"


def data_root() -> Path:
    """Filesystem whose free space the fetchers check: $DATA_ROOT, else the GLOBAL_DATA parent."""
    return Path(os.environ.get("DATA_ROOT") or GLOBAL_DATA.resolve().parent)
