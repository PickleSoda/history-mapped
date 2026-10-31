import { useChronicleNav, useSelection, useStoryNav } from '@/hooks';
import type { SheetContentKind } from '@/lib/sheet';
import { sheetContentKind } from '@/lib/sheet';

/** Reactive sheet content kind from selection + chronicle/battle-map URL state. */
export function useSheetContent(): SheetContentKind {
  const { isActive } = useChronicleNav();
  const { isActive: storyActive } = useStoryNav();
  const { sel } = useSelection();
  return sheetContentKind({ chronicleActive: isActive, hasSelection: sel != null, storyActive });
}
