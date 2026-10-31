import type { Map as MapLibreMap } from 'maplibre-gl';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { isPoint } from './map-tiles';
import {
  LINK_COLOR,
  NO_EMPHASIS,
  OHM_ADMIN_FILL_LAYER,
  OHM_ADMIN_LINE_LAYER,
  OhmCorrelation,
  addOhmAdminLayers,
  applyEmphasis,
  centroidLayerIds,
  diffLinkedState,
  hoverMarkerFilter,
  linkIndexFromFeatures,
  linkedLabelColor,
  syncLinkedLabels,
} from './ohm-highlight';

type Call = [string, ...unknown[]];

/** A fake map that records the calls the highlight helpers make. */
function fakeMap({
  layers = [OHM_ADMIN_FILL_LAYER, OHM_ADMIN_LINE_LAYER],
  sources = ['ohm', 'ohm_admin'],
  styleLayers = [] as { id: string; type: string; source?: string; sourceLayer?: string }[],
  rendered = [] as unknown[],
} = {}) {
  const calls: Call[] = [];
  const present = new Set([...layers, ...styleLayers.map((l) => l.id)]);
  const map = {
    calls,
    getLayer: (id: string) =>
      present.has(id) ? (styleLayers.find((l) => l.id === id) ?? { id }) : undefined,
    getSource: (id: string) => (sources.includes(id) ? { id } : undefined),
    getLayersOrder: () => styleLayers.map((l) => l.id),
    setFeatureState: (...args: unknown[]) => calls.push(['setFeatureState', ...args]),
    removeFeatureState: (...args: unknown[]) => calls.push(['removeFeatureState', ...args]),
    setLayoutProperty: (...args: unknown[]) => calls.push(['setLayoutProperty', ...args]),
    addLayer: (...args: unknown[]) => {
      present.add((args[0] as { id: string }).id);
      calls.push(['addLayer', ...args]);
    },
    queryRenderedFeatures: vi.fn(() => rendered),
  };
  return map as typeof map & MapLibreMap;
}

const ADMIN = { source: 'ohm_admin', sourceLayer: 'boundaries' };
const LABEL = { source: 'ohm', sourceLayer: 'land_ohm_centroids' };

describe('linkIndexFromFeatures', () => {
  it('indexes tile features by their signed ohm_osm_id', () => {
    const index = linkIndexFromFeatures([
      { properties: { id: 'rome', ohm_osm_id: -1880 } },
      { properties: { id: 'paris', ohm_osm_id: 42 } },
    ]);
    expect([...index]).toEqual([
      [-1880, 'rome'],
      [42, 'paris'],
    ]);
  });

  it('signs REST features from ohm_external_type + ohm_external_id', () => {
    const index = linkIndexFromFeatures([
      { properties: { id: 'rome', ohm_external_type: 'relation', ohm_external_id: '1880' } },
      { properties: { id: 'paris', ohm_external_type: 'node', ohm_external_id: '42' } },
      { properties: { id: 'wall', ohm_external_type: 'way', ohm_external_id: '7' } },
    ]);
    expect(index.get(-1880)).toBe('rome');
    expect(index.get(42)).toBe('paris');
    expect(index.get(7)).toBe('wall');
  });

  it('ignores features without a link or an entity id', () => {
    const index = linkIndexFromFeatures([
      { properties: { id: 'nolink', ohm_osm_id: null, ohm_external_id: null } },
      { properties: { id: 'zero', ohm_osm_id: 0 } },
      { properties: { id: 'badtype', ohm_external_type: 'area', ohm_external_id: '9' } },
      { properties: { ohm_osm_id: -5 } },
      { properties: null },
      {},
    ]);
    expect(index.size).toBe(0);
  });

  it('keeps the first entity when several features share an osm id', () => {
    const index = linkIndexFromFeatures([
      { properties: { id: 'a', ohm_osm_id: -1 } },
      { properties: { id: 'b', ohm_osm_id: -1 } },
    ]);
    expect(index.get(-1)).toBe('a');
  });
});

