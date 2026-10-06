/**
 * Full-page state — kept pure so the URL → page / sheet policy is unit-tested
 * and the React layer stays a thin shell over it.
 *
 * A *page* is the expanded, scrollable view of the current focus. Like the
 * detail panel, a selected entity wins over an active chronicle, so an entity
 * page opened from a chronicle page sits on top of it.
 */
import type { SheetHeight } from '@/stores/ephemeral';

export type FullPageKind = 'entity' | 'chronicle';

/** Which page the focus would expand into (ignores `full`). */
export function pageKindFor(a: { sel: string | null; chron: string | null }): FullPageKind | null {
  if (a.sel) return 'entity';
  if (a.chron) return 'chronicle';
  return null;
}

/** The page that is open right now, or null when collapsed / nothing to show. */
export function openPageKind(a: {
  full: boolean;
  sel: string | null;
  chron: string | null;
}): FullPageKind | null {
  return a.full ? pageKindFor(a) : null;
}

/**
 * Every page open right now, bottom → top. With both `chron` and `sel`, the
 * entity page sits on top of the chronicle page (which stays mounted beneath
 * it, keeping its scroll and graph state for when the entity page closes).
 */
export function openPageStack(a: {
  full: boolean;
  sel: string | null;
  chron: string | null;
}): FullPageKind[] {
  if (!a.full) return [];
  const stack: FullPageKind[] = [];
  if (a.chron) stack.push('chronicle');
  if (a.sel) stack.push('entity');
  return stack;
}

/**
 * URL state after "Close" on an entity page: drop the selection. Keep `full`
 * only when a chronicle is active, so closing an entity page opened on top of
 * a chronicle page returns to that chronicle page; otherwise collapse too.
 */
export function closeEntityPage(a: { full: boolean; chron: string | null }): {
  sel: null;
  full: boolean;
} {
  return { sel: null, full: a.chron ? a.full : false };
}

/** Mobile: sheet height when the `full` URL flag flips (deep link, Back,
 *  Expand / Collapse buttons). Returning to a lower snap lands on half. */
export function nextSheetForFull(a: {
  prevFull: boolean;
  nextFull: boolean;
  hasPage: boolean;
  current: SheetHeight;
}): SheetHeight {
  if (!a.prevFull && a.nextFull && a.hasPage) return 'full';
  if (a.prevFull && !a.nextFull && a.current === 'full') return 'half';
  return a.current;
}

/** Mobile: the `full` flag a user's drag to `height` implies, or null for "no
 *  change". Dragging up onto the full snap opens the page (so Back collapses
 *  it); leaving the full snap removes the flag. */
export function fullForSheet(a: {
  height: SheetHeight;
  full: boolean;
  hasPage: boolean;
}): boolean | null {
  if (a.height === 'full' && a.hasPage && !a.full) return true;
  if (a.height !== 'full' && a.full) return false;
  return null;
}
