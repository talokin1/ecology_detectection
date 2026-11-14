import type { AnalysisResult } from '../data/types.gen';
import { LEVEL_INDEX, S } from '../strings/en';

/** Four graded segments; "insufficient" shows an empty hatched scale. */
export function EvidenceScale({ level, compact = false }: { level: string; compact?: boolean }) {
  const idx = LEVEL_INDEX[level] ?? 0;
  const insufficient = level === 'insufficient';
  return (
    <div className={`evidence${compact ? ' evidence--compact' : ''}`} role="img"
      aria-label={insufficient ? S.verdict.insufficient : `Evidence: ${S.verdict.scale[idx]} (${idx + 1} of 4)`}>
      <div className="evidence__bar">
        {S.verdict.scale.map((label, i) => (
          <span key={label}
            className={`evidence__seg${insufficient ? ' is-hatched' : i <= idx ? ' is-on' : ''}${i === idx && !insufficient ? ' is-current' : ''}`} />
        ))}
      </div>
      {!compact && (
        <div className="evidence__labels">
          {S.verdict.scale.map((label, i) => (
            <span key={label} className={i === idx && !insufficient ? 'is-current' : ''}>{label}</span>
          ))}
        </div>
      )}
    </div>
  );
}

export function VerdictCard({ a }: { a: AnalysisResult }) {
  const v = a.verdict;
  const t = a.trend.display;
  return (
    <section className="verdict" aria-labelledby="verdict-headline">
      <h3 id="verdict-headline" className="verdict__headline">{v.headline}</h3>
      <EvidenceScale level={v.level} />
      <p className="verdict__sentence">{v.sentence}</p>
      {v.level !== 'insufficient' && (
        <dl className="verdict__numbers">
          <div>
            <dt>{S.verdict.rate}</dt>
            <dd className="verdict__big">{t.rate_value} <span className="verdict__unit">{t.rate_unit}</span></dd>
            <dd className="verdict__range">{t.range}</dd>
          </div>
          <div>
            <dt>{t.total_label}</dt>
            <dd className="verdict__big">{t.total_value} <span className="verdict__unit">{t.total_unit}</span></dd>
            <dd className="verdict__range">{t.percent ?? t.total_range}</dd>
          </div>
        </dl>
      )}
      {a.years_to_detect && <p className="verdict__ytd">{a.years_to_detect.text}</p>}
      <p className="verdict__sure">
        <span className="verdict__sure-label">{S.verdict.howSure}</span> {v.how_sure}
      </p>
      {v.methods_disagree && <p className="verdict__disagree">{S.verdict.disagree}</p>}
    </section>
  );
}
