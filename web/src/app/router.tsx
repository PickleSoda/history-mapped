import { lazy } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { legacyAtlasRedirect } from '@/lib/legacy-redirect';
import { AccountLayout } from './routes/AccountLayout';
import { AtlasLayout } from './routes/AtlasLayout';
import { SiteLayout } from './routes/site/SiteLayout';

// Account pages load on first visit, keeping them out of the atlas entry chunk.
const LoginPage = lazy(() => import('./routes/LoginPage').then((m) => ({ default: m.LoginPage })));
const RegisterPage = lazy(() => import('./routes/RegisterPage').then((m) => ({ default: m.RegisterPage })));
const SavedPage = lazy(() => import('./routes/SavedPage').then((m) => ({ default: m.SavedPage })));
const ContributionsPage = lazy(() =>
  import('./routes/ContributionsPage').then((m) => ({ default: m.ContributionsPage })),
);

// Public site (track B)
const LandingPage = lazy(() => import('./routes/site/LandingPage').then((m) => ({ default: m.LandingPage })));
const NotFoundPage = lazy(() => import('./routes/site/NotFoundPage').then((m) => ({ default: m.NotFoundPage })));
const EntityRoute = lazy(() => import('./routes/site/EntityRoute').then((m) => ({ default: m.EntityRoute })));
const ChronicleRoute = lazy(() =>
  import('./routes/site/ChronicleRoute').then((m) => ({ default: m.ChronicleRoute })),
);

// Browse (track D)
const BrowseIndexPage = lazy(() =>
  import('./routes/browse/BrowseIndexPage').then((m) => ({ default: m.BrowseIndexPage })),
);
const BrowseFacetPage = lazy(() =>
  import('./routes/browse/BrowseFacetPage').then((m) => ({ default: m.BrowseFacetPage })),
);
const CollectionPage = lazy(() =>
  import('./routes/browse/CollectionPage').then((m) => ({ default: m.CollectionPage })),
);
const StoriesPage = lazy(() => import('./routes/browse/StoriesPage').then((m) => ({ default: m.StoriesPage })));

// Docs (track C)
const DocsLayout = lazy(() => import('./routes/docs/DocsLayout').then((m) => ({ default: m.DocsLayout })));
const DocPage = lazy(() => import('./routes/docs/DocPage').then((m) => ({ default: m.DocPage })));

/**
 * `/` is the landing page. A query string on `/` is a link made when the
 * atlas lived there (`/?sel=…`, `/?chron=…`, `/?story=…`): send it to `/app`
 * with the same query so shared links keep working (spec D1,
 * `lib/legacy-redirect.ts`).
 */
function IndexRoute() {
  const location = useLocation();
  const target = legacyAtlasRedirect(location);
  if (target) return <Navigate to={target} replace />;
  return <LandingPage />;
}

/**
 * Route tree (spec 2026-11-01 public site, D1). The atlas is one persistent
 * shell at `/app`; browse, chronicles, selection, search, time and bbox are
 * in-shell state / search params rather than routes. The account pages sit
 * under their own layout, everything else under the site frame. The site's
 * entity and chronicle pages are the atlas's pages in site link mode
 * (`components/atlas/link-mode.tsx`).
 */
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/app" element={<AtlasLayout />} />
      <Route element={<AccountLayout />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/saved" element={<SavedPage />} />
        <Route path="/contributions" element={<ContributionsPage />} />
      </Route>
      <Route element={<SiteLayout />}>
        <Route index element={<IndexRoute />} />
        <Route path="/browse" element={<BrowseIndexPage />} />
        <Route path="/browse/stories" element={<StoriesPage />} />
        <Route path="/browse/collections/:slug" element={<CollectionPage />} />
        <Route path="/browse/:facet/:tag" element={<BrowseFacetPage />} />
        <Route path="/entities/:id" element={<EntityRoute />} />
        <Route path="/chronicles/:slug" element={<ChronicleRoute />} />
        <Route path="/docs" element={<DocsLayout />}>
          <Route index element={<DocPage />} />
          <Route path=":slug" element={<DocPage />} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
