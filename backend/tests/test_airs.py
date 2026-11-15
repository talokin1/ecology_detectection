"""Offline tests of the AIRS reader (synthetic subsets; no network, no token)."""

import json

import netCDF4
import numpy as np
import pytest
import xarray as xr
from trend_detective import airs


def fake_subset_bytes(tmp_path, value_a=280.0, value_d=270.0, fill_cell=None) -> bytes:
    """A NetCDF4 file shaped like the DAP4 response: groups, 1° lat north->south."""
    p = tmp_path / "subset.nc4"
    with netCDF4.Dataset(p, "w") as nc:
        for orbit, suffix, val in (("ascending", "A", value_a), ("descending", "D", value_d)):
            g = nc.createGroup(orbit).createGroup("Data_Fields")
            g.createDimension("y", 180)
            g.createDimension("x", 360)
            for f in airs.FIELDS:
                a = np.full((180, 360), val if f == "SurfAirTemp" else val / 10, np.float32)
                if fill_cell is not None and suffix == "D":
                    a[fill_cell] = airs.FILL
                g.createVariable(f"{f}_{suffix}", "f4", ("y", "x"))[:] = a
        loc = nc.createGroup("location").createGroup("Data_Fields")
        loc.createDimension("y", 180)
        loc.createDimension("x", 360)
        lat = np.repeat(np.arange(89.5, -90, -1.0)[:, None], 360, axis=1)
        lon = np.repeat(np.arange(-179.5, 180, 1.0)[None, :], 180, axis=0)
        loc.createVariable("Latitude", "f4", ("y", "x"))[:] = lat
        loc.createVariable("Longitude", "f4", ("y", "x"))[:] = lon
    return p.read_bytes()


def test_parse_subset_masks_fill_and_reads_axes(tmp_path):
    f = airs.parse_subset(fake_subset_bytes(tmp_path, fill_cell=(0, 0)))
    assert np.isnan(f["SurfAirTemp_D"][0, 0]) and f["SurfAirTemp_A"][0, 0] == 280.0
    assert f["lat"][0] == 89.5 and f["lon"][0] == -179.5


def test_day_night_mean_needs_both_orbits():
    a = xr.DataArray([[280.0, 280.0]], dims=("lat", "lon"))
    d = xr.DataArray([[270.0, np.nan]], dims=("lat", "lon"))
    m = airs.day_night_mean(xr.Dataset({"SurfAirTemp_A": a, "SurfAirTemp_D": d}), "SurfAirTemp")
    assert float(m[0, 0]) == 275.0 and np.isnan(float(m[0, 1]))


def test_build_grid_matches_app_grid_format(tmp_path, monkeypatch):
    months = airs.months_dir(tmp_path)
    months.mkdir(parents=True)
    for month, (a, d) in {"2003-01": (280.0, 270.0), "2003-03": (282.0, 272.0)}.items():
        f = airs.parse_subset(fake_subset_bytes(tmp_path, a, d, fill_cell=(10, 10)))
        ds = xr.Dataset(
            {k: (("lat", "lon"), f[k]) for k in airs.PATHS},
            coords={"lat": f["lat"], "lon": f["lon"]},
            attrs={"month": month},
        )
        ds.to_netcdf(months / f"{month}.nc")
    monkeypatch.setattr(airs.power_zarr, "_git_commit", lambda: "test")
    path = airs.build_grid("SurfAirTemp", 2.0, cache_dir=tmp_path)
    assert path.name == "airs_SurfAirTemp_2deg.nc"
    with xr.open_dataset(path) as g:
        assert g["SurfAirTemp"].shape == (3, 90, 180)  # Feb kept as an empty month
        assert g.attrs["lat0"] == -89.0 and g.attrs["dlat"] == 2.0
        assert float(g["SurfAirTemp"][0].mean()) == pytest.approx(275.0)
        assert np.isnan(g["SurfAirTemp"][1]).all()
        assert float(g["lat"][0]) == -89.0  # south to north, like the other grids
    prov = json.loads(path.with_name(path.name + ".provenance.json").read_text())
    for key in ("source", "variable", "accessed", "processing", "script", "doi", "short_name", "version"):
        assert prov[key]
    assert prov["months_without_data_kept_as_nan"] == ["2003-02"]
    assert "single orbit" in " ".join(prov["processing"])