describe('diffLinkedState', () => {
  it('returns the ids to add and to remove', () => {
    expect(diffLinkedState(new Set([1, 2, 3]), new Set([2, 3, 4]))).toEqual({
      add: [4],
      remove: [1],
    });
  });

  it('is empty when nothing changed', () => {
    expect(diffLinkedState(new Set([1]), new Set([1]))).toEqual({ add: [], remove: [] });
  });
});

describe('syncLinkedLabels', () => {
  it('sets `linked` on new label ids and removes it from dropped ones', () => {
    const map = fakeMap();
    const next = syncLinkedLabels(
      map,
      new Map([
        [-2, 'b'],
        [-3, 'c'],
      ]),
      new Set([-1, -2]),
    );
    expect([...next].sort()).toEqual([-2, -3].sort());
    expect(map.calls).toEqual([
      ['removeFeatureState', { ...LABEL, id: -1 }, 'linked'],
      ['setFeatureState', { ...LABEL, id: -3 }, { linked: true }],
    ]);
  });

  it('does nothing without an OHM source (fallback basemap)', () => {
    const map = fakeMap({ sources: [] });
    const next = syncLinkedLabels(map, new Map([[-2, 'b']]), new Set());
    expect(next.size).toBe(0);
    expect(map.calls).toEqual([]);
  });
});

describe('applyEmphasis', () => {
  it('sets hover state on the polygon and shows both admin layers', () => {
    const map = fakeMap();
    const state = applyEmphasis(map, { hoverOsmId: -1880, selectedOsmId: null }, NO_EMPHASIS);
    expect(state).toEqual({ hoverOsmId: -1880, selectedOsmId: null });
    expect(map.calls).toEqual([
      ['setFeatureState', { ...ADMIN, id: -1880 }, { hover: true }],
      ['setLayoutProperty', OHM_ADMIN_FILL_LAYER, 'visibility', 'visible'],
      ['setLayoutProperty', OHM_ADMIN_LINE_LAYER, 'visibility', 'visible'],
    ]);
  });

  it('removes the state and hides the layers when nothing is emphasised', () => {
    const map = fakeMap();
    const prev = applyEmphasis(map, { hoverOsmId: -1880, selectedOsmId: null }, NO_EMPHASIS);
    map.calls.length = 0;
    const state = applyEmphasis(map, NO_EMPHASIS, prev);
    expect(state).toEqual(NO_EMPHASIS);
    expect(map.calls).toEqual([
      ['removeFeatureState', { ...ADMIN, id: -1880 }, 'hover'],
      ['setLayoutProperty', OHM_ADMIN_FILL_LAYER, 'visibility', 'none'],
      ['setLayoutProperty', OHM_ADMIN_LINE_LAYER, 'visibility', 'none'],
    ]);
  });

  it('keeps a selection while the hover moves away', () => {
    const map = fakeMap();
    const prev = { hoverOsmId: -1, selectedOsmId: -1 };
    applyEmphasis(map, { hoverOsmId: null, selectedOsmId: -1 }, prev);
    expect(map.calls).toEqual([
      ['removeFeatureState', { ...ADMIN, id: -1 }, 'hover'],
      ['setLayoutProperty', OHM_ADMIN_FILL_LAYER, 'visibility', 'visible'],
      ['setLayoutProperty', OHM_ADMIN_LINE_LAYER, 'visibility', 'visible'],
    ]);
  });

  it('touches nothing when the admin layers are absent', () => {
    const map = fakeMap({ layers: [] });
    expect(applyEmphasis(map, { hoverOsmId: -1, selectedOsmId: null }, NO_EMPHASIS)).toEqual(
      NO_EMPHASIS,
    );
    expect(map.calls).toEqual([]);
  });
});

