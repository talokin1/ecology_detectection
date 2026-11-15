/**
 * "Your own area": the visitor draws a box on the map and the app averages the 2° squares inside
 * it, one value per year, and tests that series (lib/stats.ts). The same rules as for countries:
 * each square counts by the share of it inside the box times cos(latitude); squares without a
 * complete record are left out and the panel says how much of the box they were.
 * `scripts/area_stats.py` does the same in Python from the cached grids; `stats.test.ts` compares.
 */
import type { SeriesIndex } from '../data/types.gen';
import { yearlyTrend, type YearlyTrend } from './stats';

/** [west, south, east, north] in degrees; west < east (no boxes across the date line). */
export type Box = [number, number, number, number];
export type Season = 'year' | 'djf' | 'mam' | 'jja' | 'son';
export const SEASONS: Season[] = ['year', 'djf', 'mam', 'jja', 'son'];
export const isSeason = (s: string | null): s is Season => s !== null && (SEASONS as string[]).includes(s);

export type GridSeries = {
  grid: SeriesIndex['grid'];
  years: number[];
  /** Mean of each square over the years (NaN = no complete record). */
  mean: Float32Array;
  /** Step size of each square, and the differences from the mean counted in those steps, year by year. */
  step: Float32Array;
  counts: Int16Array;
};

const round1 = (v: number) => Math.round(v * 10) / 10;

export function normaliseBox(a: [number, number], b: [number, number]): Box {
  const clampLon = (v: number) => Math.max(-180, Math.min(180, v));
  const clampLat = (v: number) => Math.max(-90, Math.min(90, v));
  return [round1(clampLon(Math.min(a[0], b[0]))), round1(clampLat(Math.min(a[1], b[1]))),
    round1(clampLon(Math.max(a[0], b[0]))), round1(clampLat(Math.max(a[1], b[1])))];
}

/** A box must be a real area: at least one degree each way. */
export const boxIsValid = (b: Box) => b.every(Number.isFinite) && b[2] - b[0] >= 1 && b[3] - b[1] >= 1
  && b[0] >= -180 && b[2] <= 180 && b[1] >= -90 && b[3] <= 90;

export function parseBox(s: string | null): Box | null {
  if (!s) return null;
  const p = s.split(',').map(Number);
  if (p.length !== 4) return null;
  const b = p as Box;
  return boxIsValid(b) ? b : null;
}

export const boxParam = (b: Box) => b.map(round1).join(',');

const deg = (v: number, pos: string, neg: string) => `${Math.abs(round1(v))}°${v >= 0 ? pos : neg}`;
/** "46°N to 62°N, 46°W to 20°W" */
export const boxLabel = (b: Box) => `${deg(b[1], 'N', 'S')} to ${deg(b[3], 'N', 'S')}, ${deg(b[0], 'E', 'W')} to ${deg(b[2], 'E', 'W')}`;

export function parseSeries(index: SeriesIndex, variable: string, season: Season, buf: ArrayBuffer): GridSeries {
  const view = index.variables[variable][season];
  const cells = index.grid.nlat * index.grid.nlon;
  const n = view.last_year - view.first_year + 1;
  if (buf.byteLength !== cells * 8 + n * cells * 2) throw new Error(`series/${view.file} has an unexpected size`);
  return {
    grid: index.grid,
    years: Array.from({ length: n }, (_, i) => view.first_year + i),
    mean: new Float32Array(buf, 0, cells),
    step: new Float32Array(buf, cells * 4, cells),
    counts: new Int16Array(buf, cells * 8, n * cells),
  };
}

export type AreaSeries = {
  values: number[];
  /** Squares used, and the share of the box (by weight) that had data. */
  squares: number;
  coverage: number;
};

/** Weighted yearly mean of the squares a box overlaps; null if no square in it has data. */
export function areaSeries(gs: GridSeries, box: Box): AreaSeries | null {
  const g = gs.grid;
  const cells = g.nlat * g.nlon;
  const idx: number[] = [];
  const wts: number[] = [];
  let all = 0;
  for (let r = 0; r < g.nlat; r++) {
    const lat = g.lat0 + r * g.dlat;
    const dy = Math.min(box[3], lat + g.dlat / 2) - Math.max(box[1], lat - g.dlat / 2);
    if (dy <= 0) continue;
    for (let c = 0; c < g.nlon; c++) {
      const lon = g.lon0 + c * g.dlon;
      const dx = Math.min(box[2], lon + g.dlon / 2) - Math.max(box[0], lon - g.dlon / 2);
      if (dx <= 0) continue;
      const w = ((dx * dy) / (g.dlon * g.dlat)) * Math.cos((lat * Math.PI) / 180);
      all += w;
      const i = r * g.nlon + c;
      if (Number.isFinite(gs.mean[i])) {
        idx.push(i);
        wts.push(w);
      }
    }
  }
  const sum = wts.reduce((s, v) => s + v, 0);
  if (!idx.length || sum <= 0) return null;
  const values = gs.years.map((_, y) => {
    let v = 0;
    for (let k = 0; k < idx.length; k++) v += wts[k] * (gs.mean[idx[k]] + gs.counts[y * cells + idx[k]] * gs.step[idx[k]]);
    return v / sum;
  });
  return { values, squares: idx.length, coverage: sum / all };
}

const worldCache = new WeakMap<GridSeries, number[]>();
/** The world average: every square with a complete record, weighted by cos(latitude). */
export function worldSeries(gs: GridSeries): number[] {
  const hit = worldCache.get(gs);
  if (hit) return hit;
  const g = gs.grid;
  const out = areaSeries(gs, [g.lon0 - g.dlon / 2, g.lat0 - g.dlat / 2, g.lon0 + (g.nlon - 0.5) * g.dlon, g.lat0 + (g.nlat - 0.5) * g.dlat])!.values;
  worldCache.set(gs, out);
  return out;
}

export type AreaResult = {
  years: number[];
  area: AreaSeries;
  trend: YearlyTrend | null;
  world: { values: number[]; trend: YearlyTrend | null };
  /** Trend of (area minus world), year by year. */
  gap: YearlyTrend | null;
};

export function analyseArea(gs: GridSeries, box: Box): AreaResult | null {
  const area = areaSeries(gs, box);
  if (!area) return null;
  const world = worldSeries(gs);
  return {
    years: gs.years, area, trend: yearlyTrend(gs.years, area.values),
    world: { values: world, trend: yearlyTrend(gs.years, world) },
    gap: yearlyTrend(gs.years, area.values.map((v, i) => v - world[i])),
  };
}

/** Trend of (area A minus area B), year by year. */
export function gapBetween(gs: GridSeries, a: AreaSeries, b: AreaSeries): YearlyTrend | null {
  return yearlyTrend(gs.years, a.values.map((v, i) => v - b.values[i]));
}

/** Outward-rounded "x to y" for a range, with a real minus sign and explicit plus. */
export function formatRange(ci: [number, number], decimals: number): string {
  const f = 10 ** decimals;
  const fmt = (v: number) => {
    const r = v === 0 ? 0 : v;
    return `${r > 0 ? '+' : r < 0 ? '−' : ''}${Math.abs(r).toFixed(decimals)}`;
  };
  return `${fmt(Math.floor(ci[0] * f) / f)} to ${fmt(Math.ceil(ci[1] * f) / f)}`;
}

export function formatRate(v: number, decimals: number): string {
  const r = Number(v.toFixed(decimals));
  return `${r > 0 ? '+' : r < 0 ? '−' : ''}${Math.abs(r).toFixed(decimals)}`;
}
