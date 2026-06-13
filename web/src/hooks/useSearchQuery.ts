import { useQueryState } from 'nuqs';
import { useCallback } from 'react';
import { parseAsSearch } from '@/lib/url/params';

/**
 * Search query <-> URL `q`. Presence of `q` opens the command palette, so a
 * search is shareable. Written with `replace` (refining within the palette).
 */
export function useSearchQuery() {
  const [q, setQ] = useQueryState(
    'q',
    parseAsSearch.withOptions({ history: 'replace' }),
  );

  const isOpen = q !== null;
  const open = useCallback((initial = '') => setQ(initial), [setQ]);
  const close = useCallback(() => setQ(null), [setQ]);
  const setQuery = useCallback((next: string) => setQ(next), [setQ]);

  return { q, isOpen, open, close, setQuery };
}
