/**
 * Closable surfaces (production UX plan A1): side panels, popovers, menus and disclosures.
 * Every one has a visible close control, closes with Escape (topmost first) and returns focus to
 * whatever opened it.
 */
import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { CloseIcon, InfoIcon, MenuIcon } from './Icons';

// ---------------------------------------------------------------- Escape stack
const stack: { id: string; close: () => void }[] = [];
let listening = false;
function onKey(e: KeyboardEvent) {
  if (e.key !== 'Escape' || !stack.length) return;
  e.preventDefault();
  stack[stack.length - 1].close();
}
/** Registers a closable layer; the most recently opened one closes first on Escape. */
export function useEscape(active: boolean, close: () => void) {
  const id = useId();
  const latest = useRef(close);
  latest.current = close;
  useEffect(() => {
    if (!active) return;
    if (!listening) {
      window.addEventListener('keydown', onKey);
      listening = true;
    }
    const entry = { id, close: () => latest.current() };
    stack.push(entry);
    return () => {
      const i = stack.findIndex((s) => s.id === id);
      if (i >= 0) stack.splice(i, 1);
    };
  }, [active, id]);
}

/** Moves focus into a surface on open and back to the opener on close. */
function useFocusReturn(ref: React.RefObject<HTMLElement | null>, focusSelector = 'h2, h3, [data-autofocus]') {
  useLayoutEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    ref.current?.querySelector<HTMLElement>(focusSelector)?.focus({ preventScroll: true });
    return () => {
      if (opener && document.contains(opener)) opener.focus({ preventScroll: true });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}

// ---------------------------------------------------------------- side panel / bottom sheet
export function Panel({ title, kicker, onClose, children, className = '', tour }: {
  title: string; kicker?: string; onClose: () => void; children: ReactNode; className?: string; tour?: string;
}) {
  const ref = useRef<HTMLElement>(null);
  const titleId = useId();
  useEscape(true, onClose);
  useFocusReturn(ref);
  return (
    <section ref={ref} className={`panel-side ${className}`} role="dialog" aria-modal="false" aria-labelledby={titleId} data-tour={tour}>
      <header className="panel-side__head">
        <div>
          {kicker && <p className="panel-side__kicker">{kicker}</p>}
          <h2 id={titleId} tabIndex={-1} className="panel-side__title">{title}</h2>
        </div>
        <button type="button" className="icon-btn" aria-label={`Close: ${title}`} onClick={onClose}><CloseIcon /></button>
      </header>
      <div className="panel-side__body">{children}</div>
    </section>
  );
}

// ---------------------------------------------------------------- popover (info / help)
export function InfoPopover({ label, children, size = 'sm', icon = 'info' }: { label: string; children: ReactNode; size?: 'sm' | 'md'; icon?: 'info' | 'help' }) {
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLSpanElement>(null);
  const id = useId();
  useEscape(open, () => setOpen(false));
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => wrap.current && !wrap.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener('mousedown', away);
    return () => document.removeEventListener('mousedown', away);
  }, [open]);
  return (
    <span className="popover" ref={wrap}>
      <button type="button" className={`icon-btn icon-btn--${size}${icon === 'help' ? ' icon-btn--help' : ''}`} aria-label={label} aria-expanded={open} aria-controls={id} onClick={() => setOpen((o) => !o)}>
        {icon === 'help' ? <span aria-hidden="true">?</span> : <InfoIcon size={size === 'sm' ? 15 : 17} />}
      </button>
      {open && (
        <span id={id} role="note" className="popover__card">
          <span className="popover__body">{children}</span>
          <button type="button" className="icon-btn icon-btn--sm popover__close" aria-label="Close" onClick={() => setOpen(false)}><CloseIcon size={13} /></button>
        </span>
      )}
    </span>
  );
}

// ---------------------------------------------------------------- menu
export type MenuItem = { label: string; onSelect: () => void };
export function Menu({ label, items }: { label: string; items: MenuItem[] }) {
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const close = () => {
    setOpen(false);
    button.current?.focus();
  };
  useEscape(open, close);
  useEffect(() => {
    if (!open) return;
    wrap.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
    const away = (e: MouseEvent) => wrap.current && !wrap.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener('mousedown', away);
    return () => document.removeEventListener('mousedown', away);
  }, [open]);
  const onKeyDown = (e: React.KeyboardEvent) => {
    const items_ = [...(wrap.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [])];
    const i = items_.indexOf(document.activeElement as HTMLElement);
    if (e.key === 'ArrowDown') { e.preventDefault(); items_[(i + 1) % items_.length]?.focus(); }
    if (e.key === 'ArrowUp') { e.preventDefault(); items_[(i - 1 + items_.length) % items_.length]?.focus(); }
  };
  return (
    <div className="menu" ref={wrap} onKeyDown={onKeyDown}>
      <button ref={button} type="button" className="icon-btn" aria-label={label} aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <MenuIcon />
      </button>
      {open && (
        <div role="menu" className="menu__list" aria-label={label}>
          {items.map((it) => (
            <button key={it.label} type="button" role="menuitem" className="menu__item" onClick={() => { setOpen(false); it.onSelect(); }}>{it.label}</button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- disclosure
/** A collapsed section whose one-line summary is always visible (plan A11). */
export function Disclosure({ title, summary, children, defaultOpen = false }: { title: string; summary?: ReactNode; children: ReactNode; defaultOpen?: boolean }) {
  return (
    <details className="disclosure" open={defaultOpen}>
      <summary className="disclosure__summary">
        <span className="disclosure__title">{title}</span>
        {summary && <span className="disclosure__line">{summary}</span>}
      </summary>
      <div className="disclosure__body">{children}</div>
    </details>
  );
}
