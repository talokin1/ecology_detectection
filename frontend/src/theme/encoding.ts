/**
 * One significance encoding for every map, legend and ledger (review P0-2):
 *  - lightness and hue carry the SIZE of the trend (palette bin);
 *  - colour strength (chroma) carries CERTAINTY: cells that do not pass the map-wide test are
 *    desaturated at the same lightness (CIELAB L* kept), so "small" and "unsure" never look alike;
 *  - no data is a hatch on the land layer, never a pale colour.
 * Nothing here depends on the page theme: maps sit on a light plate in both themes.
 */
import { binIndex, hexToRgb, PALETTES, type PaletteName } from './palettes';

type RGB = [number, number, number];

const toLin = (c: number) => {
  const s = c / 255;
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
};
const fromLin = (c: number) => {
  const s = c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055;
  return Math.max(0, Math.min(255, Math.round(s * 255)));
};
const W = [0.95047, 1, 1.08883];
const f = (t: number) => (t > 216 / 24389 ? Math.cbrt(t) : (24389 / 27 * t + 16) / 116);
const fi = (t: number) => (t ** 3 > 216 / 24389 ? t ** 3 : (116 * t - 16) / (24389 / 27));

export function rgbToLab([r, g, b]: RGB): [number, number, number] {
  const [R, G, B] = [toLin(r), toLin(g), toLin(b)];
  const x = (0.4124 * R + 0.3576 * G + 0.1805 * B) / W[0];
  const y = (0.2126 * R + 0.7152 * G + 0.0722 * B) / W[1];
  const z = (0.0193 * R + 0.1192 * G + 0.9505 * B) / W[2];
  const [fx, fy, fz] = [f(x), f(y), f(z)];
  return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
}

export function labToRgb([L, a, b]: [number, number, number]): RGB {
  const fy = (L + 16) / 116;
  const fx = fy + a / 500;
  const fz = fy - b / 200;
  const [x, y, z] = [fi(fx) * W[0], fi(fy) * W[1], fi(fz) * W[2]];
  const R = 3.2406 * x - 1.5372 * y - 0.4986 * z;
  const G = -0.9689 * x + 1.8758 * y + 0.0415 * z;
  const B = 0.0557 * x - 0.204 * y + 1.057 * z;
  return [fromLin(R), fromLin(G), fromLin(B)];
}

/** Same lightness, a quarter of the chroma: "not enough evidence in this square". */
export function desaturate(rgb: RGB, keep = 0.22): RGB {
  const [L, a, b] = rgbToLab(rgb);
  return labToRgb([L, a * keep, b * keep]);
}

export type Swatches = { full: RGB[]; faded: RGB[] };
const cache = new Map<PaletteName, Swatches>();

export function swatches(palette: PaletteName): Swatches {
  const hit = cache.get(palette);
  if (hit) return hit;
  const full = PALETTES[palette].map(hexToRgb);
  const s = { full, faded: full.map((c) => desaturate(c)) };
  cache.set(palette, s);
  return s;
}

export function cellRgb(value: number, significant: boolean, limit: number, palette: PaletteName): RGB {
  const s = swatches(palette);
  const i = binIndex(value, limit, s.full.length);
  return significant ? s.full[i] : s.faded[i];
}

/** The two darkest bins at each end: stipple dots there are drawn light so they stay visible. */
export function isDarkBin(value: number, limit: number, palette: PaletteName): boolean {
  const n = PALETTES[palette].length;
  const i = binIndex(value, limit, n);
  return i <= 1 || i >= n - 2;
}
