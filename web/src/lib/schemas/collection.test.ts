import { describe, expect, it } from 'vitest';
import { CollectionListSchema, CollectionSchema, toCollectionItem } from './collection';
import {
  chronicleRow,
  collectionDetailPayload,
  collectionListPayload,
  entityRow,
  mapStoryListPayload,
  storyRow,
} from './collection.fixtures';
import { MapStoryListSchema } from './map-story-list';

describe('collection schemas', () => {
  it('parses the index, defaulting missing and malformed fields', () => {
    const list = CollectionListSchema.parse(collectionListPayload);
    expect(list.data).toHaveLength(2);
    const [roman, battles] = list.data;
    expect(roman.cover?.name).toBe('Roman Empire');
    expect(roman.cover?.entity_group).toBe('polity');
    expect(roman.cover?.tags).toContain('italy');
    expect(roman.items_by_kind).toEqual({ entity: 1, chronicle: 1, story: 1, tag: 1 });
    expect(battles.cover).toBeNull();
    expect(battles.subtitle).toBeNull();

    const sparse = CollectionListSchema.parse({ data: [{ slug: 's', title: 'S', items_by_kind: 'junk' }] });
    expect(sparse.data[0]).toMatchObject({
      description: null,
      cover: null,
      item_count: 0,
      items_by_kind: { entity: 0, chronicle: 0, story: 0, tag: 0 },
    });
  });

  it('drops unknown keys (sort_order) rather than failing', () => {
    const list = CollectionListSchema.parse(collectionListPayload);
    expect(list.data[0]).not.toHaveProperty('sort_order');
  });

  it('keeps resolved items in the author’s order and drops broken ones', () => {
    const set = CollectionSchema.parse(collectionDetailPayload.data);
    expect(set.items.map((i) => i.kind)).toEqual(['chronicle', 'story', 'entity', 'tag']);
    const [chronicle, story, entity, tag] = set.items;
    expect(chronicle).toMatchObject({ note: 'Start here.', chronicle: { slug: 'the-roman-world', entry_count: 80 } });
    expect(story.kind === 'story' && story.story.entity?.name).toBe('Battle of Cannae');
    expect(entity.note).toBeNull();
    expect(tag.kind === 'tag' && tag.tag.facet).toBe('era');
  });

  it('treats a missing items array as an empty set', () => {
    expect(CollectionSchema.parse({ slug: 's', title: 'S' }).items).toEqual([]);
    expect(CollectionSchema.parse({ slug: 's', title: 'S', items: null }).items).toEqual([]);
  });

  it('types one item by kind', () => {
    expect(toCollectionItem({ kind: 'entity', entity: entityRow })?.kind).toBe('entity');
    expect(toCollectionItem({ kind: 'chronicle', chronicle: chronicleRow, note: 'n' })).toMatchObject({
      kind: 'chronicle',
      note: 'n',
    });
    expect(toCollectionItem({ kind: 'story', entity: entityRow })).toBeNull();
    expect(toCollectionItem('nonsense')).toBeNull();
  });
});

describe('map-story list schema', () => {
  it('parses rows with their entity and chronicle, tolerating junk', () => {
    const list = MapStoryListSchema.parse(mapStoryListPayload);
    expect(list.meta).toEqual({ current_page: 1, last_page: 2, per_page: 3, total: 5 });
    const [cannae, alesia, plague] = list.data;
    expect(cannae).toMatchObject({ slug: 'battle-of-cannae', year: -216, entity: { name: 'Battle of Cannae' } });
    expect(alesia.entity).toBeNull();
    expect(alesia.chronicle).toEqual({ slug: 'gallic-wars', title: 'The Gallic Wars' });
    expect(plague).toMatchObject({ year: null, step_count: null, chronicle: null });
    expect(plague.entity).toEqual({ id: 'e5', name: 'Black Death', entity_type: null });
    expect(plague).not.toHaveProperty('extra_field');
  });

  it('accepts the bare summary shape (entity and chronicle absent)', () => {
    const bare = { ...storyRow, entity: undefined, chronicle: undefined };
    const list = MapStoryListSchema.parse({ data: [bare], meta: mapStoryListPayload.meta });
    expect(list.data[0]).toMatchObject({ entity: null, chronicle: null });
  });
});
