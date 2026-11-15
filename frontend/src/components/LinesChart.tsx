import { useEffect, useRef } from 'react';
import { FONT, loadPlotly, themeColors } from '../lib/plotly';
import { useTheme } from '../state/theme';

/** 'ink' and 'muted' follow the theme; any other value is used as a CSS colour. */
export type Line = { name: string; y: (number | null)[]; color: string; dash?: string; width?: number };

/**
 * A few yearly lines on one axis (a place and the world average, or two areas). With `centre`,
 * each line is drawn as the difference from its own average, so places with different levels
 * can be compared. `trend` is an optional straight line for the first series
 * (value = intercept + slopePerYear * year, in the units of that series).
 */
export function LinesChart({ years, lines, trend, unit, centre = false, height = 190, ariaLabel }: {
  years: number[]; lines: Line[]; trend?: { intercept: number; slopePerYear: number } | null; unit: string;
  centre?: boolean; height?: number; ariaLabel: string;
}) {
  const el = useRef<HTMLDivElement>(null);
  const theme = useTheme();
  useEffect(() => {
    let alive = true;
    const node = el.current;
    if (!node) return;
    loadPlotly().then((P) => {
      if (!alive) return;
      const c = themeColors();
      const drawn = lines.map((l) => {
        const ok = l.y.filter((v): v is number => v !== null);
        const m = centre && ok.length ? ok.reduce((s, v) => s + v, 0) / ok.length : 0;
        return { ...l, m, y: l.y.map((v) => (v === null ? null : v - m)) };
      });
      const data: unknown[] = drawn.map((l) => ({
        type: 'scatter', mode: 'lines', x: years, y: l.y, name: l.name, connectgaps: false,
        line: { color: l.color === 'ink' ? c.ink : l.color === 'muted' ? c.text3 : l.color, width: l.width ?? 2, dash: l.dash ?? 'solid' },
        hovertemplate: `${l.name}, %{x}: %{y:+.2f} ${unit}<extra></extra>`,
      }));
      if (trend && drawn[0]) {
        const y0 = years[0];
        const y1 = years[years.length - 1];
        const at = (y: number) => trend.intercept + trend.slopePerYear * y - drawn[0].m;
        data.push({ type: 'scatter', mode: 'lines', x: [y0, y1], y: [at(y0), at(y1)], line: { color: c.ink, width: 1.2, dash: 'dash' }, hoverinfo: 'skip' });
      }
      P.react(node, data, {
        height, margin: { l: 46, r: 8, t: 6, b: 26 },
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
        font: { family: FONT, size: 12, color: c.text2 }, showlegend: false, hovermode: 'closest',
        hoverlabel: { bgcolor: c.bg, bordercolor: c.lineStrong, font: { family: FONT, size: 12.5, color: c.text } },
        xaxis: { showgrid: false, ticks: 'outside', ticklen: 4, tickcolor: c.lineStrong, linecolor: c.lineStrong, dtick: 10, fixedrange: true },
        yaxis: { gridcolor: c.line, zeroline: true, zerolinecolor: c.lineStrong, zerolinewidth: 1, ticks: '', fixedrange: true },
      }, { displayModeBar: false, responsive: true });
    });
    return () => {
      alive = false;
    };
  }, [years, lines, trend, unit, centre, height, theme]);
  useEffect(() => {
    const node = el.current;
    return () => {
      if (node) loadPlotly().then((P) => P.purge(node));
    };
  }, []);
  return <div ref={el} className="series-chart" style={{ minHeight: height }} role="img" aria-label={ariaLabel} />;
}
