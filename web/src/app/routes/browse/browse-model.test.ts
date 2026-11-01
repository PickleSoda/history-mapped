import { describe, expect, it } from 'vitest';
import { CollectionSchema } from '@/lib/schemas/collection';
import { collectionDetailPayload } from '@/lib/schemas/collection.fixtures';
import type { Tag } from '@/lib/schemas/tag';
import { indexTags } from '@/lib/tags';
import {
  cardTags,
  entityImage,
  childTags,
  chronicleTypeTag,
  countItemsByKind,
  facetSections,
  filterItems,
  itemKindFilters,
  itemsByKindLabel,
  markdownParagraphs,
  numberItems,
  resolveFacetRoute,
  safeLinkTarget,
  storyKindName,
  storyKinds,
  tagCountsLabel,
  tagLineage,
  tagTree,
  yearRangeLabel,
} from './browse-model';

function tag(slug: string, facet: Tag['facet'], parent: string | null = null, counts: [number, number] = [1, 1]): Tag {
  return {
    slug,
    name: slug.toUpperCase(),
    facet,
    parent,
    description: null,
    start_year: null,
    end_year: null,
    chronicle_count: counts[0],
    entity_count: counts[1],
  };
}

const vocab = [
  tag('prehistory', 'era'),
  tag('neolithic', 'era', 'prehistory'),
  tag('medieval', 'era'),
  tag('asia', 'region'),
  tag('middle-east', 'region', 'asia'),
  tag('mesopotamia', 'region', 'middle-east'),
  tag('east-asia', 'region', 'asia'),
  tag('polar', 'region', null, [0, 0]),
  tag('lost', 'region', 'nowhere'),
  tag('ghost', 'region', null, [0, 0]),
  tag('ghost-child', 'region', 'ghost'),
  tag('war', 'theme'),
  tag('regional', 'type', null, [12, 0]),
  tag('vikings', 'topic'),
];
const index = indexTags(vocab);
const tags = [...index.values()];

describe('tag grids', () => {
  it('builds facet sections for era, region, theme and type only', () => {
    const sections = facetSections(tags);
    expect(sections.map((s) => s.facet)).toEqual(['era', 'region', 'theme', 'type']);
    expect(sections[3].heading).toBe('Kinds of chronicle');
  });

  it('nests regions under parents, keeps vocabulary order, drops unused leaves', () => {
    const roots = tagTree(tags, 'region');
    // polar is unused and childless → dropped; ghost is unused but has a used child → kept;
    // lost points at an unknown parent → a root.
    expect(roots.map((n) => n.tag.slug)).toEqual(['asia', 'lost', 'ghost']);
    const asia = roots[0];
    expect(asia.children.map((n) => n.tag.slug)).toEqual(['middle-east', 'east-asia']);
    expect(asia.children[0].children.map((n) => n.tag.slug)).toEqual(['mesopotamia']);
    expect(roots[2].children.map((n) => n.tag.slug)).toEqual(['ghost-child']);
  });

  it('nests sub-eras and leaves flat facets flat', () => {
    expect(tagTree(tags, 'era').map((n) => [n.tag.slug, n.children.map((c) => c.tag.slug)])).toEqual([
      ['prehistory', ['neolithic']],
      ['medieval', []],
    ]);
    expect(tagTree(tags, 'theme')).toHaveLength(1);
  });

  it('survives a parent cycle', () => {
    const cyclic = indexTags([tag('a', 'region', 'b'), tag('b', 'region', 'a'), tag('c', 'region')]);
    expect(tagTree([...cyclic.values()], 'region').map((n) => n.tag.slug)).toEqual(['c']);
  });

  it('lists used children and the lineage for a facet page', () => {
    expect(childTags('asia', tags).map((t) => t.slug)).toEqual(['middle-east', 'east-asia']);
    expect(childTags('ghost', tags).map((t) => t.slug)).toEqual(['ghost-child']);
    expect(tagLineage('mesopotamia', index).map((t) => t.slug)).toEqual(['asia', 'middle-east']);
    expect(tagLineage('asia', index)).toEqual([]);
  });
});

describe('facet route', () => {
  it('resolves, redirects across facets, or is not found', () => {
    expect(resolveFacetRoute('era', 'medieval', index)).toMatchObject({ status: 'ok', tag: { slug: 'medieval' } });
    expect(resolveFacetRoute('topic', 'vikings', index).status).toBe('ok');
    expect(resolveFacetRoute('era', 'asia', index)).toMatchObject({ status: 'redirect', facet: 'region' });
    expect(resolveFacetRoute('era', 'atlantis', index).status).toBe('not-found');
    expect(resolveFacetRoute('colour', 'medieval', index).status).toBe('not-found');
  });
});

describe('labels', () => {
  it('formats year spans', () => {
    expect(yearRangeLabel(500, 1499)).toBe('500 – 1499 CE');
    expect(yearRangeLabel(-3000, -501)).toBe('3000 – 501 BCE');
    expect(yearRangeLabel(-500, 499)).toBe('500 BCE – 499 CE');
    expect(yearRangeLabel(null, -3001)).toBe('until 3001 BCE');
    expect(yearRangeLabel(1945, null)).toBe('from 1945 CE');
    expect(yearRangeLabel(-216, -216)).toBe('216 BCE');
    expect(yearRangeLabel(null, null)).toBeNull();
  });

  it('counts tags and set items', () => {
    expect(tagCountsLabel({ chronicle_count: 1, entity_count: 1259 })).toBe('1 chronicle · 1,259 entities');
    expect(tagCountsLabel({ chronicle_count: 12, entity_count: 0 })).toBe('12 chronicles');
    expect(tagCountsLabel({ chronicle_count: 0, entity_count: 0 })).toBeNull();
    expect(itemsByKindLabel({ entity: 5, chronicle: 3, story: 1, tag: 0 })).toBe(
      '3 chronicles · 1 battle map · 5 entities',
    );
    expect(itemsByKindLabel({ entity: 0, chronicle: 0, story: 0, tag: 0 })).toBeNull();
  });
});

