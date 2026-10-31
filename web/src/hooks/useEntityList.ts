import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { entityList } from '@/lib/api';
import type { ListOptions } from '@/lib/api/params';
import { qk } from '@/lib/query/queryKeys';
import { useMapInsetsReady } from './ephemeral';
import { useScope } from './useScope';

/**
 * The ranked "notable here" list for the current scope (GET /entities): the
 * entities placed in the visible area, with a real total in `meta`. Unplaced
 * entities have no "here", so they only surface through search. Separate from
 * the map FeatureCollection by design (two purpose-built endpoints).
 */
export function useEntityList(opts: ListOptions = {}) {
  const scope = useScope();
  const ready = useMapInsetsReady();
  return useQuery({
    queryKey: qk.entityList(scope, opts),
    queryFn: ({ signal }) => entityList(scope, opts, signal),
    enabled: ready,
    placeholderData: keepPreviousData,
    staleTime: 5 * 60_000,
  });
}
