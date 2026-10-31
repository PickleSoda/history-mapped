import type { Map as MapLibreMap } from 'maplibre-gl';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ENTITY_GROUPS } from '@/types/atlas';
import {
  applyEntityLayerFilters,
  entityLayerFilter,
  entityTileSource,
  isMapTilesEnabled,
  isPoint,
  isPolygon,
} from './map-tiles';

afterEach(() => {
  vi.unstubAllEnvs();
});

/** The date window `entityLayerFilter` builds for [startDec, endDec]. */
const dateWindow = (startDec: number, endDec: number) => [
  'all',
  ['<=', ['to-number', ['get', 'start_decdate']], endDec],
  [
    'any',
    ['!', ['has', 'end_decdate']],
    ['>=', ['to-number', ['get', 'end_decdate']], startDec],
  ],
];

/** Swap the (float) decimal bounds for rounded ones so toEqual can compare. */
function rounded(filter: unknown): unknown {
  if (Array.isArray(filter)) return filter.map(rounded);
  if (typeof filter === 'number') return Math.round(filter * 1e5) / 1e5;
  return filter;
}

describe('isMapTilesEnabled', () => {
  it('is false when VITE_MAP_TILES_URL is unset or empty', () => {
    vi.stubEnv('VITE_MAP_TILES_URL', undefined);
    expect(isMapTilesEnabled()).toBe(false);
    vi.stubEnv('VITE_MAP_TILES_URL', '');
    expect(isMapTilesEnabled()).toBe(false);
  });

  it('is true when VITE_MAP_TILES_URL is set', () => {
    vi.stubEnv('VITE_MAP_TILES_URL', 'http://t/tiles');
    expect(isMapTilesEnabled()).toBe(true);
  });
});

describe('entityTileSource', () => {
  it('points the vector source at the atlas_entities function', () => {
    vi.stubEnv('VITE_MAP_TILES_URL', 'http://t/tiles');
    expect(entityTileSource()).toEqual({
      type: 'vector',
      tiles: ['http://t/tiles/atlas_entities/{z}/{x}/{y}'],
      minzoom: 0,
      maxzoom: 14,
    });
  });

  it('strips a trailing slash from the env value', () => {
    vi.stubEnv('VITE_MAP_TILES_URL', 'http://t/tiles/');
    expect(entityTileSource().tiles).toEqual([
      'http://t/tiles/atlas_entities/{z}/{x}/{y}',
    ]);
  });
});

describe('entityLayerFilter', () => {
  const instant = { kind: 'instant', year: 1066 } as const;

  it('combines the geometry filter with the year window', () => {
    const filter = entityLayerFilter({ geometry: 'point', time: instant, groups: [] });
    expect(rounded(filter)).toEqual(['all', isPoint, dateWindow(1066, 1067)]);
  });

  it('uses the polygon filter for fill and line layers', () => {
    const filter = entityLayerFilter({ geometry: 'polygon', time: instant, groups: [] });
    expect(rounded(filter)).toEqual(['all', isPolygon, dateWindow(1066, 1067)]);
  });

  it('adds an UPPERCASE group filter for a strict subset of groups', () => {
    const filter = entityLayerFilter({
      geometry: 'point',
      time: instant,
      groups: ['polity'],
    });
    expect(rounded(filter)).toEqual([
      'all',
      isPoint,
      dateWindow(1066, 1067),
      ['in', ['get', 'entity_group'], ['literal', ['POLITY']]],
    ]);
  });

  it('adds no group filter when every group is selected', () => {
    const filter = entityLayerFilter({
      geometry: 'point',
      time: instant,
      groups: [...ENTITY_GROUPS],
    });
    expect(rounded(filter)).toEqual(['all', isPoint, dateWindow(1066, 1067)]);
  });

  it('spans the whole range for a range time', () => {
    const filter = entityLayerFilter({
      geometry: 'point',
      time: { kind: 'range', start: 1000, end: 1100 },
      groups: [],
    });
    expect(rounded(filter)).toEqual(['all', isPoint, dateWindow(1000, 1101)]);
  });
});

describe('applyEntityLayerFilters', () => {
  it('sets a filter on each entity layer that exists', () => {
    type LayerMap = Pick<MapLibreMap, 'getLayer' | 'setFilter'>;
    const setFilter = vi.fn();
    const map: LayerMap = {
      // Only the layer's presence matters here, not the StyleLayer itself.
      getLayer: (id) =>
        id === 'line' ? undefined : ({ id } as ReturnType<LayerMap['getLayer']>),
      setFilter,
    };

    applyEntityLayerFilters(map, {
      layers: { fill: 'fill', line: 'line', symbol: 'symbol' },
      time: { kind: 'instant', year: 1066 },
      groups: [],
    });

    expect(setFilter.mock.calls.map(([id]) => id)).toEqual(['fill', 'symbol']);
    expect(rounded(setFilter.mock.calls[0]![1])).toEqual([
      'all',
      isPolygon,
      dateWindow(1066, 1067),
    ]);
    expect(rounded(setFilter.mock.calls[1]![1])).toEqual([
      'all',
      isPoint,
      dateWindow(1066, 1067),
    ]);
  });
});
