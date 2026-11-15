import { useState } from 'react';
import type { MapLayer } from '../data/types.gen';
import { CloseIcon, InfoIcon } from './Icons';
import { swatches } from '../theme/encoding';
import { rgbCss, type PaletteName } from '../theme/palettes';
import { S } from '../strings/en';

/**
 * Legend driven by the JSON (labels) and the shared encoding (colours): the full row is "clear
 * trend", the greyish row is "could be chance", hatching is "not enough data". Every mark on the
 * map is explained here, including the dots.
 */
export function MapLegend({ layer, variant = 'panel', caption }: { layer: MapLayer; variant?: 'panel' | 'strip'; caption?: string }) {
  const sw = swatches(layer.palette as PaletteName);
  const lg = layer.legend;
  const bar = (row: 'full' | 'faded') => (
    <div className={`legend__bar${row === 'faded' ? ' legend__bar--faded' : ''}`} aria-hidden="true" style={{ gridTemplateColumns: `repeat(${sw.full.length}, 1fr)` }}>
      {sw[row].map((c, i) => (
        <span key={i} style={{ background: rgbCss(c) }} title={`${lg.edges_text[i]} to ${lg.edges_text[i + 1]}`} />
      ))}
    </div>
  );
  if (variant === 'strip') {
    return (
      <div className="legend-strip" aria-label={`${lg.title}. ${S.map.keyStrong}. ${S.map.keyFaded}. ${S.map.keyNoData}.`}>
        <span className="legend-strip__word">← {layer.words.neg}</span>
        <div className="legend-strip__bars">
          {bar('full')}
          {bar('faded')}
          <div className="legend-strip__ticks" aria-hidden="true">
            <span>{lg.min_text}</span>
            <span>0</span>
            <span>{lg.max_text}</span>
          </div>
        </div>
        <span className="legend-strip__word">{layer.words.pos} →</span>
        <span className="legend-strip__units">{layer.units_label}</span>
        <span className="legend-strip__keys">
          <span><i className="legend__swatch" style={{ background: rgbCss(sw.full[sw.full.length - 3]) }} />{S.map.strong}</span>
          <span><i className="legend__swatch" style={{ background: rgbCss(sw.faded[sw.full.length - 3]) }} />{S.map.faded}</span>
          <span><i className="legend__swatch legend__swatch--nodata" />{S.map.noData}</span>
        </span>
      </div>
    );
  }
  return (
    <div className="legend">
      <div className="legend__title">{lg.title}</div>
      <div className="legend__words">
        <span>← {layer.words.neg}</span>
        <span>{layer.words.pos} →</span>
      </div>
      <div className="legend__rows">
        <span className="legend__rowlabel">{S.map.strong}</span>
        {bar('full')}
        <span className="legend__rowlabel">{S.map.faded}</span>
        {bar('faded')}
      </div>
      <div className="legend__ticks" aria-hidden="true">
        <span>{lg.min_text}</span>
        <span>0</span>
        <span>{lg.max_text}</span>
      </div>
      <ul className="legend__keys">
        <li>{S.map.keyStrong} (q = {layer.fdr_q}).</li>
        <li>{S.map.keyFaded}.</li>
        <li><i className="legend__swatch legend__swatch--nodata" />{S.map.keyNoData}.</li>
      </ul>
      {caption && <p className="legend__caption">{caption}</p>}
    </div>
  );
}

/**
 * Collapsed legend for the Explore map (production UX plan A4): just the colour bar and its ends.
 * The info button expands the full explanation; the cross hides the legend (a "Legend" button in
 * the filter bar brings it back).
 */
/** The palette as one continuous ramp (the map interpolates between the legend bins). */
function ramp(colors: [number, number, number][]): string {
  const n = colors.length;
  return `linear-gradient(to right, ${colors.map((c, i) => `${rgbCss(c)} ${(((i + 0.5) / n) * 100).toFixed(1)}%`).join(', ')})`;
}

export function LegendChip({ layer, onClose, caption }: { layer: MapLayer; onClose: () => void; caption?: string }) {
  const [open, setOpen] = useState(false);
  const sw = swatches(layer.palette as PaletteName);
  const lg = layer.legend;
  return (
    <div className={`lchip${open ? ' is-open' : ''}`} data-tour="legend">
      <div className="lchip__row">
        <span className="lchip__word">{layer.words.neg}</span>
        <div className="lchip__bars" aria-hidden="true">
          <div className="legend__bar legend__bar--smooth" style={{ background: ramp(sw.full) }} />
          <div className="lchip__ticks"><span>{lg.min_text}</span><span>0</span><span>{lg.max_text}</span></div>
        </div>
        <span className="lchip__word">{layer.words.pos}</span>
        <button type="button" className="icon-btn icon-btn--sm" aria-expanded={open} aria-label={S.legend.expand} onClick={() => setOpen((o) => !o)}><InfoIcon size={15} /></button>
        <button type="button" className="icon-btn icon-btn--sm" aria-label={S.legend.close} onClick={onClose}><CloseIcon size={14} /></button>
      </div>
      <div className="lchip__units">{layer.units_label}</div>
      {open && (
        <div className="lchip__more">
          <div className="legend__rows">
            <span className="legend__rowlabel">{S.map.strong}</span>
            <div className="legend__bar legend__bar--smooth" style={{ background: ramp(sw.full) }} />
            <span className="legend__rowlabel">{S.map.faded}</span>
            <div className="legend__bar legend__bar--smooth legend__bar--faded" style={{ background: ramp(sw.faded) }} />
          </div>
          <ul className="legend__keys">
            <li>{S.map.keyStrong} (q = {layer.fdr_q}).</li>
            <li>{S.map.keyFaded}.</li>
            <li><i className="legend__swatch legend__swatch--nodata" />{S.map.keyNoData}.</li>
            <li>{S.map.keySmooth}</li>
          </ul>
          <p className="legend__caption">{caption ? `${caption} ` : ''}{S.legend.projection} {S.legend.credit}</p>
        </div>
      )}
    </div>
  );
}
