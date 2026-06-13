/**
 * Search reuses the list endpoint (GET /entities?search=). Highlights and
 * density have no backend endpoint yet — they are deferred to their build-order
 * steps (timeline / highlights). The stubs throw so an accidental call is loud;
 * the hooks keep them disabled.
 */
import { EntityListSchema } from '@/lib/schemas/entity';
import type { EntityList } from '@/lib/schemas/entity';
import { ENTITY_GROUPS } from '@/types/atlas';
import type { EntityGroup, Scope } from '@/types/atlas';
import { api } from './client';
import { listParams } from './params';

export async function search(
  scope: Scope,
  q: string,
  signal?: AbortSignal,
): Promise<EntityList> {
  const { data } = await api.get('/api/v1/entities', {
    signal,
    params: listParams(scope, { search: q, sort: 'relevance' }),
  });
  return EntityListSchema.parse(data);
}

/**
 * Global entity search for the command palette — independent of the map
 * viewport, time, and the sidebar's group filters. Takes its own group filter.
 */
export async function searchEntities(
  q: string,
  groups: EntityGroup[],
  signal?: AbortSignal,
): Promise<EntityList> {
  const params: Record<string, string | number | string[]> = {
    search: q,
    sort: 'relevance',
    per_page: 30,
  };
  if (groups.length > 0 && groups.length < ENTITY_GROUPS.length) {
    params.groups = groups.map((g) => g.toUpperCase());
  }
  const { data } = await api.get('/api/v1/entities', { signal, params });
  return EntityListSchema.parse(data);
}

/** Deferred — no /highlights endpoint yet (period-banner build step). */
export async function highlights(): Promise<never> {
  throw new Error('highlights endpoint not implemented (deferred)');
}

/** Deferred — no /density endpoint yet (timeline build step). */
export async function timelineDensity(): Promise<never> {
  throw new Error('density endpoint not implemented (deferred)');
}
