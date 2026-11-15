import { describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { decodeFrames, frameLayer, frameValues } from './frames';
import { usePlayer } from './usePlayer';
import type { FramesLayer, MapLayer } from '../data/types.gen';

// 2 years x 3 squares: [10, -128 (missing), -5], [127, 0, -127]
const bytes = [10, -128, -5, 127, 0, -127];
const data = btoa(String.fromCharCode(...bytes.map((b) => b & 0xff)));
const frames = {
  years: [2001, 2002], grid: { lat0: 0, lon0: 0, dlat: 2, dlon: 2, nlat: 1, nlon: 3, order: '' },
  encoding: { type: 'int8-base64', step: 0.5, missing: -128 }, data, limit: 50, bins: 11, value_decimals: 1,
  units_label: '°C vs normal', legend: { title: 'Difference from normal · °C', edges_text: [], ticks: [], min_text: '', max_text: '' },
} as unknown as FramesLayer;
const base = { slope_per_decade: [1, 2, 3], significant: [0, 1, 0], limit: 1, legend: { title: 'Trend' } } as unknown as MapLayer;

describe('frames', () => {
  it('decodes signed bytes and the missing marker', () => {
    expect(Array.from(decodeFrames(frames))).toEqual(bytes);
    expect(frameValues(frames, 0)).toEqual([5, null, -2.5]);
    expect(frameValues(frames, 1)).toEqual([63.5, 0, -63.5]);
  });

  it('turns one year into a full-strength map layer with its own legend', () => {
    const l = frameLayer(frames, base, 1);
    expect(l.slope_per_decade).toEqual([63.5, 0, -63.5]);
    expect(l.significant).toEqual([1, 1, 1]);
    expect(l.limit).toBe(50);
    expect(l.legend.title).toBe('2002 · Difference from normal · °C');
  });
});

describe('usePlayer', () => {
  it('starts paused at the last year and replays from the start', () => {
    const { result } = renderHook(() => usePlayer(5, 10));
    expect(result.current.index).toBe(4);
    expect(result.current.playing).toBe(false);
    act(() => result.current.toggle());
    expect(result.current.playing).toBe(true);
    expect(result.current.index).toBe(0);
  });
});
