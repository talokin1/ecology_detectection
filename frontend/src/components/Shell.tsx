import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { Link, NavLink, Outlet } from 'react-router-dom';
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
    <button type="button" className="btn btn--ghost" aria-label={`Switch to ${next} theme`} onClick={() => setTheme(next)}>
      {theme === 'dark' ? S.theme.light : S.theme.dark}
    </button>
  );
}

export function Shell() {
  const [context, setContext] = useState<Context>(null);
  const index = useData(api.index, 'index');
  return (
    <Ctx.Provider value={setContext}>
      <header className="topbar">
        <Link to="/" className="wordmark" aria-label={`${S.appName}, home`}>
          <svg viewBox="0 0 32 32" width="22" height="22" aria-hidden="true">
            <rect width="32" height="32" rx="6" fill="currentColor" />
            <path d="M6 22 L12 17 L17 19 L26 9" stroke="var(--bg)" strokeWidth="2.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          {S.appName}
        </Link>
        <nav className="topbar__nav" aria-label="Main">
          <NavLink to="/" end>{S.nav.map}</NavLink>
          <NavLink to="/catalog">{S.nav.catalog}</NavLink>
          <NavLink to="/methods">{S.nav.methods}</NavLink>
        </nav>
        <div className="topbar__context" aria-live="polite">
          {context && (
            <>
              {context.variable && <span className="ctx__strong">{context.variable}</span>}
              {context.region && <span>{context.region}</span>}
              {context.period && <span>{context.period}</span>}
              {context.source && <span className="ctx__source">{context.source}</span>}
            </>
          )}
        </div>
        <div className="topbar__actions">
          <ShareButton />
          <ThemeButton />
        </div>
      </header>
      {index.data?.synthetic && (
        <div className="synthetic" role="note">
          <strong>Synthetic data.</strong> {S.synthetic.banner.replace('Demo data. ', '')}{' '}
          <Link to="/methods?s=data">{S.synthetic.more}</Link>
        </div>
      )}
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

export function Loading() {
  return <div className="state state--loading" aria-busy="true">{S.loading}</div>;
}
