/** Discover endpoints: on this day, meanwhile in a year, the daily expedition, for you. */
import { ForYouSchema, MeanwhileSchema, OnThisDaySchema, QuestSchema } from '@/lib/schemas/discover';
import type { ForYou, Meanwhile, OnThisDay, Quest } from '@/lib/schemas/discover';
import { api } from './client';

/** Each endpoint wraps its payload in `data`. */
const unwrap = (body: unknown): unknown => (body as { data?: unknown }).data ?? body;

/** GET /discover/on-this-day — what the atlas has for this month and day (`date`: the reader's local YYYY-MM-DD). */
export async function onThisDay(date: string, signal?: AbortSignal): Promise<OnThisDay> {
  const { data } = await api.get('/api/v1/discover/on-this-day', { params: { date }, signal });
  return OnThisDaySchema.parse(unwrap(data));
}

/** GET /discover/meanwhile — what was going on in each world region in `year` (BCE negative). */
export async function meanwhile(year: number, signal?: AbortSignal): Promise<Meanwhile> {
  const { data } = await api.get('/api/v1/discover/meanwhile', { params: { year }, signal });
  return MeanwhileSchema.parse(unwrap(data));
}

/** GET /discover/quest — the day's expedition: places and times to find on the map. */
export async function dailyQuest(date: string, signal?: AbortSignal): Promise<Quest> {
  const { data } = await api.get('/api/v1/discover/quest', { params: { date }, signal });
  return QuestSchema.parse(unwrap(data));
}

/** GET /discover/for-you — suggestions from the entities this browser opened lately (ids, most recent first). */
export async function forYou(ids: string[], signal?: AbortSignal): Promise<ForYou> {
  const { data } = await api.get('/api/v1/discover/for-you', { params: { ids: ids.join(',') }, signal });
  return ForYouSchema.parse(unwrap(data));
}
