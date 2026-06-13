import { useQueryStates } from 'nuqs';
import { useCallback } from 'react';
import { parseAsChronicle, parseAsStep } from '@/lib/url/params';
import { useSelection } from './useSelection';

/**
 * Chronicle navigation <-> URL `chron` + `step`. Both written with `push` so
 * the back button walks steps backward and then exits the chronicle. While a
 * chronicle is active, the step's {time, bbox} drive the map (the timeline is
 * locked) — that derivation lives in the chronicle player, not here.
 */
export function useChronicleNav() {
  const [{ chron, step }, set] = useQueryStates(
    {
      chron: parseAsChronicle,
      step: parseAsStep.withDefault(0),
    },
    { history: 'push' },
  );
  const { clear: clearSelection } = useSelection();

  // Entering a chronicle closes any open entity — the right panel shows the
  // tour OR the detail, never both.
  const enter = useCallback(
    (id: string) => {
      clearSelection();
      set({ chron: id, step: 0 });
    },
    [set, clearSelection],
  );
  const exit = useCallback(() => set({ chron: null, step: null }), [set]);
  const goto = useCallback((index: number) => set({ step: index }), [set]);
  const next = useCallback(() => set((p) => ({ step: (p.step ?? 0) + 1 })), [set]);
  const prev = useCallback(
    () => set((p) => ({ step: Math.max(0, (p.step ?? 0) - 1) })),
    [set],
  );

  return { chron, step, isActive: chron !== null, enter, exit, goto, next, prev };
}
