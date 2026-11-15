import { useEffect, useMemo, useRef, useState } from 'react';
import { AttributionControl, ImageSource, LngLatBounds, Map as MlMap, Marker, NavigationControl, setWorkerUrl } from 'maplibre-gl';
import type { GeoJSONSource, StyleSpecification } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
import type { MapLayer, Region } from '../data/types.gen';
import { basemapUrl } from '../data/load';
import type { PaletteName } from '../theme/palettes';
import { isDarkBin, swatches } from '../theme/encoding';
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
  /** Regions that can be hovered and clicked on this map. */
  regions: Region[];
  /** 'all' draws every region's outline; 'active' only the hovered and selected ones (countries). */
  outline?: 'all' | 'active';
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

const CANVAS = 2048;
type LandFC = { features: { geometry: { type: string; coordinates: unknown[] } }[] };
let landPromise: Promise<LandFC> | null = null;
const loadLand = () => (landPromise ??= fetch(basemapUrl('land')).then((r) => r.json() as Promise<LandFC>));

/** Fill squares without data from their neighbours (display only; the land or sea mask hides the overshoot). */
function grow(val: Float32Array, sig: Float32Array, ok: Uint8Array, nlat: number, nlon: number) {
  const add: [number, number, number][] = [];
  for (let r = 0; r < nlat; r++) {
    for (let c = 0; c < nlon; c++) {
      const i = r * nlon + c;
      if (ok[i]) continue;
      let n = 0;
      let v = 0;
      let s = 0;
      for (let dr = -1; dr <= 1; dr++) {
        const rr = r + dr;
        if (rr < 0 || rr >= nlat) continue;
        for (let dc = -1; dc <= 1; dc++) {
          const j = rr * nlon + ((c + dc + nlon) % nlon);
          if (ok[j]) {
            n++;
            v += val[j];
            s += sig[j];
          }
        }
      }
      if (n) add.push([i, v / n, s / n]);
    }
  }
  add.forEach(([i, v, s]) => {
    ok[i] = 1;
    val[i] = v;
    sig[i] = s;
  });
}

/**
 * Paint the trend as a smooth field in a square Web Mercator canvas: values are interpolated
 * between the centres of the grid squares (bilinear), colour runs continuously through the
 * palette, and colour strength follows the share of neighbouring squares that pass the map-wide
 * test. This is drawing only: tooltips, dots and every number still come from the real squares.
 */
