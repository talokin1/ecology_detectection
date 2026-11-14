import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useEscape } from './Panel';
import { CloseIcon } from './Icons';
import { S } from '../strings/en';

/** Which element each tour step points at (data-tour attributes). */
export const TOUR_TARGETS = ['variable', 'legend', 'quicklook', 'regionspanel'];

/**
 * A four-step guided tour (production UX plan B1). It never starts by itself; the page performs
 * each step's action (e.g. opening a region) and this card explains what the visitor sees.
 */
export function Tour({ step, onNext, onBack, onClose }: { step: number; onNext: () => void; onBack: () => void; onClose: () => void }) {
  const card = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const n = S.tour.steps.length;
  const s = S.tour.steps[step];
  useEscape(true, onClose);

  // highlight the target and place the card next to it, inside the viewport
  useLayoutEffect(() => {
    let raf = 0;
    let tries = 0;
    const place = () => {
      const target = document.querySelector<HTMLElement>(`[data-tour="${TOUR_TARGETS[step]}"]`);
      const c = card.current;
      if (!target || !c) {
        if (tries++ < 40) raf = requestAnimationFrame(place);
        return;
      }
      document.querySelectorAll('.is-tour-target').forEach((e) => e.classList.remove('is-tour-target'));
      target.classList.add('is-tour-target');
      const t = target.getBoundingClientRect();
      const w = c.offsetWidth;
      const h = c.offsetHeight;
      let top: number;
      let left: number;
      if (t.height > 240 && t.left > w + 28) {
        // a tall panel on the right: put the card beside it
        top = t.top + 48;
        left = t.left - w - 16;
      } else {
        top = t.bottom + 12 + h < innerHeight ? t.bottom + 12 : t.top - h - 12;
        left = t.left;
      }
      setPos({ top: Math.max(12, Math.min(top, innerHeight - h - 12)), left: Math.max(12, Math.min(left, innerWidth - w - 12)) });
    };
    raf = requestAnimationFrame(place);
    return () => cancelAnimationFrame(raf);
  }, [step]);
  useEffect(() => () => document.querySelectorAll('.is-tour-target').forEach((e) => e.classList.remove('is-tour-target')), []);
  useEffect(() => {
    card.current?.querySelector<HTMLElement>('[data-autofocus]')?.focus();
  }, [step]);

  return (
    <div ref={card} className="tour" role="dialog" aria-modal="false" aria-label={`${S.tour.stepOf(step + 1, n)}: ${s.title}`}
      style={pos ? { top: pos.top, left: pos.left } : { visibility: 'hidden' }}>
      <div className="tour__head">
        <span className="tour__step">{S.tour.stepOf(step + 1, n)}</span>
        <button type="button" className="icon-btn icon-btn--sm" aria-label={S.tour.skip} onClick={onClose}><CloseIcon size={14} /></button>
      </div>
      <p className="tour__title">{s.title}</p>
      <p className="tour__text">{s.text}</p>
      <div className="tour__actions">
        {step > 0 && <button type="button" className="btn" onClick={onBack}>{S.tour.back}</button>}
        <button type="button" className="btn btn--primary" data-autofocus onClick={step === n - 1 ? onClose : onNext}>{step === n - 1 ? S.tour.done : S.tour.next}</button>
      </div>
    </div>
  );
}
