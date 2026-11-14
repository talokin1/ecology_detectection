import { useEffect, useMemo, useRef, useState } from 'react';
import { AttributionControl, ImageSource, LngLatBounds, Map as MlMap, Marker, NavigationControl, setWorkerUrl } from 'maplibre-gl';
import type { GeoJSONSource, StyleSpecification } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
import type { MapLayer, Region } from '../data/types.gen';
import { basemapUrl } from '../data/load';
import type { PaletteName } from '../theme/palettes';
import { cellRgb, isDarkBin } from '../theme/encoding';
import { cellIndex, formatLatLon, latToMercY, MERC_MAX_LAT, mercYToLat, pointInGeometry } from '../lib/geo';
import { formatCell } from '../lib/format';
import { cellVisible, type ShowFilter } from '../lib/filter';
import { useTheme } from '../state/theme';
import { S } from '../strings/en';

// MapLibre 6 loads its worker as a separate module; point it at the bundled copy.
setWorkerUrl(workerUrl);

export type CellInfo = { lon: number; lat: number; value: number | null; significant: boolean };
export type RegionLabel = { line2?: string; muted?: boolean; prefix?: string };

type Props = {
  layer: MapLayer | undefined;
  /** Regions drawn on this map (outlines). */
  regions: Region[];
  /** Regions drawn with a heavy outline (the current investigation, or both compared regions). */
  activeRegionIds?: string[];
  /** Region highlighted from outside (ledger hover). */
  highlightRegionId?: string | null;
  /** 'world' or a [west, south, east, north] box to fit. */
  fit: 'world' | number[];
  /** Labels per region id; regions without an entry get no label. */
  labels?: Record<string, RegionLabel>;
  scrollZoom?: boolean;
  suppressTooltip?: boolean;
  onRegionClick?: (id: string) => void;
  onEmptyClick?: (cell: CellInfo, point: { x: number; y: number }) => void;
  onHoverRegion?: (id: string | null) => void;
  onEscape?: () => void;
  /** Hide squares that do not match (plan A3). */
  show?: ShowFilter;
  /** MapLibre attribution control; the credit also lives in the legend and on About. */
  attribution?: boolean;
  className?: string;
  ariaLabel: string;
};

const CORNERS: [[number, number], [number, number], [number, number], [number, number]] = [
  [-180, MERC_MAX_LAT], [180, MERC_MAX_LAT], [180, -MERC_MAX_LAT], [-180, -MERC_MAX_LAT],
];

const reducedMotion = () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

/** Fit the full width of the world (360 degrees) into the container, centred on Europe and Africa. */
function fitWorld(map: MlMap) {
  const w = map.getContainer().getBoundingClientRect().width;
  if (w > 0) map.jumpTo({ center: [12, 22], zoom: Math.max(0.3, Math.log2(w / 512)) });
}

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Paint the grid into a square Web Mercator canvas (2 px per cell horizontally). */
function paintGrid(layer: MapLayer, show: ShowFilter): HTMLCanvasElement {
  const g = layer.grid;
  const W = g.nlon * 2;
  const H = W;
  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d')!;
  const img = ctx.createImageData(W, H);
  const palette = layer.palette as PaletteName;
  const n = g.nlat * g.nlon;
  const rgba = new Uint8ClampedArray(n * 4);
  for (let i = 0; i < n; i++) {
    const v = layer.slope_per_decade[i];
    if (v === null || !cellVisible(v, layer.significant[i], show)) continue;
    const c = cellRgb(v, layer.significant[i] === 1, layer.limit, palette);
    rgba[i * 4] = c[0];
    rgba[i * 4 + 1] = c[1];
    rgba[i * 4 + 2] = c[2];
    rgba[i * 4 + 3] = 255;
  }
  const yMax = latToMercY(MERC_MAX_LAT);
  const colOf = new Int32Array(W);
  for (let px = 0; px < W; px++) {
    const lon = -180 + ((px + 0.5) / W) * 360;
    colOf[px] = Math.min(g.nlon - 1, Math.max(0, Math.floor((lon - (g.lon0 - g.dlon / 2)) / g.dlon)));
  }
  for (let py = 0; py < H; py++) {
    const lat = mercYToLat(yMax - ((py + 0.5) / H) * 2 * yMax);
    const row = Math.floor((lat - (g.lat0 - g.dlat / 2)) / g.dlat);
    if (row < 0 || row >= g.nlat) continue;
    for (let px = 0; px < W; px++) {
      const i = row * g.nlon + colOf[px];
      const o = (py * W + px) * 4;
      img.data[o] = rgba[i * 4];
      img.data[o + 1] = rgba[i * 4 + 1];
      img.data[o + 2] = rgba[i * 4 + 2];
      img.data[o + 3] = rgba[i * 4 + 3];
    }
  }
  ctx.putImageData(img, 0, 0);
  return canvas;
}

