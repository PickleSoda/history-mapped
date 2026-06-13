import { Outlet } from 'react-router-dom';
import { DetailPanel } from '@/components/atlas/DetailPanel';
import { Timeline } from '@/components/atlas/Timeline';
import { TopBar } from '@/components/atlas/TopBar';
import { MapCanvas } from '@/components/map/MapCanvas';

/**
 * The persistent shell (spec §7). The map mounts here once and never unmounts;
 * child routes swap only the right-side aside via <Outlet/>. The top bar and
 * the timeline spine frame the map.
 */
export function AtlasLayout() {
  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-background text-foreground">
      <TopBar />

      <div className="flex min-h-0 flex-1">
        {/* Persistent map */}
        <main className="relative min-w-0 flex-1">
          <MapCanvas />
        </main>

        {/* Side panel — child route content, with the selection overlay on top */}
        <aside className="relative w-[360px] max-w-[90vw] flex-none border-l bg-card">
          <div className="h-full overflow-y-auto">
            <Outlet />
          </div>
          <DetailPanel />
        </aside>
      </div>

      {/* Timeline spine */}
      <div className="h-14 flex-none border-t bg-card">
        <Timeline />
      </div>
    </div>
  );
}
