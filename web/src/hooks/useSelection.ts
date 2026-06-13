import { useQueryState } from 'nuqs';
import { useCallback } from 'react';
import { parseAsSelection } from '@/lib/url/params';

/**
 * Selected entity id <-> URL `sel` (type-prefixed, e.g. "e:marathon").
 * Written with `push` so the back button deselects. Subscribing here does NOT
 * re-render when bbox/time change — that selective subscription is half the
 * re-render budget (spec §8).
 */
export function useSelection() {
  const [sel, setSel] = useQueryState(
    'sel',
    parseAsSelection.withOptions({ history: 'push' }),
  );

  const select = useCallback((id: string) => setSel(id), [setSel]);
  const clear = useCallback(() => setSel(null), [setSel]);

  return { sel, select, clear };
}
