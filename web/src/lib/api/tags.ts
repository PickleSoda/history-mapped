/** Tag vocabulary endpoint. */
import { TagListSchema } from '@/lib/schemas/tag';
import type { TagList } from '@/lib/schemas/tag';
import { api } from './client';

/** GET /tags — every tag with chronicle/entity usage counts. */
export async function tagList(signal?: AbortSignal): Promise<TagList> {
  const { data } = await api.get('/api/v1/tags', { signal });
  return TagListSchema.parse(data);
}
