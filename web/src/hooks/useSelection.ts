import { useQueryState } from 'nuqs';
import { useCallback } from 'react';
import { PREVIEW } from '@/lib/map-story/preview';
import { parseAsSelection } from '@/lib/url/params';

/**
 * Selected entity id <-> URL `sel` (type-prefixed, e.g. "e:marathon").
 * Written with `push` so the back button deselects. Subscribing here does NOT
 * re-render when bbox/time change — that selective subscription is half the
 * re-render budget (spec §8). The admin's map-story preview (`?preview=1`)
 * never opens an entity: a click there is for editing.
 */
export function useSelection() {
  const [sel, setSel] = useQueryState(
    'sel',
    parseAsSelection.withOptions({ history: 'push' }),
  );

  const select = useCallback((id: string) => (PREVIEW ? Promise.resolve(new URLSearchParams(window.location.search)) : setSel(id)), [setSel]);
  const clear = useCallback(() => setSel(null), [setSel]);

  return { sel, select, clear };
}
