import { afterEach, describe, expect, it, vi } from 'vitest';
import { collectionDetailPayload, collectionListPayload, mapStoryListPayload } from '@/lib/schemas/collection.fixtures';
import { entitiesByTags } from './browse';
import { api } from './client';
import { collection, collectionList } from './collections';
import { mapStoryList } from './map-stories';

/** Stub the transport: no network in tests. */
function stubGet(data: unknown) {
  return vi.spyOn(api, 'get').mockResolvedValue({ data } as never);
}

afterEach(() => vi.restoreAllMocks());

describe('browse endpoints', () => {
  it('lists curated sets', async () => {
    const get = stubGet(collectionListPayload);
    const list = await collectionList();
    expect(get).toHaveBeenCalledWith('/api/v1/collections', { signal: undefined });
    expect(list.data.map((c) => c.slug)).toEqual(['the-roman-world', 'great-battles']);
  });

  it('unwraps one set from its data envelope and encodes the slug', async () => {
    const get = stubGet(collectionDetailPayload);
    const set = await collection('the roman/world');
    expect(get.mock.calls[0][0]).toBe('/api/v1/collections/the%20roman%2Fworld');
    expect(set.items).toHaveLength(4);
  });

  it('pages the story index, omitting an empty kind and capping per_page', async () => {
    const get = stubGet(mapStoryListPayload);
    await mapStoryList({ perPage: 500 });
    expect(get.mock.calls[0][1]).toMatchObject({ params: { sort: 'year', per_page: 100, page: 1 } });
    expect(get.mock.calls[0][1]?.params).not.toHaveProperty('kind');
    await mapStoryList({ kind: 'siege', sort: 'title', page: 2 });
    expect(get.mock.calls[1][1]).toMatchObject({ params: { kind: 'siege', sort: 'title', page: 2 } });
  });

  it('lists entities by tag, impact first, without map scope', async () => {
    const get = stubGet({ data: [], meta: { current_page: 1, last_page: 1, per_page: 24, total: 0 } });
    await entitiesByTags({ tags: ['medieval', 'europe'] });
    expect(get.mock.calls[0][1]?.params).toEqual({ tags: 'medieval,europe', sort: 'impact', per_page: 24, page: 1 });
  });
});
