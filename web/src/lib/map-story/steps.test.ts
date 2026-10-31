/**
 * Schema 3: alias normalisation, step dates on the timeline, chronicle entry
 * matching, feature-state carry-forward, the per-step routes/regions/places,
 * the region crossfade, the legend and the ambient query's snapped box.
 */
import { describe, expect, it } from 'vitest';
import { MapStoryDocumentSchema, normalizeDocument } from '@/lib/schemas/map-story';
import type { LngLat } from '@/lib/schemas/map-story';
import { DISRUPTED_COLOR, featureColor, NEUTRAL_COLOR, REGION_COLORS, ROUTE_COLORS, storyLegend, storyPalette } from './colors';
import { resolveFeatureStates, resolveFrames } from './geometry';
import { ambientCollection, featureCollections, featurePoints, regionTransition, terrainCollection, unitCollections } from './layers';
import { chronicleStepIndex, formatStoryDate, snapAmbientBbox, stepYear } from './steps';

const RING: LngLat[] = [
  [10, 40],
  [20, 40],
  [20, 50],
];
const RING2: LngLat[] = [
  [30, 40],
  [35, 40],
  [35, 45],
];

function story(steps: unknown[], extra: Record<string, unknown> = {}) {
  return MapStoryDocumentSchema.parse({
    schema: 3,
    slug: 'plague',
    kind: 'epidemic',
    entity: { name: 'Black Death', wikidata: 'Q42005' },
    title: 'The Black Death',
    year: 1346,
    sides: [{ id: 'genoa', name: 'Genoa', color: '#1d4ed8' }],
    units: [{ id: 'galleys', kind: 'merchant_ship', label: 'Genoese galleys' }],
    features: [
      { id: 'caffa', kind: 'outbreak', label: 'Caffa', at: [35.38, 45.03], value_n: 100 },
      { id: 'messina', kind: 'port', label: 'Messina', at: [15.55, 38.19], active: false },
      { id: 'sea-lane', kind: 'route', route_kind: 'trade', line: [[35.38, 45.03], [15.55, 38.19]], goods: ['grain'], value_n: 50 },
      { id: 'spread', kind: 'region', region_kind: 'spread', area: RING, intensity: 0.2 },
      { id: 'river', kind: 'river', line: [[0, 0], [1, 1]] },
    ],
    steps,
    ...extra,
  });
}

describe('normalizeDocument', () => {
  it('reads v1/v2 `terrain` and `terrain_state` as `features`, and one ring as a list of rings', () => {
    const doc = MapStoryDocumentSchema.parse({
      schema: 2,
      slug: 'b',
      kind: 'battle',
      entity: { name: 'B' },
      title: 'B',
      year: 1066,
      sides: [],
      units: [],
      terrain: [{ id: 'wood', kind: 'woods', area: RING }],
      steps: [{ id: 's', title: 'S', terrain_state: { wood: { state: 'burning', area: RING2 } } }],
    });
    expect(doc.features).toHaveLength(1);
    expect(doc.features[0].area).toEqual([RING]);
    expect(doc.steps[0].features.wood).toMatchObject({ state: 'burning', area: [RING2] });
    expect(doc.entity).toMatchObject({ name: 'B' });
  });

  it('prefers the v3 names when a file has both, and leaves other values alone', () => {
    const out = normalizeDocument({
      terrain: [{ id: 'a', kind: 'hill' }],
      features: [{ id: 'b', kind: 'city', area: [RING, RING2] }],
      steps: [{ id: 's', terrain_state: { a: {} }, features: { b: { active: false } } }],
    }) as { features: { id: string; area: unknown }[]; steps: Record<string, unknown>[] };
    expect(out.features.map((f) => f.id)).toEqual(['b']);
    expect(out.features[0].area).toEqual([RING, RING2]);
    expect(out.steps[0]).toEqual({ id: 's', features: { b: { active: false } } });
    expect(normalizeDocument('nope')).toBe('nope');
  });

  it('parses a chronicle story without an entity, its dates, step entities, legend and period', () => {
    const doc = story(
      [
        {
          id: 's1',
          title: 'Caffa',
          date: { year: 1346, month: 9, end: { year: 1347, month: 2, day: 40 } },
          entry: 3,
          entities: [{ name: 'Golden Horde', wikidata: 'Q79965', entity_id: 'e-1', role: 'besiegers', show: true }],
        },
        { id: 's2', title: 'Sicily', date: { year: 'soon' }, entry_id: 42 },
      ],
      {
        entity: undefined,
        chronicle: { slug: 'plague-chronicle', chronicle_id: 'c-1' },
        ambient: true,
        legend: [{ swatch: '#7f1d1d', label: 'Plague reached', style: 'blob' }],
        period: { start: { year: 1346 }, end: { year: 1353 } },
      },
    );
    expect(doc.entity).toBeNull();
    expect(doc.chronicle).toEqual({ slug: 'plague-chronicle', chronicle_id: 'c-1' });
    expect(doc.ambient).toBe(true);
    expect(doc.period).toEqual({ start: { year: 1346 }, end: { year: 1353 } });
    expect(doc.legend).toEqual([{ swatch: '#7f1d1d', label: 'Plague reached', style: 'fill' }]);
    // A malformed day drops just the day; a malformed date drops the date.
    expect(doc.steps[0].date).toEqual({ year: 1346, month: 9, end: { year: 1347, month: 2 } });
    expect(doc.steps[1].date).toBeUndefined();
    expect(doc.steps[1].entry_id).toBe('42');
    expect(doc.steps[0].entities[0]).toMatchObject({ name: 'Golden Horde', entity_id: 'e-1', show: true });
    expect(doc.units[0].side).toBeUndefined();
  });
});

