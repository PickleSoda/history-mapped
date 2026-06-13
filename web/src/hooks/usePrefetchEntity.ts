import { useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';
import { entity } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';

/**
 * Warm the detail panel before the click lands. Call the returned fn on
 * `onMouseEnter` of a list row or `onMouseOver` of a pin; for chronicles,
 * prefetch step n+1's entity.
 */
export function usePrefetchEntity() {
  const qc = useQueryClient();
  return useCallback(
    (id: string) =>
      qc.prefetchQuery({
        queryKey: qk.entity(id),
        queryFn: ({ signal }) => entity(id, signal),
        staleTime: Infinity,
      }),
    [qc],
  );
}
