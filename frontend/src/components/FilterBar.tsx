import { useState } from 'react';
import type { CatalogVariable, Index, VariableRef } from '../data/types.gen';
import { SHOW_VALUES, type ShowFilter } from '../lib/filter';
import { InfoPopover, Panel } from './Panel';
import { S } from '../strings/en';

type Props = {
  index: Index;
  variable: VariableRef;
  catalogEntry?: CatalogVariable;
  show: ShowFilter;
  regionsOpen: boolean;
  legendClosed: boolean;
  hintsDismissed: boolean;
  nonDefault: boolean;
  onVariable: (id: string) => void;
  onShow: (s: ShowFilter) => void;
  onRegions: () => void;
  onLegend: () => void;
  onIdeas: () => void;
  onReset: () => void;
};

/** One row of filters over the map (production UX plan A3). On phones the "Show" filter moves into a sheet. */
export function FilterBar(p: Props) {
  const [sheet, setSheet] = useState(false);
  const labels = S.explore.showOptions(p.variable.words.pos, p.variable.words.neg);
  const showSelect = (id: string) => (
    <label className="fbar__field">
      <span className="fbar__label">{S.explore.show}</span>
      <select id={id} className="fbar__select" value={p.show} onChange={(e) => p.onShow(e.target.value as ShowFilter)}>
        {SHOW_VALUES.map((v) => <option key={v} value={v}>{labels[v]}</option>)}
      </select>
    </label>
  );
  return (
    <div className="fbar" role="toolbar" aria-label="Map filters">
      <div className="fbar__group" data-tour="variable">
        <label className="fbar__field">
          <span className="fbar__label">{S.explore.variable}</span>
          <select className="fbar__select fbar__select--strong" value={p.variable.id} onChange={(e) => p.onVariable(e.target.value)}>
            {p.index.variables.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
          </select>
        </label>
        <InfoPopover label={S.explore.about(p.variable.name)}>
          <strong>{p.variable.long_name}</strong>, {p.variable.units_long}.{' '}
          {p.catalogEntry && <>{p.catalogEntry.definition} <em>{S.explore.whyTrends}</em> {p.catalogEntry.why_it_trends}</>}
        </InfoPopover>
      </div>
      <div className="fbar__group fbar__desktop">{showSelect('show-desktop')}</div>
      <button type="button" className="fbar__btn fbar__mobile" aria-expanded={sheet} onClick={() => setSheet(true)}>{S.explore.filters}</button>
      <button type="button" className={`fbar__btn${p.regionsOpen ? ' is-on' : ''}`} aria-pressed={p.regionsOpen} aria-label={S.explore.regionsAria} onClick={p.onRegions} data-tour="regions">
        {S.explore.regions}
      </button>
      {p.legendClosed && <button type="button" className="fbar__btn" onClick={p.onLegend}>{S.explore.legend}</button>}
      {p.hintsDismissed && <button type="button" className="fbar__btn" aria-label={S.explore.ideasAria} onClick={p.onIdeas}>{S.explore.ideas}</button>}
      {p.nonDefault && <button type="button" className="fbar__btn fbar__btn--quiet" onClick={p.onReset}>{S.explore.reset}</button>}
      <span className="fbar__period fbar__desktop">{p.variable.period}</span>
      {sheet && (
        <Panel title={S.explore.filters} onClose={() => setSheet(false)} className="panel-side--sheet">
          {showSelect('show-mobile')}
        </Panel>
      )}
    </div>
  );
}
