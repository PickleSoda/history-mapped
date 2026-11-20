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
  reachedBefore,
  relationKind,
  screenBearing,
  spreadOf,
  stepAnchor,
  stepScene,
  stepSpread,
  TRAIL_KEEP,
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
type Reach = ChroniclePlace['reaches'][number];
const place = (
  id: string,
  group: string,
  at: LngLat | null,
  borders: Border[] = [],
  reaches: Reach[] = [],
): ChroniclePlace => ({ id, group, at, borders, reaches });
const border = (id: number, from: number | null, to: number | null, primary = false): Border => ({ id, from, to, primary });
const reach = (id: string, year: number | null = null): Reach => ({ id, year });

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
    expect(scene.arcs).toHaveLength(1);
    expect(scene.arcs[0].geometry.coordinates[0]).toEqual(CARTHAGE);
    expect(scene.arcs[0].properties.dashed).toBe(false);
    expect(scene.arrows).toHaveLength(1);
    // From a polity's point, somewhere inside its realm: the line fades in.
    expect(scene.soft).toBe(true);
    // Rome took part: it is joined to the battlefield by a spoke. Carthage is on the arc.
    expect(scene.spokes).toHaveLength(1);
    expect(scene.spokes[0].properties?.id).toBe('rome');
    expect(scene.cast.map((m) => [m.id, m.primary, m.marked])).toEqual([
      ['carthage', true, true],
      ['cannae', true, true],
      ['rome', false, false],
    ]);
    expect(scene.areas).toEqual({ primary: [-1001], other: [-1002] });
    // One ripple, where it happens.
    expect(scene.pulses).toEqual([CANNAE]);
  });

  it('shows rule as a territory, not a line', () => {
    const ruler = summary('hannibal', 'Hannibal', 'PERSON', 'person');
    const scene = stepScene(entry({ type: 'rules', source: ruler, target: carthage }), places);
    expect(scene.kind).toBe('control');
    expect(scene.arcs).toEqual([]);
    expect(scene.areas.primary).toEqual([-1001]);
    expect(scene.cast.map((m) => m.id)).toEqual(['carthage']);
  });

  it('draws no line for a relationship that is not about places', () => {
    const scene = stepScene(entry({ type: 'authored', source: carthage, target: cannae }), places);
    expect(scene.arcs).toEqual([]);
    expect(scene.arrows).toEqual([]);
    expect(scene.cast).toHaveLength(2);
  });

  it('reverses "X destroyed_by Y" to travel from Y', () => {
    const rome = summary('rome', 'Roman Republic', 'POLITY', 'state');
    const scene = stepScene(entry({ type: 'destroyed_by', source: carthage, target: rome }), places);
    expect(scene.arcs[0].geometry.coordinates[0]).toEqual(ROME);
  });

  it('dashes a succession and gives it no arrowhead glow', () => {
    const rome = summary('rome', 'Roman Republic', 'POLITY', 'state');
    const scene = stepScene(entry({ type: 'succeeded_by', source: carthage, target: rome }), placesIndex([place('carthage', 'polity', CARTHAGE), place('rome', 'polity', ROME)]));
    expect(scene.arcs[0].properties.dashed).toBe(true);
  });

  it('gives a place a ring, never a line to another place', () => {
    const siege = summary('cannae', 'Siege', 'EVENT', 'siege');
    const withPlaces = placesIndex([
      place('carthage', 'polity', CARTHAGE),
      place('cannae', 'event', CANNAE),
      place('rome', 'polity', ROME),
      // A town a day's march from the battlefield.
      place('town', 'place', [16.6, 41.1]),
    ]);
    const scene = stepScene(
      entry({ source: carthage, target: siege, secondary: [{ entity_id: 'rome', name: 'Rome' }, { entity_id: 'town', name: 'Town' }] }),
      withPlaces,
    );
    // Rome, which took part, is tied to the battlefield; the town is only shown.
    expect(scene.spokes.map((f) => f.properties?.id)).toEqual(['rome']);
    expect(scene.cast.find((m) => m.id === 'town')?.marked).toBe(false);
  });

  it('rings each place of a step that names several, and ties nothing to one of them', () => {
    const several = placesIndex([
      place('florence', 'place', [11.25, 43.77]),
      place('siena', 'place', [11.33, 43.32]),
      place('venice', 'place', [12.34, 45.44]),
      place('republic', 'polity', [11.0, 43.5]),
    ]);
    const florence = summary('florence', 'Florence', 'PLACE', 'city');
    const republic = summary('republic', 'Republic of Florence', 'POLITY', 'state');
    const scene = stepScene(
      entry({
        type: 'part_of',
        source: florence,
        target: republic,
        secondary: [{ entity_id: 'siena', name: 'Siena' }, { entity_id: 'venice', name: 'Venice' }],
        year: 1348,
      }),
      several,
    );
    expect(scene.spokes).toEqual([]);
    expect(scene.pulses).toEqual([
      [11.25, 43.77],
      [11.33, 43.32],
      [12.34, 45.44],
    ]);
    expect(scene.cast.filter((m) => m.marked).map((m) => m.id)).toEqual(['florence', 'republic', 'siena', 'venice']);
  });

  it('counts places a short walk apart as one', () => {
    const near = placesIndex([place('city', 'place', [2.35, 48.86]), place('abbey', 'place', [2.36, 48.85]), place('king', 'polity', ROME)]);
    const scene = stepScene(
      entry({ secondary: [{ entity_id: 'city', name: 'Paris' }, { entity_id: 'abbey', name: 'Abbey' }, { entity_id: 'king', name: 'Kingdom' }] }),
      near,
    );
    expect(scene.pulses).toHaveLength(1);
    expect(scene.spokes.map((f) => f.properties?.id)).toEqual(['king']);
  });
});

