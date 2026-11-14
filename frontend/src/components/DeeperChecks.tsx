import { Link } from 'react-router-dom';
import type { AnalysisResult, DeeperCheck } from '../data/types.gen';
import { InfoPopover } from './Panel';
import { S } from '../strings/en';

const D = S.deeper;

function Row({ r }: { r: DeeperCheck }) {
  const value = r.value_text ? `${r.value_text} ${r.unit}` : null;
  return (
    <li className={`dcheck dcheck--${r.status}`}>
      <div className="dcheck__head">
        <span className="dcheck__label">
          {r.label}{' '}
          <InfoPopover label={`${D.whatIs} ${r.label}`} icon="help">
            {r.explain}
            {r.warnings && r.warnings.length > 0 && <> <em>{D.note}</em> {r.warnings.join(' ')}</>}
          </InfoPopover>
        </span>
        <span className={`dcheck__status dcheck__status--${r.status}`}>{r.status_text}</span>
      </div>
      {r.status === 'unavailable' ? (
        <p className="dcheck__value dcheck__value--muted">{r.reason ? D.reason(r.reason) : D.unavailable}</p>
      ) : (
        <p className="dcheck__value">
          {value ?? r.unit}
          {r.range_text && <span className="dcheck__range"> · {r.range_text}</span>}
          {r.q !== null && r.q !== undefined && <span className="dcheck__q"> · q = {r.q < 0.001 ? '< 0.001' : r.q.toFixed(3)}</span>}
        </p>
      )}
      {r.detail && <p className="dcheck__detail">{r.detail}</p>}
    </li>
  );
}

/** Results of the team's climate_stats pipeline for one region and variable (all rows, clear or not). */
export function DeeperChecks({ a }: { a: AnalysisResult }) {
  const dc = a.deeper_checks;
  if (!dc) return <p className="help">{D.none}</p>;
  const events = dc.rows.filter((r) => r.group === 'events');
  const methods = dc.rows.filter((r) => r.group === 'method');
  return (
    <div className="dchecks">
      {events.length > 0 && (
        <>
          <h3 className="dchecks__h">{D.events}</h3>
          <ul className="dchecks__list">{events.map((r) => <Row key={r.id} r={r} />)}</ul>
        </>
      )}
      <h3 className="dchecks__h">{D.methods}</h3>
      <ul className="dchecks__list">{methods.map((r) => <Row key={r.id} r={r} />)}</ul>
      <p className="insights__audit">
        {dc.text}{' '}
        <a href={`${import.meta.env.BASE_URL}data/${dc.source_file}`} download>{D.download}</a>
        {' · '}<Link to="/methods?s=deeper">{S.case.moreInMethods}</Link>
      </p>
    </div>
  );
}
