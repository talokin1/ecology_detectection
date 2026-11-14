import json

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from trend_detective import grace
from trend_detective.power_zarr import Region


def test_assign_months_follows_jpl_convention():
    """Real windows from the RL06.3Mv04 file around the two shifted solutions."""
    tb = np.array([
        ["2011-10-17", "2011-11-16"], ["2011-12-17", "2012-01-15"], ["2012-01-01", "2012-01-31"],
        ["2012-03-20", "2012-04-19"],
        ["2015-04-01", "2015-04-30"], ["2015-04-12", "2015-05-11"], ["2015-06-29", "2015-07-31"],
    ], dtype="datetime64[ns]")
    months = [str(m) for m in grace.assign_months(tb)]
    assert months == ["2011-11", "2011-12", "2012-01", "2012-04", "2015-04", "2015-05", "2015-07"]


def fake_file(path):
    """1° global grid on 0..360 longitudes; land = 10°E..40°E; ocean cells hold 1000 cm."""
    lon = np.arange(0.5, 360, 1.0)
    lat = np.arange(-89.5, 90, 1.0)
    starts = pd.to_datetime(["2003-01-01", "2003-02-01", "2003-04-01", "2003-05-01"])
    ends = starts + pd.offsets.MonthEnd(0)
    n = len(starts)
    land = ((lon >= 10) & (lon <= 40))[None, :] & np.ones((lat.size, 1), bool)
    lwe = np.where(land[None], lat[None, :, None] + np.arange(n)[:, None, None], 1000.0)
    lwe = lwe + np.zeros((n, lat.size, lon.size))
    ds = xr.Dataset(
        {
            "lwe_thickness": (("time", "lat", "lon"), lwe, {"units": "cm"}),
            "land_mask": (("lat", "lon"), land.astype(float)),
            "scale_factor": (("lat", "lon"), np.full((lat.size, lon.size), 2.0)),
            "time_bounds": (("time", "bounds"), np.stack([starts, ends], axis=1)),
        },
        coords={"time": starts + (ends - starts) / 2, "lat": lat, "lon": lon},
        attrs={"months_missing": "2003-03", "time_mean_removed": "2004.000 to 2009.999",
               "date_created": "2026-11-10T07:11:31Z"},
    )
    ds.to_netcdf(path)
    return path


@pytest.fixture
def mascon(tmp_path):
    return fake_file(tmp_path / "GRCTellus.JPL.200301_200305.GLO.RL06.3M.MSCNv04CRI.nc")


def test_land_only_cos_weighted_mean(mascon, tmp_path):
    r = Region("box", 0, 20, 5, 30)  # spans ocean (5-10E) and land (10-30E)
    s = grace.region_series(r, path=mascon, cache_dir=tmp_path / "c")
    lat = np.arange(0.5, 20, 1.0)
    w = np.cos(np.deg2rad(lat))
    assert s.iloc[0] == pytest.approx((lat * w).sum() / w.sum())  # no 1000 cm ocean leakage
    assert list(s.index.strftime("%Y-%m")) == ["2003-01", "2003-02", "2003-04", "2003-05"]
    prov = s.attrs["provenance"]
    assert prov["missing_months"] == ["2003-03"] and prov["missing_months_match_published"]
    assert prov["baseline"] == "2004.000 to 2009.999" and prov["doi"] == grace.DOI


def test_negative_longitudes_are_converted(mascon, tmp_path):
    with pytest.raises(ValueError, match="no GRACE land cells"):
        grace.region_series(Region("west", 0, 20, -60, -20), path=mascon, cache_dir=tmp_path)


def test_scale_factor_option(mascon, tmp_path):
    r = Region("box", 0, 20, 10, 30)
    plain = grace.region_series(r, path=mascon, cache_dir=tmp_path)
    scaled = grace.region_series(r, path=mascon, cache_dir=tmp_path, apply_scale_factor=True)
    assert np.allclose(scaled.to_numpy(), 2 * plain.to_numpy())


def test_cache_and_provenance_roundtrip(mascon, tmp_path):
    r = Region("box", 0, 20, 10, 30)
    first = grace.region_series(r, path=mascon, cache_dir=tmp_path)
    second = grace.region_series(r, path=mascon, cache_dir=tmp_path)
    assert not first.attrs["from_cache"] and second.attrs["from_cache"]
    pd.testing.assert_series_equal(first, second, check_freq=False)
    (sidecar,) = tmp_path.glob("*.provenance.json")
    prov = json.loads(sidecar.read_text(encoding="utf-8"))
    assert prov["variable"]["units"] == "cm" and prov["script"].endswith("grace.py")
    assert "token" not in json.dumps(prov).lower()


def test_small_region_gets_a_caveat(mascon, tmp_path):
    s = grace.region_series(Region("tiny", 10, 12, 20, 22), path=mascon, cache_dir=tmp_path)
    assert any("smaller than one mascon" in c for c in s.attrs["provenance"]["caveats"])


def test_fetch_file_falls_back_to_local_copy(mascon, monkeypatch):
    def offline(*a, **k):
        raise ConnectionError("no network")

    monkeypatch.setattr(grace.earthdata, "cmr_granules", offline)
    assert grace.fetch_file(mascon.parent) == mascon


@pytest.mark.network
def test_live_nw_india_depletion(tmp_path):
    """Groundwater loss in NW India is a textbook GRACE signal (Rodell et al., 2009)."""
    s = grace.region_series(Region("NW India", 26, 32, 72, 78), cache_dir=tmp_path)
    assert s.attrs["provenance"]["missing_months_match_published"]
    assert s.loc["2020":].mean() < s.loc[:"2006"].mean()


def test_mission_gap_of_11_months_is_stated_as_caveat():
    """Q6: the GRACE -> GRACE-FO gap (2017-07..2018-05) is 11 months, below LONG_GAP_MONTHS = 12,
    so assess() does not flag it; the safeguard is the mission-gap caveat in the provenance."""
    from trend_detective import acquire

    assert acquire.LONG_GAP_MONTHS == 12  # kept on purpose (no tuning to catch one known case)
    s = acquire.get_series("terrestrial_water_storage_grace", "ukraine")  # frozen cache, offline
    a = s.attrs["assessment"]
    assert a["longest_gap_months"] == 11 and a["checks"]["no_long_gaps"]
    caveats = " ".join(s.attrs["provenance"]["caveats"])
    assert "2017-07 to 2018-05" in caveats and "GRACE-FO" in caveats
    assert {"2017-07", "2018-05"} <= set(s.attrs["provenance"]["missing_months"])
