import { Route, Routes } from 'react-router-dom';
import { AtlasLayout } from './routes/AtlasLayout';

/**
 * Route tree. The Atlas is a single persistent shell; browse, chronicles,
 * selection, search, time, and bbox are all expressed as in-shell state /
 * search params rather than separate routes.
 */
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<AtlasLayout />} />
    </Routes>
  );
}
