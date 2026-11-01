import { describe, expect, it } from 'vitest';
import { legacyAtlasRedirect } from './legacy-redirect';

describe('legacyAtlasRedirect', () => {
  it('sends `/` with a query to `/app` with the same query', () => {
    expect(legacyAtlasRedirect({ pathname: '/', search: '?sel=e1&full=1' })).toBe('/app?sel=e1&full=1');
    expect(legacyAtlasRedirect({ pathname: '/', search: '?chron=punic-wars&step=3' })).toBe(
      '/app?chron=punic-wars&step=3',
    );
    expect(legacyAtlasRedirect({ pathname: '/', search: '?story=cannae&sstep=2' })).toBe(
      '/app?story=cannae&sstep=2',
    );
  });

  it('keeps the hash and tolerates a search without `?`', () => {
    expect(legacyAtlasRedirect({ pathname: '/', search: '?sel=e1', hash: '#x' })).toBe('/app?sel=e1#x');
    expect(legacyAtlasRedirect({ pathname: '/', search: 'sel=e1' })).toBe('/app?sel=e1');
  });

  it('leaves the bare landing alone', () => {
    expect(legacyAtlasRedirect({ pathname: '/', search: '' })).toBeNull();
    expect(legacyAtlasRedirect({ pathname: '/', search: '?' })).toBeNull();
    expect(legacyAtlasRedirect({ pathname: '/', search: '', hash: '#why' })).toBeNull();
  });

  it('leaves every other path alone', () => {
    expect(legacyAtlasRedirect({ pathname: '/app', search: '?sel=e1' })).toBeNull();
    expect(legacyAtlasRedirect({ pathname: '/browse', search: '?q=rome' })).toBeNull();
    expect(legacyAtlasRedirect({ pathname: '/login', search: '?next=%2F' })).toBeNull();
  });
});
