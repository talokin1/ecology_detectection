/**
 * The AI assistant drawer (R-13, ADR-009). It sends the visitor's question and the ids of the
 * analysis on screen to our assistant service; the service grounds Google Gemini on the same
 * precomputed JSON this app shows. Every reply is labelled as AI-generated.
 * Hidden unless VITE_ASSISTANT_URL is set at build time, so the app works without it.
 */
import { lazy, Suspense, useEffect, useRef, useState, type FormEvent, type MouseEvent } from 'react';
import { Link } from 'react-router-dom';
import type { Context } from './Shell';
import { CloseIcon } from './Icons';
import { AssistantMarkdown } from './AssistantMarkdown';
import type { AssistantChartData } from './AssistantChart';
import { S } from '../strings/en';

const AssistantChart = lazy(() => import('./AssistantChart').then((m) => ({ default: m.AssistantChart })));

const URL_BASE = (import.meta.env.VITE_ASSISTANT_URL as string | undefined)?.replace(/\/+$/, '') ?? '';
export const assistantEnabled = URL_BASE !== '';

type Suggestion = { variable_id: string; region_id: string; variable_name: string; region_name: string; why: string; verdict: string | null; href: string };
type LookedUp = { tool: string; label: string; href: string | null };
type WebSource = { title: string; uri: string; domain?: string | null };
type Reply = {
  answer: string; suggestions: Suggestion[]; looked_up?: LookedUp[]; web_sources?: WebSource[];
  search_suggestions_html?: string | null; unverified_numbers: string[]; model: string; disclaimer: string;
  language?: string; chart?: AssistantChartData | null;
};
type Msg = { role: 'user'; text: string } | { role: 'assistant'; text: string; reply?: Reply; error?: boolean };

const HISTORY_TURNS = 6;
const STORE = 'td-assistant-chat';
const KEEP = 20;

function loadChat(): Msg[] {
  try {
    const raw = sessionStorage.getItem(STORE);
    const v = raw ? (JSON.parse(raw) as unknown) : [];
    return Array.isArray(v) ? (v as Msg[]).slice(-KEEP) : [];
  } catch {
    return [];
  }
}

