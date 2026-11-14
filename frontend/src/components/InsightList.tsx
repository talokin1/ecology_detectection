import { Link } from 'react-router-dom';
import type { AnalysisResult } from '../data/types.gen';
import { S } from '../strings/en';

/** One sentence per finding, each with a link to the test behind it. Texts come from the JSON verbatim. */
export function InsightList({ a, variableId }: { a: AnalysisResult; variableId: string }) {
  const audit = a.insights_audit;
  return (
    <div className="insights">
      {a.insights.length === 0 ? (
        <p className="insights__empty">{S.case.noInsights}</p>
      ) : (
        <ol className="insights__list">
          {a.insights.map((ins, i) => (
            <li key={ins.kind} className={`insight insight--${ins.kind}`}>
              <span className="insight__num" aria-hidden="true">{String(i + 1).padStart(2, '0')}</span>
              <div>
                <p className="insight__text">{ins.text}</p>
                <div className="insight__links">
                  <Link to={`/methods?s=${ins.methods_anchor}`}>{S.case.howDoWeKnow}</Link>
                  {ins.kind === 'neighbour' && a.neighbour && (
                    <Link to={`/compare/${a.region_id}/${a.neighbour.region_id}?var=${variableId}`}>
                      {S.case.compareWith} with {a.neighbour.name}
                    </Link>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
      <p className="insights__audit">{S.case.audit(audit.tested, audit.passed, audit.q)}</p>
    </div>
  );
}
