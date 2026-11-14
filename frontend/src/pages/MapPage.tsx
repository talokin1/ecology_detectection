import { lazy, Suspense, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../data/load';
import { useData } from '../data/useData';
import type { Index } from '../data/types.gen';
import type { CellInfo } from '../components/TrendMap';
import { MapLegend } from '../components/MapLegend';
import { RegionLedger } from '../components/RegionLedger';
import { EvidenceScale } from '../components/VerdictCard';
import { ErrorState, Loading, useScreenContext } from '../components/Shell';
import { distanceKm, formatLatLon } from '../lib/geo';
import { formatCell } from '../lib/format';
import { LEVEL_INDEX, S } from '../strings/en';

const TrendMap = lazy(() => import('../components/TrendMap').then((m) => ({ default: m.TrendMap })));

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
  const selected = caseParam === 'none' ? undefined : index.cases.find((c) => c.id === (caseParam ?? defaultCase.id));
  const varId = params.get('var') ?? selected?.variable_id ?? defaultCase.variable_id;
  const variable = index.variables.find((v) => v.id === varId) ?? index.variables[0];
  const layer = useData(() => api.map(variable.id), variable.id);
  const [popup, setPopup] = useState<Popup | null>(null);
  const [hl, setHl] = useState<string | null>(null);
  const stage = useRef<HTMLDivElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  const [popupPos, setPopupPos] = useState<{ left: number; top: number } | null>(null);

  useScreenContext({ variable: variable.name, region: 'World', period: variable.period, source: variable.source }, [variable.id]);

  const activeIds = selected && selected.variable_id === variable.id
    ? [selected.region_id, ...(selected.compare_region_id ? [selected.compare_region_id] : [])] : [];

  const labels = useMemo(() => Object.fromEntries(index.regions.map((r) => {
    const v = index.verdicts[`${r.id}__${variable.id}`];
    return [r.id, v ? { line2: `${v.rate_text} · ${v.level_word.toLowerCase()}`, muted: (LEVEL_INDEX[v.level] ?? 0) < 2 } : {}];
  })), [index, variable.id]);

  const setVar = (id: string) => {
    const next = new URLSearchParams(params);
    next.set('var', id);
    if (selected && selected.variable_id !== id) next.set('case', 'none');
    setParams(next, { replace: true });
    setPopup(null);
  };
  const selectCase = (id: string) => {
    const c = index.cases.find((x) => x.id === id)!;
    setParams({ var: c.variable_id, case: id }, { replace: true });
    setPopup(null);
  };

  // popup: clamped inside the map on all sides, focus in, Escape out, focus back to the map
  useLayoutEffect(() => {
    if (!popup || !stage.current || !popupRef.current) return setPopupPos(null);
    const W = stage.current.clientWidth;
    const H = stage.current.clientHeight;
    const w = popupRef.current.offsetWidth;
    const h = popupRef.current.offsetHeight;
    setPopupPos({ left: Math.max(8, Math.min(popup.x + 12, W - w - 8)), top: Math.max(8, Math.min(popup.y + 12, H - h - 8)) });
    popupRef.current.querySelector<HTMLElement>('h3')?.focus();
  }, [popup]);
  const closePopup = () => {
    setPopup(null);
    stage.current?.querySelector<HTMLElement>('.maplibregl-canvas')?.focus();
  };
  useEffect(() => {
    if (!popup) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && closePopup();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [popup]);

  const nearest = popup
    ? index.regions.map((r) => ({ r, km: distanceKm([popup.cell.lon, popup.cell.lat], r.centroid as [number, number]) })).sort((p, q) => p.km - q.km)[0]
    : undefined;

  return (
    <div className="mappage">
      <aside className="rail" aria-label="Choose what to investigate">
        <h2 className="rail__heading">{S.map.variable}</h2>
        <div className="varlist" role="group" aria-label={S.map.variable}>
          {index.variables.map((v) => (
            <button key={v.id} type="button" aria-pressed={v.id === variable.id}
              className={`varlist__item${v.id === variable.id ? ' is-active' : ''}`} onClick={() => setVar(v.id)}>
              <span className="varlist__name">{v.name}</span>
              <span className="varlist__meta">{v.words.neg} / {v.words.pos}</span>
            </button>
          ))}
        </div>
        <Link className="rail__more" to="/catalog">{S.map.catalogLink}</Link>

        <h2 className="rail__heading">{S.map.cases}</h2>
        <ol className="caselist">
          {index.cases.map((c) => {
            const on = selected?.id === c.id;
            return (
              <li key={c.id} className={`caselist__item${on ? ' is-active' : ''}`}>
                <button type="button" className="caselist__btn" aria-expanded={on} onClick={() => selectCase(c.id)}>
                  <span className="caselist__num">{c.id}</span>
                  <span className="caselist__body">
                    <span className="caselist__title">{c.title}</span>
                    <span className="caselist__verdict"><EvidenceScale level={c.level} size="sm" /> {c.headline}</span>
                  </span>
                </button>
                {on && (
                  <div className="caselist__more">
                    <p className="caselist__q">{c.question}</p>
                    <p className="caselist__answer">{c.answer}</p>
                    <Link className="btn btn--primary" to={`/case/${c.id}`}>{S.map.openCase} →</Link>
                  </div>
                )}
              </li>
            );
          })}
        </ol>
        <p className="rail__intro">{S.map.intro} {variable.period.slice(0, 4)}.</p>
      </aside>

      <section className="stage">
        <div className="stage__map" ref={stage}>
          <Suspense fallback={<Loading />}>
            <TrendMap
              layer={layer.data}
              regions={index.regions}
              activeRegionIds={activeIds}
              highlightRegionId={hl}
              fit="world"
              labels={labels}
              suppressTooltip={!!popup}
              onHoverRegion={setHl}
              onRegionClick={(id) => {
                const c = index.cases.find((x) => x.variable_id === variable.id && (x.region_id === id || x.compare_region_id === id));
                navigate(c ? `/case/${c.id}` : `/region/${id}?var=${variable.id}`);
              }}
              onEmptyClick={(cell, pt) => setPopup({ cell, x: pt.x, y: pt.y })}
              onEscape={closePopup}
              ariaLabel={S.map.ariaWorld(variable.long_name.toLowerCase())}
            />
          </Suspense>
          <div className="stage__title" data-map-overlay>
            <h1>{variable.map_title}</h1>
            <p>{S.map.subtitle(variable.period, variable.source)}</p>
          </div>
          {layer.data && <div className="stage__legend" data-map-overlay><MapLegend layer={layer.data} variant="strip" /></div>}
          {layer.error && <div className="stage__error"><ErrorState error={layer.error} /></div>}
          {popup && nearest && (
            <div ref={popupRef} className="notopen" role="dialog" aria-modal="false" aria-labelledby="notopen-title"
              style={popupPos ? { left: popupPos.left, top: popupPos.top } : { visibility: 'hidden' }}>
              <button type="button" className="notopen__close" aria-label={S.map.close} onClick={closePopup}>×</button>
              <h3 id="notopen-title" tabIndex={-1}>{S.map.notOpenTitle}</h3>
              {popup.cell.value !== null && layer.data && (
                <p className="notopen__here">
                  {S.map.thisSquare} ({formatLatLon(popup.cell.lon, popup.cell.lat)}): <strong>{formatCell(popup.cell.value, layer.data.value_decimals)} {layer.data.units_label}</strong>,{' '}
                  {popup.cell.significant ? S.map.passes : S.map.notEnough}.
                </p>
              )}
              <p>{S.map.notOpenBody}</p>
              <Link className="btn btn--primary" to={`/region/${nearest.r.id}?var=${variable.id}`}>{S.map.openNearest(nearest.r.name)}</Link>
            </div>
          )}
        </div>
        <div className="stage__ledger">
          <RegionLedger index={index} variable={variable} layer={layer.data} activeIds={activeIds} highlightId={hl} onHover={setHl} />
          {layer.data && <p className="stage__caption">{layer.data.caption}</p>}
        </div>
      </section>
    </div>
  );
}
