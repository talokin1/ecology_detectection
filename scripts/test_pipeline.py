"""Offline tests for the field-team pipeline (scripts/pipeline_load.py, scripts/pipeline_daemon.py)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pipeline_daemon as pd_
import pipeline_load as pl


def test_ukraine_jobs_order_and_scope():
    jobs = pl.country_jobs("ukraine", slow=False)
    assert {j.region for j in jobs} == {"ukraine"}
    names = [j.name for j in jobs]
    assert "air_temperature_power" in names and "no2_tropospheric_omi" not in names
    assert "ndvi_modis" in names  # regional-only; fetched per country in the fast stage
    first_login = next(i for i, j in enumerate(jobs) if j.needs_login)
    assert all(j.needs_login for j in jobs[first_login:])  # POWER and inputs before login data
    assert {"T2M_MAX", "T2M_MIN", "PRECTOTCORR"} <= {j.name for j in jobs if j.kind == "input"}
    slow = pl.country_jobs("ukraine", slow=True)
    assert [j.name for j in slow] == pl.COUNTRY_SLOW
    assert "no2_tropospheric_omi" in {j.name for j in slow}


def test_ukraine_preset_is_canonical_box_with_crimea():
    from trend_detective import acquire

    e = acquire.list_regions()[pl.UKRAINE_REGION]
    assert e["bbox"] == [22.0, 44.0, 40.5, 52.5] and e["land_only"] is True


def test_countries_list_and_stages():
    assert pl.COUNTRIES == [pl.UKRAINE_REGION]
    assert pl.stage_names() == ("ukraine", "ukraine_slow")
    assert "world" not in pl.stage_names()
    assert pl.parse_stage("ukraine") == ("ukraine", False)
    assert pl.parse_stage("ukraine_slow") == ("ukraine", True)
    assert pd_.data_stages() == pl.stage_names()


def test_regional_only_datasets_are_included():
    from trend_detective import acquire

    catalog = acquire.list_variables(available_only=True)
    ids = pl.regional_only_ids(catalog)
    assert "ndvi_modis" in ids and "no2_tropospheric_omi" in ids
    # Even if COUNTRY_VARIABLES is a narrow list, regional-only ids are still planned.
    orig = pl.COUNTRY_VARIABLES
    try:
        pl.COUNTRY_VARIABLES = ["air_temperature_power"]
        jobs_fast, _ = pl.country_plan("ukraine", slow=False)
        jobs_slow, _ = pl.country_plan("ukraine", slow=True)
        assert "ndvi_modis" in {j.name for j in jobs_fast}
        assert "no2_tropospheric_omi" in {j.name for j in jobs_slow}
        assert "air_temperature_power" in {j.name for j in jobs_fast}
    finally:
        pl.COUNTRY_VARIABLES = orig


def test_unsupported_and_skipped_appear():
    _, planned = pl.country_plan("ukraine", slow=False)
    unsupported = {r["id"]: r for r in planned if r["status"] == "unsupported"}
    assert "air_temperature_merra2" in unsupported  # catalog stub, no reader
    orig = list(pl.COUNTRY_EXCLUDE)
    try:
        pl.COUNTRY_EXCLUDE = ["ndvi_modis"]
        _, planned = pl.country_plan("ukraine", slow=False)
        skipped = {r["id"]: r for r in planned if r["status"] == "skipped"}
        assert skipped["ndvi_modis"]["message"] == "listed in COUNTRY_EXCLUDE"
        jobs, _ = pl.country_plan("ukraine", slow=False)
        assert "ndvi_modis" not in {j.name for j in jobs}
    finally:
        pl.COUNTRY_EXCLUDE = orig


def test_unknown_country_fails_in_status(tmp_path):
    results = pl.run_country(tmp_path, "not_a_real_country", dry_run=True)
    assert results[0]["status"] == "error" and "list_regions" in results[0]["message"]
    results = pl.run_country(tmp_path, "not_a_real_country")
    status_path = tmp_path / "not_a_real_country" / "STAGE_STATUS.not_a_real_country.json"
    assert status_path.exists()
    d = json.loads(status_path.read_text())
    assert d["state"] == "failed" and d["items"][0]["status"] == "error"


def test_stage_status_files_do_not_overwrite(tmp_path):
    stage_dir = tmp_path / "ukraine"
    pl.write_stage_status(
        stage_dir,
        "ukraine",
        "done",
        [{"id": "air_temperature_power", "status": "ok"}],
        "2026-11-14T00:00:00Z",
    )
    pl.write_stage_status(
        stage_dir,
        "ukraine_slow",
        "running",
        [{"id": "no2_tropospheric_omi", "status": "ok"}],
        "2026-11-14T00:01:00Z",
    )
    fast = json.loads((stage_dir / "STAGE_STATUS.ukraine.json").read_text())
    slow = json.loads((stage_dir / "STAGE_STATUS.ukraine_slow.json").read_text())
    combined = json.loads((stage_dir / "STAGE_STATUS.json").read_text())
    assert fast["state"] == "done" and {i["id"] for i in fast["items"]} == {"air_temperature_power"}
    assert slow["state"] == "running" and {i["id"] for i in slow["items"]} == {"no2_tropospheric_omi"}
    assert "ukraine" in combined["stages"] and "ukraine_slow" in combined["stages"]
    assert {i["id"] for i in combined["stages"]["ukraine"]["items"]} == {"air_temperature_power"}
    assert combined["state"] == "running"  # slow still running
    # daemon summary reads the per-stage file, not a clobbered combined file
    cfg = pd_.Config({"SPACEAPPS_HOME": str(tmp_path), "SPACEAPPS_DATA_DIR": str(tmp_path)})
    assert pd_.stage_summary(cfg, "ukraine")["loader_state"] == "done"
    assert pd_.stage_summary(cfg, "ukraine_slow")["loader_state"] == "running"


def test_remove_orphans_and_retries(tmp_path, monkeypatch):
    d = tmp_path / "power_zarr"
    d.mkdir()
    (d / "a.csv").write_text("x")
    (d / "b.csv").write_text("x")
    (d / "b.csv.provenance.json").write_text("{}")
    assert pl.remove_orphans(tmp_path) == 1
    assert not (d / "a.csv").exists() and (d / "b.csv").exists()

    monkeypatch.setattr(pl.time, "sleep", lambda s: None)
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise OSError("boom")
        return "ok"

    assert pl.with_retries("t", flaky, retries=3) == "ok" and len(calls) == 3
    with pytest.raises(OSError):
        pl.with_retries("t", lambda: (_ for _ in ()).throw(OSError("x")), retries=1)


def test_seed_only_matching_box(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    src = repo / "data" / "cache" / "earthdata"
    src.mkdir(parents=True)
    box = {"lon_min": 22.0, "lat_min": 44.0, "lon_max": 40.5, "lat_max": 52.5}
    other = {"lon_min": 0.0, "lat_min": 0.0, "lon_max": 1.0, "lat_max": 1.0}
    for name, b in (("ua.csv", box), ("xx.csv", other)):
        (src / name).write_text("month,value\n")
        (src / f"{name}.provenance.json").write_text(__import__("json").dumps({"bbox": b}))
    monkeypatch.setattr(pl, "REPO_ROOT", repo)
    n = pl.seed_from_repo(tmp_path / "out", "earthdata", bbox=[22.0, 44.0, 40.5, 52.5])
    assert n == 2 and sorted(p.name for p in (tmp_path / "out" / "earthdata").iterdir()) == [
        "ua.csv",
        "ua.csv.provenance.json",
    ]


def test_sources_and_scrub():
    assert pd_.parse_sources("a=https://x/y.git#exp b=/srv/r#main") == [
        ("a", "https://x/y.git", "exp"),
        ("b", "/srv/r", "main"),
    ]
    with pytest.raises(ValueError):
        pd_.parse_sources("nobranch=/x")
    assert pd_.scrub("fatal: https://user:tok@github.com/x") == "fatal: https://***@github.com/x"


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _commit(repo, name, text="x"):
    (repo / name).write_text(text)
    _git(repo, "add", name)
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", f"add {name}")


def test_poll_fast_forward_dirty_and_diverged(tmp_path):
    up = tmp_path / "up"
    up.mkdir()
    _git(up, "init", "-q", "-b", "experimental")
    _commit(up, "a")
    cfg = pd_.Config(
        {
            "SPACEAPPS_HOME": str(tmp_path / "home"),
            "SPACEAPPS_SOURCES": f"up={up}#experimental",
        }
    )
    pd_.ensure_deploy(cfg)
    assert pd_.poll_and_update(cfg)["changed"] is False
    _commit(up, "b")
    r = pd_.poll_and_update(cfg)
    assert r["changed"] and (cfg.deploy / "b").exists()
    # uncommitted edit in the deploy checkout: never overwritten
    (cfg.deploy / "a").write_text("local edit")
    _commit(up, "c")
    r = pd_.poll_and_update(cfg)
    assert not r["changed"] and "uncommitted" in r["note"] and (cfg.deploy / "a").read_text() == "local edit"
    (cfg.deploy / "a").write_text("x")
    assert pd_.poll_and_update(cfg)["changed"]
    # diverged history (e.g. a force-push upstream): ignored, deploy stays
    _git(up, "reset", "-q", "--hard", "HEAD~2")
    _commit(up, "d")
    r = pd_.poll_and_update(cfg)
    assert not r["changed"] and "diverged" in r["note"] and (cfg.deploy / "c").exists()


def test_status_file(tmp_path):
    st = pd_.Status(tmp_path / "status.json")
    st.step("ukraine", "running")
    st.step("ukraine", "done", exit_code=0)
    d = json.loads((tmp_path / "status.json").read_text())
    assert d["steps"]["ukraine"]["state"] == "done" and "finished" in d["steps"]["ukraine"]