function paintGrid(layer: MapLayer, show: ShowFilter, land: LandFC | null): HTMLCanvasElement {
  const g = layer.grid;
  const W = CANVAS;
  const H = CANVAS;
  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d')!;
  const img = ctx.createImageData(W, H);
  const n = g.nlat * g.nlon;
  const val = new Float32Array(n);
  const sig = new Float32Array(n);
  const ok = new Uint8Array(n);
  for (let i = 0; i < n; i++) {
    const v = layer.slope_per_decade[i];
    if (v === null || !cellVisible(v, layer.significant[i], show)) continue;
    val[i] = v;
    sig[i] = layer.significant[i];
    ok[i] = 1;
  }
  const masked = layer.mask !== 'all' && land !== null;
  if (masked) {
    grow(val, sig, ok, g.nlat, g.nlon);
    grow(val, sig, ok, g.nlat, g.nlon);
  }
  const sw = swatches(layer.palette as PaletteName);
  const nb = sw.full.length;
  const yMax = latToMercY(MERC_MAX_LAT);
  const c0 = new Int32Array(W);
  const c1 = new Int32Array(W);
  const tx = new Float32Array(W);
  for (let px = 0; px < W; px++) {
    const f = (-180 + ((px + 0.5) / W) * 360 - g.lon0) / g.dlon;
    const b = Math.floor(f);
    tx[px] = f - b;
    c0[px] = ((b % g.nlon) + g.nlon) % g.nlon;
    c1[px] = (c0[px] + 1) % g.nlon;
  }
  const d = img.data;
  for (let py = 0; py < H; py++) {
    const lat = mercYToLat(yMax - ((py + 0.5) / H) * 2 * yMax);
    const f = Math.max(0, Math.min(g.nlat - 1, (lat - g.lat0) / g.dlat));
    const r0 = Math.min(g.nlat - 1, Math.floor(f));
    const r1 = Math.min(g.nlat - 1, r0 + 1);
    const ty = f - r0;
    const a0 = r0 * g.nlon;
    const a1 = r1 * g.nlon;
    for (let px = 0; px < W; px++) {
      const i00 = a0 + c0[px];
      const i01 = a0 + c1[px];
      const i10 = a1 + c0[px];
      const i11 = a1 + c1[px];
      const w00 = (1 - tx[px]) * (1 - ty) * ok[i00];
      const w01 = tx[px] * (1 - ty) * ok[i01];
      const w10 = (1 - tx[px]) * ty * ok[i10];
      const w11 = tx[px] * ty * ok[i11];
      const ws = w00 + w01 + w10 + w11;
      if (ws < 0.5) continue;
      const v = (w00 * val[i00] + w01 * val[i01] + w10 * val[i10] + w11 * val[i11]) / ws;
      let s = (w00 * sig[i00] + w01 * sig[i01] + w10 * sig[i10] + w11 * sig[i11]) / ws;
      s = s * s * (3 - 2 * s);
      // a value at the centre of a legend bin gets exactly that bin's colour
      const pos = Math.max(0, Math.min(nb - 1, ((v + layer.limit) / (2 * layer.limit)) * nb - 0.5));
      const b0 = Math.min(nb - 2, Math.floor(pos));
      const t = pos - b0;
      const o = (py * W + px) * 4;
      for (let k = 0; k < 3; k++) {
        const full = sw.full[b0][k] + (sw.full[b0 + 1][k] - sw.full[b0][k]) * t;
        const faded = sw.faded[b0][k] + (sw.faded[b0 + 1][k] - sw.faded[b0][k]) * t;
        d[o + k] = faded + (full - faded) * s;
      }
      d[o + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  if (masked) {
    // keep the field on land only (or on the sea only) with the same coastline the map draws
    ctx.globalCompositeOperation = layer.mask === 'land' ? 'destination-in' : 'destination-out';
    ctx.beginPath();
    land.features.forEach((ft) => {
      const polys = (ft.geometry.type === 'Polygon' ? [ft.geometry.coordinates] : ft.geometry.coordinates) as number[][][][];
      polys.forEach((rings) => rings.forEach((ring) => {
        ring.forEach(([lon, lat], k) => {
          const x = ((lon + 180) / 360) * W;
          const y = ((yMax - latToMercY(lat)) / (2 * yMax)) * H;
          if (k === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.closePath();
      }));
    });
    ctx.fill('evenodd');
    ctx.globalCompositeOperation = 'source-over';
  }
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

function regionsFC(regions: Region[], active: string[], highlight: string | null | undefined, outline: 'all' | 'active') {
  const drawn = regions.filter((r) => r.geometry && (outline === 'all' || active.includes(r.id) || highlight === r.id));
  return {
    type: 'FeatureCollection' as const,
    features: drawn.map((r) => ({
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
  const { layer, regions, outline = 'all', activeRegionIds = [], highlightRegionId, fit, labels, scrollZoom = true, suppressTooltip, show = 'all', attribution = true } = props;
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

    const regionAt = (lng: number, lat: number) => latest.current.regions.find((r) =>
      r.geometry && lng >= r.bbox[0] && lng <= r.bbox[2] && lat >= r.bbox[1] && lat <= r.bbox[3] && pointInGeometry(lng, lat, r.geometry));
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
    let cancelled = false;
    setHover(null); // a tooltip from the previous variable would show an old value with new units
    // hatching means "land without data"; a sea-only field has no data on any land, so it is hidden
    if (map.getLayer('land-hatch')) map.setLayoutProperty('land-hatch', 'visibility', layer.mask === 'ocean' ? 'none' : 'visible');
    const draw = (land: LandFC | null) => {
      if (cancelled || mapRef.current !== map) return;
      const canvas = paintGrid(layer, show, land);
      const src = map.getSource('trend') as ImageSource | undefined;
      if (src) src.updateImage({ image: canvas, coordinates: CORNERS });
      else {
        map.addSource('trend', { type: 'image', url: canvas.toDataURL('image/png'), coordinates: CORNERS });
        // the field fades in over the land outline instead of popping (plan B5)
        map.addLayer({
          id: 'trend', type: 'raster', source: 'trend',
          paint: { 'raster-resampling': 'linear', 'raster-fade-duration': 0, 'raster-opacity': 0, 'raster-opacity-transition': { duration: reducedMotion() ? 0 : 350, delay: 0 } },
        }, 'borders');
        requestAnimationFrame(() => map.setPaintProperty('trend', 'raster-opacity', 1));
      }
    };
    if (layer.mask === 'all') draw(null);
    else loadLand().then(draw, () => draw(null));
    return () => {
      cancelled = true;
    };
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
    (map.getSource('regions') as GeoJSONSource).setData(regionsFC(regions, activeRegionIds, highlightRegionId, outline));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [regionKey, activeKey, ready, highlightRegionId, outline]);

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
