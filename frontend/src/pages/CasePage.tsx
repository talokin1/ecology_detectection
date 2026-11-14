import { lazy, Suspense, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api, DataError } from '../data/load';
import { useData } from '../data/useData';
import type { AnalysisResult, Case, Index, MapLayer, Region, VariableRef } from '../data/types.gen';
import { MapLegend } from '../components/MapLegend';
import { EvidenceScale, Readout, VerdictDetails } from '../components/VerdictCard';
import { InsightList } from '../components/InsightList';
import { TrendChart, type ChartBars, type ChartHandle } from '../components/SeriesChart';
import { ExtremesChart, MonthChart, SeasonChart } from '../components/SmallCharts';
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

/** Section kicker "02 · Where"; numbers follow one order array so they never drift. */
export function Kicker({ n, children }: { n: number; children: string }) {
  return <h2 className="kicker-h"><span className="kicker-h__n">{String(n).padStart(2, '0')}</span>{children}</h2>;
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
const SECTIONS = ['overTime', 'where', 'found', 'sure', 'closer', 'keep'] as const;
const num = (s: (typeof SECTIONS)[number]) => SECTIONS.indexOf(s) + 1;

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

function CaseBody({ index, a, region, variable, theCase, layer }: {
  index: Index; a: AnalysisResult; region: Region; variable: VariableRef; theCase?: Case; layer?: MapLayer;
}) {
  const [view, setView] = useState<View>('year');
  const [detail, setDetail] = useState<'season' | 'month'>('season');
  const chart = useRef<ChartHandle>(null);
  const navigate = useNavigate();
  const pal = variable.palette as PaletteName;
  const t = a.trend.display;
  const period = `${a.period.start.slice(0, 4)}–${a.period.end.slice(0, 4)}`;
  const question = theCase?.question ?? S.case.question(variable.long_name.toLowerCase(), region.name_in_sentence);
  const fileBase = `trend-detective_${region.id}_${variable.id}`;
  const props = useMemo(() => chartProps(a, variable, view), [a, variable, view]);
  const footer = `${variable.long_name}, ${region.name}, ${period}. ${a.provenance.dataset}${a.provenance.synthetic ? ' (SYNTHETIC DEMO DATA, not a result)' : ''}. Trend Detective.`;

  return (
    <article className="case">
      <header className="case__header">
        <div className="kicker">{theCase ? `${S.case.caseLabel} ${theCase.id} · ${theCase.title}` : `${S.case.regionLabel} · ${region.name}`}</div>
        <h1 className="case__question">{question}</h1>
        {theCase?.teaser && <p className="case__teaser">{theCase.teaser}</p>}
        <p className="case__meta">
          <span>{variable.long_name}, {variable.units_long}</span>
          <span>{region.name}</span>
          <span>{period}</span>
          <span>{a.provenance.synthetic ? S.case.syntheticMeta : a.provenance.dataset}</span>
        </p>
      </header>

      <Readout value={t.rate_value} unit={t.rate_unit} headline={a.verdict.headline} level={a.verdict.level}
        rangeLine={`${t.range} · ${period}`} answer={theCase?.answer ?? a.verdict.answer} />

      <div className="grid75">
        <section className="sec">
          <div className="sec__head">
            <Kicker n={num('overTime')}>{S.case.sections.overTime}</Kicker>
            <div className="segmented" role="group" aria-label="Chart view">
              {(['year', 'month', 'raw'] as View[]).map((k) => (
                <button key={k} type="button" aria-pressed={view === k} className={view === k ? 'is-active' : ''} onClick={() => setView(k)}>{S.case.views[k]}</button>
              ))}
            </div>
          </div>
          {view !== 'raw' && a.verdict.level !== 'insufficient' && (
            <p className="chart-caption"><strong>{S.case.trendTitle}:</strong> {t.annotation}</p>
          )}
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
            {view === 'year' ? S.case.yearHelp : view === 'month' ? S.case.monthHelp : S.case.rawHelp}
            {view !== 'raw' && a.emergence.label ? ` ${a.emergence.label}` : ''}
          </p>
        </section>

        <section className="sec">
          <Kicker n={num('where')}>{S.case.sections.where}</Kicker>
          <div className="where-map">
            <Suspense fallback={<Loading height={300} />}>
              <TrendMap layer={layer} regions={[region]} activeRegionIds={[region.id]} fit={region.bbox} scrollZoom={false}
                ariaLabel={`Map of ${region.name} showing the trend of ${variable.long_name.toLowerCase()} in each grid square.`} />
            </Suspense>
          </div>
          {layer && <MapLegend layer={layer} caption={S.map.caseMapCaption} />}
        </section>
      </div>

      <div className="grid75">
        <section className="sec">
          <Kicker n={num('found')}>{S.case.sections.found}</Kicker>
          <InsightList a={a} variableId={variable.id} />
        </section>
        <section className="sec">
          <Kicker n={num('sure')}>{S.case.sections.sure}</Kicker>
          <VerdictDetails a={a} />
        </section>
      </div>

      <div className="grid75">
        <section className="sec">
          <div className="sec__head">
            <Kicker n={num('closer')}>{`${S.case.sections.closer}: ${detail === 'season' ? S.case.bySeason.toLowerCase() : S.case.byMonth.toLowerCase()}`}</Kicker>
            <div className="segmented" role="group" aria-label="Season or month">
              <button type="button" aria-pressed={detail === 'season'} className={detail === 'season' ? 'is-active' : ''} onClick={() => setDetail('season')}>{S.case.bySeason}</button>
              <button type="button" aria-pressed={detail === 'month'} className={detail === 'month' ? 'is-active' : ''} onClick={() => setDetail('month')}>{S.case.byMonth}</button>
            </div>
          </div>
          <p className="sec__units">{variable.rate_units}</p>
          {detail === 'season' ? <SeasonChart a={a} variable={variable} /> : <MonthChart a={a} variable={variable} />}
          <p className="help">{detail === 'season' ? S.case.seasonHelp : S.case.monthHelp2}</p>
        </section>
        {a.extremes && (
          <section className="sec">
            <h3 className="h3">{a.extremes.label} per year</h3>
            <p className="sec__units">{a.extremes.display.subtitle}</p>
            <ExtremesChart a={a} variable={variable} />
            <p className="help">{a.extremes.display.trend_text}</p>
          </section>
        )}
      </div>

      <section className="sec keep">
        <Kicker n={num('keep')}>{S.case.sections.keep}</Kicker>
        <div className="grid75 grid75--flat">
          <div>
            <h3 className="h3">{S.case.otherVariables}</h3>
            <div className="chips">
              {index.variables.map((v) => {
                const s = index.verdicts[`${region.id}__${v.id}`];
                return (
                  <Link key={v.id} to={`/region/${region.id}?var=${v.id}`} className={`chip chip--rich${v.id === variable.id ? ' is-active' : ''}`} aria-current={v.id === variable.id ? 'page' : undefined}>
                    <span className="chip__name">{v.name}</span>
                    {s && <span className="chip__meta"><EvidenceScale level={s.level} word size="sm" /> · {s.rate_text}</span>}
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
                  <button key={r.id} type="button" onClick={() => navigate(`/region/${r.id}?var=${variable.id}`)}
                    className={`chip chip--rich${r.id === region.id ? ' is-active' : ''}`} aria-current={r.id === region.id ? 'page' : undefined}>
                    <span className="chip__name">{r.name}</span>
                    {s && <span className="chip__meta"><EvidenceScale level={s.level} word size="sm" /> · {s.rate_text}</span>}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      <footer className="case__footer">
        <div className="case__downloads">
          <span className="muted">{S.case.download}:</span>
          <button type="button" className="btn" onClick={() => download(`${fileBase}.csv`, seriesCsv(a, variable.long_name, region.name, variable))}>{S.case.csv}</button>
          <button type="button" className="btn" onClick={() => chart.current?.downloadPng(fileBase)}>{S.case.png}</button>
        </div>
        <p className="case__prov">
          {S.case.source}: {a.provenance.dataset}. {a.provenance.processing.join('; ')}. <Link to="/methods?s=data">{S.case.dataMethods}</Link>
        </p>
      </footer>
    </article>
  );
}
