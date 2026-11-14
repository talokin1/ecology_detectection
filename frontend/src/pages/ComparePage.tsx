import { useMemo } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../data/load';
import { useData } from '../data/useData';
import type { AnalysisResult, Case, Index, Region, VariableRef } from '../data/types.gen';
import { TrendMap } from '../components/TrendMap';
import { MapLegend } from '../components/MapLegend';
import { EvidenceScale } from '../components/VerdictCard';
import { SeriesChart } from '../components/SeriesChart';
import { ErrorState, Loading, useScreenContext } from '../components/Shell';
import { REGION_COLORS } from '../theme/palettes';
import { S } from '../strings/en';

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

  if (!ra || !rb || !variable || a === b) return <ErrorState>Pick two different prepared regions to compare.</ErrorState>;
  const err = da.error ?? db.error ?? cmp.error;
  if (err) return <ErrorState error={err} />;
  if (!da.data || !db.data || !cmp.data) return <Loading />;
  return <CompareBody index={index} ra={ra} rb={rb} variable={variable} A={da.data} B={db.data} cmp={cmp.data} layer={layer.data} theCase={theCase} />;
}

function CompareBody({ index, ra, rb, variable, A, B, cmp, layer, theCase }: {
  index: Index; ra: Region; rb: Region; variable: VariableRef; A: AnalysisResult; B: AnalysisResult;
  cmp: Awaited<ReturnType<typeof api.compare>>; layer?: Awaited<ReturnType<typeof api.map>>; theCase?: Case;
}) {
  const navigate = useNavigate();
  const yRange = useMemo<[number, number]>(() => {
    const vals = [...A.series.anomaly, ...B.series.anomaly].filter((v): v is number => v !== null);
    const m = Math.max(...vals.map(Math.abs));
    return [-m * 1.05, m * 1.05];
  }, [A, B]);
  // the stored file may hold the pair in the other order; the gap's sign then flips
  const flipped = cmp.region_a !== ra.id;
  const colors = { [ra.id]: REGION_COLORS[0], [rb.id]: REGION_COLORS[1] };
  const go = (x: string, y: string, v: string) => navigate(`/compare/${x}/${y}?var=${v}`);

  return (
    <article className="case compare">
      <header className="case__header">
        <div className="kicker">{theCase ? `${S.case.caseLabel} ${theCase.id} · ${theCase.title}` : S.compare.title}</div>
        <h2 className="step"><span className="step__n">1</span>{S.case.steps.question}</h2>
        <h1 className="case__question">{theCase?.question ?? `Does ${variable.long_name.toLowerCase()} change the same way in ${ra.name} and ${rb.name}?`}</h1>
        {theCase?.teaser && <p className="case__teaser">{theCase.teaser}</p>}
        <div className="compare__pickers">
          <label>
            <span className="muted">{S.compare.variable}</span>
            <select value={variable.id} onChange={(e) => go(ra.id, rb.id, e.target.value)}>
              {index.variables.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>
          </label>
          <label>
            <span className="muted"><i className="sw sw--dot" style={{ background: REGION_COLORS[0] }} /> A</span>
            <select value={ra.id} onChange={(e) => e.target.value !== rb.id && go(e.target.value, rb.id, variable.id)}>
              {index.regions.map((r) => <option key={r.id} value={r.id} disabled={r.id === rb.id}>{r.name}</option>)}
            </select>
          </label>
          <label>
            <span className="muted"><i className="sw sw--dot" style={{ background: REGION_COLORS[1] }} /> B</span>
            <select value={rb.id} onChange={(e) => e.target.value !== ra.id && go(ra.id, e.target.value, variable.id)}>
              {index.regions.map((r) => <option key={r.id} value={r.id} disabled={r.id === ra.id}>{r.name}</option>)}
            </select>
          </label>
        </div>
      </header>

      <div className="compare__grid">
        <section className="panel">
          <h2 className="step"><span className="step__n">2</span>{S.case.steps.where}</h2>
          <div className="where-map where-map--tall">
            <TrendMap layer={layer} regions={index.regions} activeRegionIds={[ra.id, rb.id]} regionColors={colors}
              fit={union(ra, rb)} showLabels scrollZoom={false}
              onRegionClick={(id) => navigate(`/region/${id}?var=${variable.id}`)}
              ariaLabel={`Map of the trend of ${variable.long_name.toLowerCase()} with ${ra.name} and ${rb.name} outlined.`} />
          </div>
          {layer && <MapLegend layer={layer} compact />}
        </section>

        <section className="panel">
          <h2 className="step"><span className="step__n">3</span>{S.case.steps.overTime}</h2>
          {[{ r: ra, d: A, c: REGION_COLORS[0], k: 'A' }, { r: rb, d: B, c: REGION_COLORS[1], k: 'B' }].map(({ r, d, c, k }) => (
            <div key={r.id} className="compare__row">
              <div className="compare__rowhead">
                <Link to={`/region/${r.id}?var=${variable.id}`} className="compare__name">
                  <i className="sw sw--dot" style={{ background: c }} />{k} · {r.name}
                </Link>
                <div className="compare__verdict">
                  <EvidenceScale level={d.verdict.level} compact />
                  <span className="compare__headline">{d.verdict.headline}</span>
                  <span className="compare__rate">{d.trend.display.rate}</span>
                </div>
              </div>
              <SeriesChart a={d} variable={variable} view="anomaly" height={210} yRange={yRange} showAnnotation={false}
                ariaLabel={`${variable.long_name} in ${r.name}: ${d.verdict.headline}, ${d.trend.display.annotation}.`} />
            </div>
          ))}
        </section>
      </div>

      <section className={`answer${cmp.differ ? ' answer--yes' : ''}`}>
        <h2 className="step"><span className="step__n">4</span>{S.compare.question}</h2>
        <p className="answer__main">{cmp.answer}</p>
        <p className="answer__sentence">{cmp.sentence}</p>
        <dl className="verdict__numbers">
          <div>
            <dt>{S.compare.gap} ({flipped ? `${rb.name} minus ${ra.name}` : `${ra.name} minus ${rb.name}`})</dt>
            <dd className="verdict__big">{cmp.display.rate}</dd>
            <dd className="verdict__range">{cmp.display.range}</dd>
          </div>
        </dl>
        <p className="help">{S.compare.explain} <Link to="/methods?s=compare">{S.case.howDoWeKnow}</Link></p>
      </section>
    </article>
  );
}
