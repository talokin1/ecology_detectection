/**
 * Year-by-year map frames (schema/frames.schema.json): decode the int8/base64 cube once and turn
 * one year into a MapLayer-shaped object, so the existing map, legend and tooltip render it as is.
 * The numbers are the pipeline's (scripts/make_app_data.py frames_layer); nothing is computed here
 * except undoing the storage encoding.
 */
import { useEffect, useState } from 'react';
import { api } from '../data/load';
import type { FramesLayer, MapLayer } from '../data/types.gen';

const decoded = new WeakMap<FramesLayer, Int8Array>();

export function decodeFrames(f: FramesLayer): Int8Array {
  let a = decoded.get(f);
  if (!a) {
    const bin = atob(f.data);
    a = new Int8Array(bin.length);
    for (let i = 0; i < bin.length; i++) a[i] = (bin.charCodeAt(i) << 24) >> 24; // byte -> signed
    decoded.set(f, a);
  }
  return a;
}

/** Values of one year (null = no data), in the layer's units. */
export function frameValues(f: FramesLayer, yearIndex: number): (number | null)[] {
  const a = decodeFrames(f);
  const n = f.grid.nlat * f.grid.nlon;
  const off = yearIndex * n;
  const { step, missing } = f.encoding;
  const out: (number | null)[] = new Array(n);
  for (let i = 0; i < n; i++) {
    const q = a[off + i];
    out[i] = q === missing ? null : q * step;
  }
  return out;
}

/** A MapLayer for one year: same grid, palette and mask; every square drawn at full strength
 *  (a single year is not a trend test, so there is no significance to show). */
export function frameLayer(f: FramesLayer, base: MapLayer, yearIndex: number): MapLayer {
  const values = frameValues(f, yearIndex);
  return {
    ...base,
    slope_per_decade: values,
    significant: values.map(() => 1 as const),
    limit: f.limit,
    bins: f.bins,
    value_decimals: f.value_decimals,
    legend: { ...f.legend, title: `${f.years[yearIndex]} · ${f.legend.title}` },
    units_label: f.units_label,
    caption: f.caption,
  };
}

/** Loads a variable's frames only once ``enabled`` (the visitor asked for playback). */
export function useFrames(variableId: string, enabled: boolean): FramesLayer | undefined {
  const [frames, setFrames] = useState<FramesLayer>();
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    api.frames(variableId).then((x) => alive && setFrames(x), () => {});
    return () => {
      alive = false;
    };
  }, [variableId, enabled]);
  return frames && frames.variable_id === variableId ? frames : undefined;
}
