import type { MapLayer } from '../data/types.gen';
import { binEdges, hexToRgb, mix, PALETTES, type PaletteName } from '../theme/palettes';
import { S } from '../strings/en';

function fmtEdge(v: number): string {
  const r = Math.round(v * 1000) / 1000;
  if (r === 0) return '0';
  return `${r > 0 ? '+' : '−'}${Math.abs(r)}`;
}

/** Colour bar with words at both ends, plus what full colour, faded colour and grey mean. */
export function MapLegend({ layer, compact = false }: { layer: MapLayer; compact?: boolean }) {
  const pal = PALETTES[layer.palette as PaletteName];
  const edges = binEdges(layer.limit, pal.length);
  const bg = hexToRgb(getComputedStyle(document.documentElement).getPropertyValue('--bg').trim() || '#ffffff');
  const faded = pal.map((c) => {
    const [r, g, b] = mix(hexToRgb(c), bg, 0.62);
    return `rgb(${r},${g},${b})`;
  });
  return (
    <div className={`legend${compact ? ' legend--compact' : ''}`}>
      <div className="legend__title">
        Change <span className="legend__units">{layer.units_label}</span>
      </div>
      <div className="legend__words">
        <span>← {layer.words.neg}</span>
        <span>{layer.words.pos} →</span>
      </div>
      <div className="legend__bar" aria-hidden="true">
        {pal.map((c, i) => (
          <span key={c} style={{ background: c }} title={`${fmtEdge(edges[i])} to ${fmtEdge(edges[i + 1])}`} />
        ))}
      </div>
      <div className="legend__bar legend__bar--faded" aria-hidden="true">
        {faded.map((c, i) => (
          <span key={i} style={{ background: c }} />
        ))}
      </div>
      <div className="legend__ticks" aria-hidden="true">
        <span>≤ {fmtEdge(-layer.limit)}</span>
        <span>0</span>
        <span>≥ {fmtEdge(layer.limit)}</span>
      </div>
      {!compact && (
        <ul className="legend__keys">
          <li>
            <span className="legend__swatch" style={{ background: pal[pal.length - 2] }} />
            {S.map.fullColour}
          </li>
          <li>
            <span className="legend__swatch" style={{ background: faded[pal.length - 2] }} />
            {S.map.faded}
          </li>
          <li>
            <span className="legend__swatch legend__swatch--nodata" />
            {S.map.noData}
          </li>
        </ul>
      )}
    </div>
  );
}
