import type { ReactNode } from 'react';
import type { AnalysisResult } from '../data/types.gen';
import { LEVEL_INDEX, S } from '../strings/en';

function levelWord(level: string): string {
  if (level === 'insufficient') return S.verdict.insufficient;
  const i = LEVEL_INDEX[level] ?? 0;
  return i === 0 ? S.verdict.none : S.verdict.scale[i - 1];
}

/**
 * Evidence glyph: three segments for "a hint", "evidence", "strong". "No clear trend" is three
 * empty boxes, "not enough data" a hatched empty scale. The word is always available next to it.
 */
export function EvidenceScale({ level, word = false, size = 'md' }: { level: string; word?: boolean; size?: 'sm' | 'md' | 'lg' }) {
  const n = LEVEL_INDEX[level] ?? 0;
  const insufficient = level === 'insufficient';
  const w = levelWord(level);
  return (
    <span className={`evidence evidence--${size}`} role="img" aria-label={S.verdict.scaleAria(w)}>
      <span className="evidence__bar" aria-hidden="true">
        {[1, 2, 3].map((i) => (
          <span key={i} className={`evidence__seg${insufficient ? ' is-hatched' : i <= n ? ' is-on' : ''}`} />
        ))}
      </span>
      {word && <span className={`evidence__word${n >= 2 ? ' is-strong' : ''}`}>{w}</span>}
    </span>
  );
}

/** The answer strip at the top of every investigation (review P0-1). Everything comes from JSON. */
export function Readout({ value, unit, headline, level, rangeLine, answer, extra }: {
  value: string; unit: string; headline: string; level: string; rangeLine: string; answer: string; extra?: ReactNode;
}) {
  const muted = (LEVEL_INDEX[level] ?? 0) < 2;
  return (
    <section className="readout" aria-label={S.verdict.label}>
      <div className="readout__number">
        <span className={`readout__value${muted ? ' is-muted' : ''}`}>{level === 'insufficient' ? '—' : value}</span>
        <span className="readout__unit">{unit}</span>
      </div>
      <div className="readout__verdict">
        <h2 className="readout__headline">{headline}</h2>
        <EvidenceScale level={level} word size="lg" />
        <p className="readout__range">{rangeLine}</p>
      </div>
      <div className="readout__answer">
        <p>{answer}</p>
        {extra}
      </div>
    </section>
  );
}

/** Details under "How sure, and how much in total". */
export function VerdictDetails({ a }: { a: AnalysisResult }) {
  const v = a.verdict;
  const t = a.trend.display;
  return (
    <div className="vdetails">
      <p className="vdetails__sentence">{v.sentence}</p>
      {v.level !== 'insufficient' && (
        <dl className="vdetails__numbers">
          <div>
            <dt>{t.total_label}</dt>
            <dd className="vdetails__big">{t.total_value} <span className="vdetails__unit">{t.total_unit}</span></dd>
            <dd className="vdetails__range">{t.total_range}</dd>
          </div>
          {t.percent && (
            <div>
              <dt>Relative change</dt>
              <dd className="vdetails__big vdetails__big--text">{t.percent}</dd>
              <dd className="vdetails__range">{t.percent_range}</dd>
            </div>
          )}
        </dl>
      )}
      {a.years_to_detect && <p className="vdetails__ytd">{a.years_to_detect.text}</p>}
      <p className="vdetails__sure"><strong>{S.verdict.howSure}</strong> {v.how_sure}</p>
      {v.disagree_text && <p className="vdetails__disagree">{v.disagree_text}</p>}
      <p className="vdetails__caveat">{a.provenance.caveat}</p>
    </div>
  );
}
