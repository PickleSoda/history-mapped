import type { SheetHeight } from '@/stores/ephemeral';

/** vaul snap points, low → high. Index-aligned to ORDER below. */
export const SNAP_POINTS = ['130px', 0.55, 0.97] as const;
const ORDER: readonly SheetHeight[] = ['peek', 'half', 'full'];

export function heightToSnap(h: SheetHeight): number | string {
  return SNAP_POINTS[ORDER.indexOf(h)];
}

export function snapToHeight(snap: number | string | null): SheetHeight {
  const i = SNAP_POINTS.findIndex((s) => s === snap);
  return i === -1 ? 'peek' : ORDER[i];
}

export type SheetContentKind = 'chronicle' | 'detail' | 'list';

/**
 * What the sheet shows. A selected entity wins so you can drill into an entity
 * mid-tour (detail, with a "back to tour" affordance) — clearing the selection
 * falls back to the active chronicle; otherwise the tour, else the list.
 */
export function sheetContentKind(a: {
  chronicleActive: boolean;
  hasSelection: boolean;
}): SheetContentKind {
  if (a.hasSelection) return 'detail';
  if (a.chronicleActive) return 'chronicle';
  return 'list';
}

/** Height policy when selection changes: keep the map partly visible. */
export function nextSheetForSelection(a: {
  prevSel: string | null;
  nextSel: string | null;
  current: SheetHeight;
}): SheetHeight {
  if (!a.prevSel && a.nextSel) return a.current === 'peek' ? 'half' : a.current;
  if (a.prevSel && !a.nextSel) return a.current === 'full' ? 'half' : a.current;
  return a.current;
}
