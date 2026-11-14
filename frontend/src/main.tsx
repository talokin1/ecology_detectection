import { StrictMode, Suspense, lazy } from 'react';
import { createRoot } from 'react-dom/client';
import { createHashRouter, RouterProvider } from 'react-router-dom';
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import '@fontsource/inter/700.css';
import './theme/tokens.css';
import './styles.css';
import { initTheme } from './state/theme';
import { ErrorState, Loading, RouteError, Shell } from './components/Shell';
import { S } from './strings/en';

initTheme();
// a successful start clears the one-time reload guard used after deploys (see data/load.ts)
window.addEventListener('load', () => setTimeout(() => {
  try {
    sessionStorage.removeItem('td-reloaded-for-contract');
  } catch {
    /* storage may be blocked */
  }
}, 5000));

const MapPage = lazy(() => import('./pages/MapPage').then((m) => ({ default: m.MapPage })));
const CaseRoute = lazy(() => import('./pages/CasePage').then((m) => ({ default: m.CaseRoute })));
const RegionRoute = lazy(() => import('./pages/CasePage').then((m) => ({ default: m.RegionRoute })));
const CompareRoute = lazy(() => import('./pages/ComparePage').then((m) => ({ default: m.CompareRoute })));
const CatalogPage = lazy(() => import('./pages/CatalogPage').then((m) => ({ default: m.CatalogPage })));
const MethodsPage = lazy(() => import('./pages/MethodsPage').then((m) => ({ default: m.MethodsPage })));

const wrap = (el: JSX.Element) => <Suspense fallback={<Loading />}>{el}</Suspense>;

const router = createHashRouter([
  {
    path: '/',
    element: <Shell />,
    errorElement: <ErrorState>{S.errors.notFound}</ErrorState>,
    children: [
      { index: true, element: wrap(<MapPage />), errorElement: <RouteError /> },
      { path: 'case/:id', element: wrap(<CaseRoute />), errorElement: <RouteError /> },
      { path: 'region/:rid', element: wrap(<RegionRoute />), errorElement: <RouteError /> },
      { path: 'compare/:a/:b', element: wrap(<CompareRoute />), errorElement: <RouteError /> },
      { path: 'catalog', element: wrap(<CatalogPage />), errorElement: <RouteError /> },
      { path: 'methods', element: wrap(<MethodsPage />), errorElement: <RouteError /> },
      { path: '*', element: <ErrorState>{S.errors.notFound}</ErrorState> },
    ],
  },
]);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
