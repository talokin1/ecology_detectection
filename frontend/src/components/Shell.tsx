import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { Link, NavLink, Outlet, useRouteError } from 'react-router-dom';
import { api } from '../data/load';
import { useData } from '../data/useData';
import { copyLink } from '../lib/exporters';
import { setTheme, useTheme } from '../state/theme';
import { S } from '../strings/en';

export type Context = { variable?: string; region?: string; period?: string; source?: string } | null;
const Ctx = createContext<(c: Context) => void>(() => {});

/** Pages announce what is on screen; the top bar shows it (variable · region · period · source). */
export function useScreenContext(c: Context, deps: unknown[]) {
  const set = useContext(Ctx);
  useEffect(() => {
    set(c);
    return () => set(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

function ShareButton() {
  const [done, setDone] = useState(false);
  return (
    <button type="button" className="btn btn--ghost" onClick={async () => {
      if (await copyLink()) {
        setDone(true);
        setTimeout(() => setDone(false), 1800);
      }
    }}>
      {done ? S.shared : S.share}
    </button>
  );
}

function ThemeButton() {
  const theme = useTheme();
  const next = theme === 'dark' ? 'light' : 'dark';
  return (
    <button type="button" className="btn btn--ghost" aria-label={S.theme.switchTo(next)} onClick={() => setTheme(next)}>
      {theme === 'dark' ? S.theme.light : S.theme.dark}
    </button>
  );
}

/** The logo is the evidence glyph: three rising segments. */
export function Logo() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" className="logo">
      <rect x="2" y="14" width="5.5" height="6" rx="1" fill="currentColor" />
      <rect x="9.25" y="9" width="5.5" height="11" rx="1" fill="currentColor" />
      <rect x="16.5" y="4" width="5.5" height="16" rx="1" fill="currentColor" />
    </svg>
  );
}

function ContextLine({ context }: { context: Context }) {
  if (!context) return null;
  return (
    <>
      {context.variable && <span className="ctx__strong">{context.variable}</span>}
      {context.region && <span>{context.region}</span>}
      {context.period && <span>{context.period}</span>}
      {context.source && <span className="ctx__source">{context.source}</span>}
    </>
  );
}

export function Shell() {
  const [context, setContext] = useState<Context>(null);
  const index = useData(api.index, 'index');
  return (
    <Ctx.Provider value={setContext}>
      <header className="topbar">
        <Link to="/" className="wordmark" aria-label={`${S.appName}, home`}>
          <Logo />
          <span className="wordmark__text">{S.appName}</span>
        </Link>
        <nav className="topbar__nav" aria-label="Main">
          <NavLink to="/" end>{S.nav.map}</NavLink>
          <NavLink to="/catalog">{S.nav.catalog}</NavLink>
          <NavLink to="/methods">{S.nav.methods}</NavLink>
        </nav>
        <div className="topbar__context" aria-live="polite"><ContextLine context={context} /></div>
        <div className="topbar__actions">
          <ShareButton />
          <ThemeButton />
        </div>
      </header>
      {index.data?.synthetic && (
        <div className="synthetic" role="note">
          <strong>{S.synthetic.strong}</strong> {S.synthetic.banner} <Link to="/methods?s=data">{S.synthetic.more}</Link>
        </div>
      )}
      {context && <div className="context-line" aria-hidden="true"><ContextLine context={context} /></div>}
      <main className="main">
        <Outlet />
      </main>
    </Ctx.Provider>
  );
}

export function ErrorState({ error, children }: { error?: Error; children?: ReactNode }) {
  return (
    <div className="state">
      <h2>{S.errors.title}</h2>
      <p>{children ?? S.errors.body}</p>
      {error && <p className="state__detail">{error.message}</p>}
      <Link className="btn" to="/">{S.errors.back}</Link>
    </div>
  );
}

/** Route-level error boundary: a crash in one screen never blanks the whole app. */
export function RouteError() {
  const err = useRouteError();
  return <ErrorState error={err instanceof Error ? err : undefined} />;
}

export function Loading({ height }: { height?: number }) {
  return <div className="state state--loading" style={height ? { minHeight: height } : undefined} aria-busy="true">{S.loading}</div>;
}
