import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { AnalysisResult, VariableRef } from '../data/types.gen';
import { signColor, type PaletteName } from '../theme/palettes';
import { S } from '../strings/en';

/** Axis tick text for round numbers chosen by the chart (geometry, not statistics). */
function tick(v: number): string {
  if (v === 0) return '0';
  return `${v > 0 ? '+' : '−'}${Math.abs(v)}`;
}

function niceMax(v: number): number {
  const steps = [0.05, 0.1, 0.2, 0.25, 0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 10];
  return steps.find((s) => s >= v) ?? v;
}

/** Draw SVG at the real container width so 12 px text stays 12 px on phones. */
function Sized({ height, label, children }: { height: number; label: string; children: (w: number) => ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const ro = new ResizeObserver(() => setW(node.clientWidth));
    ro.observe(node);
    return () => ro.disconnect();
  }, []);
  return (
    <div ref={ref} className="small-chart-box">
      {w > 0 && (
        <svg className="small-chart" width={w} height={height} viewBox={`0 0 ${w} ${height}`} role="img" aria-label={label}>
          {children(w)}
        </svg>
      )}
    </div>
  );
}

/** Dot-and-whisker per season with the all-year trend as a reference line. */
export function SeasonChart({ a, variable }: { a: AnalysisResult; variable: VariableRef }) {
  const pal = variable.palette as PaletteName;
  const rows = a.seasons;
  if (!rows.length) return <p className="help">{S.case.noData}</p>;
  const all = a.trend.sen_per_decade;
  const m = niceMax(Math.max(...rows.flatMap((s) => s.ci95.map(Math.abs)), Math.abs(all ?? 0)) * 1.05);
  const rowH = 40, top = 24, H = top + rows.length * rowH + 26;
  return (
    <Sized height={H} label={`Trend per decade by season: ${rows.map((s) => `${s.label} ${s.display}`).join(', ')}`}>
      {(W) => {
        const L = W < 420 ? 64 : 76, R = 52;
        const x = (v: number) => L + ((v + m) / (2 * m)) * (W - L - R);
        return (
          <>
            {[-m, -m / 2, 0, m / 2, m].map((t) => (
              <g key={t}>
                <line x1={x(t)} x2={x(t)} y1={top - 4} y2={H - 22} className={t === 0 ? 'sc-zero' : 'sc-grid'} />
                <text x={x(t)} y={H - 6} textAnchor="middle" className="sc-tick">{tick(t)}</text>
              </g>
            ))}
            {all !== null && (
              <g>
                <line x1={x(all)} x2={x(all)} y1={top - 6} y2={H - 22} className="sc-ref" />
                <text x={x(all)} y={top - 10} textAnchor="middle" className="sc-ref-label">{S.case.allYear} {a.trend.display.rate_value}</text>
              </g>
            )}
            {rows.map((s, i) => {
              const y = top + i * rowH + rowH / 2;
              const col = signColor(pal, s.sen_per_decade);
              return (
                <g key={s.season}>
                  <title>{`${s.label}: ${s.display} ${variable.rate_units} (${s.ci_text})${s.passes_fdr ? '' : ', could still be chance'}`}</title>
                  <rect x={0} y={y - rowH / 2} width={W} height={rowH} fill="transparent" />
                  <text x={0} y={y + 4} className="sc-label">{s.label}</text>
                  <line x1={x(s.ci95[0])} x2={x(s.ci95[1])} y1={y} y2={y} className="sc-whisker" opacity={s.passes_fdr ? 1 : 0.5} />
                  <circle cx={x(s.sen_per_decade)} cy={y} r={6.5} fill={s.passes_fdr ? col : 'var(--bg)'} stroke={s.passes_fdr ? 'var(--bg)' : col} strokeWidth={2.2} />
                  <text x={W} y={y + 4} textAnchor="end" className={`sc-value${s.passes_fdr ? '' : ' is-faded'}`}>{s.display}</text>
                </g>
              );
            })}
          </>
        );
      }}
    </Sized>
  );
}

