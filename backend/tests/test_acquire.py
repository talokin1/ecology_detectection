import numpy as np
import pandas as pd
import pytest
from trend_detective import acquire, grace, modis_ndvi, power_zarr
from trend_detective.earthdata import NotCachedError
from trend_detective.power_zarr import Region

VARIABLES = """
version: 0.1
variables:
  - id: temp
    name: Air temperature
    definition: How warm the air is.
    why_it_trends: Warming.
    source: power
    access: {reader: power_zarr, store: merra2, variable: T2M}
    units: degC  # comment is stripped
    period: 1981-present
  - id: ndvi
    name: Greenness
    definition: How green plants are.
    why_it_trends: Growing seasons.
    source: lp_daac
    access: {reader: modis_ndvi, login: earthdata}
    units: "1"
  - id: ozone
    name: Ozone
    definition: Ozone column.
    why_it_trends: Montreal Protocol.
    source: ges_disc
    access: {reader: none}
    units: DU
"""

REGIONS = """
version: 0.1
regions:
  - id: box
    name: Test box
    bbox: [10.0, 40.0, 20.0, 50.0]
"""


def monthly(n, start="1990-01-01", value=1.0):
    idx = pd.date_range(start, periods=n, freq="MS")
    return pd.Series(value + 0.01 * np.arange(n), index=idx)


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    (tmp_path / "variables.yaml").write_text(VARIABLES, encoding="utf-8")
    (tmp_path / "regions.yaml").write_text(REGIONS, encoding="utf-8")
    monkeypatch.setattr(acquire, "CATALOG_DIR", tmp_path)
    calls = []

    def fake_power(variable, region, source, refresh=False, land_only=False):
        calls.append((variable, region, source, land_only))
        s = monthly(240)
        s.attrs["units"] = "C"
        return s

    monkeypatch.setattr(power_zarr, "region_series", fake_power)
    return calls


def test_list_variables_marks_availability(catalog):
    vs = acquire.list_variables()
    assert set(vs) == {"temp", "ndvi", "ozone"}
    assert vs["temp"].available and not vs["temp"].needs_login and vs["temp"].units == "degC"
    assert vs["ndvi"].available and vs["ndvi"].needs_login
    assert not vs["ozone"].available
    assert set(acquire.list_variables(available_only=True)) == {"temp", "ndvi"}
    assert vs["temp"].summary()["live"] and not vs["ndvi"].summary()["live"]


def test_resolve_region_forms(catalog):
    preset = acquire.resolve_region("box")
    assert (preset.lon_min, preset.lat_min, preset.lon_max, preset.lat_max) == (10, 40, 20, 50)
    box = acquire.resolve_region([10, 40, 20, 50])
    assert box.bbox_key == preset.bbox_key
    r = Region("mine", 0, 1, 0, 1)
    assert acquire.resolve_region(r) is r
    with pytest.raises(KeyError, match="unknown region preset"):
        acquire.resolve_region("atlantis")


def test_get_series_dispatches_and_annotates(catalog):
    s = acquire.get_series("temp", "box")
    (variable, region, store, land_only), = catalog
    assert land_only is False
    assert (variable, store, region.name) == ("T2M", "merra2", "Test box")
    assert s.attrs["variable_id"] == "temp" and s.attrs["units"] == "degC"
    assert s.attrs["source_units"] == "C"  # B2-11: reader string kept separately
    assert s.attrs["catalog_units"] == "degC" and s.attrs["bbox"] == [10, 40, 20, 50]
    assert s.attrs["assessment"]["status"] == "ok"


def test_unknown_and_unavailable_variables(catalog):
    with pytest.raises(KeyError):
        acquire.get_series("nope", "box")
    with pytest.raises(LookupError, match="no reader"):
        acquire.get_series("ozone", "box")


