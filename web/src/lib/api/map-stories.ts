/** Typed map-story endpoint (step-by-step battle maps). */
import { MapStorySchema } from '@/lib/schemas/map-story';
import type { MapStory } from '@/lib/schemas/map-story';
import { api } from './client';

/** GET /map-stories/{slug} — the whole story document, unwrapped from `data`. */
export async function mapStory(slug: string, signal?: AbortSignal): Promise<MapStory> {
  const { data } = await api.get(`/api/v1/map-stories/${encodeURIComponent(slug)}`, { signal });
  const payload = (data as { data?: unknown }).data ?? data;
  return MapStorySchema.parse(payload);
}
