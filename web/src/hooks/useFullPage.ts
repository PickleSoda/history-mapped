import { useQueryStates } from 'nuqs';
import { useCallback } from 'react';
import { closeEntityPage, openPageKind, openPageStack, pageKindFor } from '@/lib/full-page';
import {
  parseAsChronicle,
  parseAsFull,
  parseAsSelection,
  parseAsStep,
} from '@/lib/url/params';

const PAGE_KEYS = {
  full: parseAsFull,
  sel: parseAsSelection,
  chron: parseAsChronicle,
  step: parseAsStep,
};

/**
 * Full-page state <-> URL `full` (+ the `sel` / `chron` it expands). Written
 * with `push` so Back collapses an open page. `kind` is the topmost open page,
 * `stack` every open page (bottom → top), `focusKind` what Expand would open.
 */
export function useFullPage() {
  const [{ full, sel, chron }, set] = useQueryStates(PAGE_KEYS, { history: 'push' });

  const expand = useCallback(() => set({ full: true }), [set]);
  const collapse = useCallback(() => set({ full: null }), [set]);
  /** Open the active chronicle's page (dropping any entity on top of it). */
  const expandChronicle = useCallback(() => set({ full: true, sel: null }), [set]);
  /** Collapse the chronicle page back to the tour, at tour step `step`. */
  const collapseChronicle = useCallback(
    (step?: number) => set(step == null ? { full: null } : { full: null, step }),
    [set],
  );
  /** Close the chronicle page: leave the tour entirely. */
  const closeChronicle = useCallback(
    () => set({ full: null, chron: null, step: null, sel: null }),
    [set],
  );
  /** Close an entity page: clear the selection (see `closeEntityPage`). */
  const closeEntity = useCallback(
    () =>
      set((p) => {
        const next = closeEntityPage({ full: p.full, chron: p.chron });
        return { sel: null, full: next.full || null };
      }),
    [set],
  );

  return {
    full,
    sel,
    chron,
    kind: openPageKind({ full, sel, chron }),
    stack: openPageStack({ full, sel, chron }),
    focusKind: pageKindFor({ sel, chron }),
    expand,
    collapse,
    closeEntity,
    expandChronicle,
    collapseChronicle,
    closeChronicle,
  };
}
