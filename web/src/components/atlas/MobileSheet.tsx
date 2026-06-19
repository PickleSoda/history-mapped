import { Drawer } from 'vaul';
import { SheetContent } from '@/components/atlas/SheetContent';
import { useSheet } from '@/hooks';
import { heightToSnap, SNAP_POINTS, snapToHeight } from '@/lib/sheet';

/**
 * Persistent, non-modal bottom sheet (peek/half/full). Replaces the desktop
 * sidebar + right panel below `md`. Height is the shared `sheet` ephemeral
 * state; vaul's active snap point is bound two-way to it.
 */
export function MobileSheet() {
  const { sheet, setSheet } = useSheet();
  return (
    <Drawer.Root
      open
      modal={false}
      dismissible={false}
      snapPoints={[...SNAP_POINTS]}
      activeSnapPoint={heightToSnap(sheet)}
      setActiveSnapPoint={(snap) =>
        setSheet(snapToHeight(snap as number | string | null))
      }
    >
      <Drawer.Portal>
        <Drawer.Content
          aria-describedby={undefined}
          className="fixed inset-x-0 bottom-0 z-20 flex h-full max-h-[97%] flex-col rounded-t-2xl border bg-card p-3 outline-none"
        >
          <div
            aria-hidden
            className="mx-auto mb-2 h-1.5 w-10 flex-none rounded-full bg-border"
          />
          <Drawer.Title className="sr-only">Atlas browser</Drawer.Title>
          <div className="min-h-0 flex-1">
            <SheetContent />
          </div>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
