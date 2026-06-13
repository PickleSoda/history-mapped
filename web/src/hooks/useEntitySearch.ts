import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { searchEntities } from '@/lib/api';
import type { EntityGroup } from '@/types/atlas';

/**
 * Global entity search for the command palette. Independent of the map scope —
 * keyed on the query string and the palette-local group filter. Disabled until
 * there is a query.
 */
export function useEntitySearch(q: string, groups: EntityGroup[]) {
  return useQuery({
    queryKey: ['command-search', q, [...groups].sort()] as const,
    queryFn: ({ signal }) => searchEntities(q, groups, signal),
    enabled: q.trim().length > 0,
    placeholderData: keepPreviousData,
  });
}
