"""Polygon outlines (IPCC AR6 reference regions): point-in-polygon rule, box readers, region sets."""

import json

import numpy as np
import pytest
import yaml
from test_power_zarr import fake  # noqa: F401 - fixture
from trend_detective import acquire
from trend_detective.power_zarr import Region, region_series

TRIANGLE = [[-40.0, -40.0], [40.0, -40.0], [-40.0, 40.0]]  # lower-left half of a square


def test_outline_mask_half_open_edges():
    square = Region.from_polygons("sq", [[[0, 0], [10, 0], [10, 10], [0, 10]]])
    m = square.outline_mask([0, 5, 10], [0, 5, 10])
    # left and bottom edges in, right and top edges out: neighbours never share a cell
    assert m.tolist() == [[True, True, False], [True, True, False], [False, False, False]]


def test_neighbouring_outlines_never_share_a_cell():
    a = Region.from_polygons("a", [[[0, 0], [5, 0], [5, 10], [0, 10]]])
    b = Region.from_polygons("b", [[[5, 0], [10, 0], [10, 10], [5, 10]]])
    lat, lon = np.arange(0, 10.5, 0.5), np.arange(0, 10.5, 0.625)
    assert not (a.outline_mask(lat, lon) & b.outline_mask(lat, lon)).any()


def test_from_polygons_bounds_and_antimeridian():
    r = Region.from_polygons("t", [TRIANGLE])
    assert (r.lat_min, r.lat_max, r.lon_min, r.lon_max) == (-40, 40, -40, 40)
    rar = Region.from_polygons(
        "rar", [[[40, 65], [180, 65], [180, 74], [40, 72]], [[-180, 65], [-168, 65], [-168, 72], [-180, 74]]]
    )
    assert rar.crosses_antimeridian and (rar.lon_min, rar.lon_max) == (40, -168)
    assert rar.outline_mask([70], [100, -170, 0]).tolist() == [[True, True, False]]


def test_outline_changes_the_cache_key_but_a_box_keeps_its_old_key():
    box = Region("b", -40, 40, -40, 40)
    tri = Region.from_polygons("t", [TRIANGLE])
    assert box.cache_key == box.bbox_key and tri.cache_key != box.cache_key and tri.outline_digest


def test_power_series_is_clipped_to_the_outline(fake, tmp_path):  # noqa: F811
    """Fake T2M = latitude + month. The triangle keeps the south-west half, so its mean is below
    the full box's (whose cos-weighted latitude mean is 0)."""
    box = region_series("T2M", Region("b", -40, 40, -40, 40), cache_dir=tmp_path)
    tri = region_series("T2M", Region.from_polygons("t", [TRIANGLE], "test outline"), cache_dir=tmp_path)
    assert abs(box.iloc[0]) < 1e-9 and tri.iloc[0] < -5
    prov = json.loads(next(tmp_path.glob("*.csv.provenance.json")).read_text())
    sidecars = [json.loads(p.read_text()) for p in tmp_path.glob("*.provenance.json")]
    outlined = [p for p in sidecars if "outline" in p]
    assert prov and len(outlined) == 1 and outlined[0]["outline"]["source"] == "test outline"
    assert "outline" in outlined[0]["processing"][0]


def test_box_only_readers_refuse_outlines():
    from trend_detective import modis_ndvi, omi_no2

    tri = Region.from_polygons("t", [TRIANGLE])
    for reader in (modis_ndvi, omi_no2):
        with pytest.raises(ValueError, match="polygon outline"):
            reader.region_series(tri, offline=True)


def test_catalog_loads_ar6_regions():
    regions = acquire.list_regions()
    ar6 = acquire.region_set("ar6", buildable_only=False)
    assert len(ar6) == 46 and "ar6_neu" in regions and "ukraine" in regions
    built = acquire.region_set("ar6")
    assert {"ar6_gic", "ar6_ean", "ar6_wan"}.isdisjoint(built) and len(built) == 43
    neu = regions["ar6_neu"]
    assert neu["land_only"] is True and neu["region"].polygons and neu["region"].outline_source
    assert regions["ar6_rar"]["region"].crosses_antimeridian


def test_ar6_yaml_matches_the_vendored_csv():
    """The generated file must come from the committed source CSV, unchanged."""
    import hashlib

    doc = yaml.safe_load((acquire.CATALOG_DIR / "regions_ar6.yaml").read_text())
    src = acquire.REPO_ROOT / doc["set"]["source_file"]
    assert hashlib.sha256(src.read_bytes()).hexdigest() == doc["set"]["source_sha256"]


def test_outline_variable_from_box_reader_is_unsupported(monkeypatch):
    with pytest.raises(ValueError, match="^unsupported"):
        acquire.get_series("ndvi_modis", "ar6_neu")