describe('a spread', () => {
  const CAMP: LngLat = [-96.8, 39.1];
  const BREST: LngLat = [-4.49, 48.39];
  const FREETOWN: LngLat = [-13.23, 8.48];
  const BOSTON: LngLat = [-71.06, 42.36];
  const APIA: LngLat = [-171.77, -13.83];
  const flu = summary('flu', '1918 influenza pandemic', 'EVENT', 'epidemic_disease');
  const camp = summary('camp', 'Camp Funston', 'PLACE', 'city');
  const boston = summary('boston', 'Boston', 'PLACE', 'city');
  const usa = summary('usa', 'United States', 'POLITY', 'political_entity');
  const apia = summary('apia', 'Apia', 'PLACE', 'city');
  const second = (id: string, name: string) => ({ entity_id: id, name });
  const fluReaches = ['camp', 'brest', 'freetown', 'boston', 'apia', 'usa', 'spain'].map((id) => reach(id, 1918));
  const places = placesIndex([
    place('flu', 'event', null, [], fluReaches),
    place('camp', 'place', CAMP),
    place('brest', 'place', BREST),
    place('freetown', 'place', FREETOWN),
    place('boston', 'place', BOSTON),
    place('apia', 'place', APIA),
    place('usa', 'polity', [-98.58, 39.83], [border(-148838, 1900, null, true)]),
    place('france', 'polity', [2.2, 46.2], [border(-2202162, 1900, null, true)]),
    place('spain', 'polity', [-3.7, 40.4], [border(-1311341, 1900, null, true)]),
  ]);
  // The three 1918 steps of the pandemics chronicle, as the pipeline stored them.
  const firstWave = entry({ type: 'located_at', source: flu, target: camp, secondary: [second('usa', 'United States'), second('spain', 'Spain')], year: 1918 });
  const secondWave = entry({
    type: 'part_of',
    source: boston,
    target: usa,
    secondary: [second('france', 'France'), second('flu', 'Influenza'), second('brest', 'Brest'), second('freetown', 'Freetown')],
    year: 1918,
  });
  const samoa = entry({ type: 'spread_to', source: flu, target: apia, year: 1918 });
  const starts = (scene: ReturnType<typeof stepScene>) => scene.arcs.map((arc) => arc.geometry.coordinates[0]);

  it('finds what a step says the spreading thing reached', () => {
    expect(spreadOf(secondWave, places, 'flu')).toEqual({
      carrier: 'flu',
      // In the step's order: the relationship's ends first.
      reached: ['boston', 'usa', 'brest', 'freetown'],
      // The places it names; the realm is shown by its border, not by an arc.
      sites: [
        { id: 'boston', at: BOSTON, soft: false },
        { id: 'brest', at: BREST, soft: false },
        { id: 'freetown', at: FREETOWN, soft: false },
      ],
    });
    expect(spreadOf(secondWave, places, 'boston')).toBeNull();
    expect(stepSpread(secondWave, places)?.carrier).toBe('flu');
  });

  it('has nowhere to come from at its first appearance: rings and tinted borders only', () => {
    const scene = stepScene(firstWave, places);
    expect(scene.kind).toBe('flow');
    expect(scene.arcs).toEqual([]);
    expect(scene.pulses).toEqual([CAMP]);
    // The realms it is recorded as reaching are outlined in the spread's colour.
    expect(scene.areas.primary).toEqual([-148838, -1311341]);
    // No line from Spain, listed only for the name "Spanish flu".
    expect(scene.spokes).toEqual([]);
  });

  it('fans out to every place of the step from where it was last seen', () => {
    const scene = stepScene(secondWave, places, [firstWave]);
    // "Boston, part of the United States" is the step's relationship; the step is drawn as the spread.
    expect(scene.kind).toBe('flow');
    expect(scene.arcs).toHaveLength(3);
    expect(starts(scene)).toEqual([CAMP, CAMP, CAMP]);
    expect(scene.arrows).toHaveLength(3);
    expect(scene.soft).toBe(false);
    expect(scene.spokes).toEqual([]);
    // Equal rings at the three ports.
    expect(scene.pulses).toEqual([BOSTON, BREST, FREETOWN]);
    expect(scene.cast.filter((m) => m.marked).map((m) => m.id)).toEqual(['boston', 'usa', 'brest', 'freetown']);
    // France is in the step but not recorded as reached: its border stays grey.
    expect(scene.areas).toEqual({ primary: [-148838], other: [-2202162] });
  });

  it('comes from the nearest place it had reached', () => {
    const scene = stepScene(samoa, places, [firstWave, secondWave]);
    expect(reachedBefore([firstWave, secondWave], places, 'flu').map((site) => site.id)).toEqual(['camp', 'boston', 'brest', 'freetown']);
    expect(scene.arcs).toHaveLength(1);
    // Kansas is nearer Samoa than any Atlantic port.
    expect(starts(scene)).toEqual([CAMP]);
    const end = scene.arcs[0].geometry.coordinates.at(-1) as LngLat;
    expect(distanceKm(end, APIA)).toBeLessThan(600);
  });

  it('draws no arc to a place it had already reached', () => {
    const again = entry({ type: 'spread_to', source: flu, target: boston, year: 1919 });
    const scene = stepScene(again, places, [firstWave, secondWave]);
    expect(scene.arcs).toEqual([]);
    expect(scene.pulses).toEqual([BOSTON]);
  });

  it("starts at the thing's own point when no step has placed it yet", () => {
    const withPoint = placesIndex([place('flu', 'event', [-98.58, 39.83], [], fluReaches), place('apia', 'place', APIA)]);
    expect(starts(stepScene(samoa, withPoint))).toEqual([[-98.58, 39.83]]);
  });

  it('ignores a link from another time', () => {
    const fever = summary('fever', 'Yellow fever', 'EVENT', 'epidemic_disease');
    const old = placesIndex([place('fever', 'event', null, [], [reach('usa', 1793)]), place('usa', 'polity', [-98.58, 39.83])]);
    const canal = entry({ type: 'part_of', source: boston, target: usa, secondary: [second('fever', 'Yellow fever')], year: 1904 });
    expect(stepSpread(canal, old)).toBeNull();
    expect(stepScene(canal, old).kind).toBe('control');
    // The same link in its own years, and one with no year, do count.
    expect(stepSpread(entry({ type: 'spread_to', source: fever, target: usa, year: 1799 }), old)?.reached).toEqual(['usa']);
    const undated = placesIndex([place('fever', 'event', null, [], [reach('usa')]), place('usa', 'polity', [-98.58, 39.83])]);
    expect(stepSpread(canal, undated)?.reached).toEqual(['usa']);
  });

  it('leaves a fight its own line', () => {
    const army = summary('usa', 'United States', 'POLITY', 'political_entity');
    const battle = summary('boston', 'Battle of Boston', 'EVENT', 'battle');
    const scene = stepScene(entry({ type: 'victorious_at', source: army, target: battle, secondary: [second('flu', 'Influenza')], year: 1918 }), places);
    expect(scene.kind).toBe('conflict');
    expect(scene.arcs).toHaveLength(1);
  });

  it('leaves a trade between two others its own line', () => {
    const brest = summary('brest', 'Brest', 'PLACE', 'city');
    const scene = stepScene(entry({ type: 'trades_with', source: boston, target: brest, secondary: [second('flu', 'Influenza')], year: 1918 }), places, [firstWave]);
    expect(scene.arcs).toHaveLength(1);
    expect(starts(scene)).toEqual([BOSTON]);
  });

  it('ends at a realm when the step names no place, fading in from another realm', () => {
    const buddhism = summary('buddhism', 'Buddhism', 'CULTURE', 'religious_movement');
    const korea = summary('korea', 'Baekje', 'POLITY', 'political_entity');
    const japan = summary('japan', 'Yamato', 'POLITY', 'political_entity');
    const east = placesIndex([
      place('buddhism', 'culture', null, [], [reach('korea', 384), reach('japan', 552)]),
      place('korea', 'polity', [127.0, 36.5]),
      place('japan', 'polity', [135.8, 34.7]),
    ]);
    const toKorea = entry({ type: 'spread_to', source: buddhism, target: korea, year: 384 });
    // "Yamato adopted Buddhism": the adopter is the source of the relationship.
    const toJapan = entry({ type: 'adopted', source: japan, target: buddhism, year: 552 });
    const scene = stepScene(toJapan, east, [toKorea]);
    expect(scene.kind).toBe('flow');
    expect(starts(scene)).toEqual([[127.0, 36.5]]);
    expect(scene.soft).toBe(true);
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

  it('keeps only the last few stops of a long chronicle', () => {
    // Twelve steps round the Mediterranean, each at its own place.
    const ring = Array.from({ length: 12 }, (_, i) => place(`p${i}`, 'place', [i * 3, 35 + (i % 3)] as LngLat));
    const long = ring.map((p) => at(p.id));
    const fc = trailCollection(trailStops(long, placesIndex(ring), 11), 11);
    const stops = fc.features.filter((f) => f.properties?.role === 'stop');
    expect(stops).toHaveLength(TRAIL_KEEP);
    expect(stops.map((f) => f.properties?.label)).toEqual(['7', '8', '9', '10', '11']);
    // A segment between each pair of kept stops, and one into the current step.
    const segments = fc.features.filter((f) => f.properties?.role === 'segment');
    expect(segments.map((f) => f.properties?.age)).toEqual([4, 3, 2, 1, 0]);
    expect(trailCollection(trailStops(long, placesIndex(ring), 11), 11, 2).features.filter((f) => f.properties?.role === 'stop')).toHaveLength(2);
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
