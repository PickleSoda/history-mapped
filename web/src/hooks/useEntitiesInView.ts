import { keepPreviousData, useQueries } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { entitiesInView } from '@/lib/api';
import type { MapLayer } from '@/lib/api/params';
import { qk } from '@/lib/query/queryKeys';
import type { MapFeature, MapFeatureCollection } from '@/lib/schemas/map';
import { useMapInsetsReady } from './ephemeral';
import { useScope } from './useScope';

const LAYERS: readonly MapLayer[] = ['outer', 'core'];

/**
 * One FeatureCollection from the layers that have landed: the prominent outer
 * set first (server order), then whatever the dense core adds. Module-level so
 * `useQueries` can memoize it — the map only re-receives data when a layer
 * actually changes.
 */
function mergeLayers(results: UseQueryResult<MapFeatureCollection>[]) {
  const seen = new Set<string | number>();
  const features: MapFeature[] = [];
  let any = false;
  for (const { data } of results) {
    if (!data) continue;
    any = true;
    for (const f of data.features) {
      const id = f.id ?? f.properties.id;
      if (seen.has(id)) continue;
      seen.add(id);
      features.push(f);
    }
  }
  const data: MapFeatureCollection | undefined = any
    ? { type: 'FeatureCollection', features }
    : undefined;
  return {
    data,
    isLoading: results.some((r) => r.isLoading),
    isError: results.some((r) => r.isError),
  };
}

/**
 * The viewport query — runs constantly and feeds the map pins. Two layers over
 * the visible area (see `MapLayer`): the outer ring stays sparse, the core is
 * dense, merged into one FeatureCollection. `keepPreviousData` keeps the old
 * pins on screen during a refetch (no empty-map flash); high `staleTime`
 * because history is immutable; `signal` aborts in-flight requests on a fast
 * scrub.
 */
export function useEntitiesInView() {
  const scope = useScope();
  const ready = useMapInsetsReady();
  return useQueries({
    queries: LAYERS.map((layer) => ({
      queryKey: qk.entitiesInView(scope, layer),
      queryFn: ({ signal }: { signal: AbortSignal }) => entitiesInView(scope, layer, signal),
      enabled: ready,
      placeholderData: keepPreviousData,
      staleTime: 5 * 60_000,
      gcTime: 30 * 60_000,
    })),
    combine: mergeLayers,
  });
}
