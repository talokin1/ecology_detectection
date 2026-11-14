import { useEffect, useMemo, useRef, useState } from 'react';
import { AttributionControl, ImageSource, LngLatBounds, Map as MlMap, Marker, NavigationControl, setWorkerUrl } from 'maplibre-gl';
import type { GeoJSONSource, StyleSpecification } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
import type { MapLayer, Region } from '../data/types.gen';
import { basemapUrl } from '../data/load';
import { binIndex, hexToRgb, mix, PALETTES, type PaletteName } from '../theme/palettes';
import { cellIndex, formatLatLon, latToMercY, MERC_MAX_LAT, mercYToLat, pointInGeometry } from '../lib/geo';
import { useTheme } from '../state/theme';
import { S } from '../strings/en';

// MapLibre 6 loads its worker as a separate module; point it at the bundled copy.
setWorkerUrl(workerUrl);

export type CellInfo = { lon: number; lat: number; value: number | null; significant: boolean };

type Props = {
  layer: MapLayer | undefined;
  regions: Region[];
  /** Regions drawn with a heavy outline (the current investigation, or both compared regions). */
  activeRegionIds?: string[];
  /** Outline colour per region id (compare view); default is ink. */
  regionColors?: Record<string, string>;
  /** Fade everything outside the active regions (Case view). */
  focusActive?: boolean;
  /** 'world' or a [west, south, east, north] box to fit. */
  fit: 'world' | number[];
  showLabels?: boolean;
  /** Text added to each region label, e.g. its verdict. */
  labelExtra?: Record<string, string>;
  scrollZoom?: boolean;
  onRegionClick?: (id: string) => void;
  onEmptyClick?: (cell: CellInfo, point: { x: number; y: number }) => void;
  className?: string;
  ariaLabel: string;
};

const WORLD: [[number, number], [number, number]] = [[-168, -56], [180, 76]];
const CORNERS: [[number, number], [number, number], [number, number], [number, number]] = [
  [-180, MERC_MAX_LAT], [180, MERC_MAX_LAT], [180, -MERC_MAX_LAT], [-180, -MERC_MAX_LAT],
];

