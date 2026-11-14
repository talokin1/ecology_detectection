import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { FONT, loadPlotly, themeColors } from '../lib/plotly';
import { useTheme } from '../state/theme';

export type ChartHandle = { downloadPng: (filename: string) => void };

export type ChartBars = { x: string[]; y: (number | null)[]; colors: string | string[]; hover: string[]; opacity?: number };
export type ChartLine = { x: string[]; y: number[] } | null;
export type ChartBand = { x: string[]; lower: number[]; upper: number[] } | null;

type Props = {
  bars?: ChartBars;
  /** A thin continuous line instead of bars (actual monthly values). */
  rawLine?: { x: string[]; y: (number | null)[]; hover: string[] };
  line?: ChartLine;
  band?: ChartBand;
  /** Trend line colour (region colour in Compare); ink by default. */
  accent?: string;
  yTitle: string;
  height?: number;
  yRange?: [number, number];
  /** Vertical marker, e.g. the time of emergence. */
  marker?: { x: string; label: string } | null;
  /** Source line stamped on exported PNGs. */
  footer: string;
  ariaLabel: string;
};

const YEAR_TICKS = [1981, 1990, 2000, 2010, 2020].map((y) => `${y}-01-01`);

/**
 * Bars (or a thin line) with the Sen trend line and its 95% fan drawn ON TOP. Every value, text and
 * hover label comes from the JSON via the caller; this component only draws.
 */
export const TrendChart = forwardRef<ChartHandle, Props>(function TrendChart(props, ref) {
  const { bars, rawLine, line, band, accent, yTitle, height = 320, yRange, marker, footer, ariaLabel } = props;
  const el = useRef<HTMLDivElement>(null);
  const theme = useTheme();
  const [width, setWidth] = useState(800);

  useEffect(() => {
    const node = el.current;
    if (!node) return;
    const ro = new ResizeObserver(() => setWidth(node.clientWidth));
    ro.observe(node);
    return () => ro.disconnect();
  }, []);

  useImperativeHandle(ref, () => ({
    downloadPng: (filename: string) => {
      const node = el.current;
      if (!node) return;
      loadPlotly().then(async (P) => {
        const p = P as unknown as { relayout: (n: HTMLElement, u: unknown) => Promise<unknown> };
        const c = themeColors();
        await p.relayout(node, {
          'margin.b': 74,
          annotations: [{ xref: 'paper', yref: 'paper', x: 0, y: -0.2, xanchor: 'left', yanchor: 'top', showarrow: false, align: 'left', text: footer, font: { size: 11, color: c.text2 } }],
        });
        await P.downloadImage(node, { format: 'png', filename, scale: 2, width: 1200, height: Math.round(height * 1.5) });
        await p.relayout(node, { 'margin.b': 30, annotations: [] });
      });
    },
  }), [footer, height]);

  useEffect(() => {
    let alive = true;
    const node = el.current;
    if (!node) return;
    loadPlotly().then((P) => {
      if (!alive) return;
      const c = themeColors();
      const ink = accent ?? c.ink;
      const data: unknown[] = [];
      if (bars) {
        data.push({
          type: 'bar', x: bars.x, y: bars.y, marker: { color: bars.colors, line: { width: 0 } }, opacity: bars.opacity ?? 0.85,
          hovertemplate: bars.hover.map((t) => `${t}<extra></extra>`), name: 'values',
        });
      }
      if (rawLine) {
        data.push({
          type: 'scatter', mode: 'lines', x: rawLine.x, y: rawLine.y, connectgaps: false, line: { color: c.ink, width: 1.1 },
          hovertemplate: rawLine.hover.map((t) => `${t}<extra></extra>`), name: 'values',
        });
      }
      if (band) {
        data.push({ type: 'scatter', mode: 'lines', x: band.x, y: band.upper, line: { width: 0 }, hoverinfo: 'skip', showlegend: false });
        data.push({
          type: 'scatter', mode: 'lines', x: band.x, y: band.lower, fill: 'tonexty', fillcolor: accent ? `${accent}33` : c.band,
          line: { width: 0 }, hoverinfo: 'skip', showlegend: false,
        });
      }
      if (line) {
        data.push({ type: 'scatter', mode: 'lines', x: line.x, y: line.y, line: { color: ink, width: 2.5 }, hoverinfo: 'skip', name: 'trend' });
      }
      const narrow = width < 600;
      const layout = {
        height,
        margin: { l: 52, r: 10, t: marker ? 22 : 8, b: 30 },
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
        font: { family: FONT, size: 12, color: c.text2 },
        showlegend: false, bargap: bars && bars.x.length < 80 ? 0.18 : 0, hovermode: 'closest',
        hoverlabel: { bgcolor: c.bg, bordercolor: c.lineStrong, font: { family: FONT, size: 12.5, color: c.text } },
        xaxis: {
          type: 'date', showgrid: false, ticks: 'outside', ticklen: 4, tickcolor: c.lineStrong, linecolor: c.lineStrong,
          tickvals: narrow ? YEAR_TICKS.filter((_, i) => i % 2 === 0) : YEAR_TICKS, tickformat: '%Y', tickangle: 0, fixedrange: true,
        },
        yaxis: {
          title: { text: yTitle, font: { size: 12, color: c.text2 }, standoff: 6 },
          gridcolor: c.line, zeroline: !rawLine, zerolinecolor: c.lineStrong, zerolinewidth: 1, ticks: '', fixedrange: true,
          ...(yRange ? { range: yRange } : {}),
        },
        shapes: marker ? [{ type: 'line', xref: 'x', yref: 'paper', x0: marker.x, x1: marker.x, y0: 0, y1: 1, line: { color: c.text3, width: 1 } }] : [],
        annotations: marker
          ? [{ xref: 'x', yref: 'paper', x: marker.x, y: 1, yanchor: 'bottom', xanchor: 'left', xshift: 4, showarrow: false, text: marker.label, font: { size: 12, color: c.text2 } }]
          : [],
      };
      P.react(node, data, layout, { displayModeBar: false, responsive: true });
    });
    return () => {
      alive = false;
    };
  }, [bars, rawLine, line, band, accent, yTitle, height, yRange, marker, theme, width]);

  useEffect(() => {
    const node = el.current;
    return () => {
      if (node) loadPlotly().then((P) => P.purge(node));
    };
  }, []);

  return <div ref={el} className="series-chart" style={{ minHeight: height }} role="img" aria-label={ariaLabel} />;
});
