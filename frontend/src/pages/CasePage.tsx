import { useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api, DataError } from '../data/load';
import { useData } from '../data/useData';
import type { AnalysisResult, Case, Index, Region, VariableRef } from '../data/types.gen';
import { TrendMap } from '../components/TrendMap';
import { MapLegend } from '../components/MapLegend';
import { VerdictCard, EvidenceScale } from '../components/VerdictCard';
import { InsightList } from '../components/InsightList';
import { SeriesChart, type ChartHandle, type SeriesView } from '../components/SeriesChart';
import { ExtremesChart, MonthChart, SeasonChart } from '../components/SmallCharts';
import { ErrorState, Loading, useScreenContext } from '../components/Shell';
import { CompareView } from './ComparePage';
import { download, seriesCsv } from '../lib/exporters';
import { signColor, type PaletteName } from '../theme/palettes';
import { S } from '../strings/en';

export function CaseRoute() {
  const { id } = useParams();
  const index = useData(api.index, 'index');
  if (index.error) return <ErrorState error={index.error} />;
  if (!index.data) return <Loading />;
  const c = index.data.cases.find((x) => x.id === id);
  if (!c) return <ErrorState>{`There is no case ${id}.`}</ErrorState>;
  if (c.compare_region_id) {
    return <CompareView index={index.data} a={c.region_id} b={c.compare_region_id} variableId={c.variable_id} theCase={c} />;
  }
  return <CaseView index={index.data} regionId={c.region_id} variableId={c.variable_id} theCase={c} />;
}

export function RegionRoute() {
  const { rid } = useParams();
  const [params] = useSearchParams();
  const index = useData(api.index, 'index');
  if (index.error) return <ErrorState error={index.error} />;
  if (!index.data) return <Loading />;
  const varId = params.get('var') ?? index.data.variables[0].id;
  return <CaseView index={index.data} regionId={rid ?? ''} variableId={varId} />;
}

function StepHeading({ n, children }: { n: number; children: string }) {
  return (
    <h2 className="step">
      <span className="step__n">{n}</span>
      {children}
    </h2>
  );
}

function CaseView({ index, regionId, variableId, theCase }: { index: Index; regionId: string; variableId: string; theCase?: Case }) {
  const region = index.regions.find((r) => r.id === regionId);
  const variable = index.variables.find((v) => v.id === variableId);
  const a = useData(() => api.analysis(regionId, variableId), `${regionId}__${variableId}`);
  const layer = useData(() => api.map(variableId), variableId);

  useScreenContext(
    variable && region ? { variable: variable.name, region: region.name, period: variable.period, source: variable.source } : null,
    [variableId, regionId],
  );

  if (!region || !variable) {
    return <ErrorState>{S.map.notOpenTitle}: {regionId || 'unknown region'}.</ErrorState>;
  }
  if (a.error) {
    const missing = a.error instanceof DataError && a.error.missing;
    return <ErrorState error={missing ? undefined : a.error}>{missing ? `${S.map.notOpenTitle} for ${variable.name.toLowerCase()} in ${region.name}.` : undefined}</ErrorState>;
  }
  if (!a.data) return <Loading />;
  return <CaseBody index={index} a={a.data} region={region} variable={variable} theCase={theCase} layer={layer.data} />;
}