describe('steps on the timeline', () => {
  const doc = story([
    { id: 's1', title: 'One', date: { year: 1347, month: 10 } },
    { id: 's2', title: 'Two' },
    { id: 's3', title: 'Three', date: { year: -216, month: 8, day: 2 } },
  ]);

  it('puts each step at its own year, an undated step at the story year', () => {
    expect([0, 1, 2].map((i) => stepYear(doc, i))).toEqual([1347, 1346, -216]);
    expect(stepYear(doc, 9)).toBe(1346);
  });

  it('formats dates and spans for the player', () => {
    expect(formatStoryDate({ year: 1815, month: 6, day: 18 })).toBe('18 June 1815 CE');
    expect(formatStoryDate({ year: -216, month: 8, day: 2 })).toBe('2 August 216 BCE');
    expect(formatStoryDate({ year: 1348 })).toBe('1348 CE');
    expect(formatStoryDate({ year: 1348, month: 6, end: { year: 1348, month: 8 } })).toBe('June – August 1348 CE');
    expect(formatStoryDate({ year: 1347, month: 10, end: { year: 1348, month: 3 } })).toBe('October 1347 CE – March 1348 CE');
    expect(formatStoryDate({ year: 1347, end: { year: 1351 } })).toBe('1347 CE – 1351 CE');
  });

  it('matches a chronicle entry by its sequence number, else (no `entry`) by entry_id', () => {
    const chron = story([
      { id: 'a', title: 'A', entry: 0, entry_id: 'stale' },
      { id: 'b', title: 'B', entry: 4 },
      { id: 'c', title: 'C', entry_id: 'z' },
    ]);
    // A stale entry_id never beats the sequence number.
    expect(chronicleStepIndex(chron, { entry_id: 'new', sequence_order: 0 })).toBe(0);
    expect(chronicleStepIndex(chron, { entry_id: 'stale', sequence_order: 7 })).toBe(-1);
    expect(chronicleStepIndex(chron, { entry_id: 'y', sequence_order: 4 })).toBe(1);
    expect(chronicleStepIndex(chron, { entry_id: 'z', sequence_order: 9 })).toBe(2);
    expect(chronicleStepIndex(chron, undefined)).toBe(-1);
  });
});

