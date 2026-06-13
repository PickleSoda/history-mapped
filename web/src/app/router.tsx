import { Route, Routes } from 'react-router-dom';
import { AtlasLayout } from './routes/AtlasLayout';
import { BrowsePanel } from './routes/BrowsePanel';
import { ChronicleIndex } from './routes/ChronicleIndex';
import { ChroniclePlayer } from './routes/ChroniclePlayer';

/**
 * Route tree (spec §7). The map is the persistent layout; children swap only
 * the side panel. Selection (?sel=), search (?q=), filters (?g=), time (?t=),
 * bbox, and view are search params layered on ANY route — not routes.
 */
export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AtlasLayout />}>
        <Route index element={<BrowsePanel />} />
        <Route path="chronicles" element={<ChronicleIndex />} />
        <Route path="chronicles/:cid" element={<ChroniclePlayer />} />
      </Route>
    </Routes>
  );
}
