import { describe, expect, it } from 'vitest';
import { binIndex, hexToRgb, mix, binEdges } from '../theme/palettes';
import { cellIndex, pointInGeometry, latToMercY, mercYToLat } from './geo';
import { seriesCsv } from './exporters';
import type { AnalysisResult, MapLayer } from '../data/types.gen';

describe('palettes', () => {
  it('bins a symmetric scale and clamps out-of-range values', () => {
    expect(binIndex(-0.8, 0.8, 10)).toBe(0);
    expect(binIndex(-0.01, 0.8, 10)).toBe(4);
    expect(binIndex(0.01, 0.8, 10)).toBe(5);
    expect(binIndex(5, 0.8, 10)).toBe(9);
    expect(binIndex(-5, 0.8, 10)).toBe(0);
  });
  it('parses short and long hex and rgb()', () => {
    expect(hexToRgb('#fff')).toEqual([255, 255, 255]);
    expect(hexToRgb('#111418')).toEqual([17, 20, 24]);
    expect(hexToRgb('rgb(1, 2, 3)')).toEqual([1, 2, 3]);
  });
  it('mixes towards the background', () => {
    expect(mix([0, 0, 0], [255, 255, 255], 0.5)).toEqual([128, 128, 128]);
  });
  it('builds bin edges', () => {
    const e = binEdges(1, 10);
    expect(e).toHaveLength(11);
    expect(e[0]).toBe(-1);
    expect(e[10]).toBe(1);
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

describe('exporters', () => {
  it('writes the series as it is, with provenance and the synthetic flag', () => {
    const a = {
      period: { start: '1981-01', end: '1981-02' },
      provenance: { dataset: 'X', synthetic: true },
      series: { dates: ['1981-01', '1981-02'], raw: [1.5, null], anomaly: [0.1, null], baseline: 'b' },
      trend: { display: { annotation: '+0.1 per decade' } },
      verdict: { headline: 'H' },
    } as unknown as AnalysisResult;
    const csv = seriesCsv(a, 'Var', 'Reg');
    expect(csv).toContain('SYNTHETIC');
    expect(csv).toContain('1981-01,1.5,0.1');
    expect(csv).toContain('1981-02,,');
  });
});
