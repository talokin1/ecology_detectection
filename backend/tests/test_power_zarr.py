import json

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from trend_detective import power_zarr as data
from trend_detective.power_zarr import Region, region_series

T2M_ATTRS = {"long_name": "Temperature at 2 Meters", "units": "C", "definition": "Air temperature."}


def fake_dataset(lat_descending=False):
    time = pd.date_range("2000-01-31", periods=36, freq="ME")
    lat = np.arange(-90, 90.5, 10.0)
    lon = np.arange(-180, 180, 20.0)
    # value = latitude everywhere, plus 1 per month; last 6 months empty (pre-allocated)
    vals = lat[None, :, None] + np.arange(36)[:, None, None] + np.zeros((36, lat.size, lon.size))
    vals[30:] = np.nan
    land = vals.copy()
    land[:, :, lon < 0] = np.nan  # "land-only" variable: western half missing
    fill = vals.copy()
    fill[:, lat == 0, :] = -999.0
    ds = xr.Dataset(
        {
            "T2M": (("time", "lat", "lon"), vals, T2M_ATTRS),
            "LAND": (("time", "lat", "lon"), land, {"units": "1"}),
            "FILL": (("time", "lat", "lon"), fill),
            "T2M_00": (("time", "lat", "lon"), vals),
        },
        coords={"time": time, "lat": lat, "lon": lon},
    )
    ds.attrs.update({"id": "fake_store.zarr", "version": "POWER Version 10.0.0"})
    return ds.isel(lat=slice(None, None, -1)) if lat_descending else ds


@pytest.fixture
def fake(monkeypatch):
    calls = {"n": 0}
    ds = fake_dataset()

    def opener(source):
        calls["n"] += 1
        return ds

    monkeypatch.setattr(data, "open_source", opener)
    return calls


def test_series_shape_and_trailing_empty_months_dropped(fake, tmp_path):
    s = region_series("T2M", Region("box", 0, 20, 0, 40), cache_dir=tmp_path)
    assert len(s) == 30
    assert s.index[0] == pd.Timestamp("2000-01-01") and s.index[-1] == pd.Timestamp("2002-06-01")
    assert s.attrs["units"] == "C" and s.attrs["region"] == "box" and s.name == "T2M"
    assert np.allclose(np.diff(s.to_numpy()), 1.0)


def test_mean_is_weighted_by_cos_latitude(fake, tmp_path):
    s = region_series("T2M", Region("tall", 0, 80, 0, 40), cache_dir=tmp_path)
    lat = np.arange(0, 81, 10.0)
    w = np.cos(np.deg2rad(lat))
    assert s.iloc[0] == pytest.approx((lat * w).sum() / w.sum())
    assert s.iloc[0] < lat.mean()  # equator counts more than high latitudes


def test_descending_latitude_axis(monkeypatch, tmp_path):
    monkeypatch.setattr(data, "open_source", lambda source: fake_dataset(lat_descending=True))
    s = region_series("T2M", Region("box", 0, 20, 0, 40), cache_dir=tmp_path)
    w = np.cos(np.deg2rad([0, 10, 20]))
    assert s.iloc[0] == pytest.approx((np.array([0, 10, 20]) * w).sum() / w.sum())


def test_antimeridian_box(fake, tmp_path):
    s = region_series("T2M", Region("pacific", -10, 10, 160, -160), cache_dir=tmp_path)
    assert len(s) == 30 and s.iloc[0] == pytest.approx(0.0, abs=1e-9)
    # LAND is missing west of 0°, so only the 160°E column contributes; still a valid mean
    assert len(region_series("LAND", Region("pacific", -10, 10, 160, -160), cache_dir=tmp_path)) == 30


def test_fill_values_are_masked(fake, tmp_path):
    s = region_series("FILL", Region("eq", -10, 10, 0, 40), cache_dir=tmp_path)
    assert s.min() > -100  # -999 rows at the equator ignored


