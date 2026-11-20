import { useQueryState } from 'nuqs';
import { useCallback } from 'react';
import { parseAsSearchFilter } from '@/lib/url/params';

/** Shortest word worth filtering by. */
export const SEARCH_FILTER_MIN = 2;

/**
 * The search word kept as a filter <-> URL `q`. Set from the search box with
 * Enter; while it is set the map and the list show the entities whose name
 * matches it, whatever the year or the view. Written with `push`, so Back
 * clears it.
 */
export function useSearchFilter() {
  const [raw, setRaw] = useQueryState('q', parseAsSearchFilter.withOptions({ history: 'push' }));
  const q = raw && raw.trim().length >= SEARCH_FILTER_MIN ? raw.trim() : null;

  const setFilter = useCallback((word: string) => setRaw(word.trim() || null), [setRaw]);
  const clear = useCallback(() => setRaw(null), [setRaw]);

  return { q, setFilter, clear };
}
