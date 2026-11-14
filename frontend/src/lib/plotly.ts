/**
 * Lazy Plotly loader (basic bundle: scatter + bar). Loaded only on screens with charts,
 * so the map screen stays light.
 */
export type PlotlyLike = {
  react: (el: HTMLElement, data: unknown[], layout: unknown, config?: unknown) => Promise<unknown>;
  purge: (el: HTMLElement) => void;
  downloadImage: (el: HTMLElement, opts: { format: string; filename: string; scale?: number; width?: number; height?: number }) => Promise<unknown>;
  Plots: { resize: (el: HTMLElement) => void };
};

let promise: Promise<PlotlyLike> | undefined;

export function loadPlotly(): Promise<PlotlyLike> {
  if (!promise) {
    promise = import('plotly.js-basic-dist-min').then((m) => (m.default ?? m) as unknown as PlotlyLike);
  }
  return promise;
}

/** Read theme colours from CSS variables so charts follow light and dark themes. */
export function themeColors() {
  const cs = getComputedStyle(document.documentElement);
  const v = (name: string) => cs.getPropertyValue(name).trim();
  return {
    bg: v('--bg'), text: v('--text'), text2: v('--text-2'), text3: v('--text-3'),
    line: v('--line'), lineStrong: v('--line-strong'), ink: v('--ink'), band: v('--band'),
  };
}

export const FONT = "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";
