/**
 * Search reuses the list endpoint (GET /entities?search=). Highlights and
 * density have no backend endpoint yet — they are deferred to their build-order
 * steps (timeline / highlights). The stubs throw so an accidental call is loud;
 * the hooks keep them disabled.
 */
import { EntityListSchema, type EntityList } from '@/lib/schemas/entity';
import type { Scope } from '@/types/atlas';
import { api } from './client';
import { listParams } from './params';

export async function search(
  scope: Scope,
  q: string,
  signal?: AbortSignal,
): Promise<EntityList> {
  const { data } = await api.get('/api/v1/entities', {
    signal,
    params: listParams(scope, { search: q, sort: 'relevance' }),
  });
  return EntityListSchema.parse(data);
}

/** Deferred — no /highlights endpoint yet (period-banner build step). */
export async function highlights(): Promise<never> {
  throw new Error('highlights endpoint not implemented (deferred)');
}

/** Deferred — no /density endpoint yet (timeline build step). */
export async function timelineDensity(): Promise<never> {
  throw new Error('density endpoint not implemented (deferred)');
}
