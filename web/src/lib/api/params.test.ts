import { describe, expect, it } from 'vitest';
import type { Scope } from '@/types/atlas';
import { listParams, mapParams } from './params';

const scope: Scope = {
  z: 4,
  bbox: { w: -10, s: 35, e: 30, n: 60 },
  outer: { w: -20, s: 30, e: 40, n: 65 },
  core: { w: 0, s: 40, e: 20, n: 55 },
  time: { kind: 'instant', year: 100 },
  groups: [],
};

describe('mapParams', () => {
  it('fetches the outer box at the map zoom', () => {
    const p = mapParams(scope, 'outer');
    expect(p).toMatchObject({ bbox_min_lng: -20, bbox_max_lng: 40, zoom_level: 4, year: 100 });
  });

  it('fetches the core box as if zoomed closer', () => {
    const p = mapParams(scope, 'core');
    expect(p).toMatchObject({ bbox_min_lng: 0, bbox_max_lat: 55, zoom_level: 7 });
  });

  it('caps the boosted zoom at 22', () => {
    expect(mapParams({ ...scope, z: 21 }, 'core').zoom_level).toBe(22);
  });
});

describe('listParams', () => {
  it('ranks only the visible area', () => {
    expect(listParams(scope)).toMatchObject({
      bbox_min_lng: -10,
      bbox_min_lat: 35,
      bbox_max_lng: 30,
      bbox_max_lat: 60,
      exists_at: 100,
    });
  });
});
