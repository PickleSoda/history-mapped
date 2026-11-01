import { describe, expect, it } from 'vitest';
import { plainText } from './browse-model';
import {
  atlasHref,
  chronicleAtlasHref,
  chroniclePagePath,
  collectionPath,
  entityAtlasHref,
  entityPagePath,
  facetPath,
  storiesPath,
  storyAtlasHref,
} from './links';
import { browseDocumentTitle } from './useBrowseDocumentTitle';

describe('browse links', () => {
  it('builds site paths', () => {
    expect(entityPagePath('a b')).toBe('/entities/a%20b');
    expect(chroniclePagePath('rome')).toBe('/chronicles/rome');
    expect(chroniclePagePath('rome', 3)).toBe('/chronicles/rome?step=3');
    expect(collectionPath('the-roman-world')).toBe('/browse/collections/the-roman-world');
    expect(facetPath('era', 'medieval')).toBe('/browse/era/medieval');
    expect(storiesPath()).toBe('/browse/stories');
  });

  it('builds globe links under /app', () => {
    expect(atlasHref()).toBe('/app');
    expect(atlasHref({ sel: 'x', y: null, q: '' })).toBe('/app?sel=x');
    expect(entityAtlasHref('e1')).toBe('/app?sel=e1&full=1');
    expect(chronicleAtlasHref('rome')).toBe('/app?chron=rome');
    expect(storyAtlasHref('battle-of-cannae')).toBe('/app?story=battle-of-cannae');
  });
});

describe('document meta', () => {
  it('titles pages after the site', () => {
    expect(browseDocumentTitle('Medieval')).toBe('Medieval · History Mapped');
    expect(browseDocumentTitle(null)).toBe('History Mapped');
  });

  it('flattens markdown into a short description', () => {
    expect(plainText('See [Rome](/x) **now**.\n\nMore.')).toBe('See Rome now. More.');
    const long = plainText('word '.repeat(60), 40);
    expect(long?.length).toBeLessThanOrEqual(40);
    expect(long?.endsWith('…')).toBe(true);
    expect(plainText('   ')).toBeNull();
  });
});
