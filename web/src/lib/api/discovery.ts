/** Entity search for the command palette (GET /entities?search=). */
import { EntityListSchema } from '@/lib/schemas/entity';
import type { EntityList } from '@/lib/schemas/entity';
import { ENTITY_GROUPS } from '@/types/atlas';
import type { EntityGroup } from '@/types/atlas';
import { api } from './client';

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
