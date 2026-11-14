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
 * Regions compared: one row per prepared region on one shared zero-centred axis, so opposite
 * signs fall on either side of zero. Positions use the numeric rate and 95% range from
 * index.json; all text comes from the JSON. Rows open the quick look (production UX plan A5).
 */
export function RegionLedger({ index, variable, layer, activeIds, highlightId, onHover, onSelect }: {
  index: Index; variable: VariableRef; layer?: MapLayer; activeIds: string[]; highlightId: string | null;
  onHover: (id: string | null) => void; onSelect: (id: string) => void;
}) {
  const rows = index.regions
    .map((r) => ({ r, v: index.verdicts[`${r.id}__${variable.id}`] }))
    .filter((x) => x.v)
    .sort((p, q) => q.v.rate_value - p.v.rate_value);
  const m = niceMax(Math.max(...rows.flatMap(({ v }) => v.ci95.map(Math.abs))) * 1.05);
  const pos = (x: number) => `${((x + m) / (2 * m)) * 100}%`;
  const pal = variable.palette as PaletteName;

  return (
    <div className="ledger">
      <div className="ledger__axis" aria-hidden="true">
        <span />
        <div className="ledger__scale">
          {[-m, 0, m].map((t) => (
            <span key={t} style={{ left: pos(t) }}>{t === 0 ? `0 · ${S.ledger.zero}` : tick(t)}</span>
          ))}
        </div>
        <span />
      </div>
      <ul className="ledger__rows">
        {rows.map(({ r, v }) => {
          const strong = (LEVEL_INDEX[v.level] ?? 0) >= 2;
          const color = layer ? colorFor(v.rate_value, layer.limit, pal) : 'var(--ink)';
          return (
            <li key={r.id}>
              <button type="button" className={`ledger__row${activeIds.includes(r.id) ? ' is-active' : ''}${highlightId === r.id ? ' is-hl' : ''}`}
                onMouseEnter={() => onHover(r.id)} onMouseLeave={() => onHover(null)} onFocus={() => onHover(r.id)} onBlur={() => onHover(null)}
                onClick={() => onSelect(r.id)} aria-label={`${r.name}: ${v.rate}, ${v.range_text}, ${v.level_word}`}>
                <span className="ledger__name">
                  <span>{r.name}</span>
                  <EvidenceScale level={v.level} word size="sm" />
                </span>
                <span className="ledger__plot" aria-hidden="true">
                  <span className="ledger__zero" style={{ left: pos(0) }} />
                  <span className="ledger__whisker" style={{ left: pos(v.ci95[0]), width: `calc(${pos(v.ci95[1])} - ${pos(v.ci95[0])})` }} />
                  <span className={`ledger__dot${strong ? '' : ' is-hollow'}`} style={{ left: pos(v.rate_value), ['--dot' as string]: color }} />
                </span>
                <span className="ledger__rate">{v.rate_text}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
