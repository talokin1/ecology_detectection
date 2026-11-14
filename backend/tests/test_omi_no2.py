import json

import numpy as np
import pandas as pd
import pytest
from trend_detective import omi_no2 as om
from trend_detective.power_zarr import Region

KYIV = Region("Kyiv", 50.2, 50.7, 30.2, 30.9)


def test_grid_index_matches_real_opendap_coordinates():
    """Checked against YDim/XDim of a real v004 granule: rows 561-562 = 50.375, 50.625N;
    cols 841-843 = 30.375, 30.625, 30.875E (lat ascending, lon from -179.875)."""
    rows, cols = om.grid_index(KYIV)
    assert (rows.start, rows.stop) == (561, 563) and (cols.start, cols.stop) == (841, 844)
    assert om.row_latitudes(rows) == pytest.approx([50.375, 50.625])
    assert om.col_longitudes(cols) == pytest.approx([30.375, 30.625, 30.875])
    assert om.constraint(rows, cols) == (
        "/HDFEOS/GRIDS/ColumnAmountNO2/Data_Fields/ColumnAmountNO2TropCloudScreened[561:562][841:843]")
    assert om.row_latitudes(slice(0, 1))[0] == pytest.approx(-89.875)


def test_grid_index_rejects_bad_boxes():
    with pytest.raises(ValueError, match="antimeridian"):
        om.grid_index(Region("chukotka", 60, 70, 170, -170))
    with pytest.raises(ValueError, match="no 0.25° cell centre"):
        om.grid_index(Region("dot", 10.13, 10.2, 20.13, 20.2))


def test_box_mean_weights_by_cos_lat_and_masks_fill():
    lat = np.array([0.0, 60.0])
    no2 = np.array([[2e15, om.FILL],
                    [4e15, -1e14]])  # negative value is valid retrieval noise
    mean, frac = om.box_mean(no2.astype(np.float32), lat)
    w0, w60 = 1.0, np.cos(np.deg2rad(60))
    assert mean == pytest.approx((2e15 * w0 + (4e15 - 1e14) * w60) / (w0 + 2 * w60), rel=1e-6)
    assert frac == pytest.approx((w0 + 2 * w60) / (2 * w0 + 2 * w60))


def test_box_mean_all_fill():
    mean, frac = om.box_mean(np.full((2, 3), om.FILL, dtype=np.float32), np.array([50.375, 50.625]))
    assert np.isnan(mean) and frac == 0.0


def test_monthly_thresholds():
    days = pd.date_range("2020-01-01", "2020-03-31", freq="D")
    daily = pd.DataFrame({"value": 1e15, "valid_fraction": 1.0}, index=days)
    daily.index.name = "date"
    jan = daily.index.month == 1
    daily.loc[jan & (daily.index.day > 9), "value"] = np.nan          # January: 9 valid days
    daily.loc[jan & (daily.index.day > 9), "valid_fraction"] = 0.0
    feb = daily.index.month == 2
    daily.loc[feb, "value"] = 2e15
    daily.loc[feb & (daily.index.day <= 15), "valid_fraction"] = 0.4  # below the 50 % area rule
    daily.loc[feb & (daily.index.day == 20), "value"] = 5e15
    out = om.monthly(daily, min_valid_days=10)
    assert list(out.columns) == ["value", "n_days"]
    assert out["n_days"].tolist() == [9, 14, 31]
    assert np.isnan(out.loc["2020-01-01", "value"])
    assert out.loc["2020-02-01", "value"] == pytest.approx((13 * 2e15 + 5e15) / 14)
    assert out.loc["2020-03-01", "value"] == pytest.approx(1e15)
    loose = om.monthly(daily, min_valid_days=5, min_valid_area_fraction=0.3)
    assert loose["n_days"].tolist() == [9, 29, 31] and loose["value"].notna().all()


def test_monthly_drops_incomplete_trailing_month_and_fills_gaps():
    days = pd.to_datetime(["2020-01-05", "2020-03-01", "2020-04-10"])
    daily = pd.DataFrame({"value": [1e15, 1e15, 1e15], "valid_fraction": 1.0}, index=days)
    out = om.monthly(daily, min_valid_days=1)
    assert [f"{m:%Y-%m}" for m in out.index] == ["2020-01", "2020-02", "2020-03"]  # April incomplete
    assert out["n_days"].tolist() == [1, 0, 1] and np.isnan(out.loc["2020-02-01", "value"])
    full = om.monthly(daily, min_valid_days=1, last_day=pd.Timestamp("2020-04-30"))
    assert len(full) == 4


def fake_granules(start="2005-01-01", end="2005-06-30"):
    days = pd.date_range(start, end, freq="D")
    return [{"title": f"OMNO2d.004:OMI-Aura_L3-OMNO2d_{d:%Ym%m%d}_v004-x.he5",
             "time_start": f"{d:%Y-%m-%d}T00:00:00.000Z",
             "collection_concept_id": "C3333493715-GES_DISC"} for d in days]


