import { describe, expect, it } from 'vitest';
import { ChronicleEntrySchema } from '@/lib/schemas/chronicle';
import type { ChronicleEntry, ChroniclePlace } from '@/lib/schemas/chronicle';
import type { LngLat } from '@/lib/schemas/map-story';
import { arcGradient } from './layers';
import {
  arcPath,
  bordersAt,
  distanceKm,
  placesIndex,
  relationKind,
  screenBearing,
  stepAnchor,
  stepScene,
  trailCollection,
  trailStops,
  trimPath,
  unwrap,
} from './scene';

const CARTHAGE: LngLat = [10.32, 36.85];
const CANNAE: LngLat = [16.13, 41.3];
const ROME: LngLat = [12.5, 41.9];

function summary(id: string, name: string, group: string, type: string | null = null) {
  return { id, name, entity_group: group, entity_type: type };
}

function entry(over: {
  type?: string;
  source?: ReturnType<typeof summary>;
  target?: ReturnType<typeof summary>;
  secondary?: { entity_id: string; name: string; role?: string }[];
  approx?: unknown;
  year?: number;
}): ChronicleEntry {
  return ChronicleEntrySchema.parse({
    entry_id: 'e1',
    sequence_order: 1,
    start_year: over.year ?? -216,
    approximate_location: over.approx ?? null,
    narrative_text: 'Hannibal encircles the Romans. The legions are destroyed.',
    primary_relationship:
      over.source && over.target
        ? {
            id: 'r1',
            source_entity_id: over.source.id,
            target_entity_id: over.target.id,
            relationship_type: over.type ?? 'victorious_at',
            confidence: 'high',
            source_entity: over.source,
            target_entity: over.target,
          }
        : null,
    secondary_entities: (over.secondary ?? []).map((s) => ({ role: 'participant', entity_type: null, ...s })),
  });
}

type Border = ChroniclePlace['borders'][number];
const place = (id: string, group: string, at: LngLat | null, borders: Border[] = []): ChroniclePlace => ({ id, group, at, borders });
const border = (id: number, from: number | null, to: number | null, primary = false): Border => ({ id, from, to, primary });

describe('relationKind', () => {
  it('sorts the common step types into kinds', () => {
    expect(relationKind('victorious_at')).toBe('conflict');
    expect(relationKind('spread_to')).toBe('flow');
    expect(relationKind('succeeded_by')).toBe('succession');
    expect(relationKind('capital_of')).toBe('control');
    expect(relationKind('founded')).toBe('life');
    expect(relationKind('allied_with')).toBe('alliance');
    expect(relationKind('authored')).toBe('none');
    expect(relationKind('something_new')).toBe('link');
    expect(relationKind(null)).toBe('link');
  });

  it('makes taking part a conflict only when an end is a fight', () => {
    expect(relationKind('participated_in', ['empire', 'battle'])).toBe('conflict');
    expect(relationKind('participated_in', ['person', 'council'])).toBe('link');
    expect(relationKind('commanded', ['person', 'siege'])).toBe('conflict');
  });
});

describe('geometry', () => {
  it('arcs from one end to the other, bowed off the straight line', () => {
    const path = arcPath(CARTHAGE, CANNAE);
    expect(path[0]).toEqual(CARTHAGE);
    expect(path[path.length - 1]).toEqual(CANNAE);
    const mid = path[Math.floor(path.length / 2)];
    const straight: LngLat = [(CARTHAGE[0] + CANNAE[0]) / 2, (CARTHAGE[1] + CANNAE[1]) / 2];
    expect(distanceKm(mid, straight)).toBeGreaterThan(30);
  });

  it('takes the short way across the antimeridian', () => {
    expect(unwrap([179, 0], [-179, 0])).toEqual([181, 0]);
    const path = arcPath([179, 0], [-179, 0]);
    for (const [lng] of path) expect(lng).toBeGreaterThanOrEqual(178);
  });

  it('trims a path by length and keeps its start', () => {
    const path = arcPath(CARTHAGE, CANNAE);
    const cut = trimPath(path, 0.5);
    expect(cut[0]).toEqual(CARTHAGE);
    const full = distanceKm(CARTHAGE, CANNAE);
    expect(distanceKm(cut[cut.length - 1], CANNAE)).toBeGreaterThan(full * 0.35);
    expect(trimPath(path, 1)).toBe(path);
  });

  it('gives north as 0 and east as 90', () => {
    expect(screenBearing([0, 0], [0, 10])).toBeCloseTo(0);
    expect(screenBearing([0, 0], [10, 0])).toBeCloseTo(90);
  });
});