function saveChat(msgs: Msg[]) {
  try {
    if (msgs.length) sessionStorage.setItem(STORE, JSON.stringify(msgs.slice(-KEEP)));
    else sessionStorage.removeItem(STORE);
  } catch {
    /* storage may be blocked */
  }
}

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
  const [msgs, setMsgs] = useState<Msg[]>(loadChat);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLTextAreaElement>(null);
  const log = useRef<HTMLDivElement>(null);
  const abort = useRef<AbortController | null>(null);

  const onScreen = context?.regionId && context?.variableId ? `${context.variable} · ${context.region}` : null;
  const starters = context?.regionId && context?.variableId && context.variable && context.region
    ? S.assistant.starters.onScreen(context.variable, context.region)
    : S.assistant.starters.general;

  useEffect(() => {
    if (open) input.current?.focus();
  }, [open]);
  useEffect(() => {
    const el = log.current;
    if (!el) return;
    const last = msgs[msgs.length - 1];
    if (!busy && last?.role === 'assistant') {
      // a new answer: show its beginning, not its end
      const node = el.querySelector<HTMLElement>('.ai-msg:last-of-type');
      if (node) el.scrollTop = node.offsetTop - el.offsetTop - 8;
    } else {
      el.scrollTop = el.scrollHeight;
    }
  }, [msgs, busy]);
  useEffect(() => () => abort.current?.abort(), []);
  useEffect(() => saveChat(msgs), [msgs]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  const send = async (q: string, retry = false) => {
    const question = q.trim();
    if (!question || busy) return;
    // a retry replaces the failed answer and resends the same question
    const base = retry ? msgs.slice(0, -2) : msgs;
    const history = base;
    if (retry) setMsgs(base);
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

  const lastQuestion = [...msgs].reverse().find((m) => m.role === 'user')?.text ?? '';
  const newChat = () => {
    abort.current?.abort();
    setBusy(false);
    setMsgs([]);
    input.current?.focus();
  };
  // on narrow screens, following a link inside an answer closes the drawer so the page is visible
  const onLogClick = (e: MouseEvent) => {
    const a = (e.target as HTMLElement).closest('a');
    if (a && a.getAttribute('href')?.startsWith('#/') && window.innerWidth < 720) setOpen(false);
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    void send(text);
  };

  // The opener lives in the top bar (never over the map); the drawer is a fixed overlay.
  const opener = (
    <button type="button" className="btn btn--quiet ai-open" onClick={() => setOpen((o) => !o)}
      aria-haspopup="dialog" aria-expanded={open} aria-label={S.assistant.open} title={S.assistant.open}>
      <span className="ai-badge" aria-hidden="true">AI</span>
      <span className="ai-open__text" aria-hidden="true">{S.assistant.openShort}</span>
    </button>
  );
  if (!open) return opener;

  return (
    <>
    {opener}
    <aside className="ai-drawer" role="dialog" aria-label={S.assistant.title}>
      <header className="ai-drawer__head">
        <div>
          <div className="ai-drawer__title"><span className="ai-badge">AI</span> {S.assistant.title}</div>
          <div className="ai-drawer__sub">{onScreen ? S.assistant.about(onScreen) : S.assistant.aboutNone}</div>
        </div>
        <div className="ai-drawer__actions">
          {msgs.length > 0 && (
            <button type="button" className="btn btn--quiet" onClick={newChat}>{S.assistant.newChat}</button>
          )}
          <button type="button" className="btn btn--quiet" onClick={() => setOpen(false)} aria-label={S.assistant.close}>
            <CloseIcon />
          </button>
        </div>
      </header>

      <div className="ai-drawer__log" ref={log} aria-live="polite" onClick={onLogClick}>
        {msgs.length === 0 && (
          <div className="ai-empty">
            <p>{S.assistant.intro}</p>
            <div className="ai-chips">
              {starters.map((s) => (
                <button key={s} type="button" className="btn ai-chip" onClick={() => void send(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`ai-msg ai-msg--${m.role}${'error' in m && m.error ? ' ai-msg--error' : ''}`}>
            {m.role === 'assistant' && !('error' in m && m.error)
              ? <AssistantMarkdown text={m.text} />
              : <p className="ai-msg__text">{m.text}</p>}
            {m.role === 'assistant' && 'error' in m && m.error && i === msgs.length - 1 && lastQuestion && (
              <button type="button" className="btn ai-chip" onClick={() => void send(lastQuestion, true)}>{S.assistant.retry}</button>
            )}
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
    </>
  );
}

function ReplyExtras({ reply }: { reply: Reply }) {
  const nSources = (reply.looked_up?.length ?? 0) + (reply.web_sources?.length ?? 0);
  return (
    <>
      {reply.chart && (
        <Suspense fallback={<div className="ai-chart ai-chart--loading" />}>
          <AssistantChart chart={reply.chart} />
        </Suspense>
      )}
      {reply.suggestions.length > 0 && <div className="ai-sources__title ai-next">{S.assistant.exploreNext}</div>}
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
      {nSources > 0 && (
      <details className="ai-details">
        <summary>{S.assistant.sources(nSources)}</summary>
      {reply.looked_up && reply.looked_up.length > 0 && (
        <div className="ai-sources">
          <span className="ai-sources__title">{S.assistant.lookedUp}</span>
          <ul>
            {reply.looked_up.map((l) => (
              <li key={l.label}>{l.href ? <Link to={l.href.replace(/^#/, '')}>{l.label}</Link> : l.label}</li>
            ))}
          </ul>
        </div>
      )}
      {reply.web_sources && reply.web_sources.length > 0 && (
        <div className="ai-sources ai-sources--web">
          <span className="ai-sources__title">{S.assistant.webSources}</span>
          <ul>
            {reply.web_sources.map((w) => (
              <li key={w.uri}><a href={w.uri} target="_blank" rel="noopener noreferrer">{w.title}</a></li>
            ))}
          </ul>
        </div>
      )}
      </details>
      )}
      {reply.search_suggestions_html && <SearchSuggestions html={reply.search_suggestions_html} />}
      {reply.unverified_numbers.length > 0 && (
        <p className="ai-warn" role="note">{S.assistant.unverified(reply.unverified_numbers.join(', '))}</p>
      )}
      <p className="ai-msg__label">{S.assistant.label(reply.model)}</p>
    </>
  );
}

/**
 * Google's Search Suggestions, shown unmodified as Google requires for grounded answers. They are
 * isolated in a sandboxed frame (no scripts, no access to this page); a <base> tag makes their
 * links open in a new tab.
 */
function SearchSuggestions({ html }: { html: string }) {
  return (
    <iframe
      className="ai-suggestions-frame"
      title={S.assistant.searchSuggestions}
      sandbox="allow-popups allow-popups-to-escape-sandbox"
      srcDoc={`<!doctype html><base target="_blank">${html}`}
    />
  );
}
