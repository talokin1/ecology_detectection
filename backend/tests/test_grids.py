import json

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from trend_detective import grids
from trend_detective import power_zarr as data

T2M_ATTRS = {"long_name": "Temperature at 2 Meters", "units": "C", "definition": "Air temperature."}
NT = 24  # 18 months with data, then 6 pre-allocated empty months
LAT = np.arange(-90, 90.1, 30.0)  # 7 rows incl. both poles, like MERRA-2's -90 ... 90
LON = np.arange(-180, 180, 45.0)  # 8 columns starting at -180, like MERRA-2


def fake_dataset():
    time = pd.date_range("2000-01-31", periods=NT, freq="ME")
    # value = lat + lon / 100 + month index
    vals = (LAT[None, :, None] + LON[None, None, :] / 100 + np.arange(NT)[:, None, None]).astype(np.float32)
    vals = np.broadcast_to(vals, (NT, LAT.size, LON.size)).copy()
    vals[18:] = np.nan
    gaps = vals.copy()
    gaps[:18, LAT == 0, LON == 45] = -999.0  # one fill-valued native cell
    gaps[:18, LAT == -30, LON == 0] = np.nan  # one missing native cell
    gaps[5] = np.nan  # an interior month with no data at all
    ds = xr.Dataset(
        {
            "T2M": (("time", "lat", "lon"), vals, T2M_ATTRS),
            "GAPS": (("time", "lat", "lon"), gaps, {"units": "1"}),
        },
        coords={"time": time, "lat": LAT, "lon": LON},
    )
    ds.attrs.update({"id": "fake_store.zarr", "version": "POWER Version 10.0.0"})
    return ds


@pytest.fixture
def fake(monkeypatch):
    calls = {"n": 0}
    ds = fake_dataset()

    def opener(source):
        calls["n"] += 1
        return ds

    monkeypatch.setattr(data, "open_source", opener)
    return calls


def weighted(lats, lons, month=0):
    w = np.cos(np.deg2rad(np.repeat(lats, len(lons))))
    v = np.array([la + lo / 100 + month for la in lats for lo in lons])
    return (w * v).sum() / w.sum()


def test_centre_coarsening_matches_hand_computation(fake, tmp_path):
    # 60° cells: lat edges -90/-30/30/90, lon edges -180/-120/.../180
    ds = grids.build_grid("T2M", resolution_deg=60, cache_dir=tmp_path, method="centre")
    assert ds.sizes == {"time": 18, "lat": 3, "lon": 6}
    assert np.allclose(ds.lat, [-60, 0, 60]) and np.allclose(ds.lon, [-150, -90, -30, 30, 90, 150])
    v = ds["T2M"]
    # centre on an edge goes north / east: lat -30 -> middle row, lon 0 -> fourth column
    assert float(v.isel(time=0, lat=1, lon=3)) == pytest.approx(weighted([-30, 0], [0, 45]), abs=1e-5)
    # south row: pole row (weight 0) and -60; the -180 column goes to the first column
    assert float(v.isel(time=0, lat=0, lon=0)) == pytest.approx(-60 + (-180 - 135) / 200, abs=1e-5)
    # north row holds 30, 60 and the +90 pole row
    assert float(v.isel(time=3, lat=2, lon=4)) == pytest.approx(weighted([30, 60, 90], [90], 3), abs=1e-5)
    assert float(v.isel(time=0, lat=1, lon=3)) < 0  # cos weights favour the equator over -30
    assert np.all(ds["valid_fraction"] == 1) and np.all(ds["n_valid_months"] == 18)
    assert ds.attrs["lat0"] == -60 and ds.attrs["lon0"] == -150
    assert (ds.attrs["dlat"], ds.attrs["dlon"], ds.attrs["nlat"], ds.attrs["nlon"]) == (60, 60, 3, 6)
    assert ds["T2M"].attrs["units"] == "C" and ds["T2M"].dtype == np.float32


