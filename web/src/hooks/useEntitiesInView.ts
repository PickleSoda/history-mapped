import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { entitiesInView } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';
import { useScope } from './useScope';

/**
 * The viewport query — runs constantly, feeds BOTH the map pins and the
 * "notable here" list (one fetch, two consumers). `keepPreviousData` keeps the
 * old pins on screen during a refetch (no empty-map flash); high `staleTime`
 * because history is immutable; `signal` aborts in-flight requests on a fast
 * scrub.
 */
export function useEntitiesInView() {
  const scope = useScope();
  return useQuery({
    queryKey: qk.entitiesInView(scope),
    queryFn: ({ signal }) => entitiesInView(scope, signal),
    placeholderData: keepPreviousData,
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
  });
}
