/**
 * Data palettes (trend-viz skill). ColorBrewer 10-class diverging schemes, ordered from the
 * most negative bin to the most positive. Colour-blind safe; never rainbow.
 *  - RdBu: temperature (blue = cooling, red = warming)
 *  - BrBG: water (brown = drier, teal = wetter)
 *  - PuOr: pollution (purple = cleaner, orange = more polluted)
 */
export type PaletteName = 'RdBu' | 'BrBG' | 'PuOr';

export const PALETTES: Record<PaletteName, string[]> = {
  RdBu: ['#053061', '#2166ac', '#4393c3', '#92c5de', '#d1e5f0', '#fddbc7', '#f4a582', '#d6604d', '#b2182b', '#67001f'],
  BrBG: ['#543005', '#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#c7eae5', '#80cdc1', '#35978f', '#01665e', '#003c30'],
  PuOr: ['#2d004b', '#542788', '#8073ac', '#b2abd2', '#d8daeb', '#fee0b6', '#fdb863', '#e08214', '#b35806', '#7f3b08'],
};

/** Two-region identity colours (Okabe-Ito blue and vermillion). */
export const REGION_COLORS = ['#0072B2', '#D55E00'] as const;

/** Bin index (0..bins-1) of a value on a symmetric scale [-limit, +limit]; values beyond clamp. */
export function binIndex(value: number, limit: number, bins: number): number {
  const t = (value + limit) / (2 * limit);
  return Math.max(0, Math.min(bins - 1, Math.floor(t * bins)));
}

export function colorFor(value: number, limit: number, palette: PaletteName): string {
  const p = PALETTES[palette];
  return p[binIndex(value, limit, p.length)];
}

/** Colour of a clearly positive / negative mark in charts (strong but not the darkest bin). */
export function signColor(palette: PaletteName, sign: number): string {
  const p = PALETTES[palette];
  return sign >= 0 ? p[p.length - 3] : p[2];
}

/** Parse #rgb, #rrggbb or rgb()/rgba() into [r, g, b]. Build tools may shorten #ffffff to #fff. */
export function hexToRgb(color: string): [number, number, number] {
  const c = color.trim();
  const m = c.match(/^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)/i);
  if (m) return [Number(m[1]), Number(m[2]), Number(m[3])];
  let h = c.replace('#', '');
  if (h.length === 3 || h.length === 4) h = h.split('').slice(0, 3).map((x) => x + x).join('');
  const rgb: [number, number, number] = [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
  return rgb.some(Number.isNaN) ? [255, 255, 255] : rgb;
}

/** Mix a colour towards a background: amount 0 = colour, 1 = background. */
export function mix(rgb: [number, number, number], bg: [number, number, number], amount: number): [number, number, number] {
  return [0, 1, 2].map((i) => Math.round(rgb[i] * (1 - amount) + bg[i] * amount)) as [number, number, number];
}

/** Bin edges for the legend, e.g. [-0.8, -0.64, ..., 0.8]. */
export function binEdges(limit: number, bins: number): number[] {
  return Array.from({ length: bins + 1 }, (_, i) => -limit + (2 * limit * i) / bins);
}
