import { describe, expect, it } from 'vitest';
import type { Tag } from '@/lib/schemas/tag';
import { ancestorsOf, childrenOf, displayTags, indexTags, toggleTag } from './tags';

function tag(slug: string, facet: Tag['facet'], parent: string | null = null): Tag {
  return {
    slug,
    name: slug.toUpperCase(),
    facet,
    parent,
    description: null,
    start_year: null,
    end_year: null,
    chronicle_count: 1,
    entity_count: 1,
  };
}

const vocab = [
  tag('medieval', 'era'),
  tag('asia', 'region'),
  tag('east-asia', 'region', 'asia'),
  tag('china', 'region', 'east-asia'),
  tag('japan', 'region', 'east-asia'),
  tag('europe', 'region'),
  tag('war', 'theme'),
  tag('polity', 'type'),
];
const index = indexTags(vocab);

describe('tags', () => {
  it('walks ancestors nearest first', () => {
    expect(ancestorsOf('china', index)).toEqual(['east-asia', 'asia']);
    expect(ancestorsOf('asia', index)).toEqual([]);
  });

  it('collapses implied ancestors and orders by vocabulary', () => {
    const shown = displayTags(['polity', 'asia', 'china', 'east-asia', 'medieval', 'vikings'], index);
    expect(shown.map((t) => t.slug)).toEqual(['medieval', 'china', 'polity', 'vikings']);
    expect(shown[3].facet).toBe('topic');
  });

  it('narrows instead of OR-ing when a descendant is picked', () => {
    expect(toggleTag(['asia', 'war'], 'china', index)).toEqual(['war', 'china']);
    expect(toggleTag(['china'], 'asia', index)).toEqual(['asia']);
    expect(toggleTag(['china', 'japan'], 'europe', index)).toEqual(['china', 'japan', 'europe']);
    expect(toggleTag(['china', 'war'], 'china', index)).toEqual(['war']);
  });

  it('lists top-level tags and children for drill-down', () => {
    const all = [...index.values()];
    expect(childrenOf(null, 'region', all).map((t) => t.slug)).toEqual(['asia', 'europe']);
    expect(childrenOf('east-asia', 'region', all).map((t) => t.slug)).toEqual(['china', 'japan']);
  });
});
