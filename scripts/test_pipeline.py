"""Offline tests for the field-team pipeline (scripts/pipeline_load.py, scripts/pipeline_daemon.py)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pipeline_daemon as pd_
import pipeline_load as pl


def test_ukraine_jobs_order_and_scope():
    jobs = pl.ukraine_jobs("all", [], slow=False)
    assert {j.region for j in jobs} == {"ukraine"}
    names = [j.name for j in jobs]
    assert "air_temperature_power" in names and "no2_tropospheric_omi" not in names
    first_login = next(i for i, j in enumerate(jobs) if j.needs_login)
    assert all(j.needs_login for j in jobs[first_login:])  # POWER and inputs before login data
    assert {"T2M_MAX", "T2M_MIN", "PRECTOTCORR"} <= {j.name for j in jobs if j.kind == "input"}
    assert [j.name for j in pl.ukraine_jobs("all", [], slow=True)] == pl.UKRAINE_SLOW


def test_ukraine_preset_is_canonical_box_with_crimea():
    from trend_detective import acquire

    e = acquire.list_regions()[pl.UKRAINE_REGION]
    assert e["bbox"] == [22.0, 44.0, 40.5, 52.5] and e["land_only"] is True


def test_world_variables_are_monthly_power():
    pairs = pl.world_variables()
    assert ("merra2", "T2M") in pairs and ("syn1deg", "ALLSKY_SFC_SW_DWN") in pairs
    assert all(src in ("merra2", "syn1deg", "imerg") for src, _ in pairs)
    assert pl.world_variables(["TQV", "imerg:IMERG_PRECTOT"]) == [
        ("merra2", "TQV"),
        ("imerg", "IMERG_PRECTOT"),
    ]


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
    d = __import__("json").loads((tmp_path / "status.json").read_text())
    assert d["steps"]["ukraine"]["state"] == "done" and "finished" in d["steps"]["ukraine"]
