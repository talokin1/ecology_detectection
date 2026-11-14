"""Tests for scripts/build_all.py (catalog `convert`, Q1). SI-assisted, pending team review."""
import importlib.util
from pathlib import Path

import pytest

_p = Path(__file__).with_name("build_all.py")
_s = importlib.util.spec_from_file_location("build_all", _p)
ba = importlib.util.module_from_spec(_s)
_s.loader.exec_module(ba)


def test_convert_solar_and_kelvin():
    assert ba.compile_convert("x * 0.0864")(100.0) == pytest.approx(8.64)  # W/m^2 -> MJ/m^2/day
    assert ba.compile_convert("x - 273.15")(273.15) == pytest.approx(0.0)
    assert ba.compile_convert(None)(5) == 5


def test_convert_rejects_code():
    for bad in ("__import__('os')", "x.real", "y * 2", "[x]"):
        with pytest.raises((ValueError, SyntaxError)):
            ba.compile_convert(bad)


def test_mc4_gate_blocks_archive(tmp_path):
    p = ba.FORBIDDEN / "x.csv"
    with pytest.raises(PermissionError):
        ba.read_series(p)


def test_dry_run_builds_from_cache():
    built = ba.build(Path("unused"), dry_run=True)
    assert built and all(not b["cache_file"].startswith("team-context") for b in built)
    solar = [b for b in built if b["variable_id"] == "solar_radiation_power"]
    for b in solar:  # once the catalog has convert, values are display units
        if b["convert"]:
            assert b["units"] != b["source_units"]


def test_every_cached_catalog_variable_is_built():
    """Regression: GRACE, MODIS NDVI and OMI NO2 have no store/parameter and were skipped silently."""
    built = ba.build(Path("unused"), dry_run=True)
    ids = {b["variable_id"] for b in built}
    assert {"terrestrial_water_storage_grace", "ndvi_modis", "no2_tropospheric_omi"} <= ids
    manifest = __import__("json").loads((ba.CACHE / "MANIFEST.json").read_text())
    cached = {(f["source"], f["variable"]) for f in manifest["files"] if f.get("kind") == "series"}
    for var in ba.load_catalog():
        key = ba.manifest_key(var)
        if key in cached:
            assert var["id"] in ids, var["id"]


def test_records_carry_region_id_and_land_only():
    built = ba.build(Path("unused"), dry_run=True)
    ukr = [b for b in built if b["region_id"] == "ukraine" and b["variable_id"] == "air_temperature_power"]
    assert len(ukr) == 1 and ukr[0]["land_only"] is True and ukr[0]["bbox"]
    assert all(isinstance(b["land_only"], bool) for b in built)


def test_unknown_reader_fails_loudly():
    with pytest.raises(KeyError, match="READER_KEY"):
        ba.manifest_key({"id": "x", "access": {"reader": "new_reader"}})
