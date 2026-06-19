/**
 * The single source of truth for query keys (spec §4).
 *
 * Never hand-write a key array at a call site — always go through `qk` so
 * invalidation and prefetch line up. TanStack hashes object/array keys
 * deterministically, so passing the snapped `Scope` is stable.
 */
import type { ListOptions } from '@/lib/api/params';
import type { Scope, TimeState } from '@/types/atlas';

export const qk = {
  /** Map FeatureCollection (pins/borders). */
  entitiesInView: (scope: Scope) =>
    ['entities', 'map', scope.z, scope.bbox, scope.time, scope.groups] as const,
  /** Ranked "notable here" list (paginated). */
  entityList: (scope: Scope, opts: ListOptions) =>
    ['entities', 'list', scope.bbox, scope.time, scope.groups, opts.sort, opts.page] as const,
  entity: (id: string) => ['entity', id] as const,
  connections: (id: string) => ['entity', id, 'connections'] as const,
  search: (q: string, scope: Scope) =>
    ['search', q, scope.bbox, scope.time, scope.groups] as const,
  highlights: (time: TimeState) => ['highlights', time] as const,
  density: (scope: Scope) => ['density', scope.bbox, scope.groups] as const,
  chronicle: (slug: string) => ['chronicle', slug] as const,
  /** Public historical-periods reference list (timeline gantt). */
  historicalPeriods: () => ['reference', 'historical-periods'] as const,
};
