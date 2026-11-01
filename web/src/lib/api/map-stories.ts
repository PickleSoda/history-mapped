/** Typed map-story endpoints (step-by-step story maps, and their ambient state). */
import { AmbientStoriesSchema, MapStorySchema } from '@/lib/schemas/map-story';
import type { AmbientStory, MapStory } from '@/lib/schemas/map-story';
import { MapStoryListSchema } from '@/lib/schemas/map-story-list';
import type { MapStoryList } from '@/lib/schemas/map-story-list';
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

export interface MapStoryListParams {
  /** One story kind (`battle`, `siege`, `naval_battle`, `epidemic`…); omit for all. */
  kind?: string;
  sort?: 'year' | 'title';
  /** At most 100 (the API's cap). */
  perPage?: number;
  page?: number;
}

/** GET /map-stories — the paginated story index for the browse pages. */
export async function mapStoryList(
  { kind, sort = 'year', perPage = 48, page = 1 }: MapStoryListParams = {},
  signal?: AbortSignal,
): Promise<MapStoryList> {
  const { data } = await api.get('/api/v1/map-stories', {
    signal,
    params: { sort, per_page: Math.min(perPage, 100), page, ...(kind ? { kind } : {}) },
  });
  return MapStoryListSchema.parse(data);
}
