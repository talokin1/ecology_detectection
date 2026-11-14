import { lazy, Suspense, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../data/load';
import { useData } from '../data/useData';
import type { AnalysisResult, Case, Compare, Index, MapLayer, Region, VariableRef } from '../data/types.gen';
import { LegendChip } from '../components/MapLegend';
import { EvidenceScale, Readout } from '../components/VerdictCard';
import { InsightList } from '../components/InsightList';
import { TrendChart } from '../components/SeriesChart';
import { ErrorState, Loading, useScreenContext } from '../components/Shell';
import { Breadcrumb, Kicker } from './CasePage';
import { REGION_COLORS } from '../theme/palettes';
import { S } from '../strings/en';

const TrendMap = lazy(() => import('../components/TrendMap').then((m) => ({ default: m.TrendMap })));

export function CompareRoute() {
  const { a, b } = useParams();
  const [params] = useSearchParams();
  const index = useData(api.index, 'index');
  if (index.error) return <ErrorState error={index.error} />;
  if (!index.data) return <Loading />;
  return <CompareView index={index.data} a={a ?? ''} b={b ?? ''} variableId={params.get('var') ?? index.data.variables[0].id} />;
}

function union(r1: Region, r2: Region): number[] {
  return [Math.min(r1.bbox[0], r2.bbox[0]), Math.min(r1.bbox[1], r2.bbox[1]), Math.max(r1.bbox[2], r2.bbox[2]), Math.max(r1.bbox[3], r2.bbox[3])];
}

export function CompareView({ index, a, b, variableId, theCase }: { index: Index; a: string; b: string; variableId: string; theCase?: Case }) {
  const ra = index.regions.find((r) => r.id === a);
  const rb = index.regions.find((r) => r.id === b);
  const variable = index.variables.find((v) => v.id === variableId);
  const order = index.regions.map((r) => r.id);
  const da = useData(() => api.analysis(a, variableId), `${a}__${variableId}`);
  const db = useData(() => api.analysis(b, variableId), `${b}__${variableId}`);
  const cmp = useData(() => api.compare(a, b, variableId, order), `${a}__${b}__${variableId}`);
  const layer = useData(() => api.map(variableId), variableId);

  useScreenContext(
    variable && ra && rb ? { variable: variable.name, region: `${ra.name} vs ${rb.name}`, period: variable.period, source: variable.source } : null,
    [variableId, a, b],
  );

  if (!ra || !rb || !variable || a === b) return <ErrorState>{S.compare.pickTwo}</ErrorState>;
  const err = da.error ?? db.error ?? cmp.error;
  if (err) return <ErrorState error={err} />;
  if (!da.data || !db.data || !cmp.data) return <Loading />;
  return <CompareBody index={index} ra={ra} rb={rb} variable={variable} A={da.data} B={db.data} cmp={cmp.data} layer={layer.data} theCase={theCase} />;
}

const signed = (v: number) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v)}`;

function CompareBody({ index, ra, rb, variable, A, B, cmp, layer, theCase }: {
  index: Index; ra: Region; rb: Region; variable: VariableRef; A: AnalysisResult; B: AnalysisResult; cmp: Compare; layer?: MapLayer; theCase?: Case;
}) {
  const navigate = useNavigate();
  const [legendOpen, setLegendOpen] = useState(true);
  const grey = 'rgba(122,129,139,0.55)';
  const yRange = useMemo<[number, number]>(() => {
    const vals = [...A.series.annual.anomaly, ...B.series.annual.anomaly].filter((v): v is number => v !== null);
    const m = Math.max(...vals.map(Math.abs));
    return [-m * 1.1, m * 1.1];
  }, [A, B]);
  const regionChart = (d: AnalysisResult) => ({
    bars: {
      x: d.series.annual.years.map((y) => `${y}-07-01`), y: d.series.annual.anomaly, colors: grey,
      hover: d.series.annual.years.map((y, i) => (d.series.annual.anomaly[i] === null ? `${y}: no data` : `${y}: ${signed(d.series.annual.anomaly[i] as number)} ${d.series.anomaly_units} vs normal`)),
    },
    line: d.trend.line, band: d.trend.band95,
  });
  const g = cmp.gap_series;
  const gapChart = {
    bars: { x: g.dates, y: g.diff, colors: grey, opacity: 0.7, hover: g.dates.map((dt, i) => (g.diff[i] === null ? `${dt}: no data` : `${dt}: ${signed(g.diff[i] as number)}`)) },
    line: g.line, band: g.band95,
  };
  const go = (x: string, y: string, v: string) => navigate(`/compare/${x}/${y}?var=${v}`);
  const period = variable.period;
  const footer = `${variable.long_name}, ${ra.name} and ${rb.name}, ${period}. ${A.provenance.dataset}. Trend Detective.`;
  const rows = [{ r: ra, d: A, c: REGION_COLORS[0], k: 'A' }, { r: rb, d: B, c: REGION_COLORS[1], k: 'B' }];

  return (
    <article className="case compare">
      <header className="case__header">
        <Breadcrumb index={index} variable={variable} extra={S.compare.title} />
        <h1 className="case__question">{theCase?.question ?? S.compare.question(variable.long_name.toLowerCase(), ra.name_in_sentence, rb.name_in_sentence)}</h1>
        {theCase?.teaser && <p className="case__teaser">{theCase.teaser}</p>}
        <div className="compare__pickers">
          <label>
            <span className="muted">{S.compare.variable}</span>
            <select value={variable.id} onChange={(e) => go(ra.id, rb.id, e.target.value)}>
              {index.variables.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>
          </label>
          <label>
            <span className="muted"><i className="sw sw--line-c" style={{ background: REGION_COLORS[0] }} /> A</span>
            <select value={ra.id} onChange={(e) => e.target.value !== rb.id && go(e.target.value, rb.id, variable.id)}>
              {index.regions.map((r) => <option key={r.id} value={r.id} disabled={r.id === rb.id}>{r.name}</option>)}
            </select>
          </label>
          <label>
            <span className="muted"><i className="sw sw--line-c" style={{ background: REGION_COLORS[1] }} /> B</span>
            <select value={rb.id} onChange={(e) => e.target.value !== ra.id && go(ra.id, e.target.value, variable.id)}>
              {index.regions.map((r) => <option key={r.id} value={r.id} disabled={r.id === ra.id}>{r.name}</option>)}
            </select>
          </label>
        </div>
      </header>

      <Readout value={cmp.display.rate_value} unit={`${cmp.display.rate_unit} · ${cmp.display.gap_label.toLowerCase()}`}
        headline={theCase?.headline ?? cmp.headline} level={cmp.level} rangeLine={`${cmp.display.range} · ${cmp.gap_text}`}
        answer={theCase?.answer ?? cmp.answer} extra={<p className="readout__summary">{cmp.summary}</p>} />

      <div className="grid75">
        <section className="sec">
          <Kicker>{S.case.sections.overTime}</Kicker>
          {rows.map(({ r, d, c, k }) => (
            <div key={r.id} className="compare__row">
              <div className="compare__rowhead">
                <Link to={`/region/${r.id}?var=${variable.id}`} className="compare__name">
                  <i className="sw sw--line-c" style={{ background: c }} />{k} · {r.name}
                </Link>
                <span className="compare__verdict"><EvidenceScale level={d.verdict.level} word size="sm" /> · {d.trend.display.rate}</span>
              </div>
              <TrendChart {...regionChart(d)} accent={c} height={190} yRange={yRange} yTitle={d.series.anomaly_units} footer={footer}
                ariaLabel={`${variable.long_name} in ${r.name}: ${d.verdict.headline}, ${d.trend.display.annotation}.`} />
            </div>
          ))}
          <div className="compare__row compare__row--gap">
            <div className="compare__rowhead">
              <span className="compare__name">{g.label}</span>
              <span className="compare__verdict"><EvidenceScale level={cmp.level} word size="sm" /> · {cmp.display.rate}</span>
            </div>
            <TrendChart {...gapChart} height={190} yTitle={variable.units} footer={footer} ariaLabel={`${g.label}. ${cmp.sentence}`} />
            <p className="help">{S.compare.gapNote}</p>
          </div>
        </section>

        <section className="sec">
          <Kicker>{S.case.sections.where}</Kicker>
          <div className="where-map where-map--tall">
            <Suspense fallback={<Loading height={380} />}>
              <TrendMap layer={layer} regions={[ra, rb]} activeRegionIds={[ra.id, rb.id]} fit={union(ra, rb)} scrollZoom={false} attribution={false}
                labels={{ [ra.id]: { prefix: 'A' }, [rb.id]: { prefix: 'B' } }}
                onRegionClick={(id) => navigate(`/region/${id}?var=${variable.id}`)}
                ariaLabel={`Map of the trend of ${variable.long_name.toLowerCase()} with ${ra.name} (A) and ${rb.name} (B) outlined.`} />
            </Suspense>
          </div>
          {layer && legendOpen && <LegendChip layer={layer} onClose={() => setLegendOpen(false)} />}
          {layer && !legendOpen && <button type="button" className="btn btn--quiet" onClick={() => setLegendOpen(true)}>{S.explore.legend}</button>}
          <div className="answer">
            <p className="answer__sentence">{cmp.sentence}</p>
            <p className="help">{S.compare.explain} <Link to="/methods?s=compare">{S.case.howDoWeKnow}</Link></p>
          </div>
        </section>
      </div>

      {theCase && (
        <div className="grid-2">
          {rows.map(({ r, d, c, k }) => (
            <section key={r.id} className="sec">
              <Kicker>{`${k} · ${r.name}`}</Kicker>
              <div className="mini-verdict">
                <i className="sw sw--line-c" style={{ background: c }} />
                <div>
                  <p className="mini-verdict__headline">{d.verdict.headline}</p>
                  <EvidenceScale level={d.verdict.level} word size="sm" />
                  <p className="mini-verdict__rate">{d.trend.display.rate} · {d.trend.display.range}</p>
                  <p className="help">{d.verdict.sentence}</p>
                </div>
              </div>
              <InsightList a={d} variableId={variable.id} compact />
            </section>
          ))}
        </div>
      )}
    </article>
  );
}