def test_login_variables_are_offline_by_default(catalog, monkeypatch):
    seen = {}

    def fake_ndvi(region, refresh=False, offline=False):
        seen["offline"] = offline
        raise NotCachedError("not cached")

    monkeypatch.setattr(modis_ndvi, "region_series", fake_ndvi)
    with pytest.raises(NotCachedError):
        acquire.get_series("ndvi", "box")
    assert seen["offline"] is True
    with pytest.raises(NotCachedError):
        acquire.get_series("ndvi", "box", allow_login_fetch=True)
    assert seen["offline"] is False


def test_inventory_rows(catalog, monkeypatch):
    monkeypatch.setattr(modis_ndvi, "region_series",
                        lambda region, refresh=False, offline=False: (_ for _ in ()).throw(NotCachedError()))
    df = acquire.inventory("box").set_index("id")
    assert df.loc["temp", "status"] == "ok" and df.loc["temp", "live"]
    assert df.loc["ndvi", "status"] == "not cached"
    assert df.loc["ozone", "status"] == "no reader"


def test_assess_ok():
    a = acquire.assess(monthly(240))
    assert a["status"] == "ok" and a["record_years"] == 20.0 and a["coverage"] == 1.0
    assert a["start"] == "1990-01" and a["end"] == "2009-12" and not a["notes"]


def test_assess_too_short():
    a = acquire.assess(monthly(96))
    assert a["status"] == "too_short" and not a["checks"]["long_enough"]
    assert "at least 10 years" in a["notes"][0]


def test_assess_missing_winters_and_gaps():
    s = monthly(300)
    s = s[~s.index.month.isin([1, 2])]  # snowy months never observed
    s = s.drop(s.loc["2000-03":"2001-12"].index)  # a 2-year gap
    a = acquire.assess(s)
    assert a["status"] == "caution"
    assert not a["checks"]["seasonal_cycle_estimable"] and not a["checks"]["no_long_gaps"]
    assert any("Jan, Feb" in n for n in a["notes"]) and a["longest_gap_months"] >= 22


def test_assess_flags_flat_calendar_months():
    rng = np.random.default_rng(0)
    s = monthly(240) + rng.normal(0, 1, 240)
    s[s.index.month.isin([5, 6, 7, 8, 9])] = 0.0  # snow-free summers
    a = acquire.assess(s)
    assert a["status"] == "caution" and not a["checks"]["few_flat_months"]
    assert a["flat_months"] == [5, 6, 7, 8, 9] and a["zero_fraction"] == pytest.approx(5 / 12, abs=0.01)
    assert any("May, Jun, Jul, Aug, Sep" in n and "Sen" in n for n in a["notes"])


def test_assess_near_flat_dry_season_without_exact_zeros():
    """Sahel-like: dry months vary 50x less than the wet season, never exactly zero."""
    rng = np.random.default_rng(1)
    idx = pd.date_range("1990-01-01", periods=360, freq="MS")
    spread = np.where(idx.month.isin([11, 12, 1, 2]), 0.02, 1.0)
    s = pd.Series(5 + rng.normal(0, 1, 360) * spread, index=idx)
    a = acquire.assess(s)
    assert a["zero_fraction"] == 0 and a["flat_months"] == [1, 2, 11, 12]
    assert not a["checks"]["few_flat_months"]


def test_assess_constant_series_has_no_variation():
    a = acquire.assess(pd.Series(0.0, index=pd.date_range("1990-01-01", periods=240, freq="MS")))
    assert a["status"] == "no_variation" and "nothing to measure" in a["notes"][0]


def test_assess_empty():
    assert acquire.assess(pd.Series(dtype=float))["status"] == "too_short"


def test_real_catalog_is_consistent():
    """The shipped catalog: unique ids, every available entry names a known reader and source."""
    vs = acquire.list_variables()
    assert len(vs) >= 20
    for v in vs.values():
        assert v.definition and v.name, v.id
        assert v.entry.get("topic") and v.entry.get("how_measured"), v.id  # plan v2 filters, reanalysis note
        if v.reader == "power_zarr":
            assert v.access["store"] in power_zarr.SOURCES and v.access["variable"], v.id
    regions = acquire.list_regions()
    assert {"ukraine", "nw_india"} <= set(regions)


