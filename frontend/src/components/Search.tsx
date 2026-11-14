import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { api } from '../data/load';
import { useData } from '../data/useData';
import type { Catalog, Index } from '../data/types.gen';
import { useEscape } from './Panel';
import { CloseIcon, SearchIcon } from './Icons';
import { S } from '../strings/en';

type Item = { key: string; group: string; label: string; meta?: string; to: string };

function caseTarget(c: Index['cases'][number]): string {
  return c.compare_region_id ? `/?var=${c.variable_id}&panel=regions&q=${c.id}` : `/?var=${c.variable_id}&panel=quick&region=${c.region_id}&q=${c.id}`;
}

function build(index: Index, catalog: Catalog | undefined, query: string, currentVar: string): Item[] {
  const q = query.trim().toLowerCase();
  const has = (...t: (string | undefined)[]) => t.some((x) => x && x.toLowerCase().includes(q));
  const items: Item[] = [];
  const questions = index.cases.filter((c) => !q || has(c.question, c.title, c.teaser));
  questions.forEach((c) => items.push({ key: `q${c.id}`, group: S.search.questions, label: c.question, to: caseTarget(c) }));
  if (!q) {
    catalog?.topics.forEach((t) => items.push({ key: `t${t.id}`, group: S.search.curious, label: t.label, to: `/catalog?topic=${t.id}` }));
    catalog?.place_types.forEach((p) => items.push({ key: `p${p.id}`, group: S.search.where, label: p.label, to: `/catalog?place=${p.id}` }));
    return items;
  }
  index.regions.filter((r) => has(r.name, r.place_type)).forEach((r) =>
    items.push({ key: `r${r.id}`, group: S.search.places, label: r.name, to: `/?var=${currentVar}&panel=quick&region=${r.id}` }));
  const seen = new Set<string>();
  index.variables.filter((v) => has(v.name, v.long_name, v.topic, v.words.pos, v.words.neg)).forEach((v) => {
    seen.add(v.catalog_id);
    items.push({ key: `v${v.id}`, group: S.search.variables, label: v.name, meta: v.period, to: `/?var=${v.id}` });
  });
  catalog?.variables.filter((v) => !seen.has(v.id) && has(v.name, v.definition, v.topic)).forEach((v) =>
    items.push({ key: `c${v.id}`, group: S.search.variables, label: v.name, meta: v.status === 'ready' ? v.source_short : S.search.planned, to: v.app_variable_id ? `/?var=${v.app_variable_id}` : `/catalog?topic=${v.topic}` }));
  return items;
}

/** Search for places, variables and our questions (production UX plan B2). */
export function Search() {
  const index = useData(api.index, 'index');
  const [wantCatalog, setWantCatalog] = useState(false);
  const catalog = useData(() => (wantCatalog ? api.catalog() : Promise.resolve(undefined)), `catalog-${wantCatalog}`);
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [active, setActive] = useState(0);
  const navigate = useNavigate();
  const location = useLocation();
  const listId = useId();
  const wrap = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const currentVar = new URLSearchParams(location.search).get('var') ?? index.data?.cases.find((c) => c.id === index.data?.default_case)?.variable_id ?? 't2m';
  const items = useMemo(() => (index.data ? build(index.data, catalog.data, query, currentVar) : []), [index.data, catalog.data, query, currentVar]);

  const close = () => {
    setOpen(false);
    setMobileOpen(false);
  };
  useEscape(open || mobileOpen, close);
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => wrap.current && !wrap.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener('mousedown', away);
    return () => document.removeEventListener('mousedown', away);
  }, [open]);
  useEffect(() => setActive(0), [query]);
  useEffect(() => {
    if (mobileOpen) input.current?.focus();
  }, [mobileOpen]);

  const choose = (it: Item) => {
    navigate(it.to);
    setQuery('');
    close();
    input.current?.blur();
  };
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setActive((a) => Math.min(items.length - 1, a + 1)); }
    if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
    if (e.key === 'Enter' && items[active]) { e.preventDefault(); choose(items[active]); }
  };

  let lastGroup = '';
  return (
    <div className={`search${mobileOpen ? ' is-mobile-open' : ''}`} ref={wrap}>
      <button type="button" className="icon-btn search__toggle" aria-label={S.search.open} aria-expanded={mobileOpen} onClick={() => setMobileOpen((o) => !o)}>
        <SearchIcon />
      </button>
      <div className="search__field">
        <SearchIcon size={15} />
        <input ref={input} type="search" className="search__input" placeholder={S.search.placeholder} aria-label={S.search.label}
          role="combobox" aria-expanded={open} aria-controls={listId} aria-autocomplete="list"
          aria-activedescendant={open && items[active] ? `${listId}-${items[active].key}` : undefined}
          value={query} onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => { setOpen(true); setWantCatalog(true); }} onKeyDown={onKeyDown} />
        {mobileOpen && <button type="button" className="icon-btn icon-btn--sm" aria-label="Close search" onClick={close}><CloseIcon size={14} /></button>}
      </div>
      {open && (
        <div className="search__list" id={listId} role="listbox" aria-label={S.search.label}>
          {items.length === 0 && <p className="search__none">{S.search.none}</p>}
          {items.map((it, i) => {
            const head = it.group !== lastGroup ? it.group : null;
            lastGroup = it.group;
            return (
              <div key={it.key}>
                {head && <p className="search__group" role="presentation">{head}</p>}
                <div id={`${listId}-${it.key}`} role="option" aria-selected={i === active} className={`search__item${i === active ? ' is-active' : ''}`}
                  onMouseEnter={() => setActive(i)} onMouseDown={(e) => { e.preventDefault(); choose(it); }}>
                  <span>{it.label}</span>
                  {it.meta && <span className="search__meta">{it.meta}</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
