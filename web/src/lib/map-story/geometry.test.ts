import { describe, expect, it } from 'vitest';
import { MapStoryDocumentSchema } from '@/lib/schemas/map-story';
import type { LngLat } from '@/lib/schemas/map-story';
import { bearing, dest, distance, formation, resolveFrames, stepBounds, tween } from './geometry';

const C: LngLat = [16.13, 41.3];

function story(steps: unknown[]) {
  return MapStoryDocumentSchema.parse({
    schema: 1,
    slug: 'test',
    kind: 'battle',
    entity: { name: 'Battle of Test' },
    title: 'Battle of Test',
    year: -216,
    sides: [
      { id: 'a', name: 'A', color: '#b91c1c' },
      { id: 'b', name: 'B', color: '#1d4ed8' },
    ],
    units: [
      { id: 'foot', side: 'a', kind: 'infantry', label: 'Foot' },
      { id: 'horse', side: 'b', kind: 'cavalry', label: 'Horse' },
      { id: 'general', side: 'a', kind: 'commander', label: 'General' },
    ],
    steps,
  });
}

describe('resolveFrames', () => {
  it('carries placements forward and overrides only the keys a step sets', () => {
    const doc = story([
      { id: 's1', title: 'One', positions: { foot: { at: C, facing: 90, width: 800, depth: 40 } } },
      { id: 's2', title: 'Two', positions: { foot: { state: 'engaged' } } },
    ]);
    const [one, two] = resolveFrames(doc);
    expect(one.get('foot')).toMatchObject({ at: C, facing: 90, width: 800, state: 'ready' });
    expect(two.get('foot')).toMatchObject({ at: C, facing: 90, width: 800, state: 'engaged' });
  });

  it('leaves units off the field until placed, and drops hidden ones', () => {
    const doc = story([
      { id: 's1', title: 'One', positions: { foot: { at: C } } },
      { id: 's2', title: 'Two', positions: { horse: { at: dest(C, 0, 500), state: 'hidden' } } },
      { id: 's3', title: 'Three', positions: { horse: { state: 'ready' } } },
    ]);
    const frames = resolveFrames(doc);
    expect(frames[0].has('horse')).toBe(false);
    expect(frames[1].has('horse')).toBe(false);
    expect(frames[2].has('horse')).toBe(true);
  });

  it('pins a marker just behind the unit it rides with', () => {
    const doc = story([
      {
        id: 's1',
        title: 'One',
        positions: { foot: { at: C, facing: 0, width: 600, depth: 40 }, general: { with: 'foot' } },
      },
    ]);
    const general = resolveFrames(doc)[0].get('general');
    expect(general?.with).toBe('foot');
    // Behind (south of) a north-facing line, by half its depth plus a margin.
    expect(general!.at[1]).toBeLessThan(C[1]);
    expect(distance(C, general!.at)).toBeCloseTo(80, 0);
  });
});

describe('formation', () => {
  const base = { at: C, facing: 0, width: 1000, depth: 100, curve: 0, state: 'ready' as const, label: null, strength: null, with: null };

  it('draws a block width-wide across its facing', () => {
    const { ring, front } = formation({ ...base, shape: 'block' });
    expect(ring[0]).toEqual(ring[ring.length - 1]);
    expect(distance(front[0], front[front.length - 1])).toBeCloseTo(1000, -1);
    // The front edge lies north of the centre for a north-facing block.
    expect(front[0][1]).toBeGreaterThan(C[1]);
  });

  it('bows a crescent toward its front, centred on `at`', () => {
    const { front } = formation({ ...base, shape: 'crescent', curve: 200 });
    const middle = front[Math.floor(front.length / 2)];
    const tip = front[0];
    expect(distance(C, middle)).toBeCloseTo(50 + 100, -1);
    expect(middle[1]).toBeGreaterThan(tip[1]);
  });
});

describe('tween', () => {
  it('slides a unit along its move arrow, then lands on the new placement', () => {
    const end = dest(C, 90, 1000);
    const doc = story([
      { id: 's1', title: 'One', positions: { horse: { at: C, facing: 90 } } },
      { id: 's2', title: 'Two', positions: { horse: { at: end } } },
    ]);
    const [a, b] = resolveFrames(doc);
    // A detour north: halfway along the path is off the straight line.
    const detour = dest(dest(C, 90, 500), 0, 400);
    const mid = tween(a, b, [{ unit: 'horse', type: 'flank', path: [C, detour, end] }], 0.5).get('horse')!;
    expect(mid.at[1]).toBeGreaterThan(C[1] + 0.001);
    expect(tween(a, b, [], 1).get('horse')!.at).toEqual(end);
  });

  it('turns the short way round', () => {
    const doc = story([
      { id: 's1', title: 'One', positions: { foot: { at: C, facing: 350 } } },
      { id: 's2', title: 'Two', positions: { foot: { facing: 10 } } },
    ]);
    const [a, b] = resolveFrames(doc);
    const facing = tween(a, b, [], 0.5).get('foot')!.facing;
    expect(((facing % 360) + 360) % 360).toBeCloseTo(0, 5);
  });
});

describe('stepBounds', () => {
  it('covers units, arrows and notes', () => {
    const far = dest(C, 45, 3000);
    const doc = story([
      {
        id: 's1',
        title: 'One',
        positions: { foot: { at: C, width: 200 } },
        notes: [{ at: far, text: 'Here' }],
      },
    ]);
    const b = stepBounds(doc, resolveFrames(doc)[0], 0)!;
    expect(b[1][0]).toBeGreaterThanOrEqual(far[0]);
    expect(b[1][1]).toBeGreaterThanOrEqual(far[1]);
    expect(bearing(C, far)).toBeCloseTo(45, 0);
  });
});
