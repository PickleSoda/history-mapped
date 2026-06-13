import { DetailPanel } from '@/components/atlas/DetailPanel';
import { LeftSidebar } from '@/components/atlas/LeftSidebar';
import { Timeline } from '@/components/atlas/Timeline';
import { TopBar } from '@/components/atlas/TopBar';
import { MapCanvas } from '@/components/map/MapCanvas';

/**
 * The persistent shell (spec §7). The map mounts once and never unmounts.
 * Left: the collapsible browse/chronicles sidebar. Right: the detail panel,
 * which only appears when an entity is selected (?sel=).
 */
export function AtlasLayout() {
  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-background text-foreground">
      <TopBar />

      <div className="flex min-h-0 flex-1">
        <LeftSidebar />

        {/* Persistent map */}
        <main className="relative min-w-0 flex-1">
          <MapCanvas />
        </main>

        {/* Detail — present only when an entity is selected */}
        <DetailPanel />
      </div>

      {/* Timeline spine */}
      <div className="h-14 flex-none border-t bg-card">
        <Timeline />
      </div>
    </div>
  );
}
