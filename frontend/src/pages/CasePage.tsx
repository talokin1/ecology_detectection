import { lazy, Suspense, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api, DataError } from '../data/load';
import { useData } from '../data/useData';
import type { AnalysisResult, Case, Index, MapLayer, Region, VariableRef } from '../data/types.gen';
import { LegendChip } from '../components/MapLegend';
import { Readout, VerdictDetails } from '../components/VerdictCard';
import { InsightList } from '../components/InsightList';
import { DeeperChecks } from '../components/DeeperChecks';
import { VsWorld } from '../components/VsWorld';
import { TrendChart, type ChartBars, type ChartHandle } from '../components/SeriesChart';
import { ExtremesChart, MonthChart, SeasonChart } from '../components/SmallCharts';
import { Disclosure, InfoPopover } from '../components/Panel';
import { ErrorState, Loading, useScreenContext } from '../components/Shell';
import { CompareView } from './ComparePage';
import { download, seriesCsv } from '../lib/exporters';
import { signColor, type PaletteName } from '../theme/palettes';
import { S } from '../strings/en';

const TrendMap = lazy(() => import('../components/TrendMap').then((m) => ({ default: m.TrendMap })));

export function CaseRoute() {
  const { id } = useParams();
  const index = useData(api.index, 'index');
  if (index.error) return <ErrorState error={index.error} />;
  if (!index.data) return <Loading />;
  const c = index.data.cases.find((x) => x.id === id);
  if (!c) return <ErrorState>{S.errors.noCase(id ?? '')}</ErrorState>;
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

/** Plain section heading (no step numbers, plan A13). */
export function Kicker({ children }: { n?: number; children: string }) {
  return <h2 className="kicker-h">{children}</h2>;
}

function CaseView({ index, regionId, variableId, theCase }: { index: Index; regionId: string; variableId: string; theCase?: Case }) {
  const region = index.regions.find((r) => r.id === regionId);
  const variable = index.variables.find((v) => v.id === variableId);
  const a = useData(() => api.analysis(regionId, variableId), `${regionId}__${variableId}`);
  const layer = useData(() => api.map(variableId), variableId);

  useScreenContext(
    variable && region ? { variable: variable.name, region: region.name, period: variable.period, source: variable.source, variableId, regionId } : null,
    [variableId, regionId],
  );

  if (!region) return <ErrorState>{S.errors.noRegion(regionId)}</ErrorState>;
  if (!variable) return <ErrorState>{S.errors.notFound}</ErrorState>;
  if (a.error) {
    const missing = a.error instanceof DataError && a.error.missing;
    return <ErrorState error={missing ? undefined : a.error}>{missing ? S.errors.notOpen(variable.name.toLowerCase(), region.name) : undefined}</ErrorState>;
  }
  if (!a.data) return <Loading />;
  return <CaseBody index={index} a={a.data} region={region} variable={variable} theCase={theCase} layer={layer.data} />;
}

type View = 'year' | 'month' | 'raw';
const signed = (v: number) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v)}`;

function chartProps(a: AnalysisResult, variable: VariableRef, view: View) {
  const pal = variable.palette as PaletteName;
  const s = a.series;
  const u = s.anomaly_units;
  const color = (v: number | null) => (v === null ? 'rgba(0,0,0,0)' : signColor(pal, v));
  const hover = (label: string, v: number | null) => (v === null ? `${label}: no data` : `${label}: ${signed(v)} ${u} vs normal`);
  if (view === 'raw') {
    return { rawLine: { x: s.dates, y: s.raw, hover: s.dates.map((d, i) => `${d}: ${s.raw[i] ?? 'no data'} ${variable.units}`) }, yTitle: s.raw_label };
  }
  const bars: ChartBars = view === 'year'
    ? { x: s.annual.years.map((y) => `${y}-07-01`), y: s.annual.anomaly, colors: s.annual.anomaly.map(color), hover: s.annual.years.map((y, i) => hover(String(y), s.annual.anomaly[i])) }
    : { x: s.dates, y: s.anomaly, colors: s.anomaly.map(color), hover: s.dates.map((d, i) => hover(d, s.anomaly[i])), opacity: 0.75 };
  const hasTrend = a.verdict.level !== 'insufficient';
  return {
    bars, yTitle: s.anomaly_label,
    line: hasTrend ? a.trend.line : null, band: hasTrend ? a.trend.band95 : null,
    marker: a.emergence.year ? { x: `${a.emergence.year}-01-01`, label: String(a.emergence.year) } : null,
  };
}

/** Breadcrumb with region and variable selects (replaces "Case 0X" and the chip lists). */
export function Breadcrumb({ index, region, variable, extra }: { index: Index; region?: Region; variable: VariableRef; extra?: string }) {
  const navigate = useNavigate();
  const catalog = useData(api.catalog, 'catalog');
  const entry = catalog.data?.variables.find((c) => c.id === variable.catalog_id);
  const back = region ? `/?var=${variable.id}&panel=quick&region=${region.id}` : `/?var=${variable.id}`;
  return (
    <nav className="crumbs" aria-label="Breadcrumb">
      <Link to={back}>{S.case.breadcrumbRoot}</Link>
      <span aria-hidden="true">/</span>
      {region ? (
        <label className="crumbs__field">
          <select aria-label={S.case.region} value={region.id} onChange={(e) => navigate(`/region/${e.target.value}?var=${variable.id}`)}>
            <optgroup label={S.explore.placeModes.stories}>
              {index.regions.filter((r) => r.story).map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </optgroup>
            <optgroup label={S.explore.placeModes.countries}>
              {index.regions.filter((r) => r.kind === 'country' && !r.story).map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </optgroup>
            <optgroup label={S.explore.placeModes.world}>
              {index.regions.filter((r) => r.kind === 'world').map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </optgroup>
          </select>
        </label>
      ) : <span>{extra}</span>}
      <span aria-hidden="true">/</span>
      <label className="crumbs__field">
        <select aria-label={S.case.variable} value={variable.id} onChange={(e) => navigate(region ? `/region/${region.id}?var=${e.target.value}` : `/?var=${e.target.value}`)}>
          {index.variables.filter((v) => !v.map_only || !region).map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
        </select>
      </label>
      <InfoPopover label={S.explore.about(variable.name)}>
        <strong>{variable.long_name}</strong>, {variable.units_long}.{' '}
        {entry && <>{entry.definition} <em>{S.explore.whyTrends}</em> {entry.why_it_trends}</>}
      </InfoPopover>
    </nav>
  );
}

function CaseBody({ index, a, region, variable, theCase, layer }: {
  index: Index; a: AnalysisResult; region: Region; variable: VariableRef; theCase?: Case; layer?: MapLayer;
}) {
  const [view, setView] = useState<View>('year');
  const [detail, setDetail] = useState<'season' | 'month'>('season');
  const [legendOpen, setLegendOpen] = useState(true);
  const chart = useRef<ChartHandle>(null);
  const pal = variable.palette as PaletteName;
  const t = a.trend.display;
  const period = `${a.period.start.slice(0, 4)}–${a.period.end.slice(0, 4)}`;
  const question = theCase?.question ?? S.case.question(variable.long_name.toLowerCase(), region.name_in_sentence);
  const fileBase = `trend-detective_${region.id}_${variable.id}`;
  const props = useMemo(() => chartProps(a, variable, view), [a, variable, view]);
  const footer = `${variable.long_name}, ${region.name}, ${period}. ${a.provenance.dataset}. Trend Detective.`;
  const seasonInsight = a.insights.find((i) => i.kind === 'season' || i.kind === 'season_unresolved');

  return (
    <article className="case">
      <header className="case__header">
        <Breadcrumb index={index} region={region} variable={variable} />
        <h1 className="case__question">{question}</h1>
        {theCase?.teaser && <p className="case__teaser">{theCase.teaser}</p>}
      </header>

      <Readout value={t.rate_value} unit={t.rate_unit} headline={a.verdict.headline} level={a.verdict.level}
        rangeLine={`${t.range} · ${period}`} answer={theCase?.answer ?? a.verdict.answer} />

      <div className="grid75">
        <section className="sec">
          <div className="sec__head">
            <Kicker>{S.case.sections.overTime}</Kicker>
            <div className="segmented" role="group" aria-label="Chart view">
              {(['year', 'month', 'raw'] as View[]).map((k) => (
                <button key={k} type="button" aria-pressed={view === k} className={view === k ? 'is-active' : ''} onClick={() => setView(k)}>{S.case.views[k]}</button>
              ))}
            </div>
          </div>
          <TrendChart ref={chart} {...props} footer={footer}
            ariaLabel={`${variable.long_name} in ${region.name}, ${period}. ${a.verdict.headline}. ${t.annotation}.`} />
          {view !== 'raw' ? (
            <div className="chart-legend">
              <span><i className="sw sw--bar" style={{ background: signColor(pal, 1) }} />{S.case.above}</span>
              <span><i className="sw sw--bar" style={{ background: signColor(pal, -1) }} />{S.case.below}</span>
              <span><i className="sw sw--line" />{S.case.trendLegend}</span>
            </div>
          ) : null}
          <p className="help">
            {view === 'year' ? (a.emergence.label ?? S.case.yearHelp) : view === 'month' ? S.case.monthHelp : S.case.rawHelp(variable.source)}
          </p>
        </section>

        <section className="sec">
          <Kicker>{S.case.sections.where}</Kicker>
          <div className="where-map">
            <Suspense fallback={<Loading height={300} />}>
              <TrendMap layer={layer} regions={[region]} activeRegionIds={[region.id]} fit={region.bbox} scrollZoom={false} attribution={false}
                ariaLabel={`Map of ${region.name} showing the trend of ${variable.long_name.toLowerCase()} in each grid square.`} />
            </Suspense>
          </div>
          {layer && legendOpen && <LegendChip layer={layer} caption={S.map.caseMapCaption} onClose={() => setLegendOpen(false)} />}
          {layer && !legendOpen && <button type="button" className="btn btn--quiet" onClick={() => setLegendOpen(true)}>{S.explore.legend}</button>}
        </section>
      </div>

      <div className="grid75">
        <section className="sec">
          <Kicker>{S.case.sections.found}</Kicker>
          <InsightList a={a} variableId={variable.id} />
        </section>
        <section className="sec">
          <Kicker>{S.case.sections.sure}</Kicker>
          <p className="vdetails__sure vdetails__sure--plain"><strong>{S.verdict.howSure}</strong> {a.verdict.sure_plain}</p>
          <Disclosure title={S.case.statsDetails} summary={`${t.total_label}: ${t.total}`}>
            <VerdictDetails a={a} />
          </Disclosure>
        </section>
      </div>

      <div className="stack">
        {a.vs_world && (
          <Disclosure title={S.vsWorld.title(a.vs_world.reference)} summary={a.vs_world.headline}>
            <VsWorld a={a} region={region} variable={variable} />
          </Disclosure>
        )}
        <Disclosure title={S.case.sections.closer} summary={seasonInsight?.text ?? `${S.case.bySeason}, ${S.case.byMonth.toLowerCase()}`}>
          <div className="sec__head">
            <p className="sec__units">{variable.rate_units}</p>
            <div className="segmented" role="group" aria-label="Season or month">
              <button type="button" aria-pressed={detail === 'season'} className={detail === 'season' ? 'is-active' : ''} onClick={() => setDetail('season')}>{S.case.bySeason}</button>
              <button type="button" aria-pressed={detail === 'month'} className={detail === 'month' ? 'is-active' : ''} onClick={() => setDetail('month')}>{S.case.byMonth}</button>
            </div>
          </div>
          {detail === 'season' ? <SeasonChart a={a} variable={variable} /> : <MonthChart a={a} variable={variable} />}
          <p className="help">{detail === 'season' ? S.case.seasonHelp : S.case.monthHelp2}</p>
        </Disclosure>
        {a.extremes && (
          <Disclosure title={`${S.case.sections.extremes}: ${a.extremes.label.toLowerCase()}`} summary={a.extremes.display.trend_text}>
            <p className="sec__units">{a.extremes.display.subtitle}</p>
            <ExtremesChart a={a} variable={variable} />
          </Disclosure>
        )}
        {a.deeper_checks && (
          <Disclosure title={S.case.sections.deeper} summary={S.deeper.summary(a.deeper_checks.clear, a.deeper_checks.available)}>
            <DeeperChecks a={a} />
          </Disclosure>
        )}
        <Disclosure title={S.case.sections.data} summary={`${S.case.source}: ${a.provenance.dataset}`}>
          <div className="case__downloads">
            <button type="button" className="btn" onClick={() => download(`${fileBase}.csv`, seriesCsv(a, variable.long_name, region.name, variable))}>{S.case.csv}</button>
            <button type="button" className="btn" onClick={() => chart.current?.downloadPng(fileBase)}>{S.case.png}</button>
          </div>
          <p className="case__prov">{a.provenance.processing.join('; ')}. {a.provenance.caveat} <Link to="/methods?s=data">{S.case.dataMethods}</Link></p>
        </Disclosure>
      </div>
    </article>
  );
}