describe('stepScene', () => {
  const carthage = summary('carthage', 'Carthage', 'POLITY', 'state');
  const cannae = summary('cannae', 'Battle of Cannae', 'EVENT', 'battle');
  const places = placesIndex([
    place('carthage', 'polity', CARTHAGE, [border(-1001, -814, -146, true)]),
    place('cannae', 'event', CANNAE),
    place('rome', 'polity', ROME, [border(-1002, null, null), border(-1003, -100, 400)]),
    place('hannibal', 'person', null),
  ]);

  it('draws a battle as a red arc from the side to the battlefield, with an arrowhead', () => {
    const scene = stepScene(entry({ source: carthage, target: cannae, secondary: [{ entity_id: 'rome', name: 'Roman Republic' }] }), places);
    expect(scene.kind).toBe('conflict');
    expect(scene.anchor).toEqual(CANNAE);
    expect(scene.arc?.geometry.coordinates[0]).toEqual(CARTHAGE);
    expect(scene.arc?.properties.dashed).toBe(false);
    expect(scene.arrow).not.toBeNull();
    // From a polity's point, somewhere inside its realm: the line fades in.
    expect(scene.arc?.properties.soft).toBe(true);
    // Rome is joined to the battlefield by a spoke; Carthage is on the arc.
    expect(scene.spokes).toHaveLength(1);
    expect(scene.spokes[0].properties?.id).toBe('rome');
    expect(scene.cast.map((m) => [m.id, m.primary])).toEqual([
      ['carthage', true],
      ['cannae', true],
      ['rome', false],
    ]);
    expect(scene.areas).toEqual({ primary: [-1001], other: [-1002] });
  });

  it('shows rule as a territory, not a line', () => {
    const ruler = summary('hannibal', 'Hannibal', 'PERSON', 'person');
    const scene = stepScene(entry({ type: 'rules', source: ruler, target: carthage }), places);
    expect(scene.kind).toBe('control');
    expect(scene.arc).toBeNull();
    expect(scene.areas.primary).toEqual([-1001]);
    expect(scene.cast.map((m) => m.id)).toEqual(['carthage']);
  });

  it('draws no line for a relationship that is not about places', () => {
    const scene = stepScene(entry({ type: 'authored', source: carthage, target: cannae }), places);
    expect(scene.arc).toBeNull();
    expect(scene.cast).toHaveLength(2);
  });

  it('reverses "X destroyed_by Y" to travel from Y', () => {
    const rome = summary('rome', 'Roman Republic', 'POLITY', 'state');
    const scene = stepScene(entry({ type: 'destroyed_by', source: carthage, target: rome }), places);
    expect(scene.arc?.geometry.coordinates[0]).toEqual(ROME);
  });

  it('dashes a succession and gives it no arrowhead glow', () => {
    const rome = summary('rome', 'Roman Republic', 'POLITY', 'state');
    const scene = stepScene(entry({ type: 'succeeded_by', source: carthage, target: rome }), placesIndex([place('carthage', 'polity', CARTHAGE), place('rome', 'polity', ROME)]));
    expect(scene.arc?.properties.dashed).toBe(true);
  });
});

