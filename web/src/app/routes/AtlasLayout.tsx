import { ChroniclePlayer } from '@/components/atlas/ChroniclePlayer';
import { CommandPalette } from '@/components/atlas/CommandPalette';
import { DetailPanel } from '@/components/atlas/DetailPanel';
import { LeftSidebar } from '@/components/atlas/LeftSidebar';
import { Timeline } from '@/components/atlas/Timeline';
import { TopBar } from '@/components/atlas/TopBar';
import { MapCanvas } from '@/components/map/MapCanvas';
import { useChronicleNav } from '@/hooks';

/** The right panel hosts the chronicle tour OR the entity detail — never both. */
function RightPanel() {
  const { isActive } = useChronicleNav();
  return isActive ? <ChroniclePlayer /> : <DetailPanel />;
}

/**
 * The persistent shell (spec §7). The map fills the whole body and never
 * resizes — the sidebars are OVERLAID on top of it (rather than shrinking it),
 * so collapsing/opening a panel doesn't trigger a map re-render. The viewport
 * bbox therefore extends under the panels, which is acceptable.
 */
export function AtlasLayout() {
  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-background text-foreground">
      <TopBar />

      <div className="relative min-h-0 flex-1 overflow-hidden">
        {/* Full-bleed persistent map */}
        <MapCanvas />

        {/* Sidebars float over the map */}
        <div className="absolute inset-y-0 left-0 z-10">
          <LeftSidebar />
        </div>
        <div className="absolute inset-y-0 right-0 z-10">
          <RightPanel />
        </div>
      </div>

      {/* Timeline spine */}
      <div className="h-14 flex-none border-t bg-card">
        <Timeline />
      </div>

      <CommandPalette />
    </div>
  );
}
