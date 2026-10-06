import { useQuery } from '@tanstack/react-query';
import { entityTimeline } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';

/** Derived timeline rows for an entity (GET /entities/{id}/timeline). */
export function useEntityTimeline(id: string | null, enabled = true) {
  return useQuery({
    queryKey: qk.entityTimeline(id ?? '∅'),
    queryFn: ({ signal }) => entityTimeline(id as string, signal),
    enabled: id !== null && enabled,
    staleTime: Infinity,
  });
}
