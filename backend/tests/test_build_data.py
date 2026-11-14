"""Offline tests for scripts/build_data.py (no network, never touches the real data/cache)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from trend_detective import acquire
from trend_detective.earthdata import NotCachedError

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_data.py"


@pytest.fixture(scope="module")
def bd():
    spec = importlib.util.spec_from_file_location("build_data", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_data"] = mod  # dataclasses resolve their module through sys.modules
    try:
        spec.loader.exec_module(mod)
        yield mod
    finally:
        sys.modules.pop("build_data", None)


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    """Any accidental cache access goes to tmp_path, not the repo."""
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))


def _var(vid: str, reader: str = "power_zarr", login: bool = False) -> acquire.Variable:
    access = {"reader": reader, "store": "merra2", "variable": vid.upper()}
    if login:
        access["login"] = "earthdata"
    return acquire.Variable(vid, vid, "", "", "1", "", access, {})


CATALOG = {"temp": _var("temp"), "ice": _var("ice"), "ndvi": _var("ndvi", "modis_ndvi", login=True)}

JOBS_YAML = """
regions: [r1, r2]
matrix:
  variables: all
  exclude_variables: [ice]
inputs:
  - {parameter: T2M_MAX, store: merra2_daily, how: mean}
  - {parameter: PRECTOTCORR, store: merra2_daily, how: sum, regions: [r1]}