describe('stepAnchor', () => {
  const places = placesIndex([place('a', 'polity', CARTHAGE), place('b', 'place', ROME), place('c', 'event', CANNAE)]);

  it('prefers an entity in the location role', () => {
    const e = entry({ secondary: [{ entity_id: 'a', name: 'A' }, { entity_id: 'b', name: 'B', role: 'location' }] });
    expect(stepAnchor(e, places)).toEqual(ROME);
  });

  it('then an event or place, then the approximate location', () => {
    expect(stepAnchor(entry({ secondary: [{ entity_id: 'a', name: 'A' }, { entity_id: 'c', name: 'C' }] }), places)).toEqual(CANNAE);
    const approx = { type: 'Point', coordinates: [1, 2] };
    expect(stepAnchor(entry({ secondary: [{ entity_id: 'a', name: 'A' }], approx }), places)).toEqual([1, 2]);
    expect(stepAnchor(entry({ secondary: [{ entity_id: 'a', name: 'A' }] }), places)).toEqual(CARTHAGE);
  });

  it('is null for a step with nothing placed', () => {
    expect(stepAnchor(entry({ secondary: [{ entity_id: 'zzz', name: 'Z' }] }), places)).toBeNull();
  });
});

describe('the trail', () => {
  const places = placesIndex([place('a', 'place', CARTHAGE), place('b', 'place', ROME), place('c', 'event', CANNAE)]);
  const at = (id: string) => entry({ secondary: [{ entity_id: id, name: id }] });
  const entries = [at('a'), at('zzz'), at('b'), at('c')];

  it('stops at each placed step up to the current one', () => {
    expect(trailStops(entries, places, 2).map((s) => s.step)).toEqual([0, 2]);
    expect(trailStops(entries, places, 9).map((s) => s.step)).toEqual([0, 2, 3]);
  });

  it('numbers the earlier stops and fades older segments', () => {
    const fc = trailCollection(trailStops(entries, places, 3), 3);
    const stops = fc.features.filter((f) => f.properties?.role === 'stop');
    expect(stops.map((f) => f.properties?.label)).toEqual(['1', '3']);
    const segments = fc.features.filter((f) => f.properties?.role === 'segment');
    expect(segments.map((f) => f.properties?.age)).toEqual([1, 0]);
  });
});

describe('bordersAt', () => {
  const german = place('de', 'polity', null, [
    border(-2856857, 1878, 1890, true),
    border(-2691465, 1871, 1878),
    border(-2692425, 1890, 1918),
  ]);

  it("outlines the border version that stands in the step's year", () => {
    expect(bordersAt(german, 1914)).toEqual([-2692425]);
    expect(bordersAt(german, 1919)).toEqual([]);
    expect(bordersAt(german, null)).toEqual([]);
  });

  it('prefers the primary links when one covers the year', () => {
    expect(bordersAt(german, 1885)).toEqual([-2856857]);
    expect(bordersAt(german, 1890)).toEqual([-2856857]);
  });
});

describe('arcGradient', () => {
  const stops = (e: unknown) => (e as unknown[]).slice(3) as (number | string)[];
  const xs = (e: unknown) => stops(e).filter((_, i) => i % 2 === 0) as number[];
  const at = (e: unknown, x: number) => stops(e)[stops(e).indexOf(x) + 1];

  it('keeps its stops strictly ascending for any mix of growth, glow and soft start', () => {
    for (const grown of [0, 0.001, 0.1, 0.35, 0.5, 0.999, 1]) {
      for (const glowAt of [null, 0, 0.05, 0.5, 0.95, 1]) {
        const list = xs(arcGradient('#b91c1c', { soft: true, grown, glowAt }));
        for (let i = 1; i < list.length; i++) expect(list[i]).toBeGreaterThan(list[i - 1]);
      }
    }
  });

  it('is transparent beyond where it has grown, and faint at a soft start', () => {
    const e = arcGradient('#b91c1c', { soft: true, grown: 0.5, glowAt: null });
    expect(at(e, 0.6)).toBe('rgba(0,0,0,0)');
    expect(at(e, 0)).toBe('rgba(185,28,28,0.080)');
    expect(at(e, 0.4)).toBe('rgba(185,28,28,1.000)');
  });
});
