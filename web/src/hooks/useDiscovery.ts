import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { highlights, search, timelineDensity } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';
import type { TimeState } from '@/types/atlas';
import { useScope } from './useScope';

/**
 * Command-palette search (GET /entities?search=). Scoped to the current
 * viewport + time. Debounce the input into `q` at the call site (~200ms);
 * `keepPreviousData` stops flicker between keystrokes.
 */
export function useSearch(q: string | null) {
  const scope = useScope();
  return useQuery({
    queryKey: qk.search(q ?? '', scope),
    queryFn: ({ signal }) => search(scope, q as string, signal),
    enabled: !!q,
    placeholderData: keepPreviousData,
  });
}

/**
 * Period-highlights banner. DEFERRED — no backend endpoint yet; the hook stays
 * disabled so nothing fires until the highlights build step adds /highlights.
 */
export function useHighlights(time: TimeState) {
  return useQuery({
    queryKey: qk.highlights(time),
    queryFn: () => highlights(),
    enabled: false,
  });
}

/**
 * Timeline density histogram. DEFERRED — no backend endpoint yet; disabled
 * until the timeline build step adds /density.
 */
export function useTimelineDensity() {
  const scope = useScope();
  return useQuery({
    queryKey: qk.density(scope),
    queryFn: () => timelineDensity(),
    enabled: false,
  });
}