/** Fit the full width of the world (360 degrees) into the container, centred on Europe and Africa. */
function fitWorld(map: MlMap) {
  const w = map.getContainer().getBoundingClientRect().width;
  if (w > 0) map.jumpTo({ center: [12, 22], zoom: Math.max(0.3, Math.log2(w / 512)) });
}

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Paint the grid into a square Web Mercator canvas (2 px per cell horizontally). */
function paintGrid(layer: MapLayer, faded: [number, number, number]): HTMLCanvasElement {
  const g = layer.grid;
  const W = g.nlon * 2;
  const H = W;
  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d')!;
  const img = ctx.createImageData(W, H);
  const pal = PALETTES[layer.palette as PaletteName].map(hexToRgb);
  const palFaded = pal.map((c) => mix(c, faded, 0.62));
  const n = g.nlat * g.nlon;
  const rgba = new Uint8ClampedArray(n * 4);
  for (let i = 0; i < n; i++) {
    const v = layer.slope_per_decade[i];
    if (v === null) continue;
    const b = binIndex(v, layer.limit, pal.length);
    const c = layer.significant[i] ? pal[b] : palFaded[b];
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

function stipplePoints(layer: MapLayer) {
  const g = layer.grid;
  const features = [];
  for (let r = 0; r < g.nlat; r++) {
    for (let c = 0; c < g.nlon; c++) {
      const i = r * g.nlon + c;
      if (layer.significant[i] && layer.slope_per_decade[i] !== null) {
        features.push({
          type: 'Feature' as const,
          properties: {},
          geometry: { type: 'Point' as const, coordinates: [g.lon0 + c * g.dlon, g.lat0 + r * g.dlat] },
        });
      }
    }
  }
  return { type: 'FeatureCollection' as const, features };
}

function regionsFC(regions: Region[], active: string[], colors: Record<string, string>, ink: string) {
  return {
    type: 'FeatureCollection' as const,
    features: regions.map((r) => ({
      type: 'Feature' as const,
      properties: { id: r.id, active: active.includes(r.id) ? 1 : 0, color: colors[r.id] ?? ink },
      geometry: r.geometry as unknown as { type: "Polygon"; coordinates: number[][][] },
    })),
  };
}

/** World rectangle with the active regions cut out, used to fade the surroundings. */
function maskFC(regions: Region[], active: string[]) {
  const holes: number[][][] = [];
  regions
    .filter((r) => active.includes(r.id))
    .forEach((r) => {
      const polys = (r.geometry.type === 'Polygon' ? [r.geometry.coordinates] : r.geometry.coordinates) as number[][][][];
      polys.forEach((p) => holes.push(p[0]));
    });
  const outer = [[-180, -86], [180, -86], [180, 86], [-180, 86], [-180, -86]];
  return {
    type: 'FeatureCollection' as const,
    features: holes.length
      ? [{ type: 'Feature' as const, properties: {}, geometry: { type: 'Polygon' as const, coordinates: [outer, ...holes] } }]
      : [],
  };
}

function baseStyle(): StyleSpecification {
  const ink = cssVar('--ink');
  return {
    version: 8,
    sources: {
      land: { type: 'geojson', data: basemapUrl('land'), attribution: 'Basemap: Natural Earth' },
      countries: { type: 'geojson', data: basemapUrl('countries') },
      regions: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
      mask: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
      stipple: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
    },
    layers: [
      { id: 'ocean', type: 'background', paint: { 'background-color': cssVar('--map-ocean') } },
      { id: 'land', type: 'fill', source: 'land', paint: { 'fill-color': cssVar('--map-land') } },
      { id: 'borders', type: 'line', source: 'countries', paint: { 'line-color': cssVar('--map-border'), 'line-width': ['interpolate', ['linear'], ['zoom'], 1, 0.4, 5, 0.9] } },
      { id: 'coast', type: 'line', source: 'land', paint: { 'line-color': cssVar('--map-coast'), 'line-width': ['interpolate', ['linear'], ['zoom'], 1, 0.5, 5, 1.1] } },
      { id: 'mask', type: 'fill', source: 'mask', paint: { 'fill-color': cssVar('--bg'), 'fill-opacity': 0.62 } },
      {
        id: 'stipple', type: 'circle', source: 'stipple', minzoom: 2.6,
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 2.6, 0.7, 4, 1.3, 7, 2.2],
          'circle-color': ink, 'circle-opacity': ['interpolate', ['linear'], ['zoom'], 2.6, 0, 3.2, 0.42],
        },
      },
      { id: 'regions-fill', type: 'fill', source: 'regions', paint: { 'fill-color': ink, 'fill-opacity': 0 } },
      { id: 'regions-halo', type: 'line', source: 'regions', paint: { 'line-color': cssVar('--bg'), 'line-width': ['case', ['==', ['get', 'active'], 1], 5, 3.2], 'line-opacity': 0.85 } },
      { id: 'regions-line', type: 'line', source: 'regions', paint: { 'line-color': ['get', 'color'], 'line-width': ['case', ['==', ['get', 'active'], 1], 2.4, 1.3] } },
    ],
  };
}

