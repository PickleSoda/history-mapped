import { describe, expect, it } from 'vitest';
import { globeHref, siteHref, tagOpens } from './page-nav';
import type { PageNavIntent } from './page-nav';

/** The atlas state a site-mode navigation must never write into the page it
 *  is on (it may only appear on a fresh `/app?…` link). */
const ATLAS_KEYS = ['sel', 'chron', 'step', 'story', 'sstep', 'full'];

describe('siteHref', () => {
  it('keeps entities, chronicles and tags on the site', () => {
    expect(siteHref({ kind: 'entity', id: 'e1' })).toBe('/entities/e1');
    expect(siteHref({ kind: 'chronicle', slug: 'punic-wars' })).toBe('/chronicles/punic-wars');
    expect(siteHref({ kind: 'chronicle', slug: 'punic-wars', step: 3 })).toBe('/chronicles/punic-wars?step=3');
    expect(siteHref({ kind: 'tag', facet: 'era', slug: 'medieval' })).toBe('/browse/era/medieval');
  });

  it('sends what needs the map to the globe', () => {
    expect(siteHref({ kind: 'story', slug: 'cannae' })).toBe('/app?story=cannae');
    expect(siteHref({ kind: 'story', slug: 'cannae', step: 4 })).toBe('/app?story=cannae&sstep=4');
    expect(siteHref({ kind: 'map', entityId: 'e1' })).toBe('/app?sel=e1');
    expect(siteHref({ kind: 'map', entityId: 'e1', year: -216 })).toBe('/app?sel=e1&t=-216');
  });

  it('never writes atlas state outside /app', () => {
    const intents: PageNavIntent[] = [
      { kind: 'entity', id: 'e1' },
      { kind: 'chronicle', slug: 'c', step: 2 },
      { kind: 'tag', facet: 'region', slug: 'china' },
      { kind: 'story', slug: 's', step: 1 },
      { kind: 'map', entityId: 'e1', year: 10 },
    ];
    for (const intent of intents) {
      const url = new URL(siteHref(intent), 'https://example.org');
      if (url.pathname === '/app') continue;
      for (const key of ATLAS_KEYS) {
        // The chronicle page's own `?step=` is the page's step, not tour state.
        if (key === 'step' && url.pathname.startsWith('/chronicles/')) continue;
        expect(url.searchParams.has(key), `${siteHref(intent)} carries ${key}`).toBe(false);
      }
    }
  });
});

describe('globeHref', () => {
  it('opens the same page expanded in the atlas', () => {
    expect(globeHref({ kind: 'entity', id: 'e1' })).toBe('/app?sel=e1&full=1');
    expect(globeHref({ kind: 'chronicle', slug: 'punic-wars' })).toBe('/app?chron=punic-wars&full=1');
    expect(globeHref({ kind: 'chronicle', slug: 'punic-wars', step: 5 })).toBe(
      '/app?chron=punic-wars&step=5&full=1',
    );
  });
});

describe('tagOpens', () => {
  const tag = (chronicle_count: number, entity_count: number) => ({ chronicle_count, entity_count });

  it('opens chronicle tags in the atlas (the Chronicles tab filter)', () => {
    expect(tagOpens('atlas', tag(3, 0))).toBe(true);
    expect(tagOpens('atlas', tag(0, 40))).toBe(false);
  });

  it('opens any tag with content on the site (its browse page)', () => {
    expect(tagOpens('site', tag(3, 0))).toBe(true);
    expect(tagOpens('site', tag(0, 40))).toBe(true);
    expect(tagOpens('site', tag(0, 0))).toBe(false);
  });
});
