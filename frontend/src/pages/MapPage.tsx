import { lazy, Suspense, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../data/load';
import { useData } from '../data/useData';
import type { Case, Index } from '../data/types.gen';
import type { CellInfo } from '../components/TrendMap';
import { LegendChip } from '../components/MapLegend';
import { RegionLedger } from '../components/RegionLedger';
import { FilterBar } from '../components/FilterBar';
import { HintChip } from '../components/HintChip';
import { QuickLook } from '../components/QuickLook';
import { Panel } from '../components/Panel';
import { Tour } from '../components/Tour';
import { CloseIcon } from '../components/Icons';
import { ErrorState, Loading, useScreenContext } from '../components/Shell';
import { countVisible, isShowFilter, type ShowFilter } from '../lib/filter';
import { distanceKm, formatLatLon } from '../lib/geo';
import { formatCell } from '../lib/format';
import { LEVEL_INDEX, S } from '../strings/en';

const TrendMap = lazy(() => import('../components/TrendMap').then((m) => ({ default: m.TrendMap })));

type Popup = { cell: CellInfo; x: number; y: number };

const store = {
  get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k: string, v: string | null) => { try { if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch { /* ignore */ } },
};
const HINTS_OFF = 'td-hints-off';
const TOUR_SEEN = 'td-tour-seen';

export function MapPage() {
  const index = useData(api.index, 'index');
  if (index.error) return <ErrorState error={index.error} />;
  if (!index.data) return <Loading />;
  return <Explore index={index.data} />;
}

function Explore({ index }: { index: Index }) {
  const [params, setParams] = useSearchParams();
  const defaultCase = index.cases.find((c) => c.id === index.default_case) ?? index.cases[0];
  const varId = params.get('var') ?? defaultCase.variable_id;
  const variable = index.variables.find((v) => v.id === varId) ?? index.variables[0];
  const panel = params.get('panel');
  const region = index.regions.find((r) => r.id === params.get('region'));
  const theCase = index.cases.find((c) => c.id === params.get('q'));
  const showParam = params.get('show');
  const show: ShowFilter = isShowFilter(showParam) ? showParam : 'all';

  const layer = useData(() => api.map(variable.id), variable.id);
  const catalog = useData(api.catalog, 'catalog');
  const catalogEntry = catalog.data?.variables.find((c) => c.id === variable.catalog_id);

  const [hl, setHl] = useState<string | null>(null);
  const [popup, setPopup] = useState<Popup | null>(null);
  const [legendOpen, setLegendOpen] = useState(true);
  const [hintsOff, setHintsOff] = useState(() => store.get(HINTS_OFF) === '1');
  const [hintIdx, setHintIdx] = useState(0);
  const [tour, setTour] = useState<number | null>(null);
  const [tourSeen, setTourSeen] = useState(() => store.get(TOUR_SEEN) === '1');
  const stage = useRef<HTMLDivElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  const [popupPos, setPopupPos] = useState<{ left: number; top: number } | null>(null);

  useScreenContext({ variable: variable.name, region: region?.name ?? 'World', period: variable.period, source: variable.source }, [variable.id, region?.id]);

  /** Update the URL state (replace, so Back leaves the page rather than undoing panels). */
  const update = (patch: Record<string, string | null>) => {
    // functional form: several updates in one event never overwrite each other
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      Object.entries(patch).forEach(([k, v]) => (v === null ? next.delete(k) : next.set(k, v)));
      return next;
    }, { replace: true });
    setPopup(null);
  };

  // ?tour=1 (from the menu) starts the tour
  useEffect(() => {
    if (params.get('tour')) startTour();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.get('tour')]);

  // hints: questions for the current variable first, then the rest
  const hints = useMemo(() => [...index.cases].sort((a, b) => Number(b.variable_id === variable.id) - Number(a.variable_id === variable.id)), [index.cases, variable.id]);
  const hint = hints[hintIdx % hints.length];

  const openRegion = (id: string, q?: Case) => update({ panel: 'quick', region: id, q: q?.id ?? null, ...(q ? { var: q.variable_id } : {}) });
  const tryHint = (c: Case) => {
    if (c.compare_region_id) update({ var: c.variable_id, panel: 'regions', q: c.id, region: null });
    else openRegion(c.region_id, c);
  };
  const closePanel = () => update({ panel: null, region: null, q: null });

  const startTour = () => {
    store.set(TOUR_SEEN, '1');
    setTourSeen(true);
    setLegendOpen(true);
    setTour(0);
    update({ panel: null, region: null, q: null, show: null, tour: null }); // one update: React Router does not queue them
  };
  const goTourStep = (i: number) => {
    setTour(i);
    const comparison = index.cases.find((c) => c.compare_region_id);
    if (i <= 1) update({ panel: null, region: null, q: null });
    if (i === 1) setLegendOpen(true);
    if (i === 2) openRegion(defaultCase.region_id, defaultCase);
    if (i === 3 && comparison) update({ var: comparison.variable_id, panel: 'regions', q: comparison.id, region: null });
  };

  const activeIds = panel === 'quick' && region ? [region.id]
    : theCase?.compare_region_id && theCase.variable_id === variable.id ? [theCase.region_id, theCase.compare_region_id] : [];

  // region names only on hover, focus and for the selected region (plan A8)
  const labels = useMemo(() => {
    const ids = new Set([...activeIds, ...(hl ? [hl] : [])]);
    return Object.fromEntries(index.regions.filter((r) => ids.has(r.id)).map((r) => {
      const v = index.verdicts[`${r.id}__${variable.id}`];
      return [r.id, v ? { line2: `${v.rate_text} · ${v.level_word.toLowerCase()}`, muted: (LEVEL_INDEX[v.level] ?? 0) < 2 } : {}];
    }));
  }, [index, variable.id, hl, activeIds.join(',')]); // eslint-disable-line react-hooks/exhaustive-deps

  const visible = layer.data ? countVisible(layer.data, show) : 1;

  // "no detailed analysis here" popover: clamped inside the map, focus in, Escape out
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

  const comparisonCase = theCase?.compare_region_id && theCase.variable_id === variable.id ? theCase : undefined;

  return (
    <div className={`explore${panel ? ' has-panel' : ''}`} ref={stage}>
      <div className="explore__map">
        <Suspense fallback={<Loading />}>
          <TrendMap
            layer={layer.data}
            regions={index.regions}
            activeRegionIds={activeIds}
            highlightRegionId={hl}
            fit="world"
            labels={labels}
            show={show}
            attribution={false}
            suppressTooltip={!!popup}
            onHoverRegion={setHl}
            onRegionClick={(id) => openRegion(id)}
            onEmptyClick={(cell, pt) => setPopup({ cell, x: pt.x, y: pt.y })}
            onEscape={closePopup}
            ariaLabel={S.explore.mapAria(variable.long_name.toLowerCase())}
          />
        </Suspense>
      </div>

      <div className="explore__top" data-map-overlay>
        <FilterBar index={index} variable={variable} catalogEntry={catalogEntry} show={show}
          regionsOpen={panel === 'regions'} legendClosed={!legendOpen} hintsDismissed={hintsOff} nonDefault={show !== 'all'}
          onVariable={(id) => update({ var: id, ...(theCase && theCase.variable_id !== id ? { q: null } : {}) })}
          onShow={(s) => update({ show: s === 'all' ? null : s })}
          onRegions={() => (panel === 'regions' ? closePanel() : update({ panel: 'regions', region: null }))}
          onLegend={() => setLegendOpen(true)}
          onIdeas={() => { setHintsOff(false); store.set(HINTS_OFF, null); }}
          onReset={() => update({ show: null })} />
      </div>

      <div className="explore__bottom" data-map-overlay>
        {legendOpen && layer.data && <LegendChip layer={layer.data} synthetic={layer.data.provenance.synthetic} onClose={() => setLegendOpen(false)} />}
        {!hintsOff && hint && tour === null && !panel && (
          <HintChip hint={hint} onTry={() => tryHint(hint)} onNext={() => setHintIdx((i) => i + 1)}
            onDismiss={() => { setHintsOff(true); store.set(HINTS_OFF, '1'); }}
            offerTour={!tourSeen} onTour={startTour} />
        )}
      </div>

      {layer.data && visible === 0 && (
        <div className="explore__empty" role="status">
          <p>{S.explore.noMatch}</p>
          <button type="button" className="btn" onClick={() => update({ show: null })}>{S.explore.reset}</button>
        </div>
      )}
      {layer.error && <div className="explore__error"><ErrorState error={layer.error} /></div>}
      {layer.loading && layer.data && layer.data.variable_id !== variable.id && (
        <div className="explore__busy" role="status"><span className="spinner" aria-hidden="true" />{S.loading}</div>
      )}

      {panel === 'quick' && region && (
        <QuickLook key={`${region.id}-${variable.id}`} index={index} region={region} variable={variable}
          theCase={theCase && theCase.region_id === region.id && theCase.variable_id === variable.id ? theCase : undefined}
          onClose={closePanel} />
      )}
      {panel === 'regions' && (
        <Panel title={S.regionsPanel.title} kicker={`${variable.name} · ${variable.rate_units}`} onClose={closePanel} tour="regionspanel" className="regions">
          {comparisonCase && (
            <div className="quick__question">
              <span className="quick__qlabel">{S.quick.question}</span>
              <p>{comparisonCase.question}</p>
            </div>
          )}
          <p className="help">{S.regionsPanel.lead}</p>
          <RegionLedger index={index} variable={variable} layer={layer.data} activeIds={activeIds} highlightId={hl} onHover={setHl} onSelect={(id) => openRegion(id)} />
          {comparisonCase && (
            <div className="regions__answer">
              <p>{comparisonCase.answer}</p>
              <Link className="btn btn--primary" to={`/case/${comparisonCase.id}`}>{S.regionsPanel.fullComparison}</Link>
            </div>
          )}
        </Panel>
      )}

      {popup && nearest && (
        <div ref={popupRef} className="notopen" role="dialog" aria-modal="false" aria-labelledby="notopen-title"
          style={popupPos ? { left: popupPos.left, top: popupPos.top } : { visibility: 'hidden' }}>
          <button type="button" className="icon-btn icon-btn--sm notopen__close" aria-label={S.map.close} onClick={closePopup}><CloseIcon size={14} /></button>
          <h3 id="notopen-title" tabIndex={-1}>{S.map.notOpenTitle}</h3>
          {popup.cell.value !== null && layer.data && (
            <p className="notopen__here">
              {S.map.thisSquare} ({formatLatLon(popup.cell.lon, popup.cell.lat)}): <strong>{formatCell(popup.cell.value, layer.data.value_decimals)} {layer.data.units_label}</strong>,{' '}
              {popup.cell.significant ? S.map.passes : S.map.notEnough}.
            </p>
          )}
          <p>{S.map.notOpenBody}</p>
          <button type="button" className="btn btn--primary" onClick={() => openRegion(nearest.r.id)}>{S.map.openNearest(nearest.r.name)}</button>
        </div>
      )}

      {tour !== null && <Tour step={tour} onNext={() => goTourStep(tour + 1)} onBack={() => goTourStep(tour - 1)} onClose={() => setTour(null)} />}
    </div>
  );
}
