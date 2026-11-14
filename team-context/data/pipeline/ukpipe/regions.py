"""Region config + fractional-overlap area weights for regular lat/lon grids."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

PIPE = Path(__file__).resolve().parents[1]
CACHE = PIPE / "data" / "cache" / "weights"
R_EARTH_KM = 6371.0


@dataclass
class Region:
    name: str
    type: str
    bounds: tuple  # lon_min, lat_min, lon_max, lat_max
    cfg: dict
    geom: object = None  # shapely geometry for polygons

    @property
    def area_km2(self) -> float:
        """True region area on the sphere (bbox: R²Δλ(sinφn−sinφs); polygon: equal-area projection)."""
        if getattr(self, "_area", None) is None:
            lo0, la0, lo1, la1 = self.bounds
            if self.is_bbox:
                self._area = R_EARTH_KM ** 2 * np.deg2rad(lo1 - lo0) * (np.sin(np.deg2rad(la1)) - np.sin(np.deg2rad(la0)))
            else:
                import shapely
                tf = lambda c: np.c_[np.deg2rad(c[:, 0]) * R_EARTH_KM, np.sin(np.deg2rad(c[:, 1])) * R_EARTH_KM]
                self._area = float(shapely.area(shapely.transform(self.geom, tf)))
        return self._area

    @property
    def is_bbox(self):
        return self.type == "bbox"

    def covered_by(self, lon_min, lat_min, lon_max, lat_max, tol=0.05):
        a = self.bounds
        return a[0] >= lon_min - tol and a[1] >= lat_min - tol and a[2] <= lon_max + tol and a[3] <= lat_max + tol

    def contains_points(self, lon, lat):
        lon = np.asarray(lon, float); lat = np.asarray(lat, float)
        if self.is_bbox:
            b = self.bounds
            return (lon >= b[0]) & (lon <= b[2]) & (lat >= b[1]) & (lat <= b[3])
        import shapely
        return shapely.contains_xy(self.geom, lon, lat)


def load_polygon(shp: Path, adm0: str):
    import shapefile
    from shapely.geometry import shape
    r = shapefile.Reader(str(shp))
    flds = [f[0] for f in r.fields[1:]]
    for sr in r.iterShapeRecords():
        rec = dict(zip(flds, sr.record))
        if rec.get("ADM0_A3") == adm0:
            return shape(sr.shape.__geo_interface__)
    raise KeyError(f"{adm0} not in {shp}")


def load_region(name: str) -> Region:
    cfg = yaml.safe_load((PIPE / "config" / "regions.yaml").read_text())
    aliases = {c["alias"]: k for k, c in cfg.items() if isinstance(c, dict) and c.get("alias")}
    name = aliases.get(name, name)  # e.g. catalog name ukraine_sa_bbox -> archive key ukraine_bbox (Q2)
    if name not in cfg:
        raise SystemExit(f"Unknown region {name!r}; choices: {list(cfg)}")
    c = cfg[name]
    if c["type"] == "bbox":
        return Region(name, "bbox", (c["lon_min"], c["lat_min"], c["lon_max"], c["lat_max"]), c)
    geom = load_polygon(PIPE / c["shapefile"], c["adm0_a3"])
    import shapely
    shapely.prepare(geom)
    return Region(name, "polygon", tuple(geom.bounds), c, geom)


def bounds_from_centres(c: np.ndarray) -> np.ndarray:
    """(n,2) cell edges from regularly spaced centres."""
    c = np.asarray(c, float)
    d = np.median(np.abs(np.diff(c))) if len(c) > 1 else 1.0
    return np.stack([c - d / 2, c + d / 2], axis=1)


def _overlap_1d(b: np.ndarray, lo: float, hi: float) -> np.ndarray:
    b0, b1 = np.minimum(b[:, 0], b[:, 1]), np.maximum(b[:, 0], b[:, 1])
    return np.clip(np.minimum(b1, hi) - np.maximum(b0, lo), 0, None) / (b1 - b0)


def cell_weights(region: Region, lat_b: np.ndarray, lon_b: np.ndarray, tag: str = ""):
    """Return (frac, area_km2) arrays shaped (nlat, nlon).

    frac = fraction of the cell's lat/lon rectangle inside the region (fractional overlap,
    not cell centres). Area-weighting uses the spherical cell area R² Δλ (sin φn − sin φs);
    weight = frac * area. For polygons frac is the planar (degree-space) overlap fraction,
    which is accurate to <<1% for cells ≤ 5°.
    """
    lat_b = np.asarray(lat_b, float); lon_b = np.asarray(lon_b, float)
    s_n = np.sin(np.deg2rad(lat_b.max(1))); s_s = np.sin(np.deg2rad(lat_b.min(1)))
    dlon = np.deg2rad(np.abs(lon_b[:, 1] - lon_b[:, 0]))
    area = R_EARTH_KM ** 2 * np.outer(s_n - s_s, dlon)
    lo0, la0, lo1, la1 = region.bounds
    if region.is_bbox:
        frac = np.outer(_overlap_1d(lat_b, la0, la1), _overlap_1d(lon_b, lo0, lo1))
        return frac, area
    key = hashlib.md5(region.name.encode() + lat_b.tobytes() + lon_b.tobytes()).hexdigest()[:16]
    CACHE.mkdir(parents=True, exist_ok=True)
    cf = CACHE / f"{region.name}_{tag}_{key}.npz"
    if cf.exists():
        return np.load(cf)["frac"], area
    import shapely
    frac = np.zeros(area.shape)
    ilat = np.where(_overlap_1d(lat_b, la0, la1) > 0)[0]
    ilon = np.where(_overlap_1d(lon_b, lo0, lo1) > 0)[0]
    if len(ilat) and len(ilon):
        LA, LO = np.meshgrid(ilat, ilon, indexing="ij")
        LA, LO = LA.ravel(), LO.ravel()
        x0 = np.minimum(lon_b[LO, 0], lon_b[LO, 1]); x1 = np.maximum(lon_b[LO, 0], lon_b[LO, 1])
        y0 = np.minimum(lat_b[LA, 0], lat_b[LA, 1]); y1 = np.maximum(lat_b[LA, 0], lat_b[LA, 1])
        boxes = shapely.box(x0, y0, x1, y1)
        g = region.geom
        inside = shapely.contains_properly(g, boxes)
        touch = shapely.intersects(g, boxes) & ~inside
        f = inside.astype(float)
        if touch.any():
            inter = shapely.intersection(boxes[touch], g)
            f[touch] = shapely.area(inter) / shapely.area(boxes[touch])
        frac[LA, LO] = f
    np.savez_compressed(cf, frac=frac)
    return frac, area
