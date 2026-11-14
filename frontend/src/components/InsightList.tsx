import { Link } from 'react-router-dom';
import type { AnalysisResult } from '../data/types.gen';
import { S } from '../strings/en';

/**
 * One sentence per finding, each with a link to the test behind it. Findings that come from a
 * follow-up check are marked as such, so the audit line below can be checked by eye.
 */
export function InsightList({ a, variableId, compact = false }: { a: AnalysisResult; variableId: string; compact?: boolean }) {
  return (
    <div className={`insights${compact ? ' insights--compact' : ''}`}>
      {a.insights.length === 0 ? (
        <p className="insights__empty">{S.case.noInsights}</p>
      ) : (
        <ol className="insights__list">
          {a.insights.map((ins, i) => (
            <li key={ins.kind} className="insight">
              <span className="insight__num" aria-hidden="true">{String(i + 1).padStart(2, '0')}</span>
              <div>
                <p className="insight__text">{ins.text}</p>
                <div className="insight__links">
                  {ins.tested && <span className="insight__tested">{S.case.followUp}</span>}
                  <Link to={`/methods?s=${ins.methods_anchor}`}>{S.case.howDoWeKnow}</Link>
                  {ins.kind === 'neighbour' && a.neighbour && (
                    <Link to={`/compare/${a.region_id}/${a.neighbour.region_id}?var=${variableId}`}>{S.case.compareWith(a.neighbour.name)}</Link>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
      {!compact && <p className="insights__audit">{a.insights_audit.text}</p>}
    </div>
  );
}
