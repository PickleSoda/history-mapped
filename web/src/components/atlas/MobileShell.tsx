import { CommandPalette } from '@/components/atlas/CommandPalette';
import { MobileSheet } from '@/components/atlas/MobileSheet';
import { MobileTopBar } from '@/components/atlas/MobileTopBar';
import { TimelineScope } from '@/components/atlas/TimelineScope';
import { MapCanvas } from '@/components/map/MapCanvas';
import { useSheetSelectionSync } from '@/hooks';

/**
 * Touch shell (≤ md). A compact top bar, a full-bleed map with the collapsible
 * timeline floating over its top edge, and a persistent bottom sheet that
 * replaces both desktop asides (browse list ↔ entity detail / chronicle tour).
 */
export function MobileShell() {
  useSheetSelectionSync();
  return (
    <div className="flex h-dvh w-screen flex-col overflow-hidden bg-background text-foreground">
      <MobileTopBar />
      <div className="relative min-h-0 flex-1 overflow-hidden">
        <MapCanvas />
        <div className="pointer-events-none absolute inset-x-0 top-0 z-10 p-2">
          <div className="pointer-events-auto overflow-hidden rounded-xl border bg-card/95 shadow-sm backdrop-blur">
            <TimelineScope />
          </div>
        </div>
      </div>
      <MobileSheet />
      <CommandPalette />
    </div>
  );
}
