import { describe, expect, it } from 'vitest';
import { MapStoryDocumentSchema } from '@/lib/schemas/map-story';
import type { LngLat } from '@/lib/schemas/map-story';
import { contingentShade, storyPalette, unitColor } from './colors';
import {
  bearing,
  dest,
  distance,
  formation,
  movePath,
  onField,
  rankBands,
  resolveBeats,
  resolveConditions,
  resolveFrames,
  resolveTerrainState,
  stepBounds,
  tween,
} from './geometry';

const C: LngLat = [16.13, 41.3];

function story(steps: unknown[], extra: Record<string, unknown> = {}) {
  return MapStoryDocumentSchema.parse({
    schema: 2,
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
      { id: 'reserve', side: 'a', kind: 'infantry', label: 'Reserve' },
      { id: 'fleet', side: 'b', kind: 'ship', label: 'Flagship' },
    ],
    terrain: [{ id: 'farm', kind: 'farm', label: 'Farm', at: C }],
    steps,
    ...extra,
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

describe('schema 2 parsing', () => {
  it('degrades unknown v2 enums and malformed extras instead of failing the story', () => {
    const doc = story([
      {
        id: 's1',
        title: 'One',
        light: 'eclipse',
        wind: { from: 'north' },
        positions: { foot: { at: C, state: 'vaporised', lines: 3 } },
        moves: [{ unit: 'foot', type: 'teleport', path: [C, C], continues: { toward: 'Rome' } }],
        beats: [{ label: 'Then', positions: { foot: { facing: 10 } } }],
      },
    ]);
    const step = doc.steps[0];
    expect(step.light).toBeUndefined();
    expect(step.wind).toBeUndefined();
    expect(step.positions.foot.state).toBeUndefined();
    expect(step.positions.foot.lines).toBe(3);
    expect(step.moves[0].type).toBe('advance');
    expect(step.moves[0].continues).toBeUndefined();
    expect(step.beats[0].label).toBe('Then');
    expect(doc.alt_sites).toEqual([]);
  });
});

describe('beats', () => {
  const doc = story([
    { id: 's1', title: 'One', positions: { foot: { at: C, facing: 0 } } },
    {
      id: 's2',
      title: 'Two',
      positions: { foot: { facing: 90 } },
      beats: [
        { label: 'Flee', positions: { foot: { at: dest(C, 180, 400) } } },
        { label: 'Wheel', positions: { foot: { facing: 0, state: 'engaged' } } },
      ],
    },
    { id: 's3', title: 'Three', positions: { horse: { at: dest(C, 0, 900) } } },
  ]);

  it('resolves the frame before the beats, then one per beat', () => {
    const frames = resolveBeats(doc, 1);
    expect(frames).toHaveLength(3);
    expect(frames[0].get('foot')).toMatchObject({ at: C, facing: 90 });
    expect(frames[1].get('foot')!.at[1]).toBeLessThan(C[1]);
    expect(frames[2].get('foot')).toMatchObject({ facing: 0, state: 'engaged' });
  });

  it('carries the state after the last beat forward as the step\'s frame', () => {
    const frames = resolveFrames(doc);
    expect(frames[1]).toEqual(resolveBeats(doc, 1)[2]);
    expect(frames[2].get('foot')).toMatchObject({ facing: 0, state: 'engaged' });
    expect(resolveBeats(doc, 0)).toHaveLength(1);
  });
});

describe('detach and merge', () => {
  const doc = story([
    { id: 's1', title: 'One', positions: { foot: { at: C, facing: 0, width: 800 } } },
    { id: 's2', title: 'Two', positions: { reserve: { from: 'foot', at: dest(C, 90, 1000), width: 200 } } },
    { id: 's3', title: 'Three', positions: { reserve: { into: 'foot' } } },
    { id: 's4', title: 'Four', positions: { foot: { state: 'engaged' } } },
  ]);
  const frames = resolveFrames(doc);

  it('marks a detached unit for one step, stands a merging one on its target, then hides it', () => {
    expect(frames[1].get('reserve')).toMatchObject({ from: 'foot', into: null });
    expect(frames[2].get('reserve')).toMatchObject({ at: C, into: 'foot' });
    expect(onField(frames[2].get('reserve')!)).toBe(false);
    expect(frames[3].has('reserve')).toBe(false);
    // `from` doesn't carry forward.
    expect(frames[2].get('foot')!.from).toBeNull();
  });

  it('tweens a detached unit out of its parent and a merged one into its target', () => {
    const out = tween(frames[0], frames[1], [], 0.02).get('reserve')!;
    expect(distance(out.at, C)).toBeLessThan(60);
    const mid = tween(frames[1], frames[2], [], 0.5).get('reserve')!;
    expect(distance(mid.at, C)).toBeCloseTo(500, -1);
    expect(onField(mid)).toBe(true);
    expect(tween(frames[1], frames[2], [], 0.95).get('reserve')!.fade).toBeLessThan(0.2);
    // Once merged it is gone, not left standing for the next step's move.
    expect(tween(frames[2], frames[3], [], 0.5).has('reserve')).toBe(false);
  });

  it('starts a detached unit placed without `at` where its parent stands', () => {
    const d = story([
      { id: 's1', title: 'One', positions: { foot: { at: C } } },
      { id: 's2', title: 'Two', positions: { reserve: { from: 'foot' } } },
    ]);
    expect(resolveFrames(d)[1].get('reserve')!.at).toEqual(C);
  });
});

describe('orient: path', () => {
  const turn = dest(C, 90, 1000);
  const end = dest(turn, 0, 1000);
  const doc = story([
    { id: 's1', title: 'One', positions: { fleet: { at: C, facing: 90 } } },
    {
      id: 's2',
      title: 'Two',
      positions: { fleet: { at: end } },
      moves: [{ unit: 'fleet', type: 'advance', orient: 'path', path: [C, turn, end] }],
    },
  ]);

  it('lands facing along the last segment when the placement gives no facing', () => {
    expect(resolveFrames(doc)[1].get('fleet')!.facing).toBeCloseTo(0, 0);
  });

  it('follows the path tangent while tweening', () => {
    const [a, b] = resolveFrames(doc);
    const early = tween(a, b, doc.steps[1].moves, 0.3).get('fleet')!;
    expect(((early.facing % 360) + 360) % 360).toBeCloseTo(90, -1);
    const late = tween(a, b, doc.steps[1].moves, 0.7).get('fleet')!;
    expect(((late.facing % 360) + 360) % 360).toBeLessThan(10);
  });
});

describe('terrain state and conditions', () => {
  const doc = story([
    { id: 's1', title: 'One', light: 'night', wind: { from: 315, strength: 'strong' }, terrain_state: { farm: { held_by: 'a' } } },
    { id: 's2', title: 'Two', light: 'dawn', terrain_state: { farm: { state: 'burning' } } },
    { id: 's3', title: 'Three', wind: null, sun: { from: 90 }, terrain_state: { farm: { held_by: null } } },
    { id: 's4', title: 'Four', terrain_state: { farm: { state: null } } },
  ]);

  it('carries terrain state forward key by key, and clears it', () => {
    const holds = resolveTerrainState(doc);
    expect(holds[0].get('farm')).toEqual({ held_by: 'a', state: null, label: null });
    expect(holds[1].get('farm')).toEqual({ held_by: 'a', state: 'burning', label: null });
    expect(holds[2].get('farm')).toEqual({ held_by: null, state: 'burning', label: null });
    expect(holds[3].has('farm')).toBe(false);
  });

  it('carries light, wind and sun forward (light defaults to day)', () => {
    const c = resolveConditions(doc);
    expect(c.map((x) => x.light)).toEqual(['night', 'dawn', 'dawn', 'dawn']);
    expect(c[1].wind).toMatchObject({ from: 315, strength: 'strong' });
    expect(c[2].wind).toBeNull();
    expect(c[3].sun).toMatchObject({ from: 90 });
    expect(resolveConditions(story([{ id: 's', title: 'S' }]))[0].light).toBe('day');
  });
});

describe('formation detail', () => {
  const base = { at: C, facing: 0, width: 1200, depth: 120, curve: 0, shape: 'block' as const };
  const north = (ring: LngLat[]) => Math.max(...ring.map((p) => p[1]));
  const south = (ring: LngLat[]) => Math.min(...ring.map((p) => p[1]));

  it('stacks `lines` with gaps through the depth, the first at the front', () => {
    const { parts, fronts } = formation({ ...base, lines: 3 });
    expect(parts).toHaveLength(3);
    expect(fronts).toHaveLength(1);
    expect(north(parts[0][0])).toBeGreaterThan(north(parts[1][0]));
    // A gap between the front line and the second.
    expect(south(parts[0][0])).toBeGreaterThan(north(parts[1][0]));
  });

  it('cuts `lanes` through the formation', () => {
    const { parts } = formation({ ...base, lanes: 2 });
    expect(parts).toHaveLength(3);
    const east = (ring: LngLat[]) => Math.max(...ring.map((p) => p[0]));
    const west = (ring: LngLat[]) => Math.min(...ring.map((p) => p[0]));
    expect(west(parts[1][0])).toBeGreaterThan(east(parts[0][0]));
  });

  it('checkerboards `subunits` over several lines', () => {
    const { parts, fronts } = formation({ ...base, subunits: 4, lines: 2 });
    expect(parts).toHaveLength(8);
    expect(fronts).toHaveLength(4);
    const centreX = (ring: LngLat[]) => (Math.max(...ring.map((p) => p[0])) + Math.min(...ring.map((p) => p[0]))) / 2;
    // The rear line's first block sits behind the front line's first gap.
    const gap = (Math.max(...parts[0][0].map((p) => p[0])) + Math.min(...parts[1][0].map((p) => p[0]))) / 2;
    expect(centreX(parts[4][0])).toBeCloseTo(gap, 6);
  });

  it('draws `square` subunits as hollow squares', () => {
    const { parts } = formation({ ...base, shape: 'square', subunits: 3, width: 600, depth: 150 });
    expect(parts).toHaveLength(3);
    for (const p of parts) expect(p).toHaveLength(2);
  });

  it('splits a composite unit into rank bands, front to back', () => {
    const { centres, dividers } = rankBands({ ...base }, [0.25, 0.75]);
    expect(centres).toHaveLength(2);
    expect(dividers).toHaveLength(1);
    expect(centres[0][1]).toBeGreaterThan(centres[1][1]);
    expect(distance(C, centres[0])).toBeCloseTo(45, 0);
  });
});

describe('arrows', () => {
  it('ends a targeted fire arrow on its target, and bends an arc', () => {
    const doc = story([{ id: 's1', title: 'One', positions: { horse: { at: dest(C, 0, 800) } } }]);
    const frame = resolveFrames(doc)[0];
    const far = dest(C, 90, 5000);
    const path = movePath({ type: 'fire', path: [C, far], target: 'horse' }, frame);
    expect(path[path.length - 1]).toEqual(frame.get('horse')!.at);
    const arc = movePath({ type: 'fire', path: [C, far], arc: true }, frame);
    expect(arc.length).toBeGreaterThan(2);
    expect(arc[8][1]).toBeGreaterThan(C[1]);
  });
});

describe('stepBounds (v2)', () => {
  it('leaves out off-stage units and their arrows, tails and alternative sites', () => {
    const far = dest(C, 90, 20000);
    const doc = story(
      [
        {
          id: 's1',
          title: 'One',
          positions: { foot: { at: C, width: 200 }, horse: { at: far, frame: false } },
          moves: [
            { unit: 'horse', type: 'march', path: [far, dest(far, 270, 1000)] },
            { unit: 'foot', type: 'retreat', path: [C, dest(C, 0, 300)], continues: { toward: dest(C, 0, 30000), label: 'to Rome' } },
          ],
        },
      ],
      { alt_sites: [{ at: dest(C, 180, 15000), label: 'Elsewhere' }] },
    );
    const b = stepBounds(doc, resolveFrames(doc)[0], 0)!;
    expect(distance(b[0], b[1])).toBeLessThan(1000);
  });
});

describe('colours', () => {
  it('shades contingents deterministically, and prefers their own colour', () => {
    expect(contingentShade('#b91c1c', 0)).toBe(contingentShade('#b91c1c', 0));
    expect(contingentShade('#b91c1c', 0)).not.toBe(contingentShade('#b91c1c', 1));
    const side = {
      id: 'a',
      name: 'A',
      color: '#b91c1c',
      commanders: [],
      contingents: [
        { id: 'x', name: 'X', color: '#123456' },
        { id: 'y', name: 'Y' },
      ],
    };
    expect(unitColor(side, { contingent: 'x' })).toBe('#123456');
    expect(unitColor(side, { contingent: 'y' })).toBe(contingentShade('#b91c1c', 1));
    expect(unitColor(side, {})).toBe('#b91c1c');
    const doc = story([{ id: 's', title: 'S' }]);
    expect(storyPalette({ ...doc, sides: [side] })).toEqual(['#b91c1c', '#123456', contingentShade('#b91c1c', 1)]);
  });
});
