import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';
import {
  fetchChronicleGraph,
  fetchEntityGraph,
  normaliseChronicleGraphParams,
  normaliseEntityGraphParams,
} from '@/lib/api';
import type { ChronicleGraphParams, EntityGraphParams } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';

/** Relation graph around an entity (1 or 2 hops). `staleTime: Infinity` — the
 *  graph is as immutable as the entity. Keeps the previous graph while a new
 *  depth loads so the canvas doesn't flash empty. */
export function useEntityGraph(
  id: string | null,
  params: EntityGraphParams = {},
  enabled = true,
) {
  const p = normaliseEntityGraphParams(params);
  return useQuery({
    queryKey: qk.entityGraph(id ?? '∅', p),
    queryFn: ({ signal }) => fetchEntityGraph(id as string, p, signal),
    enabled: id !== null && enabled,
    staleTime: Infinity,
    placeholderData: (prev, prevQuery) =>
      prevQuery?.queryKey[1] === id ? keepPreviousData(prev) : undefined,
  });
}

/** Whole-chronicle relation graph with per-step membership. */
export function useChronicleGraph(
  slug: string | null,
  params: ChronicleGraphParams = {},
  enabled = true,
) {
  const p = normaliseChronicleGraphParams(params);
  return useQuery({
    queryKey: qk.chronicleGraph(slug ?? '∅', p),
    queryFn: ({ signal }) => fetchChronicleGraph(slug as string, p, signal),
    enabled: slug !== null && enabled,
    staleTime: Infinity,
  });
}

/**
 * Imperative depth-1 neighbourhood fetch for "expand node". Goes through the
 * query cache under the same key `useEntityGraph(id)` uses, so expanding a node
 * and later opening that entity's page cost one request between them.
 */
export function useFetchNeighbourhood() {
  const qc = useQueryClient();
  return useCallback(
    (id: string) => {
      const p = normaliseEntityGraphParams({ depth: 1 });
      return qc.fetchQuery({
        queryKey: qk.entityGraph(id, p),
        queryFn: ({ signal }) => fetchEntityGraph(id, p, signal),
        staleTime: Infinity,
      });
    },
    [qc],
  );
}
