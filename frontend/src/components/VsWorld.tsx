import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import type { AnalysisResult, Region, VariableRef } from '../data/types.gen';
import { LinesChart, type Line } from './LinesChart';
import { S } from '../strings/en';

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/**
 * The region next to the world average of the same variable: is it changing faster, slower, or
 * in step? Every number and sentence comes from the analysis JSON (`vs_world`).
 */
export function VsWorld({ a, region, variable }: { a: AnalysisResult; region: Region; variable: VariableRef }) {
  const v = a.vs_world;
  const lines = useMemo<Line[]>(() => (v ? [
    { name: region.name, y: v.annual.here, color: 'ink', width: 2.4 },
    { name: cap(v.reference), y: v.annual.world, color: 'muted', dash: 'dot', width: 1.8 },
  ] : []), [v, region.name]);
  if (!v) return null;
  return (
    <div className="vsworld">
      <p className="vsworld__headline">{v.headline}</p>
      <p>{v.sentence}</p>
      <LinesChart years={v.annual.years} lines={lines} unit={variable.anomaly_units} height={220}
        ariaLabel={`${variable.long_name}: yearly values for ${region.name} and for the ${v.reference}. ${v.headline}.`} />
      <div className="chart-legend">
        <span><i className="sw sw--line-c" style={{ background: 'var(--ink)' }} />{region.name}</span>
        <span><i className="sw sw--line-c area__sw-world" />{cap(v.reference)}</span>
      </div>
      <p className="help">{S.vsWorld.chartHelp}</p>
      <table className="vsworld__table">
        <caption>{S.vsWorld.caption(v.rate_units)}</caption>
        <thead>
          <tr><th scope="col">{S.vsWorld.season}</th><th scope="col">{S.vsWorld.here}</th><th scope="col">{S.vsWorld.world}</th><th scope="col">{S.vsWorld.gap}</th></tr>
        </thead>
        <tbody>
          {v.seasons.map((s) => (
            <tr key={s.season}>
              <th scope="row">{s.months}</th>
              <td>{s.display.here}</td>
              <td>{s.display.world}</td>
              <td className={s.clear ? 'is-clear' : ''}>{s.display.difference} <span className="vsworld__range">({s.display.range})</span></td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="help">{S.vsWorld.seasonHelp}</p>
      <p className="help">{v.reference_note}</p>
      <p><Link to={`/?var=${variable.id}&vs=world`}>{S.vsWorld.onMap}</Link></p>
    </div>
  );
}