def test_nan_fill_and_valid_fraction(fake, tmp_path):
    ds = grids.build_grid("GAPS", resolution_deg=60, cache_dir=tmp_path, method="centre")
    cell = ds.isel(time=0, lat=1, lon=3)  # native (-30|0) x (0|45); (-30, 0) NaN, (0, 45) fill
    w30, w0 = np.cos(np.deg2rad(30)), 1.0
    # remaining cells: (-30, 45) and (0, 0)
    expected = (w30 * (-30 + 0.45) + w0 * 0.0) / (w30 + w0)
    assert float(cell["GAPS"]) == pytest.approx(expected, abs=1e-5)
    assert float(cell["valid_fraction"]) == pytest.approx((w30 + w0) / (2 * w30 + 2 * w0), abs=1e-6)
    assert float(ds["valid_fraction"].isel(time=0, lat=1, lon=0)) == 1
    # the interior month without data is kept as NaN (regular time axis), fraction 0
    assert ds.sizes["time"] == 18
    assert ds["GAPS"].isel(time=5).isnull().all() and (ds["valid_fraction"].isel(time=5) == 0).all()
    assert int(ds["n_valid_months"].isel(lat=1, lon=3)) == 17
    prov = json.loads((tmp_path / "merra2_GAPS_60deg_centre.nc.provenance.json").read_text(encoding="utf-8"))
    assert prov["months_without_data_kept_as_nan"] == ["2000-06"]


def test_trailing_empty_months_dropped_and_time_is_month_start(fake, tmp_path):
    ds = grids.build_grid("T2M", resolution_deg=60, cache_dir=tmp_path)
    t = pd.DatetimeIndex(ds.time.values)
    assert t[0] == pd.Timestamp("2000-01-01") and t[-1] == pd.Timestamp("2001-06-01")
    assert not ds["T2M"].isnull().any()


def test_cache_round_trip_and_refresh(fake, tmp_path):
    ds = grids.build_grid("T2M", resolution_deg=60, cache_dir=tmp_path)
    path = tmp_path / "merra2_T2M_60deg.nc"
    assert path.exists() and ds.attrs["from_cache"] == 0
    n = fake["n"]
    again = grids.build_grid("T2M", resolution_deg=60, cache_dir=tmp_path)
    assert fake["n"] == n and again.attrs["from_cache"] == 1
    xr.testing.assert_allclose(ds, again)
    assert again["T2M"].dtype == np.float32 and again.attrs["nlon"] == 6
    assert again["T2M"].encoding.get("zlib") is True
    grids.build_grid("T2M", resolution_deg=60, cache_dir=tmp_path, refresh=True)
    assert fake["n"] > n
    summary = grids.grid_summary(path)
    assert summary["dims"] == {"time": 18, "lat": 3, "lon": 6}
    assert summary["time_range"] == {"start": "2000-01", "end": "2001-06"} and summary["size_mb"] > 0


def test_provenance_sidecar(fake, tmp_path):
    grids.build_grid("T2M", resolution_deg=60, cache_dir=tmp_path, method="centre")
    prov = json.loads((tmp_path / "merra2_T2M_60deg_centre.nc.provenance.json").read_text(encoding="utf-8"))
    assert prov["source_url"].endswith("power_merra2_monthly_temporal_utc.zarr")
    assert prov["short_name"] == "fake_store.zarr" and prov["version"] == "POWER Version 10.0.0"
    assert prov["variable"]["units"] == "C" and prov["variable"]["definition"] == "Air temperature."
    g = prov["grid"]
    assert (g["lat0"], g["lon0"], g["dlat"], g["dlon"], g["nlat"], g["nlon"]) == (-60, -150, 60, 60, 3, 6)
    assert prov["n_months"] == 18 and prov["time_range"] == {"start": "2000-01", "end": "2001-06"}
    assert prov["native_grid"]["nlat"] == 7 and prov["method"] == "centre"
    assert prov["land_only"] is False and prov["script"] == "backend/trend_detective/grids.py"
    assert any("dropped 6 trailing" in p for p in prov["processing"])
    assert any("-999.0" in p for p in prov["processing"]) and "git_commit" in prov and prov["accessed"]


def test_land_only(fake, monkeypatch, tmp_path):
    mask = xr.DataArray(
        np.broadcast_to(LON >= 0, (LAT.size, LON.size)), coords={"lat": LAT, "lon": LON}, dims=("lat", "lon")
    )
    monkeypatch.setattr(data, "land_mask", lambda: mask)
    ds = grids.build_grid("T2M", resolution_deg=60, land_only=True, cache_dir=tmp_path, method="centre")
    assert (tmp_path / "merra2_T2M_60deg_land_centre.nc").exists()
    assert ds["T2M"].isel(lon=[0, 1, 2]).isnull().all()  # western cells have no land
    assert (ds["valid_fraction"].isel(lon=[0, 1, 2]) == 0).all()
    assert float(ds["T2M"].isel(time=0, lat=1, lon=3)) == pytest.approx(weighted([-30, 0], [0, 45]), abs=1e-5)
    assert ds.attrs["land_only"] == 1