function CaseBody({ index, a, region, variable, theCase, layer }: {
  index: Index; a: AnalysisResult; region: Region; variable: VariableRef; theCase?: Case; layer?: Awaited<ReturnType<typeof api.map>>;
}) {
  const [view, setView] = useState<SeriesView>('anomaly');
  const [detail, setDetail] = useState<'season' | 'month'>('season');
  const chart = useRef<ChartHandle>(null);
  const navigate = useNavigate();
  const pal = variable.palette as PaletteName;
  const question = theCase?.question ?? `How has ${variable.long_name.toLowerCase()} changed in ${region.name}?`;
  const fileBase = `trend-detective_${region.id}_${variable.id}`;

  return (
    <article className="case">
      <header className="case__header">
        <div className="kicker">
          {theCase ? `${S.case.caseLabel} ${theCase.id} · ${theCase.title}` : `${S.case.regionLabel} · ${region.name}`}
        </div>
        <StepHeading n={1}>{S.case.steps.question}</StepHeading>
        <h1 className="case__question">{question}</h1>
        {theCase?.teaser && <p className="case__teaser">{theCase.teaser}</p>}
        <p className="case__meta">
          <span>{variable.long_name}</span>
          <span>{region.name}</span>
          <span>{a.period.start.slice(0, 4)}–{a.period.end.slice(0, 4)}</span>
          <span>{a.provenance.synthetic ? 'Synthetic demo data' : a.provenance.dataset}</span>
        </p>
      </header>

      <div className="case__grid">
        <section className="panel panel--where">
          <StepHeading n={2}>{S.case.steps.where}</StepHeading>
          <div className="where-map">
            <TrendMap
              layer={layer}
              regions={index.regions}
              activeRegionIds={[region.id]}
              focusActive
              fit={region.bbox}
              scrollZoom={false}
              onRegionClick={(id) => id !== region.id && navigate(`/region/${id}?var=${variable.id}`)}
              ariaLabel={`Map of ${region.name} showing the trend of ${variable.long_name.toLowerCase()} in each grid square.`}
            />
          </div>
          {layer && <MapLegend layer={layer} compact />}
          <p className="help">{S.case.whereNote}</p>
        </section>

        <section className="panel panel--time">
          <div className="panel__head">
            <StepHeading n={3}>{S.case.steps.overTime}</StepHeading>
            <div className="segmented" role="tablist" aria-label="Chart view">
              <button type="button" role="tab" aria-selected={view === 'anomaly'} className={view === 'anomaly' ? 'is-active' : ''} onClick={() => setView('anomaly')}>{S.case.anomalyView}</button>
              <button type="button" role="tab" aria-selected={view === 'raw'} className={view === 'raw' ? 'is-active' : ''} onClick={() => setView('raw')}>{S.case.rawView}</button>
            </div>
          </div>
          <SeriesChart ref={chart} a={a} variable={variable} view={view}
            ariaLabel={`${variable.long_name} in ${region.name}, monthly from ${a.period.start} to ${a.period.end}. ${a.verdict.headline}. ${a.trend.display.annotation}.`} />
          {view === 'anomaly' ? (
            <div className="chart-legend">
              <span><i className="sw sw--bar" style={{ background: signColor(pal, 1) }} />{S.case.above}</span>
              <span><i className="sw sw--bar" style={{ background: signColor(pal, -1) }} />{S.case.below}</span>
              <span><i className="sw sw--line" />{S.case.trendLegend}</span>
            </div>
          ) : null}
          <p className="help">{view === 'anomaly' ? S.case.anomalyHelp : S.case.rawHelp}</p>
        </section>

        <section className="panel panel--verdict">
          <StepHeading n={4}>{S.case.steps.verdict}</StepHeading>
          <VerdictCard a={a} />
        </section>

        <section className="panel panel--found">
          <StepHeading n={5}>{S.case.steps.found}</StepHeading>
          <InsightList a={a} variableId={variable.id} />
        </section>
      </div>

      <section className="closer">
        <h2 className="closer__title">{S.case.steps.detail}</h2>
        <div className="closer__grid">
          <div className="panel">
            <div className="panel__head">
              <h3 className="h3">{detail === 'season' ? S.case.bySeason : S.case.byMonth}<span className="h3__units"> · {variable.rate_units}</span></h3>
              <div className="segmented" role="tablist" aria-label="Season or month">
                <button type="button" role="tab" aria-selected={detail === 'season'} className={detail === 'season' ? 'is-active' : ''} onClick={() => setDetail('season')}>{S.case.bySeason}</button>
                <button type="button" role="tab" aria-selected={detail === 'month'} className={detail === 'month' ? 'is-active' : ''} onClick={() => setDetail('month')}>{S.case.byMonth}</button>
              </div>
            </div>
            {detail === 'season' ? <SeasonChart a={a} variable={variable} /> : <MonthChart a={a} variable={variable} />}
            <p className="help">{detail === 'season' ? S.case.seasonHelp : S.case.monthHelp}</p>
          </div>
          {a.extremes && (
            <div className="panel">
              <h3 className="h3">{a.extremes.label} per year</h3>
              <ExtremesChart a={a} variable={variable} />
              <p className="help">{S.case.extremesHelp} {a.extremes.threshold_text}.</p>
            </div>
          )}
        </div>
      </section>

      <section className="keep">
        <div>
          <h3 className="h3">{S.case.otherVariables}</h3>
          <div className="chips">
            {index.variables.map((v) => {
              const s = index.verdicts[`${region.id}__${v.id}`];
              return (
                <Link key={v.id} to={`/region/${region.id}?var=${v.id}`} className={`chip chip--rich${v.id === variable.id ? ' is-active' : ''}`} aria-current={v.id === variable.id}>
                  <span className="chip__name">{v.name}</span>
                  {s && <span className="chip__meta"><EvidenceScale level={s.level} compact /> {s.rate}</span>}
                </Link>
              );
            })}
          </div>
        </div>
        <div>
          <h3 className="h3">{S.case.otherRegions}</h3>
          <div className="chips">
            {index.regions.map((r) => {
              const s = index.verdicts[`${r.id}__${variable.id}`];
              return (
                <Link key={r.id} to={`/region/${r.id}?var=${variable.id}`} className={`chip chip--rich${r.id === region.id ? ' is-active' : ''}`} aria-current={r.id === region.id}>
                  <span className="chip__name">{r.name}</span>
                  {s && <span className="chip__meta"><EvidenceScale level={s.level} compact /> {s.rate}</span>}
                </Link>
              );
            })}
          </div>
        </div>
      </section>

      <footer className="case__footer">
        <div className="case__downloads">
          <span className="muted">{S.case.download}:</span>
          <button type="button" className="btn" onClick={() => download(`${fileBase}.csv`, seriesCsv(a, variable.long_name, region.name))}>{S.case.csv}</button>
          <button type="button" className="btn" onClick={() => chart.current?.downloadPng(fileBase)}>{S.case.png}</button>
        </div>
        <p className="case__prov">
          {S.case.source}: {a.provenance.dataset}. {a.provenance.processing.join('; ')}. <Link to="/methods?s=data">Data and methods</Link>
        </p>
      </footer>
    </article>
  );
}
