/**
 * Map filters (production UX plan A3). They only HIDE squares, using the `significant` flag and
 * the sign that are already in map.json. Nothing is computed.
 */
import type { MapLayer } from '../data/types.gen';

export type ShowFilter = 'all' | 'clear' | 'clear_pos' | 'clear_neg';
export const SHOW_VALUES: ShowFilter[] = ['all', 'clear', 'clear_pos', 'clear_neg'];

export function isShowFilter(v: string | null): v is ShowFilter {
  return v !== null && (SHOW_VALUES as string[]).includes(v);
}

export function cellVisible(value: number | null, significant: number, show: ShowFilter): boolean {
  if (value === null) return true; // "not enough data" stays visible as hatching
  if (show === 'all') return true;
  if (!significant) return false;
  if (show === 'clear_pos') return value > 0;
  if (show === 'clear_neg') return value < 0;
  return true;
}

/** Number of squares with data that remain visible (for the "nothing matches" state). */
export function countVisible(layer: MapLayer, show: ShowFilter): number {
  let n = 0;
  for (let i = 0; i < layer.slope_per_decade.length; i++) {
    const v = layer.slope_per_decade[i];
    if (v !== null && cellVisible(v, layer.significant[i], show)) n++;
  }
  return n;
}
