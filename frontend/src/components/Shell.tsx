import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { Link, NavLink, Outlet, useNavigate, useRouteError } from 'react-router-dom';
import { copyLink } from '../lib/exporters';
import { setTheme, useTheme } from '../state/theme';
import { Menu } from './Panel';
import { Search } from './Search';
import { Assistant, assistantEnabled } from './Assistant';
import { S } from '../strings/en';

/** What is on screen. The ids (when an analysis is open) let the AI assistant explain it. */
export type Context = {
  variable?: string; region?: string; period?: string; source?: string; variableId?: string; regionId?: string;
} | null;
const Ctx = createContext<(c: Context) => void>(() => {});

/** Pages announce what is on screen; it becomes the document title (plan B6). */
export function useScreenContext(c: Context, deps: unknown[]) {
  const set = useContext(Ctx);
  useEffect(() => {
    set(c);
    return () => set(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
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


export function Shell() {
  const [context, setContext] = useState<Context>(null);
  const [toast, setToast] = useState<string | null>(null);
  const theme = useTheme();
  const navigate = useNavigate();

  useEffect(() => {
    const parts = [context?.region && context.region !== 'World' ? context.region : null, context?.variable].filter(Boolean);
    document.title = parts.length ? `${parts.join(' · ')} · ${S.appName}` : S.appName;
  }, [context]);

  const say = (t: string) => {
    setToast(t);
    setTimeout(() => setToast(null), 1800);
  };

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
        <div className="topbar__spacer" />
        <Search />
        {assistantEnabled && <Assistant context={context} />}
        <Menu label={S.shell.menu} items={[
          { label: S.share, onSelect: async () => { if (await copyLink()) say(S.shell.copied); } },
          { label: theme === 'dark' ? S.theme.light : S.theme.dark, onSelect: () => setTheme(theme === 'dark' ? 'light' : 'dark') },
          { label: S.shell.tour, onSelect: () => navigate('/?tour=1') },
          { label: S.shell.about, onSelect: () => navigate('/about') },
        ]} />
      </header>
      <main className="main">
        <Outlet />
      </main>
      <div className="toast" role="status" aria-live="polite">{toast}</div>
    </Ctx.Provider>
  );
}

export function ErrorState({ error, children }: { error?: Error; children?: ReactNode }) {
  return (
    <div className="state">
      <h2>{S.errors.title}</h2>
      <p>{children ?? S.errors.body}</p>
      {error && <p className="state__detail">{error.message}</p>}
      <div className="state__actions">
        {error && <button type="button" className="btn" onClick={() => window.location.reload()}>{S.errors.retry}</button>}
        <Link className="btn btn--primary" to="/">{S.errors.back}</Link>
      </div>
    </div>
  );
}

/** Route-level error boundary: a crash in one screen never blanks the whole app. */
export function RouteError() {
  const err = useRouteError();
  return <ErrorState error={err instanceof Error ? err : undefined} />;
}

export function Loading({ height }: { height?: number }) {
  return (
    <div className="state state--loading" style={height ? { minHeight: height } : undefined} aria-busy="true">
      <span className="spinner" aria-hidden="true" />
      <span>{S.loading}</span>
    </div>
  );
}
