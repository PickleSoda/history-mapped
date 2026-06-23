import { ChroniclePlayer } from '@/components/atlas/ChroniclePlayer';
import { CommandPalette } from '@/components/atlas/CommandPalette';
import { DetailPanel } from '@/components/atlas/DetailPanel';
import { LeftSidebar } from '@/components/atlas/LeftSidebar';
import { TimelineScope } from '@/components/atlas/TimelineScope';
import { TopBar } from '@/components/atlas/TopBar';
import { MapCanvas } from '@/components/map/MapCanvas';
import { useChronicleNav } from '@/hooks';

/**
 * While a chronicle is active the tour takes the left rail (in place of the
 * list); the right panel is always the entity detail. So the tour and an entity
 * you drill into from it can be read side by side, instead of one replacing the
 * other.
 */
function LeftPanel() {
  const { isActive } = useChronicleNav();
  return isActive ? <ChroniclePlayer /> : <LeftSidebar />;
}

/**
 * The persistent desktop shell (spec §7). The map fills the whole body and never
 * resizes — the sidebars are OVERLAID on top of it (rather than shrinking it),
 * so collapsing/opening a panel doesn't trigger a map re-render. The viewport
 * bbox therefore extends under the panels, which is acceptable.
 */
export function DesktopShell() {
  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-background text-foreground">
      <TopBar />

      <div className="relative min-h-0 flex-1 overflow-hidden">
        {/* Full-bleed persistent map */}
        <MapCanvas />

        {/* Sidebars float over the map */}
        <div className="absolute inset-y-0 left-0 z-10">
          <LeftPanel />
        </div>
        <div className="absolute inset-y-0 right-0 z-10">
          <DetailPanel />
        </div>
      </div>

      {/* Timeline spine */}
      <div className="flex-none border-t bg-card">
        <TimelineScope />
      </div>

      <CommandPalette />
    </div>
  );
}
