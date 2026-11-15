// @vitest-environment node
/**
 * Every data file the app ships must match the shared contract in schema/ (same check the
 * browser runs on load, and the same as scripts/check_data.py on the Python side).
 */
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import Ajv2020 from 'ajv/dist/2020';

const root = path.resolve(process.cwd(), '..'); // vitest runs from frontend/
const schemaDir = path.join(root, 'schema');
const dataDir = path.join(root, 'frontend/public/data');
const read = (p: string) => JSON.parse(readFileSync(p, 'utf-8'));

const ajv = new Ajv2020({ strict: false, allErrors: true });
ajv.addSchema(read(path.join(schemaDir, 'common.schema.json')));
const v = (name: string) => ajv.compile(read(path.join(schemaDir, `${name}.schema.json`)));

const groups: [string, string, string[]][] = [
  ['index', '', ['index.json']],
  ['catalog', '', ['catalog.json']],
  ['validation', '', ['validation.json']],
  ['map', 'map', readdirSync(path.join(dataDir, 'map'))],
  ['analysis', 'analysis', readdirSync(path.join(dataDir, 'analysis'))],
  ['compare', 'compare', readdirSync(path.join(dataDir, 'compare'))],
];

describe('data contract', () => {
  for (const [schema, dir, files] of groups) {
    const validate = v(schema);
    it(`${schema}: ${files.length} file(s) match the schema`, () => {
      expect(files.length).toBeGreaterThan(0);
      for (const f of files) {
        const ok = validate(read(path.join(dataDir, dir, f)));
        expect(ok, `${dir}/${f}: ${ajv.errorsText(validate.errors)}`).toBe(true);
      }
    });
  }

  it('every verdict in the index has its analysis file, and every story region has the core variables', () => {
    const index = read(path.join(dataDir, 'index.json'));
    const have = new Set(readdirSync(path.join(dataDir, 'analysis')));
    for (const key of Object.keys(index.verdicts)) expect(have.has(`${key}.json`), key).toBe(true);
    expect(have.size).toBe(Object.keys(index.verdicts).length);
    for (const r of index.regions.filter((x: { story: boolean }) => x.story)) {
      for (const va of ['t2m', 'precip', 'soil']) expect(have.has(`${r.id}__${va}.json`), `${r.id}/${va}`).toBe(true);
    }
    for (const c of index.cases) expect(have.has(`${c.region_id}__${c.variable_id}.json`)).toBe(true);
  });

  it('countries carry an ISO code instead of an outline; other regions carry their outline', () => {
    const index = read(path.join(dataDir, 'index.json'));
    for (const r of index.regions) {
      if (r.geometry === null) expect(r.iso, r.id).toMatch(/^[A-Z]{3}$/);
      else expect(r.geometry.coordinates.length, r.id).toBeGreaterThan(0);
    }
    expect(index.regions.filter((r: { kind: string }) => r.kind === 'country').length).toBeGreaterThan(100);
  });

  it('map arrays have one value per grid cell', () => {
    for (const f of readdirSync(path.join(dataDir, 'map'))) {
      const m = read(path.join(dataDir, 'map', f));
      expect(m.slope_per_decade).toHaveLength(m.grid.nlat * m.grid.nlon);
      expect(m.significant).toHaveLength(m.grid.nlat * m.grid.nlon);
    }
  });
});
