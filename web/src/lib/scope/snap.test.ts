import { describe, expect, it } from 'vitest';
import type { Bbox, MapInsets } from '@/types/atlas';
import { cropBbox, snapBboxToTiles, snapScope } from './snap';
import { latToMercatorY } from './tiles';

const NONE: MapInsets = { top: 0, right: 0, bottom: 0, left: 0 };
const EUROPE: Bbox = { w: -25, s: 30, e: 65, n: 70 };
const time = { kind: 'instant', year: 100 } as const;

const contains = (outer: Bbox, inner: Bbox) =>
  outer.w <= inner.w && outer.e >= inner.e && outer.s <= inner.s && outer.n >= inner.n;

describe('cropBbox', () => {
  it('is the identity with no insets', () => {
    const b = cropBbox(EUROPE, NONE);
    expect(b.w).toBeCloseTo(EUROPE.w);
    expect(b.e).toBeCloseTo(EUROPE.e);
    expect(b.n).toBeCloseTo(EUROPE.n);
    expect(b.s).toBeCloseTo(EUROPE.s);
  });

  it('trims longitude linearly by the side shares', () => {
    const b = cropBbox(EUROPE, { ...NONE, left: 0.25, right: 0.1 });
    expect(b.w).toBeCloseTo(-25 + 90 * 0.25);
    expect(b.e).toBeCloseTo(65 - 90 * 0.1);
    expect(b.n).toBeCloseTo(70);
  });

  it('trims latitude in Mercator space, not degrees', () => {
    const b = cropBbox(EUROPE, { ...NONE, top: 0.5 });
    const mid = (latToMercatorY(70) + latToMercatorY(30)) / 2;
    expect(latToMercatorY(b.n)).toBeCloseTo(mid);
    // Degrees would put the cut at 50°; Mercator stretches the north, so the
    // screen midline sits further north.
    expect(b.n).toBeGreaterThan(50);
    expect(b.s).toBeCloseTo(30);
  });

  it('never leaves less than 30% of an axis', () => {
    const b = cropBbox(EUROPE, { ...NONE, top: 0.2, bottom: 1 });
    const visible =
      (latToMercatorY(b.n) - latToMercatorY(b.s)) /
      (latToMercatorY(70) - latToMercatorY(30));
    expect(visible).toBeCloseTo(0.3);
    expect(b.n).toBeLessThan(70);
  });
});

describe('snapBboxToTiles', () => {
  it('contains the input and only grows by the ring', () => {
    const tight = snapBboxToTiles(EUROPE, 4);
    const ringed = snapBboxToTiles(EUROPE, 4, 1);
    expect(contains(tight, EUROPE)).toBe(true);
    expect(contains(ringed, tight)).toBe(true);
    expect(ringed.e - ringed.w).toBeCloseTo(tight.e - tight.w + 2 * (360 / 16));
  });

  it('clamps to the world', () => {
    const b = snapBboxToTiles({ w: -200, s: -89, e: 200, n: 89 }, 2, 1);
    expect(b.w).toBe(-180);
    expect(b.e).toBe(180);
  });
});

describe('snapScope', () => {
  it('nests core ⊂ bbox ⊂ outer around the visible area', () => {
    const s = snapScope({ bbox: EUROPE, time, groups: [] });
    expect(contains(s.bbox, EUROPE)).toBe(true);
    expect(contains(s.outer, s.bbox)).toBe(true);
    expect(contains(s.bbox, s.core)).toBe(true);
    expect(s.core.e - s.core.w).toBeLessThan(s.bbox.e - s.bbox.w);
  });

  it('fetches far less than the old one-tile-at-z ring', () => {
    const s = snapScope({ bbox: EUROPE, time, groups: [] });
    const old = snapBboxToTiles(EUROPE, s.z, 1);
    expect(s.outer.e - s.outer.w).toBeLessThan((old.e - old.w) / 1.5);
    expect(s.outer.e - s.outer.w).toBeLessThan(2 * (EUROPE.e - EUROPE.w));
  });

  it('drops the area under the panels but keeps the zoom', () => {
    const open = snapScope({
      bbox: EUROPE,
      time,
      groups: [],
      insets: { ...NONE, left: 0.25, right: 0.25 },
    });
    const bare = snapScope({ bbox: EUROPE, time, groups: [] });
    expect(open.z).toBe(bare.z);
    expect(open.bbox.w).toBeGreaterThan(bare.bbox.w);
    expect(open.bbox.e).toBeLessThan(bare.bbox.e);
    // Still covers what is actually visible between the panels.
    expect(contains(open.bbox, cropBbox(EUROPE, { ...NONE, left: 0.25, right: 0.25 }))).toBe(
      true,
    );
  });

  it('is stable for a small pan (cache hit)', () => {
    const a = snapScope({ bbox: EUROPE, time, groups: [] });
    const b = snapScope({ bbox: { w: -24.5, s: 30.2, e: 65.5, n: 70.2 }, time, groups: [] });
    expect(b.bbox).toEqual(a.bbox);
    expect(b.outer).toEqual(a.outer);
  });
});