function stipplePoints(layer: MapLayer, show: ShowFilter) {
  const g = layer.grid;
  const palette = layer.palette as PaletteName;
  const features = [];
  for (let r = 0; r < g.nlat; r++) {
    for (let c = 0; c < g.nlon; c++) {
      const i = r * g.nlon + c;
      const v = layer.slope_per_decade[i];
      if (layer.significant[i] && v !== null && cellVisible(v, 1, show)) {
        features.push({
          type: 'Feature' as const,
          properties: { dark: isDarkBin(v, layer.limit, palette) ? 1 : 0 },
          geometry: { type: 'Point' as const, coordinates: [g.lon0 + c * g.dlon, g.lat0 + r * g.dlat] },
        });
      }
    }
  }
  return { type: 'FeatureCollection' as const, features };
}

function regionsFC(regions: Region[], active: string[], highlight: string | null | undefined) {
  return {
    type: 'FeatureCollection' as const,
    features: regions.map((r) => ({
      type: 'Feature' as const,
      properties: { id: r.id, active: active.includes(r.id) ? 1 : 0, hl: highlight === r.id ? 1 : 0 },
      geometry: r.geometry as unknown as { type: 'Polygon'; coordinates: number[][][] },
    })),
  };
}

/** A small diagonal hatch for land squares without data. */
function hatchImage(color: string) {
  const size = 8;
  const c = document.createElement('canvas');
  c.width = size;
  c.height = size;
  const ctx = c.getContext('2d')!;
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, size);
  ctx.lineTo(size, 0);
  ctx.stroke();
  return ctx.getImageData(0, 0, size, size);
}

function baseStyle(): StyleSpecification {
  const ink = cssVar('--map-ink');
  return {
    version: 8,
    sources: {
      land: { type: 'geojson', data: basemapUrl('land'), attribution: 'Basemap: Natural Earth' },
      countries: { type: 'geojson', data: basemapUrl('countries') },
      regions: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
      stipple: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
    },
    layers: [
      { id: 'ocean', type: 'background', paint: { 'background-color': cssVar('--map-ocean') } },
      { id: 'land', type: 'fill', source: 'land', paint: { 'fill-color': cssVar('--map-land') } },
      { id: 'borders', type: 'line', source: 'countries', paint: { 'line-color': cssVar('--map-border'), 'line-width': ['interpolate', ['linear'], ['zoom'], 1, 0.5, 4, 1.1, 7, 1.8] } },
      { id: 'coast', type: 'line', source: 'land', paint: { 'line-color': cssVar('--map-coast'), 'line-width': ['interpolate', ['linear'], ['zoom'], 1, 0.5, 5, 1.1] } },
      {
        id: 'stipple', type: 'circle', source: 'stipple', minzoom: 2.6,
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 2.6, 0.8, 4, 1.4, 7, 2.3],
          'circle-color': ['case', ['==', ['get', 'dark'], 1], '#ffffff', ink],
          'circle-opacity': ['interpolate', ['linear'], ['zoom'], 2.6, 0, 3.2, 0.65],
        },
      },
      { id: 'regions-fill', type: 'fill', source: 'regions', paint: { 'fill-color': ink, 'fill-opacity': 0 } },
      { id: 'regions-halo', type: 'line', source: 'regions', paint: { 'line-color': cssVar('--map-halo'), 'line-width': ['case', ['any', ['==', ['get', 'active'], 1], ['==', ['get', 'hl'], 1]], 6, 3.5], 'line-opacity': 0.9 } },
      { id: 'regions-line', type: 'line', source: 'regions', paint: { 'line-color': ink, 'line-width': ['case', ['==', ['get', 'hl'], 1], 3.5, ['==', ['get', 'active'], 1], 3, 1.8] } },
    ],
  };
}