describe('addOhmAdminLayers', () => {
  it('adds hidden fill + line layers below the given layer', () => {
    const map = fakeMap({ layers: ['entities-fill'] });
    addOhmAdminLayers(map, 'entities-fill');
    const added = map.calls.filter((c) => c[0] === 'addLayer');
    expect(added.map((c) => [(c[1] as { id: string }).id, c[2]])).toEqual([
      [OHM_ADMIN_FILL_LAYER, 'entities-fill'],
      [OHM_ADMIN_LINE_LAYER, 'entities-fill'],
    ]);
    for (const [, spec] of added) {
      expect(spec).toMatchObject({
        source: 'ohm_admin',
        'source-layer': 'boundaries',
        layout: { visibility: 'none' },
      });
    }
  });

  it('adds nothing without the ohm_admin source', () => {
    const map = fakeMap({ layers: [], sources: ['ohm'] });
    addOhmAdminLayers(map, 'entities-fill');
    expect(map.calls).toEqual([]);
  });
});

describe('linkedLabelColor', () => {
  const linked = ['boolean', ['feature-state', 'linked'], false];

  it('wraps a plain colour in a feature-state case', () => {
    expect(linkedLabelColor('#495049')).toEqual(['case', linked, LINK_COLOR, '#495049']);
  });

  it('falls back to the dark label colour when the layer had none', () => {
    expect(linkedLabelColor(undefined)).toEqual(['case', linked, LINK_COLOR, '#2a2722']);
  });

  it('keeps a zoom interpolation top-level and wraps each stop output', () => {
    expect(
      linkedLabelColor(['interpolate', ['linear'], ['zoom'], 0, '#111', 5, '#222']),
    ).toEqual([
      'interpolate',
      ['linear'],
      ['zoom'],
      0,
      ['case', linked, LINK_COLOR, '#111'],
      5,
      ['case', linked, LINK_COLOR, '#222'],
    ]);
  });

  it('keeps a zoom step top-level and wraps each output', () => {
    expect(linkedLabelColor(['step', ['zoom'], '#111', 6, '#222'])).toEqual([
      'step',
      ['zoom'],
      ['case', linked, LINK_COLOR, '#111'],
      6,
      ['case', linked, LINK_COLOR, '#222'],
    ]);
  });

  it('leaves a legacy function object alone', () => {
    const legacy = { stops: [[0, '#111']] };
    expect(linkedLabelColor(legacy)).toBe(legacy);
  });
});

describe('centroidLayerIds', () => {
  it('lists the OHM label-point symbol layers in style order', () => {
    const map = fakeMap({
      styleLayers: [
        { id: 'country', type: 'symbol', source: 'ohm', sourceLayer: 'land_ohm_centroids' },
        { id: 'lines', type: 'line', source: 'ohm', sourceLayer: 'land_ohm_lines' },
        { id: 'places', type: 'symbol', source: 'ohm', sourceLayer: 'place_points_centroids' },
        { id: 'state', type: 'symbol', source: 'ohm', sourceLayer: 'land_ohm_centroids' },
      ],
    });
    expect(centroidLayerIds(map)).toEqual(['country', 'state']);
  });
});

describe('hoverMarkerFilter', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('matches the hovered entity among points (GeoJSON mode)', () => {
    vi.stubEnv('VITE_MAP_TILES_URL', '');
    expect(
      hoverMarkerFilter({ hoverId: 'rome', time: { kind: 'instant', year: 100 }, groups: [] }),
    ).toEqual(['all', isPoint, ['==', ['get', 'id'], 'rome']]);
  });

  it('matches nothing when nothing is hovered', () => {
    vi.stubEnv('VITE_MAP_TILES_URL', '');
    expect(
      hoverMarkerFilter({ hoverId: null, time: { kind: 'instant', year: 100 }, groups: [] }),
    ).toEqual(['all', isPoint, ['==', ['get', 'id'], '']]);
  });

  it('also applies the time window in tile mode (tiles carry every period)', () => {
    vi.stubEnv('VITE_MAP_TILES_URL', 'http://t/tiles');
    const filter = hoverMarkerFilter({
      hoverId: 'rome',
      time: { kind: 'instant', year: 100 },
      groups: [],
    }) as unknown[];
    expect(filter[0]).toBe('all');
    expect(filter[2]).toEqual(['==', ['get', 'id'], 'rome']);
    expect(JSON.stringify(filter[1])).toContain('start_decdate');
  });
});

