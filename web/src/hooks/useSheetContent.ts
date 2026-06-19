import { useChronicleNav, useSelection } from '@/hooks';
import type { SheetContentKind } from '@/lib/sheet';
import { sheetContentKind } from '@/lib/sheet';

/** Reactive sheet content kind from selection + chronicle URL state. */
export function useSheetContent(): SheetContentKind {
  const { isActive } = useChronicleNav();
  const { sel } = useSelection();
  return sheetContentKind({ chronicleActive: isActive, hasSelection: sel != null });
}
