"""Tests for scripts/check_cache.py on a small fake cache (offline)."""

import json
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1] / "backend")]

import build_data  # noqa: E402
import check_cache  # noqa: E402

PROV = {
    "source": "fake",
    "variable": {"variable": "T2M"},
    "accessed": "2026-11-14",
    "processing": ["x"],
    "script": "x.py",
}


def fake_cache(root: Path) -> Path:
    d = root / "power_zarr"
    d.mkdir(parents=True)
    (d / "merra2_T2M_abc.csv").write_text("month,value\n2000-01-01,1.0\n")
    (d / "merra2_T2M_abc.csv.provenance.json").write_text(json.dumps(PROV))
    build_data.write_manifest(root, "2026-11-14")
    return d


def test_clean_cache_passes(tmp_path):
    fake_cache(tmp_path)
    assert check_cache.check_manifest(tmp_path) == []
    assert check_cache.check_sidecars(tmp_path) == []
    assert check_cache.check_secrets(tmp_path) == []


def test_edited_file_and_unlisted_file_are_caught(tmp_path):
    d = fake_cache(tmp_path)
    (d / "merra2_T2M_abc.csv").write_text("month,value\n2000-01-01,2.0\n")  # same size, new content
    (d / "merra2_PS_new.csv").write_text("month,value\n")
    problems = check_cache.check_manifest(tmp_path)
    assert any("content changed" in p for p in problems) and any("not in MANIFEST" in p for p in problems)
    assert any("no provenance sidecar" in p for p in check_cache.check_sidecars(tmp_path))


def test_incomplete_sidecar_and_orphan_are_caught(tmp_path):
    d = fake_cache(tmp_path)
    (d / "merra2_T2M_abc.csv.provenance.json").write_text(json.dumps({"source": "fake"}))
    (d / "gone.csv.provenance.json").write_text(json.dumps(PROV))
    problems = check_cache.check_sidecars(tmp_path)
    assert any("lacks variable" in p for p in problems) and any("orphan" in p for p in problems)


def test_token_in_sidecar_is_caught(tmp_path):
    d = fake_cache(tmp_path)
    leaked = PROV | {"note": "Authorization: Bearer " + "a" * 30}
    (d / "merra2_T2M_abc.csv.provenance.json").write_text(json.dumps(leaked))
    assert check_cache.check_secrets(tmp_path)


def test_repository_cache_passes():
    """The committed cache itself: the data-freeze gate CI runs."""
    assert check_cache.main([]) == 0