describe('OhmCorrelation', () => {
  it('maps hovered / selected entity ids to their OHM polygons', () => {
    const map = fakeMap();
    const correlation = new OhmCorrelation(map);
    correlation.setFeatures([{ properties: { id: 'rome', ohm_osm_id: -1880 } }]);
    map.calls.length = 0;

    correlation.emphasize('rome', null);
    expect(map.calls[0]).toEqual(['setFeatureState', { ...ADMIN, id: -1880 }, { hover: true }]);

    map.calls.length = 0;
    correlation.emphasize(null, 'unlinked');
    expect(map.calls).toEqual([
      ['removeFeatureState', { ...ADMIN, id: -1880 }, 'hover'],
      ['setLayoutProperty', OHM_ADMIN_FILL_LAYER, 'visibility', 'none'],
      ['setLayoutProperty', OHM_ADMIN_LINE_LAYER, 'visibility', 'none'],
    ]);
  });

  it('re-applies the last emphasis once the entity shows up in the features', () => {
    const map = fakeMap();
    const correlation = new OhmCorrelation(map);
    correlation.emphasize(null, 'rome');
    expect(map.calls.some((c) => c[0] === 'setFeatureState')).toBe(false);

    correlation.setFeatures([{ properties: { id: 'rome', ohm_osm_id: -1880 } }]);
    expect(map.calls).toContainEqual([
      'setFeatureState',
      { ...ADMIN, id: -1880 },
      { selected: true },
    ]);
  });

  it('resolves the entity under the pointer: our marker first, then a linked OHM label', () => {
    const styleLayers = [
      { id: 'country', type: 'symbol', source: 'ohm', sourceLayer: 'land_ohm_centroids' },
      { id: 'entities-symbols', type: 'symbol', source: 'entities' },
    ];
    const label = { id: -1880, layer: { id: 'country' }, properties: { osm_id: -1880 }, state: { linked: true } };
    const unlinked = { id: -9, layer: { id: 'country' }, properties: { osm_id: -9 }, state: {} };
    const marker = { layer: { id: 'entities-symbols' }, properties: { id: 'paris' }, state: {} };

    const onLabel = fakeMap({ styleLayers, rendered: [unlinked, label] });
    const correlation = new OhmCorrelation(onLabel);
    correlation.styleLoaded(null, null);
    correlation.setFeatures([{ properties: { id: 'rome', ohm_osm_id: -1880 } }]);
    expect(correlation.entityAt([1, 1], 'entities-symbols')).toBe('rome');
    expect(onLabel.queryRenderedFeatures).toHaveBeenCalledWith(
      [1, 1],
      { layers: ['entities-symbols', 'country'] },
    );

    const onMarker = fakeMap({ styleLayers, rendered: [marker, label] });
    const second = new OhmCorrelation(onMarker);
    second.styleLoaded(null, null);
    second.setFeatures([{ properties: { id: 'rome', ohm_osm_id: -1880 } }]);
    expect(second.entityAt([1, 1], 'entities-symbols')).toBe('paris');

    const onNothing = fakeMap({ styleLayers, rendered: [unlinked] });
    const third = new OhmCorrelation(onNothing);
    third.styleLoaded(null, null);
    expect(third.entityAt([1, 1], 'entities-symbols')).toBeNull();
  });

  it('forgets feature state on a style swap and re-syncs labels', () => {
    const map = fakeMap();
    const correlation = new OhmCorrelation(map);
    correlation.setFeatures([{ properties: { id: 'rome', ohm_osm_id: -1880 } }]);
    correlation.emphasize('rome', null);
    map.calls.length = 0;

    // The new style has none of the old state: set it again, remove nothing.
    correlation.styleLoaded('rome', null);
    expect(map.calls.filter((c) => c[0] === 'removeFeatureState')).toEqual([]);
    expect(map.calls).toContainEqual(['setFeatureState', { ...LABEL, id: -1880 }, { linked: true }]);
    expect(map.calls).toContainEqual(['setFeatureState', { ...ADMIN, id: -1880 }, { hover: true }]);
  });
});
