/**
 * The AI assistant drawer (R-13, ADR-009). It sends the visitor's question and the ids of the
 * analysis on screen to our assistant service; the service grounds Google Gemini on the same
 * precomputed JSON this app shows. Every reply is labelled as AI-generated.
 * Hidden unless VITE_ASSISTANT_URL is set at build time, so the app works without it.
 */
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import type { Context } from './Shell';
import { CloseIcon } from './Icons';
import { S } from '../strings/en';

const URL_BASE = (import.meta.env.VITE_ASSISTANT_URL as string | undefined)?.replace(/\/+$/, '') ?? '';
export const assistantEnabled = URL_BASE !== '';

type Suggestion = { variable_id: string; region_id: string; variable_name: string; region_name: string; why: string; verdict: string | null; href: string };
type Reply = { answer: string; suggestions: Suggestion[]; unverified_numbers: string[]; model: string; disclaimer: string };
type Msg = { role: 'user'; text: string } | { role: 'assistant'; text: string; reply?: Reply; error?: boolean };

const HISTORY_TURNS = 6;

export async function askAssistant(message: string, context: Context, history: Msg[], signal?: AbortSignal): Promise<Reply> {
  const r = await fetch(`${URL_BASE}/v1/chat`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    signal,
    body: JSON.stringify({
      message,
      region_id: context?.regionId ?? null,
      variable_id: context?.variableId ?? null,
      history: history.filter((m) => !('error' in m && m.error)).slice(-HISTORY_TURNS)
        .map((m) => ({ role: m.role, text: m.text.slice(0, 2000) })),
    }),
  });
  if (!r.ok) {
    let detail = '';
    try {
      detail = ((await r.json()) as { detail?: unknown }).detail as string;
    } catch {
      /* not JSON */
    }
    throw new Error(typeof detail === 'string' && detail ? detail : S.assistant.failed);
  }
  return (await r.json()) as Reply;
}

export function Assistant({ context }: { context: Context }) {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLTextAreaElement>(null);
  const log = useRef<HTMLDivElement>(null);
  const abort = useRef<AbortController | null>(null);

  const onScreen = context?.regionId && context?.variableId ? `${context.variable} · ${context.region}` : null;

  useEffect(() => {
    if (open) input.current?.focus();
  }, [open]);
  useEffect(() => {
    if (log.current) log.current.scrollTop = log.current.scrollHeight;
  }, [msgs, busy]);
  useEffect(() => () => abort.current?.abort(), []);

  const send = async (q: string) => {
    const question = q.trim();
    if (!question || busy) return;
    const history = msgs;
    setMsgs((m) => [...m, { role: 'user', text: question }]);
    setText('');
    setBusy(true);
    abort.current = new AbortController();
    try {
      const reply = await askAssistant(question, context, history, abort.current.signal);
      setMsgs((m) => [...m, { role: 'assistant', text: reply.answer, reply }]);
    } catch (e) {
      if ((e as Error).name === 'AbortError') return;
      setMsgs((m) => [...m, { role: 'assistant', text: (e as Error).message || S.assistant.failed, error: true }]);
    } finally {
      setBusy(false);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    void send(text);
  };

  if (!open) {
    return (
      <button type="button" className="ai-fab btn btn--primary" onClick={() => setOpen(true)} aria-haspopup="dialog">
        <span className="ai-badge" aria-hidden="true">AI</span> {S.assistant.open}
      </button>
    );
  }

  return (
    <aside className="ai-drawer" role="dialog" aria-label={S.assistant.title}>
      <header className="ai-drawer__head">
        <div>
          <div className="ai-drawer__title"><span className="ai-badge">AI</span> {S.assistant.title}</div>
          <div className="ai-drawer__sub">{onScreen ? S.assistant.about(onScreen) : S.assistant.aboutNone}</div>
        </div>
        <button type="button" className="btn btn--quiet" onClick={() => setOpen(false)} aria-label={S.assistant.close}>
          <CloseIcon />
        </button>
      </header>

      <div className="ai-drawer__log" ref={log} aria-live="polite">
        {msgs.length === 0 && (
          <div className="ai-empty">
            <p>{S.assistant.intro}</p>
            <div className="ai-chips">
              {(onScreen ? S.assistant.starters.onScreen : S.assistant.starters.general).map((s) => (
                <button key={s} type="button" className="btn ai-chip" onClick={() => void send(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`ai-msg ai-msg--${m.role}${'error' in m && m.error ? ' ai-msg--error' : ''}`}>
            <p className="ai-msg__text">{m.text}</p>
            {m.role === 'assistant' && m.reply && <ReplyExtras reply={m.reply} />}
          </div>
        ))}
        {busy && <div className="ai-msg ai-msg--assistant"><span className="spinner" aria-hidden="true" />{S.assistant.thinking}</div>}
      </div>

      <form className="ai-drawer__form" onSubmit={submit}>
        <textarea
          ref={input} value={text} maxLength={600} rows={2} placeholder={S.assistant.placeholder}
          aria-label={S.assistant.placeholder} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              void send(text);
            }
          }}
        />
        <button type="submit" className="btn btn--primary" disabled={busy || !text.trim()}>{S.assistant.send}</button>
      </form>
      <p className="ai-drawer__note">{S.assistant.note}</p>
    </aside>
  );
}

function ReplyExtras({ reply }: { reply: Reply }) {
  return (
    <>
      {reply.suggestions.length > 0 && (
        <ul className="ai-suggest">
          {reply.suggestions.map((s) => (
            <li key={`${s.region_id}-${s.variable_id}`}>
              <Link to={s.href.replace(/^#/, '')}>{s.variable_name} · {s.region_name} →</Link>
              {s.verdict && <span className="ai-suggest__verdict">{s.verdict}</span>}
              <span className="ai-suggest__why">{s.why}</span>
            </li>
          ))}
        </ul>
      )}
      {reply.unverified_numbers.length > 0 && (
        <p className="ai-warn" role="note">{S.assistant.unverified(reply.unverified_numbers.join(', '))}</p>
      )}
      <p className="ai-msg__label">{S.assistant.label(reply.model)}</p>
    </>
  );
}
