import { describe, expect, it } from 'vitest';
import { binIndex, hexToRgb, PALETTES, type PaletteName } from '../theme/palettes';
import { desaturate, rgbToLab, labToRgb, swatches, cellRgb, isDarkBin } from '../theme/encoding';
import { cellIndex, pointInGeometry, latToMercY, mercYToLat } from './geo';
import { formatCell } from './format';
import { seriesCsv } from './exporters';
import type { AnalysisResult, MapLayer } from '../data/types.gen';

describe('palettes', () => {
  it('has 11 classes with a neutral centre', () => {
    for (const p of Object.values(PALETTES)) {
      expect(p).toHaveLength(11);
      const [L, a, b] = rgbToLab(hexToRgb(p[5]));
      expect(L).toBeGreaterThan(90);
      expect(Math.hypot(a, b)).toBeLessThan(3);
    }
  });
  it('bins a symmetric scale and clamps out-of-range values', () => {
    expect(binIndex(-0.8, 0.8, 11)).toBe(0);
    expect(binIndex(0, 0.8, 11)).toBe(5);
    expect(binIndex(0.001, 0.8, 11)).toBe(5); // tiny values stay neutral (review P2-5)
    expect(binIndex(5, 0.8, 11)).toBe(10);
  });
  it('parses short and long hex and rgb()', () => {
    expect(hexToRgb('#fff')).toEqual([255, 255, 255]);
    expect(hexToRgb('#111418')).toEqual([17, 20, 24]);
    expect(hexToRgb('rgb(1, 2, 3)')).toEqual([1, 2, 3]);
  });
});

describe('significance encoding (review P0-2)', () => {
  it('round-trips through CIELAB', () => {
    for (const c of [[17, 20, 24], [214, 96, 77], [1, 102, 94]] as [number, number, number][]) {
      const back = labToRgb(rgbToLab(c));
      back.forEach((v, i) => expect(Math.abs(v - c[i])).toBeLessThanOrEqual(1));
    }
  });
  it('keeps lightness: every faded swatch is within ΔL* < 5 of its full swatch', () => {
    for (const name of Object.keys(PALETTES) as PaletteName[]) {
      const s = swatches(name);
      s.full.forEach((c, i) => {
        expect(Math.abs(rgbToLab(c)[0] - rgbToLab(s.faded[i])[0])).toBeLessThan(5);
      });
    }
  });
  it('removes most of the chroma', () => {
    const c = hexToRgb('#b2182b');
    const [, a, b] = rgbToLab(c);
    const [, a2, b2] = rgbToLab(desaturate(c));
    expect(Math.hypot(a2, b2)).toBeLessThan(0.35 * Math.hypot(a, b));
  });
  it('colours cells by size and certainty, and marks dark bins for light dots', () => {
    expect(cellRgb(0.7, true, 0.8, 'RdBu')).not.toEqual(cellRgb(0.7, false, 0.8, 'RdBu'));
    expect(isDarkBin(0.79, 0.8, 'RdBu')).toBe(true);
    expect(isDarkBin(0.1, 0.8, 'RdBu')).toBe(false);
  });
});

describe('geo', () => {
  const layer = { grid: { lat0: -89.5, lon0: -179.5, dlat: 1, dlon: 1, nlat: 180, nlon: 360 } } as MapLayer;
  it('finds the grid cell of a point', () => {
    expect(cellIndex(layer, -179.9, -89.9)).toBe(0);
    expect(cellIndex(layer, 179.9, 89.9)).toBe(180 * 360 - 1);
    expect(cellIndex(layer, 30.5, 50.5)).toBe((50 + 90) * 360 + (30 + 180));
  });
  it('inverts the Mercator latitude', () => {
    expect(mercYToLat(latToMercY(48.3))).toBeCloseTo(48.3, 6);
  });
  it('tests points against polygons with holes', () => {
    const square = { type: 'Polygon', coordinates: [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]], [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]] };
    expect(pointInGeometry(2, 2, square)).toBe(true);
    expect(pointInGeometry(5, 5, square)).toBe(false);
    expect(pointInGeometry(12, 2, square)).toBe(false);
  });
});

describe('format', () => {
  it('shows pre-rounded values with the declared decimals and a real minus sign', () => {
    expect(formatCell(0.2, 2)).toBe('+0.20');
    expect(formatCell(0.25, 2)).toBe('+0.25');
    expect(formatCell(-1.5, 1)).toBe('−1.5');
    expect(formatCell(0, 2)).toBe('0.00');
  });
});

describe('exporters', () => {
  it('writes the series as it is, with provenance, units and the synthetic flag', () => {
    const a = {
      period: { start: '1981-01', end: '1981-02' },
      provenance: { dataset: 'X', synthetic: true, version: null, doi: null, accessed: '2026-11-14', caveat: 'c' },
      series: { dates: ['1981-01', '1981-02'], raw: [1.5, null], anomaly: [0.1, null], baseline: 'b', anomaly_units: '°C' },
      trend: { display: { annotation: '+0.1 per decade' } },
      verdict: { headline: 'H' },
    } as unknown as AnalysisResult;
    const csv = seriesCsv(a, 'Var', 'Reg');
    expect(csv).toContain('SYNTHETIC');
    expect(csv).toContain('accessed: 2026-11-14');
    expect(csv).toContain('1981-01,1.5,0.1');
    expect(csv).toContain('1981-02,,');
  });
});

describe('map filters (production UX plan A3)', async () => {
  const { cellVisible, countVisible } = await import('./filter');
  it('hides only what the filter excludes', () => {
    expect(cellVisible(0.3, 0, 'all')).toBe(true);
    expect(cellVisible(0.3, 0, 'clear')).toBe(false);
    expect(cellVisible(0.3, 1, 'clear')).toBe(true);
    expect(cellVisible(-0.3, 1, 'clear_pos')).toBe(false);
    expect(cellVisible(-0.3, 1, 'clear_neg')).toBe(true);
    expect(cellVisible(null, 0, 'clear')).toBe(true); // no-data hatching stays
  });
  it('leaves no coloured non-significant square under "clear trends only"', () => {
    const layer = { slope_per_decade: [0.2, -0.1, null, 0.5], significant: [1, 0, 0, 0] } as unknown as MapLayer;
    expect(countVisible(layer, 'all')).toBe(3);
    expect(countVisible(layer, 'clear')).toBe(1);
    expect(countVisible(layer, 'clear_neg')).toBe(0);
  });
});
