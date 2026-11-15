// @vitest-environment node
/**
 * The browser's trend test (stats.ts) and area averaging (area.ts) against the Python reference:
 * stats.fixture.json is written by `python scripts/area_stats.py --fixture ...` from
 * trend_stats.py and the cached NetCDF grids. If these tests fail, the browser would show
 * numbers that the project's reference code does not produce.
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import fixture from './stats.fixture.json';
import { analyseArea, parseSeries, type Box, type Season } from './area';
import { normalTwoSided, studentTwoSided, yearlyTrend, type YearlyTrend } from './stats';
import type { SeriesIndex } from '../data/types.gen';

type Expected = {
  level: string; per_decade: number; ci90: number[]; ci95: number[]; ci99: number[];
  p_mk: number; p_ols: number; ols_per_decade: number; n: number;
} | null;

/** Relative closeness, with an absolute floor for values near zero. */
function close(got: number, want: number, rel: number, abs = 1e-12) {
  expect(Math.abs(got - want)).toBeLessThanOrEqual(Math.max(abs, rel * Math.abs(want)));
}

function same(got: YearlyTrend | null, want: Expected, rel: number, abs: number) {
  if (want === null) return expect(got).toBeNull();
  expect(got).not.toBeNull();
  const g = got as YearlyTrend;
  expect(g.n).toBe(want.n);
  close(g.perDecade, want.per_decade, rel, abs);
  (['ci90', 'ci95', 'ci99'] as const).forEach((k) => {
    close(g[k][0], want[k][0], rel, abs);
    close(g[k][1], want[k][1], rel, abs);
  });
  close(g.olsPerDecade, want.ols_per_decade, rel, abs);
  close(g.pMk, want.p_mk, Math.max(rel, 1e-9) * 50, abs);
  close(g.pOls, want.p_ols, Math.max(rel, 1e-9) * 50, abs);
  expect(g.level).toBe(want.level);
}

describe('special functions', () => {
  it('normal and Student-t tails match scipy', () => {
    close(normalTwoSided(1.959963984540054), 0.05, 1e-12);
    close(normalTwoSided(4.5), 6.795346249460121e-6, 1e-10);
    close(normalTwoSided(0.3), 0.7641771556220949, 1e-12);
    close(studentTwoSided(2.0, 10), 0.07338803477074037, 1e-10);
    close(studentTwoSided(5.5, 21.7), 1.6606682539067423e-5, 1e-10);
    close(studentTwoSided(0.4, 3.2), 0.7143747855913561, 1e-10);
  });
});

describe('yearly trend test: browser port against trend_stats.py', () => {
  for (const c of fixture.series) {
    it(c.name, () => same(yearlyTrend(c.years, c.values), c.expected as Expected, 1e-9, 1e-12));
  }
});

describe('your own area: browser result against the cached grids', () => {
  const dir = path.resolve(process.cwd(), 'public/data/series');
  const index = JSON.parse(readFileSync(path.join(dir, 'index.json'), 'utf-8')) as SeriesIndex;
  for (const c of fixture.areas) {
    it(`${c.variable} ${c.season} ${c.box.join(',')}`, () => {
      const view = index.variables[c.variable][c.season as Season];
      const file = readFileSync(path.join(dir, view.file));
      const gs = parseSeries(index, c.variable, c.season as Season, file.buffer.slice(file.byteOffset, file.byteOffset + file.byteLength) as ArrayBuffer);
      expect(gs.years).toEqual(c.years);
      const res = analyseArea(gs, c.box as Box);
      expect(res).not.toBeNull();
      const r = res!;
      expect(r.area.squares).toBe(c.expected.squares);
      close(r.area.coverage, c.expected.coverage, 1e-9);
      // values are stored in steps of `scale`: the yearly mean is within one step of the exact one
      r.area.values.forEach((v, i) => expect(Math.abs(v - c.expected.values[i])).toBeLessThanOrEqual(view.scale));
      // slopes may differ by the rounding of the stored steps: at most two steps over the record
      const tol = (2 * view.scale * 10) / (c.years.length - 1) + 1e-9;
      same(r.trend, c.expected.trend as Expected, 2e-2, tol);
      same(r.world.trend, c.expected.world as Expected, 2e-2, tol);
      same(r.gap, c.expected.gap as Expected, 2e-2, tol);
    });
  }
});
