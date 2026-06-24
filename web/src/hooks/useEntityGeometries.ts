import { useQueries } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { entity } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';
import type { EntityDetail } from '@/lib/schemas/entity';

/** Pull the geom off each loaded entity (null while loading / when unplaced).
 *  Module-level so `useQueries` doesn't re-run combine on every render, and so
 *  its structurally-shared output keeps a stable reference. */
const combineGeoms = (results: UseQueryResult<EntityDetail>[]): unknown[] =>
  results.map((r) => r.data?.geom ?? null);

/**
 * Resolve geometry for a set of entity ids via the cached entity-detail query
 * (geom is immutable, so `staleTime: Infinity` — revisiting a step is free).
 *
 * Chronicle steps reference secondary entities by id only, with no inline
 * geometry; this lets the step framing include them, not just the relationship's
 * two ends. Returns an array aligned to `ids` (each entry the entity's geom or
 * null), referentially stable while the resolved geometry is unchanged.
 */
export function useEntityGeometries(ids: string[]): unknown[] {
  return useQueries({
    queries: ids.map((id) => ({
      queryKey: qk.entity(id),
      queryFn: ({ signal }: { signal?: AbortSignal }) => entity(id, signal),
      enabled: id !== '',
      staleTime: Infinity,
    })),
    combine: combineGeoms,
  });
}
