/** Typed chronicle endpoints. */
import {
  ChronicleListSchema,
  ChronicleSchema,
  EntityChroniclesSchema,
} from '@/lib/schemas/chronicle';
import type {
  Chronicle,
  ChronicleList,
  EntityChronicles,
} from '@/lib/schemas/chronicle';
import { api } from './client';

export interface ChronicleListParams {
  /** Matches titles and tag names. */
  search?: string;
  /** Tag slugs: AND across facets, OR within a facet. */
  tags?: string[];
  sort?: 'chronological' | 'recent' | 'title' | 'impact';
  page?: number;
}

/** GET /chronicles — paginated, filterable listing for the Chronicles tab. */
export async function chronicleList(
  { search, tags = [], sort = 'chronological', page = 1 }: ChronicleListParams = {},
  signal?: AbortSignal,
): Promise<ChronicleList> {
  const { data } = await api.get('/api/v1/chronicles', {
    signal,
    params: {
      per_page: 50,
      page,
      sort,
      ...(search ? { search } : {}),
      ...(tags.length > 0 ? { tags: tags.join(',') } : {}),
    },
  });
  return ChronicleListSchema.parse(data);
}

/** GET /entities/{id}/chronicles — chronicles the entity appears in. */
export async function entityChronicles(
  id: string,
  signal?: AbortSignal,
): Promise<EntityChronicles> {
  const { data } = await api.get(
    `/api/v1/entities/${encodeURIComponent(id)}/chronicles`,
    { signal },
  );
  return EntityChroniclesSchema.parse(data);
}

/** GET /chronicles/{slug} — the whole tour. Laravel wraps the single resource
 *  in a `data` envelope, so unwrap before parsing. */
export async function chronicle(
  slug: string,
  signal?: AbortSignal,
): Promise<Chronicle> {
  const { data } = await api.get(
    `/api/v1/chronicles/${encodeURIComponent(slug)}`,
    { signal },
  );
  const payload = (data as { data?: unknown }).data ?? data;
  return ChronicleSchema.parse(payload);
}
