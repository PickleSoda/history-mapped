import { describe, expect, it } from 'vitest';
import { chronicleHref, entityHref, inAppPath } from './atlas-links';

const ORIGIN = 'https://historymapped.org';

describe('atlas links', () => {
  it('open the full page in the atlas at /app', () => {
    expect(entityHref('e1')).toBe('/app?sel=e1&full=1');
    expect(chronicleHref('punic-wars')).toBe('/app?chron=punic-wars&full=1');
  });
});

describe('inAppPath', () => {
  it('turns a same-origin URL into a router path', () => {
    expect(inAppPath(`${ORIGIN}/app?sel=e1&full=1`, ORIGIN)).toBe('/app?sel=e1&full=1');
    expect(inAppPath(`${ORIGIN}/entities/e1#about`, ORIGIN)).toBe('/entities/e1#about');
  });

  it('maps a link made when the atlas lived at / onto /app', () => {
    expect(inAppPath(`${ORIGIN}/?sel=e1&full=1`, ORIGIN)).toBe('/app?sel=e1&full=1');
    expect(inAppPath(`${ORIGIN}/`, ORIGIN)).toBe('/');
  });

  it('rejects other origins and junk', () => {
    expect(inAppPath('https://example.org/?sel=e1', ORIGIN)).toBeNull();
    expect(inAppPath(null, ORIGIN)).toBeNull();
    expect(inAppPath('http://[bad', ORIGIN)).toBeNull();
  });
});
