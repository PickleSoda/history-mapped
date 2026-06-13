import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { highlights, search, timelineDensity } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';
import type { TimeState } from '@/types/atlas';
import { useFilters } from './useFilters';
import { useScope } from './useScope';
import { useTimeState } from './useTimeState';

/**
 * Command-palette search. Scoped to current filters + time so results are
 * relevant. Debounce the input into `q` at the call site (~200ms);
 * `keepPreviousData` stops flicker between keystrokes.
 */
export function useSearch(q: string | null) {
  const { groups } = useFilters();
  const { time } = useTimeState();
  return useQuery({
    queryKey: qk.search(q ?? '', { groups, time }),
    queryFn: ({ signal }) => search(q as string, { groups, time }, signal),
    enabled: !!q,
    placeholderData: keepPreviousData,
  });
}

/** "What's new/peaked this period" banner cards for a given time. */
export function useHighlights(time: TimeState) {
  return useQuery({
    queryKey: qk.highlights(time),
    queryFn: ({ signal }) => highlights(time, signal),
  });
}

/** Histogram bars under the scrubber, keyed on bbox + groups (not time). */
export function useTimelineDensity() {
  const scope = useScope();
  return useQuery({
    queryKey: qk.density(scope),
    queryFn: ({ signal }) => timelineDensity(scope, signal),
    placeholderData: keepPreviousData,
  });
}
