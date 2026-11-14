import { Link } from 'react-router-dom';
import type { AnalysisResult } from '../data/types.gen';
import { InfoPopover } from './Panel';
import { S } from '../strings/en';

/**
 * One sentence per finding. The explanation behind it opens in place from a small help button
 * (production UX plan A11, decision D5); findings from a follow-up check say so.
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
              <p className="insight__text">
                {ins.text}{' '}
                <InfoPopover label={`${S.case.howDoWeKnow} ${ins.text}`} icon="help">
                  {S.help[ins.methods_anchor] ?? ''} <Link to={`/methods?s=${ins.methods_anchor}`}>{S.case.moreInMethods}</Link>
                </InfoPopover>
              </p>
              {(ins.tested || (ins.kind === 'neighbour' && a.neighbour)) && (
                <div className="insight__links">
                  {ins.tested && <span className="insight__tested">{S.case.followUp}</span>}
                  {ins.kind === 'neighbour' && a.neighbour && (
                    <Link to={`/compare/${a.region_id}/${a.neighbour.region_id}?var=${variableId}`}>{S.case.compareWith(a.neighbour.name)}</Link>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {!compact && <p className="insights__audit">{a.insights_audit.text}</p>}
    </div>
  );
}
