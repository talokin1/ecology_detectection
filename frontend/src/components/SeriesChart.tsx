import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import type { AnalysisResult, VariableRef } from '../data/types.gen';
import { FONT, loadPlotly, themeColors } from '../lib/plotly';
import { signColor, type PaletteName } from '../theme/palettes';
import { useTheme } from '../state/theme';

export type SeriesView = 'anomaly' | 'raw';
export type ChartHandle = { downloadPng: (filename: string) => void };

type Props = {
  a: AnalysisResult;
  variable: VariableRef;
  view: SeriesView;
  height?: number;
  /** Shared y range for stacked charts in Compare. */
  yRange?: [number, number];
  showAnnotation?: boolean;
  ariaLabel: string;
};

function signed(v: number): string {
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v)}`;
}

/**
 * Monthly anomalies as thin bars coloured by sign (above / below normal), the Sen trend line in ink
 * and its 95% range as a light fan. Everything comes from the JSON; nothing is computed here.
 */
export const SeriesChart = forwardRef<ChartHandle, Props>(function SeriesChart(
  { a, variable, view, height = 340, yRange, showAnnotation = true, ariaLabel }, ref,
) {
  const el = useRef<HTMLDivElement>(null);
  const theme = useTheme();

  useImperativeHandle(ref, () => ({
    downloadPng: (filename: string) => {
      loadPlotly().then((P) => el.current && P.downloadImage(el.current, { format: 'png', filename, scale: 2, width: 1200, height: Math.round(height * 1.4) }));
    },
  }), [height]);

  useEffect(() => {
    let alive = true;
    const node = el.current;
    if (!node) return;
    loadPlotly().then((P) => {
      if (!alive || !node) return;
      const c = themeColors();
      const pal = variable.palette as PaletteName;
      const s = a.series;
      const units = variable.units === '%' ? 'points' : variable.units;
      const x = s.dates;
      const data: unknown[] = [];
      if (view === 'anomaly') {
        const colors = s.anomaly.map((v) => (v === null ? 'rgba(0,0,0,0)' : signColor(pal, v)));
        data.push({
          type: 'bar', x, y: s.anomaly, marker: { color: colors, line: { width: 0 } }, opacity: 0.78,
          hovertemplate: s.anomaly.map((v) => (v === null ? 'no data' : `${signed(v)} ${units} from normal`)).map((t) => `%{x|%b %Y}: ${t}<extra></extra>`),
          name: 'Monthly change from normal',
        });
        data.push({
          type: 'scatter', mode: 'lines', x: a.trend.band95.x, y: a.trend.band95.upper,
          line: { width: 0 }, hoverinfo: 'skip', showlegend: false,
        });
        data.push({
          type: 'scatter', mode: 'lines', x: a.trend.band95.x, y: a.trend.band95.lower, fill: 'tonexty',
          fillcolor: c.band, line: { width: 0 }, hoverinfo: 'skip', showlegend: false,
        });
        data.push({
          type: 'scatter', mode: 'lines', x: a.trend.line.x, y: a.trend.line.y,
          line: { color: c.ink, width: 2.5 }, hoverinfo: 'skip', name: 'Trend',
        });
      } else {
        data.push({
          type: 'scatter', mode: 'lines', x, y: s.raw, connectgaps: false,
          line: { color: c.ink, width: 1.1 },
          hovertemplate: `%{x|%b %Y}: %{y} ${variable.units}<extra></extra>`, name: 'Monthly value',
        });
      }
      const layout = {
        height,
        margin: { l: 52, r: 12, t: showAnnotation && view === 'anomaly' ? 30 : 10, b: 30 },
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
        font: { family: FONT, size: 12, color: c.text2 },
        showlegend: false, bargap: 0, hovermode: 'closest',
        hoverlabel: { bgcolor: c.bg, bordercolor: c.lineStrong, font: { family: FONT, size: 12.5, color: c.text } },
        xaxis: {
          type: 'date', showgrid: false, ticks: 'outside', ticklen: 4, tickcolor: c.lineStrong,
          linecolor: c.lineStrong, tickformat: '%Y', dtick: 'M60', fixedrange: true,
        },
        yaxis: {
          title: { text: view === 'anomaly' ? s.anomaly_label : s.raw_label, font: { size: 12, color: c.text2 }, standoff: 6 },
          gridcolor: c.line, zeroline: view === 'anomaly', zerolinecolor: c.lineStrong, zerolinewidth: 1,
          ticks: '', fixedrange: true, ...(yRange && view === 'anomaly' ? { range: yRange } : {}),
        },
        annotations: showAnnotation && view === 'anomaly'
          ? [{
              xref: 'paper', yref: 'paper', x: 0, y: 1.0, yanchor: 'bottom', xanchor: 'left', showarrow: false,
              text: `<b>Trend: ${a.trend.display.annotation}</b>`, font: { size: 13, color: c.text },
            }]
          : [],
      };
      P.react(node, data, layout, { displayModeBar: false, responsive: true });
    });
    return () => {
      alive = false;
    };
  }, [a, variable, view, height, theme, yRange, showAnnotation]);

  useEffect(() => {
    const node = el.current;
    return () => {
      if (node) loadPlotly().then((P) => P.purge(node));
    };
  }, []);

  return <div ref={el} className="series-chart" style={{ minHeight: height }} role="img" aria-label={ariaLabel} />;
});
