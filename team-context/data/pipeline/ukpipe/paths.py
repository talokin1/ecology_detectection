"""Resolve data and library locations without a machine-specific absolute prefix.

Environment overrides (all optional):
  UKRAINE_SAMPLES   regional extracts
  GLOBAL_DATA       global monthly archives
  TREND_STATS_PY    official Yue-Wang implementation (trend_stats.py)
  TREND_METHODS_PY  HAC / Hamed-Rao sensitivity library (trend_methods.py)

If an override is unset, this walks parent directories for a folder named
ukraine_samples or global_data, and for a checkout that contains
.claude/skills/trend-stats/scripts/trend_stats.py. The sensitivity library
is the vendored copy at pipeline/vendor/trend_methods.py, or team-context/stats/.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()


def _env_path(name: str) -> Path | None:
    val = os.environ.get(name)
    return Path(val) if val else None


def _named_dir(folder: str) -> Path | None:
    seen = set()
    for parent in _HERE.parents:
        for cand in (parent / folder, parent.parent / folder):
            if cand in seen:
                continue
            seen.add(cand)
            if cand.is_dir():
                return cand
    return None


def ukraine_samples() -> Path:
    found = _env_path("UKRAINE_SAMPLES") or _named_dir("ukraine_samples")
    if found is None:
        raise FileNotFoundError("Set UKRAINE_SAMPLES to the regional extract directory")
    return found


def global_data() -> Path:
    found = _env_path("GLOBAL_DATA") or _named_dir("global_data")
    if found is None:
        raise FileNotFoundError("Set GLOBAL_DATA to the global monthly archive")
    return found


def repo_root() -> Path | None:
    rel = Path(".claude") / "skills" / "trend-stats" / "scripts" / "trend_stats.py"
    seen = set()
    for parent in _HERE.parents:
        for base in (parent,):
            if base in seen:
                continue
            seen.add(base)
            if (base / rel).is_file():
                return base
        parent_dir = parent.parent
        if not parent_dir.is_dir():
            continue
        try:
            siblings = list(parent_dir.iterdir())
        except OSError:
            continue
        for sib in siblings:
            if sib in seen:
                continue
            seen.add(sib)
            if (sib / rel).is_file():
                return sib
    return None


def trend_stats_py() -> Path:
    env = _env_path("TREND_STATS_PY")
    if env is not None:
        return env
    root = repo_root()
    if root is None:
        raise FileNotFoundError("Set TREND_STATS_PY to trend_stats.py")
    return root / ".claude" / "skills" / "trend-stats" / "scripts" / "trend_stats.py"


def trend_methods_py() -> Path:
    env = _env_path("TREND_METHODS_PY")
    if env is not None:
        return env
    cands = [_HERE.parents[1] / "vendor" / "trend_methods.py"]
    for parent in _HERE.parents:
        cands.append(parent / "stats" / "trend_methods.py")
        cands.append(parent / "team-context" / "stats" / "trend_methods.py")
    for cand in cands:
        if cand.is_file():
            return cand
    raise FileNotFoundError("Set TREND_METHODS_PY to the vendored trend_methods.py")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod
