/**
 * Navigation trail (breadcrumb) logic — kept pure so it can be unit-tested and
 * so the React layer is a thin shell over it.
 *
 * A *focus* is the thing the user is currently looking at: a selected entity
 * wins over an active chronicle (you can drill into an entity mid-tour). Each
 * crumb captures the full nav snapshot {sel, chron, step} so clicking it
 * restores exactly that state — including the tour step you branched off from.
 */

export type CrumbKind = 'entity' | 'chronicle';

/** The URL-driven navigation state the trail is derived from. */
export interface NavSnapshot {
  sel: string | null;
  chron: string | null;
  step: number;
}

export interface Crumb {
  /** Stable focus identity (`e:<id>` / `c:<slug>`) — unique within a trail. */
  key: string;
  kind: CrumbKind;
  label: string;
  /** Entity group token, for the dot colour; null for chronicles. */
  group: string | null;
  /** Full nav state to restore when this crumb is clicked. */
  sel: string | null;
  chron: string | null;
  step: number;
}

export interface FocusMeta {
  entityLabel?: string | null;
  entityGroup?: string | null;
  chronicleLabel?: string | null;
}

/** The current focus crumb for a snapshot, or null at the root (the list). */
export function focusOf(s: NavSnapshot, meta: FocusMeta = {}): Crumb | null {
  if (s.sel) {
    return {
      key: `e:${s.sel}`,
      kind: 'entity',
      label: meta.entityLabel || s.sel,
      group: meta.entityGroup ?? null,
      sel: s.sel,
      chron: s.chron,
      step: s.step,
    };
  }
  if (s.chron) {
    return {
      key: `c:${s.chron}`,
      kind: 'chronicle',
      label: meta.chronicleLabel || s.chron,
      group: null,
      sel: null,
      chron: s.chron,
      step: s.step,
    };
  }
  return null;
}

function crumbEqual(a: Crumb, b: Crumb): boolean {
  return (
    a.key === b.key &&
    a.label === b.label &&
    a.group === b.group &&
    a.sel === b.sel &&
    a.chron === b.chron &&
    a.step === b.step
  );
}

/**
 * Fold the current focus into the trail:
 * - null focus (back at the list) resets the trail;
 * - same focus as the tip refreshes it in place (label loaded, step advanced) —
 *   returning the SAME array reference when nothing actually changed;
 * - a focus already earlier in the trail truncates back to it (this is how
 *   browser back / a crumb click stay in sync);
 * - otherwise the focus is pushed as a new crumb.
 */
export function reconcileTrail(prev: Crumb[], next: Crumb | null): Crumb[] {
  if (!next) return prev.length === 0 ? prev : [];
  if (prev.length === 0) return [next];

  const last = prev[prev.length - 1];
  if (last.key === next.key) {
    if (crumbEqual(last, next)) return prev;
    const updated = prev.slice();
    updated[updated.length - 1] = next;
    return updated;
  }

  const existing = prev.findIndex((c) => c.key === next.key);
  if (existing !== -1) {
    const truncated = prev.slice(0, existing + 1);
    truncated[existing] = next;
    return truncated;
  }

  return [...prev, next];
}
