import { useEffect, useRef } from 'react';
import { useSelection, useSheet, useStoryNav } from '@/hooks';
import { nextSheetForSelection } from '@/lib/sheet';

/** Mobile only: nudge the sheet height when the selection changes, and to half
 *  height when a battle map starts (the step text below, the battle above). */
export function useSheetSelectionSync(): void {
  const { sel } = useSelection();
  const { story } = useStoryNav();
  const { sheet, setSheet } = useSheet();
  const prev = useRef<string | null>(sel);
  const prevStory = useRef<string | null>(story);

  useEffect(() => {
    const next = nextSheetForSelection({ prevSel: prev.current, nextSel: sel, current: sheet });
    if (next !== sheet) setSheet(next);
    prev.current = sel;
  }, [sel, sheet, setSheet]);

  useEffect(() => {
    if (story && story !== prevStory.current && sheet !== 'half') setSheet('half');
    prevStory.current = story;
  }, [story, sheet, setSheet]);
}
