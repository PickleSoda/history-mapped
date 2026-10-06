/**
 * The single source of truth for query keys (spec §4).
 *
 * Never hand-write a key array at a call site — always go through `qk` so
 * invalidation and prefetch line up. TanStack hashes object/array keys
 * deterministically, so passing the snapped `Scope` is stable.
 */
import type { ChronicleGraphParams, EntityGraphParams } from '@/lib/api/graph';
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
  /** Derived timeline rows (GET /entities/{id}/timeline). */
  entityTimeline: (id: string) => ['entity', id, 'timeline'] as const,
  /** Relation graph around an entity. Pass NORMALISED params (see
   *  `normaliseEntityGraphParams`) so the "expand node" fetch and the entity
   *  page share one cache entry. */
  entityGraph: (id: string, params: EntityGraphParams) =>
    ['entity', id, 'graph', params] as const,
  search: (q: string, scope: Scope) =>
    ['search', q, scope.bbox, scope.time, scope.groups] as const,
  highlights: (time: TimeState) => ['highlights', time] as const,
  density: (scope: Scope) => ['density', scope.bbox, scope.groups] as const,
  chronicle: (slug: string) => ['chronicle', slug] as const,
  /** Whole-chronicle relation graph (params normalised, as above). */
  chronicleGraph: (slug: string, params: ChronicleGraphParams) =>
    ['chronicle', slug, 'graph', params] as const,
  /** Public historical-periods reference list (timeline gantt). */
  historicalPeriods: () => ['reference', 'historical-periods'] as const,
};
