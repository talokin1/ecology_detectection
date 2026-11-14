import { Link } from 'react-router-dom';
import type { Index, MapLayer, VariableRef } from '../data/types.gen';
import { colorFor, type PaletteName } from '../theme/palettes';
import { EvidenceScale } from './VerdictCard';
import { LEVEL_INDEX, S } from '../strings/en';

function niceMax(v: number): number {
  const steps = [0.05, 0.1, 0.2, 0.25, 0.4, 0.5, 0.8, 1, 1.5, 2, 2.5, 3, 4, 5];
  return steps.find((s) => s >= v) ?? v;
}

const tick = (v: number) => (v === 0 ? '0' : `${v > 0 ? '+' : '−'}${Math.abs(v)}`);

/**
 * "Prepared regions, ranked": one row per region on one shared zero-centred axis. Opposite signs
 * fall on either side of the zero line, which is the challenge's key insight made visible.
 * Positions use the numeric rate and 95% range from index.json; all text comes from the JSON.
 */
export function RegionLedger({ index, variable, layer, activeIds, highlightId, onHover }: {
  index: Index; variable: VariableRef; layer?: MapLayer; activeIds: string[]; highlightId: string | null;
  onHover: (id: string | null) => void;
}) {
  const rows = index.regions
    .map((r) => ({ r, v: index.verdicts[`${r.id}__${variable.id}`] }))
    .filter((x) => x.v)
    .sort((p, q) => q.v.rate_value - p.v.rate_value);
  const m = niceMax(Math.max(...rows.flatMap(({ v }) => v.ci95.map(Math.abs))) * 1.05);
  const pos = (x: number) => `${((x + m) / (2 * m)) * 100}%`;
  const pal = variable.palette as PaletteName;
  const caseOf = (rid: string) => index.cases.find((c) => c.variable_id === variable.id && (c.region_id === rid || c.compare_region_id === rid));

  return (
    <section className="ledger" aria-labelledby="ledger-title">
      <div className="ledger__head">
        <h2 id="ledger-title" className="ledger__title">{S.ledger.title}</h2>
        <span className="ledger__units">{variable.rate_units} · 95% range</span>
      </div>
      <div className="ledger__axis" aria-hidden="true">
        <span />
        <div className="ledger__scale">
          {[-m, -m / 2, 0, m / 2, m].map((t) => (
            <span key={t} className={Math.abs(t) === m / 2 ? 'is-half' : undefined} style={{ left: pos(t) }}>{t === 0 ? `0 · ${S.ledger.zero}` : tick(t)}</span>
          ))}
        </div>
        <span /><span /><span />
      </div>
      <ul className="ledger__rows">
        {rows.map(({ r, v }) => {
          const c = caseOf(r.id);
          const strong = (LEVEL_INDEX[v.level] ?? 0) >= 2;
          const color = layer ? colorFor(v.rate_value, layer.limit, pal) : 'var(--ink)';
          const to = c ? `/case/${c.id}` : `/region/${r.id}?var=${variable.id}`;
          const active = activeIds.includes(r.id);
          return (
            <li key={r.id}>
              <Link to={to} className={`ledger__row${active ? ' is-active' : ''}${highlightId === r.id ? ' is-hl' : ''}`}
                onMouseEnter={() => onHover(r.id)} onMouseLeave={() => onHover(null)} onFocus={() => onHover(r.id)} onBlur={() => onHover(null)}
                aria-label={`${r.name}: ${v.rate}, ${v.range_text}, ${v.level_word}`}>
                <span className="ledger__name">{r.name}</span>
                <span className="ledger__plot" aria-hidden="true">
                  <span className="ledger__zero" style={{ left: pos(0) }} />
                  <span className="ledger__whisker" style={{ left: pos(v.ci95[0]), width: `calc(${pos(v.ci95[1])} - ${pos(v.ci95[0])})` }} />
                  <span className={`ledger__dot${strong ? '' : ' is-hollow'}`} style={{ left: pos(v.rate_value), ['--dot' as string]: color }} />
                </span>
                <span className="ledger__rate">{v.rate_text}</span>
                <span className="ledger__level"><EvidenceScale level={v.level} word size="sm" /></span>
                <span className="ledger__open">{c ? S.ledger.open(c.id) : S.ledger.openRegion}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