export function TrendMap(props: Props) {
  const { layer, regions, activeRegionIds = [], regionColors = {}, focusActive, fit, showLabels, labelExtra, scrollZoom = true } = props;
  const box = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const markers = useRef<Marker[]>([]);
  const [ready, setReady] = useState(false);
  const [hover, setHover] = useState<{ x: number; y: number; cell: CellInfo; region?: string } | null>(null);
  const theme = useTheme();
  const latest = useRef(props);
  latest.current = props;
  const activeKey = activeRegionIds.join(',');
  const fitKey = Array.isArray(fit) ? fit.join(',') : fit;

  // create the map once
  useEffect(() => {
    if (!box.current) return;
    const map = new MlMap({
      container: box.current,
      style: baseStyle(),
      bounds: WORLD,
      renderWorldCopies: false,
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
      maxPitch: 0,
      minZoom: 0.3,
      maxZoom: 7,
      scrollZoom,
      fadeDuration: 0,
    });
    map.touchZoomRotate.disableRotation();
    map.addControl(new NavigationControl({ showCompass: false }), 'top-right');
    map.addControl(new AttributionControl({ compact: true }), 'bottom-right');
    map.on('load', () => setReady(true));

    let raf = 0;
    map.on('mousemove', (e) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const l = latest.current.layer;
        const { lng, lat } = e.lngLat;
        const region = latest.current.regions.find((r) => pointInGeometry(lng, lat, r.geometry));
        map.getCanvas().style.cursor = region && latest.current.onRegionClick ? 'pointer' : '';
        if (!l) return setHover(null);
        const i = cellIndex(l, lng, lat);
        if (i < 0) return setHover(null);
        setHover({
          x: e.point.x, y: e.point.y, region: region?.name,
          cell: { lon: lng, lat, value: l.slope_per_decade[i], significant: l.significant[i] === 1 },
        });
      });
    });
    map.on('mouseout', () => setHover(null));
    map.on('click', (e) => {
      const { lng, lat } = e.lngLat;
      const p = latest.current;
      const region = p.regions.find((r) => pointInGeometry(lng, lat, r.geometry));
      if (region && p.onRegionClick) return p.onRegionClick(region.id);
      if (p.onEmptyClick && p.layer) {
        const i = cellIndex(p.layer, lng, lat);
        p.onEmptyClick(
          { lon: lng, lat, value: i >= 0 ? p.layer.slope_per_decade[i] : null, significant: i >= 0 && p.layer.significant[i] === 1 },
          { x: e.point.x, y: e.point.y },
        );
      }
    });
    mapRef.current = map;
    // handle for automated smoke tests
    (box.current as HTMLDivElement & { __map?: MlMap }).__map = map;
    // keep the whole world in view until the user moves the map themselves
    let userMoved = false;
    map.on('movestart', (e) => {
      if ((e as { originalEvent?: Event }).originalEvent) userMoved = true;
    });
    const ro = new ResizeObserver(() => {
      map.resize();
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

  // theme colours of the basemap
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    map.setPaintProperty('ocean', 'background-color', cssVar('--map-ocean'));
    map.setPaintProperty('land', 'fill-color', cssVar('--map-land'));
    map.setPaintProperty('borders', 'line-color', cssVar('--map-border'));
    map.setPaintProperty('coast', 'line-color', cssVar('--map-coast'));
    map.setPaintProperty('mask', 'fill-color', cssVar('--bg'));
    map.setPaintProperty('regions-halo', 'line-color', cssVar('--bg'));
    map.setPaintProperty('stipple', 'circle-color', cssVar('--ink'));
  }, [theme, ready]);

  // the trend raster and the stipple dots
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !layer) return;
    const canvas = paintGrid(layer, hexToRgb(cssVar('--bg')));
    const src = map.getSource('trend') as ImageSource | undefined;
    if (src) src.updateImage({ image: canvas, coordinates: CORNERS });
    else {
      map.addSource('trend', { type: 'image', url: canvas.toDataURL('image/png'), coordinates: CORNERS });
      map.addLayer(
        { id: 'trend', type: 'raster', source: 'trend', paint: { 'raster-resampling': 'nearest', 'raster-fade-duration': 0 } },
        'borders',
      );
    }
    (map.getSource('stipple') as GeoJSONSource).setData(stipplePoints(layer));
  }, [layer, ready, theme]);

  // region outlines, focus mask
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    (map.getSource('regions') as GeoJSONSource).setData(regionsFC(regions, activeRegionIds, regionColors, cssVar('--ink')));
    (map.getSource('mask') as GeoJSONSource).setData(focusActive ? maskFC(regions, activeRegionIds) : { type: 'FeatureCollection', features: [] });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [regions, activeKey, ready, focusActive, theme, JSON.stringify(regionColors)]);

  // labels as HTML markers (no glyph server needed)
  useEffect(() => {
    const map = mapRef.current;
    markers.current.forEach((m) => m.remove());
    markers.current = [];
    if (!map || !ready || !showLabels) return;
    regions.forEach((r) => {
      const el = document.createElement('button');
      el.type = 'button';
      el.className = `region-label${activeRegionIds.includes(r.id) ? ' is-active' : ''}`;
      const extra = labelExtra?.[r.id];
      el.innerHTML = `<span class="region-label__name"></span>${extra ? '<span class="region-label__extra"></span>' : ''}`;
      (el.querySelector('.region-label__name') as HTMLElement).textContent = r.name;
      if (extra) (el.querySelector('.region-label__extra') as HTMLElement).textContent = extra;
      el.addEventListener('click', (ev) => {
        ev.stopPropagation();
        latest.current.onRegionClick?.(r.id);
      });
      const top: [number, number] = [(r.bbox[0] + r.bbox[2]) / 2, r.bbox[3]];
      const m = new Marker({ element: el, anchor: 'bottom', offset: [0, -3] }).setLngLat(top).addTo(map);
      (m as Marker & { priority?: number }).priority = activeRegionIds.includes(r.id) ? 1 : 0;
      markers.current.push(m);
    });
    // hide labels that would overlap a label with higher priority
    const declutter = () => {
      const placed: DOMRect[] = [];
      [...markers.current]
        .sort((p, q) => ((q as Marker & { priority?: number }).priority ?? 0) - ((p as Marker & { priority?: number }).priority ?? 0))
        .forEach((mk) => {
          const el = mk.getElement();
          el.style.visibility = 'visible';
          const b = el.getBoundingClientRect();
          const hit = placed.some((o) => b.left < o.right + 4 && b.right > o.left - 4 && b.top < o.bottom + 2 && b.bottom > o.top - 2);
          if (hit) el.style.visibility = 'hidden';
          else placed.push(b);
        });
    };
    const raf = requestAnimationFrame(declutter);
    map.on('moveend', declutter);
    return () => {
      cancelAnimationFrame(raf);
      map.off('moveend', declutter);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [regions, ready, showLabels, activeKey, JSON.stringify(labelExtra)]);

  // camera
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    if (fit === 'world') fitWorld(map);
    else {
      const b = new LngLatBounds([fit[0], fit[1]], [fit[2], fit[3]]);
      map.fitBounds(b, { padding: 40, duration: 600, maxZoom: 4.6 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey, ready]);

  const units = layer?.units_label ?? '';
  const tooltip = useMemo(() => {
    if (!hover) return null;
    const { cell } = hover;
    return (
      <div className="map-tooltip" style={{ left: hover.x + 14, top: hover.y + 14 }} role="status">
        {hover.region && <div className="map-tooltip__region">{hover.region}</div>}
        <div className="map-tooltip__value">
          {cell.value === null ? S.map.noData : `${cell.value > 0 ? '+' : cell.value < 0 ? '−' : ''}${Math.abs(cell.value)} ${units}`}
        </div>
        {cell.value !== null && <div className="map-tooltip__note">{cell.significant ? S.map.notChance : S.map.chance}</div>}
        <div className="map-tooltip__coords">{formatLatLon(cell.lon, cell.lat)}</div>
      </div>
    );
  }, [hover, units]);

  return (
    <div className={`trend-map ${props.className ?? ''}`}>
      <div ref={box} className="trend-map__canvas" role="img" aria-label={props.ariaLabel} />
      {tooltip}
    </div>
  );
}