describe('feature state', () => {
  const doc = story([
    { id: 's1', title: 'One', features: { caffa: { state: 'infected', value_n: 40, value_label: '≈40%' }, spread: { intensity: 0.5 } } },
    { id: 's2', title: 'Two', features: { messina: { active: true }, caffa: { value_n: null }, spread: { area: [RING, RING2] } } },
    { id: 's3', title: 'Three', features: { spread: { area_from_entity: { wikidata: 'Q1', entity_id: 'eu' } }, 'sea-lane': { state: 'disrupted' } } },
    { id: 's4', title: 'Four', features: { spread: { area: RING2 }, caffa: null } },
  ]);
  const holds = resolveFeatureStates(doc);

  it('carries each key forward on its own; null clears a key, a null entry the feature', () => {
    expect(holds[0].get('caffa')).toMatchObject({ state: 'infected', value_n: 40, value_label: '≈40%' });
    expect(holds[1].get('caffa')).toMatchObject({ state: 'infected', value_n: null, value_label: '≈40%' });
    expect(holds[2].get('caffa')).toMatchObject({ state: 'infected', value_label: '≈40%' });
    expect(holds[3].has('caffa')).toBe(false);
    expect(holds[2].get('messina')?.active).toBe(true);
  });

  it('lets the latest geometry win: an area replaces an entity area and vice versa', () => {
    expect(holds[1].get('spread')).toMatchObject({ intensity: 0.5, area: [RING, RING2], area_entity: null });
    expect(holds[2].get('spread')).toMatchObject({ intensity: 0.5, area: null, area_entity: { entity_id: 'eu' } });
    expect(holds[3].get('spread')).toMatchObject({ area: [RING2], area_entity: null });
  });

  it('draws routes, regions and places per step, hiding inactive ones', () => {
    const one = featureCollections(doc, holds[0]);
    expect(one.places.features.filter((f) => f.properties?.role === 'place').map((f) => f.properties?.id)).toEqual(['caffa']);
    const caffa = one.places.features.find((f) => f.properties?.id === 'caffa')!;
    expect(caffa.properties).toMatchObject({ color: '#991b1b', text: 'Caffa\n≈40%', state: 'infected' });
    expect(one.places.features.some((f) => f.properties?.role === 'badge' && f.properties.icon === 'story-tstate-infected')).toBe(true);
    const route = one.routes.features[0].properties!;
    expect(route).toMatchObject({ color: ROUTE_COLORS.trade, goods: 'grain', flow: true, disrupted: false });
    const region = one.regions.features.find((f) => f.properties?.role === 'area')!;
    expect(region.geometry.type).toBe('Polygon');
    expect(region.properties?.shade).toBeCloseTo(0.1 + 0.45 * 0.5);

    const two = featureCollections(doc, holds[1]);
    expect(two.places.features.filter((f) => f.properties?.role === 'place')).toHaveLength(2);
    expect(two.regions.features.find((f) => f.properties?.role === 'area')!.geometry.type).toBe('MultiPolygon');

    // An entity's area waits for its geometry; then it is drawn from it.
    const three = featureCollections(doc, holds[2]);
    expect(three.regions.features).toHaveLength(0);
    expect(three.routes.features[0].properties).toMatchObject({ disrupted: true, flow: false });
    const geom = { type: 'Polygon', coordinates: [[[0, 0], [5, 0], [5, 5], [0, 0]]] };
    const withEntity = featureCollections(doc, holds[2], new Map([['eu', { type: 'Feature', geometry: geom }]]));
    expect(withEntity.regions.features[0].geometry).toBe(geom);
    expect(withEntity.regionRefs.get('spread')).toBe(geom);

    // Static terrain stays out of the per-step sets, and in the terrain source.
    expect(terrainCollection(doc).features.map((f) => f.properties?.kind)).toEqual(['river']);
    expect(featurePoints(one).length).toBeGreaterThan(4);
  });

  it('crossfades a reshaped region and reshades one that keeps its shape', () => {
    const a = featureCollections(doc, holds[0]);
    const b = featureCollections(doc, holds[1]);
    const first = regionTransition(new Map(), a);
    expect(first.current.features[0].properties?.xf).toBe(true);
    expect(first.changed).toBe(true);
    const same = regionTransition(first.shown, a);
    expect(same.changed).toBe(false);
    expect(same.current.features[0].properties).toMatchObject({ xf: false, shade0: same.current.features[0].properties?.shade });
    const reshaped = regionTransition(first.shown, b);
    expect(reshaped.current.features[0].properties?.xf).toBe(true);
    expect(reshaped.old.features).toHaveLength(1);
    // Same shape, new intensity: no crossfade, a blend from the old shade.
    const darker = story([
      { id: 's1', title: 'One' },
      { id: 's2', title: 'Two', features: { spread: { intensity: 1 } } },
    ]);
    const dh = resolveFeatureStates(darker);
    const d0 = regionTransition(new Map(), featureCollections(darker, dh[0]));
    const d1 = regionTransition(d0.shown, featureCollections(darker, dh[1]));
    expect(d1.old.features).toHaveLength(0);
    expect(d1.changed).toBe(true);
    expect(d1.current.features[0].properties).toMatchObject({ xf: false, shade0: 0.1 + 0.45 * 0.2, shade: 0.55 });
  });
});

