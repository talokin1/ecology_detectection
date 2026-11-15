import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../data/load';
import { useData } from '../data/useData';
import type { VariableRef } from '../data/types.gen';
import { analyseArea, areaSeries, boxIsValid, boxLabel, formatRange, formatRate, gapBetween, type Box, type Season } from '../lib/area';
import type { Level, YearlyTrend } from '../lib/stats';
import { LinesChart, type Line } from './LinesChart';
import { Disclosure, Panel } from './Panel';
import { EvidenceScale } from './VerdictCard';
import { S } from '../strings/en';

/** Second-area colour (Okabe-Ito vermillion); the first area uses the ink colour. */
const B_COLOR = '#D55E00';

function headline(level: Level, perDecade: number, variable: VariableRef): string {
  const word = perDecade > 0 ? variable.words.pos : variable.words.neg;
  return level === 'strong' ? `${S.area.levels.strong}: ${word}` : level === 'moderate' ? `${S.area.levels.moderate}: ${word}` : S.area.levels[level];
}

/** Four number fields: the keyboard way to set or fine-tune the box. */
function BoxFields({ box, onBox }: { box: Box; onBox: (b: Box) => void }) {
  const [v, setV] = useState(box.map(String));
  useEffect(() => setV(box.map(String)), [box]);
  const next = v.map(Number) as Box;
  const ok = boxIsValid(next);
  const names = S.area.edges;
  return (
    <form className="area__fields" onSubmit={(e) => { e.preventDefault(); if (ok) onBox(next); }}>
      {names.map((n, i) => (
        <label key={n}>
          <span className="fbar__label">{n}</span>
          <input type="number" step="0.5" value={v[i]} onChange={(e) => setV(v.map((x, k) => (k === i ? e.target.value : x)))} />
        </label>
      ))}
      <button type="submit" className="btn" disabled={!ok}>{S.area.apply}</button>
      {!ok && <p className="help">{S.area.badBox}</p>}
    </form>
  );
}

/**
 * The answer for an area the visitor drew: rate, 95% range, verdict, the area against the world
 * average and, optionally, against a second area. Computed in the browser from the yearly grid
 * (lib/area.ts, lib/stats.ts), with the same tests as the rest of the app.
 */
