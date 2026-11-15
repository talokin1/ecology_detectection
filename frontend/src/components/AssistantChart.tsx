/**
 * Small charts inside assistant answers. The data come from our server, which builds them from
 * the app's own precomputed files (backend/trend_detective/assistant/charts.py); the model only
 * chose which places to show. Rates: bars with the 95% range, strong colour only when the verdict
 * is "Evidence" or "Strong evidence" (the app's honesty rule). Yearly: one line per place.
 */
import { useEffect, useRef } from 'react';
import { FONT, loadPlotly, themeColors } from '../lib/plotly';
import { PALETTES, signColor, type PaletteName } from '../theme/palettes';
import { S } from '../strings/en';

export type AssistantChartData = {
  kind: 'yearly' | 'rates';
  title: string;
  units: string;
  source?: string;
  palette?: string;
  series?: { label: string; region_id: string; x: number[]; y: (number | null)[] }[];
  bars?: { label: string; region_id: string; value: number; low: number; high: number; level: string; level_word: string }[];
};

const LINE_COLORS = ['#0072B2', '#D55E00', '#009E73'];
const CLEAR = new Set(['strong', 'moderate']);

export function AssistantChart({ chart }: { chart: AssistantChartData }) {
  const el = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    const node = el.current;
    loadPlotly().then((Plotly) => {
      if (!alive || !node) return;
      const c = themeColors();
      const pal = (chart.palette && chart.palette in PALETTES ? chart.palette : 'RdBu') as PaletteName;
      let data: unknown[];
      let height = 220;
      if (chart.kind === 'rates' && chart.bars) {
        const bars = [...chart.bars].reverse(); // first item on top
        height = 60 + bars.length * 26;
        data = [{
          type: 'bar', orientation: 'h',
          y: bars.map((b) => b.label), x: bars.map((b) => b.value),
          error_x: { type: 'data', symmetric: false, array: bars.map((b) => b.high - b.value),
            arrayminus: bars.map((b) => b.value - b.low), color: c.text2, thickness: 1.2, width: 3 },
          marker: { color: bars.map((b) => signColor(pal, b.value)), opacity: bars.map((b) => (CLEAR.has(b.level) ? 1 : 0.35)) },
          hovertext: bars.map((b) => `${b.label}: ${b.value > 0 ? '+' : ''}${b.value.toFixed(2)} ${chart.units}<br>95% range ${b.low.toFixed(2)} to ${b.high.toFixed(2)}<br>${b.level_word}`),
          hoverinfo: 'text',
        }];
      } else {
        data = (chart.series ?? []).map((s, i) => ({
          type: 'scatter', mode: 'lines+markers', name: s.label, x: s.x, y: s.y, connectgaps: false,
          line: { color: LINE_COLORS[i % LINE_COLORS.length], width: 2 }, marker: { size: 4 },
          hovertemplate: `${s.label} %{x}: %{y:+.2f} ${chart.units}<extra></extra>`,
        }));
      }
      const layout = {
        height, margin: { l: chart.kind === 'rates' ? 110 : 40, r: 10, t: 6, b: 36 },
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
        font: { family: FONT, size: 11, color: c.text2 },
        showlegend: chart.kind === 'yearly' && (chart.series?.length ?? 0) > 1,
        legend: { orientation: 'h', y: -0.25 },
        xaxis: { title: { text: chart.kind === 'rates' ? chart.units : '' }, zeroline: true, zerolinecolor: c.lineStrong, gridcolor: c.line },
        yaxis: { title: { text: chart.kind === 'yearly' ? chart.units : '' }, zeroline: true, zerolinecolor: c.lineStrong, gridcolor: c.line, automargin: true },
      };
      void Plotly.react(node, data, layout, { displayModeBar: false, responsive: true });
    });
    return () => {
      alive = false;
      if (node) loadPlotly().then((P) => P.purge(node)).catch(() => {});
    };
  }, [chart]);

  return (
    <figure className="ai-chart">
      <figcaption className="ai-chart__title">{chart.title}</figcaption>
      <div ref={el} role="img" aria-label={chart.title} />
      <p className="ai-chart__note">{S.assistant.chartNote(chart.source ?? '')}</p>
    </figure>
  );
}
