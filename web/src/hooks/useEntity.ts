import { useQuery } from '@tanstack/react-query';
import { entity, entityConnections } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';

/** Detail-panel payload for the selected entity. `staleTime: Infinity` — an
 *  entity's history does not change once loaded. */
export function useEntity(id: string | null) {
  return useQuery({
    queryKey: qk.entity(id ?? '∅'),
    queryFn: ({ signal }) => entity(id as string, signal),
    enabled: id !== null,
    staleTime: Infinity,
  });
}

/** Related-entities list. Lazy: only enabled when the panel section needs it. */
export function useEntityConnections(id: string | null, enabled = true) {
  return useQuery({
    queryKey: qk.connections(id ?? '∅'),
    queryFn: ({ signal }) => entityConnections(id as string, signal),
    enabled: id !== null && enabled,
    staleTime: Infinity,
  });
}