/** Twelve bars: trend per decade of each calendar month (M1), pale when not passing the filter. */
export function MonthChart({ a, variable }: { a: AnalysisResult; variable: VariableRef }) {
  const pal = variable.palette as PaletteName;
  const rows = a.monthly_profile;
  if (!rows.length) return <p className="help">{S.case.noData}</p>;
  const m = niceMax(Math.max(...rows.flatMap((r) => r.ci95.map(Math.abs))) * 1.02);
  const top = 10, H = 210, base = H - 24;
  return (
    <Sized height={H} label={`Trend per decade by calendar month, ${rows.map((r) => `${r.name} ${r.display}`).join(', ')}`}>
      {(W) => {
        const L = 40;
        const bw = (W - L) / 12;
        const y = (v: number) => top + ((m - v) / (2 * m)) * (base - top);
        return (
          <>
            {[-m, 0, m].map((t) => (
              <g key={t}>
                <line x1={L} x2={W} y1={y(t)} y2={y(t)} className={t === 0 ? 'sc-zero' : 'sc-grid'} />
                <text x={L - 8} y={y(t) + 4} textAnchor="end" className="sc-tick">{tick(t)}</text>
              </g>
            ))}
            {rows.map((r, i) => {
              const cx = L + i * bw + bw / 2;
              const y0 = y(Math.max(0, r.sen_per_decade));
              const h = Math.abs(y(r.sen_per_decade) - y(0));
              return (
                <g key={r.month}>
                  <title>{`${r.name}: ${r.display} ${variable.rate_units} (${r.ci_text})${r.passes_fdr ? '' : ', could still be chance'}`}</title>
                  <rect x={L + i * bw} y={top} width={bw} height={base - top} fill="transparent" />
                  <rect x={cx - bw * 0.3} y={y0} width={bw * 0.6} height={Math.max(1, h)} rx={2} fill={signColor(pal, r.sen_per_decade)} opacity={r.passes_fdr ? 0.95 : 0.28} />
                  <line x1={cx} x2={cx} y1={y(r.ci95[1])} y2={y(r.ci95[0])} className="sc-whisker-thin" opacity={r.passes_fdr ? 0.9 : 0.4} />
                  <text x={cx} y={H - 6} textAnchor="middle" className="sc-tick">{r.label.slice(0, 1)}</text>
                </g>
              );
            })}
          </>
        );
      }}
    </Sized>
  );
}

/** Extreme months per year with the first and last decade averages marked; pale if it could be chance. */
export function ExtremesChart({ a, variable }: { a: AnalysisResult; variable: VariableRef }) {
  const ex = a.extremes;
  if (!ex) return null;
  const pal = variable.palette as PaletteName;
  const col = signColor(pal, ex.kind === 'hot_months' ? 1 : -1);
  const step = Math.max(1, Math.ceil(Math.max(3, ...ex.counts) / 3));
  const maxC = step * 3;
  const top = 30, H = 210, base = H - 22;
  const n = ex.years.length;
  return (
    <Sized height={H} label={`${ex.label} per year. ${ex.display.trend_text}`}>
      {(W) => {
        const L = 28;
        const bw = (W - L) / n;
        const y = (v: number) => base - (v / maxC) * (base - top);
        const xOf = (i: number) => L + i * bw;
        const idx = (year: number) => ex.years.indexOf(year);
        const seg = (yrs: number[], mean: number, label: string, anchor: 'start' | 'end') => {
          const from = idx(yrs[0]);
          const to = idx(yrs[1]);
          const xa = anchor === 'start' ? xOf(from) : xOf(to + 1);
          return (
            <g>
              <line x1={xOf(from)} x2={xOf(to + 1)} y1={y(mean)} y2={y(mean)} className="sc-mean-halo" />
              <line x1={xOf(from)} x2={xOf(to + 1)} y1={y(mean)} y2={y(mean)} className="sc-mean" />
              <line x1={xa} x2={xa} y1={14} y2={y(mean)} className="sc-mean-tick" />
              <text x={anchor === 'start' ? xa + 5 : xa - 5} y={12} textAnchor={anchor} className="sc-mean-label">{label}</text>
            </g>
          );
        };
        return (
          <g opacity={ex.passes_fdr ? 1 : 0.55}>
            {[0, step, 2 * step, maxC].map((t) => (
              <g key={t}>
                <line x1={L} x2={W} y1={y(t)} y2={y(t)} className={t === 0 ? 'sc-zero' : 'sc-grid'} />
                <text x={L - 6} y={y(t) + 4} textAnchor="end" className="sc-tick">{t}</text>
              </g>
            ))}
            {ex.counts.map((c, i) => (
              <g key={ex.years[i]}>
                <title>{`${ex.years[i]}: ${c} month${c === 1 ? '' : 's'}`}</title>
                <rect x={xOf(i)} y={top} width={bw} height={base - top} fill="transparent" />
                {c > 0 && <rect x={xOf(i) + 1} y={y(c)} width={Math.max(1, bw - 2)} height={base - y(c)} rx={1.5} fill={col} opacity={ex.passes_fdr ? 0.85 : 0.35} />}
              </g>
            ))}
            {seg(ex.early.years, ex.early.mean_per_year, `${ex.early.label}: ${ex.early.mean_per_year} ${S.case.perYear}`, 'start')}
            {seg(ex.late.years, ex.late.mean_per_year, `${ex.late.label}: ${ex.late.mean_per_year} ${S.case.perYear}`, 'end')}
            {[1990, 2000, 2010, 2020].filter((yr) => idx(yr) >= 0).map((yr) => (
              <text key={yr} x={xOf(idx(yr)) + bw / 2} y={H - 4} textAnchor="middle" className="sc-tick">{yr}</text>
            ))}
          </g>
        );
      }}
    </Sized>
  );
}