@pytest.fixture
def offline(monkeypatch):
    """No network: 181 fake days; January has only 8 valid days, others all valid."""
    calls = {"n": 0}
    monkeypatch.setattr(om.earthdata, "cmr_granules", lambda *a, **k: fake_granules())

    def fetch(granule, rows, cols):
        calls["n"] += 1
        d = pd.Timestamp(granule["time_start"][:10])
        if d.month == 1 and d.day > 8:
            return float("nan"), 0.0
        return 1e15 * (7 - d.month), 0.9

    monkeypatch.setattr(om, "_fetch_day", fetch)
    return calls


def test_region_series_and_provenance(offline, tmp_path):
    s = om.region_series(KYIV, cache_dir=tmp_path, workers=2)
    assert len(s) == 5 and s.index[0] == pd.Timestamp("2005-02-01")
    assert s.loc["2005-03-01"] == pytest.approx(4e15)
    assert s.attrs["n_days"] == [28, 31, 30, 31, 30]
    prov = s.attrs["provenance"]
    assert prov["months_dropped_few_days"] == ["2005-01"] and prov["n_months_total"] == 6
    assert prov["doi"] == "10.5067/AURA/OMI/DATA3407" and prov["version"] == "004"
    assert prov["rules"] == {"min_valid_area_fraction": 0.5, "min_valid_days": 10}
    assert any("13:30" in c for c in prov["caveats"]) and any("row anomaly" in c for c in prov["caveats"])
    assert not list(tmp_path.glob("*.partial.csv"))
    (monthly_csv,) = [p for p in tmp_path.glob("omno2d_*.csv") if "daily" not in p.name]
    assert list(pd.read_csv(monthly_csv).columns) == ["month", "value", "n_days"]
    assert "token" not in json.dumps(prov).lower()
    for f in tmp_path.glob("*.json"):
        assert "token" not in f.read_text().lower() and "bearer" not in f.read_text().lower()


def test_cached_series_needs_no_network(offline, tmp_path, monkeypatch):
    first = om.region_series(KYIV, cache_dir=tmp_path)
    monkeypatch.setattr(om.earthdata, "cmr_granules", lambda *a, **k: pytest.fail("network used"))
    monkeypatch.setattr(om, "_fetch_day", lambda *a: pytest.fail("network used"))
    second = om.region_series(KYIV, cache_dir=tmp_path)
    assert second.attrs["from_cache"] and not first.attrs["from_cache"]
    pd.testing.assert_series_equal(first, second, check_freq=False)
    # new monthly rules are computed from the cached daily means, still without network
    loose = om.region_series(KYIV, cache_dir=tmp_path, min_valid_days=5)
    assert len(loose) == 6 and not loose.attrs["from_cache"]


def test_resume_from_partial(offline, tmp_path):
    daily = om._daily_path(tmp_path, KYIV, om.VERSION)
    partial = daily.with_name(daily.name + ".partial.csv")
    partial.write_text("date,value,valid_fraction\n2005-03-01,4e15,0.9\n2005-03-02,4e15,0.9\n")
    om.region_series(KYIV, cache_dir=tmp_path)
    assert offline["n"] == 181 - 2


def test_failed_days_keep_progress_and_rerun_retries(offline, tmp_path, monkeypatch):
    good = om._fetch_day

    def flaky(granule, rows, cols):
        if granule["time_start"].startswith("2005-05-07"):
            raise OSError("HTTP 500")
        return good(granule, rows, cols)

    monkeypatch.setattr(om, "_fetch_day", flaky)
    with pytest.raises(RuntimeError, match="1 of 181 days failed.*2005-05-07"):
        om.region_series(KYIV, cache_dir=tmp_path)
    assert offline["n"] == 180 and not list(tmp_path.glob("*.provenance.json"))
    monkeypatch.setattr(om, "_fetch_day", good)
    s = om.region_series(KYIV, cache_dir=tmp_path)
    assert offline["n"] == 181 and len(s) == 5


def test_offline_raises_when_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(om.earthdata, "cmr_granules", lambda *a, **k: pytest.fail("network used"))
    with pytest.raises(om.earthdata.NotCachedError):
        om.region_series(KYIV, cache_dir=tmp_path, offline=True)


def test_opendap_url_prefers_cmr_link():
    g = fake_granules()[0]
    assert om.opendap_url(g).endswith("/granules/OMNO2d.004%3AOMI-Aura_L3-OMNO2d_2005m0101_v004-x.he5")
    link = "https://opendap.earthdata.nasa.gov/collections/C1/granules/abc.he5"
    assert om.opendap_url(g | {"links": [{"href": link}]}) == link


@pytest.mark.network
def test_live_one_summer_day_kyiv():
    g = om.earthdata.get_public(
        "https://cmr.earthdata.nasa.gov/search/granules.json",
        params={"short_name": om.SHORT_NAME, "version": om.VERSION,
                "temporal": "2020-07-03T00:00:00Z,2020-07-03T12:00:00Z"}).json()["feed"]["entry"][0]
    mean, frac = om._fetch_day(g, *om.grid_index(KYIV))
    assert 0.5e15 < mean < 5e15 and frac == pytest.approx(1.0)