describe('cards', () => {
  const slugs = ['asia', 'middle-east', 'mesopotamia', 'medieval', 'war', 'regional', 'vikings'];

  it('finds the chronicle’s kind', () => {
    expect(chronicleTypeTag(slugs, index)?.slug).toBe('regional');
    expect(chronicleTypeTag(['medieval'], index)).toBeNull();
  });

  it('shows the most specific era / region / theme tags, minus the page’s own', () => {
    expect(cardTags(slugs, index).map((t) => t.slug)).toEqual(['medieval', 'mesopotamia', 'war']);
    expect(cardTags(slugs, index, 'medieval').map((t) => t.slug)).toEqual(['mesopotamia', 'war']);
    // On the Asia page, Mesopotamia (under Asia) still shows; Asia itself is implied anyway.
    expect(cardTags(slugs, index, 'mesopotamia', 5).map((t) => t.slug)).toEqual(['medieval', 'war']);
  });
});

describe('collection items', () => {
  const set = CollectionSchema.parse(collectionDetailPayload.data);

  it('numbers items in the author’s order and keeps numbers through a filter', () => {
    const numbered = numberItems(set.items);
    expect(numbered.map((i) => [i.position, i.key])).toEqual([
      [1, 'chronicle:the-roman-world'],
      [2, 'story:battle-of-cannae'],
      [3, 'entity:6f1c2f4e-0000-4000-8000-000000000001'],
      [4, 'tag:classical'],
    ]);
    expect(filterItems(numbered, 'entity').map((i) => i.position)).toEqual([3]);
    expect(filterItems(numbered, null)).toHaveLength(4);
  });

  it('drops a repeated item', () => {
    expect(numberItems([...set.items, set.items[0]])).toHaveLength(4);
  });

  it('offers kind filters only when there is more than one kind', () => {
    const counts = countItemsByKind(numberItems(set.items));
    expect(counts).toEqual({ entity: 1, chronicle: 1, story: 1, tag: 1 });
    expect(itemKindFilters(counts)).toEqual(['chronicle', 'story', 'entity', 'tag']);
    expect(itemKindFilters({ entity: 4, chronicle: 0, story: 0, tag: 0 })).toEqual([]);
  });
});

describe('story kinds', () => {
  it('names and counts kinds, most common first', () => {
    expect(storyKindName('naval_battle')).toBe('Naval battles');
    expect(storyKindName('river_crossing')).toBe('River crossing');
    const kinds = storyKinds([{ kind: 'siege' }, { kind: 'battle' }, { kind: 'battle' }, { kind: 'epidemic' }]);
    expect(kinds).toEqual([
      { kind: 'battle', count: 2 },
      { kind: 'epidemic', count: 1 },
      { kind: 'siege', count: 1 },
    ]);
  });
});

describe('markdown subset', () => {
  it('splits paragraphs and keeps safe links', () => {
    const paras = markdownParagraphs(
      'Rome grew **fast**\nand far.\n\nSee [the Empire](/entities/abc), [Wikipedia](https://en.wikipedia.org/wiki/Rome) and [this](javascript:alert(1)).',
    );
    expect(paras).toHaveLength(2);
    expect(paras[0]).toEqual([{ type: 'text', text: 'Rome grew fast and far.' }]);
    expect(paras[1]).toEqual([
      { type: 'text', text: 'See ' },
      { type: 'link', text: 'the Empire', to: '/entities/abc', external: false },
      { type: 'text', text: ', ' },
      { type: 'link', text: 'Wikipedia', to: 'https://en.wikipedia.org/wiki/Rome', external: true },
      { type: 'text', text: ' and this).' },
    ]);
  });

  it('drops heading and list markers, and handles empty input', () => {
    expect(markdownParagraphs('# Title\n\n- one\n- two')).toEqual([
      [{ type: 'text', text: 'Title' }],
      [{ type: 'text', text: 'one two' }],
    ]);
    expect(markdownParagraphs(null)).toEqual([]);
  });

  it('accepts only in-app paths and http(s)/mailto links', () => {
    expect(safeLinkTarget('/browse')).toEqual({ to: '/browse', external: false });
    expect(safeLinkTarget('//evil.example')).toBeNull();
    expect(safeLinkTarget('mailto:a@b.c')?.external).toBe(true);
    expect(safeLinkTarget('data:text/html,x')).toBeNull();
  });
});

describe('entity images', () => {
  it('reads an image or media_refs when the summary carries one', () => {
    expect(entityImage(null)).toBeNull();
    expect(entityImage({})).toBeNull();
    expect(entityImage({ media_refs: ['https://upload.wikimedia.org/a.jpg'] })?.url).toBe(
      'https://upload.wikimedia.org/a.jpg',
    );
    expect(
      entityImage({ image: { url: 'https://upload.wikimedia.org/b.png', kind: 'flag', author: 'X' } }),
    ).toMatchObject({ kind: 'flag', credit: { author: 'X' } });
  });
});
