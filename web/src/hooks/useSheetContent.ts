import { useChronicleNav, useSelection, useStoryNav, useTalkDock } from '@/hooks';
import type { SheetContentKind } from '@/lib/sheet';
import { sheetContentKind } from '@/lib/sheet';

/** Reactive sheet content kind from selection + chronicle/battle-map URL state. */
export function useSheetContent(): SheetContentKind {
  const { isActive } = useChronicleNav();
  const { isActive: storyActive } = useStoryNav();
  const { sel } = useSelection();
  const { talkWith } = useTalkDock();
  return sheetContentKind({
    chronicleActive: isActive,
    hasSelection: sel != null,
    storyActive,
    talkActive: talkWith != null,
  });
}
