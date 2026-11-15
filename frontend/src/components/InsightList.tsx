import { Link } from 'react-router-dom';
import type { AnalysisResult } from '../data/types.gen';
import { InfoPopover } from './Panel';
import { S } from '../strings/en';

/**
 * One plain sentence per finding, each in its own card. The numbers and the method behind a
 * finding open from "How do we know?"; the count of checks we ran sits in a closed disclosure.
 */
export function InsightList({ a, variableId, compact = false }: { a: AnalysisResult; variableId: string; compact?: boolean }) {
  return (
    <div className={`insights${compact ? ' insights--compact' : ''}`}>
      {a.insights.length === 0 ? (
        <p className="insights__empty">{S.case.noInsights}</p>
      ) : (
        <ul className="insights__list">
          {a.insights.map((ins) => (
            <li key={ins.kind} className="insight">
              <p className="insight__text">{ins.text}</p>
              <div className="insight__links">
                <InfoPopover label={`${S.case.howDoWeKnow} ${ins.text}`} icon="help" text={S.case.howDoWeKnow}>
                  {ins.detail && <><strong>{ins.detail}</strong>{' '}</>}
                  {S.help[ins.methods_anchor] ?? ''} <Link to={`/methods?s=${ins.methods_anchor}`}>{S.case.moreInMethods}</Link>
                </InfoPopover>
                {ins.tested && <span className="insight__tested">{S.case.followUp}</span>}
                {ins.kind === 'neighbour' && a.neighbour && (
                  <Link to={`/compare/${a.region_id}/${a.neighbour.region_id}?var=${variableId}`}>{S.case.compareWith(a.neighbour.name)}</Link>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {!compact && (
        <details className="insights__audit">
          <summary>{S.case.auditSummary(a.insights_audit.tested)}</summary>
          <p>{a.insights_audit.text}</p>
        </details>
      )}
    </div>
  );
}
