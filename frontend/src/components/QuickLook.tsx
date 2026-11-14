import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../data/load';
import { useData } from '../data/useData';
import type { Case, Index, Region, VariableRef } from '../data/types.gen';
import { Panel } from './Panel';
import { EvidenceScale } from './VerdictCard';
import { TrendChart } from './SeriesChart';
import { signColor, type PaletteName } from '../theme/palettes';
import { S } from '../strings/en';

const signed = (v: number) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v)}`;

/**
 * The answer next to the map (production UX plan A6): rate, 95% range, verdict, yearly series
 * with trend, the answer sentence, and the way to the full analysis or a comparison. This one
 * panel covers the whole challenge scope (variable, region, series, rate, significance).
 */
export function QuickLook({ index, region, variable, theCase, onClose }: {
  index: Index; region: Region; variable: VariableRef; theCase?: Case; onClose: () => void;
}) {
  const a = useData(() => api.analysis(region.id, variable.id), `${region.id}__${variable.id}`);
  const [other, setOther] = useState(() => index.regions.find((r) => r.id !== region.id)?.id ?? '');
  const pal = variable.palette as PaletteName;
  const chart = useMemo(() => {
    if (!a.data) return null;
    const s = a.data.series;
    return {
      bars: {
        x: s.annual.years.map((y) => `${y}-07-01`), y: s.annual.anomaly,
        colors: s.annual.anomaly.map((v) => (v === null ? 'rgba(0,0,0,0)' : signColor(pal, v))),
        hover: s.annual.years.map((y, i) => (s.annual.anomaly[i] === null ? `${y}: no data` : `${y}: ${signed(s.annual.anomaly[i] as number)} ${s.anomaly_units} vs normal`)),
      },
      line: a.data.verdict.level === 'insufficient' ? null : a.data.trend.line,
      band: a.data.verdict.level === 'insufficient' ? null : a.data.trend.band95,
    };
  }, [a.data, pal]);
  const full = theCase ? `/case/${theCase.id}` : `/region/${region.id}?var=${variable.id}`;

  return (
    <Panel title={region.name} kicker={`${variable.name} · ${variable.period}`} onClose={onClose} tour="quicklook" className="quick">
      {theCase && (
        <div className="quick__question">
          <span className="quick__qlabel">{S.quick.question}</span>
          <p>{theCase.question}</p>
        </div>
      )}
      {a.error && <p className="help">{S.errors.notOpen(variable.name.toLowerCase(), region.name)}</p>}
      {!a.data && !a.error && (
        <div className="skeleton" aria-busy="true" aria-label={S.quick.loading}>
          <span className="skeleton__line skeleton__line--big" />
          <span className="skeleton__line" />
          <span className="skeleton__block" />
        </div>
      )}
      {a.data && chart && (
        <>
          <div className="quick__readout">
            <div className="quick__number">
              <span className="quick__value">{a.data.verdict.level === 'insufficient' ? '—' : a.data.trend.display.rate_value}</span>
              <span className="quick__unit">{a.data.trend.display.rate_unit}</span>
            </div>
            <p className="quick__headline">{a.data.verdict.headline}</p>
            <EvidenceScale level={a.data.verdict.level} word />
            <p className="quick__range">{a.data.trend.display.range}</p>
          </div>
          <TrendChart {...chart} height={170} yTitle={a.data.series.anomaly_units}
            footer={`${variable.long_name}, ${region.name}. ${a.data.provenance.dataset}. Trend Detective.`}
            ariaLabel={`${variable.long_name} in ${region.name}, yearly: ${a.data.verdict.headline}. ${a.data.trend.display.annotation}.`} />
          <p className="quick__answer">{theCase?.answer ?? a.data.verdict.answer}</p>
          <p className="quick__sure"><strong>{S.quick.howSure}</strong> {a.data.verdict.how_sure}</p>
          <div className="quick__actions">
            <Link className="btn btn--primary" to={full}>{S.quick.full}</Link>
          </div>
          <form className="quick__compare" onSubmit={(e) => e.preventDefault()}>
            <label>
              <span className="fbar__label">{S.quick.compare}</span>
              <select className="fbar__select" value={other} onChange={(e) => setOther(e.target.value)}>
                {index.regions.filter((r) => r.id !== region.id).map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </label>
            <Link className="btn" to={`/compare/${region.id}/${other}?var=${variable.id}`}>{S.quick.compareGo}</Link>
          </form>
        </>
      )}
    </Panel>
  );
}