def test_cache_is_used_and_refresh_bypasses_it(fake, tmp_path):
    r = Region("box", 0, 20, 0, 40)
    first = region_series("T2M", r, cache_dir=tmp_path)
    n = fake["n"]
    second = region_series("T2M", r, cache_dir=tmp_path)
    assert fake["n"] == n  # no new read
    pd.testing.assert_series_equal(first, second, check_freq=False)
    assert second.attrs["units"] == "C" and second.attrs["from_cache"] and not first.attrs["from_cache"]
    region_series("T2M", r, cache_dir=tmp_path, refresh=True)
    assert fake["n"] > n
    # a different box must not hit the same cache file
    other = region_series("T2M", Region("box2", 20, 40, 0, 40), cache_dir=tmp_path)
    assert other.iloc[0] != first.iloc[0]


def test_int_and_float_bounds_share_a_cache_file(fake, tmp_path):
    region_series("T2M", Region("box", 0, 20, 0, 40), cache_dir=tmp_path)
    n = fake["n"]
    s = region_series("T2M", Region("box", 0.0, 20.0, 0.0, 40.0), cache_dir=tmp_path)
    assert fake["n"] == n and s.attrs["from_cache"] and len(list(tmp_path.glob("*.csv"))) == 1


def test_errors(fake, tmp_path):
    with pytest.raises(KeyError):
        region_series("NOPE", Region("box", 0, 20, 0, 40), cache_dir=tmp_path)
    with pytest.raises(ValueError, match="smaller than one grid cell"):
        region_series("T2M", Region("tiny", 1, 2, 1, 2), cache_dir=tmp_path)
    with pytest.raises(ValueError, match="no data"):
        region_series("LAND", Region("west", 0, 20, -100, -40), cache_dir=tmp_path)
    assert not list(tmp_path.glob("*LAND*"))  # failures are not cached


@pytest.mark.parametrize("args", [(10, 5, 0, 10), (-95, 0, 0, 10), (0, 10, 0, 190), (0, 10, 5, 5)])
def test_region_validation(args):
    with pytest.raises(ValueError):
        Region("bad", *args)


def test_list_variables_hides_hourly_variants(fake):
    assert data.list_variables() == ["FILL", "LAND", "T2M"]
    assert data.variable_info("T2M")["definition"] == "Air temperature."


def test_provenance_sidecar(fake, tmp_path):
    r = Region("box", 0, 20, 0, 40)
    s = region_series("T2M", r, cache_dir=tmp_path)
    (csv,) = tmp_path.glob("*.csv")
    prov = json.loads((tmp_path / (csv.name + ".provenance.json")).read_text(encoding="utf-8"))
    assert prov == s.attrs["provenance"]
    assert prov["version"] == "POWER Version 10.0.0" and prov["short_name"] == "fake_store.zarr"
    assert prov["source_url"].startswith("https://nasa-power.s3") and prov["variable"]["units"] == "C"
    assert prov["bbox"] == {"lat_min": 0, "lat_max": 20, "lon_min": 0, "lon_max": 40}
    assert prov["time_range"] == {"start": "2000-01", "end": "2002-06"} and prov["n_months"] == 30
    assert prov["accessed"].endswith("Z") and prov["script"].endswith("power_zarr.py")
    assert region_series("T2M", r, cache_dir=tmp_path).attrs["provenance"] == prov


def test_cache_dir_follows_env(monkeypatch, tmp_path):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path))
    assert data.default_cache_dir() == tmp_path / "power_zarr"
    monkeypatch.delenv("CACHE_DIR")
    assert data.default_cache_dir().parts[-3:] == ("data", "cache", "power_zarr")


@pytest.mark.network
def test_live_archive_ukraine_temperature(tmp_path):
    s = region_series("T2M", Region("Ukraine", 44, 52.5, 22, 40.5), cache_dir=tmp_path)
    assert s.index[0] == pd.Timestamp("1981-01-01") and len(s) >= 540
    assert -15 < s.min() and s.max() < 30  # monthly means in degC
    assert s.attrs["provenance"]["version"].startswith("POWER")


@pytest.mark.network
def test_live_series_through_team_statistics(tmp_path):
    """End to end: live region series into the team's reference statistics."""
    from trend_stats import analyze_series

    s = region_series("T2M", Region("Ukraine", 44, 52.5, 22, 40.5), cache_dir=tmp_path)
    out = analyze_series(s.index.to_numpy(), s.to_numpy(), units="degC", variable_name="Air temperature")
    assert out["deseasonalized"] and out["n"] == len(s)
    assert 0.3 < out["sen_slope_per_decade"] < 0.8 and out["mk"]["p"] < 0.05


