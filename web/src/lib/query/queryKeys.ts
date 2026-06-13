/**
 * The single source of truth for query keys (spec §4).
 *
 * Never hand-write a key array at a call site — always go through `qk` so
 * invalidation and prefetch line up. TanStack hashes object/array keys
 * deterministically, so passing the snapped `Scope` is stable.
 */
import type { EntityGroup, Scope, TimeState } from '@/types/atlas';

export const qk = {
  entitiesInView: (scope: Scope) =>
    ['entities', 'view', scope.z, scope.bbox, scope.time, scope.groups] as const,
  entity: (id: string) => ['entity', id] as const,
  connections: (id: string) => ['entity', id, 'connections'] as const,
  search: (q: string, filters: { groups: EntityGroup[]; time: TimeState }) =>
    ['search', q, filters.groups, filters.time] as const,
  highlights: (time: TimeState) => ['highlights', time] as const,
  density: (scope: Scope) => ['density', scope.bbox, scope.groups] as const,
  chronicle: (id: string) => ['chronicle', id] as const,
};