def test_grace_offline_and_cache_without_raw_file(tmp_path, monkeypatch):
    from test_grace import fake_file

    path = fake_file(tmp_path / "GRCTellus.JPL.200301_200305.GLO.RL06.3M.MSCNv04CRI.nc")
    r = Region("box", 0, 20, 10, 30)
    with pytest.raises(NotCachedError):
        grace.region_series(r, cache_dir=tmp_path / "c", offline=True)
    grace.region_series(r, path=path, cache_dir=tmp_path / "c")
    monkeypatch.setattr(grace, "fetch_file", lambda *a, **k: pytest.fail("raw file needed"))
    s = grace.region_series(r, cache_dir=tmp_path / "c", offline=True)
    assert s.attrs["from_cache"] and s.attrs["provenance"]["file"] == path.name


def test_assess_flags_mostly_zero_series_with_rare_outliers():
    """Sea-ice-over-Ukraine-like: 84% exact zeros, a few tiny values in every calendar month."""
    rng = np.random.default_rng(2)
    idx = pd.date_range("1981-01-01", periods=540, freq="MS")
    s = pd.Series(np.where(rng.random(540) < 0.16, rng.random(540) * 0.005, 0.0), index=idx)
    a = acquire.assess(s)
    assert a["flat_months"] == [] and a["zero_fraction"] > 0.8
    assert a["status"] == "caution" and any("exactly zero" in n for n in a["notes"])


def test_preset_land_only_flag_is_used(catalog, tmp_path):
    (tmp_path / "regions.yaml").write_text(REGIONS + """  - id: coast
    name: Coast
    bbox: [10.0, 40.0, 20.0, 50.0]
    land_only: true
""", encoding="utf-8")
    acquire._load_yaml.cache_clear()
    acquire.get_series("temp", "coast")
    acquire.get_series("temp", "coast", land_only=False)
    acquire.get_series("temp", [10, 40, 20, 50])
    assert [c[3] for c in catalog] == [True, False, False]


def test_internal_inputs_state_their_semantics():
    """Q3: T2M_MAX/T2M_MIN/PRECTOTCORR_SUM are internal inputs, never user-facing variables."""
    inputs = acquire.list_inputs()
    assert {"T2M_MAX", "T2M_MIN", "PRECTOTCORR_SUM"} <= set(inputs)
    assert not set(inputs) & set(acquire.list_variables())
    for e in inputs.values():
        assert e["internal"] is True and e["semantics"] and e["monthly"]["how"] in {"mean", "sum"}, e["id"]
    assert "hottest hour of the month" in inputs["T2M_MAX"]["semantics"]
    assert inputs["PRECTOTCORR_SUM"]["units"] == "mm/month"


def test_real_catalog_solar_display_conversion():
    """Q1: cache stays W/m^2; the only conversion is the catalog's convert field."""
    v = acquire.list_variables()["solar_radiation_power"].entry
    assert str(v["units"]).split("#")[0].strip() == "W/m^2"
    assert v["display_units"] == "MJ/m^2/day" and v["convert"] == "x * 0.0864"
    assert eval(v["convert"], {}, {"x": 1.0}) == pytest.approx(86400 / 1e6)  # noqa: S307
    imerg = acquire.list_variables()["precipitation_imerg"].entry
    assert imerg["source"] == "power" and "convert" not in imerg


def test_real_ukraine_preset_is_canonical_land_only_box():
    """Q2: canonical Ukraine = [22.0, 44.0, 40.5, 52.5], land only; SA box is a non-app alternate."""
    regions = acquire.list_regions()
    assert regions["ukraine"]["bbox"] == [22.0, 44.0, 40.5, 52.5] and regions["ukraine"]["land_only"] is True
    assert regions["ukraine_sa_bbox"]["app"] is False