def test_land_only_excludes_sea_cells(fake, monkeypatch, tmp_path):
    """Fake land = eastern half (lon >= 0); the fake T2M equals latitude + month everywhere."""
    ds = fake_dataset()
    mask = xr.DataArray(np.broadcast_to(ds.lon.values >= 20, (ds.lat.size, ds.lon.size)).copy(),
                        coords={"lat": ds.lat, "lon": ds.lon}, dims=("lat", "lon"))
    monkeypatch.setattr(data, "land_mask", lambda: mask)
    r = Region("coast", 0, 20, 0, 40)  # lon 0 and 20 cells; only lon 20 is "land"
    full = region_series("T2M", r, cache_dir=tmp_path)
    land = region_series("T2M", r, cache_dir=tmp_path, land_only=True)
    pd.testing.assert_series_equal(full, land, check_freq=False, check_names=False)  # field is lon-invariant
    assert len(list(tmp_path.glob("*.csv"))) == 2  # separate cache entries
    assert land.attrs["provenance"]["land_only"] and not full.attrs["provenance"]["land_only"]
    assert any("land cells only" in step for step in land.attrs["provenance"]["processing"])
    with pytest.raises(ValueError, match="no data"):
        region_series("T2M", Region("sea", 0, 20, -60, -30), cache_dir=tmp_path, land_only=True)


def daily_series(start="2001-01-01", end="2001-03-31", value=2.0):
    idx = pd.date_range(start, end, freq="D")
    s = pd.Series(value, index=idx, name="PRECTOTCORR")
    s.attrs["units"] = "mm/day"
    return s


def test_monthly_from_daily_mean_and_sum():
    s = daily_series()
    mean = data.monthly_from_daily(s, "mean")
    total = data.monthly_from_daily(s, "sum")
    assert list(mean.index.strftime("%Y-%m")) == ["2001-01", "2001-02", "2001-03"]
    assert np.allclose(mean, 2.0) and list(total) == [62.0, 56.0, 62.0]  # 31, 28, 31 days
    assert total.attrs["units"] == "mm/month" and mean.attrs["units"] == "mm/day"
    assert total.attrs["aggregation"]["how"] == "sum" and mean.index.name == "month"


def test_monthly_from_daily_80_percent_rule_and_no_low_bias():
    s = daily_series()
    s = s.drop(s.loc["2001-01-01":"2001-01-03"].index)  # Jan: 28/31 = 90% present -> kept
    s = s.drop(s.loc["2001-02-01":"2001-02-10"].index)  # Feb: 18/28 = 64% present -> dropped
    total = data.monthly_from_daily(s, "sum")
    assert list(total.index.strftime("%Y-%m")) == ["2001-01", "2001-03"]
    assert total.iloc[0] == pytest.approx(62.0)  # scaled to the full month, not 56
    assert total.attrs["aggregation"]["months_dropped"] == ["2001-02"]
    with pytest.raises(ValueError):
        data.monthly_from_daily(s, "median")


def test_daily_source_keeps_dates(monkeypatch, tmp_path):
    time = pd.date_range("2000-12-31", periods=400, freq="D")
    lat, lon = np.arange(-10, 11, 10.0), np.arange(0, 41, 20.0)
    vals = np.ones((400, lat.size, lon.size)) * np.arange(400)[:, None, None]
    vals[-20:] = np.nan  # pre-allocated future days
    ds = xr.Dataset({"T2M_MAX": (("time", "lat", "lon"), vals, {"units": "C", "long_name": "Tmax"})},
                    coords={"time": time, "lat": lat, "lon": lon})
    monkeypatch.setattr(data, "open_source", lambda source: ds)
    s = region_series("T2M_MAX", Region("box", -10, 10, 0, 40), "merra2_daily", cache_dir=tmp_path)
    assert len(s) == 380 and s.index.name == "date" and s.index[1] == pd.Timestamp("2001-01-01")
    prov = s.attrs["provenance"]
    assert prov["frequency"] == "daily" and prov["n_days"] == 380
    assert prov["time_range"]["start"] == "2000-12-31"
    again = region_series("T2M_MAX", Region("box", -10, 10, 0, 40), "merra2_daily", cache_dir=tmp_path)
    assert again.attrs["from_cache"] and again.index[1] == pd.Timestamp("2001-01-01")
