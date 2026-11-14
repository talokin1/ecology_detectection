import { useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../data/load';
import { useData } from '../data/useData';
import type { Index } from '../data/types.gen';
import { TrendMap, type CellInfo } from '../components/TrendMap';
import { MapLegend } from '../components/MapLegend';
import { EvidenceScale } from '../components/VerdictCard';
import { ErrorState, Loading, useScreenContext } from '../components/Shell';
import { distanceKm, formatLatLon } from '../lib/geo';
import { S } from '../strings/en';

type Popup = { cell: CellInfo; x: number; y: number };

export function MapPage() {
  const index = useData(api.index, 'index');
  if (index.error) return <ErrorState error={index.error} />;
  if (!index.data) return <Loading />;
  return <MapView index={index.data} />;
}

function MapView({ index }: { index: Index }) {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const defaultCase = index.cases.find((c) => c.id === index.default_case) ?? index.cases[0];
  const caseParam = params.get('case');
  const openCase = caseParam === 'none' ? undefined : index.cases.find((c) => c.id === (caseParam ?? defaultCase.id));
  const varId = params.get('var') ?? openCase?.variable_id ?? defaultCase.variable_id;
  const variable = index.variables.find((v) => v.id === varId) ?? index.variables[0];
  const layer = useData(() => api.map(variable.id), variable.id);
  const [popup, setPopup] = useState<Popup | null>(null);

  useScreenContext({ variable: variable.name, region: 'World', period: variable.period, source: variable.source }, [variable.id]);

  const labelExtra = useMemo(
    () => Object.fromEntries(index.regions.map((r) => [r.id, index.verdicts[`${r.id}__${variable.id}`]?.rate ?? ''])),
    [index, variable.id],
  );

  const setVar = (id: string) => {
    const next = new URLSearchParams(params);
    next.set('var', id);
    if (openCase && openCase.variable_id !== id) next.set('case', 'none');
    setParams(next, { replace: true });
    setPopup(null);
  };
  const showCase = (id: string) => {
    const c = index.cases.find((x) => x.id === id)!;
    setParams({ var: c.variable_id, case: id }, { replace: true });
    setPopup(null);
  };

  const nearest = popup
    ? index.regions
        .map((r) => ({ r, km: distanceKm([popup.cell.lon, popup.cell.lat], r.centroid as [number, number]) }))
        .sort((p, q) => p.km - q.km)[0]
    : undefined;

  const caseVerdict = openCase ? index.verdicts[`${openCase.region_id}__${openCase.variable_id}`] : undefined;

  return (
    <div className="mappage">
      <aside className="mappage__panel" aria-label="Choose what to investigate">
        <h1 className="mappage__title">{S.map.title}</h1>
        <p className="mappage__intro">{S.map.intro}</p>

        <h2 className="panel-heading">{S.map.variable}</h2>
        <div className="varlist" role="radiogroup" aria-label={S.map.variable}>
          {index.variables.map((v) => (
            <button key={v.id} type="button" role="radio" aria-checked={v.id === variable.id}
              className={`varlist__item${v.id === variable.id ? ' is-active' : ''}`} onClick={() => setVar(v.id)}>
              <span className="varlist__name">{v.name}</span>
              <span className="varlist__meta">{v.rate_units} · {v.words.neg} / {v.words.pos}</span>
            </button>
          ))}
          <Link className="varlist__more" to="/catalog">All variables in the catalog →</Link>
        </div>

        <h2 className="panel-heading">{S.map.cases}</h2>
        <ol className="caselist">
          {index.cases.map((c) => {
            const v = index.verdicts[`${c.region_id}__${c.variable_id}`];
            return (
              <li key={c.id}>
                <button type="button" className={`caselist__item${openCase?.id === c.id ? ' is-active' : ''}`} onClick={() => showCase(c.id)}>
                  <span className="caselist__num">{c.id}</span>
                  <span className="caselist__body">
                    <span className="caselist__title">{c.title}</span>
                    <span className="caselist__verdict">{v?.headline}</span>
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
        <p className="mappage__hint">{S.map.preparedRegions}</p>
      </aside>

      <section className="mappage__map" aria-label="World trend map">
        <TrendMap
          layer={layer.data}
          regions={index.regions}
          activeRegionIds={openCase ? [openCase.region_id, ...(openCase.compare_region_id ? [openCase.compare_region_id] : [])] : []}
          fit="world"
          showLabels
          labelExtra={labelExtra}
          onRegionClick={(id) => navigate(`/region/${id}?var=${variable.id}`)}
          onEmptyClick={(cell, pt) => setPopup({ cell, x: pt.x, y: pt.y })}
          ariaLabel={`World map of the trend in ${variable.long_name.toLowerCase()} per decade since 1981. Outlined regions have a full investigation.`}
        />

        {openCase && (
          <article className="casecard" aria-label={`Case ${openCase.id}`}>
            <button type="button" className="casecard__close" aria-label={S.map.close} onClick={() => setParams({ var: variable.id, case: 'none' }, { replace: true })}>×</button>
            <div className="kicker">{S.case.caseLabel} {openCase.id} · {openCase.title}</div>
            <h2 className="casecard__q">{openCase.question}</h2>
            <p className="casecard__teaser">{openCase.teaser}</p>
            {caseVerdict && (
              <div className="casecard__verdict">
                <EvidenceScale level={caseVerdict.level} compact />
                <div>
                  <div className="casecard__headline">{caseVerdict.headline}</div>
                  <div className="casecard__rate">{caseVerdict.rate}</div>
                </div>
              </div>
            )}
            <Link className="btn btn--primary" to={`/case/${openCase.id}`}>{S.map.openCase} →</Link>
          </article>
        )}

        {layer.data && (
          <div className="mappage__legend">
            <MapLegend layer={layer.data} />
          </div>
        )}
        {layer.data && <p className="mappage__caption">{layer.data.caption}</p>}
        {layer.error && <div className="mappage__error"><ErrorState error={layer.error} /></div>}

        {popup && nearest && (
          <div className="notopen" style={{ left: Math.min(popup.x + 12, 9999), top: popup.y + 12 }} role="dialog" aria-label={S.map.notOpenTitle}>
            <button type="button" className="notopen__close" aria-label={S.map.close} onClick={() => setPopup(null)}>×</button>
            <div className="notopen__coords">{formatLatLon(popup.cell.lon, popup.cell.lat)}</div>
            {popup.cell.value !== null && (
              <div className="notopen__here">
                {S.map.here}: <strong>{popup.cell.value > 0 ? '+' : popup.cell.value < 0 ? '−' : ''}{Math.abs(popup.cell.value)} {layer.data?.units_label}</strong>
                , {popup.cell.significant ? S.map.notChance : S.map.chance}
              </div>
            )}
            <h3>{S.map.notOpenTitle}</h3>
            <p>{S.map.notOpenBody}</p>
            <div className="notopen__nearest">{S.map.nearest}: <strong>{nearest.r.name}</strong> ({Math.round(nearest.km / 100) * 100} km)</div>
            <Link className="btn btn--primary" to={`/region/${nearest.r.id}?var=${variable.id}`}>Open {nearest.r.name} →</Link>
          </div>
        )}
      </section>
    </div>
  );
}
