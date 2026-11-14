import type { Case } from '../data/types.gen';
import { CloseIcon } from './Icons';
import { S } from '../strings/en';

/**
 * Our prepared questions appear one at a time as a suggestion (production UX plan A7), never as a
 * numbered list. Clicking the question opens its answer; "Next" shows another; the cross hides
 * all suggestions (the "Ideas" button brings them back).
 */
export function HintChip({ hint, onTry, onNext, onDismiss, offerTour, onTour }: {
  hint: Case; onTry: () => void; onNext: () => void; onDismiss: () => void; offerTour: boolean; onTour: () => void;
}) {
  return (
    <aside className="hint" aria-label={S.hints.label}>
      <span className="hint__try">{S.hints.try}</span>
      <button type="button" className="hint__q" onClick={onTry}>{hint.question}</button>
      <button type="button" className="hint__next" onClick={onNext} aria-label={S.hints.next}>Next</button>
      <button type="button" className="icon-btn icon-btn--sm" aria-label={S.hints.dismiss} onClick={onDismiss}><CloseIcon size={14} /></button>
      {offerTour && <button type="button" className="hint__tour" onClick={onTour}>{S.hints.tour}</button>}
    </aside>
  );
}
