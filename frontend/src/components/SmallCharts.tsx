import type { AnalysisResult, VariableRef } from '../data/types.gen';
import { signColor, type PaletteName } from '../theme/palettes';

function signed(v: number): string {
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v)}`;
}

function niceMax(v: number): number {
  const steps = [0.05, 0.1, 0.2, 0.25, 0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 10];
  return steps.find((s) => s >= v) ?? v;
}

/** Dot-and-whisker per season: Sen slope per decade with its 95% range. */
export function SeasonChart({ a, variable }: { a: AnalysisResult; variable: VariableRef }) {
  const pal = variable.palette as PaletteName;
  const rows = a.seasons;
  const m = niceMax(Math.max(...rows.flatMap((s) => s.ci95.map(Math.abs))) * 1.05);
  const W = 520, L = 72, R = 64, rowH = 38, top = 8, H = top + rows.length * rowH + 26;
  const x = (v: number) => L + ((v + m) / (2 * m)) * (W - L - R);
  return (
    <svg className="small-chart" viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={`Trend per decade by season: ${rows.map((s) => `${s.label} ${s.display}`).join(', ')}`}>
      <line x1={x(0)} x2={x(0)} y1={top} y2={H - 22} className="sc-zero" />
      {rows.map((s, i) => {
        const y = top + i * rowH + rowH / 2;
        const col = signColor(pal, s.sen_per_decade);
        return (
          <g key={s.season}>
            <title>{`${s.label}: ${s.display} ${variable.rate_units} (95% range ${signed(s.ci95[0])} to ${signed(s.ci95[1])})${s.passes_fdr ? '' : ', could still be chance'}`}</title>
            <rect x={0} y={y - rowH / 2} width={W} height={rowH} fill="transparent" />
            <text x={0} y={y + 4} className="sc-label">{s.label}</text>
            <line x1={x(s.ci95[0])} x2={x(s.ci95[1])} y1={y} y2={y} className="sc-whisker" opacity={s.passes_fdr ? 1 : 0.45} />
            <circle cx={x(s.sen_per_decade)} cy={y} r={6} fill={s.passes_fdr ? col : 'var(--bg)'} stroke={s.passes_fdr ? 'var(--bg)' : col} strokeWidth={2} />
            <text x={W} y={y + 4} textAnchor="end" className={`sc-value${s.passes_fdr ? '' : ' is-faded'}`}>{s.display}</text>
          </g>
        );
      })}
      {[-m, 0, m].map((t) => (
        <text key={t} x={x(t)} y={H - 6} textAnchor="middle" className="sc-tick">{t === 0 ? '0' : signed(t)}</text>
      ))}
    </svg>
  );
}

/** Twelve bars: trend per decade of each calendar month (M1), faded when not significant after FDR. */
export function MonthChart({ a, variable }: { a: AnalysisResult; variable: VariableRef }) {
  const pal = variable.palette as PaletteName;
  const rows = a.monthly_profile;
  const m = niceMax(Math.max(...rows.flatMap((r) => r.ci95.map(Math.abs))) * 1.02);
  const W = 520, L = 40, top = 10, H = 200, base = H - 24;
  const bw = (W - L) / 12;
  const y = (v: number) => top + ((m - v) / (2 * m)) * (base - top);
  return (
    <svg className="small-chart" viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={`Trend per decade by calendar month, from ${rows[0].label} to ${rows[11].label}`}>
      {[-m, 0, m].map((t) => (
        <g key={t}>
          <line x1={L} x2={W} y1={y(t)} y2={y(t)} className={t === 0 ? 'sc-zero-h' : 'sc-grid'} />
          <text x={L - 8} y={y(t) + 4} textAnchor="end" className="sc-tick">{t === 0 ? '0' : signed(t)}</text>
        </g>
      ))}
      {rows.map((r, i) => {
        const cx = L + i * bw + bw / 2;
        const col = signColor(pal, r.sen_per_decade);
        const y0 = y(Math.max(0, r.sen_per_decade));
        const h = Math.abs(y(r.sen_per_decade) - y(0));
        return (
          <g key={r.month}>
            <title>{`${r.label}: ${signed(r.sen_per_decade)} ${variable.rate_units} (95% range ${signed(r.ci95[0])} to ${signed(r.ci95[1])})${r.passes_fdr ? '' : ', could still be chance'}`}</title>
            <rect x={L + i * bw} y={top} width={bw} height={base - top} fill="transparent" />
            <rect x={cx - bw * 0.3} y={y0} width={bw * 0.6} height={Math.max(1, h)} rx={2} fill={col} opacity={r.passes_fdr ? 0.95 : 0.3} />
            <line x1={cx} x2={cx} y1={y(r.ci95[1])} y2={y(r.ci95[0])} className="sc-whisker-thin" opacity={r.passes_fdr ? 0.9 : 0.4} />
            <text x={cx} y={H - 6} textAnchor="middle" className="sc-tick">{r.label.slice(0, 1)}</text>
          </g>
        );
      })}
    </svg>
  );
}

/** Extreme months per year with the average of the first and the last decade marked. */
export function ExtremesChart({ a, variable }: { a: AnalysisResult; variable: VariableRef }) {
  const ex = a.extremes;
  if (!ex) return null;
  const pal = variable.palette as PaletteName;
  const col = signColor(pal, ex.kind === 'hot_months' ? 1 : -1);
  const maxC = Math.max(4, ...ex.counts);
  const W = 520, L = 28, top = 30, H = 200, base = H - 22;
  const n = ex.years.length;
  const bw = (W - L) / n;
  const y = (v: number) => base - (v / maxC) * (base - top);
  const xOf = (i: number) => L + i * bw;
  // the decade averages: a line over the bars, its label in the free band above the plot
  const seg = (from: number, to: number, mean: number, label: string, anchor: 'start' | 'end') => (
    <g>
      <line x1={xOf(from)} x2={xOf(to + 1)} y1={y(mean)} y2={y(mean)} className="sc-mean-halo" />
      <line x1={xOf(from)} x2={xOf(to + 1)} y1={y(mean)} y2={y(mean)} className="sc-mean" />
      <line x1={anchor === 'start' ? xOf(from) : xOf(to + 1)} x2={anchor === 'start' ? xOf(from) : xOf(to + 1)} y1={14} y2={y(mean)} className="sc-mean-tick" />
      <text x={anchor === 'start' ? xOf(from) + 5 : xOf(to + 1) - 5} y={12} textAnchor={anchor} className="sc-mean-label">{label}</text>
    </g>
  );
  return (
    <svg className="small-chart" viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={`${ex.label} per year: about ${ex.early.mean_per_year} a year in ${ex.early.label}, about ${ex.late.mean_per_year} a year in ${ex.late.label}`}>
      {[0, Math.round(maxC / 2), maxC].map((t) => (
        <g key={t}>
          <line x1={L} x2={W} y1={y(t)} y2={y(t)} className={t === 0 ? 'sc-zero-h' : 'sc-grid'} />
          <text x={L - 6} y={y(t) + 4} textAnchor="end" className="sc-tick">{t}</text>
        </g>
      ))}
      {ex.counts.map((c, i) => (
        <g key={ex.years[i]}>
          <title>{`${ex.years[i]}: ${c} month${c === 1 ? '' : 's'}`}</title>
          <rect x={xOf(i)} y={top} width={bw} height={base - top} fill="transparent" />
          {c > 0 && <rect x={xOf(i) + 1} y={y(c)} width={Math.max(1, bw - 2)} height={base - y(c)} rx={1.5} fill={col} opacity={0.85} />}
        </g>
      ))}
      {seg(0, 9, ex.early.mean_per_year, `${ex.early.label}: ${ex.early.mean_per_year} a year`, 'start')}
      {seg(n - 10, n - 1, ex.late.mean_per_year, `${ex.late.label}: ${ex.late.mean_per_year} a year`, 'end')}
      {[0, 10, 20, 30, 40].filter((i) => i < n).map((i) => (
        <text key={i} x={xOf(i) + bw / 2} y={H - 4} textAnchor="middle" className="sc-tick">{ex.years[i]}</text>
      ))}
    </svg>
  );
}