"""


def _monthly(n: int = 240, from_cache: bool = True) -> pd.Series:
    rng = np.random.default_rng(0)
    idx = pd.date_range("2001-01-01", periods=n, freq="MS")
    s = pd.Series(10 + np.sin(np.arange(n)) + rng.normal(0, 1, n), index=idx)
    s.attrs.update({"from_cache": from_cache, "assessment": acquire.assess(s)})
    return s


def _daily(days: int = 3650) -> pd.Series:
    rng = np.random.default_rng(1)
    idx = pd.date_range("2001-01-01", periods=days, freq="D")
    s = pd.Series(rng.normal(5, 3, days), index=idx)
    s.attrs["from_cache"] = False
    return s


@pytest.fixture
def spec(bd, tmp_path):
    path = tmp_path / "build.yaml"
    path.write_text(JOBS_YAML, encoding="utf-8")
    return bd.load_jobs(path)


# --- job parsing and expansion ----------------------------------------------------------------

def test_load_jobs_validates(bd, tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("regions: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="regions"):
        bd.load_jobs(bad)
    bad.write_text("regions: [a]\ninputs:\n  - {parameter: T2M}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="store"):
        bd.load_jobs(bad)
    bad.write_text("regions: [a]\ninputs:\n  - {parameter: T2M, store: s, how: max}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="how"):
        bd.load_jobs(bad)


def test_default_job_list_parses(bd):
    spec = bd.load_jobs(bd.DEFAULT_JOBS)
    assert spec["regions"] == ["south_ukraine", "ukraine", "north_europe", "south_europe"]
    assert set(spec["regions"]) <= set(acquire.list_regions())
    assert [i["parameter"] for i in spec["inputs"]] == ["T2M_MAX", "T2M_MIN", "PRECTOTCORR"]
    assert all(i["store"] == "merra2_daily" for i in spec["inputs"])


def test_expand_matrix_and_inputs(bd, spec):
    jobs = bd.expand_jobs(spec, catalog=CATALOG)
    variables = [j for j in jobs if j.kind == "variable"]
    inputs = [j for j in jobs if j.kind == "input"]
    assert [(j.region, j.name) for j in variables] == [
        ("r1", "temp"), ("r1", "ice"), ("r1", "ndvi"), ("r2", "temp"), ("r2", "ice"), ("r2", "ndvi")]
    assert [j.excluded for j in variables if j.name == "ice"] == [True, True]
    assert all(j.needs_login == (j.name == "ndvi") for j in variables)
    assert [(j.region, j.name, j.how) for j in inputs] == [
        ("r1", "T2M_MAX", "mean"), ("r2", "T2M_MAX", "mean"), ("r1", "PRECTOTCORR", "sum")]


def test_expand_only_and_explicit_list(bd, spec):
    jobs = bd.expand_jobs(spec, catalog=CATALOG, only=["r9"])
    assert {j.region for j in jobs} == {"r9"}
    spec = spec | {"matrix": {"variables": ["temp"]}}
    assert [j.name for j in bd.expand_jobs(spec, catalog=CATALOG) if j.kind == "variable"] == ["temp", "temp"]
    with pytest.raises(KeyError):
        bd.expand_jobs(spec | {"matrix": {"variables": ["nope"]}}, catalog=CATALOG)


def test_default_matrix_uses_available_catalog(bd):
    jobs = bd.expand_jobs(bd.load_jobs(bd.DEFAULT_JOBS))
    avail = acquire.list_variables(available_only=True)
    assert {j.name for j in jobs if j.kind == "variable"} == set(avail)
    assert len([j for j in jobs if j.kind == "variable"]) == 4 * len(avail)


# --- running: earthdata skipping, failures, exit code -----------------------------------------

def test_earthdata_not_cached_is_skipped_not_error(bd, monkeypatch):
    calls = []

    def fake_get_series(vid, region, *, allow_login_fetch=False, refresh=False):
        calls.append((vid, allow_login_fetch, refresh))
        raise NotCachedError("not in cache")

    monkeypatch.setattr(acquire, "get_series", fake_get_series)
    job = bd.Job("variable", "r1", "ndvi", needs_login=True)
    r = bd.run_job(job, refresh=True)
    assert r.status == "not cached" and not r.is_error
    assert calls == [("ndvi", False, False)]  # no login, no refresh of a login-only series
    r = bd.run_job(job, refresh=True, with_earthdata=True)
    assert r.is_error  # with a login a missing cache is a real failure
    assert calls[-1] == ("ndvi", True, True)


def test_earthdata_served_from_cache(bd, monkeypatch):
    monkeypatch.setattr(acquire, "get_series", lambda *a, **k: _monthly(from_cache=True))
    r = bd.run_job(bd.Job("variable", "r1", "ndvi", needs_login=True))
    assert (r.status, r.origin, r.n, r.n_unit) == ("ok", "cached", 240, "mo")
    assert r.period == "2001-01..2020-12"


def test_failures_do_not_stop_run_and_set_exit_code(bd, monkeypatch, spec):
    def fake_get_series(vid, region, **kw):
        if vid == "temp" and region == "r2":
            raise ValueError("no data for 'TEMP' in region 'r2' (ocean)")
        if vid == "ndvi":
            raise NotCachedError("x")
        return _monthly(from_cache=False)

    def fake_input(parameter, region, *, store, refresh=False):
        if parameter == "PRECTOTCORR":
            raise ConnectionError("connection reset")
        return _daily()

    monkeypatch.setattr(acquire, "get_series", fake_get_series)
    monkeypatch.setattr(acquire, "get_input_series", fake_input)
    lines: list[str] = []
    results = bd.run_jobs(bd.expand_jobs(spec, catalog=CATALOG), echo=lines.append)
    status = {(r.job.region, r.job.name): r.status for r in results}
    assert status == {
        ("r1", "temp"): "ok", ("r1", "ice"): "skipped", ("r1", "ndvi"): "not cached",
        ("r2", "temp"): "no data", ("r2", "ice"): "skipped", ("r2", "ndvi"): "not cached",
        ("r1", "T2M_MAX"): "ok", ("r2", "T2M_MAX"): "ok", ("r1", "PRECTOTCORR"): "error",
    }
    assert len(lines) == len(results)
    daily = next(r for r in results if r.job.name == "T2M_MAX")
    assert (daily.n, daily.n_unit, daily.origin) == (3650, "d", "fetched")
    assert daily.period.startswith("2001-01-01..")
    out: list[str] = []
    assert bd.summarise(results, echo=out.append) == 1
    assert any("FAILED r1 PRECTOTCORR" in line and "ConnectionError" in line for line in out)
    ok_only = [r for r in results if r.status != "error"]
    assert bd.summarise(ok_only, echo=lambda _: None) == 0


def test_main_dry_run_fetches_nothing(bd, monkeypatch, tmp_path, capsys, spec):
    def boom(*a, **k):
        raise AssertionError("dry run must not fetch")

    monkeypatch.setattr(acquire, "get_series", boom)
    monkeypatch.setattr(acquire, "get_input_series", boom)
    monkeypatch.setattr(bd, "_power_cache_path", lambda job: tmp_path / "missing.csv")
    monkeypatch.setattr(bd, "expand_jobs", lambda s, only=None: [
        bd.Job("variable", "r1", "temp"), bd.Job("variable", "r1", "ndvi", needs_login=True)])
    jobs = tmp_path / "build.yaml"
    jobs.write_text(JOBS_YAML, encoding="utf-8")
    assert bd.main(["--jobs", str(jobs), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "would fetch" in out and "Earthdata" in out
    assert not (tmp_path / "cache" / bd.MANIFEST_NAME).exists()


def test_main_build_exit_code_and_manifest_in_tmp(bd, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(bd, "default_cache_root", lambda: tmp_path / "cache")
    (tmp_path / "cache").mkdir()
    monkeypatch.setattr(bd, "expand_jobs", lambda s, only=None: [bd.Job("variable", "r1", "temp")])
    monkeypatch.setattr(acquire, "get_series", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    jobs = tmp_path / "build.yaml"
    jobs.write_text(JOBS_YAML, encoding="utf-8")
    assert bd.main(["--jobs", str(jobs)]) == 1
    assert (tmp_path / "cache" / bd.MANIFEST_NAME).exists()
    assert "FAILED r1 temp" in capsys.readouterr().out


# --- manifest ---------------------------------------------------------------------------------

def _write_csv(path: Path, text: str, prov: dict | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    if prov is not None:
        path.with_name(path.name + ".provenance.json").write_text(json.dumps(prov), encoding="utf-8")


def test_write_manifest(bd, tmp_path):
    root = tmp_path / "cache"
    csv_a = "time,value\n2001-01-01,1.5\n2001-02-01,2.5\n2001-03-01,3.5\n"
    prov = {"variable": {"variable": "T2M", "source": "merra2"}, "region_name": "Ukraine",
            "bbox": {"lat_min": 44.0, "lat_max": 52.5, "lon_min": 22.0, "lon_max": 40.5},
            "land_only": True, "git_commit": "abc1234", "accessed": "2026-11-14T10:00:00Z"}
    _write_csv(root / "power_zarr" / "merra2_T2M_x.csv", csv_a, prov)
    _write_csv(root / "earthdata" / "mod13c2_ndvi_y.csv", "month,value,valid_fraction\n2000-02-01,,0.4\n",
               None)
    _write_csv(root / "raw" / "big.csv", "a\n1\n", None)  # raw is not frozen

    m = bd.write_manifest(root, freeze_date="2026-11-14")
    assert (m["freeze_date"], m["n_files"]) == ("2026-11-14", 2)
    paths = [f["path"] for f in m["files"]]
    assert paths == ["earthdata/mod13c2_ndvi_y.csv", "power_zarr/merra2_T2M_x.csv"]
    a = m["files"][1]
    assert a["sha256"] == hashlib.sha256(csv_a.encode()).hexdigest()
    assert (a["rows"], a["first"], a["last"]) == (3, "2001-01-01", "2001-03-01")
    assert (a["variable"], a["region_name"], a["land_only"]) == ("T2M", "Ukraine", True)
    assert a["bbox"]["lat_max"] == 52.5
    assert (a["git_commit"], a["accessed"]) == ("abc1234", "2026-11-14T10:00:00Z")
    b = m["files"][0]
    assert (b["rows"], b["first"], b["has_provenance"], b["variable"]) == (1, "2000-02-01", False, None)
    assert m["total_bytes"] == sum((root / p).stat().st_size for p in paths)

    text = (root / bd.MANIFEST_NAME).read_text(encoding="utf-8")
    assert json.loads(text) == m
    assert text == json.dumps(m, indent=2, sort_keys=True) + "\n"
    bd.write_manifest(root, freeze_date="2026-11-14")
    assert (root / bd.MANIFEST_NAME).read_text(encoding="utf-8") == text  # deterministic
    assert bd.write_manifest(root)["n_files"] == 2  # MANIFEST.json itself is not listed


def test_write_manifest_empty_cache(bd, tmp_path):
    m = bd.write_manifest(tmp_path, freeze_date="2026-11-14")
    assert (m["n_files"], m["total_bytes"], m["files"]) == (0, 0, [])


def test_manifest_skips_unfinished_partial_files(bd, tmp_path):
    d = tmp_path / "earthdata"
    d.mkdir()
    (d / "omno2d_x.csv.partial.csv").write_text("date,value\n2005-01-01,1\n", encoding="utf-8")
    assert bd.build_manifest(tmp_path)["n_files"] == 0


def test_manifest_lists_grids_and_preset_ids(bd, tmp_path):
    """B1-02: committed map grids are frozen too; B1-03: series carry the preset id."""
    root = tmp_path / "cache"
    prov = {"variable": {"variable": "T2M", "source": "merra2"}, "region_name": "Ukraine",
            "bbox": {"lat_min": 44.0, "lat_max": 52.5, "lon_min": 22.0, "lon_max": 40.5}}
    _write_csv(root / "power_zarr" / "merra2_T2M_x.csv", "time,value\n2001-01-01,1.5\n", prov)
    grid = root / "grids" / "merra2_T2M_2deg.nc"
    grid.parent.mkdir(parents=True)
    grid.write_bytes(b"CDF\x01fake")
    gprov = {"variable": {"variable": "T2M", "source": "merra2"}, "n_months": 549,
             "time_range": {"start": "1981-01", "end": "2026-09"}}
    grid.with_name(grid.name + ".provenance.json").write_text(json.dumps(gprov), encoding="utf-8")
    m = bd.build_manifest(root, freeze_date="2026-11-14")
    by_path = {f["path"]: f for f in m["files"]}
    assert set(by_path) == {"grids/merra2_T2M_2deg.nc", "power_zarr/merra2_T2M_x.csv"}
    g = by_path["grids/merra2_T2M_2deg.nc"]
    assert (g["kind"], g["rows"], g["first"], g["last"]) == ("grid", 549, "1981-01", "2026-09")
    assert by_path["power_zarr/merra2_T2M_x.csv"]["region_id"] == "ukraine"
    assert "grids" in m["directories"]