describe('colours and legend', () => {
  it("colours a feature by its holder's side, then its own side, then the palette", () => {
    const sides = new Map([
      ['a', { id: 'a', name: 'A', color: '#111111', commanders: [], contingents: [] }],
      ['b', { id: 'b', name: 'B', color: '#222222', commanders: [], contingents: [] }],
    ]);
    const region = { kind: 'region', region_kind: 'spread', route_kind: null, side: 'b' };
    expect(featureColor(sides, region, 'a')).toBe('#111111');
    expect(featureColor(sides, region)).toBe('#222222');
    expect(featureColor(sides, { ...region, side: null })).toBe(REGION_COLORS.spread);
    expect(featureColor(sides, { kind: 'mine', side: null })).toBe(NEUTRAL_COLOR);
  });

  it('draws a unit without a side in the neutral colour, and registers it', () => {
    const doc = story([{ id: 's1', title: 'One', positions: { galleys: { at: [20, 40] } } }]);
    const { points } = unitCollections(doc, resolveFrames(doc)[0], []);
    expect(points.features[0].properties).toMatchObject({ color: NEUTRAL_COLOR, role: 'pin' });
    expect(storyPalette(doc)).toContain(NEUTRAL_COLOR);
  });

  it("lists the story's own legend, then the kinds it draws, without repeats", () => {
    const doc = story([{ id: 's1', title: 'One', features: { 'sea-lane': { state: 'disrupted' } } }], {
      legend: [{ swatch: '#7F1D1D', label: 'Plague reached', style: 'fill' }],
    });
    expect(storyLegend(doc).map((l) => l.label)).toEqual(['Plague reached', 'Outbreak', 'Port', 'Trade route', 'Disrupted']);
    expect(storyLegend(doc)[4]).toEqual({ swatch: DISRUPTED_COLOR, label: 'Disrupted', style: 'line' });
  });
});

describe('ambient', () => {
  it('snaps the viewport outward to a tile grid, wrapping longitudes', () => {
    expect(snapAmbientBbox({ w: -10.3, s: 35.2, e: 30.4, n: 60.1 })).toEqual([-45, 0, 45, 90]);
    expect(snapAmbientBbox({ w: 2.1, s: 45.3, e: 4.9, n: 47.2 })).toEqual([0, 45, 5.625, 47.8125]);
    // Small pans inside the same tiles give the same key.
    expect(snapAmbientBbox({ w: -9, s: 36, e: 31, n: 61 })).toEqual(snapAmbientBbox({ w: -10.3, s: 35.2, e: 30.4, n: 60.1 }));
    expect(snapAmbientBbox({ w: -400, s: -80, e: 20, n: 80 })).toEqual([-180, -90, 180, 90]);
    // Across the antimeridian: west > east.
    const [w, , e] = snapAmbientBbox({ w: 170, s: -10, e: 190, n: 10 });
    expect(w).toBeGreaterThan(e);
  });

  it('tags every feature with its story and sizes values against the view', () => {
    const fc = ambientCollection([
      {
        slug: 'black-death',
        kind: 'epidemic',
        title: 'The Black Death',
        step_index: 5,
        step_title: 'Paris',
        features: {
          type: 'FeatureCollection',
          features: [
            { type: 'Feature', geometry: { type: 'Point', coordinates: [2, 48] }, properties: { id: 'paris', value_n: 50, color: '#991b1b', intensity: null } },
            { type: 'Feature', geometry: { type: 'Point', coordinates: [12, 41] }, properties: { id: 'rome', value_n: 200, color: null } },
          ],
        },
      },
    ]);
    expect(fc.features[0].properties).toMatchObject({ story: 'black-death', step: 5, title: 'The Black Death', color: '#991b1b' });
    expect(fc.features[1].properties?.color).toBe(NEUTRAL_COLOR);
    expect(fc.features[1].properties?.radius).toBeGreaterThan(fc.features[0].properties?.radius);
  });
});
