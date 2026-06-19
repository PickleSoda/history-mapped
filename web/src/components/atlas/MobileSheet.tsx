import { Drawer } from 'vaul';
import { SheetContent } from '@/components/atlas/SheetContent';
import { useSheet } from '@/hooks';
import { heightToSnap, SNAP_POINTS, snapToHeight } from '@/lib/sheet';

/**
 * Visible height of the sheet at the active snap, as a CSS length. vaul renders
 * a full-height drawer and reveals it from the top via transform, so a
 * bottom-pinned footer would sit below the viewport at any non-full snap.
 * Sizing the inner content to this height keeps its bottom edge on-screen.
 * Numeric snaps are viewport fractions; string snaps are absolute (e.g. px).
 */
function visibleHeightCss(snap: number | string): string {
  return typeof snap === 'number' ? `${snap * 100}dvh` : snap;
}

/**
 * Persistent, non-modal bottom sheet (peek/half/full). Replaces the desktop
 * sidebar + right panel below `md`. Height is the shared `sheet` ephemeral
 * state; vaul's active snap point is bound two-way to it.
 */
export function MobileSheet() {
  const { sheet, setSheet } = useSheet();
  const snap = heightToSnap(sheet);
  return (
    <Drawer.Root
      open
      modal={false}
      dismissible={false}
      snapPoints={[...SNAP_POINTS]}
      activeSnapPoint={snap}
      setActiveSnapPoint={(next) =>
        setSheet(snapToHeight(next as number | string | null))
      }
    >
      <Drawer.Portal>
        <Drawer.Content
          aria-describedby={undefined}
          className="fixed inset-x-0 bottom-0 z-20 flex h-[97dvh] flex-col rounded-t-2xl border bg-card outline-none"
        >
          {/* Occupy only the visible portion of the snapped sheet so a pinned
              footer (e.g. the chronicle Next-step bar) sits at the visible
              bottom edge instead of below the fold. */}
          <div
            className="flex min-h-0 flex-col p-3"
            style={{ height: visibleHeightCss(snap) }}
          >
            <div
              aria-hidden
              className="mx-auto mb-2 h-1.5 w-10 flex-none rounded-full bg-border"
            />
            <Drawer.Title className="sr-only">Atlas browser</Drawer.Title>
            <div className="min-h-0 flex-1">
              <SheetContent />
            </div>
          </div>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