export function AreaPanel({ variable, season, decimals, mask, worldRef, box, box2, onBox, onBox2, onDraw, onDrawSecond, onClose }: {
  variable: VariableRef; season: Season; decimals: number; mask: string;
  /** false = this variable has no sound world average, so the area is not compared with one. */
  worldRef: boolean; box: Box; box2: Box | null;
  onBox: (b: Box) => void; onBox2: (b: Box | null) => void; onDraw: () => void; onDrawSecond: () => void; onClose: () => void;
}) {
  const gs = useData(() => api.gridSeries(variable.id, season), `${variable.id}/${season}`);
  const res = useMemo(() => (gs.data ? analyseArea(gs.data, box) : null), [gs.data, box]);
  const second = useMemo(() => {
    if (!gs.data || !box2 || !res) return null;
    const b = areaSeries(gs.data, box2);
    return b ? { b, gap: gapBetween(gs.data, res.area, b) } : null;
  }, [gs.data, box2, res]);
  const u = variable.rate_units;
  const worldName = S.area.world(mask);
  const pText = (p: number) => (p < 0.001 ? '< 0.001' : `= ${p.toFixed(3)}`);
  const rate = (t: YearlyTrend) => formatRate(t.perDecade, decimals);
  const range = (t: YearlyTrend) => `${S.area.range} ${formatRange(t.ci95, decimals)}`;
  const lines = useMemo<Line[]>(() => (res ? [
    { name: S.area.you, y: res.area.values, color: 'ink', width: 2.4 },
    ...(second ? [{ name: S.area.second, y: second.b.values, color: B_COLOR, width: 2 }] : []),
    ...(worldRef ? [{ name: worldName, y: res.world.values, color: 'muted', dash: 'dot', width: 1.8 }] : []),
  ] : []), [res, second, worldName, worldRef]);
  const period = gs.data ? `${gs.data.years[0]}–${gs.data.years[gs.data.years.length - 1]}` : variable.period;
  const t = res?.trend ?? null;

  return (
    <Panel title={S.area.title} kicker={`${variable.name} · ${S.explore.seasons[season]} · ${period}`} onClose={onClose} className="quick area">
      <p className="area__where">{boxLabel(box)}{res && ` · ${S.area.squares(res.area.squares)}`}</p>
      {gs.error && <p className="help">{gs.error.message}</p>}
      {!gs.data && !gs.error && (
        <div className="skeleton" aria-busy="true" aria-label={S.quick.loading}>
          <span className="skeleton__line skeleton__line--big" /><span className="skeleton__line" /><span className="skeleton__block" />
        </div>
      )}
      {gs.data && !res && <p className="help">{S.area.noData(variable.name.toLowerCase())}</p>}
      {res && !t && <p className="help">{S.area.flat}</p>}
      {res && t && (
        <>
          <div className="quick__readout">
            <div className="quick__number">
              <span className="quick__value">{t.level === 'insufficient' ? '—' : rate(t)}</span>
              <span className="quick__unit">{u}</span>
            </div>
            <p className="quick__headline">{headline(t.level, t.perDecade, variable)}</p>
            <EvidenceScale level={t.level} word />
            <p className="quick__range">{range(t)}</p>
          </div>
          {(t.level === 'strong' || t.level === 'moderate') && <p className="area__caution">{S.area.caution}</p>}
          {res.area.coverage < 0.995 && <p className="help">{S.area.coverage(Math.round(res.area.coverage * 100))}</p>}
          <LinesChart years={res.years} lines={lines} trend={t} unit={variable.anomaly_units} centre
            ariaLabel={`${variable.long_name}, yearly values of your area${worldRef ? ` and of the ${worldName.toLowerCase()}` : ''}, ${period}. ${headline(t.level, t.perDecade, variable)}: ${rate(t)} ${u}.`} />
          <div className="chart-legend">
            <span><i className="sw sw--line-c" style={{ background: 'var(--ink)' }} />{S.area.you}</span>
            {second && <span><i className="sw sw--line-c" style={{ background: B_COLOR }} />{S.area.second}</span>}
            {worldRef && <span><i className="sw sw--line-c area__sw-world" />{worldName}</span>}
          </div>
          <p className="help">{S.area.chartHelp}</p>

          {!worldRef && <p className="help">{S.area.noWorld} <Link to="/methods?s=views">{S.case.moreInMethods}</Link></p>}
          {worldRef && res.world.trend && res.gap && (
            <section className="area__vs">
              <h3>{S.area.vsWorld(worldName)}</h3>
              <p className="area__gap"><strong>{S.area.gapWords[res.gap.level]}</strong></p>
              <p>{S.area.vsWorldText(worldName, rate(res.world.trend), S.area.worldWords[res.world.trend.level], rate(res.gap), formatRange(res.gap.ci95, decimals), u)} {S.area.gapTails[res.gap.level]}</p>
            </section>
          )}

          <section className="area__vs">
            <h3>{S.area.secondTitle}</h3>
            {!box2 && (
              <>
                <p className="help">{S.area.secondHelp}</p>
                <button type="button" className="btn" onClick={onDrawSecond}>{S.area.addSecond}</button>
              </>
            )}
            {box2 && !second && <p className="help">{S.area.noData(variable.name.toLowerCase())}</p>}
            {box2 && second && (
              <>
                <p className="area__where"><i className="sw sw--line-c" style={{ background: B_COLOR }} /> {boxLabel(box2)}</p>
                {second.gap ? (
                  <>
                    <p className="area__gap"><strong>{S.area.gapWords[second.gap.level]}</strong></p>
                    <p>{S.area.vsSecondText(rate(second.gap), formatRange(second.gap.ci95, decimals), u)} {S.area.gapTails[second.gap.level]}</p>
                  </>
                ) : <p className="help">{S.area.flat}</p>}
              </>
            )}
            {box2 && (
              <div className="quick__actions">
                <button type="button" className="btn" onClick={onDrawSecond}>{S.area.redrawSecond}</button>
                <button type="button" className="btn btn--quiet" onClick={() => onBox2(null)}>{S.area.removeSecond}</button>
              </div>
            )}
          </section>
        </>
      )}
      <div className="quick__actions">
        <button type="button" className="btn btn--primary" onClick={onDraw}>{S.area.redraw}</button>
      </div>
      <Disclosure title={S.area.edit} summary={boxLabel(box)}>
        <BoxFields box={box} onBox={onBox} />
      </Disclosure>
      <Disclosure title={S.area.howTitle} summary={S.area.howSummary}>
        <p className="help">{S.area.how}</p>
        <p className="help">{S.area.quick}</p>
        <p className="help">{S.area.caution}</p>
        {t && <p className="help">{S.area.tests(t.n, pText(t.pMk), pText(t.pOls))}</p>}
        <p className="help"><Link to="/methods?s=area">{S.case.moreInMethods}</Link></p>
      </Disclosure>
    </Panel>
  );
}
