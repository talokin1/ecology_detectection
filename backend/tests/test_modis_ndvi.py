import json

import numpy as np
import pandas as pd
import pytest
from trend_detective import modis_ndvi as nd
from trend_detective.power_zarr import Region

UKRAINE = Region("Ukraine", 44, 52.5, 22, 40.5)


def test_grid_index_matches_real_opendap_subset():
    """Rows/cols checked against coordinates returned by OPeNDAP (52.475..44.025N, 22.025..40.475E)."""
    rows, cols = nd.grid_index(UKRAINE)
    assert (rows.start, rows.stop) == (750, 920) and (cols.start, cols.stop) == (4040, 4410)
    assert nd.constraint(rows, cols).count("[750:919][4040:4409]") == 2
    lat = nd.row_latitudes(rows)
    assert lat[0] == pytest.approx(52.475) and lat[-1] == pytest.approx(44.025) and lat.size == 170


def test_grid_index_rejects_bad_boxes():
    with pytest.raises(ValueError, match="antimeridian"):
        nd.grid_index(Region("chukotka", 60, 70, 170, -170))
    with pytest.raises(ValueError, match="too large"):
        nd.grid_index(Region("world", -90, 90, -180, 180))
    with pytest.raises(ValueError, match="smaller than one"):
        nd.grid_index(Region("dot", 10.001, 10.002, 20.001, 20.002))


def test_box_mean_divides_by_10000_and_filters_quality():
    lat = np.array([0.0, 60.0])
    ndvi = np.array([[8000, 2000, -3000],    # equator: good, cloudy, ocean (fill)
                     [4000, 6000, -3000]])   # 60N:     good, snow,   ocean
    rel = np.array([[0, 3, -1],
                    [1, 2, -1]])
    mean, frac = nd.box_mean(ndvi, rel, lat)
    w0, w60 = 1.0, np.cos(np.deg2rad(60))
    assert mean == pytest.approx((0.8 * w0 + 0.4 * w60) / (w0 + w60))
    assert frac == pytest.approx((w0 + w60) / (2 * w0 + 2 * w60))
    assert 0 < mean < 1  # a CF decoder would have multiplied by 10000


def test_box_mean_all_ocean_or_all_bad():
    lat = np.array([10.0])
    assert np.isnan(nd.box_mean(np.array([[-3000, -3000]]), np.array([[-1, -1]]), lat)[0])
    mean, frac = nd.box_mean(np.array([[5000, 5000]]), np.array([[3, 2]]), lat)
    assert np.isnan(mean) and frac == 0.0


def fake_granules(n=24):
    months = pd.date_range("2001-01-01", periods=n, freq="MS")
    return [{"title": f"MOD13C2.A{m:%Y%j}.061.x", "time_start": f"{m:%Y-%m-%d}T00:00:00.000Z",
             "collection_concept_id": "C2565788914-LPCLOUD"} for m in months]


@pytest.fixture
def offline(monkeypatch):
    """No network: CMR returns 24 fake months; each month's value encodes its index."""
    calls = {"n": 0}
    monkeypatch.setattr(nd.earthdata, "cmr_granules", lambda *a, **k: fake_granules())

    def fetch(granule, rows, cols):
        calls["n"] += 1
        m = pd.Timestamp(granule["time_start"][:10])
        frac = 0.5 if m.month in (1, 2) else 0.95  # snowy Jan/Feb fail the 80% rule
        return 0.3 + 0.01 * m.month, frac

    monkeypatch.setattr(nd, "_fetch_month", fetch)
    return calls


def test_region_series_drops_low_coverage_months(offline, tmp_path):
    s = nd.region_series(UKRAINE, cache_dir=tmp_path, workers=2)
    assert len(s) == 20 and not any(s.index.month.isin([1, 2]))
    prov = s.attrs["provenance"]
    assert prov["months_dropped_low_coverage"][:2] == ["2001-01", "2001-02"]
    assert prov["n_granules"] == 24 and prov["n_months"] == 20 and prov["doi"] == nd.DOI
    assert s.loc["2001-07-01"] == pytest.approx(0.37)
    assert not list(tmp_path.glob("*.partial.csv"))  # cleaned up after completion


def test_cached_series_needs_no_network(offline, tmp_path, monkeypatch):
    first = nd.region_series(UKRAINE, cache_dir=tmp_path)
    monkeypatch.setattr(nd.earthdata, "cmr_granules", lambda *a, **k: pytest.fail("network used"))
    second = nd.region_series(UKRAINE, cache_dir=tmp_path)
    assert second.attrs["from_cache"] and not first.attrs["from_cache"]
    pd.testing.assert_series_equal(first, second, check_freq=False)
    (csv,) = tmp_path.glob("*.csv")
    assert list(pd.read_csv(csv).columns) == ["month", "value", "valid_fraction"]


def test_resume_from_partial(offline, tmp_path):
    out = nd._cache_path(tmp_path, UKRAINE, nd.MIN_VALID_FRACTION)
    partial = out.with_name(out.name + ".partial.csv")
    partial.write_text("month,value,valid_fraction\n2001-03-01,0.33,0.9\n2001-04-01,0.34,0.9\n")
    nd.region_series(UKRAINE, cache_dir=tmp_path)
    assert offline["n"] == 22  # two months were already done


def test_failed_months_keep_progress_and_rerun_retries(offline, tmp_path, monkeypatch):
    good = nd._fetch_month

    def flaky(granule, rows, cols):
        if granule["time_start"].startswith("2001-05"):
            raise OSError("HTTP 400")
        return good(granule, rows, cols)

    monkeypatch.setattr(nd, "_fetch_month", flaky)
    with pytest.raises(RuntimeError, match="1 of 24 months failed.*2001-05"):
        nd.region_series(UKRAINE, cache_dir=tmp_path)
    assert offline["n"] == 23 and not list(tmp_path.glob("*.provenance.json"))
    monkeypatch.setattr(nd, "_fetch_month", good)
    s = nd.region_series(UKRAINE, cache_dir=tmp_path)
    assert offline["n"] == 24 and len(s) == 20  # only the failed month was fetched again


def test_threshold_is_part_of_the_cache_key(offline, tmp_path):
    strict = nd.region_series(UKRAINE, cache_dir=tmp_path)
    loose = nd.region_series(UKRAINE, cache_dir=tmp_path, min_valid_fraction=0.4)
    assert len(loose) == 24 and len(strict) == 20
    for f in tmp_path.glob("*.provenance.json"):
        assert "token" not in json.dumps(json.loads(f.read_text())).lower()


@pytest.mark.network
def test_live_one_month_ukraine():
    (g,) = [g for g in nd.earthdata.cmr_granules(nd.SHORT_NAME, nd.VERSION)
            if g["time_start"].startswith("2020-07")]
    mean, frac = nd._fetch_month(g, *nd.grid_index(UKRAINE))
    assert 0.4 < mean < 0.8 and frac > 0.9  # midsummer cropland and forest


def test_offline_raises_when_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(nd.earthdata, "cmr_granules", lambda *a, **k: pytest.fail("network used"))
    with pytest.raises(nd.earthdata.NotCachedError):
        nd.region_series(UKRAINE, cache_dir=tmp_path, offline=True)
