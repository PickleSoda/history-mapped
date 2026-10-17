import { lazy } from 'react';
import { Route, Routes } from 'react-router-dom';
import { AccountLayout } from './routes/AccountLayout';
import { AtlasLayout } from './routes/AtlasLayout';

// Account pages load on first visit, keeping them out of the atlas entry chunk.
const LoginPage = lazy(() => import('./routes/LoginPage').then((m) => ({ default: m.LoginPage })));
const RegisterPage = lazy(() => import('./routes/RegisterPage').then((m) => ({ default: m.RegisterPage })));
const SavedPage = lazy(() => import('./routes/SavedPage').then((m) => ({ default: m.SavedPage })));
const ContributionsPage = lazy(() =>
  import('./routes/ContributionsPage').then((m) => ({ default: m.ContributionsPage })),
);

/**
 * Route tree. The Atlas is a single persistent shell; browse, chronicles,
 * selection, search, time, and bbox are all expressed as in-shell state /
 * search params rather than separate routes. The account pages (sign in,
 * saved items, contributions) sit outside it, under their own layout.
 */
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<AtlasLayout />} />
      <Route element={<AccountLayout />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/saved" element={<SavedPage />} />
        <Route path="/contributions" element={<ContributionsPage />} />
      </Route>
    </Routes>
  );
}
