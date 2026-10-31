/** Typed map-story endpoints (step-by-step story maps, and their ambient state). */
import { AmbientStoriesSchema, MapStorySchema } from '@/lib/schemas/map-story';
import type { AmbientStory, MapStory } from '@/lib/schemas/map-story';
import { api } from './client';

/** GET /map-stories/{slug} — the whole story document, unwrapped from `data`. */
export async function mapStory(slug: string, signal?: AbortSignal): Promise<MapStory> {
  const { data } = await api.get(`/api/v1/map-stories/${encodeURIComponent(slug)}`, { signal });
  const payload = (data as { data?: unknown }).data ?? data;
  return MapStorySchema.parse(payload);
}

/**
 * GET /map-stories/ambient?year=&bbox=w,s,e,n — the stories that opt into
 * ambient mode, each at its last step starting by `year`, with the features of
 * that step inside the box (`w > e` crosses the antimeridian).
 */
export async function ambientStories(
  year: number,
  bbox: [number, number, number, number],
  signal?: AbortSignal,
): Promise<AmbientStory[]> {
  const { data } = await api.get('/api/v1/map-stories/ambient', {
    params: { year, bbox: bbox.map((v) => Math.round(v * 1000) / 1000).join(',') },
    signal,
  });
  return AmbientStoriesSchema.parse(data).data;
}
