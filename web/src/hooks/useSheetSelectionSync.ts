import { useEffect, useRef } from 'react';
import { useSelection, useSheet } from '@/hooks';
import { nextSheetForSelection } from '@/lib/sheet';

/** Mobile only: nudge the sheet height when the selection changes. */
export function useSheetSelectionSync(): void {
  const { sel } = useSelection();
  const { sheet, setSheet } = useSheet();
  const prev = useRef<string | null>(sel);

  useEffect(() => {
    const next = nextSheetForSelection({ prevSel: prev.current, nextSel: sel, current: sheet });
    if (next !== sheet) setSheet(next);
    prev.current = sel;
  }, [sel, sheet, setSheet]);
}
