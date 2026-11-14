"""Tests for scripts/build_all.py (catalog `convert`, Q1). SI-assisted, pending team review."""
import importlib.util
from pathlib import Path

import pytest

_p = Path(__file__).with_name("build_all.py")
_s = importlib.util.spec_from_file_location("build_all", _p)
ba = importlib.util.module_from_spec(_s); _s.loader.exec_module(ba)


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