export function TrendMap(props: Props) {
  const { layer, regions, activeRegionIds = [], highlightRegionId, fit, labels, scrollZoom = true, suppressTooltip, show = 'all', attribution = true } = props;
  const box = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const markers = useRef<Marker[]>([]);
  const cursor = useRef<{ lon: number; lat: number } | null>(null);
  const [ready, setReady] = useState(false);
  const [narrow, setNarrow] = useState(false);
  const [hover, setHover] = useState<{ x: number; y: number; cell: CellInfo; region?: string } | null>(null);
  const theme = useTheme();
  const latest = useRef(props);
  latest.current = props;
  const activeKey = activeRegionIds.join(',');
  const regionKey = regions.map((r) => r.id).join(',');
  const fitKey = Array.isArray(fit) ? fit.join(',') : fit;
  const stipple = useMemo(() => (layer ? stipplePoints(layer, show) : null), [layer, show]);

  // create the map once
  useEffect(() => {
    if (!box.current) return;
    const map = new MlMap({
      container: box.current,
      style: baseStyle(),
      center: [12, 22],
      zoom: 1,
      renderWorldCopies: false,
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
      keyboard: false,
      maxPitch: 0,
      minZoom: 0.3,
      maxZoom: 7,
      scrollZoom,
      fadeDuration: 0,
    });
    map.touchZoomRotate.disableRotation();
    map.addControl(new NavigationControl({ showCompass: false }), 'top-right');
    if (attribution) map.addControl(new AttributionControl({ compact: true }), 'bottom-right');
    map.on('load', () => {
      map.addImage('hatch', hatchImage(cssVar('--map-hatch')));
      // hatch = not enough data; shown at world scale, where it marks whole areas (ice sheets), not coastal slivers
      map.addLayer({ id: 'land-hatch', type: 'fill', source: 'land', maxzoom: 3.5, paint: { 'fill-pattern': 'hatch' } }, 'borders');
      setReady(true);
    });
    const canvas = map.getCanvas();
    canvas.setAttribute('tabindex', '0');

    const regionAt = (lng: number, lat: number) => latest.current.regions.find((r) => pointInGeometry(lng, lat, r.geometry));
    const cellAt = (lng: number, lat: number): CellInfo | null => {
      const l = latest.current.layer;
      if (!l) return null;
      const i = cellIndex(l, lng, lat);
      if (i < 0) return null;
      return { lon: lng, lat, value: l.slope_per_decade[i], significant: l.significant[i] === 1 };
    };
    let lastRegion: string | null = null;
    const showAt = (lng: number, lat: number, x: number, y: number) => {
      const region = regionAt(lng, lat);
      const id = region?.id ?? null;
      if (id !== lastRegion) {
        lastRegion = id;
        latest.current.onHoverRegion?.(id);
      }
      canvas.style.cursor = region && latest.current.onRegionClick ? 'pointer' : '';
      const cell = cellAt(lng, lat);
      setHover(cell ? { x, y, cell, region: region?.name } : null);
    };
    const activate = (lng: number, lat: number, x: number, y: number) => {
      const p = latest.current;
      const region = regionAt(lng, lat);
      if (region && p.onRegionClick) return p.onRegionClick(region.id);
      const cell = cellAt(lng, lat);
      if (p.onEmptyClick && cell) p.onEmptyClick(cell, { x, y });
    };

    let raf = 0;
    map.on('mousemove', (e) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => showAt(e.lngLat.lng, e.lngLat.lat, e.point.x, e.point.y));
    });
    map.on('mouseout', () => {
      setHover(null);
      lastRegion = null;
      latest.current.onHoverRegion?.(null);
    });
    map.on('click', (e) => activate(e.lngLat.lng, e.lngLat.lat, e.point.x, e.point.y));

    // keyboard: arrows move a square cursor, Enter opens, +/- zoom, Escape closes popups
    canvas.addEventListener('keydown', (ev) => {
      const c = cursor.current ?? { lon: map.getCenter().lng, lat: map.getCenter().lat };
      const moves: Record<string, [number, number]> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] };
      if (moves[ev.key]) {
        ev.preventDefault();
        const next = { lon: Math.max(-179.5, Math.min(179.5, c.lon + moves[ev.key][0])), lat: Math.max(-80, Math.min(84, c.lat + moves[ev.key][1])) };
        cursor.current = next;
        const pt = map.project([next.lon, next.lat]);
        const w = canvas.clientWidth;
        const h = canvas.clientHeight;
        if (pt.x < 20 || pt.y < 20 || pt.x > w - 20 || pt.y > h - 20) map.jumpTo({ center: [next.lon, next.lat] });
        const p2 = map.project([next.lon, next.lat]);
        showAt(next.lon, next.lat, p2.x, p2.y);
      } else if (ev.key === 'Enter' && cursor.current) {
        ev.preventDefault();
        const p2 = map.project([cursor.current.lon, cursor.current.lat]);
        activate(cursor.current.lon, cursor.current.lat, p2.x, p2.y);
      } else if (ev.key === '+' || ev.key === '=') map.zoomIn();
      else if (ev.key === '-') map.zoomOut();
      else if (ev.key === 'Escape') latest.current.onEscape?.();
    });
    canvas.addEventListener('blur', () => setHover(null));

    mapRef.current = map;
    // handle for automated smoke tests
    (box.current as HTMLDivElement & { __map?: MlMap }).__map = map;
    let userMoved = false;
    map.on('movestart', (e) => {
      if ((e as { originalEvent?: Event }).originalEvent) userMoved = true;
    });
    const ro = new ResizeObserver(() => {
      map.resize();
      setNarrow(map.getContainer().clientWidth < 500);
      if (latest.current.fit === 'world' && !userMoved) fitWorld(map);
    });
    ro.observe(box.current);
    return () => {
      ro.disconnect();
      markers.current.forEach((m) => m.remove());
      map.remove();
      mapRef.current = null;
      setReady(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // accessible name on the focusable canvas (not on the container, which holds buttons)
  useEffect(() => {
    mapRef.current?.getCanvas().setAttribute('aria-label', `${props.ariaLabel} ${S.map.keyboardHelp}`);
  }, [props.ariaLabel, ready]);

  // basemap colours (a light plate in both themes)
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    map.setPaintProperty('ocean', 'background-color', cssVar('--map-ocean'));
    map.setPaintProperty('land', 'fill-color', cssVar('--map-land'));
  }, [theme, ready]);

  // the trend raster
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !layer) return;
    const canvas = paintGrid(layer, show);
    const src = map.getSource('trend') as ImageSource | undefined;
    if (src) src.updateImage({ image: canvas, coordinates: CORNERS });
    else {
      map.addSource('trend', { type: 'image', url: canvas.toDataURL('image/png'), coordinates: CORNERS });
      // the grid fades in over the land outline instead of popping (plan B5)
      map.addLayer({
        id: 'trend', type: 'raster', source: 'trend',
        paint: { 'raster-resampling': 'nearest', 'raster-fade-duration': 0, 'raster-opacity': 0, 'raster-opacity-transition': { duration: reducedMotion() ? 0 : 350, delay: 0 } },
      }, 'borders');
      requestAnimationFrame(() => map.setPaintProperty('trend', 'raster-opacity', 1));
    }
  }, [layer, ready, show]);

  // stipple dots: rebuilt only when the layer changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !stipple) return;
    (map.getSource('stipple') as GeoJSONSource).setData(stipple);
  }, [stipple, ready]);

  // region outlines
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    (map.getSource('regions') as GeoJSONSource).setData(regionsFC(regions, activeRegionIds, highlightRegionId));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [regionKey, activeKey, ready, highlightRegionId]);

  // labels as HTML markers (no glyph server needed)
  useEffect(() => {
    const map = mapRef.current;
    markers.current.forEach((m) => m.remove());
    markers.current = [];
    if (!map || !ready || !labels) return;
    regions.forEach((r) => {
      const spec = labels[r.id];
      if (!spec) return;
      const el = document.createElement('button');
      el.type = 'button';
      const active = activeRegionIds.includes(r.id);
      el.className = `region-label${active ? ' is-active' : ''}${highlightRegionId === r.id ? ' is-hl' : ''}`;
      const name = document.createElement('span');
      name.className = 'region-label__name';
      name.textContent = spec.prefix ? `${spec.prefix} · ${r.name}` : r.name;
      el.appendChild(name);
      if (spec.line2) {
        const extra = document.createElement('span');
        extra.className = `region-label__extra${spec.muted ? ' is-muted' : ''}`;
        extra.textContent = spec.line2;
        el.appendChild(extra);
      }
      el.addEventListener('click', (ev) => {
        ev.stopPropagation();
        latest.current.onRegionClick?.(r.id);
      });
      el.addEventListener('mouseenter', () => latest.current.onHoverRegion?.(r.id));
      el.addEventListener('mouseleave', () => latest.current.onHoverRegion?.(null));
      // world labels sit above the region; A/B labels sit on it, so they never leave a zoomed map
      const m = spec.prefix
        ? new Marker({ element: el, anchor: 'center' }).setLngLat(r.centroid as [number, number]).addTo(map)
        : new Marker({ element: el, anchor: 'bottom', offset: [0, -4] }).setLngLat([(r.bbox[0] + r.bbox[2]) / 2, r.bbox[3]]).addTo(map);
      (m as Marker & { priority?: number }).priority = active ? 1 : 0;
      markers.current.push(m);
    });
    // hide labels that overlap a higher-priority label or do not fit inside the map
    const declutter = () => {
      const frame = map.getContainer().getBoundingClientRect();
      // overlays drawn on top of the map (title, legend) count as already placed
      const host = box.current?.closest('.stage__map') ?? null;
      const placed: DOMRect[] = host ? [...host.querySelectorAll('[data-map-overlay] > *, [data-map-overlay]')].map((e) => e.getBoundingClientRect()) : [];
      [...markers.current]
        .sort((p, q) => ((q as Marker & { priority?: number }).priority ?? 0) - ((p as Marker & { priority?: number }).priority ?? 0))
        .forEach((mk) => {
          const el = mk.getElement();
          el.style.visibility = 'visible';
          const b = el.getBoundingClientRect();
          const outside = b.left < frame.left + 2 || b.right > frame.right - 2 || b.top < frame.top + 2 || b.bottom > frame.bottom - 2;
          const hit = placed.some((o) => b.left < o.right + 4 && b.right > o.left - 4 && b.top < o.bottom + 2 && b.bottom > o.top - 2);
          if (hit || outside) el.style.visibility = 'hidden';
          else placed.push(b);
        });
    };
    const raf = requestAnimationFrame(declutter);
    map.on('moveend', declutter);
    map.on('resize', declutter);
    return () => {
      cancelAnimationFrame(raf);
      map.off('moveend', declutter);
      map.off('resize', declutter);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [regionKey, ready, activeKey, JSON.stringify(labels), highlightRegionId]);

  // camera
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    if (fit === 'world') fitWorld(map);
    else {
      const b = new LngLatBounds([fit[0], fit[1]], [fit[2], fit[3]]);
      map.fitBounds(b, { padding: 24, duration: reducedMotion() ? 0 : 600, maxZoom: 4.6 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey, ready]);

  const decimals = layer?.value_decimals ?? 2;
  const units = layer?.units_label ?? '';
  const tooltip = useMemo(() => {
    if (!hover || suppressTooltip) return null;
    const { cell } = hover;
    return (
      <div className="map-tooltip" style={{ left: hover.x + 14, top: hover.y + 14 }}>
        {hover.region && <div className="map-tooltip__region">{hover.region}</div>}
        <div className="map-tooltip__value">{cell.value === null ? S.map.noData : `${formatCell(cell.value, decimals)} ${units}`}</div>
        {cell.value !== null && <div className="map-tooltip__note">{cell.significant ? S.map.passes : S.map.notEnough}</div>}
        <div className="map-tooltip__coords">{formatLatLon(cell.lon, cell.lat)}</div>
      </div>
    );
  }, [hover, units, decimals, suppressTooltip]);

  return (
    <div className={`trend-map${narrow ? ' is-narrow' : ''} ${props.className ?? ''}`}>
      <div ref={box} className="trend-map__canvas" />
      {tooltip}
    </div>
  );
}
