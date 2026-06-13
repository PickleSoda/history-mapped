/** Typed endpoints for search, period highlights, and timeline density. */
import {
  DensitySchema,
  HighlightsSchema,
  SearchResultsSchema,
  type Density,
  type Highlights,
  type SearchResults,
} from '@/lib/schemas/search';
import { serializeBbox, serializeTime } from '@/lib/url/serialize';
import type { EntityGroup, Scope, TimeState } from '@/types/atlas';
import { api } from './client';

export async function search(
  q: string,
  filters: { groups: EntityGroup[]; time: TimeState },
  signal?: AbortSignal,
): Promise<SearchResults> {
  const { data } = await api.get('/api/v1/atlas/search', {
    signal,
    params: {
      q,
      groups: filters.groups.join(','),
      t: serializeTime(filters.time),
    },
  });
  return SearchResultsSchema.parse(data);
}

export async function highlights(
  time: TimeState,
  signal?: AbortSignal,
): Promise<Highlights> {
  const { data } = await api.get('/api/v1/atlas/highlights', {
    signal,
    params: { t: serializeTime(time) },
  });
  return HighlightsSchema.parse(data);
}

export async function timelineDensity(
  scope: Scope,
  signal?: AbortSignal,
): Promise<Density> {
  const { data } = await api.get('/api/v1/atlas/density', {
    signal,
    params: {
      bbox: serializeBbox(scope.bbox),
      groups: scope.groups.join(','),
    },
  });
  return DensitySchema.parse(data);
}
