import { describe, expect, it } from 'vitest';
import {
  ATLAS_PATH,
  atlasHref,
  chroniclePagePath,
  collectionPath,
  docPath,
  entityPagePath,
  facetPath,
  isEntityId,
  parseStepParam,
  storiesPath,
} from './site-links';

describe('site paths', () => {
  it('builds the standalone page paths', () => {
    expect(entityPagePath('f26cde2f-d00e-47f6-8a34-fe2d9a96e71d')).toBe(
      '/entities/f26cde2f-d00e-47f6-8a34-fe2d9a96e71d',
    );
    expect(collectionPath('roman-world')).toBe('/browse/collections/roman-world');
    expect(facetPath('era', 'medieval')).toBe('/browse/era/medieval');
    expect(storiesPath()).toBe('/browse/stories');
    expect(docPath('frontend-app')).toBe('/docs/frontend-app');
    expect(docPath('')).toBe('/docs');
  });

  it('encodes path segments', () => {
    expect(facetPath('topic', 'a/b c')).toBe('/browse/topic/a%2Fb%20c');
    expect(entityPagePath('x?y')).toBe('/entities/x%3Fy');
  });

  it('adds a chronicle step only when it is a valid index', () => {
    expect(chroniclePagePath('punic-wars')).toBe('/chronicles/punic-wars');
    expect(chroniclePagePath('punic-wars', null)).toBe('/chronicles/punic-wars');
    expect(chroniclePagePath('punic-wars', 0)).toBe('/chronicles/punic-wars?step=0');
    expect(chroniclePagePath('punic-wars', 4)).toBe('/chronicles/punic-wars?step=4');
    expect(chroniclePagePath('punic-wars', -1)).toBe('/chronicles/punic-wars');
    expect(chroniclePagePath('punic-wars', 1.5)).toBe('/chronicles/punic-wars');
  });

  it('parses ?step= as a non-negative integer', () => {
    expect(parseStepParam('3')).toBe(3);
    expect(parseStepParam('0')).toBe(0);
    expect(parseStepParam(null)).toBeNull();
    expect(parseStepParam('')).toBeNull();
    expect(parseStepParam('-2')).toBeNull();
    expect(parseStepParam('2.5')).toBeNull();
    expect(parseStepParam('abc')).toBeNull();
  });

  it('recognises entity ids', () => {
    expect(isEntityId('f26cde2f-d00e-47f6-8a34-fe2d9a96e71d')).toBe(true);
    expect(isEntityId('F26CDE2F-D00E-47F6-8A34-FE2D9A96E71D')).toBe(true);
    expect(isEntityId('x')).toBe(false);
    expect(isEntityId('Q1747689')).toBe(false);
    expect(isEntityId(undefined)).toBe(false);
  });
});

describe('atlasHref', () => {
  it('is the bare atlas without params', () => {
    expect(ATLAS_PATH).toBe('/app');
    expect(atlasHref()).toBe('/app');
    expect(atlasHref({ sel: null, full: false, year: null })).toBe('/app');
  });

  it('builds the open-on-the-globe links', () => {
    expect(atlasHref({ sel: 'e1', full: true })).toBe('/app?sel=e1&full=1');
    expect(atlasHref({ chron: 'punic-wars', full: true })).toBe('/app?chron=punic-wars&full=1');
    expect(atlasHref({ chron: 'punic-wars', step: 3, full: true })).toBe(
      '/app?chron=punic-wars&step=3&full=1',
    );
  });

  it('writes the year as the `t` instant', () => {
    expect(atlasHref({ sel: 'e1', year: -216 })).toBe('/app?sel=e1&t=-216');
    expect(atlasHref({ year: 1453 })).toBe('/app?t=1453');
  });

  it('leaves default (0) and orphan steps out', () => {
    expect(atlasHref({ story: 'cannae' })).toBe('/app?story=cannae');
    expect(atlasHref({ story: 'cannae', sstep: 0 })).toBe('/app?story=cannae');
    expect(atlasHref({ story: 'cannae', sstep: 2 })).toBe('/app?story=cannae&sstep=2');
    expect(atlasHref({ chron: 'x', step: 0 })).toBe('/app?chron=x');
    expect(atlasHref({ step: 2, sstep: 3 })).toBe('/app');
  });

  it('encodes values', () => {
    expect(atlasHref({ chron: 'a&b' })).toBe('/app?chron=a%26b');
  });
});
