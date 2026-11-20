import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';
import { mapFocus } from '@/lib/api';
import type { MapFocusTarget } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';
import { useChronicleNav } from './useChronicleNav';
import { useFilters } from './useFilters';
import { useSearchFilter } from './useSearchFilter';
import { useSelection } from './useSelection';
import { useStoryNav } from './useStoryNav';

/**
 * What the map is narrowed to, if anything: the selected entity with its
 * relations (it wins), else the search word kept as a filter. A chronicle or
 * a battle map draws its own cast, so nothing is narrowed while one plays.
 */
export function useFocusTarget(): MapFocusTarget | null {
  const { sel } = useSelection();
  const { q } = useSearchFilter();
  const { isActive: chronicleActive } = useChronicleNav();
  const { isActive: storyActive } = useStoryNav();
  const busy = chronicleActive || storyActive;
  return useMemo<MapFocusTarget | null>(() => {
    if (busy) return null;
    if (sel) return { kind: 'related', id: sel };
    return q ? { kind: 'search', q } : null;
  }, [busy, sel, q]);
}

/**
 * The focused set's map points (GET /entities/map/focus). While a new target
 * loads, the previous set stays on the map; `data` is undefined only when
 * nothing is focused or the first set has not arrived.
 */
export function useFocusSet() {
  const target = useFocusTarget();
  const { groups } = useFilters();
  const query = useQuery({
    queryKey: qk.mapFocus(target ?? { kind: 'search', q: '' }, groups),
    queryFn: ({ signal }) => mapFocus(target as MapFocusTarget, groups, signal),
    enabled: target !== null,
    placeholderData: keepPreviousData,
    staleTime: 5 * 60_000,
  });
  return {
    target,
    data: target ? query.data : undefined,
    /** True once `data` belongs to `target` (not the previous set). */
    settled: target !== null && query.isSuccess && !query.isPlaceholderData,
  };
}
