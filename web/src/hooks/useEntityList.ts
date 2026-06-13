import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { entityList } from '@/lib/api';
import type { ListOptions } from '@/lib/api/params';
import { qk } from '@/lib/query/queryKeys';
import { useScope } from './useScope';

/**
 * The ranked "notable here" list for the current scope (GET /entities). Returns
 * a real total in `meta` and includes unplaced entities. Separate from the map
 * FeatureCollection by design (two purpose-built endpoints).
 */
export function useEntityList(opts: ListOptions = {}) {
  const scope = useScope();
  return useQuery({
    queryKey: qk.entityList(scope, opts),
    queryFn: ({ signal }) => entityList(scope, opts, signal),
    placeholderData: keepPreviousData,
    staleTime: 5 * 60_000,
  });
}