def test_overlap_fractions_hand_case():
    # native columns every 90° from -180 (edges -225, -135, -45, 45, 135); targets 120° from -180
    f = grids._axis_fractions(np.array([-180.0, -90, 0, 90]), -180.0, 120.0, 3, "overlap", periodic=True)
    expected = np.array([[0.5, 0, 0.5], [75 / 90, 15 / 90, 0], [0, 1, 0], [0, 15 / 90, 75 / 90]])
    assert np.allclose(f.toarray(), expected)
    c = grids._axis_fractions(np.array([-180.0, -90, 0, 90]), -180.0, 120.0, 3, "centre", periodic=True)
    assert np.allclose(c.toarray(), [[1, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]])  # -90 is in [-180, -60)


@pytest.mark.parametrize("method", grids.METHODS)
def test_area_weighted_global_mean_is_preserved(method):
    rng = np.random.default_rng(0)
    lat, lon = np.arange(-90, 90.1, 7.5), np.arange(-180, 180, 11.25)
    x = rng.normal(size=(3, lat.size, lon.size))
    da = xr.DataArray(x, coords={"time": np.arange(3), "lat": lat, "lon": lon}, dims=("time", "lat", "lon"))
    out = grids.coarsen(da, 30, method)
    flat = grids._axis_fractions(lat, -90.0, 30, 6, method)
    flon = grids._axis_fractions(lon, -180.0, 30, 12, method, periodic=True)
    w_n = np.cos(np.deg2rad(lat))
    area = np.outer((w_n[:, None] * flat.toarray()).sum(0), flon.toarray().sum(0))  # native weight per cell
    coarse = (out["value"].values * area).sum((1, 2)) / area.sum()
    native = (x * w_n[None, :, None]).sum((1, 2)) / (w_n.sum() * lon.size)
    assert np.allclose(coarse, native)


def test_latitude_bands_give_the_same_result():
    rng = np.random.default_rng(1)
    da = fake_dataset()["T2M"].copy(data=rng.normal(size=(NT, LAT.size, LON.size)))
    one = grids.coarsen(da, 60)
    many = grids.coarsen(da, 60, max_band_values=NT * LON.size * 2)  # 2 native rows per band
    xr.testing.assert_allclose(one, many)
    desc = grids.coarsen(da.isel(lat=slice(None, None, -1)), 60)
    xr.testing.assert_allclose(one, desc)


def test_errors(fake, tmp_path):
    with pytest.raises(ValueError, match="divide 180"):
        grids.build_grid("T2M", resolution_deg=0.7, cache_dir=tmp_path)
    with pytest.raises(KeyError):
        grids.build_grid("NOPE", resolution_deg=60, cache_dir=tmp_path)
    with pytest.raises(ValueError, match="monthly"):
        grids.build_grid("T2M", source="merra2_daily", resolution_deg=60, cache_dir=tmp_path)
    with pytest.raises(ValueError, match="method"):
        grids.build_grid("T2M", resolution_deg=60, method="bilinear", cache_dir=tmp_path)


@pytest.mark.network
def test_live_coarse_global_temperature(tmp_path):
    ds = grids.build_grid("T2M", resolution_deg=10, cache_dir=tmp_path)
    w = np.cos(np.deg2rad(ds.lat))
    first_year = ds["T2M"].sel(time="1981").mean("time").weighted(w).mean(("lat", "lon"))
    assert 13 < float(first_year) < 16 and ds.sizes["lat"] == 18


def test_default_method_is_overlap_and_file_names(tmp_path):
    assert grids.grid_path(tmp_path, "T2M", "merra2", 2.0).name == "merra2_T2M_2deg.nc"
    centre = grids.grid_path(tmp_path, "T2M", "merra2", 2.0, method="centre")
    assert centre.name == "merra2_T2M_2deg_centre.nc"
