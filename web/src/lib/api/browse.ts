/**
 * Browse-page reads over existing resources (spec 2026-11-01 public site, D4).
 * The atlas list (`entityList`) is scoped to the visible map; the browse pages
 * list everything carrying a tag, wherever and whenever it is.
 */
import { EntityListSchema } from '@/lib/schemas/entity';
import type { EntityList } from '@/lib/schemas/entity';
import { api } from './client';

export interface EntitiesByTagsParams {
  /** Tag slugs: AND across facets, OR within a facet. */
  tags: string[];
  sort?: 'impact' | 'chronological' | 'name';
  perPage?: number;
  page?: number;
}

/** GET /entities?tags=a,b&sort=impact — paginated EntitySummaryResource rows. */
export async function entitiesByTags(
  { tags, sort = 'impact', perPage = 24, page = 1 }: EntitiesByTagsParams,
  signal?: AbortSignal,
): Promise<EntityList> {
  const { data } = await api.get('/api/v1/entities', {
    signal,
    params: { tags: tags.join(','), sort, per_page: perPage, page },
  });
  return EntityListSchema.parse(data);
}
