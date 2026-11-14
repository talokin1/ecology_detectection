/**
 * Loads the precomputed JSON files and validates each one against the shared schema
 * (schema/*.schema.json). The app never computes statistics; it only reads these files.
 */
import Ajv2020, { type ValidateFunction } from 'ajv/dist/2020';
import common from '../../../schema/common.schema.json';
import indexSchema from '../../../schema/index.schema.json';
import analysisSchema from '../../../schema/analysis.schema.json';
import mapSchema from '../../../schema/map.schema.json';
import compareSchema from '../../../schema/compare.schema.json';
import catalogSchema from '../../../schema/catalog.schema.json';
import validationSchema from '../../../schema/validation.schema.json';
import type { AnalysisResult, Catalog, Compare, Index, MapLayer, Validation } from './types.gen';

const ajv = new Ajv2020({ allErrors: false, strict: false });
ajv.addSchema(common);
const validators = {
  index: ajv.compile(indexSchema),
  analysis: ajv.compile(analysisSchema),
  map: ajv.compile(mapSchema),
  compare: ajv.compile(compareSchema),
  catalog: ajv.compile(catalogSchema),
  validation: ajv.compile(validationSchema),
};

export class DataError extends Error {
  constructor(public file: string, message: string, public missing = false) {
    super(message);
  }
}

const cache = new Map<string, Promise<unknown>>();
const DATA_ROOT = `${import.meta.env.BASE_URL}data/`;

function load<T>(file: string, validate: ValidateFunction): Promise<T> {
  const hit = cache.get(file);
  if (hit) return hit as Promise<T>;
  const p = fetch(DATA_ROOT + file)
    .then(async (r) => {
      if (!r.ok) throw new DataError(file, `${file} is not available (HTTP ${r.status}).`, r.status === 404);
      const json: unknown = await r.json();
      if (!validate(json)) {
        const e = validate.errors?.[0];
        throw new DataError(file, `${file} does not match the data contract: ${e?.instancePath || '/'} ${e?.message ?? ''}`);
      }
      return json as T;
    })
    .catch((err) => {
      cache.delete(file);
      throw err instanceof DataError ? err : new DataError(file, `${file} could not be read.`);
    });
  cache.set(file, p);
  return p;
}

export const api = {
  index: () => load<Index>('index.json', validators.index),
  catalog: () => load<Catalog>('catalog.json', validators.catalog),
  validation: () => load<Validation>('validation.json', validators.validation),
  map: (variable: string) => load<MapLayer>(`map/${variable}.json`, validators.map),
  analysis: (region: string, variable: string) =>
    load<AnalysisResult>(`analysis/${region}__${variable}.json`, validators.analysis),
  /** Compare files are stored once per unordered pair; the caller gets them in its own order. */
  compare: async (a: string, b: string, variable: string, regionOrder: string[]) => {
    const [x, y] = regionOrder.indexOf(a) <= regionOrder.indexOf(b) ? [a, b] : [b, a];
    return load<Compare>(`compare/${x}__${y}__${variable}.json`, validators.compare);
  },
};

export const basemapUrl = (name: 'land' | 'countries') => `${import.meta.env.BASE_URL}basemap/${name}.geojson`;
