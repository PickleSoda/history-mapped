/** Curated sets (spec 2026-11-01 public site, D4): file-authored, DB-served. */
import { CollectionListSchema, CollectionSchema } from '@/lib/schemas/collection';
import type { Collection, CollectionList } from '@/lib/schemas/collection';
import { api } from './client';

/** GET /collections — published sets, by sort order then title. */
export async function collectionList(signal?: AbortSignal): Promise<CollectionList> {
  const { data } = await api.get('/api/v1/collections', { signal });
  return CollectionListSchema.parse(data);
}

/** GET /collections/{slug} — one set with its items resolved, in the author's
 *  order. Laravel wraps the single resource in `data`; unwrap before parsing.
 *  Unknown slugs are a 404 (an axios error). */
export async function collection(slug: string, signal?: AbortSignal): Promise<Collection> {
  const { data } = await api.get(`/api/v1/collections/${encodeURIComponent(slug)}`, { signal });
  const payload = (data as { data?: unknown }).data ?? data;
  return CollectionSchema.parse(payload);
}
