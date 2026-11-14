/** Small geometry helpers for drawing the grid in Web Mercator and hit-testing it. */
import type { MapLayer } from '../data/types.gen';

export const MERC_MAX_LAT = 85.0511287798;

export function latToMercY(lat: number): number {
  const c = Math.max(-MERC_MAX_LAT, Math.min(MERC_MAX_LAT, lat));
  const r = (c * Math.PI) / 180;
  return Math.log(Math.tan(Math.PI / 4 + r / 2));
}

export function mercYToLat(y: number): number {
  return (Math.atan(Math.sinh(y)) * 180) / Math.PI;
}

/** Index into the flat grid arrays for a lon/lat, or -1 outside the grid. */
export function cellIndex(layer: MapLayer, lon: number, lat: number): number {
  const g = layer.grid;
  const row = Math.floor((lat - (g.lat0 - g.dlat / 2)) / g.dlat);
  const wrapped = ((((lon + 180) % 360) + 360) % 360) - 180;
  const col = Math.floor((wrapped - (g.lon0 - g.dlon / 2)) / g.dlon);
  if (row < 0 || row >= g.nlat || col < 0 || col >= g.nlon) return -1;
  return row * g.nlon + col;
}

export function formatLatLon(lon: number, lat: number): string {
  const la = `${Math.abs(lat).toFixed(1)}° ${lat >= 0 ? 'N' : 'S'}`;
  const lo = `${Math.abs(lon).toFixed(1)}° ${lon >= 0 ? 'E' : 'W'}`;
  return `${la}, ${lo}`;
}

/** Point-in-polygon (ray casting) for GeoJSON Polygon / MultiPolygon coordinates. */
export function pointInGeometry(lon: number, lat: number, geometry: { type: string; coordinates: unknown[] }): boolean {
  const polys = (geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates) as number[][][][];
  return polys.some((rings) => {
    let inside = false;
    rings.forEach((ring, k) => {
      let inRing = false;
      for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        const [xi, yi] = ring[i];
        const [xj, yj] = ring[j];
        if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inRing = !inRing;
      }
      if (k === 0) inside = inRing;
      else if (inRing) inside = false; // hole
    });
    return inside;
  });
}

export function distanceKm(a: [number, number], b: [number, number]): number {
  const toR = Math.PI / 180;
  const dLat = (b[1] - a[1]) * toR;
  const dLon = (b[0] - a[0]) * toR;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[1] * toR) * Math.cos(b[1] * toR) * Math.sin(dLon / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(h));
}
