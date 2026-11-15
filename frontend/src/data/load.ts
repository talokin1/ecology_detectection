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
import seriesIndexSchema from '../../../schema/series-index.schema.json';
import type { AnalysisResult, Catalog, Compare, Index, MapLayer, SeriesIndex, Validation } from './types.gen';
import { parseSeries, type GridSeries, type Season } from '../lib/area';

const ajv = new Ajv2020({ allErrors: false, strict: false });
ajv.addSchema(common);
const validators = {
  index: ajv.compile(indexSchema),
  analysis: ajv.compile(analysisSchema),
  map: ajv.compile(mapSchema),
  compare: ajv.compile(compareSchema),
  catalog: ajv.compile(catalogSchema),
  validation: ajv.compile(validationSchema),
  seriesIndex: ajv.compile(seriesIndexSchema),
};

export class DataError extends Error {
  constructor(public file: string, message: string, public missing = false) {
    super(message);
  }
}

const cache = new Map<string, Promise<unknown>>();
const DATA_ROOT = `${import.meta.env.BASE_URL}data/`;

const RELOAD_FLAG = 'td-reloaded-for-contract';

/**
 * GitHub Pages serves every file with max-age=600, so right after a deploy a browser can mix a
 * cached old file with new code (or old code with new data). Data are always revalidated
 * (cheap 304 when unchanged); on a contract mismatch we refetch bypassing the cache, and if that
 * still fails the page itself is stale, so we reload it once.
 */
async function fetchValid<T>(file: string, validate: ValidateFunction, mode: RequestCache): Promise<T> {
  const r = await fetch(DATA_ROOT + file, { cache: mode });
  if (!r.ok) throw new DataError(file, `${file} is not available (HTTP ${r.status}).`, r.status === 404);
  const json: unknown = await r.json();
  if (!validate(json)) {
    const e = validate.errors?.[0];
    throw new DataError(file, `${file} does not match the data contract: ${e?.instancePath || '/'} ${e?.message ?? ''}`);
  }
  return json as T;
}

async function reloadStalePageOnce(): Promise<boolean> {
  try {
    if (sessionStorage.getItem(RELOAD_FLAG)) return false;
    sessionStorage.setItem(RELOAD_FLAG, '1');
    await fetch(window.location.pathname, { cache: 'reload' }); // refresh the cached index.html
    window.location.reload();
    return true;
  } catch {
    return false;
  }
}

function load<T>(file: string, validate: ValidateFunction): Promise<T> {
  const hit = cache.get(file);
  if (hit) return hit as Promise<T>;
  const p = fetchValid<T>(file, validate, 'no-cache')
    .catch(async (err) => {
      if (!(err instanceof DataError) || err.missing) throw err;
      try {
        return await fetchValid<T>(file, validate, 'reload');
      } catch (again) {
        if (again instanceof DataError && !again.missing && (await reloadStalePageOnce())) {
          return new Promise<T>(() => {}); // the page is reloading
        }
        throw again;
      }
    })
    .catch((err) => {
      cache.delete(file);
      throw err instanceof DataError ? err : new DataError(file, `${file} could not be read.`);
    });
  cache.set(file, p);
  return p;
}

type Geometry = { type: 'Polygon' | 'MultiPolygon'; coordinates: unknown[] };
let hydrated: Promise<Index> | null = null;

/**
 * index.json lists countries without outlines (they would repeat the basemap). The outline is
 * taken from basemap/countries.geojson by ISO code; parts far from the mainland (outside the
 * region's bbox) are left out, exactly as in the data.
 */
function hydratedIndex(): Promise<Index> {
  if (hydrated) return hydrated;
  hydrated = load<Index>('index.json', validators.index).then(async (index) => {
    if (!index.regions.some((r) => r.geometry === null)) return index;
    const fc = (await (await fetch(basemapUrl('countries'))).json()) as { features: { properties: { iso: string }; geometry: Geometry }[] };
    const byIso = new Map(fc.features.map((f) => [f.properties.iso, f.geometry]));
    const regions = index.regions.map((r) => {
      if (r.geometry !== null || !r.iso) return r;
      const g = byIso.get(r.iso);
      if (!g) return r;
      const polys = (g.type === 'Polygon' ? [g.coordinates] : g.coordinates) as number[][][][];
      const [w, s, e, n] = r.bbox;
      const inside = polys.filter((rings) => {
        const [x, y] = rings[0][0];
        return x >= w - 0.6 && x <= e + 0.6 && y >= s - 0.6 && y <= n + 0.6;
      });
      return { ...r, geometry: { type: 'MultiPolygon' as const, coordinates: inside } };
    });
    return { ...index, regions: regions.filter((r) => r.geometry !== null) };
  }).catch((err) => {
    hydrated = null;
    throw err;
  });
  return hydrated;
}

const gridSeries = new Map<string, Promise<GridSeries>>();
/** Yearly means of every 2° square for one variable and season (binary, about 1.5 MB). */
function loadGridSeries(variable: string, season: Season): Promise<GridSeries> {
  const key = `${variable}/${season}`;
  const hit = gridSeries.get(key);
  if (hit) return hit;
  const p = load<SeriesIndex>('series/index.json', validators.seriesIndex).then(async (index) => {
    const view = index.variables[variable]?.[season];
    if (!view) throw new DataError(key, `No yearly grid for ${variable}.`, true);
    const file = `series/${view.file}`;
    const r = await fetch(DATA_ROOT + file, { cache: 'no-cache' });
    if (!r.ok) throw new DataError(file, `${file} is not available (HTTP ${r.status}).`, r.status === 404);
    try {
      return parseSeries(index, variable, season, await r.arrayBuffer());
    } catch (e) {
      throw new DataError(file, e instanceof Error ? e.message : `${file} could not be read.`);
    }
  }).catch((err) => {
    gridSeries.delete(key);
    throw err instanceof DataError ? err : new DataError(key, `The yearly grid for ${variable} could not be read.`);
  });
  gridSeries.set(key, p);
  return p;
}

/** File name of a map view: whole year or one season, plain or minus the world average. */
export const mapFile = (variable: string, season: Season = 'year', relative = false) =>
  `map/${variable}${season === 'year' ? '' : `__${season}`}${relative ? '__rel' : ''}.json`;

export const api = {
  index: () => hydratedIndex(),
  catalog: () => load<Catalog>('catalog.json', validators.catalog),
  validation: () => load<Validation>('validation.json', validators.validation),
  map: (variable: string, season: Season = 'year', relative = false) =>
    load<MapLayer>(mapFile(variable, season, relative), validators.map),
  gridSeries: loadGridSeries,
  analysis: (region: string, variable: string) =>
    load<AnalysisResult>(`analysis/${region}__${variable}.json`, validators.analysis),
  /** Compare files are stored once per unordered pair; the caller gets them in its own order. */
  compare: async (a: string, b: string, variable: string, regionOrder: string[]) => {
    const [x, y] = regionOrder.indexOf(a) <= regionOrder.indexOf(b) ? [a, b] : [b, a];
    return load<Compare>(`compare/${x}__${y}__${variable}.json`, validators.compare);
  },
};

export const basemapUrl = (name: 'land' | 'countries') => `${import.meta.env.BASE_URL}basemap/${name}.geojson`;
